# Lĩnh vực 05: Quản Lý Bộ Nhớ
# Domain 05: Memory Management

> **Lĩnh vực:** Quản Lý Bộ Nhớ (Memory Management)
> **Số mẫu:** 12
> **Ngôn ngữ:** Rust
> **Ngày cập nhật:** 2026-02-18

---

## Tổng quan

Rust patterns liên quan đến quản lý bộ nhớ, allocation, và lifecycle. Rust loại bỏ garbage collector nhưng không loại bỏ mọi vấn đề bộ nhớ. Memory leak vẫn xảy ra (và là safe Rust), stack overflow vẫn xảy ra với recursion sâu, allocation thừa làm giảm throughput, và reference cycles qua `Arc` gây leak nghiêm trọng trong production. Domain này tập trung vào 12 anti-patterns phổ biến nhất khi quản lý bộ nhớ trong Rust — từ `mem::forget` leak đến custom allocator bugs, từ Vec grow patterns đến ZST confusion.

---

## Mục lục

| #  | Tên mẫu | Mức độ |
|----|---------|--------|
| MM-01 | Memory Leak Qua `mem::forget` | 🟠 HIGH |
| MM-02 | Stack Overflow Do Recursion | 🟠 HIGH |
| MM-03 | Vec Grow Liên Tục | 🟡 MEDIUM |
| MM-04 | String Allocation Thừa | 🟡 MEDIUM |
| MM-05 | Large Struct Trên Stack | 🟠 HIGH |
| MM-06 | Arc Overhead Khi Single-Threaded | 🟡 MEDIUM |
| MM-07 | Vòng Tham Chiếu Arc (Arc Cycles) | 🔴 CRITICAL |
| MM-08 | Drop Bomb (Panic Trong Drop) | 🟠 HIGH |
| MM-09 | Global Allocator Lỗi | 🔴 CRITICAL |
| MM-10 | Iterator Collect Thừa | 🟡 MEDIUM |
| MM-11 | Fragmentation Jemalloc | 🟡 MEDIUM |
| MM-12 | Zero-Size Type Confusion | 🟡 MEDIUM |

---

## MM-01: Memory Leak Qua `mem::forget`

### 1. Tên

**Memory Leak Qua `mem::forget`** (Intentional forget to skip drop)

### 2. Phân loại

- **Lĩnh vực:** Memory Management
- **Danh mục con:** Resource Leak / Drop Avoidance
- **Mã định danh:** MM-01

### 3. Mức nghiêm trọng

🟠 **HIGH** — `mem::forget` là safe Rust nhưng gây leak bộ nhớ, file handles, sockets, và mọi tài nguyên mà `Drop` trait quản lý. Trong long-running services, leak tích lũy dẫn đến OOM kill.

### 4. Vấn đề

`std::mem::forget` tiêu thụ ownership của giá trị nhưng KHÔNG gọi destructor (`drop`). Đây là safe function vì Rust không đảm bảo destructor luôn chạy (xem `Rc` cycle). Lập trình viên dùng `mem::forget` để tránh double-free khi làm FFI, nhưng thường quên rằng mọi tài nguyên bên trong cũng bị leak theo.

```
mem::forget(value) — vòng đời bộ nhớ:

  Stack                          Heap
  ┌──────────────┐              ┌──────────────────────┐
  │ value: MyObj  │─────────────▶│ data: Vec<u8>        │
  │ (ptr, len,   │              │ [72, 65, 4C, 4C, 4F] │
  │  capacity)   │              │ capacity = 1024      │
  └──────────────┘              └──────────────────────┘
         │                               │
  mem::forget(value)                     │
         │                               │
         ▼                               ▼
  Stack frame freed               Heap KHÔNG freed!
  (không gọi Drop)               ├─ Vec<u8>: 1024 bytes leaked
                                  ├─ File handle: leaked
                                  ├─ Socket: leaked
                                  └─ Mỗi lần gọi: +1024 bytes

  Sau 1 triệu lần: ~1GB leaked → OOM kill
```

**Nguyên nhân phổ biến:**
- FFI wrapper cần chuyển ownership sang C, dùng `mem::forget` để Rust không drop
- Tránh double-free khi tự quản lý memory layout
- `ManuallyDrop` không được biết đến hoặc hiểu sai

### 5. Phát hiện

**Dấu hiệu nhận biết:**
- `mem::forget` xuất hiện ngoài context FFI
- Giá trị bị forget chứa heap-allocated fields (Vec, String, Box)
- Không có comment giải thích tại sao forget là cần thiết
- Memory usage tăng dần theo thời gian trong production

```bash
# Tìm tất cả mem::forget usage
rg --type rust 'mem::forget\s*\(' -n

# Tìm std::mem::forget không qua use
rg --type rust 'std::mem::forget\s*\(' -n

# Tìm forget trên giá trị có heap data (Vec, String, Box, HashMap)
rg --type rust 'mem::forget\s*\(\s*\w+\s*\)' -B 5 | rg '(Vec|String|Box|HashMap|BTreeMap|Arc|Rc)'

# Tìm ManuallyDrop::new nhưng không có ManuallyDrop::drop
rg --type rust 'ManuallyDrop::new' --files-with-matches | xargs rg 'ManuallyDrop::drop'

# Monitor memory growth (Linux)
# watch -n 5 'ps -o rss,vsz,pid -p $(pgrep my_service)'
```

### 6. Giải pháp

```rust
// ❌ BAD: mem::forget gây leak heap data
use std::mem;

struct Connection {
    socket: std::net::TcpStream,
    buffer: Vec<u8>,
    metadata: String,
}

fn transfer_to_c_library(conn: Connection) -> *mut libc::c_void {
    let raw_fd = conn.socket.as_raw_fd();
    // LEAK! buffer (Vec<u8>) và metadata (String) bị leak
    // socket cũng bị leak vì Drop không chạy
    mem::forget(conn);
    // Chỉ truyền fd sang C, nhưng mất ~64KB buffer + metadata
    raw_fd as *mut libc::c_void
}

// Trong vòng lặp xử lý request:
fn handle_requests(listener: std::net::TcpListener) {
    for stream in listener.incoming().flatten() {
        let conn = Connection {
            socket: stream,
            buffer: vec![0u8; 65536],  // 64KB mỗi connection
            metadata: format!("conn-{}", uuid::Uuid::new_v4()),
        };
        let ptr = transfer_to_c_library(conn);
        // Mỗi request: +64KB leaked
        // 1000 req/s × 64KB = 64MB/s leaked → OOM trong vài phút
        unsafe { c_library_process(ptr); }
    }
}
```

```rust
// ✅ GOOD: Dùng ManuallyDrop + giải phóng thủ công từng field
use std::mem::ManuallyDrop;
use std::os::unix::io::IntoRawFd;

struct Connection {
    socket: std::net::TcpStream,
    buffer: Vec<u8>,
    metadata: String,
}

fn transfer_to_c_library(conn: Connection) -> *mut libc::c_void {
    // Lấy fd ra trước, socket consumed → không leak
    let raw_fd = conn.socket.into_raw_fd();
    // buffer và metadata được drop bình thường khi conn kết thúc scope
    // (socket đã move ra ngoài, chỉ buffer + metadata còn lại để drop)
    drop(conn.buffer);
    drop(conn.metadata);
    raw_fd as *mut libc::c_void
}

// ✅ GOOD: Nếu CẦN forget, dùng ManuallyDrop để kiểm soát từng field
fn transfer_buffer_to_c(mut conn: Connection) -> (*mut u8, usize) {
    let buffer = std::mem::take(&mut conn.buffer);  // lấy buffer ra
    let ptr = buffer.as_ptr() as *mut u8;
    let len = buffer.len();
    // Chỉ forget buffer (C sẽ free), conn.socket và metadata vẫn drop
    mem::forget(buffer);
    // conn dropped ở đây — socket closed, metadata freed
    (ptr, len)
}

// ✅ BEST: Dùng Box::into_raw cho FFI ownership transfer
fn connection_to_ffi(conn: Connection) -> *mut Connection {
    let boxed = Box::new(conn);
    Box::into_raw(boxed)  // C gọi connection_free() để giải phóng
}

/// # Safety
/// ptr phải được tạo bởi connection_to_ffi
#[no_mangle]
pub unsafe extern "C" fn connection_free(ptr: *mut Connection) {
    if !ptr.is_null() {
        let _ = Box::from_raw(ptr);  // Drop chạy đầy đủ
    }
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Mỗi `mem::forget` có comment giải thích TẠI SAO cần thiết
- [ ] Giá trị bị forget không chứa heap-allocated fields chưa giải phóng
- [ ] Xem xét `ManuallyDrop` thay vì `mem::forget`
- [ ] FFI transfer dùng `Box::into_raw` / `Box::from_raw` pattern
- [ ] Long-running service có memory monitoring (Prometheus, grafana)
- [ ] Có test kiểm tra memory không tăng sau N iterations

```bash
# Clippy lint cho mem::forget
cargo clippy -- -W clippy::mem_forget

# Miri detect leak (nightly only)
cargo +nightly miri test -- --test-threads=1

# Valgrind (Linux)
cargo build && valgrind --leak-check=full ./target/debug/my_app

# Custom test: kiểm tra memory không tăng
# Dùng jemalloc stats hoặc /proc/self/status trong test
```

```toml
# clippy.toml
mem-forget = "warn"
```

---

## MM-02: Stack Overflow Do Recursion

### 1. Tên

**Stack Overflow Do Recursion** (Deep recursion on limited stack)

### 2. Phân loại

- **Lĩnh vực:** Memory Management
- **Danh mục con:** Stack Management / Recursion
- **Mã định danh:** MM-02

### 3. Mức nghiêm trọng

🟠 **HIGH** — Default stack size chỉ 8MB (Linux) hoặc 1MB (Windows thread). Recursion sâu trên cây dữ liệu, JSON parsing, hoặc graph traversal gây crash process. Không thể catch stack overflow trong safe Rust.

### 4. Vấn đề

Mỗi lời gọi hàm đệ quy tạo một stack frame mới chứa local variables, return address, và saved registers. Với struct lớn trên stack hoặc recursion sâu, stack vượt quá giới hạn OS gây SIGSEGV (Linux) hoặc STATUS_STACK_OVERFLOW (Windows). Rust KHÔNG có tail call optimization (TCO) được đảm bảo.

```
Stack growth trong recursion (default 8MB):

  High address
  ┌────────────────────────────────┐ ← Stack limit (8MB)
  │  main() frame: 256 bytes      │
  ├────────────────────────────────┤
  │  parse_json() frame: 2KB      │  depth=0
  │  ├─ local buffer: [u8; 1024]  │
  │  └─ return addr, saved regs   │
  ├────────────────────────────────┤
  │  parse_json() frame: 2KB      │  depth=1
  ├────────────────────────────────┤
  │  parse_json() frame: 2KB      │  depth=2
  ├────────────────────────────────┤
  │         ... × 4000 ...        │
  ├────────────────────────────────┤
  │  parse_json() frame: 2KB      │  depth=4000
  │  Total: 4000 × 2KB = 8MB      │
  ├────────────────────────────────┤
  │  ████████ STACK OVERFLOW ████  │ ← SIGSEGV / abort
  └────────────────────────────────┘
  Low address (guard page)

  4000 levels × 2KB/frame = 8MB → CRASH
  Với JSON nested 5000 levels → guaranteed crash
```

**Nguyên nhân phổ biến:**
- Parse nested data (JSON, XML, AST) bằng recursive descent
- Tree/graph traversal không giới hạn depth
- Visitor pattern trên deep AST
- User-controlled input depth (untrusted JSON)

### 5. Phát hiện

**Dấu hiệu nhận biết:**
- Recursive function không có depth limit
- Pattern `fn f(...) { ... f(...) ... }` với user-controlled depth
- `thread 'main' has overflowed its stack` trong logs
- Process bị killed bởi SIGSEGV

```bash
# Tìm hàm đệ quy (gọi chính nó)
rg --type rust 'fn\s+(\w+)\s*\(' -n | while read line; do
  func_name=$(echo "$line" | rg -o 'fn\s+(\w+)' | rg -o '\w+$')
  file=$(echo "$line" | cut -d: -f1)
  rg --type rust "$func_name\s*\(" "$file" | wc -l | xargs -I{} test {} -gt 1 && echo "RECURSIVE: $line"
