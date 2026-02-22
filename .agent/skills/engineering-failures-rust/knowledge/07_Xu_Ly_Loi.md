# Domain 07: Xử Lý Lỗi (Error Handling)

> Rust patterns liên quan đến error handling: Result, Option, panic, thiserror, anyhow.

---

## Pattern 01: Unwrap() Trong Production

### Tên
Unwrap() Trong Production (Unwrap in Production Code)

### Phân loại
Error Handling / Panic / Unwrap

### Mức nghiêm trọng
CRITICAL 🔴

### Vấn đề

```
fn get_config() -> Config {
    let content = fs::read_to_string("config.toml").unwrap();
                                                    ^^^^^^^^
    let config: Config = toml::from_str(&content).unwrap();
                                                  ^^^^^^^^
    config
}
// File missing → panic!
// Invalid TOML → panic!
// Production service crashes, no recovery
```

`unwrap()` gọi `panic!()` khi Result là Err hoặc Option là None. Trong production, panic = process crash = downtime.

### Phát hiện

```bash
# Tìm unwrap() calls
rg --type rust "\.unwrap\(\)" -n

# Tìm unwrap() ngoài test files
rg --type rust "\.unwrap\(\)" -n --glob "!*test*" --glob "!*bench*"

# Tìm expect() với message kém
rg --type rust "\.expect\(\"" -n

# Count unwrap per file
rg --type rust "\.unwrap\(\)" -c | sort -t: -k2 -rn
```

### Giải pháp

❌ **BAD**
```rust
fn parse_port(s: &str) -> u16 {
    s.parse().unwrap() // panic nếu s không phải number
}
```

✅ **GOOD**
```rust
fn parse_port(s: &str) -> Result<u16, ParseIntError> {
    s.parse()
}

// Hoặc với context
fn parse_port(s: &str) -> anyhow::Result<u16> {
    s.parse().context(format!("invalid port: {s}"))
}
```

### Phòng ngừa

- [ ] `unwrap()` chỉ trong tests và examples
- [ ] `expect("descriptive message")` nếu panic là intentional
- [ ] `?` operator cho error propagation
- [ ] `unwrap_or()`, `unwrap_or_default()`, `unwrap_or_else()` cho defaults
- Tool: `cargo clippy -W clippy::unwrap_used`

---

## Pattern 02: Error Type Quá Generic

### Tên
Error Type Quá Generic (Box<dyn Error> Everywhere)

### Phân loại
Error Handling / Type / Generic

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```
fn process() -> Result<(), Box<dyn std::error::Error>> {
                         ^^^^^^^^^^^^^^^^^^^^^^^^^^
    // Caller không biết lỗi cụ thể
    // Không thể match on error type
    // Không thể recover từ specific errors
}

match process() {
    Ok(_) => {},
    Err(e) => {
        // e là Box<dyn Error> — chỉ biết .to_string()
        // Không biết: IO error? Parse error? Network error?
        // Không thể: retry nếu network, skip nếu parse
    }
}
```

### Phát hiện

```bash
# Tìm Box<dyn Error> return types
rg --type rust "Box<dyn\s*(std::)?error::Error>" -n

# Tìm Box<dyn Error + Send + Sync>
rg --type rust "Box<dyn.*Error.*Send.*Sync>" -n

# Tìm anyhow::Error (acceptable trong application code)
rg --type rust "anyhow::(Error|Result)" -n

# Tìm thiserror usage (good practice)
rg --type rust "thiserror" -n
```

### Giải pháp

❌ **BAD**: Generic error type
```rust
fn read_config() -> Result<Config, Box<dyn std::error::Error>> {
    let s = fs::read_to_string("config.toml")?;
    let c: Config = toml::from_str(&s)?;
    Ok(c)
}
```

