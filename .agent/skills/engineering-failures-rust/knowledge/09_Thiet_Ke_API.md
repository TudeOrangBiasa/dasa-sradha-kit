# Domain 09: Thiết Kế API Và Crate (API & Crate Design)

> Rust patterns liên quan đến API design: public interface, type safety, builder pattern, semantic versioning.

---

## Pattern 01: Leaking Implementation Details

### Tên
Leaking Implementation Details (Lộ Chi Tiết Triển Khai Qua Public API)

### Phân loại
API Design / Encapsulation / Public

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```rust
// pub fields expose internals:
pub struct Connection {
    pub socket: TcpStream,     // Users can mess with socket directly
    pub buffer: Vec<u8>,       // Internal buffer exposed
    pub state: ConnectionState, // State machine leaked
}
```

### Phát hiện

```bash
rg --type rust "pub struct.*\{" -A 10 | rg "pub\s+\w+:"
rg --type rust "pub use.*::" -n
```

### Giải pháp

❌ **BAD**
```rust
pub struct Cache { pub entries: HashMap<String, Vec<u8>> }
```

✅ **GOOD**
```rust
pub struct Cache {
    entries: HashMap<String, Vec<u8>>, // Private
}

impl Cache {
    pub fn get(&self, key: &str) -> Option<&[u8]> { self.entries.get(key).map(|v| v.as_slice()) }
    pub fn set(&mut self, key: String, value: Vec<u8>) { self.entries.insert(key, value); }
    pub fn len(&self) -> usize { self.entries.len() }
}
```

### Phòng ngừa
- [ ] Private fields by default, expose via methods
- [ ] `#[non_exhaustive]` for enums and structs in public API
- [ ] Re-export only public API items
- Tool: `cargo doc --open` to review public API

---

## Pattern 02: Missing #[non_exhaustive]

### Tên
Missing #[non_exhaustive] (Enum/Struct Không Mở Rộng Được)

### Phân loại
API Design / Versioning / Breaking Change

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```rust
pub enum Error { NotFound, Timeout, InvalidInput }
// Adding new variant = BREAKING CHANGE for downstream match arms
// Users: match err { NotFound => ..., Timeout => ..., InvalidInput => ... }
// New variant added → their match no longer exhaustive → compile error
```

### Phát hiện

```bash
rg --type rust "pub enum" -n | rg -v "non_exhaustive"
rg --type rust "#\[non_exhaustive\]" -n
```

### Giải pháp

❌ **BAD**
```rust
pub enum DatabaseError { ConnectionFailed, QueryFailed, Timeout }
// Adding AuthFailed later breaks downstream code
```

✅ **GOOD**
```rust
#[non_exhaustive]
pub enum DatabaseError { ConnectionFailed, QueryFailed, Timeout }
// Users MUST have a wildcard arm:
// match err { ConnectionFailed => ..., _ => handle_unknown() }
// Adding new variants is non-breaking

#[non_exhaustive]
pub struct Config { pub host: String, pub port: u16 }
// Users can't construct directly: Config { host: ..., port: ... }
// Must use builder or constructor
```

### Phòng ngừa
- [ ] `#[non_exhaustive]` on all public enums
- [ ] `#[non_exhaustive]` on public structs with possible future fields
- [ ] Provides forward compatibility
- Tool: `cargo semver-checks`

---

## Pattern 03: Builder Pattern Thiếu

### Tên
Builder Pattern Thiếu (Complex Struct Without Builder)

### Phân loại
API Design / Construction / Ergonomics

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```rust
pub fn connect(host: &str, port: u16, timeout: Duration,
    max_retries: u32, tls: bool, cert_path: Option<&Path>,
    keep_alive: bool, buffer_size: usize) -> Connection
// 8 parameters — error-prone, hard to read
```

### Phát hiện

```bash
rg --type rust "pub fn.*\(.*,.*,.*,.*,.*\)" -n
rg --type rust "Builder|builder\(\)" -n
```

