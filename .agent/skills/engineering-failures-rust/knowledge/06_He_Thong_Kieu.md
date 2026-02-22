# Domain 06: Hệ Thống Kiểu (Type System)

> Rust patterns liên quan đến type system: traits, generics, enums, PhantomData, conversions.

---

## Pattern 01: Trait Object Safety Violation

### Tên
Trait Object Safety Violation (Vi Phạm Object Safety Của Trait)

### Phân loại
Type System / Trait / Object Safety

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```
Trait Definition:
  trait MyTrait {
      fn generic_method<T>(&self, val: T);  ← Generic method
      fn returns_self(&self) -> Self;        ← Returns Self
  }
       │
       ▼
  dyn MyTrait  ← COMPILER ERROR!
       │
       ├── "the trait `MyTrait` cannot be made into an object"
       │
       ├── Lý do 1: Generic method → compiler không biết size tại runtime
       │   (vtable không thể chứa infinite monomorphized versions)
       │
       └── Lý do 2: Self return → compiler không biết concrete type
           (dyn MyTrait không biết Self là gì)
```

Khi trait có generic methods hoặc return `Self`, Rust compiler không thể tạo vtable cho dynamic dispatch. Điều này chặn việc dùng `Box<dyn Trait>`, `&dyn Trait`, hoặc `Arc<dyn Trait>`.

Object safety rules:
1. Methods không được có generic type parameters
2. Methods không được return `Self` (trừ khi có `where Self: Sized`)
3. Trait không được có `Self: Sized` bound trên chính trait
4. Methods phải có receiver (`&self`, `&mut self`, `self`, `Box<Self>`, etc.)

### Phát hiện

```bash
# Tìm trait definitions có generic methods
rg --type rust "fn\s+\w+\s*<" -B 5 | rg "trait\s+\w+"

# Tìm methods return Self trong trait
rg --type rust "-> Self" -B 10 | rg -A 10 "trait\s+\w+"

# Tìm attempts dùng dyn với trait
rg --type rust "dyn\s+\w+" -n

# Tìm trait có associated type với Self bound
rg --type rust "type\s+\w+.*=.*Self" -n
```

### Giải pháp

❌ **BAD**: Trait không object-safe
```rust
trait Serializer {
    fn serialize<T: serde::Serialize>(&self, val: &T) -> Vec<u8>;
    fn clone_self(&self) -> Self;
}

// COMPILER ERROR: cannot make into object
fn process(s: &dyn Serializer) { }
```

✅ **GOOD**: Object-safe trait design
```rust
trait Serializer {
    // Dùng trait object thay vì generic
    fn serialize(&self, val: &dyn erased_serde::Serialize) -> Vec<u8>;

    // where Self: Sized exempts from object safety
    fn clone_self(&self) -> Self where Self: Sized;

    // Hoặc return Box<dyn Trait>
    fn clone_boxed(&self) -> Box<dyn Serializer>;
}

// Giờ có thể dùng dynamic dispatch
fn process(s: &dyn Serializer) { }
```

✅ **GOOD**: Dùng associated types thay generic
```rust
trait Handler {
    type Input;
    type Output;
    fn handle(&self, input: Self::Input) -> Self::Output;
}
```

### Phòng ngừa

- [ ] Review trait design trước khi publish
- [ ] Dùng `where Self: Sized` cho methods không cần dynamic dispatch
- [ ] Prefer associated types over generic methods trong trait
- [ ] Test với `Box<dyn Trait>` sớm trong development
- Tool: `cargo clippy` — warns về object safety issues
- Tool: `rust-analyzer` — IDE hiển thị object safety errors

---

## Pattern 02: Orphan Rule Workaround Kém

### Tên
Orphan Rule Workaround Kém (Poor Orphan Rule Workaround)

