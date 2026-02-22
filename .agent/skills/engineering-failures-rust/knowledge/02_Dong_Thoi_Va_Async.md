# Lĩnh vực 02: Đồng Thời Và Async
# Domain 02: Concurrency & Async

> **Lĩnh vực:** Đồng Thời và Lập Trình Bất Đồng Bộ
> **Số mẫu:** 18
> **Ngôn ngữ:** Rust
> **Ngày cập nhật:** 2026-02-18

---

## Tổng quan

Rust cung cấp các nguyên thủy đồng thời an toàn tại compile-time (`Send`, `Sync`, ownership) và hệ sinh thái async phong phú (Tokio, async-std). Tuy nhiên, ranh giới giữa sync và async, giữa thread-pool và executor, vẫn ẩn chứa nhiều bẫy nghiêm trọng — từ deadlock, starvation đến undefined behavior trong cancellation.

---

## Mục lục

| #  | Mã     | Tên mẫu                                 | Mức độ      |
|----|--------|-----------------------------------------|-------------|
| 1  | CA-01  | Blocking Trong Async                    | 🔴 CRITICAL |
| 2  | CA-02  | Tokio Runtime Lồng Nhau                 | 🔴 CRITICAL |
| 3  | CA-03  | Send/Sync Thiếu                         | 🟠 HIGH     |
| 4  | CA-04  | Deadlock Arc<Mutex>                     | 🔴 CRITICAL |
| 5  | CA-05  | Channel Đầy Không Xử Lý                 | 🟠 HIGH     |
| 6  | CA-06  | Bầy Đàn Ồ Ạt                           | 🟠 HIGH     |
| 7  | CA-07  | Select Bias                             | 🟡 MEDIUM   |
| 8  | CA-08  | Spawn Không Join                        | 🟠 HIGH     |
| 9  | CA-09  | Async Trait Overhead                    | 🟡 MEDIUM   |
| 10 | CA-10  | Rayon Trong Tokio                       | 🔴 CRITICAL |
| 11 | CA-11  | RwLock Starvation                       | 🟠 HIGH     |
| 12 | CA-12  | Atomic Ordering Sai                     | 🔴 CRITICAL |
| 13 | CA-13  | Future Không Poll                       | 🟡 MEDIUM   |
| 14 | CA-14  | Cancellation Unsafety                   | 🟠 HIGH     |
| 15 | CA-15  | Mutex Guard Qua Await                   | 🔴 CRITICAL |
| 16 | CA-16  | Oneshot Receiver Drop                   | 🟡 MEDIUM   |
| 17 | CA-17  | Task Local Confusion                    | 🟡 MEDIUM   |
| 18 | CA-18  | Graceful Shutdown Thiếu                 | 🟠 HIGH     |

---

## CA-01: Blocking Trong Async (Blocking in Async)

### 1. Tên

**Blocking Trong Async** (Blocking in Async Context)

### 2. Phân loại

- **Lĩnh vực:** Concurrency & Async
- **Danh mục con:** Executor Starvation / Latency
- **Mã định danh:** CA-01

### 3. Mức nghiêm trọng

🔴 **CRITICAL** — Gọi hàm blocking (I/O, sleep, tính toán nặng) trực tiếp trong async task làm tê liệt toàn bộ Tokio worker thread, gây starvation cho các task khác và tăng latency đột biến.

### 4. Vấn đề

Tokio sử dụng một pool thread nhỏ (mặc định = số CPU). Mỗi thread chạy nhiều async task bằng cách poll chúng xen kẽ. Khi một task gọi hàm blocking, toàn bộ thread bị "đóng băng" — không task nào khác trên thread đó được tiến hành cho đến khi call blocking kết thúc.

```
  Tokio Worker Thread Pool (4 threads)
  ┌──────────┬──────────┬──────────┬──────────┐
  │ Thread 1 │ Thread 2 │ Thread 3 │ Thread 4 │
  └────┬─────┴──────────┴──────────┴──────────┘
       │
       │  task_A được schedule → gọi std::thread::sleep(10s)
       ▼
  ┌─────────────────────────────────────────────┐
  │  Thread 1: FROZEN for 10 seconds            │
  │  task_B, task_C, task_D ... tất cả CHỜ     │
  │  Throughput giảm 25% (1/4 thread mất)       │
  └─────────────────────────────────────────────┘

  Nếu 4/4 thread bị block → toàn bộ runtime CHẾT
```

**Nguyên nhân phổ biến:**
- Dùng `std::thread::sleep` thay vì `tokio::time::sleep`
- Đọc file đồng bộ (`std::fs::read`) trong async fn
- Gọi thư viện sync nặng (database driver cũ, C FFI)
- Tính toán CPU-intensive trực tiếp trong async block

### 5. Phát hiện trong mã nguồn

**Dấu hiệu:**
- `std::thread::sleep` bên trong `async fn`
- `std::fs`, `std::net` bên trong `async fn` không có `spawn_blocking`
- Hàm sync trả về kết quả dài trong context async
- Log thấy "task is taking a long time" từ Tokio

**Ripgrep:**
```bash
# Tìm blocking sleep trong async context
rg "thread::sleep" --type rust

# Tìm std::fs trong async fn
rg -n "std::fs::" --type rust

# Tìm blocking read/write
rg -n "(std::io::Read|std::io::Write)" --type rust
```

### 6. Giải pháp

| Tình huống | Giải pháp |
|-----------|-----------|
| Sleep | `tokio::time::sleep` |
| File I/O | `tokio::fs` hoặc `spawn_blocking` |
| CPU-intensive | `tokio::task::spawn_blocking` |
| Thư viện sync | `spawn_blocking` + channel để nhận kết quả |

```rust
// ❌ BAD: Blocking trong async
async fn process_request(path: &str) -> String {
    std::thread::sleep(std::time::Duration::from_secs(1)); // BLOCKS THREAD
    std::fs::read_to_string(path).unwrap()                 // BLOCKS THREAD
}

// ✅ GOOD: Dùng async I/O
async fn process_request(path: &str) -> String {
    tokio::time::sleep(std::time::Duration::from_secs(1)).await; // Non-blocking
    tokio::fs::read_to_string(path).await.unwrap()               // Non-blocking
}

// ✅ GOOD: CPU-intensive → spawn_blocking
async fn process_heavy(data: Vec<u8>) -> Vec<u8> {
    tokio::task::spawn_blocking(move || {
        // heavy computation here — runs on blocking thread pool
        compress_data(data)
    })
    .await
    .expect("blocking task panicked")
}

// ✅ GOOD: Thư viện sync cần kết quả
async fn query_sync_db(query: String) -> Result<Vec<Row>, DbError> {
    let result = tokio::task::spawn_blocking(move || {
        sync_db_client.execute(&query)
    })
    .await
    .map_err(|e| DbError::JoinError(e))??;
    Ok(result)
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Không có `std::thread::sleep` trong bất kỳ `async fn` nào
- [ ] Không có `std::fs::*` trong `async fn` (dùng `tokio::fs`)
- [ ] CPU > 1ms → `spawn_blocking`
- [ ] Dùng `tokio-console` để phát hiện task bị block lâu
- [ ] Review tất cả FFI calls trong async context

**Clippy / Công cụ:**
```bash
# Tokio console để monitor task starvation
cargo add tokio-console

# Lint thủ công
rg "std::thread::sleep|std::fs::" --type rust
```

---

## CA-02: Tokio Runtime Lồng Nhau (Nested Runtime)

### 1. Tên

**Tokio Runtime Lồng Nhau** (Nested Tokio Runtime)

### 2. Phân loại

- **Lĩnh vực:** Concurrency & Async
- **Danh mục con:** Runtime Management / Panic
- **Mã định danh:** CA-02

### 3. Mức nghiêm trọng

🔴 **CRITICAL** — Tạo `Runtime::block_on` bên trong một Tokio runtime đang chạy gây panic ngay lập tức: "Cannot start a runtime from within a Tokio runtime."

### 4. Vấn đề

Tokio không cho phép gọi `block_on` từ một async context đang chạy vì nó sẽ cố gắng block thread hiện tại — điều không thể làm khi thread đó đang thuộc Tokio worker pool.

```
  Tokio Runtime A (main)
  └── Worker Thread
       └── async fn foo()
            └── Runtime::new().block_on(...)  ← PANIC!
                 "Cannot start a runtime
                  from within a Tokio runtime"

  Nguyên nhân: block_on cần block thread hiện tại
               nhưng thread thuộc Runtime A,
               không thể block nó cho Runtime B
```

**Nguyên nhân phổ biến:**
- Thư viện bên thứ ba gọi `block_on` bên trong
- Hàm helper sync cần kết quả async → tạo runtime mới
- `actix-rt` kết hợp với `tokio` runtime

### 5. Phát hiện trong mã nguồn

**Dấu hiệu:**
- Panic "Cannot start a runtime from within a Tokio runtime"
- `Runtime::new()` hoặc `Builder::new_*().build()` trong non-main code
- `block_on` trong hàm được gọi từ async context

**Ripgrep:**
```bash
# Tìm block_on
rg -n "\.block_on\(" --type rust

# Tìm tạo runtime mới
rg -n "Runtime::new\(\)|Builder::new" --type rust

# Tìm tokio::main lồng nhau
rg -n "#\[tokio::main\]" --type rust
```

### 6. Giải pháp

| Tình huống | Giải pháp |
|-----------|-----------|
| Cần kết quả async từ sync | `tokio::task::block_in_place` |
| Thư viện cần runtime riêng | `spawn_blocking` + `Handle::current()` |
| Test cần runtime | `#[tokio::test]` |
| Main entry point | Chỉ một `#[tokio::main]` |

```rust
// ❌ BAD: Tạo runtime trong async context
async fn bad_wrapper() {
    let rt = tokio::runtime::Runtime::new().unwrap(); // PANIC tại đây
    let result = rt.block_on(async {
        some_async_work().await
    });
}

// ✅ GOOD: Dùng Handle để re-enter
async fn good_wrapper() {
    // Nếu THỰC SỰ cần block, dùng block_in_place
    let result = tokio::task::block_in_place(|| {
        tokio::runtime::Handle::current().block_on(async {
            some_async_work().await
        })
    });
}

// ✅ GOOD: Hàm sync cần async result
fn sync_fn_needing_async() -> String {
    // Chạy trong spawn_blocking, có thể dùng Handle
    let handle = tokio::runtime::Handle::current();
    handle.block_on(async {
        some_async_work().await
    })
}

// Gọi đúng cách:
async fn caller() {
    let result = tokio::task::spawn_blocking(sync_fn_needing_async)
        .await
        .unwrap();
}

// ✅ GOOD: Test
#[tokio::test]
async fn my_test() {
    // Không cần tạo runtime thủ công
    let result = some_async_work().await;
    assert_eq!(result, expected);
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Chỉ một `#[tokio::main]` trong toàn bộ binary
- [ ] Không có `Runtime::new()` ngoài main/test setup
- [ ] Khi cần `block_on` trong async → dùng `block_in_place`
- [ ] Kiểm tra dependencies không tạo runtime riêng
- [ ] Dùng `tokio::test` cho mọi async test

**Clippy / Công cụ:**
```bash
# Không có clippy lint sẵn, tìm thủ công
rg "Runtime::new\(\)|\.block_on\(" --type rust

# Kiểm tra dependency có tạo runtime không
cargo tree | grep "tokio"
```