done

# Đơn giản hơn: tìm pattern self-call phổ biến
rg --type rust 'fn\s+(\w+).*\{' -A 20 | rg 'self\.\1\(|(\w+)\(\s*.*\.\1\('

# Tìm parse/visit/traverse không có depth parameter
rg --type rust 'fn\s+(parse|visit|traverse|walk|recurse)\w*\s*\(' | rg -v 'depth|limit|max_depth'

# Tìm thread::Builder::new().stack_size() — ai đó đã gặp vấn đề
rg --type rust 'stack_size\s*\('
```

### 6. Giải pháp

```rust
// ❌ BAD: Recursive JSON parser không giới hạn depth
use serde_json::Value;

fn count_depth(value: &Value) -> usize {
    match value {
        Value::Object(map) => {
            1 + map.values()
                .map(|v| count_depth(v))  // đệ quy không giới hạn!
                .max()
                .unwrap_or(0)
        }
        Value::Array(arr) => {
            1 + arr.iter()
                .map(|v| count_depth(v))  // tương tự
                .max()
                .unwrap_or(0)
        }
        _ => 0,
    }
}

// Attacker gửi JSON nested 10000 levels → CRASH
// {"a":{"a":{"a":{"a": ... }}}}

fn process_tree(node: &TreeNode) {
    println!("{}", node.name);
    for child in &node.children {
        process_tree(child);  // tree depth 50000 → crash
    }
}
```

```rust
// ✅ GOOD: Giới hạn depth + chuyển sang iterative khi có thể
use serde_json::Value;

const MAX_JSON_DEPTH: usize = 128;

fn count_depth_safe(value: &Value) -> Result<usize, &'static str> {
    count_depth_inner(value, 0)
}

fn count_depth_inner(value: &Value, current_depth: usize) -> Result<usize, &'static str> {
    if current_depth > MAX_JSON_DEPTH {
        return Err("JSON nesting depth exceeds maximum allowed");
    }
    match value {
        Value::Object(map) => {
            let max_child = map.values()
                .map(|v| count_depth_inner(v, current_depth + 1))
                .collect::<Result<Vec<_>, _>>()?
                .into_iter()
                .max()
                .unwrap_or(0);
            Ok(1 + max_child)
        }
        Value::Array(arr) => {
            let max_child = arr.iter()
                .map(|v| count_depth_inner(v, current_depth + 1))
                .collect::<Result<Vec<_>, _>>()?
                .into_iter()
                .max()
                .unwrap_or(0);
            Ok(1 + max_child)
        }
        _ => Ok(0),
    }
}

// ✅ BEST: Chuyển sang iterative bằng explicit stack
fn process_tree_iterative(root: &TreeNode) {
    let mut stack: Vec<&TreeNode> = vec![root];
    while let Some(node) = stack.pop() {
        println!("{}", node.name);
        // Push children in reverse order để giữ thứ tự duyệt
        for child in node.children.iter().rev() {
            stack.push(child);
        }
    }
    // Explicit stack trên heap → chỉ giới hạn bởi RAM, không bị stack overflow
}

// ✅ GOOD: Dùng stacker crate cho trường hợp cần giữ recursive style
fn deep_recursive_with_stacker(node: &TreeNode) {
    stacker::maybe_grow(32 * 1024, 1024 * 1024, || {
        // Tự động allocate thêm stack khi gần đầy
        println!("{}", node.name);
        for child in &node.children {
            deep_recursive_with_stacker(child);
        }
    });
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Mỗi recursive function có `max_depth` parameter hoặc check
- [ ] User-controlled input (JSON, XML) có depth limit TRƯỚC khi parse
- [ ] Tree/graph traversal dùng iterative + explicit stack cho production
- [ ] Thread stack size được cấu hình phù hợp nếu cần recursive
- [ ] Fuzzer test với deeply nested input

```bash
# Clippy không bắt được stack overflow — cần review thủ công

# Test với deeply nested JSON
python3 -c "print('{\"a\":' * 10000 + '1' + '}' * 10000)" | cargo run

# Dùng stacker crate
# Cargo.toml: stacker = "0.1"

# Tăng stack size cho thread cụ thể
# std::thread::Builder::new().stack_size(32 * 1024 * 1024).spawn(...)

# Fuzzing với cargo-fuzz
cargo install cargo-fuzz
cargo fuzz init
# Thêm test case với deeply nested structures
```

```toml
# Cargo.toml — stacker cho safe recursive functions
[dependencies]
stacker = "0.1"
```

---

## MM-03: Vec Grow Liên Tục

### 1. Tên

**Vec Grow Liên Tục** (Vec reallocates without pre-allocation)

### 2. Phân loại

- **Lĩnh vực:** Memory Management
- **Danh mục con:** Allocation / Performance
- **Mã định danh:** MM-03

### 3. Mức nghiêm trọng

🟡 **MEDIUM** — Không gây crash hay UB, nhưng Vec grow chiến lược doubling gây nhiều lần reallocate + memcpy khi không dùng `with_capacity`. Trong hot path xử lý hàng triệu items, overhead tích lũy đáng kể.

### 4. Vấn đề

`Vec::new()` bắt đầu với capacity 0. Khi push, Vec allocate 4, rồi 8, 16, 32, ... (doubling strategy). Mỗi lần grow phải: (1) allocate vùng nhớ mới, (2) memcpy toàn bộ data cũ sang, (3) free vùng cũ. Nếu biết trước kích thước, `Vec::with_capacity(n)` loại bỏ hoàn toàn overhead này.

```
Vec::new() + 1000 lần push:

  Push #  │ Capacity │ Reallocate? │ Bytes copied │ Total allocations
  ────────┼──────────┼─────────────┼──────────────┼──────────────────
  1       │ 0 → 4   │ YES         │ 0            │ 1
  5       │ 4 → 8   │ YES         │ 4 × size_of  │ 2
  9       │ 8 → 16  │ YES         │ 8 × size_of  │ 3
  17      │ 16 → 32 │ YES         │ 16 × size_of │ 4
  ...     │ ...     │ ...         │ ...          │ ...
  513     │ 512→1024│ YES         │ 512× size_of │ 10
  ────────┼──────────┼─────────────┼──────────────┼──────────────────
  Total   │ 1024    │ 10 lần     │ ~1023 × size │ 10 allocations

  Vec::with_capacity(1000):

  Push #  │ Capacity │ Reallocate? │ Bytes copied │ Total allocations
  ────────┼──────────┼─────────────┼──────────────┼──────────────────
  1-1000  │ 1000    │ NO          │ 0            │ 1
  ────────┼──────────┼─────────────┼──────────────┼──────────────────
  Total   │ 1000    │ 0 lần      │ 0            │ 1 allocation

  Tiết kiệm: 9 allocations + 1023× memcpy
```

### 5. Phát hiện

**Dấu hiệu nhận biết:**
- `Vec::new()` ngay trước vòng lặp push
- `let mut v = vec![];` theo sau bởi nhiều `v.push()`
- Hàm return `Vec<T>` mà biết trước kích thước từ input
- Benchmark cho thấy allocation là bottleneck

```bash
# Tìm Vec::new() theo sau bởi push trong vòng lặp
rg --type rust 'Vec::new\(\)' -A 10 | rg 'push\('

# Tìm vec![] rỗng
rg --type rust 'let\s+mut\s+\w+\s*=\s*vec!\[\s*\]' -n

# Tìm Vec::new theo sau bởi for loop
rg --type rust 'Vec::new\(\)' -A 5 | rg 'for\s+\w+\s+in'

# Tìm hàm nhận &[T] hoặc Iterator và trả về Vec mà thiếu with_capacity
rg --type rust 'fn\s+\w+.*->.*Vec<' -A 15 | rg -v 'with_capacity|capacity'
```

### 6. Giải pháp

```rust
// ❌ BAD: Vec grow nhiều lần trong vòng lặp
fn parse_csv_records(csv_data: &str) -> Vec<Record> {
    let mut records = Vec::new();  // capacity = 0
    for line in csv_data.lines() {
        if let Ok(record) = parse_line(line) {
            records.push(record);  // grow: 0→4→8→16→32...
        }
    }
    records
}

fn collect_user_ids(users: &[User]) -> Vec<u64> {
    let mut ids = Vec::new();  // biết trước: users.len()!
    for user in users {
        ids.push(user.id);
    }
    ids
}

fn merge_sorted(a: &[i32], b: &[i32]) -> Vec<i32> {
    let mut result = Vec::new();  // biết trước: a.len() + b.len()
    let (mut i, mut j) = (0, 0);
    while i < a.len() && j < b.len() {
        if a[i] <= b[j] {
            result.push(a[i]);
            i += 1;
        } else {
            result.push(b[j]);
            j += 1;
        }
    }
    result.extend_from_slice(&a[i..]);
    result.extend_from_slice(&b[j..]);
    result
}
```

```rust
// ✅ GOOD: Pre-allocate với with_capacity
fn parse_csv_records(csv_data: &str) -> Vec<Record> {
    let line_count = csv_data.lines().count();
    let mut records = Vec::with_capacity(line_count);
    for line in csv_data.lines() {
        if let Ok(record) = parse_line(line) {
            records.push(record);
        }
    }
    records
}

fn collect_user_ids(users: &[User]) -> Vec<u64> {
    let mut ids = Vec::with_capacity(users.len());
    for user in users {
        ids.push(user.id);
    }
    ids
    // Hoặc đơn giản hơn:
    // users.iter().map(|u| u.id).collect()
    // (collect() tự dùng size_hint từ iterator!)
}

fn merge_sorted(a: &[i32], b: &[i32]) -> Vec<i32> {
    let mut result = Vec::with_capacity(a.len() + b.len());
    let (mut i, mut j) = (0, 0);
    while i < a.len() && j < b.len() {
        if a[i] <= b[j] {
            result.push(a[i]);
            i += 1;
        } else {
            result.push(b[j]);
            j += 1;
        }
    }
    result.extend_from_slice(&a[i..]);
    result.extend_from_slice(&b[j..]);
    result
    // Chính xác 1 allocation, 0 reallocate
}

// ✅ GOOD: Dùng iterator chain — collect() tự lấy size_hint
fn collect_user_ids_idiomatic(users: &[User]) -> Vec<u64> {
    users.iter().map(|u| u.id).collect()
    // collect() gọi size_hint() → (users.len(), Some(users.len()))
    // → allocate chính xác 1 lần
}

// ✅ GOOD: Shrink sau khi filter nếu kết quả nhỏ hơn nhiều
fn active_users(users: &[User]) -> Vec<&User> {
    let mut result: Vec<&User> = users.iter()
        .filter(|u| u.is_active)
        .collect();
    // Nếu chỉ 10% active → capacity thừa 90%
    if result.len() < result.capacity() / 2 {
        result.shrink_to_fit();
    }
    result
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Mỗi `Vec::new()` kiểm tra: có biết trước kích thước không?
- [ ] `Vec::with_capacity()` cho mọi trường hợp biết trước size
- [ ] Dùng `collect()` trên iterator có `size_hint()` chính xác
- [ ] Hot path dùng benchmark để so sánh allocation counts
- [ ] `shrink_to_fit()` sau filter nếu kết quả nhỏ hơn nhiều

```bash
# Clippy lint cho Vec::new thay vì with_capacity
cargo clippy -- -W clippy::uninit_vec

# Benchmark allocation
cargo bench -- --baseline before_optimization

# Dùng dhat (allocation profiler)
# Cargo.toml: dhat = "0.3"
# #[global_allocator] static ALLOC: dhat::Alloc = dhat::Alloc;
```

---

## MM-04: String Allocation Thừa

### 1. Tên

**String Allocation Thừa** (Unnecessary String allocation with format!)

### 2. Phân loại

- **Lĩnh vực:** Memory Management
- **Danh mục con:** Allocation / String Handling
- **Mã định danh:** MM-04

### 3. Mức nghiêm trọng

🟡 **MEDIUM** — `format!()` luôn tạo `String` mới trên heap. Trong vòng lặp hoặc hot path, hàng triệu String temporaries gây allocation pressure, tăng GC (nếu dùng jemalloc) và cache misses.

### 4. Vấn đề

`format!()` macro tạo mới `String` mỗi lần gọi. Khi cần ghi vào buffer có sẵn (file, network, log), `write!()` / `writeln!()` ghi trực tiếp mà không tạo intermediate String. Tương tự, `to_string()` trên types có `Display` cũng allocate.

```
format!() vs write!() — allocation flow:

  format!("user-{}-action-{}", user_id, action)
  ┌─────────────────────────────────────────┐
  │ 1. Allocate String::new()  (heap)       │
  │ 2. Write "user-" vào String             │
  │ 3. Write user_id.to_string() (THÊM 1   │
  │    allocation cho temp String!)          │
  │ 4. Write "-action-"                     │
  │ 5. Write action.to_string() (THÊM 1!)  │
  │ 6. Return String                        │
  │ = 3 heap allocations cho 1 format!      │
  └─────────────────────────────────────────┘

  write!(buffer, "user-{}-action-{}", user_id, action)
  ┌─────────────────────────────────────────┐
  │ 1. Write trực tiếp vào buffer có sẵn   │
  │ 2. Không allocation mới                 │
  │ = 0 heap allocations                    │
  └─────────────────────────────────────────┘

  Trong vòng lặp 1M iterations:
  format!: 3M allocations → ~100ms overhead
  write!:  0 allocations  → ~5ms
```

### 5. Phát hiện

**Dấu hiệu nhận biết:**
- `format!()` trong vòng lặp
- `format!()` kết quả chỉ được write vào file/socket/buffer
- `.to_string()` ngay trước `.as_bytes()` hoặc `write!()`
- Nhiều `format!` concatenation thay vì một `write!` chain

```bash
# Tìm format! trong vòng lặp
rg --type rust 'format!\(' -B 3 | rg '(for|while|loop)'

# Tìm format! mà kết quả chỉ dùng cho write
rg --type rust 'write.*format!\(' -n

# Tìm to_string() ngay trước as_bytes()
rg --type rust '\.to_string\(\)\s*\.as_bytes\(\)' -n

# Tìm format! concatenation patterns
rg --type rust 'let\s+\w+\s*=\s*format!' -A 2 | rg '(write|push_str|\.as_str)'

# Tìm String::new() + push_str pattern (nên dùng format! hoặc write!)
rg --type rust 'String::new\(\)' -A 5 | rg 'push_str'
```

### 6. Giải pháp

```rust
// ❌ BAD: format! tạo String mới mỗi lần trong vòng lặp
use std::io::Write;

fn write_log_entries(
    writer: &mut impl Write,
    entries: &[LogEntry],
) -> std::io::Result<()> {
    for entry in entries {
        // format! tạo String mới → heap allocation
        let line = format!(
            "[{}] {} - {}: {}\n",
            entry.timestamp,
            entry.level,
            entry.module,
            entry.message,
        );
        writer.write_all(line.as_bytes())?;
        // line dropped → String freed
        // 100K entries = 100K allocations + frees
    }
    Ok(())
}

fn build_sql_query(table: &str, columns: &[&str], filters: &[Filter]) -> String {
    let cols = columns.iter()
        .map(|c| format!("`{}`", c))  // N allocations cho mỗi column
        .collect::<Vec<_>>()
        .join(", ");  // +1 allocation cho join

    let where_clause = filters.iter()
        .map(|f| format!("{} {} ?", f.column, f.op))  // N allocations
        .collect::<Vec<_>>()
        .join(" AND ");  // +1 allocation

    format!("SELECT {} FROM `{}` WHERE {}", cols, table, where_clause)
    // +1 allocation cho final string
    // Total: 2N + 3 allocations
}
```

```rust
// ✅ GOOD: write! trực tiếp vào buffer, không tạo intermediate String
use std::io::Write;
use std::fmt::Write as FmtWrite;

fn write_log_entries(
    writer: &mut impl Write,
    entries: &[LogEntry],
) -> std::io::Result<()> {
    // Reuse buffer giữa các entries
    let mut line_buf = String::with_capacity(256);
    for entry in entries {
        line_buf.clear();  // reset length, giữ capacity
        write!(
            &mut line_buf,
            "[{}] {} - {}: {}\n",
            entry.timestamp,
            entry.level,
            entry.module,
            entry.message,
        ).expect("String write cannot fail");
        writer.write_all(line_buf.as_bytes())?;
    }
    // 1 allocation (ban đầu), reuse cho 100K entries
    Ok(())
}

fn build_sql_query(table: &str, columns: &[&str], filters: &[Filter]) -> String {
    // Estimate capacity upfront
    let estimated_len = 30 + table.len()
        + columns.iter().map(|c| c.len() + 3).sum::<usize>()
        + filters.iter().map(|f| f.column.len() + f.op.len() + 5).sum::<usize>();

    let mut query = String::with_capacity(estimated_len);
    query.push_str("SELECT ");

    for (i, col) in columns.iter().enumerate() {
        if i > 0 { query.push_str(", "); }
        query.push('`');
        query.push_str(col);
        query.push('`');
    }

    write!(&mut query, " FROM `{}` WHERE ", table)
        .expect("String write cannot fail");

    for (i, filter) in filters.iter().enumerate() {
        if i > 0 { query.push_str(" AND "); }
        write!(&mut query, "{} {} ?", filter.column, filter.op)
            .expect("String write cannot fail");
    }

    query
    // 1 allocation total (hoặc 0 nếu estimated_len đủ)
}

// ✅ GOOD: Dùng Cow<str> để tránh allocation khi không cần thiết
use std::borrow::Cow;

fn normalize_path(path: &str) -> Cow<'_, str> {
    if path.contains("//") {
        // Chỉ allocate khi thực sự cần thay đổi
        Cow::Owned(path.replace("//", "/"))
    } else {
        // Không thay đổi → trả về borrow, 0 allocation
        Cow::Borrowed(path)
    }
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] `format!()` trong vòng lặp → đổi sang `write!()` + buffer reuse
- [ ] Kết quả `format!()` chỉ dùng cho `write_all()` → dùng `write!()` trực tiếp
- [ ] `.to_string()` + `.as_bytes()` → dùng `Display` trait trực tiếp
- [ ] Nhiều String concatenation → dùng `String::with_capacity()` + `push_str()`
- [ ] Return `Cow<str>` thay vì `String` khi có thể trả về borrow

