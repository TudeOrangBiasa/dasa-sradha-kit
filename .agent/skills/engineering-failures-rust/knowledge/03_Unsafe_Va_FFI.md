# Lĩnh vực 03: Unsafe Và FFI
# Domain 03: Unsafe & FFI

> **Lĩnh vực:** Unsafe Rust và Foreign Function Interface
> **Số mẫu:** 12
> **Ngôn ngữ:** Rust
> **Ngày cập nhật:** 2026-02-18

---

## Tổng quan

`unsafe` Rust trao quyền kiểm soát tuyệt đối cho lập trình viên — nhưng đồng thời tước đi mạng lưới bảo vệ của compiler. FFI (Foreign Function Interface) là cầu nối giữa Rust và thế giới C/C++, nơi mọi contract an toàn phải được lập trình viên tự đảm bảo. Một lỗi nhỏ trong `unsafe` block hoặc trên biên giới FFI có thể dẫn đến undefined behavior, use-after-free, data race hay crash không xác định — những lỗi mà compiler không thể bắt và chỉ công cụ như Miri hoặc AddressSanitizer mới phát hiện được.

---

## Mục lục

| #  | Mã     | Tên mẫu                                  | Mức độ      |
|----|--------|------------------------------------------|-------------|
| 1  | UF-01  | Undefined Behavior Ẩn                    | 🔴 CRITICAL |
| 2  | UF-02  | Null Pointer Từ C FFI                    | 🔴 CRITICAL |
| 3  | UF-03  | Sai ABI Convention                       | 🔴 CRITICAL |
| 4  | UF-04  | Dangling Pointer FFI                     | 🔴 CRITICAL |
| 5  | UF-05  | Transmute Lạm Dụng                       | 🔴 CRITICAL |
| 6  | UF-06  | Uninitialized Memory (MaybeUninit)       | 🔴 CRITICAL |
| 7  | UF-07  | Data Race Trong Unsafe                   | 🔴 CRITICAL |
| 8  | UF-08  | Union Field Sai                          | 🟠 HIGH     |
| 9  | UF-09  | Invariant Vi Phạm                        | 🔴 CRITICAL |
| 10 | UF-10  | Memory Leak Qua FFI                      | 🟠 HIGH     |
| 11 | UF-11  | Thread Safety FFI                        | 🔴 CRITICAL |
| 12 | UF-12  | Panic Qua FFI Boundary                   | 🔴 CRITICAL |

---

## UF-01: Undefined Behavior Ẩn (Hidden Undefined Behavior)

### 1. Tên

**Undefined Behavior Ẩn** (Hidden Undefined Behavior in Unsafe Block)

### 2. Phân loại

- **Lĩnh vực:** Unsafe Rust
- **Danh mục con:** Memory Safety / Correctness
- **Mã định danh:** UF-01

### 3. Mức nghiêm trọng

🔴 **CRITICAL** — Undefined behavior (UB) trong unsafe block có thể biểu hiện ngay lập tức hoặc im lặng trong nhiều tháng rồi đột ngột gây crash/data corruption khi thay đổi compiler version hoặc optimization level. Compiler Rust được phép giả định UB không bao giờ xảy ra và tối ưu hóa theo cách hoàn toàn bất ngờ.

### 4. Vấn đề

```
unsafe block: lập trình viên hứa "code này an toàn"
                │
                ▼
    ┌──────────────────────────────┐
    │  Compiler tin tưởng tuyệt   │
    │  đối — không kiểm tra gì    │
    └──────────────┬───────────────┘
                   │ UB xảy ra (VD: reference đến freed memory)
                   ▼
    ┌──────────────────────────────┐
    │  Compiler giả định UB = ∅   │
    │  → tối ưu hóa sai lệch      │
    │  → hành vi hoàn toàn không  │
    │    đoán trước được           │
    └──────────────────────────────┘

UB phổ biến nhất:
  • Tạo &T / &mut T trỏ vào vùng nhớ freed / uninitialized
  • Alias &mut T (hai &mut T cùng trỏ vào một vùng nhớ)
  • Đọc/ghi ngoài biên của slice
  • Tạo enum/bool với bit pattern không hợp lệ
```

### 5. Phát hiện

```bash
# Tìm unsafe block trong codebase
rg --type rust "unsafe\s*\{" -n

# Tìm raw pointer dereference
rg --type rust "\*\s*(mut\s+)?[a-zA-Z_]" -n

# Tìm slice::from_raw_parts usage
rg --type rust "slice::from_raw_parts" -n

# Chạy Miri để phát hiện UB tại runtime
cargo +nightly miri test
cargo +nightly miri run
```

### 6. Giải pháp

```rust
// ❌ BAD: Tạo reference từ raw pointer mà không kiểm tra
unsafe fn bad_deref(ptr: *const i32) -> i32 {
    *ptr  // UB nếu ptr null hoặc dangling
}

// ❌ BAD: Alias &mut T — UB tường minh
fn create_aliases(v: &mut Vec<i32>) {
    let alias1: &mut Vec<i32> = unsafe { &mut *(v as *mut Vec<i32>) };
    let alias2: &mut Vec<i32> = unsafe { &mut *(v as *mut Vec<i32>) };
    // alias1 và alias2 cùng trỏ vào v → UB!
    alias1.push(1);
    alias2.push(2);
}

// ❌ BAD: slice::from_raw_parts với độ dài sai
unsafe fn bad_slice(ptr: *const u8, len: usize) -> &'static [u8] {
    std::slice::from_raw_parts(ptr, len * 2)  // len * 2 có thể vượt biên!
}

// ✅ GOOD: Kiểm tra pointer trước khi deref
unsafe fn safe_deref(ptr: *const i32) -> Option<i32> {
    if ptr.is_null() {
        return None;
    }
    // Caller phải đảm bảo ptr còn sống và aligned
    Some(unsafe { *ptr })
}

// ✅ GOOD: Tài liệu hóa safety contract trong doc comment
/// # Safety
///
/// - `ptr` phải là non-null
/// - `ptr` phải trỏ đến một `i32` được khởi tạo hợp lệ
/// - `ptr` phải còn sống trong suốt lifetime 'a
/// - `len` phải khớp chính xác với số phần tử được cấp phát
unsafe fn documented_slice<'a>(ptr: *const u8, len: usize) -> &'a [u8] {
    debug_assert!(!ptr.is_null(), "ptr must not be null");
    debug_assert!(len <= isize::MAX as usize, "len too large");
    std::slice::from_raw_parts(ptr, len)
}

// ✅ GOOD: Đóng gói unsafe trong abstraction an toàn
pub struct SafeBuffer {
    ptr: *mut u8,
    len: usize,
    cap: usize,
}

impl SafeBuffer {
    pub fn get(&self, idx: usize) -> Option<u8> {
        if idx >= self.len {
            return None;
        }
        // SAFETY: idx < self.len, ptr hợp lệ và được cấp phát với cap >= len
        Some(unsafe { *self.ptr.add(idx) })
    }
}
```

### 7. Phòng ngừa

```toml
# Cargo.toml — thêm Miri vào CI
[dev-dependencies]
# Không cần dep, chạy: cargo +nightly miri test

# .cargo/config.toml — bật sanitizer trong CI
[target.x86_64-unknown-linux-gnu]
rustflags = ["-Z", "sanitizer=address"]
```

```bash
# Clippy lint liên quan đến unsafe
cargo clippy -- \
  -W clippy::undocumented_unsafe_blocks \
  -W clippy::multiple_unsafe_ops_per_block \
  -W clippy::ptr_as_ptr

# Bắt buộc tài liệu safety cho mọi unsafe block
# Thêm vào lib.rs / main.rs:
#![deny(clippy::undocumented_unsafe_blocks)]
```

---

## UF-02: Null Pointer Từ C FFI (Null Pointer from C FFI)

### 1. Tên

**Null Pointer Từ C FFI** (Null Pointer Dereference via C FFI)

### 2. Phân loại

- **Lĩnh vực:** FFI
- **Danh mục con:** Null Safety / C Interop
- **Mã định danh:** UF-02

### 3. Mức nghiêm trọng

🔴 **CRITICAL** — Nhiều hàm C trả về NULL để báo lỗi (malloc, fopen, getenv…). Nếu Rust không kiểm tra và chuyển thẳng sang reference, dereference NULL pointer gây segfault hoặc UB tức thì.

### 4. Vấn đề