---

## CA-03: Send/Sync Thiếu (Missing Send/Sync Bounds)

### 1. Tên

**Send/Sync Thiếu** (Missing Send/Sync Trait Bounds)

### 2. Phân loại

- **Lĩnh vực:** Concurrency & Async
- **Danh mục con:** Type Safety / Compile Error
- **Mã định danh:** CA-03

### 3. Mức nghiêm trọng

🟠 **HIGH** — Thiếu `Send`/`Sync` bounds dẫn đến lỗi compile khó hiểu, hoặc tệ hơn là dùng `unsafe` không đúng để bypass — gây data race tiềm ẩn.

### 4. Vấn đề

Tokio yêu cầu Future được spawn phải implement `Send` (có thể gửi sang thread khác). Nếu Future chứa type không `Send` (như `Rc`, `RefCell`, `*mut T`), compile sẽ thất bại với thông báo lỗi dài và khó đọc.

```
  tokio::spawn(future)
       │
       ▼ requires: Future: Send + 'static
  ┌─────────────────────────────────────────┐
  │  async fn foo() {                       │
  │      let x = Rc::new(42);  ← !Send     │
  │      bar().await;           ← future   │
  │      println!("{}", x);    ← x still   │
  │  }                           held here  │
  └─────────────────────────────────────────┘
  Error: `Rc<i32>` cannot be sent between
         threads safely
```

**Nguyên nhân phổ biến:**
- Giữ `Rc<T>` qua `.await` point
- `RefCell<T>` trong struct được spawn
- Raw pointer `*mut T` trong Future
- Closure capture non-Send type

### 5. Phát hiện trong mã nguồn

**Dấu hiệu:**
- Lỗi compile: "cannot be sent between threads safely"
- Lỗi compile: "the trait `Send` is not implemented for..."
- `Rc::new` hoặc `RefCell::new` trong async function

**Ripgrep:**
```bash
# Tìm Rc trong async context (potential issue)
rg -n "Rc::new\|RefCell::new" --type rust

# Tìm raw pointer trong struct
rg -n "\*mut\s+\w+" --type rust

# Tìm spawn mà không có Send bound
rg -n "tokio::spawn|thread::spawn" --type rust
```

### 6. Giải pháp

| Type không Send | Thay thế Send-safe |
|----------------|-------------------|
| `Rc<T>` | `Arc<T>` |
| `RefCell<T>` | `Mutex<T>` hoặc `RwLock<T>` |
| `*mut T` | Bọc trong struct với unsafe Send impl (cẩn thận) |
| Non-Send closure | Chuyển data ra khỏi await point |

```rust
// ❌ BAD: Rc qua await point
async fn bad_fn() {
    let data = Rc::new(vec![1, 2, 3]); // Rc: !Send
    some_async_call().await;            // data còn sống qua đây
    println!("{:?}", data);             // Error!
}

// ✅ GOOD: Arc thay Rc
async fn good_fn() {
    let data = Arc::new(vec![1, 2, 3]); // Arc: Send
    some_async_call().await;
    println!("{:?}", data);
}

// ✅ GOOD: Drop trước await nếu không cần sau
async fn good_fn_drop() {
    {
        let data = Rc::new(vec![1, 2, 3]);
        println!("{:?}", data);
        // data dropped here (end of block)
    }
    some_async_call().await; // data không còn tồn tại
}

// ✅ GOOD: Generic bound rõ ràng
async fn spawn_safe<T>(value: T)
where
    T: Send + 'static,
{
    tokio::spawn(async move {
        process(value).await;
    });
}

// ✅ GOOD: Trait object cần Send
fn make_handler() -> Box<dyn Fn() -> BoxFuture<'static, ()> + Send + Sync> {
    Box::new(|| Box::pin(async { do_work().await }))
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Không dùng `Rc`/`RefCell` trong async fn nếu spawn vào Tokio
- [ ] Kiểm tra tất cả struct được spawn có implement `Send`
- [ ] Khi viết trait object trong async: `Box<dyn Trait + Send + Sync>`
- [ ] Dùng `#[tokio::test]` để catch Send errors sớm
- [ ] Tránh giữ non-Send value qua `.await` point

**Clippy / Công cụ:**
```bash
cargo clippy -- -W clippy::future_not_send

# Kiểm tra Send manually
# (Rust compiler sẽ bắt được khi build)
cargo check
```

---

## CA-04: Deadlock Arc<Mutex> (Arc<Mutex> Deadlock)

### 1. Tên

**Deadlock Arc\<Mutex\>** (Mutex Deadlock via Arc)

### 2. Phân loại

- **Lĩnh vực:** Concurrency & Async
- **Danh mục con:** Deadlock / Liveness
- **Mã định danh:** CA-04

### 3. Mức nghiêm trọng

🔴 **CRITICAL** — Deadlock khiến chương trình treo vô thời hạn, không panic, không log, không thể recover — chỉ có thể phát hiện qua timeout hoặc monitoring.

### 4. Vấn đề

Deadlock xảy ra khi hai hoặc nhiều thread cùng chờ nhau giải phóng lock. Với `Arc<Mutex<T>>`, pattern nguy hiểm nhất là lock theo thứ tự khác nhau, hoặc lock lần hai trên cùng thread (re-entrant lock — Rust Mutex không hỗ trợ).

```
  Thread A                    Thread B
  ─────────────────────────   ─────────────────────────
  lock(mutex_A) ✓             lock(mutex_B) ✓
  ...                         ...
  lock(mutex_B) ← WAIT        lock(mutex_A) ← WAIT
       │                            │
       └──────── DEADLOCK ──────────┘

  Đặc biệt nguy hiểm: Re-entrant trong Rust
  lock(mutex_A) ✓
  gọi hàm()
      └── lock(mutex_A) ← PANIC (poisoned) hoặc DEADLOCK
```

**Nguyên nhân phổ biến:**
- Khóa hai mutex theo thứ tự khác nhau ở các nơi
- Gọi hàm khác trong khi giữ lock, hàm đó cũng cần lock
- Async: giữ lock qua `.await` (xem CA-15)
- Recursive lock trên cùng thread

### 5. Phát hiện trong mã nguồn

**Dấu hiệu:**
- Chương trình treo không phản hồi
- CPU 0% nhưng process vẫn chạy
- `RUST_BACKTRACE` không giúp ích (thread đang chờ)
- Dùng `gdb` hoặc `lldb` thấy tất cả thread ở `futex_wait`

**Ripgrep:**
```bash
# Tìm multiple mutex lock trong cùng scope
rg -n "\.lock\(\)" --type rust

# Tìm các nơi lock nhiều mutex
rg -n "let.*lock.*=.*lock\(\)" --type rust -A 5
```

### 6. Giải pháp

| Nguyên nhân | Giải pháp |
|------------|-----------|
| Lock thứ tự khác nhau | Thiết lập thứ tự lock toàn cục |
| Re-entrant lock | Tách logic, truyền data thay vì lock lại |
| Lock quá rộng | Giảm scope của MutexGuard |
| Nhiều mutex | Xem xét dùng một Mutex bọc struct lớn hơn |

```rust
// ❌ BAD: Thứ tự lock khác nhau
async fn thread_a(a: Arc<Mutex<i32>>, b: Arc<Mutex<i32>>) {
    let _ga = a.lock().unwrap(); // Lock A trước
    let _gb = b.lock().unwrap(); // Lock B sau
}

async fn thread_b(a: Arc<Mutex<i32>>, b: Arc<Mutex<i32>>) {
    let _gb = b.lock().unwrap(); // Lock B trước ← DEADLOCK với thread_a
    let _ga = a.lock().unwrap(); // Lock A sau
}

// ✅ GOOD: Thứ tự lock nhất quán (luôn A trước B)
fn lock_both(a: &Mutex<i32>, b: &Mutex<i32>) -> (MutexGuard<i32>, MutexGuard<i32>) {
    // Dùng địa chỉ pointer để xác định thứ tự nhất quán
    if (a as *const _) < (b as *const _) {
        let ga = a.lock().unwrap();
        let gb = b.lock().unwrap();
        (ga, gb)
    } else {
        let gb = b.lock().unwrap();
        let ga = a.lock().unwrap();
        (ga, gb)
    }
}

// ✅ GOOD: Tránh lock lồng nhau bằng cách clone data ra
fn update_without_nesting(shared: Arc<Mutex<MyData>>) {
    let data_copy = {
        let guard = shared.lock().unwrap();
        guard.clone() // Clone data, release lock
    }; // Guard dropped here

    // Xử lý data_copy mà không giữ lock
    let new_data = process(data_copy);

    // Lock lại chỉ để write
    *shared.lock().unwrap() = new_data;
}

// ✅ GOOD: Cấu trúc lại để tránh re-entrant
struct Service {
    inner: Mutex<Inner>,
}

impl Service {
    pub fn do_work(&self) {
        let mut inner = self.inner.lock().unwrap();
        inner.step_one();
        inner.step_two(); // Không cần lock lại vì inner là &mut Inner
    }
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Xác lập thứ tự lock toàn cục và document nó
- [ ] Không gọi hàm "black box" khi đang giữ lock
- [ ] Không giữ lock qua `.await` (CA-15)
- [ ] Dùng `parking_lot::Mutex` có timeout để detect deadlock
- [ ] Dùng `tracing` để log lock acquisition
- [ ] Xem xét thay Mutex bằng message passing (channel)

**Clippy / Công cụ:**
```bash
# parking_lot có deadlock detection feature
cargo add parking_lot --features deadlock_detection

# Kích hoạt trong main
#[cfg(feature = "deadlock_detection")]
{
    std::thread::spawn(move || loop {
        std::thread::sleep(Duration::from_secs(10));
        let deadlocks = parking_lot::deadlock::check_deadlock();
        if !deadlocks.is_empty() {
            eprintln!("{} deadlocks detected", deadlocks.len());
        }
    });
}
```

---

## CA-05: Channel Đầy Không Xử Lý (Bounded Channel Full)

### 1. Tên

**Channel Đầy Không Xử Lý** (Bounded Channel Backpressure Ignored)

### 2. Phân loại

- **Lĩnh vực:** Concurrency & Async
- **Danh mục con:** Backpressure / Resource Exhaustion
- **Mã định danh:** CA-05

### 3. Mức nghiêm trọng

🟠 **HIGH** — Khi bounded channel đầy và sender không xử lý đúng, hoặc dùng `try_send` bỏ qua lỗi, dẫn đến mất dữ liệu hoặc sender bị block vô thời hạn.

### 4. Vấn đề

Bounded channel có kích thước giới hạn để tạo backpressure. Khi channel đầy: `send().await` sẽ chờ, `try_send()` trả về lỗi. Bỏ qua cả hai đều gây vấn đề.

```
  Producer (fast)          Bounded Channel [capacity=10]
  ───────────────          ─────────────────────────────
  send msg 1  →            [1][2][3][4][5][6][7][8][9][10]  ← FULL
  send msg 2  →            try_send() → Err(Full) → bị bỏ qua!
  send msg 3  →            Dữ liệu MẤT không có log

  Hoặc:
  send().await →            Producer bị BLOCK vô thời hạn
                            nếu consumer không xử lý kịp