```bash
# Clippy lints
cargo clippy -- \
  -W clippy::format_in_format_args \
  -W clippy::to_string_in_format_args \
  -W clippy::format_push_string \
  -W clippy::manual_string_new

# Benchmark string allocation
cargo bench -- string_benchmark
```

---

## MM-05: Large Struct Trên Stack

### 1. Tên

**Large Struct Trên Stack** (Large struct on stack causes overflow)

### 2. Phân loại

- **Lĩnh vực:** Memory Management
- **Danh mục con:** Stack Management / Struct Layout
- **Mã định danh:** MM-05

### 3. Mức nghiêm trọng

🟠 **HIGH** — Struct chứa large array `[u8; 1048576]` hoặc deeply nested types trên stack chiếm hàng MB. Kết hợp với recursion hoặc thread stack nhỏ, gây stack overflow ngay lần gọi đầu tiên.

### 4. Vấn đề

Rust để tất cả local variables trên stack theo mặc định. Struct lớn (chứa fixed-size arrays, embedded buffers) chiếm toàn bộ trên stack frame. Khi truyền by-value giữa các hàm, compiler có thể copy toàn bộ (nếu không tối ưu thành move). Đặc biệt nguy hiểm khi dùng trong recursive functions hoặc threads với stack nhỏ.

```
Large struct trên stack:

  fn process() {
      let config = AppConfig { ... };  // 2MB trên stack!
  }

  Stack layout:
  ┌──────────────────────────────────┐  ← Stack top (8MB limit)
  │ main() locals: ~1KB             │
  ├──────────────────────────────────┤
  │ process() locals:               │
  │ ┌────────────────────────────┐  │
  │ │ AppConfig {                │  │
  │ │   name: [u8; 256]    256B │  │
  │ │   buffer: [u8; 1MB]  1MB  │  │
  │ │   cache: [u8; 512KB] 512K │  │
  │ │   log: [u8; 256KB]  256K  │  │
  │ │ }                         │  │
  │ │ Total: ~2MB               │  │
  │ └────────────────────────────┘  │
  ├──────────────────────────────────┤
  │ Remaining: ~6MB                 │
  │ → Chỉ 3 lần gọi nữa = OVERFLOW│
  └──────────────────────────────────┘

  Trong thread với stack_size = 2MB:
  → process() gọi 1 lần = OVERFLOW ngay!
```

### 5. Phát hiện

**Dấu hiệu nhận biết:**
- Struct chứa `[u8; N]` với N > 4096
- `#[repr(C)]` struct với nhiều large fields
- Local variable có type chứa embedded arrays
- Stack overflow ngay khi gọi function (không cần recursion)

```bash
# Tìm large fixed-size arrays trong struct
rg --type rust '\[u8;\s*\d{4,}\]' -n

# Tìm array size > 65536 (64KB)
rg --type rust '\[\w+;\s*\d{5,}\]' -n

# Tìm struct có nhiều array fields
rg --type rust 'struct\s+\w+' -A 20 | rg '\[\w+;\s*\d+'

# Tìm const size lớn dùng cho arrays
rg --type rust 'const\s+\w+:\s*usize\s*=\s*\d{5,}' -n

# Kiểm tra size_of cho struct cụ thể (thêm vào test)
# assert!(std::mem::size_of::<MyStruct>() < 4096);
```

### 6. Giải pháp

```rust
// ❌ BAD: Struct 2MB trên stack
struct PacketParser {
    header: [u8; 256],
    payload: [u8; 1_048_576],  // 1MB trên stack!
    checksum_buffer: [u8; 65536],
    metadata: ParserMetadata,  // thêm vài KB
}

fn parse_packet(data: &[u8]) -> Result<Packet, Error> {
    let parser = PacketParser {
        header: [0u8; 256],
        payload: [0u8; 1_048_576],  // 1MB trên stack frame!
        checksum_buffer: [0u8; 65536],
        metadata: ParserMetadata::default(),
    };
    parser.parse(data)
}

// Stack overflow nếu gọi trong thread nhỏ hoặc recursive context

struct ImageProcessor {
    pixels: [u8; 4_194_304],  // 4MB — chắc chắn overflow
    width: u32,
    height: u32,
}
```

```rust
// ✅ GOOD: Heap-allocate large buffers bằng Box hoặc Vec
struct PacketParser {
    header: [u8; 256],          // nhỏ → OK trên stack
    payload: Box<[u8; 1_048_576]>,  // 1MB trên heap
    checksum_buffer: Vec<u8>,    // dynamic size trên heap
    metadata: ParserMetadata,
}

impl PacketParser {
    fn new() -> Self {
        Self {
            header: [0u8; 256],
            // Box::new([0u8; 1MB]) vẫn tạo trên stack trước!
            // Dùng vec! + into_boxed_slice để tránh
            payload: vec![0u8; 1_048_576]
                .into_boxed_slice()
                .try_into()
                .expect("size mismatch"),
            checksum_buffer: vec![0u8; 65536],
            metadata: ParserMetadata::default(),
        }
    }
}

// ✅ GOOD: Dùng Vec cho dynamic buffers
struct ImageProcessor {
    pixels: Vec<u8>,
    width: u32,
    height: u32,
}

impl ImageProcessor {
    fn new(width: u32, height: u32) -> Self {
        let pixel_count = (width as usize) * (height as usize) * 4; // RGBA
        Self {
            pixels: vec![0u8; pixel_count],  // heap-allocated
            width,
            height,
        }
    }
}

// ✅ GOOD: Box::new_zeroed cho large zero-initialized arrays (nightly)
// Hoặc dùng bytemuck/zeroed_box từ crates.io
fn create_large_buffer() -> Box<[u8; 1_048_576]> {
    // Stable workaround: allocate as Vec then convert
    let v: Vec<u8> = vec![0u8; 1_048_576];
    let boxed_slice = v.into_boxed_slice();
    // Safety: Vec đảm bảo layout tương thích
    unsafe {
        let raw = Box::into_raw(boxed_slice) as *mut [u8; 1_048_576];
        Box::from_raw(raw)
    }
}

// ✅ GOOD: Đảm bảo struct nhỏ với compile-time check
struct SmallConfig {
    name: String,        // 24 bytes (ptr + len + cap)
    port: u16,           // 2 bytes
    timeout_ms: u32,     // 4 bytes
}

const _: () = assert!(
    std::mem::size_of::<SmallConfig>() <= 64,
    "SmallConfig phải nhỏ hơn 64 bytes trên stack"
);
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Struct trên stack phải < 4KB (rule of thumb)
- [ ] Array `[T; N]` với `N * size_of::<T>() > 4096` → dùng `Vec<T>` hoặc `Box<[T; N]>`
- [ ] Compile-time assert cho critical struct sizes
- [ ] Thread spawn luôn set `stack_size` nếu xử lý large data
- [ ] Dùng `Vec::into_boxed_slice()` thay vì `Box::new([0; N])` cho large arrays

```bash
# Clippy lint
cargo clippy -- -W clippy::large_stack_arrays -W clippy::large_types_passed_by_value