✅ **GOOD**: Custom error type (thiserror cho libraries)
```rust
#[derive(Debug, thiserror::Error)]
pub enum ConfigError {
    #[error("failed to read config file: {0}")]
    Io(#[from] std::io::Error),
    #[error("failed to parse config: {0}")]
    Parse(#[from] toml::de::Error),
    #[error("missing required field: {field}")]
    MissingField { field: String },
}

fn read_config() -> Result<Config, ConfigError> {
    let s = fs::read_to_string("config.toml")?; // Auto-convert to ConfigError::Io
    let c: Config = toml::from_str(&s)?; // Auto-convert to ConfigError::Parse
    Ok(c)
}

// Caller can match on specific errors
match read_config() {
    Err(ConfigError::Io(e)) if e.kind() == ErrorKind::NotFound => {
        Config::default() // Use defaults if file missing
    }
    Err(e) => return Err(e.into()),
    Ok(c) => c,
}
```

✅ **GOOD**: anyhow cho application code
```rust
use anyhow::{Context, Result};

fn read_config() -> Result<Config> {
    let s = fs::read_to_string("config.toml")
        .context("reading config file")?;
    let c: Config = toml::from_str(&s)
        .context("parsing config TOML")?;
    Ok(c)
}
```

### Phòng ngừa

- [ ] Libraries: `thiserror` cho typed errors
- [ ] Applications: `anyhow` cho ergonomic errors
- [ ] NEVER `Box<dyn Error>` — dùng thiserror hoặc anyhow
- [ ] `.context()` cho every `?` operator
- Tool: `cargo clippy`

---

## Pattern 03: ? Operator Che Giấu Context

### Tên
? Operator Che Giấu Context (? Operator Hides Error Context)

### Phân loại
Error Handling / Context / Debugging

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```
fn setup() -> Result<()> {
    let config = fs::read_to_string("config.toml")?;
    let db_url = parse_config(&config)?;
    let pool = create_pool(&db_url)?;
    let schema = load_schema(&pool)?;
    migrate(&pool, &schema)?;
    Ok(())
}

// Error: "connection refused"
// Which step failed? parse_config? create_pool? migrate?
// No context → hard to debug in production
```

### Phát hiện

```bash
# Tìm ? operator without context
rg --type rust "\?\s*;" -n

# Tìm chains of ? without .context()
rg --type rust "\?\s*$" -n

# Tìm proper .context() usage (reference)
rg --type rust "\.context\(" -n

# Tìm .map_err() usage
rg --type rust "\.map_err\(" -n
```

### Giải pháp

❌ **BAD**: Bare ? operator
```rust
fn init() -> anyhow::Result<()> {
    let s = fs::read_to_string(path)?;     // "No such file"
    let c: Config = serde_json::from_str(&s)?; // "expected value"
    let db = connect(&c.db_url)?;           // "connection refused"
    Ok(())
    // Caller gets generic error, no idea which step
}
```

✅ **GOOD**: Context on every ?
```rust
fn init() -> anyhow::Result<()> {
    let s = fs::read_to_string(path)
        .with_context(|| format!("reading config from {}", path.display()))?;
    let c: Config = serde_json::from_str(&s)
        .context("parsing config JSON")?;
    let db = connect(&c.db_url)
        .with_context(|| format!("connecting to database at {}", c.db_url))?;
    Ok(())
    // Error: "connecting to database at postgres://...: connection refused"
}
```

### Phòng ngừa

- [ ] `.context()` hoặc `.with_context()` cho EVERY `?`
- [ ] Context message mô tả WHAT was being done
- [ ] Include relevant values (path, URL, ID)
- [ ] anyhow::Context trait cho Result AND Option
- Tool: Custom clippy lint (community)

---

## Pattern 04: Thiserror vs Anyhow Dùng Sai Chỗ

### Tên
Thiserror vs Anyhow Dùng Sai Chỗ (Wrong Error Crate Choice)

### Phân loại
Error Handling / Crate / Architecture

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```
Library crate dùng anyhow:
  pub fn parse(s: &str) -> anyhow::Result<Ast> { }
  // Caller KHÔNG thể match on error type
  // Callers forced to depend on anyhow
  // Breaking: library error types hidden

Application code dùng thiserror cho mọi thứ:
  #[derive(Error)]
  enum AppError {
      #[error("io: {0}")] Io(#[from] io::Error),
      #[error("db: {0}")] Db(#[from] sqlx::Error),
      #[error("http: {0}")] Http(#[from] reqwest::Error),
      // 20+ variants just wrapping other errors → verbose, no value
  }
```