### Phân loại
Type System / Trait / Coherence

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```
Crate A (external):          Crate B (external):
  struct ForeignType            trait ForeignTrait

Your Crate:
  impl ForeignTrait for ForeignType
       │
       └── COMPILER ERROR: orphan rule!
           "only traits defined in the current crate
            can be implemented for arbitrary types"

Workaround phổ biến (SAI):
  struct Wrapper(ForeignType);
  impl Deref for Wrapper {
      type Target = ForeignType;  ← Deref polymorphism HACK
  }
```

Orphan rule ngăn implement foreign trait cho foreign type. Developer thường dùng newtype wrapper nhưng lạm dụng `Deref` trait để "inherit" methods — đây là anti-pattern vì `Deref` chỉ dành cho smart pointers.

### Phát hiện

```bash
# Tìm newtype wrappers (tuple struct với 1 field)
rg --type rust "struct\s+\w+\(pub\s" -n

# Tìm Deref impl cho non-pointer types
rg --type rust "impl.*Deref\s+for" -n

# Tìm Deref Target assignments
rg --type rust "type Target\s*=" -n

# Tìm pattern: struct wrapper + Deref cùng file
rg --type rust -l "impl.*Deref" | xargs rg "struct\s+\w+\("
```

### Giải pháp

❌ **BAD**: Deref polymorphism cho newtype
```rust
struct MyVec(Vec<String>);

impl std::ops::Deref for MyVec {
    type Target = Vec<String>;
    fn deref(&self) -> &Self::Target { &self.0 }
}
// MyVec auto-inherits Vec methods — confusing API
```

✅ **GOOD**: Explicit delegation
```rust
struct MyVec(Vec<String>);

impl MyVec {
    pub fn push(&mut self, val: String) { self.0.push(val); }
    pub fn len(&self) -> usize { self.0.len() }
    pub fn iter(&self) -> std::slice::Iter<'_, String> { self.0.iter() }
    pub fn as_inner(&self) -> &Vec<String> { &self.0 }
}
```

✅ **GOOD**: Extension trait pattern
```rust
// Thay vì impl ForeignTrait for ForeignType,
// define own trait và impl cho ForeignType
trait MyExtension {
    fn custom_behavior(&self) -> String;
}

impl MyExtension for external_crate::ForeignType {
    fn custom_behavior(&self) -> String {
        format!("extended: {}", self.name())
    }
}
```

### Phòng ngừa

- [ ] Chỉ dùng `Deref` cho smart pointer types
- [ ] Newtype: delegate methods explicitly hoặc dùng `delegate` crate
- [ ] Extension trait pattern khi cần thêm behavior cho foreign type
- [ ] Document lý do dùng newtype wrapper
- Tool: `cargo clippy -W clippy::deref_addrof`

---

## Pattern 03: Enum Exhaustiveness Bỏ Qua

### Tên
Enum Exhaustiveness Bỏ Qua (Enum Exhaustiveness Ignored)

### Phân loại
Type System / Enum / Pattern Matching

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```
enum Status { Active, Inactive, Pending }

match status {
    Status::Active => handle_active(),
    Status::Inactive => handle_inactive(),
    _ => default_handler(),     ← Wildcard catch-all
}
       │
       ▼
  Sau đó thêm variant mới:
  enum Status { Active, Inactive, Pending, Suspended }
       │
       └── _ => default_handler()  ← Suspended rơi vào default
           KHÔNG có compiler warning!
           Bug ẩn: Suspended treated as default
```

Wildcard `_` trong match statement bắt tất cả variants không liệt kê. Khi enum evolve (thêm variant), compiler không warning vì `_` đã cover. Bug chỉ phát hiện ở runtime.

### Phát hiện

```bash
# Tìm wildcard catch-all trong match
rg --type rust "_ =>" -n

# Tìm match statements
rg --type rust "match\s+\w+" -n -A 10

# Tìm #[non_exhaustive] enums
rg --type rust "#\[non_exhaustive\]" -n -A 3

# Tìm enums có nhiều variants
rg --type rust "enum\s+\w+" -n -A 15
```

### Giải pháp