```
C function: char* get_name() { return NULL; }  ← báo lỗi bằng NULL
                │
                │ Rust nhận *const c_char
                ▼
    ┌────────────────────────────────────┐
    │  CStr::from_ptr(ptr)               │
    │  (không kiểm tra null)             │
    │         │                          │
    │         ▼                          │
    │  Dereference 0x0000000000000000    │
    │         │                          │
    │         ▼                          │
    │       SEGFAULT / UB                │
    └────────────────────────────────────┘

Trong C: NULL là giá trị trả về lỗi hợp lệ
Trong Rust: tạo reference từ NULL = UB ngay lập tức
```

### 5. Phát hiện

```bash
# Tìm CStr::from_ptr không có kiểm tra null trước đó
rg --type rust "CStr::from_ptr" -n -A 2

# Tìm extern C binding
rg --type rust "extern\s+\"C\"" -n

# Tìm *const c_char / *mut c_char usage
rg --type rust "\*\s*(const|mut)\s+c_char" -n

# Tìm .unwrap() trực tiếp sau FFI call
rg --type rust "extern.*\n.*fn.*\*" --multiline -n
```

### 6. Giải pháp

```rust
use std::ffi::{CStr, c_char};

// ❌ BAD: Chuyển thẳng pointer thành &CStr mà không kiểm tra null
extern "C" {
    fn get_config_path() -> *const c_char;
}

fn bad_get_path() -> String {
    unsafe {
        let ptr = get_config_path();
        CStr::from_ptr(ptr)  // UB nếu ptr == NULL!
            .to_string_lossy()
            .into_owned()
    }
}

// ✅ GOOD: Luôn kiểm tra null trước khi dereference
fn good_get_path() -> Option<String> {
    unsafe {
        let ptr = get_config_path();
        if ptr.is_null() {
            return None;
        }
        // SAFETY: ptr non-null, C code đảm bảo valid UTF-8 null-terminated string
        Some(
            CStr::from_ptr(ptr)
                .to_string_lossy()
                .into_owned()
        )
    }
}

// ✅ GOOD: Wrapper type để enforce null check tại type level
use std::ptr::NonNull;

extern "C" {
    fn create_handle() -> *mut std::ffi::c_void;
    fn destroy_handle(h: *mut std::ffi::c_void);
}

pub struct Handle(NonNull<std::ffi::c_void>);

impl Handle {
    pub fn new() -> Option<Self> {
        let ptr = unsafe { create_handle() };
        NonNull::new(ptr).map(Handle)  // None nếu ptr == NULL
    }
}

impl Drop for Handle {
    fn drop(&mut self) {
        unsafe { destroy_handle(self.0.as_ptr()) }
    }
}

// ✅ GOOD: Dùng Option<NonNull<T>> trong struct FFI
#[repr(C)]
struct FfiResult {
    data: *mut u8,   // nullable
    len: usize,
}

fn process_ffi_result(res: FfiResult) -> Option<Vec<u8>> {
    let ptr = NonNull::new(res.data)?;  // Trả về None nếu null
    if res.len == 0 {
        return Some(Vec::new());
    }
    // SAFETY: ptr non-null, len đúng, memory thuộc về C caller
    let slice = unsafe { std::slice::from_raw_parts(ptr.as_ptr(), res.len) };
    Some(slice.to_vec())
}
```

### 7. Phòng ngừa

```bash
# Clippy lint
cargo clippy -- \
  -W clippy::not_unsafe_ptr_arg_deref \
  -W clippy::ptr_as_ptr

# Dùng bindgen để tự động sinh binding an toàn hơn
# bindgen tự động map pointer trả về thành Option<NonNull<T>>
# khi detect hàm có thể trả NULL

# Trong build.rs:
# bindgen::Builder::default()
#     .header("wrapper.h")
#     .generate_comments(true)
#     .generate()
```

```rust
// Macro kiểm tra null cho toàn project
macro_rules! non_null_or_return {
    ($ptr:expr, $ret:expr) => {
        if $ptr.is_null() {
            return $ret;
        }
    };
}
```

---

## UF-03: Sai ABI Convention (Wrong ABI Convention)

### 1. Tên

**Sai ABI Convention** (Incorrect ABI / Calling Convention Mismatch)

### 2. Phân loại

- **Lĩnh vực:** FFI
- **Danh mục con:** ABI / Calling Convention
- **Mã định danh:** UF-03

### 3. Mức nghiêm trọng

🔴 **CRITICAL** — Mismatch ABI giữa Rust và C gây stack corruption, wrong return values, hoặc crash không xác định. Compiler không phát hiện được — lỗi chỉ thấy tại runtime với hành vi ngẫu nhiên.

### 4. Vấn đề

```
Rust side:                    C side:
extern "C" fn foo(x: i32)    void foo(float x)  ← type mismatch!
                │                     │
                └──────── ABI ─────────┘
                           │
                    Stack frame layout:
                    Rust: i32 (4 bytes, integer register)
                    C:   float (4 bytes, FP register)
                           │
                    C đọc FP register → garbage value
                    Stack có thể bị lệch (variadic args)
                    Return value đọc sai register

Lỗi phổ biến:
  • Thiếu `extern "C"` → Rust ABI (không ổn định)
  • Sai type: i32 ↔ u32 ↔ f32 (cùng 4 bytes, khác register)
  • Variadic function không có `...` trong Rust
  • Windows stdcall vs cdecl mismatch
```

### 5. Phát hiện

```bash
# Tìm extern block không có ABI specification
rg --type rust "^extern\s*\{" -n

# Tìm callback function pointer không có "C" ABI
rg --type rust "fn\s*\(.*\)\s*->" -n | rg -v "extern"

# Tìm potential type mismatch (bool / c_int)
rg --type rust "extern.*fn.*bool" -n

# Kiểm tra struct layout với #[repr(C)]
rg --type rust "extern.*struct" -n | rg -v "#\[repr\(C\)\]"
```

### 6. Giải pháp

```rust
use std::ffi::{c_int, c_float, c_char, c_void};

// ❌ BAD: Dùng Rust type thay vì C type
extern "C" {
    fn c_add(a: i32, b: i32) -> i32;  // OK trên most platforms, nhưng fragile
    fn set_callback(cb: fn(i32) -> i32);  // BAD: Rust fn ABI ≠ C function pointer
    fn process(flag: bool) -> bool;  // BAD: bool size khác nhau trên C/Rust
}

// ❌ BAD: Quên extern "C" cho callback được gọi từ C
fn my_callback(x: i32) -> i32 {  // Rust ABI, không gọi được từ C!
    x * 2
}

// ✅ GOOD: Dùng C-compatible types từ std::ffi
extern "C" {
    fn c_add(a: c_int, b: c_int) -> c_int;
    fn set_callback(cb: Option<unsafe extern "C" fn(c_int) -> c_int>);
    fn process(flag: c_int) -> c_int;  // C bool thường là int
}

// ✅ GOOD: Callback phải có extern "C"
unsafe extern "C" fn my_callback(x: c_int) -> c_int {
    x * 2
}

// ✅ GOOD: Register callback đúng cách
fn register() {
    unsafe {
        set_callback(Some(my_callback));
    }
}

// ✅ GOOD: Struct FFI phải có #[repr(C)]
#[repr(C)]
pub struct Point {
    x: c_float,
    y: c_float,
}

// ❌ BAD: Struct không có repr(C) — layout không đảm bảo
pub struct BadPoint {
    x: f32,
    y: f32,
    // Compiler có thể reorder fields!
}

// ✅ GOOD: Enum FFI phải có repr(C) hoặc repr(i32) cụ thể
#[repr(C)]
pub enum Status {
    Ok = 0,
    Error = 1,
    Pending = 2,
}

// ✅ GOOD: Variadic function khai báo đúng
extern "C" {
    fn printf(format: *const c_char, ...) -> c_int;
}

// ✅ GOOD: Windows stdcall cho WinAPI
#[cfg(windows)]
extern "stdcall" {
    fn MessageBoxA(
        hwnd: *mut c_void,
        text: *const c_char,
        caption: *const c_char,
        utype: c_int,
    ) -> c_int;
}
```

### 7. Phòng ngừa

```bash
# Dùng bindgen để tự động sinh binding chính xác
cargo install bindgen-cli
bindgen wrapper.h -o src/bindings.rs \
  --use-core \
  --with-derive-default \
  --with-derive-debug

# Clippy
cargo clippy -- \
  -W improper_ctypes \
  -W improper_ctypes_definitions

# cbindgen để kiểm tra Rust → C export
cargo install cbindgen
cbindgen --config cbindgen.toml --crate my-crate --output include/my_crate.h
```