### Phát hiện

```bash
# Check if library uses anyhow (anti-pattern)
rg "anyhow" -n --glob "Cargo.toml" | grep -v "\[dev-dependencies\]"

# Check if application has excessive thiserror enums
rg --type rust "#\[derive.*Error\]" -A 20 -n | grep "#\[from\]" | wc -l

# Check lib.rs for anyhow in public API
rg --type rust "anyhow" -n --glob "src/lib.rs"
```

### Giải pháp

❌ **BAD**: anyhow in library
```rust
// lib.rs — library crate
pub fn compile(src: &str) -> anyhow::Result<Program> { }
// Callers can't match errors!
```

✅ **GOOD**: thiserror in library, anyhow in application
```rust
// Library:
#[derive(Debug, thiserror::Error)]
pub enum CompileError {
    #[error("syntax error at line {line}: {message}")]
    Syntax { line: usize, message: String },
    #[error("type error: {0}")]
    Type(String),
}

pub fn compile(src: &str) -> Result<Program, CompileError> { }

// Application (main.rs):
use anyhow::{Context, Result};

fn main() -> Result<()> {
    let program = mylib::compile(&src)
        .context("compiling source")?;
    Ok(())
}
```

### Phòng ngừa

- [ ] Library crate → `thiserror` (typed, matchable errors)
- [ ] Application binary → `anyhow` (ergonomic, context-rich)
- [ ] Library pub API: NEVER return `anyhow::Result`
- [ ] Application: use thiserror for domain errors, anyhow for infra

---

## Pattern 05: Panic Trong Library Code

### Tên
Panic Trong Library Code (Panic in Library)

### Phân loại
Error Handling / Panic / Library

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```
// Library code:
pub fn divide(a: f64, b: f64) -> f64 {
    if b == 0.0 {
        panic!("division by zero");  ← Library kills caller's process!
    }
    a / b
}

// Also: assert!, todo!, unimplemented!, unreachable! (in reachable code)
// vec[index] — panics on out of bounds
// HashMap[key] — panics on missing key
```

### Phát hiện

```bash
# Tìm panic! trong library code
rg --type rust "panic!\(|todo!\(|unimplemented!\(|unreachable!\(" -n --glob "src/lib.rs" --glob "src/**/*.rs"

# Tìm assert! ngoài tests
rg --type rust "assert!\(|assert_eq!\(|assert_ne!\(" -n --glob "!*test*"

# Tìm indexing operations (potential panic)
rg --type rust "\[\w+\]" -n --glob "src/**/*.rs"
```

### Giải pháp

❌ **BAD**: Panic in library
```rust
pub fn get_user(users: &[User], index: usize) -> &User {
    &users[index] // panic nếu out of bounds!
}
```

✅ **GOOD**: Return Result hoặc Option
```rust
pub fn get_user(users: &[User], index: usize) -> Option<&User> {
    users.get(index)
}

pub fn divide(a: f64, b: f64) -> Result<f64, MathError> {
    if b == 0.0 {
        return Err(MathError::DivisionByZero);
    }
    Ok(a / b)
}
```

### Phòng ngừa

- [ ] Library code: NEVER panic (return Result/Option)
- [ ] `todo!()` chỉ trong development, NEVER in release
- [ ] `.get()` thay `[]` indexing
- [ ] `assert!` chỉ cho invariants truly unreachable
- Tool: `cargo clippy -W clippy::panic`

---

## Pattern 06: Expect() Message Kém

### Tên
Expect() Message Kém (Poor Expect Messages)

### Phân loại
Error Handling / Panic / Message

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```
let port = env::var("PORT").expect("PORT");
// Panic message: "PORT: NotPresent"
// Không rõ: PORT là gì? Phải làm gì?

let config = fs::read_to_string("config.toml").expect("failed");
// Panic message: "failed: No such file or directory"
// Không rõ: file nào? Path nào?
```

### Phát hiện