```

**Nguyên nhân phổ biến:**
- `try_send(msg).ok()` — bỏ qua lỗi Full silently
- Channel capacity quá nhỏ
- Consumer chậm hơn producer
- Dead consumer (channel đầy mãi)

### 5. Phát hiện trong mã nguồn

**Dấu hiệu:**
- `try_send(...).ok()` hoặc `try_send(...).unwrap_or(())`
- Metric cho thấy message count giảm không giải thích được
- Producer log nhiều hơn consumer log

**Ripgrep:**
```bash
# Tìm try_send bị bỏ qua
rg -n "try_send.*\.ok\(\)|try_send.*unwrap_or" --type rust

# Tìm channel creation để review capacity
rg -n "channel\([0-9]+\)|bounded\([0-9]+\)" --type rust
```

### 6. Giải pháp

| Tình huống | Giải pháp |
|-----------|-----------|
| Mất dữ liệu không chấp nhận được | Dùng `send().await` với backpressure |
| Có thể drop message | Log + metric khi drop |
| Consumer chậm | Tăng capacity hoặc thêm consumer |
| Dead consumer | Kiểm tra receiver còn sống |

```rust
// ❌ BAD: Bỏ qua lỗi full
async fn bad_producer(tx: mpsc::Sender<Message>, msg: Message) {
    tx.try_send(msg).ok(); // Silently drops message when full!
}

// ✅ GOOD: Xử lý backpressure đúng cách
async fn good_producer(tx: mpsc::Sender<Message>, msg: Message) -> Result<(), ProducerError> {
    tx.send(msg).await.map_err(|_| ProducerError::ReceiverClosed)?;
    Ok(())
}

// ✅ GOOD: try_send với explicit handling
async fn good_producer_nonblocking(
    tx: mpsc::Sender<Message>,
    msg: Message,
) -> Result<(), ProducerError> {
    match tx.try_send(msg) {
        Ok(()) => Ok(()),
        Err(mpsc::error::TrySendError::Full(msg)) => {
            tracing::warn!("Channel full, dropping message: {:?}", msg);
            metrics::increment_counter!("channel_drops_total");
            Err(ProducerError::ChannelFull)
        }
        Err(mpsc::error::TrySendError::Closed(_)) => {
            Err(ProducerError::ReceiverClosed)
        }
    }
}