# Kiểm tra size tại compile time
# const _: () = assert!(std::mem::size_of::<MyStruct>() < 4096);

# Miri có thể phát hiện stack overflow trong tests
cargo +nightly miri test

# Profile stack usage
# perf record -e page-faults cargo test
```

---

## MM-06: Arc Overhead Khi Single-Threaded

### 1. Tên

**Arc Overhead Khi Single-Threaded** (Using Arc when Rc suffices)

### 2. Phân loại

- **Lĩnh vực:** Memory Management
- **Danh mục con:** Smart Pointer / Performance
- **Mã định danh:** MM-06

### 3. Mức nghiêm trọng

🟡 **MEDIUM** — `Arc<T>` dùng atomic operations cho reference counting, chi phí ~10-20x so với `Rc<T>` non-atomic increment. Trong single-threaded code hoặc Tokio single-runtime, Arc overhead không cần thiết.

### 4. Vấn đề

`Arc<T>` (Atomic Reference Counting) dùng `AtomicUsize` cho strong/weak count — mỗi clone/drop gọi `fetch_add`/`fetch_sub` atomic instruction. Trên x86, atomic operations invalidate cache line trên tất cả CPU cores. Trong single-threaded code, `Rc<T>` dùng plain `usize` — clone/drop chỉ là increment/decrement thường, nhanh gấp nhiều lần.

```
Arc vs Rc — chi phí clone:

  Arc<T>::clone()
  ┌──────────────────────────────────────┐
  │ 1. atomic fetch_add(1, Relaxed)     │  ← CPU pipeline stall
  │ 2. Memory barrier (x86: implicit)   │  ← Cache line invalidate
  │ 3. ~10-20ns per clone               │
  └──────────────────────────────────────┘

  Rc<T>::clone()
  ┌──────────────────────────────────────┐
  │ 1. self.count += 1                  │  ← Plain ADD instruction
  │ 2. ~1-2ns per clone                 │
  └──────────────────────────────────────┘

  Trong event loop clone 1M lần/giây:
  Arc: 1M × 20ns = 20ms/s overhead
  Rc:  1M × 2ns  = 2ms/s overhead
  Chênh lệch: 18ms/s → 1.08s/phút → đáng kể cho latency-sensitive apps
```

### 5. Phát hiện

**Dấu hiệu nhận biết:**
- `Arc<T>` trong code chỉ chạy trên 1 thread
- `Arc<T>` trong single-threaded Tokio runtime (`current_thread`)
- `Arc<Mutex<T>>` khi không cần cross-thread sharing
- Module không có `Send`/`Sync` requirement nhưng dùng Arc

```bash
# Tìm Arc usage
rg --type rust 'Arc::new\(' -n

# Tìm Arc trong file không có thread/spawn/send/sync
rg --type rust 'Arc::new\(' --files-with-matches | while read f; do
  rg '(thread|spawn|Send|Sync|tokio.*multi)' "$f" > /dev/null || echo "SUSPECT: $f"
done

# Tìm Arc<Mutex> (có thể dùng Rc<RefCell> nếu single-threaded)
rg --type rust 'Arc<\s*Mutex<' -n

# Tìm Arc clone trong vòng lặp
rg --type rust '\.clone\(\)' -B 3 | rg 'Arc'
```

### 6. Giải pháp

```rust
// ❌ BAD: Arc trong single-threaded async runtime
use std::sync::Arc;
use tokio::sync::Mutex;

#[tokio::main(flavor = "current_thread")]  // single-threaded!
async fn main() {
    let config = Arc::new(Mutex::new(AppConfig::load()));
    let db_pool = Arc::new(DatabasePool::connect().await);

    // Tất cả chạy trên 1 thread, Arc overhead vô ích
    let handler = Arc::clone(&config);
    let db = Arc::clone(&db_pool);

    tokio::spawn(async move {
        // Vẫn trên cùng thread! Arc không cần thiết
        let cfg = handler.lock().await;
        process_request(&cfg, &db).await;
    });
}

// ❌ BAD: Arc cho shared state trong single module
struct EventBus {
    handlers: Vec<Arc<dyn Fn(&Event)>>,  // single-threaded event bus
}

impl EventBus {
    fn subscribe(&mut self, handler: Arc<dyn Fn(&Event)>) {
        self.handlers.push(handler);
    }
}
```

```rust
// ✅ GOOD: Rc + RefCell cho single-threaded code
use std::rc::Rc;
use std::cell::RefCell;

#[tokio::main(flavor = "current_thread")]
async fn main() {
    // Rc cho single-threaded Tokio runtime
    let config = Rc::new(RefCell::new(AppConfig::load()));
    let db_pool = Rc::new(DatabasePool::connect().await);

    let handler = Rc::clone(&config);
    let db = Rc::clone(&db_pool);

    // Dùng tokio::task::spawn_local thay vì spawn
    tokio::task::spawn_local(async move {
        let cfg = handler.borrow();
        process_request(&cfg, &db).await;
    });
}

// ✅ GOOD: Rc cho single-threaded event bus
struct EventBus {
    handlers: Vec<Rc<dyn Fn(&Event)>>,
}

impl EventBus {
    fn subscribe(&mut self, handler: Rc<dyn Fn(&Event)>) {
        self.handlers.push(handler);
    }

    fn emit(&self, event: &Event) {
        for handler in &self.handlers {
            handler(event);
        }
    }
}

// ✅ GOOD: Khi CẦN multi-threaded, dùng Arc nhưng document tại sao
/// Shared across multiple Tokio worker threads.
/// Arc required because `tokio::spawn` requires Send + 'static.
struct SharedState {
    inner: Arc<tokio::sync::RwLock<StateInner>>,
}