```bash
# Tìm expect() với message ngắn (< 20 chars)
rg --type rust '\.expect\("[^"]{1,15}"\)' -n

# Tìm expect() với message không mô tả
rg --type rust '\.expect\("(failed|error|invalid|bad|wrong)' -n

# Tìm expect() calls
rg --type rust "\.expect\(" -n
```

### Giải pháp

❌ **BAD**: Vague expect messages
```rust
let port: u16 = env::var("PORT").expect("PORT").parse().expect("parse");
```

✅ **GOOD**: Descriptive expect messages
```rust
let port: u16 = env::var("PORT")
    .expect("PORT environment variable must be set")
    .parse()
    .expect("PORT must be a valid u16 (1-65535)");
```

✅ **BETTER**: Return Result thay vì expect
```rust
fn get_port() -> anyhow::Result<u16> {
    let port_str = env::var("PORT").context("PORT env var not set")?;
    port_str.parse().context("PORT must be valid u16")
}
```

### Phòng ngừa

- [ ] expect message: giải thích WHY it should exist
- [ ] Include: what to do to fix
- [ ] Prefer `?` + context over expect
- Tool: `cargo clippy -W clippy::expect_used`

---

## Pattern 07: Error Chain Bị Mất

### Tên
Error Chain Bị Mất (Lost Error Chain)

### Phân loại
Error Handling / Chain / Source

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```
fn connect() -> Result<(), AppError> {
    match db::connect() {
        Ok(conn) => Ok(()),
        Err(e) => Err(AppError::DatabaseError(e.to_string())),
                                              ^^^^^^^^^^^^^
        // Original error converted to String → chain lost
        // Cannot: downcast, inspect source, print full chain
    }
}
```

### Phát hiện

```bash
# Tìm .to_string() trong error conversion
rg --type rust "Err\(.*\.to_string\(\)" -n

# Tìm format! trong error creation
rg --type rust "Err\(.*format!\(" -n

# Tìm proper #[source] usage
rg --type rust "#\[source\]|#\[from\]" -n

# Tìm Error::source() implementations
rg --type rust "fn source\(" -n
```

### Giải pháp

❌ **BAD**: Error chain lost
```rust
#[derive(Debug)]
enum AppError {
    Database(String), // String loses original error
}

fn connect() -> Result<(), AppError> {
    db::connect().map_err(|e| AppError::Database(e.to_string()))
}
```

✅ **GOOD**: Preserve error chain
```rust
#[derive(Debug, thiserror::Error)]
enum AppError {
    #[error("database error")]
    Database(#[source] sqlx::Error), // Preserves original error

    #[error("config error")]
    Config(#[from] ConfigError), // Auto-converts AND preserves chain
}

fn connect() -> Result<(), AppError> {
    db::connect().map_err(AppError::Database)?;
    Ok(())
}

// Full error chain accessible:
// "database error"
// Caused by: "connection refused"
// Caused by: "No route to host"
```

### Phòng ngừa

- [ ] NEVER `.to_string()` on errors (loses chain)
- [ ] `#[source]` attribute preserves error chain
- [ ] `#[from]` for auto-conversion + chain
- [ ] Test: verify error chain with `error.source()`

---

## Pattern 08: Result<(), ()> Vô Nghĩa

### Tên
Result<(), ()> Vô Nghĩa (Meaningless Result Type)

### Phân loại
Error Handling / Type / Semantics

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```
fn validate(input: &str) -> Result<(), ()> {
                                     ^^
    // Error is unit () — no information!
    // Caller: match validate(s) {
    //   Err(()) => ??? // What went wrong? No idea
    // }
}
```

### Phát hiện

```bash
# Tìm Result<_, ()>
rg --type rust "Result<.*,\s*\(\)>" -n

# Tìm Result<(), ()>
rg --type rust "Result<\(\),\s*\(\)>" -n

# Tìm Ok(()) vs Err(())
rg --type rust "Err\(\(\)\)" -n
```

### Giải pháp

❌ **BAD**
```rust
fn validate(s: &str) -> Result<(), ()> {
    if s.is_empty() { Err(()) } else { Ok(()) }
}
```