❌ **BAD**: Wildcard catch-all
```rust
enum Command { Start, Stop, Pause, Resume }

fn execute(cmd: Command) {
    match cmd {
        Command::Start => start(),
        Command::Stop => stop(),
        _ => {} // Pause và Resume bị bỏ qua âm thầm
    }
}
```

✅ **GOOD**: Liệt kê tất cả variants
```rust
fn execute(cmd: Command) {
    match cmd {
        Command::Start => start(),
        Command::Stop => stop(),
        Command::Pause => pause(),
        Command::Resume => resume(),
        // Compiler sẽ error khi thêm variant mới
    }
}
```

✅ **GOOD**: Dùng `#[non_exhaustive]` cho public enums
```rust
// Trong library crate
#[non_exhaustive]
pub enum Error {
    NotFound,
    PermissionDenied,
    Timeout,
}
// External crate PHẢI có _ arm → biết rõ có thể thêm variant
```

### Phòng ngừa

- [ ] Tránh `_` trong match enum — liệt kê explicit
- [ ] Dùng `#[non_exhaustive]` cho public enums có thể mở rộng
- [ ] Review match statements khi thêm enum variant
- Tool: `cargo clippy -W clippy::wildcard_enum_match_arm`
- Tool: `cargo clippy -W clippy::match_wildcard_for_single_variants`

---

## Pattern 04: Newtype Pattern Thiếu

### Tên
Newtype Pattern Thiếu (Missing Newtype Pattern)

### Phân loại
Type System / Type Safety / Domain Modeling

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```
fn transfer(from: u64, to: u64, amount: u64) → Result<()>
                │        │         │
                ▼        ▼         ▼
          Cả 3 đều u64 — compiler không phân biệt!

  transfer(amount, user_id, order_id)  ← COMPILES FINE!
           ^^^^^^  ^^^^^^^  ^^^^^^^^
           Đảo thứ tự → bug logic, compiler OK
```

Dùng primitive types cho domain values (UserId, OrderId, Amount) khiến compiler không catch lỗi khi nhầm lẫn arguments. Newtype pattern tạo type-safe wrappers zero-cost.

### Phát hiện

```bash
# Tìm functions có nhiều params cùng type
rg --type rust "fn\s+\w+\(.*:\s*(u32|u64|i32|i64|String|&str).*,.*:\s*(u32|u64|i32|i64|String|&str)" -n

# Tìm type aliases (thường là dấu hiệu cần newtype)
rg --type rust "type\s+\w+\s*=\s*(u32|u64|i32|i64|String)" -n

# Tìm domain concepts dùng primitive
rg --type rust "(user_id|order_id|account_id|amount):\s*(u64|i64|u32|String)" -n
```

### Giải pháp

❌ **BAD**: Primitive obsession
```rust
fn transfer(from: u64, to: u64, amount: u64) -> Result<(), Error> {
    // from, to, amount đều u64 — dễ nhầm
    db.execute("UPDATE accounts SET balance = balance - ? WHERE id = ?",
               amount, from)?;
    Ok(())
}

// Bug: nhầm thứ tự, compiler không catch
transfer(100, 42, 999); // amount=100? from=42?
```

✅ **GOOD**: Newtype wrappers
```rust
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
struct UserId(u64);

#[derive(Debug, Clone, Copy, PartialEq, PartialOrd)]
struct Amount(u64);

impl Amount {
    pub fn new(val: u64) -> Result<Self, Error> {
        if val == 0 { return Err(Error::ZeroAmount); }
        Ok(Self(val))
    }
}

fn transfer(from: UserId, to: UserId, amount: Amount) -> Result<(), Error> {
    // Compiler catches nhầm thứ tự
    // transfer(Amount(100), UserId(42), ...) → COMPILE ERROR
    Ok(())
}
```

### Phòng ngừa

