# Lĩnh vực 01: Ownership Và Borrowing
# Domain 01: Ownership & Borrowing

> **Lĩnh vực:** Hệ thống Sở hữu và Mượn Tham chiếu
> **Số mẫu:** 15
> **Ngôn ngữ:** Rust
> **Ngày cập nhật:** 2026-02-18

---

## Tổng quan

Ownership và Borrowing là nền tảng của Rust — chúng thay thế garbage collector bằng các quy tắc tĩnh ở compile-time. Tuy nhiên, hiểu sai hoặc lách qua các quy tắc này dẫn đến: hiệu năng kém, undefined behavior, memory leak, hoặc code không thể maintain.

---

## Mục lục

| # | Tên mẫu | Mức độ |
|---|---------|--------|
| OB-01 | Clone Thừa Thãi | 🟡 MEDIUM |
| OB-02 | RefCell Lạm Dụng | 🟠 HIGH |
| OB-03 | Lifetime Elision Sai | 🟠 HIGH |
| OB-04 | Vòng Tham Chiếu Rc | 🔴 CRITICAL |
| OB-05 | Borrow Checker Bypass | 🔴 CRITICAL |
| OB-06 | Move Sau Borrow | 🟠 HIGH |
| OB-07 | String vs &str Confusion | 🟡 MEDIUM |
| OB-08 | Mutex Poisoning Bỏ Qua | 🟠 HIGH |
| OB-09 | Drop Order Bất Ngờ | 🟠 HIGH |
| OB-10 | Cow Không Dùng | 🟡 MEDIUM |
| OB-11 | Pin Hiểu Sai | 🔴 CRITICAL |
| OB-12 | Self-Referential Struct | 🔴 CRITICAL |
| OB-13 | Implicit Copy Surprise | 🟡 MEDIUM |
| OB-14 | Mutable Aliasing Ẩn | 🟠 HIGH |
| OB-15 | Box Thừa | 🟡 MEDIUM |

---

## OB-01: Clone Thừa Thãi (Excessive Cloning)

### 1. Tên

**Clone Thừa Thãi** (Excessive Cloning)

### 2. Phân loại

- **Lĩnh vực:** Ownership & Borrowing
- **Danh mục con:** Performance / Allocation
- **Mã định danh:** OB-01

### 3. Mức nghiêm trọng

🟡 **MEDIUM** — Không gây UB nhưng tạo ra chi phí allocation và copy không cần thiết, có thể trở thành bottleneck trong hot path.

### 4. Vấn đề

Lập trình viên mới thường dùng `.clone()` như "phép màu" để thoát khỏi borrow checker thay vì hiểu đúng ownership. Kết quả là heap allocation dày đặc, throughput giảm, và code che giấu ý định thực sự.

```
                 ┌─────────────────────────────────────┐
                 │  Hàm nhận &String nhưng caller      │
                 │  clone() trước khi truyền vào       │
                 └──────────────┬──────────────────────┘
                                │
                                ▼
            ┌───────────────────────────────────────┐
            │  heap allocation #1 (owner String)    │
            │  ──────────────────────────────────   │
            │  .clone()  →  heap allocation #2      │
            │  ──────────────────────────────────   │
            │  hàm chỉ cần đọc → &str đủ dùng      │
            └───────────────────────────────────────┘
```

**Nguyên nhân phổ biến:**
- Truyền `String` vào hàm cần `&str` → clone để "làm hài lòng compiler"
- Lưu giá trị vào struct khi chỉ cần reference
- Clone trong vòng lặp mà không nhận ra chi phí

### 5. Phát hiện trong mã nguồn

**Dấu hiệu nhận biết:**
- `.clone()` xuất hiện ngay trước lời gọi hàm
- Tham số hàm kiểu `String` thay vì `&str`
- `.clone()` trong body của vòng lặp `for` / `while`
- `to_string()` hoặc `.to_owned()` không cần thiết

**Regex patterns (dùng với ripgrep):**

```bash
# Tìm .clone() ngay trước lời gọi hàm
rg '\.clone\(\)\s*[,\)]' --type rust

# Tìm hàm nhận String thay vì &str
rg 'fn\s+\w+\s*\([^)]*:\s*String[^)]*\)' --type rust

# Tìm .clone() bên trong vòng lặp
rg -A5 'for\s+\w+\s+in' --type rust | rg '\.clone\(\)'

# Tìm to_string() / to_owned() không cần thiết
rg '\.(to_string|to_owned)\(\)\s*[,\)]' --type rust
```

### 6. Giải pháp

| Tình huống | Thay vì | Dùng |
|------------|---------|------|
| Hàm chỉ đọc chuỗi | `fn f(s: String)` | `fn f(s: &str)` |
| Hàm chỉ đọc Vec | `fn f(v: Vec<T>)` | `fn f(v: &[T])` |
| Hàm chỉ đọc struct | `fn f(x: MyStruct)` | `fn f(x: &MyStruct)` |
| Tham chiếu ngắn hơn lifetime | Dùng `Arc<T>` | Dùng `&T` |

**Rust code — BAD:**

```rust
fn print_greeting(name: String) {  // nhận ownership không cần thiết
    println!("Hello, {}!", name);
}

fn process_names(names: Vec<String>) {
    for name in &names {
        print_greeting(name.clone());  // clone vô ích trong vòng lặp
    }
}

struct Config {
    host: String,
    port: u16,
}

fn connect(config: Config) {  // di chuyển toàn bộ struct
    println!("Connecting to {}:{}", config.host, config.port);
}

fn main() {
    let names = vec!["Alice".to_string(), "Bob".to_string()];
    process_names(names);

    let cfg = Config { host: "localhost".to_string(), port: 8080 };
    connect(cfg.clone());  // clone cả struct chỉ để in
    connect(cfg);
}
```

**Rust code — GOOD:**

```rust
fn print_greeting(name: &str) {  // mượn, không nhận ownership
    println!("Hello, {}!", name);
}

fn process_names(names: &[String]) {  // &[T] thay vì Vec<T>
    for name in names {
        print_greeting(name);  // coerce String -> &str tự động
    }
}

struct Config {
    host: String,
    port: u16,
}

fn connect(host: &str, port: u16) {  // chỉ mượn những gì cần
    println!("Connecting to {}:{}", host, port);
}

fn main() {
    let names = vec!["Alice".to_string(), "Bob".to_string()];
    process_names(&names);  // truyền slice, không move

    let cfg = Config { host: "localhost".to_string(), port: 8080 };
    connect(&cfg.host, cfg.port);  // không cần clone
    connect(&cfg.host, cfg.port);  // gọi lại vẫn được
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Hàm có thực sự cần ownership hay chỉ cần đọc?
- [ ] Tham số `String` có thể đổi thành `&str` không?
- [ ] Tham số `Vec<T>` có thể đổi thành `&[T]` không?
- [ ] `.clone()` trong vòng lặp có thể tránh được không?
- [ ] Review `Deref coercion` để tự động chuyển kiểu

**Clippy lints:**

```bash
cargo clippy -- \
  -W clippy::clone_on_ref_ptr \
  -W clippy::redundant_clone \
  -W clippy::needless_pass_by_value
```

---

## OB-02: RefCell Lạm Dụng (RefCell Abuse)

### 1. Tên

**RefCell Lạm Dụng** (RefCell Abuse)

### 2. Phân loại

- **Lĩnh vực:** Ownership & Borrowing
- **Danh mục con:** Interior Mutability / Runtime Panics
- **Mã định danh:** OB-02

### 3. Mức nghiêm trọng

🟠 **HIGH** — `RefCell` chuyển borrow checking từ compile-time sang runtime. Borrow panic không thể bắt ở compile-time, dễ xảy ra trong production với stack trace khó debug.

### 4. Vấn đề

`RefCell<T>` cung cấp interior mutability — hữu ích trong một số trường hợp nhưng dễ bị lạm dụng khi lập trình viên muốn "thoát khỏi" borrow checker. Khi hai `borrow_mut()` xảy ra cùng lúc (trong cùng một luồng), chương trình **panic** thay vì compile error.

```
  compile-time (safe)         runtime (panic!)
  ──────────────────          ────────────────────────────────
  &mut T chỉ được 1           RefCell::borrow_mut() lần 2
  lần cùng lúc                trong khi lần 1 còn sống
  → compile error             → thread 'main' panicked at
                                'already mutably borrowed'
```

**Nguyên nhân phổ biến:**
- Dùng `Rc<RefCell<T>>` như "shared mutable state" không có kế hoạch
- Gọi `borrow_mut()` bên trong closure đang giữ `borrow()`
- Thiếu thiết kế rõ ràng về ai sở hữu dữ liệu

### 5. Phát hiện trong mã nguồn

**Dấu hiệu nhận biết:**
- `Rc<RefCell<T>>` hoặc `Arc<Mutex<T>>` dùng không nhất quán
- Nhiều lần `.borrow_mut()` trong cùng một scope
- `RefCell` trong struct field mà không có comment giải thích
- `unwrap()` sau `borrow_mut()` hoặc `try_borrow_mut()`

**Regex patterns:**

```bash
# Tìm RefCell usage
rg 'RefCell<' --type rust

# Tìm nhiều borrow_mut() gần nhau (cùng block)
rg '\.borrow_mut\(\)' --type rust -n

# Tìm Rc<RefCell pattern
rg 'Rc<RefCell<' --type rust

# Tìm borrow_mut().unwrap() hoặc borrow() trong closure
rg 'borrow_mut\(\)\s*\.' --type rust
```

### 6. Giải pháp

| Tình huống | Thay vì RefCell | Dùng |
|------------|-----------------|------|
| Single thread, clear owner | `RefCell<T>` | Refactor ownership |
| Multi-thread shared state | `Rc<RefCell<T>>` | `Arc<Mutex<T>>` |
| Event callback cần mutation | `RefCell` workaround | Channel hoặc Message passing |
| Tách lớp đọc/ghi | `RefCell<T>` random | `Cell<T>` cho Copy types |

**Rust code — BAD:**

```rust
use std::cell::RefCell;
use std::rc::Rc;

struct Node {
    value: i32,
    children: Vec<Rc<RefCell<Node>>>,
}

fn sum_tree(node: &Rc<RefCell<Node>>) -> i32 {
    let borrowed = node.borrow();  // borrow #1
    let sum: i32 = borrowed.children
        .iter()
        .map(|child| {
            let mut b = child.borrow_mut();  // borrow #2 — panic nếu child == node
            b.value *= 2;
            b.value
        })
        .sum();
    borrowed.value + sum
}