// ✅ GOOD: Timeout-based send
async fn send_with_timeout(
    tx: mpsc::Sender<Message>,
    msg: Message,
    timeout: Duration,
) -> Result<(), ProducerError> {
    tokio::time::timeout(timeout, tx.send(msg))
        .await
        .map_err(|_| ProducerError::Timeout)?
        .map_err(|_| ProducerError::ReceiverClosed)
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Không bao giờ dùng `try_send(...).ok()` mà không log
- [ ] Monitor channel capacity với metrics
- [ ] Test với producer nhanh hơn consumer
- [ ] Xác định rõ semantic: "drop or wait" cho từng channel
- [ ] Đặt capacity dựa trên benchmark, không đoán mò

**Clippy / Công cụ:**
```bash
# Tìm try_send bị bỏ qua
rg "try_send.*\.ok\(\)" --type rust

# Không có clippy lint sẵn, cần review thủ công
cargo clippy
```

---

## CA-06: Bầy Đàn Ồ Ạt (Thundering Herd)

### 1. Tên

**Bầy Đàn Ồ Ạt** (Thundering Herd Problem)

### 2. Phân loại

- **Lĩnh vực:** Concurrency & Async
- **Danh mục con:** Performance / Resource Contention
- **Mã định danh:** CA-06

### 3. Mức nghiêm trọng

🟠 **HIGH** — Khi tài nguyên sẵn sàng, hàng trăm task đồng loạt thức dậy và tranh giành, gây spike CPU/DB và phần lớn task thất bại hoặc phải thử lại.

### 4. Vấn đề

Thundering herd xảy ra khi nhiều task cùng đợi một sự kiện (cache miss, lock release, connection available). Khi sự kiện xảy ra, tất cả thức dậy nhưng chỉ một task thực sự "thắng".

```
  Cache MISS → 1000 tasks cùng wake up
  ┌─────────────────────────────────────────┐
  │  Task 1: try DB query → OK              │
  │  Task 2: try DB query → OK              │
  │  Task 3: try DB query → OK              │
  │  ...                                    │
  │  Task 1000: try DB query → timeout      │
  └─────────────────────────────────────────┘
  DB overwhelmed, 999 requests duplicated,
  cache chứa 1000 bản copy cùng một data
```

**Nguyên nhân phổ biến:**
- Broadcast channel thức dậy tất cả waiter
- Cache expiry đồng thời (cache stampede)
- Nhiều task chờ cùng một Mutex
- Retry storm sau service recovery

### 5. Phát hiện trong mã nguồn

**Dấu hiệu:**
- Spike CPU/DB ngay khi service recover
- Log thấy hàng trăm request cùng timestamp cho cùng resource
- Nhiều task với kết quả giống hệt nhau

**Ripgrep:**
```bash
# Tìm broadcast channel (wake all)
rg -n "broadcast::channel\|Notify::notify_all" --type rust

# Tìm pattern "many waiters, one result"
rg -n "Condvar::notify_all\|wake_all" --type rust
```

### 6. Giải pháp

| Tình huống | Giải pháp |
|-----------|-----------|
| Cache stampede | Single-flight / request coalescing |
| Lock contention | Giảm số waiter, work stealing |
| Retry storm | Exponential backoff + jitter |
| Broadcast wakeup | Dùng `notify_one` nếu chỉ cần một |

```rust
// ❌ BAD: Cache miss gây thundering herd
async fn get_user(id: u64, cache: Arc<Cache>, db: Arc<Db>) -> User {
    if let Some(user) = cache.get(id) {
        return user;
    }
    // Mọi task đều chạy vào đây cùng lúc khi cache miss
    let user = db.query_user(id).await.unwrap();
    cache.set(id, user.clone());
    user
}

// ✅ GOOD: Single-flight pattern (request coalescing)
use std::collections::HashMap;
use tokio::sync::Mutex;

struct SingleFlight {
    in_flight: Mutex<HashMap<u64, Arc<tokio::sync::watch::Receiver<Option<User>>>>>,
}

impl SingleFlight {
    async fn get_user(&self, id: u64, db: &Db, cache: &Cache) -> User {
        if let Some(user) = cache.get(id) {
            return user;
        }

        let mut in_flight = self.in_flight.lock().await;

        // Nếu đã có request đang bay → chờ kết quả của nó
        if let Some(rx) = in_flight.get(&id) {
            let mut rx = rx.as_ref().clone();
            drop(in_flight); // Release lock trước khi await
            rx.changed().await.unwrap();
            return rx.borrow().clone().unwrap();
        }

        // Đây là request đầu tiên → tạo channel, broadcast cho waiters
        let (tx, rx) = tokio::sync::watch::channel(None);
        in_flight.insert(id, Arc::new(rx));
        drop(in_flight);

        let user = db.query_user(id).await.unwrap();
        cache.set(id, user.clone());
        tx.send(Some(user.clone())).unwrap();

        let mut in_flight = self.in_flight.lock().await;
        in_flight.remove(&id);

        user
    }
}

// ✅ GOOD: Jitter cho retry storm
async fn retry_with_jitter<F, T, E>(f: F) -> Result<T, E>
where
    F: Fn() -> std::pin::Pin<Box<dyn std::future::Future<Output = Result<T, E>>>>,
{
    let mut delay = Duration::from_millis(100);
    for attempt in 0..5 {
        match f().await {
            Ok(v) => return Ok(v),
            Err(e) if attempt == 4 => return Err(e),
            Err(_) => {
                let jitter = rand::random::<u64>() % 100;
                tokio::time::sleep(delay + Duration::from_millis(jitter)).await;
                delay = (delay * 2).min(Duration::from_secs(30));
            }
        }
    }
    unreachable!()
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Cache key có expiry ngẫu nhiên (staggered TTL) để tránh đồng loạt hết hạn
- [ ] Dùng single-flight cho expensive operations
- [ ] Retry luôn có jitter
- [ ] Monitor số lượng concurrent request cho cùng resource
- [ ] Dùng `notify_one` thay `notify_all` khi chỉ cần một waiter tiếp tục

**Clippy / Công cụ:**
```bash
# Không có lint sẵn, cần architectural review
# Dùng tokio-console để thấy task wakeup patterns
```

---

## CA-07: Select Bias (Tokio Select Bias)

### 1. Tên

**Select Bias** (Biased Branch Selection in tokio::select!)

### 2. Phân loại

- **Lĩnh vực:** Concurrency & Async
- **Danh mục con:** Fairness / Starvation
- **Mã định danh:** CA-07

### 3. Mức nghiêm trọng

🟡 **MEDIUM** — `tokio::select!` kiểm tra branch theo thứ tự nếu nhiều branch sẵn sàng cùng lúc, dẫn đến một số branch bị starve.

### 4. Vấn đề

`tokio::select!` khi nhiều branch ready cùng lúc sẽ chọn branch **đầu tiên** trong code (không ngẫu nhiên). Nếu một branch luôn ready, branch sau nó không bao giờ được xử lý.

```
  loop {
      tokio::select! {
          msg = high_freq_channel.recv() => { ... }  ← luôn ready
          msg = low_freq_channel.recv() => { ... }   ← NEVER selected
          _ = shutdown.recv() => { break; }           ← NEVER selected
      }
  }

  Kết quả: shutdown signal bị bỏ qua
           low_freq_channel bị starve
```

**Nguyên nhân phổ biến:**
- Một channel có throughput cao hơn các channel khác
- Shutdown signal không được ưu tiên
- Timer branch bị bỏ qua vì data channel luôn ready

### 5. Phát hiện trong mã nguồn

**Dấu hiệu:**
- Một số branch trong `select!` không bao giờ được log
- Shutdown timeout vì shutdown branch không được chọn
- Metric thấy một channel xử lý 99% message

**Ripgrep:**
```bash
# Tìm tất cả select! để review
rg -n "tokio::select!" --type rust

# Tìm select! với nhiều branch
rg -n "tokio::select!" --type rust -A 10
```

### 6. Giải pháp

| Tình huống | Giải pháp |
|-----------|-----------|
| Cần fairness | `biased` keyword bị disable, dùng loop riêng |
| Ưu tiên shutdown | Đặt shutdown branch đầu tiên |
| Fairness thực sự | Dùng `tokio::select! { biased; ... }` (Tokio 1.x) |
| Multiple queues fair | `futures::select_biased!` hoặc round-robin |

```rust
// ❌ BAD: Shutdown có thể bị starve
async fn bad_event_loop(
    mut data_rx: mpsc::Receiver<Data>,
    mut shutdown: oneshot::Receiver<()>,
) {
    loop {
        tokio::select! {
            Some(data) = data_rx.recv() => {
                process(data).await;
            }
            _ = &mut shutdown => {   // Có thể không bao giờ được chọn
                break;               // nếu data_rx luôn có data
            }
        }
    }
}

// ✅ GOOD: Ưu tiên shutdown bằng cách kiểm tra trước
async fn good_event_loop(
    mut data_rx: mpsc::Receiver<Data>,
    mut shutdown: oneshot::Receiver<()>,
) {
    loop {
        tokio::select! {
            biased; // Tokio sẽ kiểm tra theo thứ tự code

            _ = &mut shutdown => {
                tracing::info!("Shutting down event loop");
                break;
            }
            Some(data) = data_rx.recv() => {
                process(data).await;
            }
        }
    }
}

// ✅ GOOD: Round-robin fairness cho nhiều channel
async fn fair_event_loop(
    mut rx1: mpsc::Receiver<Msg1>,
    mut rx2: mpsc::Receiver<Msg2>,
) {
    let mut turn = 0u8;
    loop {
        if turn % 2 == 0 {
            tokio::select! {
                biased;
                Some(msg) = rx1.recv() => handle_msg1(msg).await,
                Some(msg) = rx2.recv() => handle_msg2(msg).await,
            }
        } else {
            tokio::select! {
                biased;
                Some(msg) = rx2.recv() => handle_msg2(msg).await,
                Some(msg) = rx1.recv() => handle_msg1(msg).await,
            }
        }
        turn = turn.wrapping_add(1);
    }
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Luôn đặt shutdown signal là branch đầu tiên
- [ ] Dùng `biased;` khi muốn kiểm soát thứ tự ưu tiên rõ ràng
- [ ] Monitor branch execution count với metrics
- [ ] Test behavior khi một channel bão hòa
- [ ] Document ý định ưu tiên trong comment

**Clippy / Công cụ:**
```bash
# Không có lint tự động, review code thủ công
rg "tokio::select!" --type rust -A 15 | grep -B 3 "shutdown\|cancel\|stop"
```

---

## CA-08: Spawn Không Join (Detached Task)

### 1. Tên

**Spawn Không Join** (Detached Task / Fire-and-Forget)

### 2. Phân loại

- **Lĩnh vực:** Concurrency & Async
- **Danh mục con:** Resource Leak / Error Handling
- **Mã định danh:** CA-08

### 3. Mức nghiêm trọng

🟠 **HIGH** — Task được spawn nhưng JoinHandle bị drop → task vẫn chạy nhưng panic và lỗi bị bỏ qua hoàn toàn, resource leak không được detect.

### 4. Vấn đề

`tokio::spawn` trả về `JoinHandle<T>`. Nếu drop handle mà không await, task vẫn chạy ("detached") nhưng:
1. Panic trong task không propagate → bị nuốt im lặng
2. Không có cách biết task kết thúc hay chưa
3. Graceful shutdown khó vì không tracking task

```
  tokio::spawn(async { critical_work().await })
       │
       ▼ JoinHandle dropped immediately
  ┌─────────────────────────────────────────────┐
  │  Task chạy detached                         │
  │  │                                          │
  │  └── panic!("DB connection failed")         │
  │       │                                     │
  │       ▼                                     │
  │  [ERROR] task panicked silently             │
  │  Caller: không biết gì cả                   │
  └─────────────────────────────────────────────┘
```

**Nguyên nhân phổ biến:**
- `tokio::spawn(...)` không lưu handle
- `let _ = tokio::spawn(...)` — explicit drop
- Spawn trong loop không track handles

### 5. Phát hiện trong mã nguồn

**Dấu hiệu:**
- Task errors không xuất hiện trong log
- `tokio::spawn(...)` không assign vào biến
- Shutdown nhưng tasks chưa hoàn thành

**Ripgrep:**
```bash
# Tìm spawn không assign
rg -n "tokio::spawn\(" --type rust

# Tìm spawn với let _ (explicit drop)
rg -n "let _ = tokio::spawn" --type rust

# Tìm spawn trong loop
rg -n "tokio::spawn" --type rust -B 2 | grep -E "for|while|loop"
```

### 6. Giải pháp

| Tình huống | Giải pháp |
|-----------|-----------|
| Task quan trọng | Lưu JoinHandle, await khi shutdown |
| Nhiều task | `JoinSet` để track tập hợp |
| Fire-and-forget OK | Log errors explicitly trong task |
| Background task | `tokio::spawn` + store handle trong struct |

```rust
// ❌ BAD: Drop handle, panic bị bỏ qua
fn start_worker(data: Data) {
    tokio::spawn(async move {
        process(data).await.unwrap(); // panic bị bỏ qua!
    }); // JoinHandle dropped
}

// ✅ GOOD: Lưu handle và await khi shutdown
struct Worker {
    handle: tokio::task::JoinHandle<()>,
}

impl Worker {
    fn start(data: Data) -> Self {
        let handle = tokio::spawn(async move {
            if let Err(e) = process(data).await {
                tracing::error!("Worker error: {}", e);
            }
        });
        Self { handle }
    }

    async fn shutdown(self) {
        self.handle.await.expect("Worker task panicked");
    }
}

// ✅ GOOD: JoinSet cho nhiều task
async fn run_workers(items: Vec<Data>) {
    let mut set = tokio::task::JoinSet::new();

    for item in items {
        set.spawn(async move {
            process(item).await
        });
    }

    // Chờ tất cả hoàn thành, xử lý lỗi
    while let Some(result) = set.join_next().await {
        match result {
            Ok(Ok(())) => {}
            Ok(Err(e)) => tracing::error!("Task failed: {}", e),
            Err(e) => tracing::error!("Task panicked: {}", e),
        }
    }
}

// ✅ GOOD: Fire-and-forget nhưng có error handling
fn fire_and_forget(data: Data) {
    tokio::spawn(async move {
        match process(data).await {
            Ok(()) => {}
            Err(e) => {
                tracing::error!("Background task failed: {}", e);
                metrics::increment_counter!("background_task_errors");
            }
        }
    });
    // Không cần JoinHandle vì error đã được handle trong task
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Mọi `tokio::spawn` phải có lý do rõ ràng nếu không lưu handle
- [ ] Task quan trọng → lưu trong `JoinSet` hoặc struct field
- [ ] Mọi task phải có error handling internal
- [ ] Graceful shutdown phải chờ tất cả JoinHandle
- [ ] Không dùng `let _ = tokio::spawn(...)` trừ khi có comment giải thích

**Clippy / Công cụ:**
```bash
cargo clippy -- -W clippy::detached_futures

# Tìm spawn không assign
rg "tokio::spawn\(" --type rust | grep -v "let "
```

---

## CA-09: Async Trait Overhead (Async Trait Dynamic Dispatch)

### 1. Tên

**Async Trait Overhead** (Excessive Dynamic Dispatch in Async Traits)

### 2. Phân loại

- **Lĩnh vực:** Concurrency & Async
- **Danh mục con:** Performance / Allocation
- **Mã định danh:** CA-09

### 3. Mức nghiêm trọng

🟡 **MEDIUM** — Mỗi async trait method call với `async_trait` crate tạo một heap allocation (`Box<dyn Future>`). Trong hot path, hàng triệu allocation/giây.

### 4. Vấn đề

Rust chưa hỗ trợ native `async fn` trong traits (stable trước 1.75). Crate `async_trait` giải quyết bằng cách wrap Future trong `Box<dyn Future>`. Điều này tiện lợi nhưng tốn kém trong hot path.

```
  #[async_trait]
  trait Handler {
      async fn handle(&self, req: Request) -> Response;
  }
  ↓ Expand thành:
  fn handle(&self, req: Request) -> Box<dyn Future<Output=Response> + Send + '_>

  Mỗi call = heap allocation + pointer indirection
  10,000 req/s = 10,000 allocations/s chỉ cho dispatch
```

**Nguyên nhân phổ biến:**
- Dùng `async_trait` cho hot path handlers
- Trait object `Box<dyn Handler>` thay vì generics
- Middleware chain với nhiều layer async trait

### 5. Phát hiện trong mã nguồn

**Dấu hiệu:**
- `#[async_trait]` trên trait trong hot path
- Profiler thấy nhiều allocation từ `Box::new` trong async context
- `dyn Handler` thay vì `impl Handler<T>`

**Ripgrep:**
```bash
# Tìm async_trait usage
rg -n "#\[async_trait\]" --type rust

# Tìm Box<dyn Future>
rg -n "Box<dyn Future" --type rust

# Tìm dyn trong hot path
rg -n "dyn.*Handler\|dyn.*Service\|dyn.*Processor" --type rust
```

### 6. Giải pháp

| Tình huống | Giải pháp |
|-----------|-----------|
| Rust >= 1.75 | Native `async fn in trait` |
| Hot path | Generics thay trait objects |
| Cần trait objects | `async_trait` OK cho cold path |
| Complex return types | `impl Trait` hoặc `type Future = ...` |

```rust
// ❌ BAD: async_trait trong hot path
#[async_trait]
trait RequestHandler: Send + Sync {
    async fn handle(&self, req: Request) -> Response; // Box allocation mỗi call
}

// ✅ GOOD: Native async fn in trait (Rust 1.75+)
trait RequestHandler: Send + Sync {
    fn handle(&self, req: Request) -> impl Future<Output = Response> + Send + '_;
}

// ✅ GOOD: Generics thay trait objects
async fn dispatch<H: RequestHandler>(handler: &H, req: Request) -> Response {
    handler.handle(req).await // Monomorphized, no allocation
}

// ✅ GOOD: Khi PHẢI dùng trait objects (plugin system, etc.)
// Chấp nhận overhead nhưng chỉ cho non-hot-path
#[async_trait]
trait Plugin: Send + Sync {
    async fn on_event(&self, event: Event) -> Result<(), PluginError>;
}

// Cho hot path: enum dispatch thay trait objects
enum HandlerKind {
    Json(JsonHandler),
    Binary(BinaryHandler),
    Stream(StreamHandler),
}

impl HandlerKind {
    async fn handle(&self, req: Request) -> Response {
        match self {
            HandlerKind::Json(h) => h.handle(req).await,
            HandlerKind::Binary(h) => h.handle(req).await,
            HandlerKind::Stream(h) => h.handle(req).await,
        }
    }
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Upgrade lên Rust 1.75+ để dùng native async fn in traits
- [ ] Hot path: generics (`impl Trait`) thay `Box<dyn Trait>`
- [ ] Profile trước khi optimize — đừng over-engineer
- [ ] `async_trait` OK cho cold path (startup, config, plugins)
- [ ] Dùng enum dispatch khi số lượng implementations hữu hạn

**Clippy / Công cụ:**
```bash
# Không có lint sẵn
# Profile với criterion + flamegraph
cargo add criterion --dev
cargo add flamegraph --dev
```

---

## CA-10: Rayon Trong Tokio (Rayon in Tokio Context)

### 1. Tên

**Rayon Trong Tokio** (Blocking Rayon Thread Pool in Tokio Runtime)

### 2. Phân loại

- **Lĩnh vực:** Concurrency & Async
- **Danh mục con:** Thread Pool Conflict / Starvation
- **Mã định danh:** CA-10

### 3. Mức nghiêm trọng

🔴 **CRITICAL** — Gọi Rayon `par_iter()` trực tiếp trong Tokio async task làm Tokio worker threads bị block bởi Rayon work-stealing, gây deadlock hoặc starvation nghiêm trọng.

### 4. Vấn đề

Rayon và Tokio đều có thread pool riêng. Rayon dùng work-stealing và có thể block thread hiện tại để chờ Rayon tasks trên thread khác. Khi Rayon chạy trên Tokio thread, nó block Tokio worker → starvation.

```
  Tokio Worker Threads (4)
  ┌──────┬──────┬──────┬──────┐
  │  T1  │  T2  │  T3  │  T4  │
  └──┬───┴──┬───┴──┬───┴──┬───┘
     │      │      │      │
     │  Rayon par_iter() gọi từ T1
     ▼      ▼      ▼      ▼
  [Rayon chiếm T1, T2, T3, T4]
  [Tokio không còn thread để chạy]
  [DEADLOCK nếu Rayon task cần Tokio]
```

**Nguyên nhân phổ biến:**
- `data.par_iter().map(...)` trong `async fn`
- Thư viện xử lý dữ liệu dùng Rayon được gọi từ async
- `rayon::join` trong Tokio context

### 5. Phát hiện trong mã nguồn

**Dấu hiệu:**
- `par_iter` hoặc `rayon::` trong `async fn`
- Runtime cảnh báo "task is taking too long"
- Tất cả Tokio tasks bị delay khi xử lý batch lớn

**Ripgrep:**
```bash
# Tìm rayon trong async context
rg -n "par_iter\|par_chunks\|rayon::" --type rust

# Kết hợp với async fn
rg -n "par_iter" --type rust -B 10 | grep "async fn"
```

### 6. Giải pháp

| Tình huống | Giải pháp |
|-----------|-----------|
| CPU-intensive parallel | `spawn_blocking` + Rayon bên trong |
| Rayon tách biệt | Dedicated Rayon thread pool, communicate qua channel |
| Không quá nặng | `tokio::task::spawn_blocking` với iter thường |
| Lớn và thường xuyên | Kiến trúc Actor pattern |

```rust
// ❌ BAD: Rayon trực tiếp trong async
async fn process_batch(data: Vec<u64>) -> Vec<u64> {
    data.par_iter()  // BLOCKS Tokio worker threads
        .map(|x| expensive_compute(*x))
        .collect()
}

// ✅ GOOD: spawn_blocking để tách ra khỏi Tokio pool
async fn process_batch_safe(data: Vec<u64>) -> Vec<u64> {
    tokio::task::spawn_blocking(move || {
        // Bây giờ chạy trên blocking thread pool, không ảnh hưởng Tokio
        data.par_iter()
            .map(|x| expensive_compute(*x))
            .collect()
    })
    .await
    .expect("Blocking task panicked")
}

// ✅ GOOD: Dedicated Rayon pool với channel
struct ComputeWorker {
    tx: std::sync::mpsc::SyncSender<ComputeJob>,
}

impl ComputeWorker {
    fn new() -> Self {
        let (tx, rx) = std::sync::mpsc::sync_channel(100);

        // Rayon pool chạy trên dedicated thread, không phải Tokio thread
        std::thread::spawn(move || {
            rayon::ThreadPoolBuilder::new()
                .num_threads(4)
                .build_global()
                .unwrap();

            for job in rx {
                let result = job.data.par_iter()
                    .map(|x| expensive_compute(*x))
                    .collect::<Vec<_>>();
                job.reply.send(result).ok();
            }
        });

        Self { tx }
    }

    async fn compute(&self, data: Vec<u64>) -> Vec<u64> {
        let (reply_tx, reply_rx) = tokio::sync::oneshot::channel();
        self.tx.send(ComputeJob { data, reply: reply_tx }).unwrap();
        reply_rx.await.unwrap()
    }
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Không có `par_iter` trực tiếp trong `async fn`
- [ ] CPU-intensive + parallel → `spawn_blocking` + Rayon bên trong
- [ ] Kiểm tra dependency có dùng Rayon không khi được gọi từ async
- [ ] Benchmark để xác định có cần Rayon không (overhead spawn_blocking)
- [ ] Cân nhắc `tokio::task::spawn_blocking` thuần túy cho đơn giản hơn

**Clippy / Công cụ:**
```bash
# Tìm rayon trong async
rg "par_iter\|par_chunks\|rayon::" --type rust

# Tokio console để xem thread utilization
cargo add console-subscriber
```

---

## CA-11: RwLock Starvation (Reader-Writer Lock Starvation)

### 1. Tên

**RwLock Starvation** (Writer Starvation in RwLock)

### 2. Phân loại

- **Lĩnh vực:** Concurrency & Async
- **Danh mục con:** Starvation / Fairness
- **Mã định danh:** CA-11

### 3. Mức nghiêm trọng

🟠 **HIGH** — Trong `std::sync::RwLock`, liên tục có reader mới có thể làm writer chờ mãi mãi (writer starvation), dữ liệu không bao giờ được update.

### 4. Vấn đề

`std::sync::RwLock` trên Linux (pthreads) cho phép reader mới vào ngay cả khi writer đang chờ, nếu còn reader khác đang giữ lock. Kết quả: writer bị starve nếu read traffic liên tục.

```
  Reader stream: R1 R2 R3 R4 R5 R6 ... (liên tục)

  Time:  0    1    2    3    4    5    6
         R1── R2── R3── R4── R5── R6──
              ↑ W chờ đây
              W muốn write nhưng luôn có reader
              W: starved indefinitely

  Chú ý: tokio::sync::RwLock fairness tốt hơn
          nhưng vẫn có vấn đề nếu không cẩn thận
```

**Nguyên nhân phổ biến:**
- `RwLock` cho config/cache read-heavy
- Writer cần update định kỳ nhưng reader không dứt
- Không giới hạn concurrent readers

### 5. Phát hiện trong mã nguồn

**Dấu hiệu:**
- Config thay đổi nhưng service vẫn dùng giá trị cũ
- Writer task treo lâu hơn bình thường
- Metric cho thấy write latency tăng khi read traffic cao

**Ripgrep:**
```bash
# Tìm RwLock usage
rg -n "RwLock::new\|RwLock<" --type rust

# Tìm write() trong RwLock
rg -n "\.write\(\)" --type rust
```

### 6. Giải pháp

| Tình huống | Giải pháp |
|-----------|-----------|
| Config read-heavy | `arc-swap` crate (atomic swap) |
| Writer starvation | `parking_lot::RwLock` (fair) |
| Async context | `tokio::sync::RwLock` |
| Snapshot pattern | Swap Arc<T> atomically |

```rust
// ❌ BAD: std::sync::RwLock với high read contention
use std::sync::{Arc, RwLock};

struct ConfigStore {
    inner: Arc<RwLock<Config>>,
}

impl ConfigStore {
    fn get(&self) -> Config {
        self.inner.read().unwrap().clone()
    }

    fn update(&self, new: Config) {
        // Có thể bị starve nếu get() liên tục
        *self.inner.write().unwrap() = new;
    }
}

// ✅ GOOD: arc-swap cho read-heavy config
use arc_swap::ArcSwap;

struct ConfigStore {
    inner: ArcSwap<Config>,
}

impl ConfigStore {
    fn get(&self) -> Arc<Config> {
        self.inner.load_full() // Lock-free read
    }

    fn update(&self, new: Config) {
        self.inner.store(Arc::new(new)); // Atomic swap, không starvation
    }
}

// ✅ GOOD: parking_lot::RwLock (writer-fair)
use parking_lot::RwLock;

struct DataStore {
    inner: RwLock<Data>,
}

impl DataStore {
    fn read(&self) -> parking_lot::RwLockReadGuard<Data> {
        self.inner.read() // Fair: writer không bị starve
    }

    fn write(&self) -> parking_lot::RwLockWriteGuard<Data> {
        self.inner.write()
    }
}

// ✅ GOOD: Tokio RwLock trong async
use tokio::sync::RwLock;

struct AsyncStore {
    inner: RwLock<Data>,
}

impl AsyncStore {
    async fn read(&self) -> tokio::sync::RwLockReadGuard<'_, Data> {
        self.inner.read().await
    }

    async fn write(&self) -> tokio::sync::RwLockWriteGuard<'_, Data> {
        self.inner.write().await // Tokio guarantees writer won't starve
    }
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Read-heavy config/cache → dùng `arc-swap`
- [ ] Cần fairness → `parking_lot::RwLock`
- [ ] Async context → `tokio::sync::RwLock`
- [ ] Tránh `std::sync::RwLock` khi write starvation là concern
- [ ] Monitor write latency percentile (P99 cao = possible starvation)

**Clippy / Công cụ:**
```bash
# Tìm std::sync::RwLock (có thể đổi sang parking_lot)
rg "std::sync::RwLock\|sync::RwLock" --type rust

cargo add arc-swap      # Cho config
cargo add parking_lot   # Cho fair mutex/rwlock
```

---

## CA-12: Atomic Ordering Sai (Wrong Atomic Ordering)

### 1. Tên

**Atomic Ordering Sai** (Incorrect Memory Ordering for Atomics)

### 2. Phân loại

- **Lĩnh vực:** Concurrency & Async
- **Danh mục con:** Memory Model / Undefined Behavior
- **Mã định danh:** CA-12

### 3. Mức nghiêm trọng

🔴 **CRITICAL** — Dùng sai `Ordering` với atomic operations dẫn đến data race, cache coherency violation, và undefined behavior trên multi-core CPU.

### 4. Vấn đề

Rust atomic operations nhận `Ordering` parameter để kiểm soát memory ordering. Dùng `Relaxed` khi cần `Acquire/Release` cho phép CPU/compiler reorder operations, gây race condition không nhìn thấy trong test nhưng xuất hiện trên production với nhiều core.

```
  Thread A                    Thread B
  ─────────────────────────   ─────────────────────────
  data = 42;                  while !ready.load(Relaxed) {}
  ready.store(true, Relaxed); println!("{}", data); // có thể thấy 0!

  CPU có thể reorder vì Relaxed:
  ready.store(true)  ← CPU thực thi trước
  data = 42          ← sau (reordered)

  ✅ Đúng: store(true, Release) / load(Acquire)
```

**Ordering semantics:**
- `Relaxed`: Không đảm bảo ordering gì — chỉ cho counter thuần
- `Acquire`: Tạo "acquire fence" — đọc thấy mọi thứ trước Release
- `Release`: Tạo "release fence" — mọi write trước nó visible sau Acquire
- `AcqRel`: Kết hợp Acquire + Release (cho read-modify-write)
- `SeqCst`: Tổng thứ tự toàn cục — đắt nhất nhưng an toàn nhất

### 5. Phát hiện trong mã nguồn

**Dấu hiệu:**
- `Ordering::Relaxed` trên flag/ready signal
- `AtomicBool` để synchronize data access
- Heisenbugs chỉ xuất hiện trên multi-core

**Ripgrep:**
```bash
# Tìm Relaxed ordering
rg -n "Ordering::Relaxed\|Relaxed\)" --type rust

# Tìm AtomicBool dùng làm synchronization flag
rg -n "AtomicBool\|AtomicUsize\|AtomicPtr" --type rust
```

### 6. Giải pháp

| Use case | Ordering |
|---------|---------|
| Counter không sync data | `Relaxed` |
| Flag để signal (writer) | `Release` |
| Flag để check (reader) | `Acquire` |
| Compare-and-swap | `AcqRel` (success) / `Relaxed` (failure) |
| Cần total order | `SeqCst` |

```rust
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
use std::sync::Arc;

// ❌ BAD: Relaxed cho synchronization flag
fn bad_producer(data: Arc<AtomicU64>, ready: Arc<AtomicBool>) {
    data.store(42, Ordering::Relaxed);
    ready.store(true, Ordering::Relaxed); // CPU có thể reorder!
}

fn bad_consumer(data: Arc<AtomicU64>, ready: Arc<AtomicBool>) {
    while !ready.load(Ordering::Relaxed) {} // Không đảm bảo thấy data=42
    println!("{}", data.load(Ordering::Relaxed)); // Race condition!
}

// ✅ GOOD: Acquire/Release pair
fn good_producer(data: Arc<AtomicU64>, ready: Arc<AtomicBool>) {
    data.store(42, Ordering::Relaxed); // OK: synchronized bởi Release
    ready.store(true, Ordering::Release); // Release fence: mọi write trước đây visible
}

fn good_consumer(data: Arc<AtomicU64>, ready: Arc<AtomicBool>) {
    while !ready.load(Ordering::Acquire) {} // Acquire: đảm bảo thấy data=42
    println!("{}", data.load(Ordering::Relaxed)); // Safe: synchronized
}

// ✅ GOOD: Counter thuần (Relaxed OK)
struct RequestCounter {
    count: AtomicU64,
}

impl RequestCounter {
    fn increment(&self) {
        self.count.fetch_add(1, Ordering::Relaxed); // OK: không sync data khác
    }

    fn get(&self) -> u64 {
        self.count.load(Ordering::Relaxed) // OK: approximate count
    }
}

// ✅ GOOD: Compare-and-swap đúng
fn try_claim(flag: &AtomicBool) -> bool {
    flag.compare_exchange(
        false,              // expected
        true,               // new
        Ordering::AcqRel,  // success ordering
        Ordering::Relaxed, // failure ordering
    ).is_ok()
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] `Relaxed` chỉ cho counter không dùng để sync data khác
- [ ] Flag signal: writer dùng `Release`, reader dùng `Acquire`
- [ ] Khi không chắc → dùng `SeqCst` (đắt hơn nhưng đúng)
- [ ] Review mọi `Ordering::Relaxed` với đôi mắt hoài nghi
- [ ] Dùng Miri để detect data races

**Clippy / Công cụ:**
```bash
# Miri để detect data races
cargo +nightly miri test

# Loom để test concurrent code
cargo add loom --dev

# Không có clippy lint tự động cho ordering
```

---

## CA-13: Future Không Poll (Unawaited Future)

### 1. Tên

**Future Không Poll** (Unawaited / Unpolled Future)

### 2. Phân loại

- **Lĩnh vực:** Concurrency & Async
- **Danh mục con:** Correctness / Logic Error
- **Mã định danh:** CA-13

### 3. Mức nghiêm trọng

🟡 MEDIUM — Future được tạo nhưng không `.await` → không được poll → không thực thi. Trong Rust, Future là lazy; không poll = không chạy.

### 4. Vấn đề

Không như Promise trong JS, Rust Future không chạy cho đến khi được poll (thông qua `.await`, `spawn`, `block_on`, etc.). Tạo Future mà quên `.await` dẫn đến code không làm gì mà không có lỗi compile.

```
  async fn save(data: Data) -> Result<(), DbError> {
      db.insert(data)  // Trả về Future<Output=Result>
                       // KHÔNG có .await → Future tạo ra rồi DROP
      Ok(())           // Hàm return Ok ngay lập tức
                       // data KHÔNG được lưu vào DB!
  }

  Compiler warning: "unused `impl Future` that must be used"
  Nhưng dễ bị bỏ qua!
```

**Nguyên nhân phổ biến:**
- Quên `.await` sau async call
- Refactor thêm `async` vào hàm nhưng không update caller
- Copy-paste code mà không thêm `.await`

### 5. Phát hiện trong mã nguồn

**Dấu hiệu:**
- Compiler warning: "unused `impl Future`"
- Operation không có effect (DB không được update, file không được write)
- Test pass nhưng side effects không xảy ra

**Ripgrep:**
```bash
# Tìm gọi async fn mà không có .await
# (Khó tự động, phải nhờ compiler warning)
cargo build 2>&1 | grep "unused.*Future"

# Tìm pattern gọi fn không có await sau
rg -n "\w+\(.*\);" --type rust | grep -v "\.await"
```

### 6. Giải pháp

| Tình huống | Giải pháp |
|-----------|-----------|
| Quên await | Thêm `.await` |
| Không cần kết quả | Explicit `let _ = fn().await` |
| Fire-and-forget | `tokio::spawn(fn())` |
| Nhiều concurrent | `futures::join!` hoặc `tokio::join!` |

```rust
// ❌ BAD: Quên .await
async fn sync_data(db: &Db, cache: &Cache) -> Result<(), Error> {
    db.save(cache.get_all()); // Future không được poll!
    Ok(())
}

// ✅ GOOD: Thêm .await
async fn sync_data(db: &Db, cache: &Cache) -> Result<(), Error> {
    db.save(cache.get_all()).await?;
    Ok(())
}

// ✅ GOOD: Khi cần run concurrently
async fn sync_all(db: &Db, items: Vec<Item>) -> Result<(), Error> {
    let futures: Vec<_> = items.iter()
        .map(|item| db.save(item))
        .collect();

    futures::future::try_join_all(futures).await?;
    Ok(())
}

// ✅ GOOD: Luôn bật warning-as-error cho Future
// Trong Cargo.toml hoặc build script:
// [profile.dev]
// rustflags = ["-W", "unused-must-use"]
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Enable `#[must_use]` warning trong CI (treat warnings as errors)
- [ ] Review mọi async fn call có `.await`
- [ ] Dùng `cargo clippy` để bắt unawaited futures
- [ ] Test side effects, không chỉ return values
- [ ] Dùng `#[must_use]` attribute trên Future-returning functions

**Clippy / Công cụ:**
```bash
cargo clippy -- -D warnings -W unused-must-use

# Trong .cargo/config.toml
# [build]
# rustflags = ["-D", "unused-must-use"]
```

---

## CA-14: Cancellation Unsafety (Unsafe Async Cancellation)

### 1. Tên

**Cancellation Unsafety** (Unsafe State on Async Task Cancellation)

### 2. Phân loại

- **Lĩnh vực:** Concurrency & Async
- **Danh mục con:** Correctness / Data Integrity
- **Mã định danh:** CA-14

### 3. Mức nghiêm trọng

🟠 **HIGH** — Khi Tokio cancel một task (drop JoinHandle, timeout, select! chọn branch khác), Future bị drop tại bất kỳ `.await` point nào — có thể để lại state không nhất quán.

### 4. Vấn đề

Async cancellation trong Rust xảy ra bằng cách drop Future. Drop có thể xảy ra tại **bất kỳ `.await` point** nào. Nếu code có invariants "phải hoàn thành step A trước step B", cancellation có thể phá vỡ chúng.

```
  async fn transfer_money(from: AccountId, to: AccountId, amount: u64) {
      db.debit(from, amount).await;   // ← Cancelled HERE!
      //                                   debit đã thực hiện
      //                                   credit KHÔNG được thực hiện
      db.credit(to, amount).await;
  }

  Kết quả: tiền bị mất — debit không có credit tương ứng!

  Cancellation xảy ra khi:
  - tokio::time::timeout() hết hạn
  - tokio::select! chọn branch khác
  - JoinHandle bị drop
  - CancellationToken được cancel
```

**Nguyên nhân phổ biến:**
- Multi-step transaction không atomic
- Cleanup code sau `.await` không được thực thi
- Resource acquisition không được release

### 5. Phát hiện trong mã nguồn

**Dấu hiệu:**
- Multiple `db.await` calls trong một hàm không có transaction
- Lock acquisition trước await mà không được released (CA-15)
- File write sau await không được close/flush

**Ripgrep:**
```bash
# Tìm multiple await trong functions có "transfer", "update", "create"
rg -n "\.await" --type rust -B 2 | grep -A 5 "transfer\|transaction\|atomic"

# Tìm timeout wrapping multi-step operations
rg -n "tokio::time::timeout" --type rust
```

### 6. Giải pháp

| Tình huống | Giải pháp |
|-----------|-----------|
| DB transaction | Wrap trong DB transaction, rollback on drop |
| File I/O | Dùng tmp file + atomic rename |
| Multi-step | `select_biased!` với cleanup branch |
| Resource cleanup | Implement `Drop` cho cleanup |

```rust
// ❌ BAD: Non-atomic multi-step với cancellation risk
async fn bad_transfer(db: &Db, from: u64, to: u64, amount: u64) {
    db.debit(from, amount).await;   // Có thể cancel ở đây
    db.credit(to, amount).await;    // Không bao giờ chạy
}

// ✅ GOOD: DB transaction với auto-rollback
async fn good_transfer(db: &Db, from: u64, to: u64, amount: u64) -> Result<(), DbError> {
    let mut tx = db.begin_transaction().await?;

    // Nếu cancelled ở đây, tx drop → auto rollback
    tx.debit(from, amount).await?;
    tx.credit(to, amount).await?;

    tx.commit().await?; // Chỉ commit khi tất cả thành công
    Ok(())
}

// ✅ GOOD: CancellationSafe wrapper
struct CancellationGuard {
    cleanup: Option<Box<dyn FnOnce() + Send>>,
}

impl CancellationGuard {
    fn new(cleanup: impl FnOnce() + Send + 'static) -> Self {
        Self { cleanup: Some(Box::new(cleanup)) }
    }

    fn disarm(mut self) {
        self.cleanup = None; // Don't run cleanup on normal exit
    }
}

impl Drop for CancellationGuard {
    fn drop(&mut self) {
        if let Some(cleanup) = self.cleanup.take() {
            cleanup(); // Run cleanup if cancelled (dropped early)
        }
    }
}

async fn safe_operation(resource: &Resource) -> Result<(), Error> {
    resource.acquire().await?;

    // Nếu bị cancel, guard sẽ release trong Drop
    let guard = CancellationGuard::new(|| resource.release_sync());

    do_work().await?;

    resource.release().await?;
    guard.disarm(); // Normal exit, no cleanup needed
    Ok(())
}

// ✅ GOOD: tokio-util CancellationToken
use tokio_util::sync::CancellationToken;

async fn cancellable_work(token: CancellationToken) -> Result<(), Error> {
    tokio::select! {
        biased;
        _ = token.cancelled() => {
            // Cleanup khi cancel
            cleanup().await;
            Err(Error::Cancelled)
        }
        result = do_actual_work() => result,
    }
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Multi-step operations trong DB → dùng transaction
- [ ] Resource acquisition → implement `Drop` cho cleanup
- [ ] Dùng `CancellationToken` từ `tokio-util` cho structured cancellation
- [ ] Test cancellation behavior explicitly
- [ ] Không assume code sau `.await` luôn được chạy

**Clippy / Công cụ:**
```bash
cargo add tokio-util --features sync

# Test cancellation
#[tokio::test]
async fn test_cancellation() {
    let token = CancellationToken::new();
    let handle = tokio::spawn(cancellable_work(token.clone()));
    token.cancel();
    let result = handle.await.unwrap();
    assert!(matches!(result, Err(Error::Cancelled)));
}
```

---

## CA-15: Mutex Guard Qua Await (MutexGuard Across Await Point)

### 1. Tên

**Mutex Guard Qua Await** (Holding MutexGuard Across Await Point)

### 2. Phân loại

- **Lĩnh vực:** Concurrency & Async
- **Danh mục con:** Deadlock / Send Violation
- **Mã định danh:** CA-15

### 3. Mức nghiêm trọng

🔴 **CRITICAL** — Giữ `std::sync::MutexGuard` qua `.await` point vi phạm `Send` (compile error) hoặc gây deadlock, vì guard giữ lock trong khi task có thể được schedule sang thread khác.

### 4. Vấn đề

`std::sync::MutexGuard` không implement `Send`. Nếu giữ guard qua `.await`, compiler sẽ báo lỗi khi task cần `Send`. Ngay cả `tokio::sync::MutexGuard` (Send) nếu giữ qua `.await` vẫn gây deadlock: task bị suspend nhưng lock vẫn bị giữ.

```
  async fn bad() {
      let guard = mutex.lock().await;  // Acquire lock
      //       guard giữ lock ở đây
      some_async_call().await;          // Task bị suspend
      //                                 lock VẪN bị giữ trong khi suspend!
      //                                 Nếu some_async_call cần lock này
      //                                 → DEADLOCK
      do_something(*guard);
  }
```

**Nguyên nhân phổ biến:**
- Lock để đọc data, sau đó await để fetch thêm
- Guard được lưu trong struct với async methods
- Vô tình giữ guard qua await trong closure

### 5. Phát hiện trong mã nguồn

**Dấu hiệu:**
- Compile error: "future is not Send" + mention of MutexGuard
- Deadlock khi một function gọi chính nó hoặc function dùng cùng lock
- Task timeout khi lock bị giữ lâu

**Ripgrep:**
```bash
# Tìm lock().await hoặc lock().unwrap() trước .await
rg -n "\.lock\(\)" --type rust -A 5 | grep -B 3 "\.await"

# Tìm MutexGuard trong async fn
rg -n "MutexGuard\|lock()" --type rust
```

### 6. Giải pháp

| Tình huống | Giải pháp |
|-----------|-----------|
| Chỉ cần đọc data | Clone/copy data rồi drop guard trước await |
| Cần giữ lock dài | Dùng `tokio::sync::Mutex` (async-aware) |
| Pattern đọc-sửa-ghi | Hạn chế scope lock, await ngoài |
| Shared mutable state | Redesign với message passing |

```rust
// ❌ BAD: Giữ std::sync::MutexGuard qua .await
async fn bad_fn(shared: Arc<Mutex<Data>>) {
    let guard = shared.lock().unwrap(); // Acquire lock
    process_async(&*guard).await;       // guard còn sống → compile error hoặc deadlock
}

// ✅ GOOD: Drop guard trước await
async fn good_fn(shared: Arc<Mutex<Data>>) {
    let data = {
        let guard = shared.lock().unwrap();
        guard.clone() // Clone data
        // guard dropped here, lock released
    };

    process_async(&data).await; // Await mà không giữ lock
}

// ✅ GOOD: tokio::sync::Mutex cho async context
use tokio::sync::Mutex as AsyncMutex;

async fn good_fn_async_mutex(shared: Arc<AsyncMutex<Data>>) {
    // tokio::sync::Mutex::lock() trả về guard có thể giữ qua await
    // nhưng PHẢI biết rằng lock bị giữ trong suốt thời gian await
    let mut guard = shared.lock().await;

    // Chỉ dùng khi cần giữ lock suốt quá trình async
    // VÀ không có deadlock risk
    guard.update_field();
    update_via_guard(&mut *guard).await; // OK nếu không có lock contention
}

// ✅ BEST: Redesign tránh giữ lock qua await
async fn best_approach(shared: Arc<Mutex<Data>>, fetcher: &Fetcher) {
    // 1. Đọc dữ liệu cần thiết
    let id = shared.lock().unwrap().get_id();

    // 2. Fetch không giữ lock
    let extra = fetcher.fetch(id).await;

    // 3. Update với lock ngắn hạn
    shared.lock().unwrap().update(extra);
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Không giữ `std::sync::MutexGuard` qua `.await`
- [ ] Pattern: lock → clone/copy → drop guard → await → lock lại nếu cần
- [ ] Dùng block `{}` để explicit drop guard
- [ ] Prefer `tokio::sync::Mutex` chỉ khi thực sự cần giữ lock qua await
- [ ] Code review: tìm `lock()` theo sau bởi `.await` trong cùng scope

**Clippy / Công cụ:**
```bash
# Clippy có thể detect một số case
cargo clippy -- -W clippy::await_holding_lock

# Đây là một trong những lint quan trọng nhất
cargo clippy -- -D clippy::await_holding_lock
```

---

## CA-16: Oneshot Receiver Drop (Dropped Oneshot Receiver)

### 1. Tên

**Oneshot Receiver Drop** (Oneshot Channel Receiver Dropped Before Receiving)

### 2. Phân loại

- **Lĩnh vực:** Concurrency & Async
- **Danh mục con:** Communication / Error Handling
- **Mã định danh:** CA-16

### 3. Mức nghiêm trọng

🟡 MEDIUM — Khi `oneshot::Receiver<T>` bị drop trước khi nhận, `Sender::send()` trả về `Err(value)`. Nếu sender không xử lý lỗi này, operation được thực hiện nhưng kết quả bị bỏ.

### 4. Vấn đề

`tokio::sync::oneshot` cho phép gửi một giá trị duy nhất. Nếu receiver bị drop (task cancel, timeout, scope exit), sender không thể gửi và nhận `Err`. Code không kiểm tra lỗi này sẽ bỏ qua kết quả silently.

```
  Scenario: Request-Response pattern

  Caller                    Worker
  ──────                    ──────
  let (tx, rx) = oneshot::channel();
  worker.send(Request { tx });

  // Caller timeout sau 1s
  tokio::time::timeout(1s, rx.await)
  // rx dropped on timeout!

                            // Worker finishes after 2s
                            tx.send(result)
                            // Returns Err(result) — bị bỏ qua!
                            // Worker không biết caller đã bỏ
```

**Nguyên nhân phổ biến:**
- `timeout()` wrap `rx.await` → rx dropped khi timeout
- Task cancel trước khi nhận response
- Scope exit với rx chưa được await

### 5. Phát hiện trong mã nguồn

**Dấu hiệu:**
- `tx.send(result).unwrap()` trong worker có thể panic khi receiver gone
- `tx.send(result).ok()` bỏ qua receiver gone silently
- Worker panic "send on dropped oneshot"

**Ripgrep:**
```bash
# Tìm oneshot send không kiểm tra lỗi
rg -n "\.send\(.*\)\.ok\(\)\|\.send\(.*\)\.unwrap\(\)" --type rust

# Tìm oneshot channel creation
rg -n "oneshot::channel\(\)" --type rust
```

### 6. Giải pháp

| Tình huống | Giải pháp |
|-----------|-----------|
| Worker không biết caller gone | Kiểm tra `tx.is_closed()` trước send |
| Timeout ở caller | Handle `Err` từ `send` gracefully |
| Cancel propagation | Dùng `CancellationToken` thay oneshot |
| Cleanup khi receiver gone | Worker kiểm tra `is_closed()` định kỳ |

```rust
// ❌ BAD: Panic hoặc bỏ qua receiver gone
async fn bad_worker(request: Request) {
    let result = do_expensive_work().await;
    request.reply.send(result).unwrap(); // PANIC nếu receiver gone!
}

// ❌ BAD: Silently bỏ qua
async fn also_bad_worker(request: Request) {
    let result = do_expensive_work().await;
    request.reply.send(result).ok(); // Bỏ qua mà không log
}

// ✅ GOOD: Kiểm tra trước khi làm việc nặng
async fn good_worker(request: Request) {
    // Kiểm tra receiver còn sống không trước khi tốn công
    if request.reply.is_closed() {
        tracing::debug!("Caller already gone, skipping work");
        return;
    }

    let result = do_expensive_work().await;

    // Kiểm tra lại sau work (có thể timeout trong khi làm việc)
    if let Err(unsent) = request.reply.send(result) {
        tracing::debug!("Caller gone during processing, result dropped");
        // Cleanup nếu cần với unsent value
        cleanup(unsent).await;
    }
}

// ✅ GOOD: Caller xử lý receiver closed
async fn caller(worker_tx: mpsc::Sender<Request>) -> Result<Response, Error> {
    let (reply_tx, reply_rx) = tokio::sync::oneshot::channel();

    worker_tx.send(Request { reply: reply_tx }).await
        .map_err(|_| Error::WorkerDead)?;

    match tokio::time::timeout(Duration::from_secs(5), reply_rx).await {
        Ok(Ok(response)) => Ok(response),
        Ok(Err(_)) => Err(Error::WorkerDroppedSender),  // Worker dropped sender
        Err(_) => Err(Error::Timeout),                   // Timeout
    }
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Worker luôn kiểm tra `tx.is_closed()` trước khi làm việc nặng
- [ ] Không dùng `send(...).unwrap()` trong worker
- [ ] Log khi receiver gone (debug level)
- [ ] Cleanup expensive resources khi work không được nhận
- [ ] Test timeout scenario explicitly

**Clippy / Công cụ:**
```bash
# Tìm unwrap trên oneshot send
rg "\.send\(.*\)\.unwrap\(\)" --type rust

# Không có clippy lint sẵn
cargo clippy
```

---

## CA-17: Task Local Confusion (task_local! Confusion)

### 1. Tên

**Task Local Confusion** (Misunderstanding task_local! Scope)

### 2. Phân loại

- **Lĩnh vực:** Concurrency & Async
- **Danh mục con:** Correctness / Scope
- **Mã định danh:** CA-17

### 3. Mức nghiêm trọng

🟡 MEDIUM — `task_local!` giá trị chỉ available trong scope của `LocalKey::scope()`. Spawn task con không kế thừa task-local values từ task cha, gây `None` hoặc panic khi truy cập.

### 4. Vấn đề

`tokio::task_local!` tạo storage cục bộ cho từng task, tương tự thread-local nhưng cho async tasks. Nhiều lập trình viên kỳ vọng task con kế thừa giá trị từ task cha — điều này KHÔNG xảy ra.

```
  task_local! { static REQUEST_ID: String; }

  async fn handle_request(id: String) {
      REQUEST_ID.scope(id, async {
          // REQUEST_ID available ở đây

          tokio::spawn(async {
              // Task CON — REQUEST_ID KHÔNG available!
              REQUEST_ID.with(|id| ...) // PANIC: task local not set
          });
      }).await;
  }
```

**Nguyên nhân phổ biến:**
- Dùng task_local cho request context (tracing ID, user ID)
- Spawn subtask kỳ vọng kế thừa context
- Middleware set task_local nhưng handler spawn task

### 5. Phát hiện trong mã nguồn

**Dấu hiệu:**
- Panic "task local not set" trong spawned tasks
- Tracing ID không xuất hiện trong subtask logs
- `task_local.try_with()` trả về `None` trong spawned task

**Ripgrep:**
```bash
# Tìm task_local usage
rg -n "task_local!\|LocalKey" --type rust

# Tìm spawn trong scope của task_local
rg -n "tokio::spawn" --type rust -B 10 | grep -B 5 "scope("
```

### 6. Giải pháp

| Tình huống | Giải pháp |
|-----------|-----------|
| Request context trong subtask | Truyền explicit qua parameter |
| Tracing context | `tracing::Span::enter()` và `instrument()` |
| User context | Truyền `Arc<UserContext>` |
| Wrap spawn với context | Helper function set task_local trước spawn |

```rust
use tokio::task_local;

task_local! {
    static REQUEST_ID: String;
}

// ❌ BAD: Kỳ vọng kế thừa task_local
async fn bad_handler(request_id: String) {
    REQUEST_ID.scope(request_id, async {
        tokio::spawn(async {
            // PANIC: task local not set trong spawned task
            let id = REQUEST_ID.with(|id| id.clone());
            process_with_id(id).await;
        });
    }).await;
}

// ✅ GOOD: Truyền explicit vào spawned task
async fn good_handler(request_id: String) {
    REQUEST_ID.scope(request_id.clone(), async {
        let id_for_spawn = request_id.clone();
        tokio::spawn(async move {
            // id_for_spawn được truyền tường minh
            REQUEST_ID.scope(id_for_spawn, async {
                let id = REQUEST_ID.with(|id| id.clone());
                process_with_id(id).await;
            }).await;
        });
    }).await;
}

// ✅ GOOD: Helper để propagate context
async fn spawn_with_context<F, Fut>(
    request_id: String,
    f: F,
) -> tokio::task::JoinHandle<()>
where
    F: FnOnce() -> Fut + Send + 'static,
    Fut: std::future::Future<Output = ()> + Send + 'static,
{
    tokio::spawn(async move {
        REQUEST_ID.scope(request_id, f()).await;
    })
}

// ✅ GOOD: Dùng tracing span thay task_local cho request ID
use tracing::Instrument;

async fn good_tracing_handler(request_id: String) {
    let span = tracing::info_span!("request", request_id = %request_id);

    async move {
        tokio::spawn(
            async move {
                tracing::info!("Processing in subtask"); // Kế thừa span
                do_work().await;
            }
            .instrument(span.clone()), // Instrument subtask với span
        );
    }
    .instrument(span)
    .await;
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Hiểu rõ: task_local KHÔNG kế thừa qua `tokio::spawn`
- [ ] Dùng `tracing::Span` + `instrument()` cho distributed tracing
- [ ] Truyền context explicit qua parameter hoặc `Arc<T>`
- [ ] Document rõ ràng nếu dùng task_local cho gì
- [ ] Test behavior trong spawned tasks

**Clippy / Công cụ:**
```bash
# Không có lint tự động
# Dùng tracing ecosystem thay task_local cho observability
cargo add tracing tracing-subscriber
```

---

## CA-18: Graceful Shutdown Thiếu (Missing Graceful Shutdown)

### 1. Tên

**Graceful Shutdown Thiếu** (Missing Graceful Shutdown Logic)

### 2. Phân loại

- **Lĩnh vực:** Concurrency & Async
- **Danh mục con:** Reliability / Data Integrity
- **Mã định danh:** CA-18

### 3. Mức nghiêm trọng

🟠 **HIGH** — Thiếu graceful shutdown dẫn đến: request đang xử lý bị cắt giữa chừng, dữ liệu chưa flush ra disk bị mất, connection pool không được đóng sạch, Kubernetes pod restart loop.

### 4. Vấn đề

Khi nhận SIGTERM (Kubernetes, systemd, Ctrl+C), chương trình cần thời gian để:
1. Ngừng nhận request mới
2. Chờ request đang xử lý hoàn thành
3. Flush buffer/cache
4. Đóng connections

Không làm điều này → data loss và "failed" request.

```
  SIGTERM received
       │
       ▼  Không có graceful shutdown:
  Process exits IMMEDIATELY
  ┌────────────────────────────────────────────┐
  │  Request A: 50% complete → ABORTED         │
  │  Request B: writing to DB → PARTIAL WRITE  │
  │  Buffer: 1000 log entries → LOST           │
  │  Connection pool: 50 conns → LEAKED        │
  └────────────────────────────────────────────┘

  → User sees 500 errors
  → DB có orphaned transactions
  → Kubernetes: pod restart loop
```

**Nguyên nhân phổ biến:**
- Không handle SIGTERM/SIGINT
- Chỉ dùng `std::process::exit()` không cleanup
- Background tasks không được tracked
- HTTP server không drain connections

### 5. Phát hiện trong mã nguồn

**Dấu hiệu:**
- Không có `tokio::signal::ctrl_c()` hoặc signal handler
- `std::process::exit()` được gọi trực tiếp
- Không có tracking cho background tasks
- Kubernetes readiness probe fail sau SIGTERM

**Ripgrep:**
```bash
# Tìm signal handling
rg -n "ctrl_c\|signal::unix\|SIGTERM\|SIGINT" --type rust

# Tìm direct exit
rg -n "std::process::exit\|process::exit" --type rust

# Kiểm tra có graceful shutdown không
rg -n "graceful\|shutdown\|drain" --type rust
```

### 6. Giải pháp

| Tình huống | Giải pháp |
|-----------|-----------|
| HTTP server | `axum`/`actix` graceful shutdown |
| Background tasks | `JoinSet` + `CancellationToken` |
| Buffers | Explicit flush trước exit |
| Kubernetes | Readiness probe + terminationGracePeriodSeconds |

```rust
use tokio::signal;
use tokio_util::sync::CancellationToken;
use tokio::task::JoinSet;

// ✅ GOOD: Graceful shutdown với CancellationToken
#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let shutdown_token = CancellationToken::new();
    let mut task_set = JoinSet::new();

    // Spawn background tasks với shutdown token
    let token = shutdown_token.clone();
    task_set.spawn(async move {
        background_worker(token).await;
    });

    let token = shutdown_token.clone();
    task_set.spawn(async move {
        another_worker(token).await;
    });

    // HTTP server với graceful shutdown
    let server = axum::Server::bind(&"0.0.0.0:8080".parse()?)
        .serve(app.into_make_service())
        .with_graceful_shutdown(async {
            // Chờ signal hoặc token
            tokio::select! {
                _ = signal::ctrl_c() => {},
                _ = shutdown_token.cancelled() => {},
            }
        });

    // Xử lý shutdown signal
    tokio::select! {
        _ = signal::ctrl_c() => {
            tracing::info!("Received Ctrl+C, initiating graceful shutdown");
        }
        // Thêm SIGTERM cho Linux/Kubernetes
        _ = async {
            #[cfg(unix)]
            {
                let mut sigterm = signal::unix::signal(signal::unix::SignalKind::terminate())?;
                sigterm.recv().await;
                Ok::<_, Box<dyn std::error::Error>>(())
            }
        } => {
            tracing::info!("Received SIGTERM, initiating graceful shutdown");
        }
        result = server => {
            result?;
        }
    }

    // Signal tất cả task dừng
    shutdown_token.cancel();

    // Chờ tất cả task hoàn thành với timeout
    let shutdown_deadline = tokio::time::sleep(Duration::from_secs(30));
    tokio::pin!(shutdown_deadline);

    loop {
        tokio::select! {
            _ = &mut shutdown_deadline => {
                tracing::warn!("Shutdown deadline exceeded, forcing exit");
                break;
            }
            result = task_set.join_next() => {
                match result {
                    Some(Ok(())) => {}
                    Some(Err(e)) => tracing::error!("Task error during shutdown: {}", e),
                    None => {
                        tracing::info!("All tasks completed, shutdown successful");
                        break;
                    }
                }
            }
        }
    }

    // Flush buffers
    tracing::info!("Flushing logs...");
    // logging framework flush

    Ok(())
}

// Worker biết về cancellation
async fn background_worker(token: CancellationToken) {
    loop {
        tokio::select! {
            biased;
            _ = token.cancelled() => {
                tracing::info!("Background worker shutting down");
                // Cleanup
                flush_pending().await;
                break;
            }
            _ = do_periodic_work() => {}
        }
    }
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Handle SIGTERM (Linux) và Ctrl+C (Windows/dev)
- [ ] HTTP server dùng `with_graceful_shutdown()`
- [ ] Tất cả background task nhận `CancellationToken`
- [ ] Timeout cho shutdown (tránh block vô thời hạn)
- [ ] Flush tất cả buffers (log, metrics, cache) trước exit
- [ ] Test graceful shutdown trong integration test
- [ ] Kubernetes: đặt `terminationGracePeriodSeconds` phù hợp

**Clippy / Công cụ:**
```bash
cargo add tokio-util --features sync   # CancellationToken
cargo add signal-hook                  # Cross-platform signals

# Test shutdown
# Gửi SIGTERM trong test:
# nix::sys::signal::kill(nix::unistd::Pid::this(), nix::sys::signal::Signal::SIGTERM)
```

---

## Tóm tắt nhanh

| Mã | Tên | Mức độ | Phát hiện nhanh |
|----|-----|--------|-----------------|
| CA-01 | Blocking Trong Async | 🔴 CRITICAL | `std::thread::sleep` trong `async fn` |
| CA-02 | Tokio Runtime Lồng Nhau | 🔴 CRITICAL | `Runtime::new()` trong async |
| CA-03 | Send/Sync Thiếu | 🟠 HIGH | `Rc`/`RefCell` trong spawned task |
| CA-04 | Deadlock Arc<Mutex> | 🔴 CRITICAL | Multiple `lock()` khác thứ tự |
| CA-05 | Channel Đầy Không Xử Lý | 🟠 HIGH | `try_send(...).ok()` |
| CA-06 | Bầy Đàn Ồ Ạt | 🟠 HIGH | Nhiều task chờ cùng cache key |
| CA-07 | Select Bias | 🟡 MEDIUM | `select!` không có `biased;` |
| CA-08 | Spawn Không Join | 🟠 HIGH | `tokio::spawn(...)` không assign |
| CA-09 | Async Trait Overhead | 🟡 MEDIUM | `#[async_trait]` hot path |
| CA-10 | Rayon Trong Tokio | 🔴 CRITICAL | `par_iter()` trong `async fn` |
| CA-11 | RwLock Starvation | 🟠 HIGH | `std::sync::RwLock` read-heavy |
| CA-12 | Atomic Ordering Sai | 🔴 CRITICAL | `Ordering::Relaxed` cho flag |
| CA-13 | Future Không Poll | 🟡 MEDIUM | `async fn` gọi không có `.await` |
| CA-14 | Cancellation Unsafety | 🟠 HIGH | Multi-step await không atomic |
| CA-15 | Mutex Guard Qua Await | 🔴 CRITICAL | `lock()` trước `.await` cùng scope |
| CA-16 | Oneshot Receiver Drop | 🟡 MEDIUM | `send(...).unwrap()` trong worker |
| CA-17 | Task Local Confusion | 🟡 MEDIUM | `task_local!` trong spawned task |
| CA-18 | Graceful Shutdown Thiếu | 🟠 HIGH | Không handle SIGTERM |

---

## Lệnh Ripgrep Tổng Hợp

```bash
# Scan toàn bộ project cho các anti-pattern concurrency
echo "=== CA-01: Blocking in Async ===" && rg "std::thread::sleep|std::fs::" --type rust

echo "=== CA-02: Nested Runtime ===" && rg "Runtime::new\(\)|\.block_on\(" --type rust

echo "=== CA-04: Multiple Locks ===" && rg "\.lock\(\)" --type rust -l

echo "=== CA-05: Ignored Channel Full ===" && rg "try_send.*\.ok\(\)" --type rust

echo "=== CA-08: Detached Spawn ===" && rg "tokio::spawn\(" --type rust | grep -v "let "

echo "=== CA-10: Rayon in Async ===" && rg "par_iter\|rayon::" --type rust

echo "=== CA-12: Relaxed Ordering ===" && rg "Ordering::Relaxed" --type rust

echo "=== CA-15: Guard Across Await ===" && rg "await_holding_lock" --type rust

echo "=== CA-18: Missing Shutdown ===" && rg "ctrl_c\|SIGTERM\|graceful" --type rust
```

---

*Domain 02 — Concurrency & Async | 18 patterns | Rust | 2026-02-18*