- [ ] Dùng newtype cho domain IDs, amounts, quantities
- [ ] Derive common traits: Debug, Clone, Copy, PartialEq, Hash
- [ ] Add validation trong constructor (`new()`)
- [ ] Zero-cost abstraction — no runtime overhead
- Tool: `derive_more` crate cho auto-derive Display, From, etc.

---

## Pattern 05: Generic Bounds Quá Lỏng

### Tên
Generic Bounds Quá Lỏng (Generic Bounds Too Loose)

### Phân loại
Type System / Generics / Bounds

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```
fn process<T>(item: T) → String
    │
    ▼
  T không có bound nào
    │
    ├── Không thể gọi bất kỳ method nào trên T
    │   (chỉ có thể move, drop)
    │
    ├── Phải thêm bounds sau → BREAKING CHANGE cho callers
    │   process<T: Debug>(item: T)
    │   ↑ Callers passing non-Debug types sẽ break
    │
    └── Hoặc dùng `T: Any` downcast hack
        ↑ Runtime type checking, mất compile-time safety
```

Generic function thiếu trait bounds cần thiết. API ban đầu quá permissive, thêm bounds sau là breaking change nếu đã publish.

### Phát hiện

```bash
# Tìm generic functions không có bounds
rg --type rust "fn\s+\w+<T>\s*\(" -n

# Tìm dùng Any cho type erasure
rg --type rust "T:\s*Any|dyn Any" -n

# Tìm generic functions với where clause
rg --type rust "where\s+T:" -n

# So sánh: generic params vs bounds used
rg --type rust "fn\s+\w+<\w+>" -n -A 5
```

### Giải pháp

❌ **BAD**: No bounds, phải thêm sau
```rust
// v1.0 — quá lỏng
pub fn cache<T>(key: &str, value: T) {
    // Muốn serialize T nhưng không có bound
    // Phải dùng unsafe hoặc Any downcast
}

// v1.1 — thêm bound = BREAKING CHANGE
pub fn cache<T: Serialize>(key: &str, value: T) { }
```

✅ **GOOD**: Correct bounds từ đầu
```rust
pub fn cache<T>(key: &str, value: T)
where
    T: Serialize + DeserializeOwned + Send + 'static
{
    let bytes = serde_json::to_vec(&value).unwrap();
    store.set(key, bytes);
}
```

✅ **GOOD**: Dùng impl Trait cho simplicity
```rust
pub fn process(item: impl Into<Value> + Debug) -> String {
    let val = item.into();
    format!("{:?}", val)
}
```

### Phòng ngừa

- [ ] Define bounds khi tạo generic function, không thêm sau
- [ ] Think: "What operations do I need on T?"
- [ ] Dùng `impl Trait` cho simple cases
- [ ] Sealed trait pattern cho public APIs
- Tool: `cargo semver-checks` — detect breaking changes

---

## Pattern 06: Generic Bounds Quá Chặt

### Tên
Generic Bounds Quá Chặt (Generic Bounds Too Tight)

### Phân loại
Type System / Generics / Bounds

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```
fn simple_log<T>(item: &T)
where T: Clone + Debug + Display + Send + Sync + 'static
         + Hash + Eq + Ord + Serialize + Default
    │
    ▼
  Function body chỉ dùng: println!("{:?}", item)
    │
    └── Chỉ cần T: Debug
        9 bounds thừa → API khó dùng
        Callers phải satisfy ALL bounds dù không cần
```

Quá nhiều trait bounds không cần thiết khiến API restrictive. Callers phải implement tất cả traits dù function chỉ dùng một phần.

### Phát hiện

```bash
# Tìm where clause với nhiều bounds (4+)
rg --type rust "where.*\+.*\+.*\+.*\+" -n

# Tìm bound list dài trên cùng dòng
rg --type rust ":\s*\w+\s*\+\s*\w+\s*\+\s*\w+\s*\+\s*\w+" -n

# Count bounds per function
rg --type rust "where" -A 5 -n
```

### Giải pháp