✅ **GOOD**
```rust
fn validate(s: &str) -> Result<(), ValidationError> {
    if s.is_empty() {
        return Err(ValidationError::Empty { field: "input" });
    }
    Ok(())
}

// Hoặc dùng bool nếu không cần error info
fn is_valid(s: &str) -> bool {
    !s.is_empty()
}
```

### Phòng ngừa

- [ ] Error type phải carry information
- [ ] `bool` nếu chỉ cần true/false
- [ ] `Result<T, Error>` với meaningful Error type
- Tool: `cargo clippy -W clippy::result_unit_err`

---

## Pattern 09: Custom Error Không Implement Source

### Tên
Custom Error Không Implement Source (Custom Error Missing Source)

### Phân loại
Error Handling / Trait / Implementation

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```
#[derive(Debug)]
struct MyError {
    message: String,
    cause: Option<Box<dyn std::error::Error>>,
}

impl std::fmt::Display for MyError {
    fn fmt(&self, f: &mut std::fmt::Formatter) -> std::fmt::Result {
        write!(f, "{}", self.message)
    }
}

impl std::error::Error for MyError {}
// source() defaults to None — cause is LOST!
// Error chain reporting tools can't traverse
```

### Phát hiện

```bash
# Tìm custom Error impl without source
rg --type rust "impl.*Error\s+for" -A 5 -n | rg -v "source\("

# Tìm manual Error implementations
rg --type rust "impl\s+(std::)?error::Error\s+for" -n

# Tìm proper source() implementations
rg --type rust "fn source\(&self\)" -n
```

### Giải pháp

❌ **BAD**: Missing source()
```rust
impl std::error::Error for MyError {} // source() returns None
```

✅ **GOOD**: Implement source() or use thiserror
```rust
// Manual:
impl std::error::Error for MyError {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        self.cause.as_deref()
    }
}

// Better: thiserror handles this automatically
#[derive(Debug, thiserror::Error)]
enum MyError {
    #[error("IO failed: {message}")]
    Io { message: String, #[source] cause: std::io::Error },
}
```

### Phòng ngừa

- [ ] Use `thiserror` — implements source() automatically
- [ ] Manual impl: ALWAYS override `source()`
- [ ] Test error chain traversal
- Tool: `thiserror` crate

---

## Pattern 10: Option::unwrap Trên Iterator

### Tên
Option::unwrap Trên Iterator (Unwrap on Iterator Methods)

### Phân loại
Error Handling / Option / Iterator

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```
let first = items.iter().next().unwrap();
// Empty iterator → panic!

let max = items.iter().max().unwrap();
// Empty collection → panic!

let found = items.iter().find(|x| x.id == target_id).unwrap();
// Not found → panic!
```

### Phát hiện

```bash
# Tìm iterator + unwrap chains
rg --type rust "\.(next|last|max|min|find|position)\(\)\.unwrap\(\)" -n

# Tìm first/last element access
rg --type rust "\.(first|last)\(\)\.unwrap\(\)" -n

# Tìm safe alternatives (reference)
rg --type rust "\.(first|last|next)\(\)\?" -n
```

### Giải pháp

❌ **BAD**
```rust
let first = items.first().unwrap();
let found = items.iter().find(|x| x.active).unwrap();
```

✅ **GOOD**
```rust
let first = items.first().ok_or(Error::EmptyCollection)?;
let found = items.iter().find(|x| x.active)
    .ok_or_else(|| Error::NotFound { criteria: "active" })?;

// Hoặc với default
let first = items.first().unwrap_or(&default_item);
let found = items.iter().find(|x| x.active).copied().unwrap_or_default();
```

### Phòng ngừa

- [ ] `.ok_or()` / `.ok_or_else()` để convert Option → Result
- [ ] `.unwrap_or()` / `.unwrap_or_default()` cho safe defaults
- [ ] NEVER unwrap iterator results
- Tool: `cargo clippy -W clippy::unwrap_used`

---

## Pattern 11: Panic Hook Không Set

### Tên
Panic Hook Không Set (Missing Panic Hook)