#[tokio::main]  // default: multi-thread flavor
async fn main() {
    let state = SharedState {
        inner: Arc::new(tokio::sync::RwLock::new(StateInner::new())),
    };
    // Arc cần thiết ở đây vì multi-threaded runtime
    for _ in 0..num_cpus::get() {
        let state = state.inner.clone();
        tokio::spawn(async move {
            // Chạy trên worker thread khác nhau
            let guard = state.read().await;
            process(&guard).await;
        });
    }
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Single-threaded runtime (`current_thread`) → dùng `Rc`, không `Arc`
- [ ] Module không cross-thread → `Rc<RefCell<T>>` thay vì `Arc<Mutex<T>>`
- [ ] Comment tại sao cần `Arc` khi dùng (vì multi-thread requirement)
- [ ] `spawn_local` cho single-threaded task thay vì `spawn`
- [ ] Benchmark Arc vs Rc nếu clone-heavy

```bash
# Clippy lint
cargo clippy -- -W clippy::rc_mutex

# Tìm Tokio flavor
rg --type rust 'tokio::main' -A 1 | rg 'flavor'

# Benchmark Arc vs Rc
# Dùng criterion::black_box để tránh optimize away
cargo bench -- arc_vs_rc
```

---

## MM-07: Vòng Tham Chiếu Arc (Arc Cycles)

### 1. Tên

**Vòng Tham Chiếu Arc** (Arc reference cycles cause memory leak)

### 2. Phân loại

- **Lĩnh vực:** Memory Management
- **Danh mục con:** Smart Pointer / Reference Cycle
- **Mã định danh:** MM-07

### 3. Mức nghiêm trọng

🔴 **CRITICAL** — `Arc` cycle giữ reference count > 0 mãi mãi, memory KHÔNG BAO GIỜ được giải phóng. Trong long-running services, mỗi cycle tạo permanent leak. Đây là bug nguy hiểm vì rất khó debug — memory tăng chậm, không có stack trace, không có error.

### 4. Vấn đề

`Arc<T>` (và `Rc<T>`) dùng reference counting để quyết định khi nào drop. Nếu A giữ Arc tới B và B giữ Arc tới A, cả hai đều có strong count >= 1 mãi mãi — không bao giờ drop. Kết hợp với `Mutex` hoặc `RefCell` bên trong, cycle có thể xảy ra ở runtime mà compiler không bắt được.

```
Arc cycle — reference count không bao giờ về 0:

  Tạo A và B:
  ┌──────────────┐         ┌──────────────┐
  │ Arc<Node> A  │         │ Arc<Node> B  │
  │ strong: 1    │         │ strong: 1    │
  │ next: None   │         │ next: None   │
  └──────────────┘         └──────────────┘

  Sau A.next = Some(Arc::clone(&B)) và B.next = Some(Arc::clone(&A)):
  ┌──────────────┐  next   ┌──────────────┐
  │ Arc<Node> A  │────────▶│ Arc<Node> B  │
  │ strong: 2    │◀────────│ strong: 2    │
  │              │  next   │              │
  └──────────────┘         └──────────────┘

  Drop cả A và B (ra khỏi scope):
  ┌──────────────┐  next   ┌──────────────┐
  │ Arc<Node> A  │────────▶│ Arc<Node> B  │
  │ strong: 1 !! │◀────────│ strong: 1 !! │  ← vẫn > 0!
  │ LEAKED       │  next   │ LEAKED       │  ← KHÔNG drop!
  └──────────────┘         └──────────────┘

  Cycle này tồn tại VĨ VIỄN trong heap cho đến khi process exit.
  N cycles = N × (size_of::<Node>() × 2) leaked MÃI MÃI.
```

### 5. Phát hiện

**Dấu hiệu nhận biết:**
- `Arc<Mutex<T>>` trong struct, và T cũng chứa `Arc` tham chiếu ngược
- Parent-child pattern nơi child giữ `Arc` tới parent
- Observer pattern nơi subject giữ Arc tới observer và ngược lại
- Memory tăng dần nhưng không có "leak" rõ ràng

```bash
# Tìm struct chứa Arc<Mutex<...>> chứa Arc
rg --type rust 'Arc<\s*Mutex<' -A 10 | rg 'Arc<'

# Tìm pattern: struct có field Arc và field trỏ ngược
rg --type rust 'struct\s+\w+' -A 20 | rg '(parent|owner|back_ref).*Arc'

# Tìm Arc::new trong vòng lặp hoặc repeated creation
rg --type rust 'Arc::new\(' -B 3 | rg '(for|while|loop|fn\s+new)'

# Tìm Weak usage (indicator ai đó đã biết vấn đề)
rg --type rust 'Weak<' -n

# Tìm struct có 2+ Arc fields (potential cycle)
rg --type rust 'struct\s+\w+' -A 15 | rg -c 'Arc<' | rg -v '^0$'
```

### 6. Giải pháp

```rust
// ❌ BAD: Arc cycle giữa parent và children
use std::sync::{Arc, Mutex};

struct TreeNode {
    value: String,
    parent: Option<Arc<Mutex<TreeNode>>>,    // Strong ref tới parent!
    children: Vec<Arc<Mutex<TreeNode>>>,      // Strong ref tới children
}

fn build_tree() -> Arc<Mutex<TreeNode>> {
    let root = Arc::new(Mutex::new(TreeNode {
        value: "root".to_string(),
        parent: None,
        children: vec![],
    }));

    let child = Arc::new(Mutex::new(TreeNode {
        value: "child".to_string(),
        parent: Some(Arc::clone(&root)),  // child → root (strong)
        children: vec![],
    }));

    root.lock().unwrap().children.push(Arc::clone(&child));  // root → child (strong)
    // CYCLE: root ←(strong)→ child
    // Khi root và child ra khỏi scope:
    // root strong_count = 1 (từ child.parent) → KHÔNG drop
    // child strong_count = 1 (từ root.children) → KHÔNG drop

    root  // Leaked permanently!
}

// ❌ BAD: Observer pattern với Arc cycle
struct EventEmitter {
    listeners: Vec<Arc<Mutex<dyn Listener>>>,
}

struct MyWidget {
    name: String,
    emitter: Arc<Mutex<EventEmitter>>,  // widget → emitter (strong)
}

impl Listener for MyWidget { /* ... */ }

fn setup() {
    let emitter = Arc::new(Mutex::new(EventEmitter { listeners: vec![] }));
    let widget = Arc::new(Mutex::new(MyWidget {
        name: "btn".to_string(),
        emitter: Arc::clone(&emitter),  // widget → emitter
    }));
    emitter.lock().unwrap().listeners.push(widget.clone());  // emitter → widget
    // CYCLE: widget ←→ emitter → LEAK
}
```

```rust
// ✅ GOOD: Weak reference phá vỡ cycle
use std::sync::{Arc, Mutex, Weak};

struct TreeNode {
    value: String,
    parent: Option<Weak<Mutex<TreeNode>>>,   // Weak ref tới parent!
    children: Vec<Arc<Mutex<TreeNode>>>,      // Strong ref tới children
}

fn build_tree() -> Arc<Mutex<TreeNode>> {
    let root = Arc::new(Mutex::new(TreeNode {
        value: "root".to_string(),
        parent: None,
        children: vec![],
    }));

    let child = Arc::new(Mutex::new(TreeNode {
        value: "child".to_string(),
        parent: Some(Arc::downgrade(&root)),  // Weak! Không tăng strong_count
        children: vec![],
    }));

    root.lock().unwrap().children.push(Arc::clone(&child));

    // Drop child: strong_count = 1 (từ root.children) → giữ
    // Drop root variable: strong_count = 0 → Drop root
    // → root.children drop → child strong_count = 0 → Drop child
    // → child.parent (Weak) → upgrade() = None → OK
    // → Tất cả freed!

    root
}

// ✅ GOOD: Truy cập parent qua Weak
fn get_parent_value(node: &Arc<Mutex<TreeNode>>) -> Option<String> {
    let guard = node.lock().unwrap();
    guard.parent.as_ref().and_then(|weak| {
        weak.upgrade().map(|parent_arc| {
            parent_arc.lock().unwrap().value.clone()
        })
    })
    // upgrade() trả về None nếu parent đã bị drop → safe
}

// ✅ GOOD: Observer pattern với Weak listeners
struct EventEmitter {
    listeners: Vec<Weak<Mutex<dyn Listener>>>,  // Weak!
}

impl EventEmitter {
    fn emit(&mut self, event: &Event) {
        // Clean up dead listeners và emit
        self.listeners.retain(|weak| {
            if let Some(listener) = weak.upgrade() {
                listener.lock().unwrap().on_event(event);
                true  // giữ
            } else {
                false  // listener đã drop, xóa khỏi list
            }
        });
    }

    fn subscribe(&mut self, listener: &Arc<Mutex<dyn Listener>>) {
        self.listeners.push(Arc::downgrade(listener));
    }
}

// ✅ GOOD: Arena allocation — tránh Arc hoàn toàn cho tree structures
// Dùng crate: typed-arena, bumpalo, slotmap
use slotmap::{SlotMap, DefaultKey};

struct ArenaTree {
    nodes: SlotMap<DefaultKey, ArenaNode>,
}

struct ArenaNode {
    value: String,
    parent: Option<DefaultKey>,  // Index, không phải pointer!
    children: Vec<DefaultKey>,
}
// Không có reference counting → không có cycle → không có leak
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Parent → children: `Arc` (strong), Child → parent: `Weak`
- [ ] Observer pattern: subject giữ `Weak<Observer>`, observer giữ `Arc<Subject>`
- [ ] Review mọi struct có 2+ Arc fields — check cycle possibility
- [ ] Xem xét arena allocation cho tree/graph structures
- [ ] Long-running services: monitor memory growth trend

```bash
# Clippy không bắt được Arc cycles — cần review thủ công

# Miri có thể detect leaked memory trong tests
cargo +nightly miri test -- --test-threads=1

# Valgrind
cargo build && valgrind --leak-check=full ./target/debug/my_app

# Test pattern: tạo N nodes, drop, kiểm tra Weak::upgrade() = None
# assert!(weak_ref.upgrade().is_none());

# Memory profiling cho long-running services
# heaptrack cargo run -- serve
# hoặc dùng jemalloc profiling
```

---

## MM-08: Drop Bomb (Panic Trong Drop)

### 1. Tên

**Drop Bomb** (Panic inside Drop implementation)

### 2. Phân loại

- **Lĩnh vực:** Memory Management
- **Danh mục con:** Drop / Panic Safety
- **Mã định danh:** MM-08

### 3. Mức nghiêm trọng

🟠 **HIGH** — Panic trong `Drop::drop()` khi đang unwind (do panic trước đó) gây **double panic** → process abort ngay lập tức. Không thể catch, không thể recover, service chết không có graceful shutdown.

### 4. Vấn đề

Khi Rust panic, nó bắt đầu unwinding stack — gọi `drop()` cho mọi local variable. Nếu một `drop()` implementation cũng panic (ví dụ: flush file fails, network disconnect fails), đó là panic-during-unwind. Rust KHÔNG HỖ TRỢ nested panic — process gọi `abort()` ngay lập tức.

```
Double panic — process abort flow:

  Thread execution:
  ┌──────────────────────────────────────────┐
  │ 1. some_function() panics               │
  │    → unwinding begins                   │
  ├──────────────────────────────────────────┤
  │ 2. Drop LocalVar_A → OK                 │
  │ 3. Drop LocalVar_B → OK                 │
  │ 4. Drop MyFileWriter → drop() {         │
  │         self.file.flush()               │
  │           → Err(BrokenPipe)             │
  │         .unwrap()  ← PANIC!             │
  │    }                                    │
  ├──────────────────────────────────────────┤
  │ 5. DOUBLE PANIC detected                │
  │    → std::process::abort()              │
  │    → SIGABRT                            │
  │    → NO graceful shutdown               │
  │    → NO cleanup                         │
  │    → NO error reporting                 │
  └──────────────────────────────────────────┘

  Hậu quả:
  - Database connections NOT returned to pool
  - Temp files NOT cleaned up
  - Metrics NOT flushed
  - Logs NOT written
```

### 5. Phát hiện

**Dấu hiệu nhận biết:**
- `impl Drop for X` chứa `.unwrap()`, `.expect()`, `panic!()`
- Drop gọi fallible operations (I/O, network, database)
- Process abort trong production mà không có panic message
- `thread panicked while panicking` trong stderr

```bash
# Tìm Drop impl chứa unwrap/expect/panic
rg --type rust 'impl\s+Drop\s+for' -A 30 | rg '(unwrap|expect|panic!)'

# Tìm Drop impl chứa I/O operations
rg --type rust 'impl\s+Drop\s+for' -A 30 | rg '(flush|close|write|send|shutdown)'

# Tìm Drop impl gọi hàm có thể fail
rg --type rust 'fn\s+drop\s*\(&mut\s+self\)' -A 20 | rg '(unwrap|expect|\?)'

# Tìm "thread panicked while panicking" trong logs
rg 'panicked while panicking' /var/log/

# Tìm Drop trait implementation
rg --type rust 'impl\s+Drop' -n
```

### 6. Giải pháp

```rust
// ❌ BAD: Panic trong Drop
struct BufferedWriter {
    file: std::fs::File,
    buffer: Vec<u8>,
}

impl Drop for BufferedWriter {
    fn drop(&mut self) {
        // flush() có thể fail → Err
        self.file.write_all(&self.buffer).unwrap();  // PANIC nếu I/O error!
        self.file.flush().unwrap();  // PANIC nếu disk full!
        // Nếu đang unwind từ panic khác → ABORT
    }
}

struct DatabaseConnection {
    conn: Connection,
    transaction_active: bool,
}

impl Drop for DatabaseConnection {
    fn drop(&mut self) {
        if self.transaction_active {
            // network error → panic → double panic nếu đang unwind
            self.conn.execute("ROLLBACK").unwrap();
        }
    }
}
```

```rust
// ✅ GOOD: Drop không bao giờ panic
struct BufferedWriter {
    file: std::fs::File,
    buffer: Vec<u8>,
}

impl BufferedWriter {
    /// Explicit flush — caller xử lý error
    fn flush(&mut self) -> std::io::Result<()> {
        self.file.write_all(&self.buffer)?;
        self.buffer.clear();
        self.file.flush()
    }
}

impl Drop for BufferedWriter {
    fn drop(&mut self) {
        // Best-effort flush, log lỗi thay vì panic
        if !self.buffer.is_empty() {
            if let Err(e) = self.file.write_all(&self.buffer) {
                eprintln!("WARNING: BufferedWriter drop failed to flush: {e}");
                // KHÔNG panic, KHÔNG unwrap
            }
            if let Err(e) = self.file.flush() {
                eprintln!("WARNING: BufferedWriter drop failed to flush: {e}");
            }
        }
    }
}

// ✅ GOOD: Explicit close method + Drop as safety net
struct DatabaseConnection {
    conn: Option<Connection>,  // Option để take() trong close()
    transaction_active: bool,
}

impl DatabaseConnection {
    /// Explicit close — caller handles error
    fn close(mut self) -> Result<(), DbError> {
        if let Some(conn) = self.conn.take() {
            if self.transaction_active {
                conn.execute("ROLLBACK")?;
            }
            conn.close()?;
        }
        Ok(())
    }
}

impl Drop for DatabaseConnection {
    fn drop(&mut self) {
        // Safety net — best-effort cleanup
        if let Some(conn) = self.conn.take() {
            if self.transaction_active {
                // Log nhưng không panic
                let _ = conn.execute("ROLLBACK");  // ignore result
            }
            let _ = conn.close();  // ignore result
        }
    }
}

// ✅ GOOD: Dùng std::thread::panicking() để biết đang unwind
impl Drop for ResourceGuard {
    fn drop(&mut self) {
        if std::thread::panicking() {
            // Đang unwind — TUYỆT ĐỐI KHÔNG panic
            let _ = self.cleanup();  // best-effort, ignore errors
            return;
        }
        // Không đang unwind — có thể log chi tiết hơn
        if let Err(e) = self.cleanup() {
            tracing::error!("ResourceGuard cleanup failed: {e}");
        }
    }
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] `Drop::drop()` KHÔNG BAO GIỜ chứa `unwrap()`, `expect()`, `panic!()`
- [ ] Fallible cleanup → explicit `close()` method, Drop chỉ là safety net
- [ ] Drop dùng `let _ = fallible_op();` để ignore errors
- [ ] Dùng `std::thread::panicking()` để detect unwind context
- [ ] Review mọi `impl Drop` trong codebase

```bash
# Clippy lint cho panic trong Drop
# (Clippy chưa có lint chuyên biệt, cần review thủ công)

# Grep pattern: Drop + unwrap
rg --type rust 'impl\s+Drop' -A 30 | rg '(\.unwrap\(\)|\.expect\(|panic!\()'

# Test double panic: force panic + panic-in-drop
# #[test]
# #[should_panic]
# fn test_no_double_panic() {
#     let _guard = MyGuard::new();
#     panic!("intentional");
#     // MyGuard::drop() must not panic
# }

# Kiểm tra process exit code (134 = SIGABRT = double panic)
cargo test 2>&1; echo "Exit code: $?"
```

---

## MM-09: Global Allocator Lỗi

### 1. Tên

**Global Allocator Lỗi** (Custom global allocator bugs corrupt heap)

### 2. Phân loại

- **Lĩnh vực:** Memory Management
- **Danh mục con:** Allocator / Heap Corruption
- **Mã định danh:** MM-09

### 3. Mức nghiêm trọng

🔴 **CRITICAL** — Custom global allocator có bug gây: heap corruption, use-after-free, double-free, hoặc returning overlapping memory regions. Mọi allocation trong process đều đi qua global allocator — bug ở đây ảnh hưởng toàn bộ program. Hậu quả không deterministic, khó reproduce.

### 4. Vấn đề

Rust cho phép thay thế default allocator bằng `#[global_allocator]`. Khi implement `GlobalAlloc` trait, phải đảm bảo: (1) returned pointer aligned đúng, (2) memory regions không overlap, (3) dealloc chỉ free memory do alloc cấp, (4) alloc trả về null khi hết memory. Bất kỳ violation nào gây undefined behavior mà compiler không thể phát hiện.

```
Global allocator flow — mọi allocation đi qua đây:

  Vec::new() ─────────┐
  String::new() ──────┤
  Box::new() ─────────┤
  HashMap::new() ─────┤       ┌─────────────────────┐
  Arc::new() ─────────┼──────▶│ #[global_allocator]  │
  format!() ──────────┤       │ CustomAlloc          │
  println!() ─────────┤       │                     │
  tracing::info!() ───┘       │ fn alloc(layout) {  │
                              │   // BUG ở đây      │
                              │   // → TOÀN BỘ      │
                              │   //   program      │
                              │   //   affected     │
                              │ }                   │
                              └─────────────────────┘

  Ví dụ bug: alignment sai
  ┌─────────────────────────────────────────────────┐
  │ Request: alloc(size=16, align=8)                │
  │ Return:  0x7fff1001  ← align=1, KHÔNG phải 8!  │
  │                                                 │
  │ Hậu quả:                                       │
  │ - SIMD instructions crash (require align=16)    │
  │ - Atomic operations UB (require natural align)  │
  │ - Struct field access → wrong offset            │
  └─────────────────────────────────────────────────┘
```

### 5. Phát hiện

**Dấu hiệu nhận biết:**
- `#[global_allocator]` trong codebase
- `unsafe impl GlobalAlloc for X`
- Random crashes, corrupted data, SIGSEGV at random locations
- Valgrind/ASAN báo invalid read/write ở heap
- Bug không reproducible (timing-dependent memory corruption)

```bash
# Tìm custom global allocator
rg --type rust '#\[global_allocator\]' -n

# Tìm GlobalAlloc implementation
rg --type rust 'impl\s+GlobalAlloc\s+for' -n

# Tìm unsafe trong allocator code
rg --type rust 'impl\s+GlobalAlloc' -A 30 | rg 'unsafe'

# Tìm alloc/dealloc implementation
rg --type rust 'fn\s+(alloc|dealloc|realloc)\s*\(' -n

# Kiểm tra xem có dùng well-tested allocator crate không
rg 'jemalloc\|mimalloc\|tikv-jemallocator' Cargo.toml
```

### 6. Giải pháp

```rust
// ❌ BAD: Custom allocator với bug alignment
use std::alloc::{GlobalAlloc, Layout};

struct BuggyAllocator;

unsafe impl GlobalAlloc for BuggyAllocator {
    unsafe fn alloc(&self, layout: Layout) -> *mut u8 {
        // BUG: libc::malloc không đảm bảo alignment > 16 bytes
        // Layout yêu cầu align=32 (ví dụ: AVX struct) → UB
        libc::malloc(layout.size()) as *mut u8
    }

    unsafe fn dealloc(&self, ptr: *mut u8, _layout: Layout) {
        libc::free(ptr as *mut libc::c_void);
    }

    unsafe fn realloc(&self, ptr: *mut u8, _layout: Layout, new_size: usize) -> *mut u8 {
        // BUG: realloc có thể return pointer với alignment khác!
        libc::realloc(ptr as *mut libc::c_void, new_size) as *mut u8
    }
}

#[global_allocator]
static ALLOC: BuggyAllocator = BuggyAllocator;

// ❌ BAD: Tracking allocator với data race
use std::sync::atomic::{AtomicUsize, Ordering};

struct TrackingAllocator {
    allocated: AtomicUsize,
    inner: std::alloc::System,
}

unsafe impl GlobalAlloc for TrackingAllocator {
    unsafe fn alloc(&self, layout: Layout) -> *mut u8 {
        let ptr = self.inner.alloc(layout);
        if !ptr.is_null() {
            // BUG: Ordering::Relaxed có thể gây accounting sai
            // trong multi-threaded, nhưng KHÔNG gây UB ở đây.
            // Bug thực sự: quên check alignment
            self.allocated.fetch_add(layout.size(), Ordering::Relaxed);
        }
        ptr
    }

    unsafe fn dealloc(&self, ptr: *mut u8, layout: Layout) {
        self.inner.dealloc(ptr, layout);
        // BUG: nếu ptr không phải do alloc cấp → double free
        // Không có validation!
        self.allocated.fetch_sub(layout.size(), Ordering::Relaxed);
    }
}
```

```rust
// ✅ GOOD: Dùng well-tested allocator crate
// Cargo.toml:
// [dependencies]
// tikv-jemallocator = "0.5"   # hoặc mimalloc = "0.1"

#[cfg(not(target_env = "msvc"))]
use tikv_jemallocator::Jemalloc;

#[cfg(not(target_env = "msvc"))]
#[global_allocator]
static GLOBAL: Jemalloc = Jemalloc;

// ✅ GOOD: Nếu CẦN custom allocator, wrap System allocator
use std::alloc::{GlobalAlloc, Layout, System};
use std::sync::atomic::{AtomicUsize, Ordering};

struct MonitoredAllocator {
    inner: System,
    total_allocated: AtomicUsize,
    total_deallocated: AtomicUsize,
    allocation_count: AtomicUsize,
}

impl MonitoredAllocator {
    const fn new() -> Self {
        Self {
            inner: System,
            total_allocated: AtomicUsize::new(0),
            total_deallocated: AtomicUsize::new(0),
            allocation_count: AtomicUsize::new(0),
        }
    }

    pub fn stats(&self) -> AllocStats {
        AllocStats {
            total_allocated: self.total_allocated.load(Ordering::Relaxed),
            total_deallocated: self.total_deallocated.load(Ordering::Relaxed),
            allocation_count: self.allocation_count.load(Ordering::Relaxed),
        }
    }
}

unsafe impl GlobalAlloc for MonitoredAllocator {
    unsafe fn alloc(&self, layout: Layout) -> *mut u8 {
        // Delegate hoàn toàn cho System — đã được kiểm chứng
        let ptr = self.inner.alloc(layout);
        if !ptr.is_null() {
            self.total_allocated.fetch_add(layout.size(), Ordering::Relaxed);
            self.allocation_count.fetch_add(1, Ordering::Relaxed);
        }
        ptr
    }

    unsafe fn dealloc(&self, ptr: *mut u8, layout: Layout) {
        // Delegate hoàn toàn cho System
        self.inner.dealloc(ptr, layout);
        self.total_deallocated.fetch_add(layout.size(), Ordering::Relaxed);
    }

    // KHÔNG override realloc — System.realloc đã xử lý alignment đúng
}

#[global_allocator]
static ALLOC: MonitoredAllocator = MonitoredAllocator::new();

pub struct AllocStats {
    pub total_allocated: usize,
    pub total_deallocated: usize,
    pub allocation_count: usize,
}

// ✅ GOOD: Dùng dhat cho allocation profiling (dev only)
#[cfg(feature = "dhat-heap")]
#[global_allocator]
static ALLOC: dhat::Alloc = dhat::Alloc;
```

### 7. Phòng ngừa

**Checklist:**
- [ ] KHÔNG viết custom GlobalAlloc trừ khi THẬT SỰ cần thiết
- [ ] Dùng `tikv-jemallocator`, `mimalloc`, hoặc `System` (default)
- [ ] Custom allocator chỉ wrap well-tested allocator (thêm monitoring)
- [ ] Test allocator với Miri (phát hiện UB)
- [ ] Test allocator với ASAN (Address Sanitizer)
- [ ] Benchmark với realistic workload trước khi deploy

```bash
# Miri test cho allocator correctness
MIRIFLAGS="-Zmiri-disable-isolation" cargo +nightly miri test

# Address Sanitizer (nightly)
RUSTFLAGS="-Z sanitizer=address" cargo +nightly test

# Valgrind
cargo build && valgrind --tool=memcheck ./target/debug/my_app

# Heaptrack — allocation profiling
heaptrack cargo run -- serve
heaptrack_gui heaptrack.my_app.*.gz
```

```toml
# Cargo.toml — allocator dependencies
[dependencies]
tikv-jemallocator = { version = "0.5", optional = true }
mimalloc = { version = "0.1", optional = true }

[features]
jemalloc = ["tikv-jemallocator"]
mimalloc-alloc = ["mimalloc"]
dhat-heap = ["dhat"]

[dev-dependencies]
dhat = "0.3"
```

---

## MM-10: Iterator Collect Thừa

### 1. Tên

**Iterator Collect Thừa** (Unnecessary collect when iterator suffices)

### 2. Phân loại

- **Lĩnh vực:** Memory Management
- **Danh mục con:** Allocation / Iterator
- **Mã định danh:** MM-10

### 3. Mức nghiêm trọng

🟡 **MEDIUM** — `.collect::<Vec<_>>()` allocates toàn bộ kết quả vào Vec trên heap. Khi chỉ cần iterate qua kết quả 1 lần (sum, count, any, all, find, for_each), collect tạo allocation không cần thiết. Đặc biệt lãng phí với data lớn — collect 10M items = 10M × size_of<T> heap.

### 4. Vấn đề

Iterator trong Rust là lazy — chúng không tính toán cho đến khi consumed. `.collect()` force-evaluates toàn bộ iterator vào collection. Nếu sau collect chỉ dùng `.iter().sum()` hoặc `.len()`, thì collect là hoàn toàn thừa — iterator chain đã có thể tính trực tiếp.

```
collect() thừa vs iterator chain:

  collect() rồi sum():
  ┌────────────────────────────────────────────────────┐
  │ data.iter()                                        │
  │   .filter(|x| x > 0)                              │
  │   .map(|x| x * 2)                                 │
  │   .collect::<Vec<_>>()  ← HEAP ALLOC (10M items!) │
  │   .iter()               ← iterate lại từ đầu      │
  │   .sum::<i64>()         ← cuối cùng chỉ cần sum   │
  └────────────────────────────────────────────────────┘
  Memory: 10M × 8 bytes = 80MB heap
  Steps: filter → map → collect → iterate → sum (2 passes)

  Iterator chain trực tiếp:
  ┌────────────────────────────────────────────────────┐
  │ data.iter()                                        │
  │   .filter(|x| x > 0)                              │
  │   .map(|x| x * 2)                                 │
  │   .sum::<i64>()    ← tính trực tiếp, 0 allocation │
  └────────────────────────────────────────────────────┘
  Memory: 0 bytes heap
  Steps: filter → map → sum (1 pass, streaming)
```

### 5. Phát hiện

**Dấu hiệu nhận biết:**
- `.collect::<Vec<_>>().iter()...` — collect rồi iterate lại
- `.collect::<Vec<_>>().len()` — collect chỉ để đếm
- `.collect::<Vec<_>>().is_empty()` — collect chỉ để check empty
- `.collect()` trước `.for_each()`
- Intermediate collect giữa 2 iterator chains

```bash
# Tìm collect() theo sau bởi iter()
rg --type rust '\.collect::<Vec<.*>>\(\)\s*\.\s*(iter|into_iter)\(' -n

# Tìm collect() theo sau bởi len/is_empty
rg --type rust '\.collect::<Vec<.*>>\(\)\s*\.\s*(len|is_empty)\(' -n

# Tìm collect rồi for_each
rg --type rust '\.collect::<Vec' -A 2 | rg '\.for_each\('

# Tìm collect rồi sum/count/any/all/find
rg --type rust '\.collect::<Vec' -A 2 | rg '\.(sum|count|any|all|find|min|max|fold)\('

# Tìm pattern: collect vào biến rồi chỉ dùng 1 lần
rg --type rust 'let\s+\w+\s*:\s*Vec<' -A 5 | rg '\.(iter|len|is_empty|first|last)\('
```

### 6. Giải pháp

```rust
// ❌ BAD: collect thừa — allocate Vec chỉ để iterate lại
fn total_revenue(orders: &[Order]) -> f64 {
    let completed: Vec<&Order> = orders.iter()
        .filter(|o| o.status == Status::Completed)
        .collect();  // allocate Vec<&Order>

    completed.iter()
        .map(|o| o.amount)
        .sum()  // chỉ cần sum!
}

fn has_admin(users: &[User]) -> bool {
    let admins: Vec<&User> = users.iter()
        .filter(|u| u.role == Role::Admin)
        .collect();  // allocate Vec<&User>

    !admins.is_empty()  // chỉ cần check 1 phần tử!
}

fn count_active(items: &[Item]) -> usize {
    let active: Vec<&Item> = items.iter()
        .filter(|i| i.is_active)
        .collect();  // allocate TOÀN BỘ active items

    active.len()  // chỉ cần đếm!
}

fn process_batch(records: &[Record]) -> Vec<ProcessedRecord> {
    let filtered: Vec<&Record> = records.iter()
        .filter(|r| r.is_valid())
        .collect();  // intermediate Vec

    let mapped: Vec<ProcessedRecord> = filtered.iter()
        .map(|r| process(r))
        .collect();  // final Vec — cái này CẦN

    mapped
    // 2 allocations thay vì 1
}
```

```rust
// ✅ GOOD: Iterator chain trực tiếp, không collect thừa
fn total_revenue(orders: &[Order]) -> f64 {
    orders.iter()
        .filter(|o| o.status == Status::Completed)
        .map(|o| o.amount)
        .sum()  // 0 allocation, 1 pass
}

fn has_admin(users: &[User]) -> bool {
    users.iter()
        .any(|u| u.role == Role::Admin)  // short-circuit: dừng ở admin đầu tiên
}

fn count_active(items: &[Item]) -> usize {
    items.iter()
        .filter(|i| i.is_active)
        .count()  // 0 allocation, 1 pass
}

fn process_batch(records: &[Record]) -> Vec<ProcessedRecord> {
    records.iter()
        .filter(|r| r.is_valid())
        .map(|r| process(r))
        .collect()  // 1 allocation — chỉ final result
}

// ✅ GOOD: Khi cần reuse filtered results nhiều lần → collect hợp lý
fn analyze_errors(logs: &[LogEntry]) -> ErrorReport {
    // Collect 1 lần vì dùng lại nhiều nơi
    let errors: Vec<&LogEntry> = logs.iter()
        .filter(|l| l.level == Level::Error)
        .collect();

    ErrorReport {
        total: errors.len(),
        by_module: group_by_module(&errors),
        latest: errors.last().copied(),
        sample: errors.iter().take(10).copied().collect(),
    }
}

// ✅ GOOD: Iterator adaptor thay vì collect + index
fn find_first_match(items: &[Item], query: &str) -> Option<&Item> {
    // ❌ let matches: Vec<&Item> = items.iter().filter(...).collect();
    //    matches.first()
    // ✅ Dùng find trực tiếp
    items.iter().find(|i| i.name.contains(query))
}

// ✅ GOOD: Dùng itertools cho complex operations mà không collect
use itertools::Itertools;

fn top_3_scores(students: &[Student]) -> Vec<f64> {
    students.iter()
        .map(|s| s.score)
        .sorted_by(|a, b| b.partial_cmp(a).unwrap())
        .take(3)
        .collect()  // collect chỉ 3 items, không toàn bộ
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Mỗi `.collect()` kiểm tra: kết quả có được iterate lại không?
- [ ] `.collect().len()` → `.count()`
- [ ] `.collect().is_empty()` → `.next().is_none()` hoặc `.any()`
- [ ] `.collect().iter().sum()` → `.sum()`
- [ ] `.collect().first()` → `.next()`
- [ ] Intermediate collect giữa chains → merge thành 1 chain
- [ ] Chỉ collect khi cần reuse result nhiều lần hoặc cần random access

```bash
# Clippy lints
cargo clippy -- \
  -W clippy::needless_collect \
  -W clippy::iter_overeager_cloned \
  -W clippy::flat_map_identity

# Benchmark collect vs iterator
cargo bench -- iterator_benchmark
```

---

## MM-11: Fragmentation Jemalloc

### 1. Tên

**Fragmentation Jemalloc** (Memory fragmentation in long-running services)

### 2. Phân loại

- **Lĩnh vực:** Memory Management
- **Danh mục con:** Allocator / Fragmentation
- **Mã định danh:** MM-11

### 3. Mức nghiêm trọng

🟡 **MEDIUM** — Long-running services (web servers, databases, queues) accumulate memory fragmentation: RSS (Resident Set Size) tăng dần dù logical usage không đổi. Jemalloc và system allocator đều bị, nhưng patterns khác nhau. Service chạy vài tuần có thể dùng 2-3x memory thực tế cần.

### 4. Vấn đề

Memory fragmentation xảy ra khi allocator không thể tái sử dụng freed memory do kích thước hoặc alignment không khớp. Trong Rust, patterns tạo fragmentation:
- Vec/String grow tạo chuỗi allocations kích thước 2^n
- Short-lived allocations xen kẽ long-lived allocations
- HashMap resize tạo large allocation rồi free cũ

```
Fragmentation trong long-running service:

  Thời điểm T=0 (khởi động):
  Heap: [████████████████████████████████] 100MB allocated
  RSS:  100MB
  Used: 100MB
  Frag: 0%

  Thời điểm T=1h (sau nhiều request):
  Heap: [██░░██░██░░░██░░██░░░░██░░██░░] 100MB allocated
  RSS:  200MB  ← OS thấy process dùng 200MB!
  Used: 100MB  ← thực tế chỉ cần 100MB
  Frag: 50%

  ██ = đang dùng (allocated, in-use)
  ░░ = đã free nhưng OS chưa lấy lại (fragmented holes)

  Tại sao OS không lấy lại?
  ┌──────────────────────────────────────────┐
  │ Page 4KB:                                │
  │ [FREE][USED][FREE][FREE][USED][FREE]     │
  │                                          │
  │ OS chỉ reclaim page nếu TOÀN BỘ page    │
  │ đều free. 1 byte used = giữ cả 4KB page │
  └──────────────────────────────────────────┘
```

### 5. Phát hiện

**Dấu hiệu nhận biết:**
- RSS tăng dần theo thời gian mặc dù request rate ổn định
- `jemalloc_ctl::stats::resident` >> `jemalloc_ctl::stats::allocated`
- `/proc/PID/status` VmRSS tăng nhưng logic memory usage không đổi
- Service restart giảm memory đáng kể (fragmentation reset)

```bash
# Monitor RSS growth (Linux)
# watch -n 60 'grep VmRSS /proc/$(pgrep my_service)/status'

# Jemalloc stats (nếu đã enable)
# curl http://localhost:9090/debug/jemalloc/stats

# So sánh allocated vs resident
rg --type rust 'jemalloc_ctl' -n

# Tìm pattern gây fragmentation: HashMap clear + reuse
rg --type rust '\.clear\(\)' -B 3 | rg '(HashMap|Vec|String)'

# Tìm Vec/String grow patterns
rg --type rust '\.(push|extend|append)\(' -n | head -50

# Tìm tạo mới object trong vòng lặp (short-lived allocations)
rg --type rust '(String::new|Vec::new|HashMap::new)' -B 3 | rg '(for|while|loop)'
```

### 6. Giải pháp

```rust
// ❌ BAD: Pattern gây fragmentation cao
use std::collections::HashMap;

struct RequestHandler {
    // Mỗi request tạo mới HashMap → allocate → process → drop → fragment
}

impl RequestHandler {
    fn handle(&self, request: &Request) -> Response {
        // Tạo mới mỗi request → short-lived allocation
        let mut headers = HashMap::new();
        for (k, v) in &request.headers {
            headers.insert(k.to_lowercase(), v.clone());  // String alloc × N
        }

        // Tạo response body — short-lived String
        let body = format!("{{\"status\": \"ok\", \"request_id\": \"{}\"}}", request.id);

        // Tạo Vec mới mỗi lần — grow pattern
        let mut log_entries = Vec::new();
        for item in &request.items {
            log_entries.push(format!("Processed: {}", item.name));  // N allocations
        }

        // Khi hàm return: headers, body, log_entries drop
        // → fragments xen kẽ với long-lived data (connection pool, etc.)
        Response::new(body)
    }
}
```

```rust
// ✅ GOOD: Reuse buffers, pre-allocate, minimize short-lived allocations
use std::collections::HashMap;

struct RequestHandler {
    // Thread-local reusable buffers
    header_buf: HashMap<String, String>,
    body_buf: String,
    log_buf: Vec<String>,
}

impl RequestHandler {
    fn new() -> Self {
        Self {
            header_buf: HashMap::with_capacity(32),
            body_buf: String::with_capacity(4096),
            log_buf: Vec::with_capacity(64),
        }
    }

    fn handle(&mut self, request: &Request) -> Response {
        // Reuse HashMap — clear giữ capacity, không realloc
        self.header_buf.clear();
        for (k, v) in &request.headers {
            self.header_buf.insert(k.to_lowercase(), v.clone());
        }

        // Reuse String buffer
        self.body_buf.clear();
        use std::fmt::Write;
        write!(
            &mut self.body_buf,
            "{{\"status\": \"ok\", \"request_id\": \"{}\"}}",
            request.id
        ).expect("write to String cannot fail");

        // Reuse Vec buffer
        self.log_buf.clear();
        for item in &request.items {
            // Reuse String từ log_buf nếu có thể
            self.log_buf.push(format!("Processed: {}", item.name));
        }

        Response::new(self.body_buf.clone())
    }
}

// ✅ GOOD: Object pool cho frequently allocated types
use crossbeam::queue::ArrayQueue;

struct BufferPool {
    pool: ArrayQueue<Vec<u8>>,
    buffer_size: usize,
}

impl BufferPool {
    fn new(capacity: usize, buffer_size: usize) -> Self {
        let pool = ArrayQueue::new(capacity);
        for _ in 0..capacity {
            let _ = pool.push(Vec::with_capacity(buffer_size));
        }
        Self { pool, buffer_size }
    }

    fn acquire(&self) -> PooledBuffer<'_> {
        let mut buf = self.pool.pop()
            .unwrap_or_else(|| Vec::with_capacity(self.buffer_size));
        buf.clear();
        PooledBuffer { pool: self, buffer: Some(buf) }
    }
}