```toml
# Cargo.toml — bật lint bắt buộc
[lints.rust]
improper_ctypes = "deny"
improper_ctypes_definitions = "deny"
```

---

## UF-04: Dangling Pointer FFI (CString Dropped Early)

### 1. Tên

**Dangling Pointer FFI** (CString / Temporary Dropped Before FFI Use)

### 2. Phân loại

- **Lĩnh vực:** FFI
- **Danh mục con:** Lifetime / Use-After-Free
- **Mã định danh:** UF-04

### 3. Mức nghiêm trọng

🔴 **CRITICAL** — `CString` bị drop ngay sau khi `.as_ptr()` được gọi. Pointer trả về trỏ vào vùng nhớ đã được giải phóng — C code đọc garbage data hoặc gây heap corruption.

### 4. Vấn đề

```
let ptr = CString::new("hello").unwrap().as_ptr();
              │                    │
              │    CString::new() tạo CString tạm thời
              │    .as_ptr() lấy raw pointer
              │    CString tạm thời bị DROP ngay đây!
              │                    │
              ▼                    ▼
         ptr trỏ vào         Bộ nhớ được
         freed memory!       giải phóng

Vấn đề tương tự với String::as_ptr(), Vec::as_ptr()
khi temporary không được bind vào variable.

Timeline:
  T1: CString allocated → ptr = 0x1234
  T2: CString dropped   → 0x1234 freed (ptr dangling!)
  T3: C reads ptr       → UB / heap corruption
```

### 5. Phát hiện

```bash
# Pattern nguy hiểm nhất: .new(...).unwrap().as_ptr() trên một dòng
rg --type rust "CString::new\(.*\)\.unwrap\(\)\.as_ptr\(\)" -n

# Tìm as_ptr() sau CString không bind
rg --type rust "CString::new" -n -A 3

# Tìm temporary string pointer
rg --type rust '\.as_ptr\(\)' -n -B 2

# Tìm c_str() chain
rg --type rust '\.to_cstring\(\).*\.as_ptr\(\)' -n
```

### 6. Giải pháp

```rust
use std::ffi::{CString, c_char, c_int};

extern "C" {
    fn set_name(name: *const c_char);
    fn process_data(data: *const c_char) -> c_int;
}

// ❌ BAD: CString tạm thời bị drop ngay sau as_ptr()
fn bad_set_name(name: &str) {
    unsafe {
        let ptr = CString::new(name).unwrap().as_ptr();
        //                          ↑ CString dropped HERE!
        set_name(ptr);  // ptr là dangling pointer!
    }
}

// ❌ BAD: Dạng khác của cùng lỗi
fn bad_process(data: &str) -> i32 {
    unsafe {
        process_data(
            CString::new(data).unwrap().as_ptr()
            //                         ↑ CString dropped trước khi process_data chạy!
        ) as i32
    }
}

// ✅ GOOD: Bind CString vào biến để kéo dài lifetime
fn good_set_name(name: &str) {
    let c_name = CString::new(name).expect("Name contains null byte");
    unsafe {
        set_name(c_name.as_ptr());
        // c_name vẫn sống đến cuối block → ptr hợp lệ
    }
    // c_name dropped ở đây — sau khi set_name đã hoàn thành
}

// ✅ GOOD: Bind trước, dùng sau
fn good_process(data: &str) -> i32 {
    let c_data = CString::new(data).expect("Data contains null byte");
    let result = unsafe {
        process_data(c_data.as_ptr())
    };
    // c_data dropped ở đây
    result as i32
}

// ✅ GOOD: Khi C function giữ pointer lâu dài → dùng Box::into_raw
extern "C" {
    fn register_persistent_name(name: *const c_char);
    fn unregister_persistent_name(name: *const c_char);
}

struct PersistentName(*mut c_char);

impl PersistentName {
    fn new(name: &str) -> Self {
        let c_name = CString::new(name).expect("invalid name");
        let raw = c_name.into_raw();  // CString không bị drop, ta sở hữu raw
        unsafe { register_persistent_name(raw) };
        PersistentName(raw)
    }
}

impl Drop for PersistentName {
    fn drop(&mut self) {
        unsafe {
            unregister_persistent_name(self.0);
            // Tái tạo CString để drop đúng cách
            let _ = CString::from_raw(self.0);
        }
    }
}
```

### 7. Phòng ngừa

```bash
# Clippy bắt được một số pattern này
cargo clippy -- -W clippy::temporary_cstring_as_ptr

# Miri phát hiện use-after-free tại runtime
cargo +nightly miri test

# Code review checklist:
# □ Mọi .as_ptr() phải có biến bind giữ CString/String/Vec sống
# □ Không dùng .as_ptr() trong argument list (temporary drop)
# □ Nếu C giữ pointer lâu dài → dùng into_raw() + manual drop
```

```rust
// Lint tùy chỉnh qua macro
macro_rules! cstring_ptr {
    ($s:expr) => {{
        // Compiler error nếu result không được bind
        let _cstring = CString::new($s).expect("null byte in string");
        compile_error!("Use: let c = CString::new(...)?; foo(c.as_ptr())")
    }};
}
```

---

## UF-05: Transmute Lạm Dụng (Transmute Abuse)

### 1. Tên

**Transmute Lạm Dụng** (std::mem::transmute Misuse)

### 2. Phân loại

- **Lĩnh vực:** Unsafe Rust
- **Danh mục con:** Type System / Memory Reinterpretation
- **Mã định danh:** UF-05

### 3. Mức nghiêm trọng

🔴 **CRITICAL** — `transmute` là hàm nguy hiểm nhất trong Rust. Nó bỏ qua toàn bộ type system và reinterpret bits mà không kiểm tra tính hợp lệ. Dùng sai tạo ra giá trị không hợp lệ (invalid enum, uninitialized bool, etc.) gây UB ngay lập tức.

### 4. Vấn đề

```
std::mem::transmute::<A, B>(value)
  │
  ├─ Size A != Size B → Compile error (Rust bắt được)
  │
  └─ Size A == Size B → Rust tin tưởng bạn:
       A bits reinterpret as B
              │
       ┌──────┴───────────────────────────┐
       │ Các trường hợp UB:               │
       │  • bool với bit pattern != 0/1   │
       │  • enum với discriminant sai     │
       │  • &T với alignment sai          │
       │  • lifetime extension (phổ biến) │
       │  • fn pointer → usize → fn ptr  │
       └──────────────────────────────────┘

Ví dụ nguy hiểm:
  transmute::<u8, bool>(2)  → bool với bit 2 = UB
  transmute::<u32, MyEnum>(99)  → invalid discriminant = UB
```

### 5. Phát hiện

```bash
# Tìm mọi transmute usage
rg --type rust "mem::transmute|std::mem::transmute" -n

# Tìm transmute dùng để extend lifetime (rất nguy hiểm)
rg --type rust "transmute.*lifetime|transmute.*'static" -n

# Tìm transmute fn pointer
rg --type rust "transmute.*fn\s*\(" -n

# Tìm transmute trong lib/production code (không phải test)
rg --type rust "transmute" --glob "!*test*" --glob "!*spec*" -n
```

### 6. Giải pháp