fn main() {
    let root = Rc::new(RefCell::new(Node { value: 1, children: vec![] }));
    let child = Rc::clone(&root);  // child trỏ vào root
    root.borrow_mut().children.push(child);  // vòng tham chiếu + panic tiềm ẩn
    println!("{}", sum_tree(&root));  // PANIC: already borrowed
}
```

**Rust code — GOOD:**

```rust
// Thiết kế lại với ownership rõ ràng
struct Node {
    value: i32,
    children: Vec<Node>,  // owned, không cần Rc/RefCell
}

impl Node {
    fn sum(&self) -> i32 {
        self.value + self.children.iter().map(|c| c.sum()).sum::<i32>()
    }

    fn double_children(&mut self) {
        for child in &mut self.children {
            child.value *= 2;
            child.double_children();
        }
    }
}

fn main() {
    let mut root = Node {
        value: 1,
        children: vec![
            Node { value: 2, children: vec![] },
            Node { value: 3, children: vec![] },
        ],
    };
    root.double_children();
    println!("{}", root.sum());  // an toàn, không panic
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Thiết kế ownership trước khi code — ai sở hữu dữ liệu?
- [ ] Nếu cần `RefCell`, ghi comment giải thích tại sao
- [ ] Dùng `try_borrow()` / `try_borrow_mut()` và xử lý `Err`
- [ ] Xem xét thay bằng message passing (channels)
- [ ] Kiểm tra vòng tham chiếu khi dùng `Rc<RefCell<T>>`

**Clippy lints:**

```bash
cargo clippy -- \
  -W clippy::borrow_interior_mutable_const \
  -W clippy::cell_ref_counting
```

---

## OB-03: Lifetime Elision Sai (Lifetime Elision Misunderstanding)

### 1. Tên

**Lifetime Elision Sai** (Lifetime Elision Misunderstanding)

### 2. Phân loại

- **Lĩnh vực:** Ownership & Borrowing
- **Danh mục con:** Lifetime / API Design
- **Mã định danh:** OB-03

### 3. Mức nghiêm trọng

🟠 **HIGH** — Lifetime elision ẩn tạo ra API không đúng ý định, dẫn đến lỗi compile khó hiểu ở phía người dùng hoặc borrow quá ngắn/dài hơn cần thiết.

### 4. Vấn đề

Rust cho phép bỏ qua lifetime annotations trong nhiều trường hợp (lifetime elision rules). Khi lập trình viên không hiểu quy tắc này, họ viết hàm trả về reference nhưng lifetime được suy ra sai, hoặc struct chứa reference với lifetime không khớp với ý định.

```
  Lifetime Elision Rules:
  ┌──────────────────────────────────────────────────────────┐
  │ Rule 1: Mỗi tham số reference có lifetime riêng          │
  │         fn f(x: &T, y: &U) → fn f<'a,'b>(x: &'a T, ...) │
  │                                                          │
  │ Rule 2: Nếu chỉ có 1 input lifetime → output dùng nó    │
  │         fn f(x: &T) -> &U  →  fn f<'a>(x: &'a T) -> &'a U│
  │                                                          │
  │ Rule 3: Nếu có &self/&mut self → output dùng lifetime đó │
  │         fn f(&self, x: &T) -> &U  →  lifetime của self   │
  └──────────────────────────────────────────────────────────┘

  Hiểu sai Rule 2 với 2 inputs:
  fn first_or(a: &str, b: &str) -> &str  ← COMPILE ERROR
  Compiler không biết output sống bao lâu so với a hay b
```

### 5. Phát hiện trong mã nguồn

**Dấu hiệu nhận biết:**
- Hàm trả về `&T` với nhiều tham số `&T` nhưng không có annotation
- Struct chứa `&T` mà không có lifetime parameter
- Compile error "lifetime may not live long enough" ở caller
- Annotation `'_` dùng ở nơi cần lifetime cụ thể

**Regex patterns:**

```bash
# Tìm hàm trả về reference với nhiều tham số reference (có thể thiếu annotation)
rg 'fn\s+\w+\s*\([^)]*&[^)]*&[^)]*\)\s*->\s*&' --type rust

# Tìm struct có field reference không có lifetime
rg 'struct\s+\w+\s*\{[^}]*&\s*\w' --type rust -A5

# Tìm explicit lifetime được dùng
rg "fn\s+\w+\s*<'[a-z]" --type rust

# Tìm 'static lifetime có thể sai
rg "'static" --type rust
```

### 6. Giải pháp

| Trường hợp | Elision Result | Annotation đúng |
|------------|---------------|-----------------|
| 1 input ref → output ref | input lifetime | Không cần annotation |
| 2+ input refs → output ref | **Compile Error** | Phải annotate |
| `&self` + input → output | `self` lifetime | Thường đúng |
| Struct field `&T` | **Cần annotation** | `struct Foo<'a> { f: &'a T }` |

**Rust code — BAD:**

```rust
// Ambiguous: compiler không biết output lifetime là 'a hay 'b
fn longer(a: &str, b: &str) -> &str {  // COMPILE ERROR
    if a.len() >= b.len() { a } else { b }
}

// Struct với reference không có lifetime parameter
struct StrSplit {
    remainder: &str,  // COMPILE ERROR: missing lifetime
    delimiter: &str,
}

// Sai ý định: muốn trả về tham số x nhưng elision gán lifetime của &self
struct Parser {
    input: String,
}
impl Parser {
    fn parse<'a>(&self, token: &'a str) -> &str {
        // Thực ra trả về &'1 str (lifetime của self), không phải 'a
        // Nhưng nếu trả về token thì borrow checker sẽ từ chối
        &self.input[..]
    }
}
```

**Rust code — GOOD:**

```rust
// Explicit lifetime — rõ ràng output sống bằng min(a, b)
fn longer<'a>(a: &'a str, b: &'a str) -> &'a str {
    if a.len() >= b.len() { a } else { b }
}

// Struct với lifetime parameter rõ ràng
struct StrSplit<'a, 'b> {
    remainder: &'a str,
    delimiter: &'b str,
}

impl<'a, 'b> StrSplit<'a, 'b> {
    fn new(s: &'a str, d: &'b str) -> Self {
        StrSplit { remainder: s, delimiter: d }
    }
}

// Rõ ràng: output sống bằng 'input
struct Parser {
    input: String,
}
impl Parser {
    fn first_token<'a>(&self, source: &'a str) -> &'a str {
        // Trả về slice của source (lifetime 'a), không phải của self
        source.split_whitespace().next().unwrap_or("")
    }
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Mọi hàm trả về `&T` với 2+ tham số reference → annotate lifetime
- [ ] Mọi struct chứa `&T` → thêm `<'a>` parameter
- [ ] Đọc lại elision rules trước khi bỏ qua annotation
- [ ] Dùng `cargo expand` để xem lifetime sau elision
- [ ] Viết test với nhiều lifetime khác nhau để verify behavior

**Clippy lints:**

```bash
cargo clippy -- \
  -W clippy::needless_lifetimes \
  -W clippy::extra_unused_lifetimes
# Dùng rustc để xem lifetime elaboration:
# rustc --edition 2021 -Z identify-regions src/lib.rs
```

---

## OB-04: Vòng Tham Chiếu Rc (Rc Reference Cycles)

### 1. Tên

**Vòng Tham Chiếu Rc** (Rc Reference Cycles)

### 2. Phân loại

- **Lĩnh vực:** Ownership & Borrowing
- **Danh mục con:** Memory Leak / Reference Counting
- **Mã định danh:** OB-04

### 3. Mức nghiêm trọng

🔴 **CRITICAL** — Vòng tham chiếu với `Rc<T>` gây **memory leak** không thể khắc phục ở runtime. Rust đảm bảo memory safety nhưng không đảm bảo không có leak.

### 4. Vấn đề

`Rc<T>` dùng reference counting — khi count = 0 thì drop. Nhưng nếu A giữ `Rc` trỏ vào B và B giữ `Rc` trỏ lại A, count của cả hai không bao giờ về 0, dù không còn external reference nào. Dữ liệu bị rò rỉ cho đến khi process kết thúc.

```
  Vòng tham chiếu (Reference Cycle):

  ┌─────────┐    Rc::clone    ┌─────────┐
  │  Node A │ ─────────────► │  Node B │
  │ count=2 │                │ count=2 │
  └─────────┘ ◄───────────── └─────────┘
                 Rc::clone

  Khi main() kết thúc:
  - Drop external ref A → count A: 2→1  (≠0, không drop!)
  - Drop external ref B → count B: 2→1  (≠0, không drop!)
  → LEAK: cả A và B ở lại heap mãi mãi
```

### 5. Phát hiện trong mã nguồn

**Dấu hiệu nhận biết:**
- Struct chứa `Rc<RefCell<Self>>` hoặc `Rc<RefCell<T>>` trỏ về phía cha
- Tree/graph với parent pointer dùng `Rc`
- `Rc::clone` trong vòng lặp xây dựng cấu trúc hai chiều
- Thiếu `Weak<T>` trong cấu trúc parent-child

**Regex patterns:**

```bash
# Tìm Rc<RefCell pattern (dễ tạo cycle)
rg 'Rc<RefCell<' --type rust

# Tìm field parent/owner dùng Rc (nên là Weak)
rg 'parent\s*:\s*Rc<' --type rust
rg 'owner\s*:\s*Rc<' --type rust

# Tìm Weak usage (nếu không có → có thể thiếu)
rg 'Weak<' --type rust

# Tìm Rc::clone trong block (kiểm tra thủ công)
rg 'Rc::clone\|\.clone\(\)' --type rust -A2
```

### 6. Giải pháp

| Mối quan hệ | Hướng | Dùng |
|-------------|-------|------|
| Parent → Children | Ownership | `Rc<RefCell<T>>` |
| Child → Parent | Back-reference | `Weak<RefCell<T>>` |
| Sibling → Sibling | Sharing | `Rc<RefCell<T>>` (cẩn thận) |
| Không cần sharing | Ownership | `Box<T>` hoặc owned |

**Rust code — BAD:**

```rust
use std::cell::RefCell;
use std::rc::Rc;

#[derive(Debug)]
struct Node {
    value: i32,
    children: Vec<Rc<RefCell<Node>>>,
    parent: Option<Rc<RefCell<Node>>>,  // CYCLE: parent dùng Rc
}

fn main() {
    let parent = Rc::new(RefCell::new(Node {
        value: 1,
        children: vec![],
        parent: None,
    }));

    let child = Rc::new(RefCell::new(Node {
        value: 2,
        children: vec![],
        parent: Some(Rc::clone(&parent)),  // child → parent (Rc)
    }));

    parent.borrow_mut().children.push(Rc::clone(&child));  // parent → child (Rc)
    // Khi hàm kết thúc: parent count=2, child count=2 → LEAK!
}
```

**Rust code — GOOD:**

```rust
use std::cell::RefCell;
use std::rc::{Rc, Weak};

#[derive(Debug)]
struct Node {
    value: i32,
    children: Vec<Rc<RefCell<Node>>>,
    parent: Option<Weak<RefCell<Node>>>,  // Weak: không tăng count
}

impl Node {
    fn new(value: i32) -> Rc<RefCell<Self>> {
        Rc::new(RefCell::new(Node {
            value,
            children: vec![],
            parent: None,
        }))
    }

    fn add_child(parent: &Rc<RefCell<Node>>, child: Rc<RefCell<Node>>) {
        child.borrow_mut().parent = Some(Rc::downgrade(parent));  // Weak ref
        parent.borrow_mut().children.push(child);
    }
}

fn main() {
    let parent = Node::new(1);
    let child = Node::new(2);

    Node::add_child(&parent, child);
    // Khi hàm kết thúc:
    // - parent count: 1 → 0 → DROP (kéo theo children)
    // - child count: 1 → 0 → DROP
    // - Weak ref trong child.parent trở thành None tự động
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Mọi back-reference (child → parent, callback → owner) → dùng `Weak<T>`
- [ ] Vẽ sơ đồ ownership trước khi code graph/tree
- [ ] Dùng `Rc::strong_count()` trong tests để verify count về 0
- [ ] Xem xét arenas (`typed-arena` crate) cho graph phức tạp
- [ ] Dùng Miri để phát hiện leak trong unit tests

**Clippy lints:**

```bash
cargo clippy -- -W clippy::rc_clone_in_vec_init
# Dùng Miri để detect leak:
cargo +nightly miri test
```

---

## OB-05: Borrow Checker Bypass (Unsafe Borrow)

### 1. Tên

**Borrow Checker Bypass** (Unsafe Borrow)

### 2. Phân loại

- **Lĩnh vực:** Ownership & Borrowing
- **Danh mục con:** Unsafe / Undefined Behavior
- **Mã định danh:** OB-05

### 3. Mức nghiêm trọng

🔴 **CRITICAL** — Bypass borrow checker bằng `unsafe` + raw pointer tạo **undefined behavior**, có thể dẫn đến use-after-free, dangling pointer, hoặc data race mà compiler không cảnh báo.

### 4. Vấn đề

Khi borrow checker từ chối code, một số lập trình viên dùng `unsafe` và raw pointer để "lách qua". Đây là sai lầm nghiêm trọng: borrow checker từ chối vì có lý do hợp lệ. Bypass nó mà không có invariants chắc chắn dẫn đến UB không xác định.

```
  Safe Rust:
  ┌────────────────────────────────────────────┐
  │  &mut T   →  compiler guarantee:           │
  │  chỉ 1 mutable reference tại một thời điểm │
  └────────────────────────────────────────────┘

  Unsafe bypass:
  ┌────────────────────────────────────────────────────────┐
  │  let ptr = &mut data as *mut T;                        │
  │  let ref1 = &mut *ptr;  // mutable ref #1             │
  │  let ref2 = &mut *ptr;  // mutable ref #2 ← UB!      │
  │  // Compiler không thấy, nhưng đây là aliasing UB     │
  │  // Có thể: wrong optimization, memory corruption     │
  └────────────────────────────────────────────────────────┘
```

### 5. Phát hiện trong mã nguồn

**Dấu hiệu nhận biết:**
- `unsafe` block không có SAFETY comment
- Cast `as *mut T` hoặc `as *const T` trong code thường
- `std::mem::transmute` để thay đổi lifetime
- `ptr::read` / `ptr::write` ngoài abstraction layer
- `from_raw_parts` / `from_raw_parts_mut` không check bounds

**Regex patterns:**

```bash
# Tìm unsafe blocks
rg 'unsafe\s*\{' --type rust -n

# Tìm raw pointer cast
rg 'as\s*\*mut\s+\w\|as\s*\*const\s+\w' --type rust

# Tìm transmute (rất nguy hiểm)
rg 'mem::transmute\|transmute::<' --type rust

# Tìm from_raw_parts
rg 'from_raw_parts' --type rust

# Tìm unsafe block không có SAFETY comment
rg -B2 'unsafe\s*\{' --type rust | rg -v 'SAFETY\|Safety\|safety'
```

### 6. Giải pháp

| Vấn đề muốn giải quyết | Unsafe workaround | Safe alternative |
|------------------------|-------------------|------------------|
| Chia `Vec` thành 2 phần mutable | `ptr::add` + cast | `split_at_mut()` |
| Đọc struct có uninitialized field | `mem::zeroed()` | `MaybeUninit<T>` |
| Thay đổi lifetime của reference | `mem::transmute` | Refactor ownership |
| Self-referential struct | Raw pointer | `Pin` + `PhantomPinned` |

**Rust code — BAD:**

```rust
fn split_mut(data: &mut [i32]) -> (&mut [i32], &mut [i32]) {
    let mid = data.len() / 2;
    // Cố gắng tạo 2 mutable slice từ 1 slice
    // WRONG: tạo aliasing mutable reference → UB
    unsafe {
        let ptr = data.as_mut_ptr();
        let left = std::slice::from_raw_parts_mut(ptr, mid);
        let right = std::slice::from_raw_parts_mut(ptr.add(mid), data.len() - mid);
        (left, right)  // hai mutable ref vào cùng allocation → UB nếu dùng sai
    }
}

// Thay đổi lifetime bằng transmute (CRITICAL)
fn bad_lifetime_hack<'a>(s: &str) -> &'a str {
    unsafe { std::mem::transmute(s) }  // UB: trả về dangling ref sau khi source drop
}
```

**Rust code — GOOD:**

```rust
fn split_mut(data: &mut [i32]) -> (&mut [i32], &mut [i32]) {
    let mid = data.len() / 2;
    data.split_at_mut(mid)  // stdlib đã handle unsafe nội bộ một cách đúng đắn
}

// Không cần hack lifetime — thiết kế lại
struct TextProcessor {
    buffer: String,
}

impl TextProcessor {
    fn process<'a>(&'a self) -> &'a str {
        // Trả về reference với lifetime gắn với self — đúng và an toàn
        &self.buffer
    }
}