struct PooledBuffer<'a> {
    pool: &'a BufferPool,
    buffer: Option<Vec<u8>>,
}

impl<'a> Drop for PooledBuffer<'a> {
    fn drop(&mut self) {
        if let Some(buf) = self.buffer.take() {
            // Return to pool thay vì drop → giảm fragmentation
            let _ = self.pool.pool.push(buf);
        }
    }
}

impl<'a> std::ops::Deref for PooledBuffer<'a> {
    type Target = Vec<u8>;
    fn deref(&self) -> &Vec<u8> {
        self.buffer.as_ref().unwrap()
    }
}

impl<'a> std::ops::DerefMut for PooledBuffer<'a> {
    fn deref_mut(&mut self) -> &mut Vec<u8> {
        self.buffer.as_mut().unwrap()
    }
}

// ✅ GOOD: Jemalloc background thread + tuning
// Cargo.toml:
// tikv-jemallocator = { version = "0.5", features = ["background_threads"] }

#[cfg(not(target_env = "msvc"))]
#[global_allocator]
static GLOBAL: tikv_jemallocator::Jemalloc = tikv_jemallocator::Jemalloc;

// Tuning jemalloc for reduced fragmentation
// MALLOC_CONF="background_thread:true,dirty_decay_ms:1000,muzzy_decay_ms:1000"
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Reuse buffers (clear + reuse thay vì drop + new)
- [ ] Pre-allocate với `with_capacity` cho hot path
- [ ] Object pool cho frequently allocated large objects
- [ ] Jemalloc với `background_thread:true` cho better page reclamation
- [ ] Monitor RSS vs allocated ratio (fragmentation indicator)
- [ ] Periodic service restart nếu fragmentation > threshold