```rust
use std::mem;

// ❌ BAD: transmute để convert giữa numeric types
unsafe fn bad_f32_to_bits(f: f32) -> u32 {
    mem::transmute(f)
}

// ✅ GOOD: Dùng API có sẵn
fn good_f32_to_bits(f: f32) -> u32 {
    f.to_bits()  // f32::to_bits() là safe API
}

// ❌ BAD: transmute để extend lifetime — cực kỳ nguy hiểm
fn bad_extend_lifetime<'a>(s: &'a str) -> &'static str {
    unsafe { mem::transmute(s) }
    // 'static reference đến data có thể bị drop → UAF!
}

// ✅ GOOD: Dùng Box::leak nếu thực sự cần 'static
fn intentional_leak(s: String) -> &'static str {
    Box::leak(s.into_boxed_str())
    // Explicit, documented, và memory leak là có chủ đích
}

// ❌ BAD: transmute enum từ integer
#[repr(u8)]
enum Direction { North = 0, South = 1, East = 2, West = 3 }

unsafe fn bad_from_u8(v: u8) -> Direction {
    mem::transmute(v)  // UB nếu v >= 4!
}

// ✅ GOOD: Implement TryFrom với kiểm tra range
impl TryFrom<u8> for Direction {
    type Error = u8;
    fn try_from(v: u8) -> Result<Self, Self::Error> {
        match v {
            0 => Ok(Direction::North),
            1 => Ok(Direction::South),
            2 => Ok(Direction::East),
            3 => Ok(Direction::West),
            n => Err(n),
        }
    }
}

// ❌ BAD: transmute slice → khác element type
unsafe fn bad_slice_cast(s: &[u8]) -> &[u32] {
    mem::transmute(s)  // length sai (×4), alignment không đảm bảo!
}

// ✅ GOOD: Dùng bytemuck cho safe pod casting
// (crate bytemuck)
use bytemuck::cast_slice;

fn good_slice_cast(s: &[u8]) -> Option<&[u32]> {
    bytemuck::try_cast_slice(s).ok()  // Kiểm tra alignment và length
}

// ❌ BAD: transmute function pointer
type CCallback = unsafe extern "C" fn(*mut u8) -> i32;
fn bad_fn_cast(f: fn(*mut u8) -> i32) -> CCallback {
    unsafe { mem::transmute(f) }  // ABI mismatch!
}

// ✅ GOOD: Khai báo đúng ABI ngay từ đầu
unsafe extern "C" fn my_callback(data: *mut u8) -> i32 {
    // implementation
    0
}
let _cb: CCallback = my_callback;  // Type-safe, no transmute needed
```

### 7. Phòng ngừa

```bash
# Clippy cảnh báo transmute
cargo clippy -- \
  -W clippy::transmute_ptr_to_ref \
  -W clippy::transmute_int_to_bool \
  -W clippy::transmute_int_to_char \
  -W clippy::transmute_int_to_float \
  -W clippy::transmute_float_to_int \
  -W clippy::unsound_collection_transmute \
  -W clippy::transmute_undefined_repr

# Thêm vào lib.rs để deny trong production code
#![deny(clippy::transmute_ptr_to_ref)]
#![deny(clippy::transmute_int_to_bool)]

# Alternatives to transmute:
# f32::to_bits / f32::from_bits
# u32::from_ne_bytes / u32::to_ne_bytes
# bytemuck::cast / bytemuck::cast_slice (safe pod casting)
# num_enum::TryFromPrimitive (enum từ int)
```

---

## UF-06: Uninitialized Memory (MaybeUninit Misuse)

### 1. Tên

**Uninitialized Memory (MaybeUninit Misuse)** (Đọc Bộ Nhớ Chưa Khởi Tạo)

### 2. Phân loại

- **Lĩnh vực:** Unsafe Rust
- **Danh mục con:** Memory Safety / Initialization
- **Mã định danh:** UF-06

### 3. Mức nghiêm trọng

🔴 **CRITICAL** — Đọc bộ nhớ chưa khởi tạo là UB trong Rust (và C). Compiler có thể tối ưu hóa dựa trên giả định dữ liệu hợp lệ, dẫn đến hành vi hoàn toàn không đoán trước. `MaybeUninit` là API đúng nhưng rất dễ dùng sai.

### 4. Vấn đề

```
MaybeUninit<T>:
  ┌─────────────────────────────────┐
  │  Trạng thái: Chưa khởi tạo     │
  │  Nội dung: Garbage bits         │
  │  Tạo bởi: MaybeUninit::uninit() │
  └─────────┬───────────────────────┘
            │
  Hai path hợp lệ:
  1. write() → assume_init() → SAFE
  2. Không write() → assume_init() → UB!

Lỗi phổ biến:
  • Quên gọi write() trước assume_init()
  • assume_init() sau partial initialization (struct có nhiều field)
  • Dùng mem::uninitialized() (deprecated, luôn UB)
  • FFI array: chỉ C ghi vào một phần, Rust đọc toàn bộ
```

### 5. Phát hiện

```bash
# Tìm mem::uninitialized (luôn UB, deprecated)
rg --type rust "mem::uninitialized\(\)" -n

# Tìm assume_init usage
rg --type rust "assume_init\(\)" -n -B 5

# Tìm MaybeUninit::uninit usage
rg --type rust "MaybeUninit::uninit\(\)" -n -A 10

# Tìm zeroed() được dùng cho non-zero-initializable types
rg --type rust "mem::zeroed\(\)" -n
```

### 6. Giải pháp

```rust
use std::mem::MaybeUninit;

// ❌ BAD: mem::uninitialized (deprecated và luôn UB nếu T có invalid bit patterns)
unsafe fn bad_array() -> [String; 4] {
    std::mem::uninitialized()  // String không thể là "uninitialized"!
}

// ❌ BAD: assume_init() mà không ghi đủ
unsafe fn bad_partial_init() -> (i32, String) {
    let mut val: MaybeUninit<(i32, String)> = MaybeUninit::uninit();
    // Chỉ ghi field đầu, quên String
    (*val.as_mut_ptr()).0 = 42;
    val.assume_init()  // UB: String field chưa được init!
}

// ❌ BAD: FFI buffer đọc nhiều hơn C đã ghi
extern "C" {
    fn fill_buffer(buf: *mut u8, len: usize) -> usize; // trả về số bytes thực sự ghi
}

unsafe fn bad_ffi_buffer() -> Vec<u8> {
    let mut buf: [MaybeUninit<u8>; 1024] = MaybeUninit::uninit_array();
    let _written = fill_buffer(buf.as_mut_ptr() as *mut u8, 1024);
    // Đọc toàn bộ 1024 bytes, nhưng chỉ `written` bytes được init!
    buf.iter().map(|b| b.assume_init()).collect()  // UB!
}

// ✅ GOOD: Khởi tạo đúng cách với MaybeUninit
unsafe fn good_primitive() -> i32 {
    let mut val: MaybeUninit<i32> = MaybeUninit::uninit();
    val.write(42);  // Khởi tạo trước
    val.assume_init()  // Safe: đã được write()
}

// ✅ GOOD: Array init với MaybeUninit
fn good_array_init() -> [i32; 1024] {
    // Cách 1: zeroed (OK cho primitive types)
    let arr: [i32; 1024] = unsafe { std::mem::zeroed() };
    arr
}

fn good_array_uninit() -> [String; 4] {
    // Cách an toàn: init từng phần tử
    [
        String::from("a"),
        String::from("b"),
        String::from("c"),
        String::from("d"),
    ]
}

// ✅ GOOD: FFI buffer — chỉ đọc phần đã được ghi
unsafe fn good_ffi_buffer() -> Vec<u8> {
    let mut buf: Vec<u8> = vec![0u8; 1024];  // zero-initialized
    let written = fill_buffer(buf.as_mut_ptr(), buf.len());
    buf.truncate(written);  // Chỉ giữ phần C đã ghi
    buf
}

// ✅ GOOD: MaybeUninit array đúng cách (Rust 1.55+)
unsafe fn good_uninit_array() -> [i32; 4] {
    let mut arr: [MaybeUninit<i32>; 4] = MaybeUninit::uninit_array();
    for (i, slot) in arr.iter_mut().enumerate() {
        slot.write(i as i32 * 2);  // Ghi từng phần tử
    }
    MaybeUninit::array_assume_init(arr)  // Tất cả đã init
}
```

### 7. Phòng ngừa

```bash
# Miri phát hiện reads of uninitialized memory
cargo +nightly miri test

# Clippy
cargo clippy -- \
  -W clippy::uninit_assumed_init \
  -W clippy::uninit_vec

# Deny mem::uninitialized
#![deny(deprecated)]  # mem::uninitialized() is deprecated

# AddressSanitizer trong CI
RUSTFLAGS="-Z sanitizer=memory" cargo +nightly test \
  --target x86_64-unknown-linux-gnu
```

```toml
# Cargo.toml
[lints.rust]
deprecated = "deny"  # Bắt mem::uninitialized()
```

---

## UF-07: Data Race Trong Unsafe (Data Race in Unsafe Code)

### 1. Tên

**Data Race Trong Unsafe** (Data Race via Unsafe Raw Pointer Sharing)

### 2. Phân loại

- **Lĩnh vực:** Unsafe Rust / Concurrency
- **Danh mục con:** Thread Safety / Data Race
- **Mã định danh:** UF-07

### 3. Mức nghiêm trọng

🔴 **CRITICAL** — Rust ngăn data race tại compile-time thông qua `Send`/`Sync`. Nhưng `unsafe` cho phép bypass — chia sẻ raw pointer giữa threads mà không đồng bộ hóa tạo ra data race, một dạng UB không xác định trong Rust (khác với C++, Rust không định nghĩa behavior của data race).