❌ **BAD**: Excessive bounds
```rust
fn log_item<T>(item: &T)
where T: Clone + Debug + Display + Send + Sync + Hash + Eq + Serialize
{
    println!("{:?}", item); // Chỉ dùng Debug!
}
```

✅ **GOOD**: Minimal bounds
```rust
fn log_item<T: Debug>(item: &T) {
    println!("{:?}", item);
}

// Thêm bounds chỉ khi thực sự dùng
fn store_item<T>(item: T)
where T: Serialize + Send + 'static
{
    let bytes = serde_json::to_vec(&item)?;
    tokio::spawn(async move { cache.set(bytes).await });
}
```

### Phòng ngừa

- [ ] Mỗi bound phải tương ứng với operation trong function body
- [ ] Review: remove bound → compiler error? Nếu không → bound thừa
- [ ] Separate concerns: function nhỏ với bounds riêng
- Tool: `cargo clippy` — warns về unused bounds (nightly)

---

## Pattern 07: PhantomData Hiểu Sai

### Tên
PhantomData Hiểu Sai (PhantomData Misunderstanding)

### Phân loại
Type System / Generics / PhantomData

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```
Struct chứa raw pointer:
  struct MyPtr<T> {
      ptr: *const T,
      // Thiếu PhantomData<T>!
  }
       │
       ▼
  Compiler nghĩ MyPtr KHÔNG own T:
  - Drop check: không gọi drop(T) khi MyPtr drop
  - Variance: T là bivariant (thay vì covariant)
  - Auto traits: MyPtr có thể Send/Sync dù T không
       │
       └── UB khi T bị drop quá sớm hoặc accessed across threads

PhantomData variants:
  PhantomData<T>          → owns T (covariant, drop check)
  PhantomData<*const T>   → covariant, NO drop check
  PhantomData<*mut T>     → invariant, NO drop check
  PhantomData<fn(T)>      → contravariant
  PhantomData<fn() -> T>  → covariant
```

`PhantomData` cần thiết khi struct chứa raw pointer hoặc generic type parameter không dùng trực tiếp. Thiếu hoặc sai variance marker gây undefined behavior.

### Phát hiện

```bash
# Tìm struct chứa raw pointer không có PhantomData
rg --type rust "struct.*\{" -A 10 | rg "\*const|\*mut"
rg --type rust -l "\*const\s+T|\*mut\s+T" | xargs rg -L "PhantomData"

# Tìm PhantomData usage
rg --type rust "PhantomData" -n

# Tìm struct có generic param nhưng không dùng trong fields
rg --type rust "struct\s+\w+<" -A 10 -n
```

### Giải pháp

❌ **BAD**: Raw pointer struct thiếu PhantomData
```rust
struct MyBox<T> {
    ptr: *mut T,
    // Compiler: T is unused → bivariant
    // Drop check: won't consider T
}

unsafe impl<T: Send> Send for MyBox<T> {} // Nhưng T variance sai!
```

✅ **GOOD**: PhantomData với correct variance
```rust
use std::marker::PhantomData;

struct MyBox<T> {
    ptr: *mut T,
    _marker: PhantomData<T>, // Owns T, covariant, drop check active
}

// Cho non-owning reference:
struct MyRef<'a, T> {
    ptr: *const T,
    _marker: PhantomData<&'a T>, // Borrows T, lifetime tracked
}
```

### Phòng ngừa

- [ ] Mọi struct chứa raw pointer PHẢI có PhantomData
- [ ] Chọn đúng variance: own vs borrow vs invariant
- [ ] Test drop ordering với `#[cfg(test)]` drop trackers
- [ ] Document variance choice
- Tool: `cargo miri` — detect UB từ sai variance
- Ref: Rustonomicon — PhantomData chapter

---

## Pattern 08: Turbofish Ambiguity

### Tên
Turbofish Ambiguity (Turbofish Syntax Cần Thiết)

### Phân loại
Type System / Generics / Syntax

### Mức nghiêm trọng
LOW 🟢