### Giải pháp

❌ **BAD**
```rust
let conn = connect("db.example.com", 5432, Duration::from_secs(30),
    3, true, Some(Path::new("/certs/ca.pem")), true, 8192);
```

✅ **GOOD**
```rust
let conn = Connection::builder()
    .host("db.example.com")
    .port(5432)
    .timeout(Duration::from_secs(30))
    .max_retries(3)
    .tls(true)
    .cert_path("/certs/ca.pem")
    .build()?;

// Builder with typestate for required fields:
pub struct ConnectionBuilder<H, P> {
    host: H,
    port: P,
    timeout: Duration,
}
// Only build() available when host AND port are set
```

### Phòng ngừa
- [ ] Builder pattern for >3 parameters
- [ ] Typestate builders for compile-time required field checks
- [ ] `derive_builder` crate for auto-generation
- Tool: `derive_builder`, `typed-builder` crates

---

## Pattern 04: Error Type Quá Generic

### Tên
Error Type Quá Generic (Box<dyn Error> In Public API)

### Phân loại
API Design / Error / Type Safety

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```rust
pub fn process(data: &[u8]) -> Result<Output, Box<dyn std::error::Error>>
// Users can't match on specific errors
// Can't distinguish retryable vs fatal
// Forces users to downcast
```

### Phát hiện

```bash
rg --type rust "Box<dyn.*Error>" -n | rg "pub fn"
rg --type rust "anyhow::Error|anyhow::Result" -n | rg "pub fn"
```

### Giải pháp

❌ **BAD**
```rust
pub fn connect(url: &str) -> Result<Connection, Box<dyn Error>> { ... }
pub fn query(sql: &str) -> anyhow::Result<Rows> { ... } // anyhow in public API!
```

✅ **GOOD**
```rust
#[derive(Debug, thiserror::Error)]
pub enum ConnectError {
    #[error("DNS resolution failed: {0}")]
    DnsError(#[from] std::io::Error),
    #[error("TLS handshake failed")]
    TlsError(#[source] native_tls::Error),
    #[error("Authentication failed")]
    AuthError,
}

pub fn connect(url: &str) -> Result<Connection, ConnectError> { ... }
// Users can match: Err(ConnectError::AuthError) => retry_with_new_credentials()
```

### Phòng ngừa
- [ ] `thiserror` for library error types
- [ ] `anyhow` only in application code, never in library public API
- [ ] Specific error enums per operation
- Tool: `thiserror` crate

---

## Pattern 05: Semantic Versioning Vi Phạm

### Tên
Semantic Versioning Vi Phạm (Breaking Change Without Major Bump)

### Phân loại
API Design / Versioning / SemVer

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```
v1.2.0 → v1.3.0 (minor bump)
But: public function signature changed!
→ Downstream crates break on update
→ Trust in versioning lost
```

### Phát hiện

```bash
rg --type rust "pub fn|pub struct|pub enum|pub trait" -n
cargo semver-checks check-release  # Automated SemVer checking
```

### Giải pháp

❌ **BAD**: Breaking changes in minor/patch version
```toml
# v1.2.0: pub fn process(data: &str) -> Result<Output, Error>
# v1.3.0: pub fn process(data: &str, opts: Options) -> Result<Output, Error>
#         ← BREAKING! New required parameter
```

✅ **GOOD**: Follow SemVer strictly
```toml
# Non-breaking addition (minor bump OK):
# v1.2.0: pub fn process(data: &str) -> Result<Output, Error>
# v1.3.0: pub fn process(data: &str) -> Result<Output, Error>  # unchanged
#         pub fn process_with_opts(data: &str, opts: Options) -> Result<Output, Error>  # new

# Breaking change requires major bump:
# v2.0.0: pub fn process(data: &str, opts: Options) -> Result<Output, Error>
```

### Phòng ngừa
- [ ] `cargo semver-checks` in CI
- [ ] `#[non_exhaustive]` for future-proofing
- [ ] New functions instead of changing existing signatures
- Tool: `cargo-semver-checks`