### 4. Vấn đề

```
Thread 1:                    Thread 2:
let ptr: *mut i32 = ...;    let ptr: *mut i32 = ... (same addr)
unsafe { *ptr = 42; }       unsafe { *ptr = 99; }
         │                           │
         └──────── concurrent ────────┘
                       │
               DATA RACE = UB!

Rust type system:
  *mut T → không impl Send/Sync → không thể share giữa threads
  Lập trình viên dùng unsafe để cast/transmute → bypass!

Kịch bản phổ biến:
  • Global mutable static mà không có Mutex/atomic
  • *mut T chia sẻ qua Arc<UnsafeCell<T>> mà không lock
  • Thread pool ghi vào cùng buffer không có sync
```

### 5. Phát hiện

```bash
# Tìm static mut (global mutable state)
rg --type rust "static\s+mut\s" -n

# Tìm UnsafeCell được share qua Arc
rg --type rust "Arc.*UnsafeCell" -n

# Tìm Send impl cho non-Send types
rg --type rust "unsafe impl Send" -n

# Tìm Sync impl thủ công
rg --type rust "unsafe impl Sync" -n

# Tìm raw pointer clone để chia sẻ
rg --type rust "as \*mut|as \*const" -n -B 2 -A 5
```

### 6. Giải pháp

```rust
use std::sync::{Arc, Mutex, atomic::{AtomicI32, Ordering}};

// ❌ BAD: static mut — data race khi access từ nhiều threads
static mut COUNTER: i32 = 0;

fn bad_increment() {
    unsafe { COUNTER += 1; }  // Data race nếu gọi từ nhiều threads!
}

// ❌ BAD: Chia sẻ *mut T qua thread boundary
fn bad_shared_ptr() {
    let mut data = vec![0i32; 100];
    let ptr = data.as_mut_ptr();

    // ptr không impl Send → compiler error!
    // Nhưng nếu wrap trong newtype với unsafe impl Send:
    struct UnsafePtr(*mut i32);
    unsafe impl Send for UnsafePtr {}  // Bypass compiler!

    let shared = UnsafePtr(ptr);
    std::thread::spawn(move || {
        unsafe { *shared.0 = 42; }  // Data race với main thread!
    });
    data[0] = 99;  // Concurrent access → UB!
}

// ✅ GOOD: Dùng AtomicI32 cho counter
static COUNTER: AtomicI32 = AtomicI32::new(0);

fn good_increment() {
    COUNTER.fetch_add(1, Ordering::SeqCst);  // Thread-safe
}

// ✅ GOOD: Mutex cho mutable shared state
fn good_shared_state() {
    let data = Arc::new(Mutex::new(vec![0i32; 100]));
    let data_clone = data.clone();

    std::thread::spawn(move || {
        let mut guard = data_clone.lock().unwrap();
        guard[0] = 42;  // Exclusive access
    });
    {
        let mut guard = data.lock().unwrap();
        guard[0] = 99;  // Exclusive access
    }
}

// ✅ GOOD: Khi cần parallel write vào disjoint parts — split_at_mut
fn good_parallel_write() {
    let mut data = vec![0i32; 100];
    let (left, right) = data.split_at_mut(50);

    std::thread::scope(|s| {
        s.spawn(|| { left[0] = 1; });   // Safe: disjoint
        s.spawn(|| { right[0] = 2; });  // Safe: disjoint
    });
}

// ✅ GOOD: unsafe impl Send/Sync chỉ khi có internal synchronization
use std::cell::UnsafeCell;

pub struct SafeShared<T> {
    inner: UnsafeCell<T>,
    lock: std::sync::Mutex<()>,
}

// SAFETY: lock đảm bảo exclusive access trước khi modify inner
unsafe impl<T: Send> Send for SafeShared<T> {}
unsafe impl<T: Send> Sync for SafeShared<T> {}

impl<T> SafeShared<T> {
    pub fn with<F, R>(&self, f: F) -> R
    where F: FnOnce(&mut T) -> R
    {
        let _guard = self.lock.lock().unwrap();
        // SAFETY: Mutex đảm bảo chỉ một thread access inner tại một thời điểm
        let val = unsafe { &mut *self.inner.get() };
        f(val)
    }
}
```

### 7. Phòng ngừa

```bash
# ThreadSanitizer phát hiện data race tại runtime
RUSTFLAGS="-Z sanitizer=thread" cargo +nightly test \
  --target x86_64-unknown-linux-gnu

# Miri
cargo +nightly miri test

# Clippy
cargo clippy -- \
  -W clippy::non_send_fields_in_send_ty

# Deny static mut
#![deny(static_mut_refs)]  # Rust 1.77+
# Hoặc dùng OnceLock / LazyLock thay vì static mut
```

```rust
// Thay thế static mut bằng OnceLock (thread-safe)
use std::sync::OnceLock;

static CONFIG: OnceLock<String> = OnceLock::new();

fn get_config() -> &'static str {
    CONFIG.get_or_init(|| String::from("default"))
}
```

---

## UF-08: Union Field Sai (Wrong Union Field Read)

### 1. Tên

**Union Field Sai** (Reading Wrong Union Field Causes UB)

### 2. Phân loại

- **Lĩnh vực:** Unsafe Rust
- **Danh mục con:** Union / Type Punning
- **Mã định danh:** UF-08

### 3. Mức nghiêm trọng

🟠 **HIGH** — Rust union chia sẻ cùng vùng nhớ cho tất cả fields. Đọc field khác với field vừa ghi reinterpret bits — nếu target type có invalid bit patterns (bool, enum, reference) thì là UB. Nếu là primitive thuần thì là type punning (có thể intentional).

### 4. Vấn đề

```
union MyUnion {
    int_val: i32,
    float_val: f32,
    flag: bool,   ← nguy hiểm!
}

Vùng nhớ: [0x00, 0x00, 0x02, 0x00]
                         ↑
              Giá trị 0x00020000 như i32
              ≠ bit pattern hợp lệ cho bool!

Đọc .flag → bool với bit pattern 0 hoặc khác 0/1 → UB!
Đọc .float_val từ i32 data → type punning (có thể OK)
Đọc .enum_val → discriminant không hợp lệ → UB!
```

### 5. Phát hiện

```bash
# Tìm union definitions
rg --type rust "^union\s" -n -A 10

# Tìm union field access trong unsafe
rg --type rust "\.\s*(int_val|float_val|flag|data)\b" -n

# Tìm union với bool/enum/reference fields
rg --type rust "union" -n -A 10 | rg "bool|enum|&"
```

### 6. Giải pháp

```rust
// ❌ BAD: Union với bool/enum field — đọc sai field là UB
union BadUnion {
    raw: u32,
    flag: bool,   // bool phải là 0 hoặc 1
    count: u8,
}

fn bad_union_read(val: u32) -> bool {
    let u = BadUnion { raw: val };
    unsafe { u.flag }  // UB nếu val bits không phải 0x00 hay 0x01!
}

// ✅ GOOD: Union chỉ với Copy + no-invalid-values types (primitive)
#[repr(C)]
union SafeUnion {
    int_val: i32,
    float_bits: u32,    // Dùng để type-pun f32 ↔ u32
    bytes: [u8; 4],
}

fn type_pun_f32(f: f32) -> u32 {
    let u = SafeUnion { float_bits: f.to_bits() };
    // SAFETY: f32 và u32 có cùng size, tất cả bit patterns đều hợp lệ cho u32
    unsafe { u.float_bits }
    // NHƯNG: Dùng f32::to_bits() còn an toàn hơn và không cần unsafe!
}

// ✅ GOOD: Tag union (discriminated union) với enum wrapper
enum TaggedUnion {
    Int(i32),
    Float(f32),
    Bytes([u8; 4]),
}

// ✅ GOOD: FFI C union — phải theo tagged pattern từ C side
#[repr(C)]
union CValue {
    i: i32,
    f: f32,
    b: [u8; 4],
}

#[repr(C)]
struct TaggedCValue {
    tag: u32,  // 0 = int, 1 = float, 2 = bytes
    value: CValue,
}

fn read_tagged_c_value(tagged: &TaggedCValue) -> i64 {
    match tagged.tag {
        0 => unsafe { tagged.value.i as i64 },
        1 => unsafe { tagged.value.f as i64 },
        _ => 0,
    }
}

// ✅ GOOD: Dùng bytemuck thay vì union cho type punning
use bytemuck::{Pod, Zeroable};

#[derive(Copy, Clone, Pod, Zeroable)]
#[repr(C)]
struct F32Bits(f32);

fn safe_f32_to_u32(f: f32) -> u32 {
    f.to_bits()  // Không cần union!
}
```