### Vấn đề

```
let result = "42".parse();
     │
     ▼
  COMPILER ERROR: "type annotations needed"
  "cannot infer type of the type parameter `F`"
     │
     ├── parse() → Result<F, F::Err> — F unknown
     │
     ├── Fix 1: let result: i32 = "42".parse().unwrap();
     │           ^^^^^ type annotation
     │
     └── Fix 2: let result = "42".parse::<i32>().unwrap();
                                   ^^^^^^^^ turbofish
```

Type inference thất bại khi compiler không có đủ context. Thường xảy ra với `collect()`, `parse()`, `default()`. Turbofish `::<Type>` hoặc type annotation cần thiết.

### Phát hiện

```bash
# Tìm collect() không có type annotation
rg --type rust "\.collect\(\)" -n

# Tìm parse() không có type annotation
rg --type rust "\.parse\(\)" -n

# Tìm turbofish usage
rg --type rust "::<" -n

# Tìm Default::default() không annotated
rg --type rust "Default::default\(\)" -n
```

### Giải pháp

❌ **BAD**: Type inference fails
```rust
let nums = vec![1, 2, 3].iter().map(|x| x * 2).collect();
// ERROR: cannot infer type

let val = "42".parse();
// ERROR: cannot infer type
```

✅ **GOOD**: Type annotation hoặc turbofish
```rust
// Option 1: Type annotation (preferred cho readability)
let nums: Vec<i32> = vec![1, 2, 3].iter().map(|x| x * 2).collect();

// Option 2: Turbofish
let nums = vec![1, 2, 3].iter().map(|x| x * 2).collect::<Vec<i32>>();

// Option 3: Turbofish cho parse
let val = "42".parse::<i32>().unwrap();

// Option 4: Let binding với type
let val: i32 = "42".parse().unwrap();
```

### Phòng ngừa

- [ ] Prefer type annotation over turbofish cho readability
- [ ] Dùng turbofish khi chain methods (no let binding available)
- [ ] IDE / rust-analyzer sẽ suggest type annotations
- Tool: `rust-analyzer` — inlay hints hiển thị inferred types

---

## Pattern 09: Deref Polymorphism Abuse

### Tên
Deref Polymorphism Abuse (Lạm Dụng Deref Cho Kế Thừa)

### Phân loại
Type System / Trait / Deref

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```
struct Animal { name: String }
struct Dog { inner: Animal, breed: String }

impl Deref for Dog {
    type Target = Animal;        ← ANTI-PATTERN!
    fn deref(&self) -> &Animal { &self.inner }
}
       │
       ▼
  dog.name  ← "Works" như OOP inheritance
       │
       ├── Implicit coercion: &Dog → &Animal (confusing)
       ├── Method resolution: Dog methods → Animal methods (unexpected)
       ├── Ownership unclear: ai own Animal?
       └── Deref designed cho smart pointers (Box, Rc, Arc)
           KHÔNG phải cho composition/inheritance
```

`Deref` trait dùng cho smart pointer types (Box, Rc, Arc). Implement cho non-pointer types để "fake" OOP inheritance gây confusion về ownership, implicit conversion, và method resolution.

### Phát hiện

```bash
# Tìm Deref impl cho non-standard types
rg --type rust "impl.*Deref\s+for\s+(?!Box|Rc|Arc|Ref|MutexGuard|RwLock)" -n

# Tìm tất cả Deref implementations
rg --type rust "impl.*Deref\s+for" -n -A 3

# Tìm Target type assignments
rg --type rust "type Target\s*=" -n

# Check: Deref target là domain type (not standard library)
rg --type rust "type Target\s*=\s*(?!str|\\[|\()" -n
```

### Giải pháp

❌ **BAD**: Deref for inheritance
```rust
struct Button { x: i32, y: i32, width: i32, height: i32 }
struct TextButton { button: Button, text: String }

impl Deref for TextButton {
    type Target = Button;
    fn deref(&self) -> &Button { &self.button }
}
// text_btn.x works nhưng là anti-pattern
```