// Khi THỰC SỰ cần unsafe — phải có SAFETY comment
fn safe_unsafe_example(data: &mut [i32], idx: usize) -> &mut i32 {
    // SAFETY: idx đã được caller verify < data.len()
    // Không có aliasing vì chỉ trả về 1 reference tại một thời điểm
    unsafe { data.get_unchecked_mut(idx) }
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Mọi `unsafe` block phải có `// SAFETY:` comment
- [ ] Trước khi dùng unsafe, tìm safe alternative trong stdlib
- [ ] Chạy Miri (`cargo miri test`) để phát hiện UB
- [ ] Review unsafe code bởi người có kinh nghiệm Rust
- [ ] Bọc unsafe trong abstraction với safe public API

**Clippy lints:**

```bash
cargo clippy -- \
  -W clippy::undocumented_unsafe_blocks \
  -W clippy::multiple_unsafe_ops_per_block \
  -F unsafe_code  # Cấm hoàn toàn nếu không cần FFI
# Miri:
cargo +nightly miri test
```

---

## OB-06: Move Sau Borrow (Use After Move)

### 1. Tên

**Move Sau Borrow** (Use After Move)

### 2. Phân loại

- **Lĩnh vực:** Ownership & Borrowing
- **Danh mục con:** Move Semantics / Compile Error
- **Mã định danh:** OB-06

### 3. Mức nghiêm trọng

🟠 **HIGH** — Thường là compile error nên ít nguy hiểm ở runtime, nhưng gây mất thời gian refactor do hiểu sai move semantics, đặc biệt trong closures và async contexts.

### 4. Vấn đề

Khi một giá trị bị move, ownership chuyển sang nơi khác và biến gốc không còn hợp lệ. Lỗi phổ biến: move vào closure rồi cố dùng lại, hoặc move trong một nhánh của `match` rồi dùng ở nhánh khác.

```
  Move Semantics:
  ┌──────────────────────────────────────────────┐
  │  let s = String::from("hello");              │
  │  let t = s;        // s moved vào t         │
  │  println!("{}", s); // COMPILE ERROR         │
  │  // value used here after move               │
  └──────────────────────────────────────────────┘

  Move trong Closure:
  ┌──────────────────────────────────────────────┐
  │  let data = vec![1, 2, 3];                  │
  │  let f = move || data.len();  // data moved │
  │  println!("{:?}", data);  // COMPILE ERROR  │
  └──────────────────────────────────────────────┘
```

### 5. Phát hiện trong mã nguồn

**Dấu hiệu nhận biết:**
- `move ||` closure nhưng biến vẫn được dùng sau closure
- Truyền vào hàm lấy ownership rồi dùng lại
- `match` arm move một nhánh, các nhánh khác không dùng được nữa
- Iterator adapter (`.map()`, `.filter()`) move biến capture

**Regex patterns:**

```bash
# Tìm move closure
rg 'move\s*\|\|' --type rust -n

# Tìm hàm lấy ownership (tham số không có &)
rg 'fn\s+\w+\s*\([^)]*:\s*[A-Z]\w+[^)]*\)' --type rust

# Tìm pattern dùng biến sau khi có thể đã move
rg 'spawn.*move' --type rust

# Tìm into() chuyển đổi có move
rg '\.into\(\)' --type rust
```

### 6. Giải pháp

| Tình huống | Vấn đề | Giải pháp |
|------------|---------|-----------|
| Closure cần data và caller cũng cần | Move vào closure | Clone trước khi move |
| Hàm lấy ownership nhưng cần dùng lại | Move vào hàm | Truyền `&T` hoặc lấy lại từ return |
| Move trong một nhánh match | Partial move | Dùng `ref` hoặc clone |
| Async spawn cần data | Lifetime ngắn hơn | Arc hoặc clone trước spawn |

**Rust code — BAD:**

```rust
use std::thread;

fn process(data: Vec<i32>) -> i32 {  // lấy ownership
    data.iter().sum()
}

fn main() {
    let data = vec![1, 2, 3, 4, 5];

    let handle = thread::spawn(move || {
        println!("Thread: {:?}", data);  // data moved vào thread
    });

    // COMPILE ERROR: data đã moved vào closure ở trên
    println!("Main: {:?}", data);
    let sum = process(data);  // COMPILE ERROR: double move
    println!("Sum: {}", sum);

    handle.join().unwrap();
}
```

**Rust code — GOOD:**

```rust
use std::sync::Arc;
use std::thread;

fn process(data: &[i32]) -> i32 {  // mượn thay vì lấy ownership
    data.iter().sum()
}

fn main() {
    let data = Arc::new(vec![1, 2, 3, 4, 5]);

    let data_for_thread = Arc::clone(&data);  // clone Arc (cheap)
    let handle = thread::spawn(move || {
        println!("Thread: {:?}", data_for_thread);
    });

    // data vẫn hợp lệ — chỉ clone Arc header, không clone Vec
    println!("Main: {:?}", data);
    let sum = process(&data);  // mượn data
    println!("Sum: {}", sum);

    handle.join().unwrap();
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Nếu cần dùng lại sau move → clone trước hoặc dùng `Arc`
- [ ] Thiết kế hàm nhận `&T` thay vì `T` nếu không cần ownership
- [ ] Với thread/async → dùng `Arc<T>` cho shared data
- [ ] Đọc compiler error message kỹ — chỉ ra điểm move chính xác
- [ ] Dùng `#[derive(Clone)]` cho struct cần share

**Clippy lints:**

```bash
cargo clippy -- \
  -W clippy::needless_pass_by_value \
  -W clippy::large_stack_arrays
```

---

## OB-07: String vs &str Confusion

### 1. Tên

**String vs &str Nhầm Lẫn** (String vs &str Confusion)

### 2. Phân loại

- **Lĩnh vực:** Ownership & Borrowing
- **Danh mục con:** Type Design / API Ergonomics
- **Mã định danh:** OB-07

### 3. Mức nghiêm trọng

🟡 **MEDIUM** — Không gây UB nhưng dẫn đến API kém ergonomic, allocation không cần thiết, hoặc lifetime error khó hiểu.

### 4. Vấn đề

`String` là owned heap-allocated string. `&str` là reference vào UTF-8 bytes (có thể là `String`, literal, hoặc slice). Nhầm giữa hai loại dẫn đến: hàm quá restrictive (chỉ nhận `String`), allocation không cần thiết, hoặc lifetime lỗi khi cố trả về `&str` từ `String` local.

```
  String (Owned)            &str (Borrowed)
  ┌─────────────────┐       ┌─────────────────────┐
  │ ptr ─────────►  │       │ ptr ─────────────►  │
  │ len             │       │ len                 │
  │ capacity        │       │ (no capacity)       │
  └─────────────────┘       └─────────────────────┘
  Heap allocation           Bất kỳ UTF-8 nào

  Lỗi phổ biến:
  fn bad(s: &String) → fn good(s: &str)  (Deref coercion làm &String → &str)
  fn bad() -> &str { String::from("x") } → COMPILE ERROR: trả về local ref
```

### 5. Phát hiện trong mã nguồn

**Dấu hiệu nhận biết:**
- Tham số `&String` thay vì `&str`
- Return type `&str` từ `String` tạo locally
- `format!()` dùng để concatenate rồi bỏ đi ngay
- `.to_string()` không cần thiết khi `&str` đủ dùng

**Regex patterns:**

```bash
# Tìm tham số &String (nên dùng &str)
rg ':\s*&String' --type rust

# Tìm return &str từ hàm (có thể trả về local String)
rg '->\s*&str' --type rust

# Tìm to_string() không cần thiết
rg '\.to_string\(\)\s*[,;\)]' --type rust

# Tìm format! dùng để tạo String rồi ngay lập tức dùng như &str
rg 'let\s+\w+\s*=\s*format!' --type rust
```

### 6. Giải pháp

| Tình huống | Kiểu sai | Kiểu đúng |
|------------|---------|-----------|
| Hàm chỉ đọc string | `fn f(s: &String)` | `fn f(s: &str)` |
| Hàm chỉ đọc, nhận cả String lẫn literal | `fn f(s: String)` | `fn f(s: impl AsRef<str>)` |
| Struct cần sở hữu chuỗi | `struct F { s: &str }` | `struct F { s: String }` |
| Struct có thể mượn hoặc sở hữu | `String` hoặc `&str` | `Cow<'a, str>` |
| Trả về từ hàm không có input ref | `-> &str` | `-> String` |

**Rust code — BAD:**

```rust
// Hàm nhận &String — kém ergonomic
fn greet(name: &String) {
    println!("Hello, {}!", name);
}

// Cố trả về &str từ String local → COMPILE ERROR
fn get_greeting() -> &str {
    let s = String::from("hello");
    &s  // COMPILE ERROR: s drop khi hàm return
}

// Dùng String khi &str đủ
fn is_empty_string(s: String) -> bool {
    s.is_empty()  // lấy ownership rồi bỏ ngay
}

fn main() {
    let s = String::from("Alice");
    greet(&s);
    greet(&"Bob".to_string());  // phải to_string() khi muốn truyền literal
}
```

**Rust code — GOOD:**

```rust
// Nhận &str — chấp nhận cả String và literal (Deref coercion)
fn greet(name: &str) {
    println!("Hello, {}!", name);
}

// Trả về String khi không có input ref để borrow từ
fn get_greeting() -> String {
    String::from("hello")
}

// Mượn thay vì lấy ownership
fn is_empty_str(s: &str) -> bool {
    s.is_empty()
}

// Nếu muốn nhận cả String owned lẫn &str — dùng Into<String>
fn store_name(name: impl Into<String>) -> String {
    name.into()
}

fn main() {
    let s = String::from("Alice");
    greet(&s);       // String → &str (Deref)
    greet("Bob");    // &str literal trực tiếp
    greet("Charlie");

    let _ = store_name("literal");         // &str
    let _ = store_name(String::from("x")); // String
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Hàm chỉ đọc chuỗi → tham số `&str`
- [ ] Hàm cần store chuỗi → tham số `impl Into<String>`
- [ ] Không return `&str` tạo từ `String` local
- [ ] Xem xét `Cow<'a, str>` cho hot path có thể mượn hoặc sở hữu
- [ ] Review Deref coercions: `String` → `&str`, `Vec<T>` → `&[T]`

**Clippy lints:**

```bash
cargo clippy -- \
  -W clippy::ptr_arg \
  -W clippy::str_to_string \
  -W clippy::string_to_string
```

---

## OB-08: Mutex Poisoning Bỏ Qua (Ignoring Mutex Poisoning)

### 1. Tên

**Mutex Poisoning Bỏ Qua** (Ignoring Mutex Poisoning)

### 2. Phân loại

- **Lĩnh vực:** Ownership & Borrowing
- **Danh mục con:** Concurrency / Error Handling
- **Mã định danh:** OB-08

### 3. Mức nghiêm trọng

🟠 **HIGH** — Bỏ qua mutex poisoning có thể dẫn đến đọc/ghi dữ liệu ở trạng thái không nhất quán (partially updated), gây bug logic khó phát hiện trong production.

### 4. Vấn đề

Khi một thread panic trong khi giữ `Mutex`, Rust đánh dấu mutex là "poisoned". Lần tiếp theo `lock()` được gọi, nó trả về `Err(PoisonError)`. Dùng `.unwrap()` hoặc `.expect()` ở đây đúng là panic ngay, nhưng dùng `.unwrap_or_default()` hay bỏ qua error có thể để lộ dữ liệu inconsistent.

```
  Thread A (panic trong lock):
  ┌─────────────────────────────────────┐
  │  mutex.lock() → OK                 │
  │  data.field1 = new_value;          │
  │  // PANIC xảy ra ở đây             │
  │  data.field2 = new_value;  ← chưa  │
  └─────────────────────────────────────┘
                  │
                  ▼
         Mutex bị POISONED
                  │
  Thread B:       ▼
  ┌────────────────────────────────────────┐
  │  let lock = mutex.lock()              │
  │      .unwrap_or_else(|e| e.into_inner())│
  │  // Đọc data: field1 đã thay đổi     │
  │  //           field2 chưa thay đổi   │
  │  // → Inconsistent state!            │
  └────────────────────────────────────────┘
```

### 5. Phát hiện trong mã nguồn

**Dấu hiệu nhận biết:**
- `.lock().unwrap()` không có xử lý PoisonError
- `.lock().unwrap_or_else(|e| e.into_inner())` — bỏ qua poisoning
- Không có recovery logic sau khi phát hiện poisoned mutex
- Nhiều field được update không atomically trong lock

**Regex patterns:**

```bash
# Tìm lock().unwrap() (không xử lý poisoning)
rg '\.lock\(\)\s*\.unwrap\(\)' --type rust

# Tìm into_inner() sau poisoned error (có thể OK hoặc không)
rg 'into_inner\(\)' --type rust

# Tìm mọi Mutex lock pattern
rg '\.lock\(\)' --type rust -n

# Tìm RwLock tương tự
rg '\.read\(\)\s*\.unwrap\(\)\|\.write\(\)\s*\.unwrap\(\)' --type rust
```

### 6. Giải pháp

| Pattern | Vấn đề | Giải pháp |
|---------|---------|-----------|
| `.lock().unwrap()` | Propagate panic nếu poisoned | OK nếu design là "crash on poisoned" |
| `.lock().unwrap_or_else(|e| e.into_inner())` | Dùng dữ liệu inconsistent | Chỉ dùng nếu biết chắc data vẫn valid |
| Bỏ qua Result | Không xử lý | Luôn xử lý `LockResult` |
| Atomic updates | Nhiều field | Batch update trong 1 lock, hoặc dùng transaction |

**Rust code — BAD:**

```rust
use std::sync::{Arc, Mutex};
use std::thread;

struct BankAccount {
    balance: f64,
    transaction_count: u64,
}

fn transfer(account: Arc<Mutex<BankAccount>>, amount: f64) {
    let mut guard = account.lock().unwrap();  // panic nếu poisoned
    guard.balance -= amount;
    // Giả sử panic xảy ra ở đây (ví dụ: amount validation)
    if amount < 0.0 { panic!("negative amount"); }
    guard.transaction_count += 1;  // Chưa được update khi panic ở trên
}

fn read_balance_ignoring_poison(account: &Arc<Mutex<BankAccount>>) -> f64 {
    // Bỏ qua poisoning — đọc dữ liệu có thể inconsistent
    account.lock()
        .unwrap_or_else(|e| e.into_inner())  // DANGER: dữ liệu có thể sai
        .balance
}
```

**Rust code — GOOD:**

```rust
use std::sync::{Arc, Mutex};
use std::thread;

struct BankAccount {
    balance: f64,
    transaction_count: u64,
}

#[derive(Debug)]
enum TransferError {
    LockPoisoned,
    NegativeAmount,
    InsufficientFunds,
}

fn transfer(
    account: &Arc<Mutex<BankAccount>>,
    amount: f64,
) -> Result<(), TransferError> {
    // Validate trước khi lock
    if amount < 0.0 {
        return Err(TransferError::NegativeAmount);
    }

    let mut guard = account.lock().map_err(|_| TransferError::LockPoisoned)?;

    if guard.balance < amount {
        return Err(TransferError::InsufficientFunds);
    }

    // Update atomically trong lock — không có code có thể panic ở giữa
    guard.balance -= amount;
    guard.transaction_count += 1;
    Ok(())
}

fn read_balance(account: &Arc<Mutex<BankAccount>>) -> Result<f64, &'static str> {
    account.lock()
        .map(|guard| guard.balance)
        .map_err(|_| "mutex poisoned — data may be inconsistent")
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Không panic bên trong lock guard (validate trước khi lock)
- [ ] Xử lý `PoisonError` một cách có chủ ý, không bỏ qua
- [ ] Batch mọi update liên quan trong cùng một lock scope
- [ ] Xem xét `parking_lot::Mutex` (không poison, thay bằng panic propagation)
- [ ] Dùng `?` operator để propagate lock errors lên caller

**Clippy lints:**

```bash
cargo clippy -- \
  -W clippy::mutex_atomic \
  -W clippy::mutex_integer
# Xem xét dùng parking_lot crate:
# parking_lot::Mutex không có poisoning
```

---

## OB-09: Drop Order Bất Ngờ (Unexpected Drop Order)

### 1. Tên

**Drop Order Bất Ngờ** (Unexpected Drop Order)

### 2. Phân loại

- **Lĩnh vực:** Ownership & Borrowing
- **Danh mục con:** RAII / Resource Management
- **Mã định danh:** OB-09

### 3. Mức nghiêm trọng

🟠 **HIGH** — Drop order ảnh hưởng đến: unlock mutex, commit transaction, flush buffer, đóng file handle. Sai thứ tự drop có thể gây deadlock, data corruption, hoặc resource leak.

### 4. Vấn đề

Rust drop biến theo thứ tự ngược với khai báo (LIFO). Trong struct, field được drop theo thứ tự khai báo. Tuy nhiên, temporary values trong expression có drop order phức tạp hơn, đặc biệt trong `let` statement và `match`.

```
  Drop Order trong function:
  let a = ...;   // drop thứ 3 (cuối)
  let b = ...;   // drop thứ 2
  let c = ...;   // drop thứ 1 (đầu tiên)

  Drop Order trong struct:
  struct Foo { a: A, b: B, c: C }
  Drop order: a → b → c  (theo thứ tự khai báo)

  Vấn đề với MutexGuard:
  let guard = mutex.lock().unwrap();
  let data = guard.data;  // guard vẫn sống
  drop(guard);            // unlock NGAY ĐÂY
  expensive_operation();  // chạy mà không giữ lock ← ĐÚNG

  NHƯNG:
  let data = mutex.lock().unwrap().data;
  // MutexGuard là TEMPORARY → drop NGAY sau statement này
  // → mutex unlock sớm hơn mong đợi
```

### 5. Phát hiện trong mã nguồn

**Dấu hiệu nhận biết:**
- `mutex.lock().unwrap().field` — guard drop ngay
- Không có `let _guard = ...` để giữ guard sống
- Struct field order ảnh hưởng đến cleanup behavior
- `drop()` explicit không ở đúng vị trí

**Regex patterns:**

```bash
# Tìm chained lock().field (guard drop ngay)
rg '\.lock\(\)\s*\.\s*(?:unwrap|expect)\(\)\s*\.\w+' --type rust

# Tìm drop() explicit
rg '\bdrop\s*\(' --type rust -n

# Tìm let _ = pattern (intentional drop)
rg 'let\s+_\s*=' --type rust

# Tìm temporary MutexGuard trong expression
rg '\.lock\(\)[^;]*;' --type rust
```

### 6. Giải pháp

| Tình huống | Vấn đề | Giải pháp |
|------------|---------|-----------|
| Chain `.lock().field` | Guard drop ngay | `let guard = ...; guard.field` |
| Muốn drop sớm | Giữ guard quá lâu | `drop(guard)` explicit hoặc scope block |
| Struct cleanup order | Field drop order sai | Đặt fields theo đúng cleanup order |
| Transaction + Connection | Connection drop trước Transaction | Đặt Connection field sau Transaction |

**Rust code — BAD:**

```rust
use std::sync::{Arc, Mutex};

struct Database {
    data: Vec<String>,
}

fn bad_guard_usage(db: &Arc<Mutex<Database>>) -> String {
    // Guard là temporary, drop NGAY sau line này
    let first = db.lock().unwrap().data.first().cloned();
    // Mutex đã unlock ở đây! Nếu cần atomic read-then-write, đây là bug
    first.unwrap_or_default()
}

// Drop order trong struct — sai
struct BadOrder {
    handle: FileHandle,      // drop thứ 1 — handle bị đóng
    buffer: FlushBuffer,     // drop thứ 2 — flush fail vì handle đã đóng!
}
```

**Rust code — GOOD:**

```rust
use std::sync::{Arc, Mutex};

struct Database {
    data: Vec<String>,
}

fn good_guard_usage(db: &Arc<Mutex<Database>>) -> String {
    // Giữ guard trong named binding — explicit lifetime
    let guard = db.lock().unwrap();
    let first = guard.data.first().cloned();
    // guard drop ở đây (end of scope) — unlock sau khi xong
    first.unwrap_or_default()
}

fn scoped_lock(db: &Arc<Mutex<Database>>, new_item: String) {
    {
        let mut guard = db.lock().unwrap();
        guard.data.push(new_item);
        // guard drop ở đây — unlock trước expensive_operation
    }
    expensive_operation();  // chạy mà không giữ lock
}

// Drop order trong struct — đúng
struct GoodOrder {
    buffer: FlushBuffer,     // drop thứ 1 — flush trước
    handle: FileHandle,      // drop thứ 2 — đóng handle sau
}

fn expensive_operation() {
    // ...
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Không chain `.lock().field` khi cần giữ lock lâu hơn
- [ ] Dùng scope block `{}` để kiểm soát drop timing
- [ ] Thiết kế struct field order theo cleanup sequence
- [ ] Implement `Drop` explicit khi cleanup order quan trọng
- [ ] Test drop order với log trong `Drop::drop()`

**Clippy lints:**

```bash
cargo clippy -- \
  -W clippy::await_holding_lock \
  -W clippy::await_holding_refcell_ref
```

---

## OB-10: Cow Không Dùng (Missing Copy-on-Write)

### 1. Tên

**Cow Không Dùng** (Missing Copy-on-Write)

### 2. Phân loại

- **Lĩnh vực:** Ownership & Borrowing
- **Danh mục con:** Performance / Allocation
- **Mã định danh:** OB-10

### 3. Mức nghiêm trọng

🟡 **MEDIUM** — Thiếu `Cow<T>` trong hot path có thể gây allocation không cần thiết khi hầu hết trường hợp không cần modify data, ảnh hưởng throughput.

### 4. Vấn đề

`Cow<'a, B>` (Clone-on-Write) cho phép một hàm trả về reference nếu không cần modify, hoặc owned value nếu cần modify. Không dùng `Cow` khiến API phải chọn: luôn trả về owned (allocation) hoặc luôn trả về reference (lifetime constraint).

```
  Không dùng Cow:
  fn sanitize(s: &str) -> String {    // luôn allocate
      if s.contains('<') {
          s.replace('<', "&lt;")       // cần String mới
      } else {
          s.to_string()               // clone vô ích!
      }
  }

  Dùng Cow:
  fn sanitize(s: &str) -> Cow<str> {  // allocate chỉ khi cần
      if s.contains('<') {
          Cow::Owned(s.replace('<', "&lt;"))   // allocate
      } else {
          Cow::Borrowed(s)                     // zero-copy
      }
  }
```

### 5. Phát hiện trong mã nguồn

**Dấu hiệu nhận biết:**
- Hàm nhận `&str` nhưng trả về `String` — dù đa số trường hợp không cần modify
- `to_string()` / `to_owned()` trong nhánh "no-op" của if/else
- API nhận `&str` và trả về `String` mà không transform
- Hàm parser/validator luôn allocate dù input thường valid

**Regex patterns:**

```bash
# Tìm hàm nhận &str trả về String (ứng viên cho Cow)
rg 'fn\s+\w+\s*\([^)]*:\s*&str[^)]*\)\s*->\s*String' --type rust

# Tìm .to_owned() / .to_string() trong else branch
rg 'else\s*\{[^}]*\.to_owned\(\)' --type rust

# Tìm Cow đang được dùng (để tham khảo)
rg 'Cow<' --type rust

# Tìm pattern clone trong conditional
rg 'if.*\{[^}]*\.replace\|[^}]*\.to_string\(\)' --type rust
```

### 6. Giải pháp

| Tình huống | Trước | Sau |
|------------|-------|-----|
| Sanitize string | `-> String` luôn allocate | `-> Cow<str>` allocate khi cần |
| Parse + validate | `-> String` copy input | `-> Cow<str>` borrow nếu valid |
| Normalize data | `-> String` | `-> Cow<[T]>` cho slices |

**Rust code — BAD:**

```rust
// Luôn allocate String dù chỉ đôi khi cần modify
fn escape_html(s: &str) -> String {
    if s.contains('<') || s.contains('>') || s.contains('&') {
        s.replace('&', "&amp;")
         .replace('<', "&lt;")
         .replace('>', "&gt;")
    } else {
        s.to_string()  // UNNECESSARY ALLOCATION: không cần modify nhưng vẫn allocate
    }
}

fn normalize_path(path: &str) -> String {
    if path.starts_with('/') {
        path.to_string()  // clone không cần thiết
    } else {
        format!("/{}", path)  // cần allocate
    }
}
```

**Rust code — GOOD:**

```rust
use std::borrow::Cow;

fn escape_html(s: &str) -> Cow<str> {
    if s.contains('<') || s.contains('>') || s.contains('&') {
        // Chỉ allocate khi thực sự cần modify
        Cow::Owned(
            s.replace('&', "&amp;")
             .replace('<', "&lt;")
             .replace('>', "&gt;")
        )
    } else {
        Cow::Borrowed(s)  // zero-copy: borrow trực tiếp
    }
}

fn normalize_path(path: &str) -> Cow<str> {
    if path.starts_with('/') {
        Cow::Borrowed(path)          // borrow nếu đã đúng format
    } else {
        Cow::Owned(format!("/{}", path))  // allocate nếu cần prefix
    }
}

fn process_paths(paths: &[&str]) {
    for path in paths {
        let normalized = normalize_path(path);
        // Hầu hết paths đã có '/' → zero allocation trong vòng lặp
        println!("{}", normalized);
    }
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Hàm transform string có nhánh "không đổi gì" → xem xét `Cow`
- [ ] Benchmark trước và sau để đo tác động thực sự
- [ ] Dùng `Cow<[T]>` cho slice transformations
- [ ] API public nên dùng `Cow` cho flexibility
- [ ] `impl From<&str> for Cow<str>` đã có sẵn

**Clippy lints:**

```bash
cargo clippy -- \
  -W clippy::redundant_clone
# Profiling:
cargo flamegraph --test your_test -- --test-thread 1
```

---

## OB-11: Pin Hiểu Sai (Pin Misuse)

### 1. Tên

**Pin Hiểu Sai** (Pin Misuse)

### 2. Phân loại

- **Lĩnh vực:** Ownership & Borrowing
- **Danh mục con:** Async / Memory Safety
- **Mã định danh:** OB-11

### 3. Mức nghiêm trọng

🔴 **CRITICAL** — Dùng `Pin` sai có thể dẫn đến **undefined behavior** khi Future bị move sau khi đã được polled, đặc biệt với self-referential futures và async generators.

### 4. Vấn đề

`Pin<P>` đảm bảo value được trỏ bởi `P` sẽ không bao giờ được move trong memory. Điều này cần thiết cho self-referential structs và async futures. Hiểu sai thường ở chỗ: dùng `unsafe` để unpin khi không đủ điều kiện, hoặc quên implement `PhantomPinned`.

```
  Safe Future (Unpin):
  ┌──────────────────────────────────────┐
  │  struct SimpleFuture { data: i32 }  │
  │  // data không self-reference        │
  │  // an toàn khi move                 │
  └──────────────────────────────────────┘

  Self-referential Future (KHÔNG Unpin):
  ┌──────────────────────────────────────────┐
  │  struct SelfRefFuture {                  │
  │    data: String,                         │
  │    ptr: *const String,  // → data        │
  │  }                                       │
  │  // Nếu SelfRefFuture bị move:          │
  │  //   data di chuyển đến address mới    │
  │  //   ptr vẫn trỏ địa chỉ cũ → DANGLING │
  └──────────────────────────────────────────┘
```

### 5. Phát hiện trong mã nguồn

**Dấu hiệu nhận biết:**
- `unsafe { Pin::new_unchecked(...) }` không có SAFETY comment
- Struct có pointer/reference tới chính nó nhưng không có `PhantomPinned`
- `get_unchecked_mut` trong `Pin` context
- Custom Future implementation không xử lý pinning đúng

**Regex patterns:**

```bash
# Tìm Pin::new_unchecked (unsafe)
rg 'Pin::new_unchecked' --type rust

# Tìm get_unchecked_mut
rg 'get_unchecked_mut' --type rust

# Tìm struct không có PhantomPinned nhưng có raw pointer field
rg 'struct\s+\w+\s*\{[^}]*\*const\|\*mut' --type rust

# Tìm PhantomPinned usage (đang dùng đúng)
rg 'PhantomPinned' --type rust

# Tìm impl Future manually
rg 'impl\s+Future\s+for' --type rust
```

### 6. Giải pháp

| Tình huống | Sai | Đúng |
|------------|-----|------|
| Self-referential struct | Không `PhantomPinned` | Thêm `_pin: PhantomPinned` |
| Pin từ Box | `Pin::new_unchecked` | `Box::pin(...)` |
| Truy cập `&mut T` từ Pin | `unsafe get_unchecked_mut` tùy tiện | Chỉ trong `Unpin` context hoặc verified invariants |
| Async generator | Custom Future | Dùng `async fn` — compiler tự handle |

**Rust code — BAD:**

```rust
use std::pin::Pin;
use std::marker::PhantomPinned;

// Self-referential struct thiếu PhantomPinned — có thể bị move!
struct BadSelfRef {
    data: String,
    self_ptr: *const String,  // trỏ vào data
}

impl BadSelfRef {
    fn new(data: String) -> Self {
        let mut s = BadSelfRef { data, self_ptr: std::ptr::null() };
        s.self_ptr = &s.data as *const String;  // BUG: địa chỉ của stack local
        s  // MOVED! self_ptr giờ là dangling pointer
    }
}

// Unsafe unpin không có justification
fn bad_unpin<T>(pinned: Pin<&mut T>) -> &mut T {
    // SAFETY: (không có comment, không có reasoning)
    unsafe { pinned.get_unchecked_mut() }  // UB nếu T is !Unpin
}
```

**Rust code — GOOD:**

```rust
use std::pin::Pin;
use std::marker::PhantomPinned;

struct SelfRef {
    data: String,
    self_ptr: *const String,
    _pin: PhantomPinned,  // Đánh dấu là !Unpin — không thể move khi pinned
}

impl SelfRef {
    fn new(data: String) -> Pin<Box<Self>> {
        let s = SelfRef {
            data,
            self_ptr: std::ptr::null(),
            _pin: PhantomPinned,
        };
        let mut boxed = Box::pin(s);

        // SAFETY: chúng ta đang set self_ptr để trỏ vào data của chính struct này.
        // Struct được pin trong Box nên sẽ không bao giờ move.
        // self_ptr chỉ được đặt một lần ở đây và không bao giờ thay đổi sau đó.
        let ptr = &boxed.data as *const String;
        unsafe { boxed.as_mut().get_unchecked_mut().self_ptr = ptr; }

        boxed
    }

    fn get_data(self: Pin<&Self>) -> &str {
        &self.data
    }
}

// Dùng async fn thay vì implement Future thủ công
async fn good_async_pattern() {
    let data = String::from("hello");
    // Compiler tự generate Future đúng với pinning
    some_async_op(&data).await;
}

async fn some_async_op(_: &str) {}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Struct có raw pointer → cân nhắc `PhantomPinned`
- [ ] Mọi `unsafe` pin operation → có SAFETY comment đầy đủ
- [ ] Ưu tiên `async fn` hơn manual `Future` implementation
- [ ] Test với `#[tokio::test]` và không đặt assumption về address stability
- [ ] Đọc Rust Nomicon chapter về Pin trước khi implement

**Clippy lints:**

```bash
cargo clippy -- \
  -W clippy::undocumented_unsafe_blocks
# Dùng Miri để detect Pin violations:
cargo +nightly miri test
```

---

## OB-12: Self-Referential Struct

### 1. Tên

**Self-Referential Struct** (Self-Referential Struct)

### 2. Phân loại

- **Lĩnh vực:** Ownership & Borrowing
- **Danh mục con:** Memory Safety / Lifetime
- **Mã định danh:** OB-12

### 3. Mức nghiêm trọng

🔴 **CRITICAL** — Self-referential struct không được pin đúng cách gây **dangling pointer** khi struct bị move, dẫn đến use-after-free và undefined behavior.

### 4. Vấn đề

Rust không cho phép struct chứa reference trỏ vào chính nó (borrow checker reject). Workaround phổ biến là dùng raw pointer — nhưng nếu struct bị move (trả về từ hàm, push vào Vec), con trỏ trỏ vào địa chỉ cũ (stack frame đã deallocated).

```
  Self-referential struct bị move:

  Stack frame A:
  ┌─────────────────────────────┐
  │  struct {                   │
  │    data: [0x1000]  "hello" │  ← actual data
  │    ptr:  0x1000            │  ← self-reference
  │  }                         │
  └─────────────────────────────┘
         │ MOVE (return, push_into_vec)
         ▼
  Stack frame B / Heap:
  ┌─────────────────────────────┐
  │  struct {                   │
  │    data: [0x2000]  "hello" │  ← moved to new address
  │    ptr:  0x1000            │  ← DANGLING! trỏ vào old address
  │  }                         │
  └─────────────────────────────┘
```

### 5. Phát hiện trong mã nguồn

**Dấu hiệu nhận biết:**
- Struct có `*const T` hoặc `*mut T` field trỏ vào field khác trong cùng struct
- `new()` function tạo struct rồi trả về bằng value (không phải `Pin<Box<>>`)
- Field kiểu `&'self T` (không valid trong Rust nhưng workaround bằng pointer)
- Linked list hoặc parser với internal cursor

**Regex patterns:**

```bash
# Tìm struct có raw pointer field (potential self-ref)
rg 'struct\s+\w+[^{]*\{[^}]*\*(?:const|mut)\s+\w' --type rust -A5

# Tìm kết hợp raw pointer + String/Vec trong cùng struct
rg '\*const\s+\w\|\*mut\s+\w' --type rust

# Tìm việc tạo raw pointer từ &self
rg '&self\.\w+\s+as\s+\*const\|&mut\s+self\.\w+\s+as\s+\*mut' --type rust

# Tìm PhantomPinned (đã xử lý đúng)
rg 'PhantomPinned' --type rust
```

### 6. Giải pháp

| Approach | Trường hợp | Implementation |
|----------|------------|----------------|
| Dùng indices thay pointer | Collection | Store `usize` index thay vì `*const T` |
| Pin + PhantomPinned | Cần self-ref thực sự | `Box::pin()` + unsafe init |
| `ouroboros` crate | API phức tạp | Macro generated safe API |
| Redesign | Hầu hết cases | Tách data và cursor |

**Rust code — BAD:**

```rust
// Self-referential struct — NGUY HIỂM
struct Parser {
    input: String,
    current: *const u8,  // trỏ vào input.as_ptr()
}

impl Parser {
    fn new(input: String) -> Self {  // trả về by value → MOVE!
        let current = input.as_ptr();
        Parser { input, current }  // current trỏ địa chỉ của input trước khi move
        // Sau move: input ở địa chỉ mới, current vẫn trỏ địa chỉ cũ → DANGLING
    }

    fn peek(&self) -> u8 {
        unsafe { *self.current }  // UB: đọc dangling pointer
    }
}

fn main() {
    let p = Parser::new(String::from("hello"));  // move từ new() → UB
    println!("{}", p.peek());  // UB!
}
```

**Rust code — GOOD (dùng indices):**

```rust
// Approach 1: Dùng index thay vì pointer — đơn giản nhất
struct Parser {
    input: String,
    pos: usize,  // index thay vì raw pointer
}

impl Parser {
    fn new(input: String) -> Self {
        Parser { input, pos: 0 }  // an toàn khi move
    }

    fn peek(&self) -> Option<u8> {
        self.input.as_bytes().get(self.pos).copied()
    }

    fn advance(&mut self) {
        self.pos += 1;
    }
}

// Approach 2: Tách data và parser
struct Input {
    data: String,
}

struct ParserState<'a> {
    input: &'a str,
    pos: usize,
}

impl<'a> ParserState<'a> {
    fn new(input: &'a Input) -> Self {
        ParserState { input: &input.data, pos: 0 }
    }

    fn peek(&self) -> Option<u8> {
        self.input.as_bytes().get(self.pos).copied()
    }
}

fn main() {
    let input = Input { data: String::from("hello world") };
    let mut parser = ParserState::new(&input);
    while let Some(b) = parser.peek() {
        print!("{}", b as char);
        parser.pos += 1;
    }
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Thay raw pointer self-reference bằng index
- [ ] Nếu cần self-ref thực sự → dùng `Pin<Box<T>>`
- [ ] Xem xét `ouroboros` hoặc `self_cell` crate cho safe API
- [ ] Chạy Miri để phát hiện dangling pointer
- [ ] Viết test move struct sau khi khởi tạo

**Clippy lints:**

```bash
cargo clippy -- \
  -W clippy::undocumented_unsafe_blocks
# Test với Miri:
cargo +nightly miri test
# Xem xét crates:
# ouroboros = "0.18"
# self_cell = "1.0"
```

---

## OB-13: Implicit Copy Surprise

### 1. Tên

**Implicit Copy Bất Ngờ** (Implicit Copy Surprise)

### 2. Phân loại

- **Lĩnh vực:** Ownership & Borrowing
- **Danh mục con:** Copy Semantics / Performance
- **Mã định danh:** OB-13

### 3. Mức nghiêm trọng

🟡 **MEDIUM** — Copy type có thể bị copy ngầm nhiều lần mà không có cảnh báo, gây hiệu năng kém với large structs. Ngược lại, quên rằng type là Copy dẫn đến code phức tạp không cần thiết.

### 4. Vấn đề

Rust types implement `Copy` sẽ được copy ngầm thay vì move. Điều này tốt cho small types (`i32`, `bool`, `f64`) nhưng nguy hiểm khi `#[derive(Copy)]` được thêm vào struct lớn — mỗi assignment tạo ra copy đầy đủ mà không có cảnh báo.

```
  Copy Type:
  ┌──────────────────────────────────┐
  │  let x: i32 = 5;                │
  │  let y = x;   // COPY (không move)│
  │  println!("{}", x);  // vẫn OK  │
  └──────────────────────────────────┘

  Large Struct với #[derive(Copy)]:
  ┌──────────────────────────────────────────────────┐
  │  #[derive(Copy, Clone)]                          │
  │  struct BigMatrix { data: [f64; 1000] }  // 8KB │
  │                                                  │
  │  let m1 = BigMatrix { data: [0.0; 1000] };      │
  │  let m2 = m1;  // COPY: 8KB memcpy ngầm!        │
  │  process(m1);  // COPY nữa: thêm 8KB memcpy!    │
  └──────────────────────────────────────────────────┘
```

### 5. Phát hiện trong mã nguồn

**Dấu hiệu nhận biết:**
- `#[derive(Copy, Clone)]` trên struct có field array lớn
- `#[derive(Copy)]` trên struct nhiều field
- Hàm nhận Copy type by value — mỗi lần gọi là một copy
- Iterator `.copied()` trên slice của large structs

**Regex patterns:**

```bash
# Tìm struct derive Copy
rg '#\[derive[^\]]*Copy[^\]]*\]' --type rust -A3

# Tìm struct có array field lớn với Copy
rg -B3 'data:\s*\[[^\]]+;\s*[0-9]{3,}' --type rust | rg 'Copy'

# Tìm hàm nhận struct by value (tiềm năng copy)
rg 'fn\s+\w+\s*\([^)]*:\s*[A-Z]\w*[^)&]*\)' --type rust

# Tìm .copied() trên iterator
rg '\.copied\(\)' --type rust
```

### 6. Giải pháp

| Tình huống | Vấn đề | Giải pháp |
|------------|---------|-----------|
| Large struct với Copy | 8KB ngầm mỗi assignment | Bỏ Copy, dùng clone() explicit |
| Small POD struct | Không có Copy → move unnecessarily | Thêm `#[derive(Copy, Clone)]` |
| Hàm nhận large Copy struct | Copy không cần thiết | Đổi sang `&T` |
| Muốn cả hai | Cần owned đôi khi | Nhận `impl Borrow<T>` |

**Rust code — BAD:**

```rust
// Copy không nên cho struct lớn
#[derive(Debug, Copy, Clone)]
struct Transform {
    matrix: [f64; 16],  // 128 bytes
    position: [f64; 3], // 24 bytes
    rotation: [f64; 4], // 32 bytes
}  // Tổng: ~184 bytes — quá lớn cho Copy

fn apply_transform(t: Transform, points: &mut Vec<[f64; 3]>) {  // Copy ngầm
    for point in points.iter_mut() {
        // sử dụng t...
        let _ = t.matrix[0];
    }
}

fn main() {
    let t = Transform { matrix: [0.0; 16], position: [0.0; 3], rotation: [0.0; 4] };
    let mut points = vec![[1.0, 2.0, 3.0]];
    apply_transform(t, &mut points);  // 184 byte copy
    apply_transform(t, &mut points);  // 184 byte copy lần nữa
    apply_transform(t, &mut points);  // ...
}
```

**Rust code — GOOD:**

```rust
// Không có Copy — explicit clone khi thực sự cần
#[derive(Debug, Clone)]
struct Transform {
    matrix: [f64; 16],
    position: [f64; 3],
    rotation: [f64; 4],
}

fn apply_transform(t: &Transform, points: &mut Vec<[f64; 3]>) {  // borrow: zero cost
    for point in points.iter_mut() {
        let _ = t.matrix[0];
    }
}

// Copy phù hợp cho small, POD types
#[derive(Debug, Copy, Clone, PartialEq)]
struct Point2D {
    x: f32,
    y: f32,
}  // 8 bytes — phù hợp để Copy

fn translate(p: Point2D, dx: f32, dy: f32) -> Point2D {  // Copy OK ở đây
    Point2D { x: p.x + dx, y: p.y + dy }
}

fn main() {
    let t = Transform { matrix: [0.0; 16], position: [0.0; 3], rotation: [0.0; 4] };
    let mut points = vec![[1.0, 2.0, 3.0]];
    apply_transform(&t, &mut points);  // zero-copy reference
    apply_transform(&t, &mut points);  // vẫn zero-copy
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Struct > 64 bytes → không nên `#[derive(Copy)]`
- [ ] Struct chứa non-trivial data → xem xét kỹ trước khi Copy
- [ ] Hàm nhận large struct by value → đổi sang `&T`
- [ ] Benchmark copy cost cho struct trong hot path
- [ ] `#[derive(Copy)]` chỉ cho POD types nhỏ

**Clippy lints:**

```bash
cargo clippy -- \
  -W clippy::large_stack_arrays \
  -W clippy::large_types_passed_by_value
```

---

## OB-14: Mutable Aliasing Ẩn (Hidden Mutable Aliasing)

### 1. Tên

**Mutable Aliasing Ẩn** (Hidden Mutable Aliasing)

### 2. Phân loại

- **Lĩnh vực:** Ownership & Borrowing
- **Danh mục con:** Safety / Data Race
- **Mã định danh:** OB-14

### 3. Mức nghiêm trọng

🟠 **HIGH** — Mutable aliasing ẩn qua raw pointer hoặc interior mutability có thể tạo data race trong single-threaded code hoặc undefined behavior nếu dùng với unsafe.

### 4. Vấn đề

Rust forbid aliasing mutable references ở compile-time. Tuy nhiên, `UnsafeCell` và raw pointers cho phép tạo mutable aliasing — an toàn chỉ khi invariants được duy trì thủ công. Khi lập trình viên không hiểu điều này, họ tạo aliasing mutable access mà trông có vẻ OK nhưng là UB.

```
  Aliasing Rule của Rust (STACKED BORROWS):
  ┌────────────────────────────────────────────┐
  │  &T   có thể alias nhau — OK              │
  │  &mut T không được alias — compile error  │
  │                                            │
  │  Raw pointer: thoát khỏi compiler check  │
  │  UnsafeCell: interior mutability          │
  │  → Invariants phải được maintain thủ công │
  └────────────────────────────────────────────┘

  Hidden aliasing qua index trick:
  let v = &mut vec[0];   // mutable ref tới index 0
  vec.push(new_item);    // COMPILE ERROR: vec borrowed
  // Nhưng nếu bypass bằng unsafe...
  // → reallocation → v là dangling pointer
```

### 5. Phát hiện trong mã nguồn

**Dấu hiệu nhận biết:**
- Hai `*mut T` raw pointer từ cùng allocation
- `UnsafeCell` không có wrapper type an toàn
- `split_at_mut` workaround bằng raw pointer thủ công
- Global mutable state qua `static mut`

**Regex patterns:**

```bash
# Tìm static mut (mutable aliasing tiềm ẩn)
rg 'static\s+mut\s+' --type rust

# Tìm UnsafeCell usage
rg 'UnsafeCell' --type rust

# Tìm nhiều raw pointer từ cùng source
rg 'as\s*\*mut' --type rust -n

# Tìm unsafe block với dereference raw pointer
rg 'unsafe\s*\{[^}]*\*\s*\w' --type rust

# Tìm &raw mut (Rust 1.82+)
rg '&raw\s+mut' --type rust
```

### 6. Giải pháp

| Pattern | Vấn đề | Giải pháp |
|---------|---------|-----------|
| `static mut` | Global mutable state, data race | `Mutex<T>` hoặc `OnceLock<T>` |
| Hai `*mut T` từ Vec | UB khi Vec realloc | `split_at_mut()` |
| `UnsafeCell` exposed | Không có safety boundary | Wrap trong safe abstraction |
| Multiple mutable access | Compiler bypass | Tái cấu trúc ownership |

**Rust code — BAD:**

```rust
// static mut — data race trong multi-thread, UB trong single-thread nếu re-entrant
static mut COUNTER: u64 = 0;

fn increment() {
    unsafe {
        COUNTER += 1;  // UB: không có synchronization
    }
}

// Tạo hai mutable reference từ cùng Vec bằng unsafe
fn bad_two_mut(v: &mut Vec<i32>) {
    let ptr = v.as_mut_ptr();
    unsafe {
        let first: &mut i32 = &mut *ptr;
        let second: &mut i32 = &mut *ptr.add(1);
        // Hai &mut vào cùng allocation — vi phạm aliasing rules
        *first = 10;
        *second = 20;
        // Thực ra ở đây OK vì khác index, nhưng compiler không biết
        // và optimizer có thể dựa vào aliasing rules để tối ưu sai
    }
}
```

**Rust code — GOOD:**

```rust
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::OnceLock;

// Dùng atomic cho global counter
static COUNTER: AtomicU64 = AtomicU64::new(0);

fn increment() {
    COUNTER.fetch_add(1, Ordering::Relaxed);  // thread-safe, không UB
}

fn get_count() -> u64 {
    COUNTER.load(Ordering::Relaxed)
}

// Tách mutable slice đúng cách
fn good_two_mut(v: &mut Vec<i32>) {
    if v.len() >= 2 {
        // split_at_mut đảm bảo không alias
        let (left, right) = v.split_at_mut(1);
        left[0] = 10;
        right[0] = 20;
    }
}

// Global state phức tạp hơn dùng OnceLock + Mutex
static CONFIG: OnceLock<std::sync::Mutex<Vec<String>>> = OnceLock::new();

fn get_config() -> &'static std::sync::Mutex<Vec<String>> {
    CONFIG.get_or_init(|| std::sync::Mutex::new(vec![]))
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Không dùng `static mut` — dùng `Mutex`, `AtomicT`, hoặc `OnceLock`
- [ ] Mọi `UnsafeCell` phải được wrap trong safe abstraction
- [ ] Dùng `split_at_mut()` thay vì raw pointer trick
- [ ] Chạy Miri với STACKED_BORROWS để phát hiện aliasing vi phạm
- [ ] Không expose raw pointer trong public API

**Clippy lints:**

```bash
cargo clippy -- \
  -W clippy::mut_from_ref \
  -W clippy::cast_ref_to_mut
# Miri với Stacked Borrows:
MIRIFLAGS="-Zmiri-strict-provenance" cargo +nightly miri test
```

---

## OB-15: Box Thừa (Unnecessary Boxing)

### 1. Tên

**Box Thừa** (Unnecessary Boxing)

### 2. Phân loại

- **Lĩnh vực:** Ownership & Borrowing
- **Danh mục con:** Allocation / Performance
- **Mã định danh:** OB-15

### 3. Mức nghiêm trọng

🟡 **MEDIUM** — `Box<T>` không cần thiết tạo heap allocation và thêm pointer indirection, làm chậm code do cache miss và allocation overhead.

### 4. Vấn đề

`Box<T>` hữu ích khi: (1) size của T không biết tại compile-time, (2) cần owned trait object, (3) tránh large stack allocation. Dùng ngoài những trường hợp này là boxing không cần thiết, tốn heap allocation và thêm indirection.

```
  Box<T> = Heap allocation + Pointer:

  Stack:                 Heap:
  ┌──────────┐          ┌──────────────────┐
  │ ptr ─────┼─────────►│  T (actual data) │
  └──────────┘          └──────────────────┘

  Khi Box không cần thiết:
  Box<i32>   → chỉ cần i32 (4 bytes stack)
  Box<String>→ String đã là indirection
  Box<Vec<T>>→ Vec<T> đã heap-allocated
  fn f() -> Box<ConcreteType> → chỉ cần ConcreteType
```

### 5. Phát hiện trong mã nguồn

**Dấu hiệu nhận biết:**
- `Box<String>`, `Box<Vec<T>>` — đã heap-allocated rồi
- `Box<i32>`, `Box<bool>` — type nhỏ không cần box
- Hàm trả về `Box<ConcreteType>` thay vì `ConcreteType`
- `Box::new(...)` cho struct nhỏ (<= 16 bytes)

**Regex patterns:**

```bash
# Tìm Box wrapping already-heap-allocated types
rg 'Box<String>\|Box<Vec<\|Box<HashMap<\|Box<BTreeMap<' --type rust

# Tìm Box wrapping primitive types
rg 'Box<i\d\+\|Box<u\d\+\|Box<f\d\+\|Box<bool\|Box<char' --type rust

# Tìm fn return Box<ConcreteType> (không phải trait object)
rg '->\s*Box<[A-Z][A-Za-z0-9]*>' --type rust

# Tìm Box::new
rg 'Box::new\s*(' --type rust -n

# Tìm Box<dyn ...> (hợp lệ — trait object)
rg 'Box<dyn\s' --type rust
```

### 6. Giải pháp

| Trường hợp | Box thừa | Thay thế |
|------------|---------|----------|
| Primitive types | `Box<i32>` | `i32` |
| String | `Box<String>` | `String` |
| Vec | `Box<Vec<T>>` | `Vec<T>` |
| Concrete return type | `Box<Foo>` | `Foo` |
| Recursive struct | Cần `Box<Node>` | Giữ Box (cần thiết!) |
| Trait object | `Box<dyn Trait>` | Giữ Box (cần thiết!) |
| Large stack struct | `LargeStruct` | `Box<LargeStruct>` (đây là dùng đúng) |

**Rust code — BAD:**

```rust
// Box wrapping primitives và heap types — không cần thiết
fn get_count() -> Box<i32> {  // i32 nhỏ, không cần Box
    Box::new(42)
}

fn get_names() -> Box<Vec<String>> {  // Vec đã là heap
    Box::new(vec!["Alice".to_string(), "Bob".to_string()])
}

struct Config {
    name: Box<String>,    // String đã heap-allocated
    count: Box<i32>,      // primitive không cần Box
    tags: Box<Vec<String>>,  // Vec đã heap
}

impl Config {
    fn new() -> Box<Config> {  // Config nhỏ, không cần Box
        Box::new(Config {
            name: Box::new(String::from("default")),
            count: Box::new(0),
            tags: Box::new(vec![]),
        })
    }
}
```

**Rust code — GOOD:**

```rust
// Không Box khi không cần thiết
fn get_count() -> i32 {
    42
}

fn get_names() -> Vec<String> {
    vec!["Alice".to_string(), "Bob".to_string()]
}

struct Config {
    name: String,      // String trực tiếp
    count: i32,        // primitive trực tiếp
    tags: Vec<String>, // Vec trực tiếp
}

impl Config {
    fn new() -> Self {  // trả về by value
        Config {
            name: String::from("default"),
            count: 0,
            tags: vec![],
        }
    }
}

// Box HỢP LỆ: Recursive type (bắt buộc)
enum Tree {
    Leaf(i32),
    Node(Box<Tree>, Box<Tree>),  // cần Box để có finite size
}

// Box HỢP LỆ: Trait object
fn make_handler() -> Box<dyn std::error::Error> {
    Box::new(std::io::Error::new(std::io::ErrorKind::Other, "error"))
}

// Box HỢP LỆ: Tránh large stack allocation
struct LargeData {
    buffer: [u8; 1024 * 1024],  // 1MB — nên Box
}

fn process() -> Box<LargeData> {
    Box::new(LargeData { buffer: [0u8; 1024 * 1024] })
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] `Box<String>`, `Box<Vec<T>>` → xóa Box
- [ ] `Box<i32>`, `Box<bool>` → xóa Box
- [ ] Hàm return `Box<ConcreteType>` → return `ConcreteType`
- [ ] Giữ Box cho: recursive types, trait objects, >1MB structs
- [ ] Review allocation với cargo flamegraph trước khi tối ưu

**Clippy lints:**

```bash
cargo clippy -- \
  -W clippy::box_collection \
  -W clippy::redundant_allocation \
  -W clippy::borrowed_box
```

---

## Tóm tắt Domain 01

| Mã | Tên | Mức | Clippy Key Lint |
|----|-----|-----|-----------------|
| OB-01 | Clone Thừa Thãi | 🟡 MEDIUM | `redundant_clone`, `needless_pass_by_value` |
| OB-02 | RefCell Lạm Dụng | 🟠 HIGH | `borrow_interior_mutable_const` |
| OB-03 | Lifetime Elision Sai | 🟠 HIGH | `needless_lifetimes` |
| OB-04 | Vòng Tham Chiếu Rc | 🔴 CRITICAL | `rc_clone_in_vec_init` + Miri |
| OB-05 | Borrow Checker Bypass | 🔴 CRITICAL | `undocumented_unsafe_blocks` + Miri |
| OB-06 | Move Sau Borrow | 🟠 HIGH | `needless_pass_by_value` |
| OB-07 | String vs &str | 🟡 MEDIUM | `ptr_arg`, `str_to_string` |
| OB-08 | Mutex Poisoning | 🟠 HIGH | `mutex_atomic` |
| OB-09 | Drop Order Bất Ngờ | 🟠 HIGH | `await_holding_lock` |
| OB-10 | Cow Không Dùng | 🟡 MEDIUM | `redundant_clone` |
| OB-11 | Pin Hiểu Sai | 🔴 CRITICAL | `undocumented_unsafe_blocks` + Miri |
| OB-12 | Self-Referential Struct | 🔴 CRITICAL | Miri (STACKED_BORROWS) |
| OB-13 | Implicit Copy | 🟡 MEDIUM | `large_stack_arrays` |
| OB-14 | Mutable Aliasing Ẩn | 🟠 HIGH | `mut_from_ref`, `cast_ref_to_mut` |
| OB-15 | Box Thừa | 🟡 MEDIUM | `box_collection`, `redundant_allocation` |

### Phân bố mức độ Domain 01

- 🔴 CRITICAL: 4 (OB-04, OB-05, OB-11, OB-12)
- 🟠 HIGH: 6 (OB-02, OB-03, OB-06, OB-08, OB-09, OB-14)
- 🟡 MEDIUM: 5 (OB-01, OB-07, OB-10, OB-13, OB-15)

### Lệnh kiểm tra toàn diện cho Domain 01

```bash
# Chạy tất cả Clippy lints liên quan
cargo clippy -- \
  -W clippy::redundant_clone \
  -W clippy::needless_pass_by_value \
  -W clippy::ptr_arg \
  -W clippy::box_collection \
  -W clippy::redundant_allocation \
  -W clippy::borrowed_box \
  -W clippy::rc_clone_in_vec_init \
  -W clippy::undocumented_unsafe_blocks \
  -W clippy::mut_from_ref \
  -W clippy::await_holding_lock \
  -W clippy::str_to_string \
  -W clippy::large_stack_arrays

# Chạy Miri cho CRITICAL patterns
cargo +nightly miri test

# Miri với Stacked Borrows strict mode
MIRIFLAGS="-Zmiri-strict-provenance" cargo +nightly miri test
```