### 7. Phòng ngừa

```bash
# Miri phát hiện đọc sai union field
cargo +nightly miri test

# Clippy
cargo clippy -- -W clippy::multiple_unsafe_ops_per_block

# Code review: Mọi union cần tài liệu:
# □ Field nào đang "active" tại thời điểm nào
# □ Safety invariant của mỗi field access
# □ Prefer enum over union khi không cần FFI
```

---

## UF-09: Invariant Vi Phạm (Safety Invariant Violation)

### 1. Tên

**Invariant Vi Phạm** (Safety Invariant Violation)

### 2. Phân loại

- **Lĩnh vực:** Unsafe Rust
- **Danh mục con:** Abstraction Safety / Invariant Maintenance
- **Mã định danh:** UF-09

### 3. Mức nghiêm trọng

🔴 **CRITICAL** — Các type trong standard library và ecosystem có safety invariant mà unsafe code phải duy trì. Vi phạm invariant (ví dụ: String chứa invalid UTF-8, Vec với len > cap) gây UB trong safe code downstream.

### 4. Vấn đề

```
Type              │ Safety Invariant
──────────────────┼──────────────────────────────────
String            │ bytes phải là valid UTF-8
&str              │ trỏ đến valid UTF-8
Vec<T>            │ len <= cap, ptr hợp lệ và aligned
Box<T>            │ ptr non-null, sở hữu allocation
NonNull<T>        │ ptr non-null (nhưng có thể dangling)
BTreeMap          │ keys luôn sorted
──────────────────┴──────────────────────────────────

Nếu vi phạm:
  String với non-UTF8 → str operations → UB
  Vec với len > cap → push → write ngoài allocation → UB
  BTreeMap unsorted → binary search → undefined results
```

### 5. Phát hiện

```bash
# Tìm String::from_utf8_unchecked
rg --type rust "from_utf8_unchecked" -n

# Tìm Vec::set_len (thường dùng sai invariant)
rg --type rust "set_len\(" -n -B 5

# Tìm Box::from_raw (có thể vi phạm ownership invariant)
rg --type rust "Box::from_raw" -n

# Tìm str::from_utf8_unchecked
rg --type rust "str::from_utf8_unchecked" -n
```

### 6. Giải pháp

```rust
// ❌ BAD: Vi phạm UTF-8 invariant của String
fn bad_string_from_bytes(bytes: Vec<u8>) -> String {
    unsafe { String::from_utf8_unchecked(bytes) }
    // Nếu bytes không phải UTF-8 → UB trong mọi operation sau đó!
}

// ✅ GOOD: Luôn validate UTF-8
fn good_string_from_bytes(bytes: Vec<u8>) -> Result<String, std::string::FromUtf8Error> {
    String::from_utf8(bytes)  // Safe: validate UTF-8
}

// ✅ GOOD: Chỉ dùng _unchecked khi đã chắc chắn là UTF-8
fn fast_string_from_known_utf8(bytes: Vec<u8>) -> String {
    debug_assert!(std::str::from_utf8(&bytes).is_ok(), "bytes must be UTF-8");
    // SAFETY: bytes đã được validate là UTF-8 bởi caller/producer
    unsafe { String::from_utf8_unchecked(bytes) }
}

// ❌ BAD: Vec::set_len vi phạm invariant
fn bad_vec_extend(v: &mut Vec<u8>, additional: usize) {
    v.reserve(additional);
    unsafe {
        v.set_len(v.len() + additional);
        // Các phần tử mới chưa được init! Đọc sẽ là UB (nếu T không phải primitive)
    }
}

// ✅ GOOD: Dùng resize hoặc extend cho Vec
fn good_vec_extend(v: &mut Vec<u8>, additional: usize) {
    let new_len = v.len() + additional;
    v.resize(new_len, 0u8);  // Zero-initialized
}

// ✅ GOOD: set_len đúng cách với FFI (ghi rồi mới set_len)
unsafe fn ffi_fill_vec() -> Vec<u8> {
    extern "C" { fn fill(buf: *mut u8, len: usize) -> usize; }
    let mut buf: Vec<u8> = Vec::with_capacity(1024);
    // SAFETY: fill() ghi vào buf[0..n], n <= capacity
    let n = fill(buf.as_mut_ptr(), buf.capacity());
    assert!(n <= buf.capacity(), "C function wrote too many bytes");
    // SAFETY: Đã xác nhận n <= capacity và fill() đã init buf[0..n]
    buf.set_len(n);
    buf
}

// ❌ BAD: Box::from_raw vi phạm ownership
fn bad_double_free(ptr: *mut i32) {
    let _box1 = unsafe { Box::from_raw(ptr) };
    let _box2 = unsafe { Box::from_raw(ptr) };
    // Cả hai box cùng sở hữu ptr → double free khi drop!
}

// ✅ GOOD: Box::from_raw chỉ gọi một lần, tương ứng với Box::into_raw
fn good_roundtrip() {
    let boxed = Box::new(42i32);
    let raw = Box::into_raw(boxed);
    // ... pass to C, do unsafe operations ...
    let _recovered = unsafe { Box::from_raw(raw) };  // Gọi đúng một lần
    // _recovered drop → free memory đúng một lần
}
```

### 7. Phòng ngừa

```bash
# Miri verify invariants tại runtime
cargo +nightly miri test

# debug_assert để verify invariants trong debug build
# assert! để verify critical invariants trong production

# Clippy
cargo clippy -- \
  -W clippy::unsafe_removed_from_name \
  -W clippy::undocumented_unsafe_blocks

# Pattern: Luôn document safety contract với "# Safety" doc section
# Mọi unsafe fn và unsafe block phải có comment giải thích
# tại sao code đó an toàn và invariants nào được duy trì
```

---

## UF-10: Memory Leak Qua FFI (Memory Leak via FFI)

### 1. Tên

**Memory Leak Qua FFI** (Memory Leak via FFI Ownership Transfer)

### 2. Phân loại

- **Lĩnh vực:** FFI
- **Danh mục con:** Resource Management / Ownership
- **Mã định danh:** UF-10

### 3. Mức nghiêm trọng

🟠 **HIGH** — Memory leak trong long-running process gây OOM crash. FFI tạo ra hai loại leak phổ biến: Rust dùng Box::into_raw để pass sang C nhưng không nhận lại, hoặc C cấp phát memory nhưng Rust không gọi C free function.

### 4. Vấn đề

```
Ownership qua FFI boundary:

  Rust side          │    C side
  ─────────────────────────────────
  Box::into_raw(b)   →  void* ptr
  (Rust không còn    │  C giữ ptr
   sở hữu nữa)       │  nhưng không free!
                     │
  ══ LEAK: Không ai gọi free! ══

  Hoặc ngược lại:
  C: malloc(size)    →  *mut T
  Rust: drop(...)    ×  Rust free! (sai deallocator!)
  C: free(ptr)       →  DOUBLE FREE!
```

### 5. Phát hiện

```bash
# Tìm Box::into_raw mà không có Box::from_raw tương ứng
rg --type rust "Box::into_raw" -n
rg --type rust "Box::from_raw" -n

# Tìm CString::into_raw
rg --type rust "CString::into_raw|into_raw_parts" -n

# Tìm FFI memory allocation
rg --type rust "libc::malloc|libc::free|libc::calloc" -n

# Tìm extern C functions trả về pointer (có thể cần manual free)
rg --type rust "extern.*fn.*\*\s*(mut|const)" -n
```

### 6. Giải pháp