---

## Pattern 06: Accepting Owned When Borrowing Suffices

### Tên
Accepting Owned Types (String/Vec Khi &str/&[T] Đủ)

### Phân loại
API Design / Ergonomics / Ownership

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```rust
pub fn search(query: String) -> Vec<Result>
// Forces caller to allocate String even from &str:
search("hello".to_string()); // Unnecessary allocation
search(my_string); // Moves ownership — caller loses access
```

### Phát hiện

```bash
rg --type rust "pub fn.*\(.*String|pub fn.*Vec<" -n
rg --type rust "pub fn.*\(.*&str|pub fn.*&\[" -n
```

### Giải pháp

❌ **BAD**
```rust
pub fn log(message: String) { println!("{}", message); }
pub fn process(data: Vec<u8>) -> usize { data.len() }
```

✅ **GOOD**
```rust
// Borrow when not owning:
pub fn log(message: &str) { println!("{}", message); }
pub fn process(data: &[u8]) -> usize { data.len() }

// Accept impl AsRef for flexibility:
pub fn read_file(path: impl AsRef<Path>) -> io::Result<Vec<u8>> {
    fs::read(path.as_ref())
}
// Works with: &str, String, &Path, PathBuf, OsStr, etc.

// Accept Into<T> when you need owned:
pub fn set_name(name: impl Into<String>) { self.name = name.into(); }
// Works with: &str (converts), String (no-op move)
```

### Phòng ngừa
- [ ] `&str` over `String`, `&[T]` over `Vec<T>` for read-only
- [ ] `impl AsRef<T>` for path-like parameters
- [ ] `impl Into<T>` when ownership is needed
- Tool: Clippy `needless_pass_by_value`

---

## Pattern 07: Missing Display/Debug Implementations

### Tên
Missing Display/Debug (Public Types Without Display/Debug)

### Phân loại
API Design / Traits / Ergonomics

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```rust
pub struct Config { host: String, port: u16 }
// println!("{:?}", config); → ERROR: Config doesn't implement Debug
// format!("{}", error); → ERROR: doesn't implement Display
// Users can't log, debug, or format your types
```

### Phát hiện

```bash
rg --type rust "pub struct|pub enum" -B 2 | rg -v "Debug|Display|derive"
rg --type rust "#\[derive.*Debug" -n
```

### Giải pháp

❌ **BAD**
```rust
pub struct ServerConfig { pub host: String, pub port: u16 }
// No Debug, Display, Clone, PartialEq
```

✅ **GOOD**
```rust
#[derive(Debug, Clone, PartialEq)]
pub struct ServerConfig { pub host: String, pub port: u16 }

impl fmt::Display for ServerConfig {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}:{}", self.host, self.port)
    }
}
```

### Phòng ngừa
- [ ] `#[derive(Debug)]` on ALL public types
- [ ] `Display` for types users will format/log
- [ ] `Clone`, `PartialEq` where meaningful
- Tool: Clippy `missing_debug_implementations`

---

## Pattern 08: Unsafe In Public API

### Tên
Unsafe In Public API (Exposing Unsafe Functions Unnecessarily)

### Phân loại
API Design / Safety / Unsafe

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```rust
pub unsafe fn parse(data: *const u8, len: usize) -> &str {
    std::str::from_utf8_unchecked(std::slice::from_raw_parts(data, len))
}
// Every caller must uphold safety invariants
// Easy to misuse → undefined behavior
```

### Phát hiện

```bash
rg --type rust "pub unsafe fn" -n
rg --type rust "pub.*unsafe" -n
```

### Giải pháp

❌ **BAD**
```rust
pub unsafe fn get_unchecked(data: &[u8], index: usize) -> u8 {
    *data.get_unchecked(index)
}
```