✅ **GOOD**: Explicit composition
```rust
struct TextButton {
    button: Button,
    text: String,
}

impl TextButton {
    pub fn x(&self) -> i32 { self.button.x }
    pub fn y(&self) -> i32 { self.button.y }
    pub fn text(&self) -> &str { &self.text }
    pub fn as_button(&self) -> &Button { &self.button }
}
```

✅ **GOOD**: Trait-based polymorphism
```rust
trait Widget {
    fn position(&self) -> (i32, i32);
    fn size(&self) -> (i32, i32);
    fn draw(&self);
}

impl Widget for Button { /* ... */ }
impl Widget for TextButton { /* ... */ }
```

### Phòng ngừa

- [ ] `Deref` chỉ cho smart pointer types
- [ ] Composition: delegate methods explicitly
- [ ] AsRef/Borrow cho non-owning conversions
- [ ] Trait-based polymorphism cho shared behavior
- Tool: `cargo clippy -W clippy::deref_addrof`

---

## Pattern 10: From/Into Conversion Chain

### Tên
From/Into Conversion Chain Phức Tạp (Complex From/Into Chains)

### Phân loại
Type System / Trait / Conversion

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```
From implementations:
  impl From<A> for B { ... }
  impl From<B> for C { ... }

  let a = A::new();
  let c: C = a.into();  ← COMPILE ERROR!
       │
       ▼
  Rust KHÔNG chain From/Into:
  A → B exists, B → C exists
  BUT A → C does NOT auto-exist!

  Phải:
  let b: B = a.into();
  let c: C = b.into();

  Hoặc: impl From<A> for C explicitly
```

Rust's From/Into traits không transitive. Developer assume rằng `A → B → C` chain tự động hoạt động nhưng thực tế phải implement `From<A> for C` riêng. Quá nhiều From impls cũng gây confusion.

### Phát hiện

```bash
# Tìm tất cả From implementations
rg --type rust "impl\s+From<" -n

# Tìm .into() calls (potential confusion points)
rg --type rust "\.into\(\)" -n

# Tìm From impl chains (A→B, B→C pattern)
rg --type rust "impl\s+From<\w+>\s+for\s+\w+" -n

# Count From impls per type
rg --type rust "impl\s+From<" -n | sort
```

### Giải pháp

❌ **BAD**: Implicit chain assumption
```rust
impl From<String> for UserId { /* ... */ }
impl From<UserId> for DatabaseKey { /* ... */ }

// Developer assumes this works:
let key: DatabaseKey = some_string.into(); // COMPILE ERROR!
// String → UserId → DatabaseKey NOT automatic
```

✅ **GOOD**: Explicit conversions cho clarity
```rust
impl From<String> for UserId {
    fn from(s: String) -> Self { UserId(s.parse().unwrap()) }
}

// Explicit method thay vì From chain
impl DatabaseKey {
    pub fn from_user_id(id: UserId) -> Self { /* ... */ }
    pub fn from_string(s: String) -> Self {
        Self::from_user_id(UserId::from(s))
    }
}
```

✅ **GOOD**: Limit From impls, dùng named methods
```rust
// From chỉ cho "natural" conversions (lossless, obvious)
impl From<u64> for UserId { /* obvious */ }

// Named methods cho conversions cần context
impl UserId {
    pub fn to_database_key(&self) -> DatabaseKey { /* ... */ }
    pub fn parse(s: &str) -> Result<Self, ParseError> { /* ... */ }
}
```

### Phòng ngừa

- [ ] From chỉ cho lossless, obvious conversions
- [ ] TryFrom cho fallible conversions
- [ ] Named methods (`to_xxx`, `as_xxx`) cho domain-specific conversions
- [ ] Document conversion semantics
- [ ] Tránh From chains dài (A→B→C→D)
- Tool: `cargo clippy -W clippy::from_over_into` — prefer From over Into