```rust
use std::ffi::{CString, c_char, c_void};

extern "C" {
    fn process_data(data: *mut c_void);
    fn c_get_result() -> *mut c_char;
    fn c_free_result(ptr: *mut c_char);
}

// ❌ BAD: Box::into_raw mà không có cơ chế free
fn bad_pass_to_c(data: Vec<u8>) {
    let boxed = data.into_boxed_slice();
    let ptr = Box::into_raw(boxed) as *mut c_void;
    unsafe { process_data(ptr) };
    // ptr KHÔNG BAO GIỜ được free! Memory leak!
}

// ✅ GOOD: Wrap trong RAII struct để đảm bảo free
struct OwnedByC(*mut c_void, usize);

impl OwnedByC {
    fn new(data: Vec<u8>) -> Self {
        let len = data.len();
        let boxed = data.into_boxed_slice();
        let ptr = Box::into_raw(boxed) as *mut c_void;
        Self(ptr, len)
    }

    fn as_ptr(&self) -> *mut c_void { self.0 }
}

impl Drop for OwnedByC {
    fn drop(&mut self) {
        if !self.0.is_null() {
            // Tái tạo Box để drop đúng cách
            unsafe {
                let _ = Box::from_raw(
                    std::slice::from_raw_parts_mut(self.0 as *mut u8, self.1)
                );
            }
        }
    }
}

fn good_pass_to_c(data: Vec<u8>) {
    let owned = OwnedByC::new(data);
    unsafe { process_data(owned.as_ptr()) };
    // OwnedByC dropped → Box freed
}

// ❌ BAD: C-allocated string bị drop bởi Rust deallocator
fn bad_c_string() -> String {
    let ptr = unsafe { c_get_result() };
    // CString::from_raw sẽ free bằng Rust allocator!
    // Nhưng ptr được allocate bởi C malloc → wrong deallocator → UB!
    let cstring = unsafe { CString::from_raw(ptr) };
    cstring.to_string_lossy().into_owned()
}

// ✅ GOOD: Dùng đúng C free function
fn good_c_string() -> String {
    let ptr = unsafe { c_get_result() };
    if ptr.is_null() {
        return String::new();
    }
    let result = unsafe {
        std::ffi::CStr::from_ptr(ptr)
            .to_string_lossy()
            .into_owned()
    };
    unsafe { c_free_result(ptr) };  // Gọi C free function
    result
}

// ✅ GOOD: RAII wrapper cho C-allocated resources
struct CResult(*mut c_char);

impl CResult {
    fn new() -> Option<Self> {
        let ptr = unsafe { c_get_result() };
        if ptr.is_null() { None } else { Some(CResult(ptr)) }
    }

    fn as_str(&self) -> &str {
        unsafe { std::ffi::CStr::from_ptr(self.0).to_str().unwrap_or("") }
    }
}

impl Drop for CResult {
    fn drop(&mut self) {
        unsafe { c_free_result(self.0) };
    }
}
```

### 7. Phòng ngừa

```bash
# Valgrind để phát hiện memory leak
valgrind --leak-check=full --error-exitcode=1 ./target/debug/my_app

# AddressSanitizer
RUSTFLAGS="-Z sanitizer=address" cargo +nightly test

# Heaptrack (Linux)
heaptrack ./target/debug/my_app

# Quy tắc FFI:
# □ Mỗi Box::into_raw phải có Box::from_raw tương ứng
# □ Mỗi CString::into_raw phải có CString::from_raw
# □ C-allocated memory phải dùng C free function
# □ Dùng RAII wrapper để đảm bảo cleanup
```

---

## UF-11: Thread Safety FFI (Non-thread-safe C Library)

### 1. Tên

**Thread Safety FFI** (Calling Non-thread-safe C Library from Multiple Threads)

### 2. Phân loại

- **Lĩnh vực:** FFI / Concurrency
- **Danh mục con:** Thread Safety / C Interop
- **Mã định danh:** UF-11

### 3. Mức nghiêm trọng

🔴 **CRITICAL** — Nhiều C library không thread-safe (dùng global state, errno, non-reentrant functions). Gọi chúng từ nhiều threads đồng thời gây data race, heap corruption, hoặc crash không xác định.

### 4. Vấn đề

```
Ví dụ: OpenSSL < 1.1.0, libxml2, strtok(), gmtime()

Thread 1:              Thread 2:
  openssl_init()         openssl_init()
       │                      │
       └──── race condition ───┘
              trên global state
              của OpenSSL → crash!

  Rust type system:
    extern "C" fn không thể express "not thread-safe"
    → Compiler cho phép gọi từ bất kỳ thread nào
    → Lập trình viên phải manually enforce

errno:
  Thread 1: read(fd, buf, n)  → sets errno = EAGAIN
  Thread 2: write(fd2, ...)   → overwrites errno!
  Thread 1: check errno       → WRONG errno!
  (Thực tế: errno là thread-local, nhưng không phải mọi C func)
```

### 5. Phát hiện

```bash
# Tìm FFI calls mà không có Mutex/sync wrapper
rg --type rust "extern.*fn" -n -A 20 | rg -v "Mutex|lock|sync"

# Tìm global C library init functions (thường cần protect)
rg --type rust ".*_init\(\)|.*_global_init\(\)" -n

# Tìm errno access
rg --type rust "errno|Error::last_os_error" -n

# Tìm unsafe impl Send/Sync cho FFI types
rg --type rust "unsafe impl Send|unsafe impl Sync" -n
```

### 6. Giải pháp

```rust
use std::sync::{Mutex, OnceLock};
use std::ffi::{c_int, c_char};

// ❌ BAD: Gọi non-thread-safe C lib từ nhiều threads
extern "C" {
    fn libfoo_init() -> c_int;
    fn libfoo_process(data: *const c_char) -> c_int;
    fn libfoo_cleanup();
}

struct BadFooClient;

impl BadFooClient {
    fn new() -> Self {
        unsafe { libfoo_init(); }  // Race nếu gọi đồng thời!
        BadFooClient
    }

    fn process(&self, data: &str) -> i32 {
        let c = std::ffi::CString::new(data).unwrap();
        unsafe { libfoo_process(c.as_ptr()) }  // Data race trên global state!
    }
}

// ✅ GOOD: Serialize access với Mutex
static FOO_MUTEX: OnceLock<Mutex<()>> = OnceLock::new();

fn get_foo_lock() -> &'static Mutex<()> {
    FOO_MUTEX.get_or_init(|| {
        unsafe { libfoo_init(); }  // Init chỉ một lần
        Mutex::new(())
    })
}

pub struct SafeFooClient {
    _private: (),
}

impl SafeFooClient {
    pub fn new() -> Self {
        get_foo_lock();  // Đảm bảo init
        SafeFooClient { _private: () }
    }

    pub fn process(&self, data: &str) -> i32 {
        let c = std::ffi::CString::new(data).unwrap();
        let _guard = get_foo_lock().lock().unwrap();
        // SAFETY: Giữ lock → chỉ một thread gọi libfoo_process tại một thời điểm
        unsafe { libfoo_process(c.as_ptr()) }
    }
}

// ✅ GOOD: Dùng thread_local cho C library với per-thread state
thread_local! {
    static THREAD_CTX: std::cell::RefCell<Option<ThreadContext>> =
        std::cell::RefCell::new(None);
}

struct ThreadContext(*mut c_void);

extern "C" {
    fn libbar_create_context() -> *mut c_void;
    fn libbar_destroy_context(ctx: *mut c_void);
    fn libbar_process(ctx: *mut c_void, data: *const c_char) -> c_int;
}

impl Drop for ThreadContext {
    fn drop(&mut self) {
        if !self.0.is_null() {
            unsafe { libbar_destroy_context(self.0); }
        }
    }
}

pub fn thread_safe_process(data: &str) -> i32 {
    THREAD_CTX.with(|ctx| {
        let mut ctx = ctx.borrow_mut();
        if ctx.is_none() {
            let raw = unsafe { libbar_create_context() };
            *ctx = Some(ThreadContext(raw));
        }
        let c = std::ffi::CString::new(data).unwrap();
        if let Some(ref tc) = *ctx {
            unsafe { libbar_process(tc.0, c.as_ptr()) }
        } else {
            -1
        }
    })
}
```

### 7. Phòng ngừa

```bash
# Kiểm tra documentation của C library:
# □ Thread-safe? Reentrant?
# □ Global initialization cần serialization?
# □ Per-thread context hay global context?

# ThreadSanitizer
RUSTFLAGS="-Z sanitizer=thread" cargo +nightly test

# Tìm C lib thread safety trong docs
# VD: "man strtok_r" vs "man strtok"
# _r suffix thường = reentrant = thread-safe

# Wrapper pattern:
# □ Dùng OnceLock + Mutex để serialize global C state
# □ Dùng thread_local! cho per-thread C context
# □ Document: "SAFETY: requires FOO_MUTEX held"
```

---

## UF-12: Panic Qua FFI Boundary (Panic Across FFI Boundary)

### 1. Tên

**Panic Qua FFI Boundary** (Rust Panic Unwinding Across FFI Boundary = UB)