```bash
# Jemalloc stats endpoint
# Thêm vào service:
# pub fn jemalloc_stats() -> JemallocStats {
#     let allocated = tikv_jemalloc_ctl::stats::allocated::read().unwrap();
#     let resident = tikv_jemalloc_ctl::stats::resident::read().unwrap();
#     JemallocStats { allocated, resident, fragmentation: 1.0 - (allocated as f64 / resident as f64) }
# }

# Dùng heaptrack cho fragmentation analysis
heaptrack cargo run -- serve &
# ... run load test ...
heaptrack_gui heaptrack.*.gz

# Jemalloc tuning env var
export MALLOC_CONF="background_thread:true,dirty_decay_ms:1000,muzzy_decay_ms:1000"

# DHAT profiler cho allocation patterns
# Cargo.toml: dhat = "0.3"
```

---

## MM-12: Zero-Size Type Confusion

### 1. Tên

**Zero-Size Type Confusion** (Misunderstanding ZST allocation behavior)

### 2. Phân loại

- **Lĩnh vực:** Memory Management
- **Danh mục con:** Type System / ZST
- **Mã định danh:** MM-12

### 3. Mức nghiêm trọng

🟡 **MEDIUM** — Zero-Size Types (ZST) như `()`, `PhantomData<T>`, `struct Marker;` có `size_of::<T>() == 0`. Rust KHÔNG allocate memory cho chúng, và `Vec<ZST>` chỉ track length — không có actual heap data. Hiểu sai ZST gây bugs khi FFI, custom allocators, hoặc raw pointer arithmetic.