✅ **GOOD**
```rust
// Safe public API, unsafe contained internally:
pub fn get(data: &[u8], index: usize) -> Option<u8> {
    data.get(index).copied()
}

// If unsafe is needed, document safety invariants:
/// # Safety
/// - `data` must point to `len` valid bytes
/// - `data` must be valid UTF-8
pub unsafe fn from_raw(data: *const u8, len: usize) -> &str {
    std::str::from_utf8_unchecked(std::slice::from_raw_parts(data, len))
}
```

### Phòng ngừa
- [ ] Safe wrappers around unsafe internals
- [ ] `/// # Safety` doc comments for all `pub unsafe fn`
- [ ] Minimize public unsafe surface
- Tool: `cargo clippy`, `cargo miri`

---

## Pattern 09: Inconsistent Naming

### Tên
Inconsistent Naming (API Naming Convention Vi Phạm)

### Phân loại
API Design / Naming / Convention

### Mức nghiêm trọng
LOW 🟢

### Vấn đề

```rust
// Mixed conventions:
pub fn getData() -> Data { ... }      // camelCase — NOT Rust
pub fn to_str(&self) -> &str { ... }  // to_ implies conversion
pub fn as_string(&self) -> String { } // as_ implies cheap borrow but allocates!
pub fn into_vec(self) -> Vec<u8> { }  // Correct: into_ consumes self
```

### Phát hiện

```bash
rg --type rust "pub fn [a-z]+[A-Z]" -n  # camelCase detection
rg --type rust "fn as_\w+.*->.*String|fn as_\w+.*->.*Vec" -n
rg --type rust "fn to_\w+.*\(&self\)" -n
```

### Giải pháp

Rust API naming conventions:
```rust
// as_ — cheap borrow, no allocation
fn as_str(&self) -> &str
fn as_bytes(&self) -> &[u8]

// to_ — expensive conversion, allocates
fn to_string(&self) -> String
fn to_vec(&self) -> Vec<u8>

// into_ — consumes self, may or may not allocate
fn into_inner(self) -> T
fn into_bytes(self) -> Vec<u8>

// is_ — boolean check
fn is_empty(&self) -> bool

// with_ — builder-style
fn with_capacity(cap: usize) -> Self
```

### Phòng ngừa
- [ ] Follow Rust API guidelines: `as_`/`to_`/`into_`/`is_`
- [ ] `snake_case` for functions and variables
- [ ] Read: [Rust API Guidelines](https://rust-lang.github.io/api-guidelines/)
- Tool: Clippy naming lints

---

## Pattern 10: Missing Documentation

### Tên
Missing Documentation (Public API Without Doc Comments)

### Phân loại
API Design / Documentation / Usability

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```rust
pub fn process(data: &[u8], mode: u8) -> Result<Vec<u8>, Error>
// What does mode mean? Valid values?
// What errors can be returned?
// Is the output guaranteed to be valid UTF-8?
// Thread-safe?
```

### Phát hiện

```bash
rg --type rust "pub fn" -n | rg -v "///"
rg --type rust "#!\[warn\(missing_docs\)\]" -n
```

### Giải pháp

❌ **BAD**
```rust
pub fn encode(data: &[u8], level: u32) -> Vec<u8> { ... }
```

✅ **GOOD**
```rust
/// Compresses data using zstd algorithm.
///
/// # Arguments
/// * `data` - Raw bytes to compress
/// * `level` - Compression level (1-22, default 3)
///
/// # Returns
/// Compressed bytes, or error if level is out of range.
///
/// # Examples
/// ```
/// let compressed = encode(b"hello world", 3)?;
/// assert!(compressed.len() < 11);
/// ```
///
/// # Panics
/// Never panics.
pub fn encode(data: &[u8], level: u32) -> Result<Vec<u8>, EncodeError> { ... }
```

### Phòng ngừa
- [ ] `#![warn(missing_docs)]` in `lib.rs`
- [ ] Doc comments with examples (`///`)
- [ ] `# Errors`, `# Panics`, `# Safety` sections
- Tool: `cargo doc --open`, `#![deny(missing_docs)]`