### 2. Phân loại

- **Lĩnh vực:** FFI
- **Danh mục con:** Exception Safety / Panic
- **Mã định danh:** UF-12

### 3. Mức nghiêm trọng

🔴 **CRITICAL** — Rust panic unwinding qua FFI boundary (vào C code) là UB theo Rust specification. C không hiểu Rust's unwinding ABI — stack frame không được cleaned up đúng cách, C destructor không chạy, chương trình rơi vào trạng thái không xác định.

### 4. Vấn đề

```
C calls Rust callback:
  C frame: foo()
    │
    └── calls Rust: my_callback()
                        │
                    panic!("oops")
                        │
                    Rust unwinds...
                        │
                    Đến C frame foo()
                        │
                    C không biết xử lý Rust unwind!
                        │
                 UB / SIGABRT / Crash

Nguy hiểm đặc biệt khi:
  • Callback được C gọi (signal handler, library callback)
  • Rust library exported với extern "C"
  • Plugin system (C host, Rust plugin)
  • WASM host gọi Rust
```

### 5. Phát hiện

```bash
# Tìm extern "C" functions mà không có catch_unwind
rg --type rust "extern.*\"C\".*fn" -n -A 20 | rg -v "catch_unwind|panic::catch"

# Tìm panic! trong extern "C" functions
rg --type rust "pub extern.*\"C\".*fn" -n -A 30 | rg "panic!|unwrap\(\)|expect\("

# Tìm .unwrap() trong FFI callback
rg --type rust "unsafe extern.*fn" -n -A 10 | rg "unwrap|expect|panic"

# Tìm exported C functions
rg --type rust "#\[no_mangle\]" -n -A 5
```

### 6. Giải pháp

```rust
use std::panic;
use std::ffi::{c_int, c_char, c_void};

// ❌ BAD: Panic trong extern "C" function = UB
#[no_mangle]
pub extern "C" fn bad_callback(data: *const c_char) -> c_int {
    let s = unsafe { std::ffi::CStr::from_ptr(data) };
    let parsed: i32 = s.to_str()
        .unwrap()         // Panic nếu invalid UTF-8 → UB!
        .parse()
        .unwrap();        // Panic nếu parse fail → UB!
    parsed
}

// ❌ BAD: .expect() trong FFI
#[no_mangle]
pub extern "C" fn bad_process(input: *mut c_void) -> c_int {
    let boxed: Box<Vec<u8>> = unsafe {
        Box::from_raw(input as *mut Vec<u8>)
    };
    let result = do_something(&boxed).expect("processing failed");  // Panic → UB!
    result as c_int
}

// ✅ GOOD: catch_unwind để ngăn panic lan qua FFI
#[no_mangle]
pub extern "C" fn safe_callback(data: *const c_char) -> c_int {
    let result = panic::catch_unwind(|| {
        // Tất cả logic trong đây
        let s = unsafe { std::ffi::CStr::from_ptr(data) };
        let parsed: i32 = s.to_str()
            .map_err(|_| -1)?
            .parse()
            .map_err(|_| -1i32)?;
        Ok::<i32, i32>(parsed)
    });

    match result {
        Ok(Ok(val)) => val,
        Ok(Err(e)) => e,
        Err(_panic) => {
            // Panic bị bắt — log và trả về error code
            eprintln!("Rust panic caught at FFI boundary!");
            -2  // Error code đặc biệt cho "internal panic"
        }
    }
}

// ✅ GOOD: Macro để wrap mọi FFI function
macro_rules! ffi_catch {
    ($default:expr, $body:block) => {{
        match std::panic::catch_unwind(|| $body) {
            Ok(val) => val,
            Err(_) => {
                eprintln!("[FFI] Rust panic intercepted");
                $default
            }
        }
    }};
}

#[no_mangle]
pub extern "C" fn safe_process(n: c_int) -> c_int {
    ffi_catch!(-1, {
        // Logic có thể panic nhưng sẽ bị bắt
        let result = risky_operation(n as i32);
        result as c_int
    })
}

fn risky_operation(n: i32) -> i32 {
    // Có thể panic, nhưng macro ffi_catch sẽ bắt
    vec![1, 2, 3][n as usize]  // Có thể panic nếu n >= 3
}

// ✅ GOOD: Abort thay vì unwind cho panic trong FFI (nếu crash là OK)
// Trong Cargo.toml:
// [profile.release]
// panic = "abort"
//
// Hoặc per-function (Rust nightly):
// #[panic_handler] custom implementation

// ✅ GOOD: std::panic::set_hook để log trước khi abort
pub fn install_ffi_panic_hook() {
    panic::set_hook(Box::new(|info| {
        eprintln!("[FFI PANIC] {}", info);
        // Log to file, sentry, etc.
    }));
}
```

### 7. Phòng ngừa

```toml
# Cargo.toml — dùng panic=abort để biến panic thành hard crash
# (an toàn hơn UB, dễ debug hơn undefined behavior)
[profile.release]
panic = "abort"

[profile.dev]
# Giữ "unwind" trong dev để catch_unwind hoạt động trong tests
panic = "unwind"
```

```bash
# Clippy
cargo clippy -- -W clippy::panic_in_result_fn

# Kiểm tra mọi #[no_mangle] extern "C" function có catch_unwind
rg --type rust "#\[no_mangle\]" -n -A 5 | rg -v "catch_unwind"

# Test với panic hook
# □ Mọi extern "C" function phải wrap bằng catch_unwind hoặc
# □ Dùng panic = "abort" trong Cargo.toml cho crate FFI
# □ Document: "This function must not panic" nếu không có catch_unwind
```

---

## Tóm tắt

| Mã    | Tên                        | Mức độ   | Công cụ phát hiện              |
|-------|----------------------------|----------|--------------------------------|
| UF-01 | Undefined Behavior Ẩn      | CRITICAL | Miri, Clippy, Code Review      |
| UF-02 | Null Pointer Từ C FFI      | CRITICAL | Clippy, Code Review, bindgen   |
| UF-03 | Sai ABI Convention         | CRITICAL | Clippy, bindgen, cbindgen      |
| UF-04 | Dangling Pointer FFI       | CRITICAL | Miri, Clippy, Code Review      |
| UF-05 | Transmute Lạm Dụng        | CRITICAL | Clippy, Miri, Code Review      |
| UF-06 | Uninitialized Memory       | CRITICAL | Miri, ASan/MSan                |
| UF-07 | Data Race Trong Unsafe     | CRITICAL | TSan, Miri                     |
| UF-08 | Union Field Sai            | HIGH     | Miri, Code Review              |
| UF-09 | Invariant Vi Phạm          | CRITICAL | Miri, debug_assert             |
| UF-10 | Memory Leak Qua FFI        | HIGH     | Valgrind, ASan, RAII pattern   |
| UF-11 | Thread Safety FFI          | CRITICAL | TSan, Documentation, Mutex     |
| UF-12 | Panic Qua FFI Boundary     | CRITICAL | catch_unwind, panic=abort      |

### Nguyên tắc vàng

1. **Minimize unsafe scope** — unsafe block càng nhỏ càng tốt
2. **Document every unsafe block** — giải thích tại sao code an toàn
3. **Run Miri** — phát hiện UB mà compiler bỏ qua
4. **Use RAII** — đảm bảo cleanup qua Drop
5. **catch_unwind at FFI boundary** — ngăn panic lan qua C
6. **Prefer safe abstractions** — bytemuck, CString binding, NonNull
7. **Code review unsafe code với chuyên gia** — unsafe không bao giờ là self-review

### Lệnh CI nên có

```bash
# Toàn bộ bộ kiểm tra unsafe/FFI
cargo clippy -- \
  -W clippy::undocumented_unsafe_blocks \
  -W clippy::multiple_unsafe_ops_per_block \
  -W clippy::transmute_ptr_to_ref \
  -W clippy::transmute_int_to_bool \
  -W clippy::not_unsafe_ptr_arg_deref \
  -W clippy::temporary_cstring_as_ptr \
  -W clippy::uninit_assumed_init

cargo +nightly miri test

RUSTFLAGS="-Z sanitizer=address" cargo +nightly test --target x86_64-unknown-linux-gnu
RUSTFLAGS="-Z sanitizer=thread"  cargo +nightly test --target x86_64-unknown-linux-gnu
RUSTFLAGS="-Z sanitizer=memory"  cargo +nightly test --target x86_64-unknown-linux-gnu
```