### Phân loại
Error Handling / Panic / Recovery

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```
fn main() {
    // No panic hook set
    start_server();
}

// Thread panics → default output to stderr
// No structured logging
// No error reporting (Sentry, etc.)
// No cleanup actions
// Stack trace format: unhelpful in production
```

### Phát hiện

```bash
# Tìm panic hook setup
rg --type rust "set_hook|panic::set_hook|std::panic::set_hook" -n

# Tìm color-eyre / human-panic setup
rg --type rust "color_eyre|human_panic|better_panic" -n

# Check main.rs for panic handling
rg --type rust "set_hook" --glob "src/main.rs" -n
```

### Giải pháp

❌ **BAD**: No panic hook
```rust
fn main() {
    // Default panic output — not structured, no reporting
    run_app();
}
```

✅ **GOOD**: Custom panic hook
```rust
fn main() -> anyhow::Result<()> {
    // Setup structured panic reporting
    std::panic::set_hook(Box::new(|info| {
        let payload = info.payload();
        let message = if let Some(s) = payload.downcast_ref::<&str>() {
            s.to_string()
        } else if let Some(s) = payload.downcast_ref::<String>() {
            s.clone()
        } else {
            "unknown panic".to_string()
        };

        let location = info.location()
            .map(|l| format!("{}:{}:{}", l.file(), l.line(), l.column()))
            .unwrap_or_default();

        tracing::error!(
            panic.message = %message,
            panic.location = %location,
            "PANIC occurred"
        );
    }));

    run_app()
}
```

✅ **GOOD**: color-eyre for better error reports
```rust
fn main() -> color_eyre::Result<()> {
    color_eyre::install()?; // Beautiful panic + error reports
    run_app()
}
```

### Phòng ngừa

- [ ] Set panic hook in main()
- [ ] Structured logging for panics
- [ ] `color-eyre` hoặc `human-panic` cho user-facing apps
- [ ] Report panics to error tracking (Sentry)

---

## Pattern 12: Infallible Error Type

### Tên
Infallible Error Type (Error Type Cho Function Không Fail)

### Phân loại
Error Handling / Type / Design

### Mức nghiêm trọng
LOW 🟢

### Vấn đề

```
fn format_name(first: &str, last: &str) -> Result<String, MyError> {
    Ok(format!("{} {}", first, last))
    // Function NEVER fails → Result misleading
    // Caller phải handle Err case that can't happen
}

impl TryFrom<i32> for Positive {
    type Error = NeverError; // Custom "never" error
    fn try_from(v: i32) -> Result<Self, Self::Error> {
        Ok(Self(v.abs())) // abs() always succeeds → TryFrom wrong choice
    }
}
```

### Phát hiện

```bash
# Tìm Result return type với function that always Ok
rg --type rust "-> Result<" -A 10 -n | rg -v "Err\(|return Err|\?"

# Tìm Infallible type usage
rg --type rust "Infallible|std::convert::Infallible" -n

# Tìm TryFrom implementations that never fail
rg --type rust "impl TryFrom" -A 10 | rg -v "Err"
```

### Giải pháp

❌ **BAD**: Result for infallible operation
```rust
fn uppercase(s: &str) -> Result<String, SomeError> {
    Ok(s.to_uppercase()) // Never fails
}
```

✅ **GOOD**: Direct return for infallible operations
```rust
fn uppercase(s: &str) -> String {
    s.to_uppercase()
}

// Use From instead of TryFrom when infallible
impl From<i32> for Positive {
    fn from(v: i32) -> Self {
        Self(v.abs())
    }
}

// Use std::convert::Infallible when trait requires Error type
impl FromStr for AlwaysValid {
    type Err = std::convert::Infallible;
    fn from_str(s: &str) -> Result<Self, Self::Err> {
        Ok(Self(s.to_string()))
    }
}
```

### Phòng ngừa

- [ ] Result chỉ khi function CAN fail
- [ ] From thay TryFrom khi infallible
- [ ] `std::convert::Infallible` khi trait requires error type
- [ ] Direct return cho pure/infallible functions