### 4. Vấn đề

ZST là types có kích thước 0 bytes. Rust xử lý chúng đặc biệt: `Box::new(())` trả về dangling pointer (không allocate), `Vec::<()>::with_capacity(1_000_000)` không allocate heap memory, và pointer arithmetic trên ZST luôn trả về cùng address. Lập trình viên không biết điều này có thể tạo bugs nghiêm trọng khi làm FFI hoặc unsafe code.

```
ZST behavior — không allocation:

  Các ZST phổ biến:
  - ()                     : unit type, 0 bytes
  - PhantomData<T>         : marker type, 0 bytes
  - struct Marker;         : empty struct, 0 bytes
  - [u8; 0]               : empty array, 0 bytes

  Vec<()> internal representation:
  ┌─────────────────────────────────────────────┐
  │ Vec<()> {                                   │
  │   ptr: NonNull::dangling(),  ← KHÔNG trỏ   │
  │                                 vào heap!   │
  │   len: 1_000_000,           ← track count  │
  │   cap: usize::MAX,         ← "infinite"    │
  │ }                                           │
  │                                             │
  │ Heap memory used: 0 bytes                   │
  │ (dù "chứa" 1 triệu elements)              │
  └─────────────────────────────────────────────┘

  So sánh với Vec<u8>:
  ┌─────────────────────────────────────────────┐
  │ Vec<u8> {                                   │
  │   ptr: 0x7fff_1234_0000, ← trỏ vào heap   │
  │   len: 1_000_000,                          │
  │   cap: 1_000_000,                          │
  │ }                                           │
  │                                             │
  │ Heap memory used: 1_000_000 bytes           │
  └─────────────────────────────────────────────┘
```

### 5. Phát hiện

**Dấu hiệu nhận biết:**
- `Vec<()>` hoặc `Vec<PhantomData<T>>` used — developer có biết không allocate?
- Raw pointer arithmetic trên ZST (luôn same address)
- FFI passing ZST — C side expects actual memory
- Custom allocator nhận `Layout { size: 0 }` — phải xử lý đặc biệt

```bash
# Tìm ZST usage
rg --type rust 'Vec<\s*\(\)\s*>' -n
rg --type rust 'Vec<\s*PhantomData' -n

# Tìm Box::new cho ZST
rg --type rust 'Box::new\(\s*\(\)\s*\)' -n

# Tìm pointer arithmetic trên ZST
rg --type rust '\.offset\(' -B 5 | rg 'PhantomData\|struct\s+\w+;'

# Tìm Layout::new::<T> với potential ZST
rg --type rust 'Layout::new::<' -n

# Tìm alloc gọi với size=0
rg --type rust 'Layout::from_size_align\s*\(\s*0' -n

# Tìm struct không có fields (= ZST)
rg --type rust 'struct\s+\w+\s*;' -n
```

### 6. Giải pháp

```rust
// ❌ BAD: Hiểu sai ZST — expect allocation khi không có
use std::marker::PhantomData;

struct Token;  // ZST: 0 bytes

fn allocate_tokens(count: usize) -> Vec<Token> {
    // Developer nghĩ: "allocate count tokens trên heap"
    // Thực tế: 0 bytes allocated, chỉ có len=count
    let mut tokens = Vec::with_capacity(count);
    for _ in 0..count {
        tokens.push(Token);
    }
    tokens
    // tokens.capacity() = usize::MAX (!)
    // heap usage = 0 bytes
}

// ❌ BAD: FFI truyền ZST pointer — C side dereference → UB
#[repr(C)]
struct EmptyHeader;  // 0 bytes trong Rust, nhưng C có thể expect >= 1 byte

extern "C" {
    fn process_header(header: *const EmptyHeader);
}

fn send_to_c() {
    let header = EmptyHeader;
    let ptr = &header as *const EmptyHeader;
    // ptr là dangling-ish — trỏ vào stack nhưng size = 0
    unsafe { process_header(ptr); }
    // C side: memcpy(dst, header, sizeof(EmptyHeader))
    // sizeof trong C >= 1 → đọc memory ngoài → UB
}

// ❌ BAD: Custom allocator không xử lý size=0
use std::alloc::{GlobalAlloc, Layout};

struct BadAlloc;
unsafe impl GlobalAlloc for BadAlloc {
    unsafe fn alloc(&self, layout: Layout) -> *mut u8 {
        // layout.size() có thể = 0 cho ZST!
        libc::malloc(layout.size()) as *mut u8
        // malloc(0) behavior là implementation-defined:
        // - Có thể return NULL
        // - Có thể return unique non-null pointer
        // Rust yêu cầu: alloc(size=0) PHẢI return non-null aligned pointer
        // hoặc NULL (để báo OOM) — nhưng KHÔNG BAO GIỜ được gọi!
    }

    unsafe fn dealloc(&self, ptr: *mut u8, layout: Layout) {
        libc::free(ptr as *mut libc::c_void);
        // Nếu ptr từ ZST alloc → free dangling pointer → UB
    }
}
```

```rust
// ✅ GOOD: Hiểu đúng ZST và sử dụng phù hợp
use std::marker::PhantomData;

// ZST làm type-level marker — ĐÚNG use case
struct Authenticated;
struct Anonymous;

struct Session<State> {
    user_id: Option<u64>,
    _state: PhantomData<State>,  // 0 bytes, chỉ cho type system
}

impl Session<Anonymous> {
    fn login(self, user_id: u64) -> Session<Authenticated> {
        Session {
            user_id: Some(user_id),
            _state: PhantomData,
        }
    }
}

impl Session<Authenticated> {
    fn get_user_id(&self) -> u64 {
        self.user_id.unwrap()  // safe: state machine đảm bảo có user_id
    }
}

// ✅ GOOD: Dùng HashSet thay vì Vec<ZST> nếu cần collection
use std::collections::HashSet;

fn track_events(event_ids: &[u64]) -> usize {
    // ❌ let markers: Vec<()> = event_ids.iter().map(|_| ()).collect();
    //    markers.len()  // chỉ cần count!

    // ✅ Nếu cần unique count:
    let unique: HashSet<u64> = event_ids.iter().copied().collect();
    unique.len()

    // ✅ Nếu chỉ cần total count:
    // event_ids.len()
}

// ✅ GOOD: FFI — không truyền ZST, dùng opaque pointer
#[repr(C)]
struct OpaqueHandle {
    _private: [u8; 1],  // Ít nhất 1 byte cho C compatibility
}

// ✅ GOOD: Custom allocator xử lý ZST đúng
use std::alloc::{GlobalAlloc, Layout, System};

struct SafeAlloc;

unsafe impl GlobalAlloc for SafeAlloc {
    unsafe fn alloc(&self, layout: Layout) -> *mut u8 {
        if layout.size() == 0 {
            // ZST: trả về aligned dangling pointer
            // KHÔNG gọi malloc(0)
            return layout.align() as *mut u8;
        }
        System.alloc(layout)
    }

    unsafe fn dealloc(&self, ptr: *mut u8, layout: Layout) {
        if layout.size() == 0 {
            // ZST: không có gì để free
            return;
        }
        System.dealloc(ptr, layout);
    }
}

// ✅ GOOD: assert size > 0 khi cần actual allocation
fn allocate_buffer<T>(count: usize) -> Vec<T> {
    assert!(
        std::mem::size_of::<T>() > 0,
        "allocate_buffer không hỗ trợ ZST — dùng counter thay thế"
    );
    Vec::with_capacity(count)
}

// ✅ GOOD: Document ZST behavior cho API users
/// Tạo pool of markers. Lưu ý: vì Marker là ZST,
/// pool KHÔNG allocate heap memory. Chỉ track count.
///
/// Nếu cần actual memory allocation, dùng `Vec<Box<dyn Any>>`.
fn create_marker_pool(count: usize) -> Vec<Marker> {
    vec![Marker; count]  // 0 bytes heap, len = count
}

struct Marker;
```

### 7. Phòng ngừa

**Checklist:**
- [ ] ZST dùng đúng mục đích: type-level marker, PhantomData, state machine
- [ ] KHÔNG expect heap allocation cho Vec/Box/Arc chứa ZST
- [ ] FFI struct PHẢI có ít nhất 1 byte (`[u8; 1]`) hoặc dùng opaque pointer
- [ ] Custom allocator xử lý `Layout.size() == 0` đặc biệt
- [ ] Document ZST behavior cho API consumers
- [ ] Raw pointer arithmetic trên ZST → KHÔNG dùng `.offset()`

```bash
# Clippy lint (limited ZST detection)
cargo clippy -- -W clippy::zero_sized_map_values

# Kiểm tra size_of cho types
# println!("Size: {}", std::mem::size_of::<MyType>());

# Miri detect ZST pointer UB
cargo +nightly miri test

# Tìm ZST trong codebase
rg --type rust 'struct\s+\w+\s*;' -n  # empty structs
rg --type rust 'PhantomData<' -n       # phantom data usage
```

---

## Tổng kết

### Bảng tham chiếu nhanh

| Mã | Pattern | Mức độ | Phòng ngừa chính |
|----|---------|--------|-------------------|
| MM-01 | mem::forget leak | 🟠 HIGH | ManuallyDrop, Box::into_raw |
| MM-02 | Stack overflow recursion | 🟠 HIGH | Iterative + explicit stack |
| MM-03 | Vec grow liên tục | 🟡 MEDIUM | with_capacity() |
| MM-04 | String allocation thừa | 🟡 MEDIUM | write!() + buffer reuse |
| MM-05 | Large struct on stack | 🟠 HIGH | Box, Vec, heap allocation |
| MM-06 | Arc single-threaded | 🟡 MEDIUM | Rc + RefCell |
| MM-07 | Arc cycles | 🔴 CRITICAL | Weak references, arena |
| MM-08 | Panic in Drop | 🟠 HIGH | No unwrap in drop, explicit close |
| MM-09 | Custom allocator bug | 🔴 CRITICAL | Use tested crates, Miri/ASAN |
| MM-10 | Collect thừa | 🟡 MEDIUM | Iterator chain trực tiếp |
| MM-11 | Jemalloc fragmentation | 🟡 MEDIUM | Buffer reuse, object pool |
| MM-12 | ZST confusion | 🟡 MEDIUM | Understand ZST, FFI compat |

### Công cụ phát hiện

| Công cụ | Phát hiện | Cách dùng |
|---------|-----------|-----------|
| `cargo clippy` | MM-01, 03, 05, 06, 10, 12 | `cargo clippy -- -W clippy::mem_forget -W clippy::large_stack_arrays` |
| `cargo +nightly miri test` | MM-01, 07, 09, 12 | Detect UB, leaks |
| Valgrind | MM-01, 07, 09 | `valgrind --leak-check=full ./target/debug/app` |
| ASAN | MM-09 | `RUSTFLAGS="-Z sanitizer=address" cargo +nightly test` |
| `dhat` | MM-03, 04, 10, 11 | Allocation profiling |
| `heaptrack` | MM-11 | Fragmentation analysis |
| `ripgrep` | All | Pattern scanning (xem từng section) |

### Quy tắc vàng

1. **Hiểu ownership = hiểu memory.** Rust's borrow checker quản lý phần lớn, nhưng `Arc` cycles, `mem::forget`, và custom allocators vượt khỏi tầm kiểm soát của compiler.

2. **Pre-allocate khi biết trước size.** `with_capacity()` cho Vec/String/HashMap loại bỏ hầu hết allocation overhead.

3. **Drop phải infallible.** Không bao giờ panic trong `Drop::drop()`. Dùng explicit `close()`/`flush()` method, drop chỉ là safety net.

4. **Weak phá vỡ cycles.** Parent → child dùng strong ref, child → parent dùng Weak. Hoặc dùng arena allocation.

5. **Monitor memory trong production.** RSS growth trend, fragmentation ratio, allocation rate — đo lường liên tục cho long-running services.
