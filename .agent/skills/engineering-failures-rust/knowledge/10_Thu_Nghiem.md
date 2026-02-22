# Domain 10: Thử Nghiệm Và Fuzzing (Testing & Fuzzing)

> Rust patterns liên quan đến testing: determinism, mocking, property testing, fuzzing, benchmarking, integration isolation.

---

## Pattern 01: Test Không Deterministic

### Tên
Test Không Deterministic (Non-Deterministic Tests)

### Phân loại
Testing / Reliability / Flaky

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```rust
#[test]
fn test_random_behavior() {
    let result = generate_id(); // Uses SystemTime or thread_rng
    assert!(result.len() > 0);  // Passes sometimes, fails sometimes
}

#[test]
fn test_timing() {
    let start = Instant::now();
    do_work();
    assert!(start.elapsed() < Duration::from_millis(100)); // Flaky on CI
}
```

### Phát hiện

```bash
rg --type rust "SystemTime|thread_rng|rand::" -n --glob "*test*"
rg --type rust "elapsed\(\)|sleep\(" -n --glob "*test*"
rg --type rust "#\[ignore\]" -n
```

### Giải pháp

❌ **BAD**
```rust
#[test]
fn test_sort() {
    let mut data: Vec<u32> = (0..100).map(|_| rand::random()).collect();
    data.sort();
    assert!(data.windows(2).all(|w| w[0] <= w[1]));
}
```

✅ **GOOD**
```rust
#[test]
fn test_sort_deterministic() {
    use rand::SeedableRng;
    let mut rng = rand::rngs::StdRng::seed_from_u64(42); // Fixed seed
    let mut data: Vec<u32> = (0..100).map(|_| rng.gen()).collect();
    data.sort();
    assert!(data.windows(2).all(|w| w[0] <= w[1]));
}

// For time-dependent: inject clock
trait Clock { fn now(&self) -> Instant; }
struct TestClock(Instant);
impl Clock for TestClock { fn now(&self) -> Instant { self.0 } }
```

### Phòng ngừa
- [ ] Fixed seeds for random-based tests
- [ ] Inject clock/time dependencies
- [ ] No `sleep()` in tests — use channels/barriers
- Tool: `proptest` with deterministic seeds

---

## Pattern 02: Mock Thiếu Cho Trait

### Tên
Mock Thiếu Cho Trait (No Mock Implementation for Trait)

### Phân loại
Testing / Mocking / Dependency

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```rust
// Struct with direct dependency — untestable
struct OrderService {
    db: PostgresPool, // Concrete type — can't mock
}

impl OrderService {
    fn create_order(&self, item: &str) -> Result<Order, Error> {
        self.db.execute("INSERT INTO orders ...") // Needs real DB in test
    }
}
```

### Phát hiện

```bash
rg --type rust "struct \w+Service" -A 5 | rg -v "dyn |impl |Arc<"
rg --type rust "#\[cfg\(test\)\]" -A 10 | rg "mock|Mock"
rg --type rust "mockall|mock!" -n
```

### Giải pháp

❌ **BAD**
```rust
struct Service { db: PgPool } // Concrete — needs real DB
```

✅ **GOOD**
```rust
// Trait for dependency:
trait OrderRepo: Send + Sync {
    fn insert(&self, order: &NewOrder) -> Result<Order, DbError>;
    fn find(&self, id: i64) -> Result<Option<Order>, DbError>;
}

struct OrderService<R: OrderRepo> { repo: R }

// Mock in tests:
#[cfg(test)]
mod tests {
    use mockall::automock;
    #[automock]
    impl OrderRepo for MockOrderRepo {}

    #[test]
    fn test_create_order() {
        let mut mock = MockOrderRepo::new();
        mock.expect_insert().returning(|_| Ok(Order { id: 1, .. }));
        let svc = OrderService { repo: mock };
        assert!(svc.create_order("item").is_ok());
    }
}
```

### Phòng ngừa
- [ ] Trait boundaries for all external dependencies
- [ ] `mockall` crate for auto-mock generation
- [ ] Generic or `dyn Trait` for service dependencies
- Tool: `mockall`, `mock_it`

---

## Pattern 03: Proptest/Quickcheck Config Sai

### Tên
Property Testing Config Sai (Proptest Misconfigured)

### Phân loại
Testing / Property / Coverage

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```rust
proptest! {
    #[test]
    fn test_parse(s in ".*") { // Too broad — generates garbage
        let _ = parse(&s);    // Never finds edge cases
    }
}
// Default 256 cases too few for complex invariants
```

### Phát hiện

```bash
rg --type rust "proptest!" -A 5 -n
rg --type rust "ProptestConfig|PROPTEST_CASES" -n
rg --type rust "prop_assert|prop_assume" -n
```

### Giải pháp

❌ **BAD**
```rust
proptest! {
    #[test]
    fn test_roundtrip(v in any::<Vec<u8>>()) {
        // Only 256 cases, no shrinking config
    }
}
```

✅ **GOOD**
```rust
proptest! {
    #![proptest_config(ProptestConfig::with_cases(10_000))]

    #[test]
    fn test_roundtrip(v in prop::collection::vec(any::<u8>(), 0..1024)) {
        let encoded = encode(&v);
        let decoded = decode(&encoded).unwrap();
        prop_assert_eq!(v, decoded);
    }

    #[test]
    fn test_parse_valid(s in "[a-zA-Z0-9_]{1,64}") { // Constrained input
        let result = parse(&s);
        prop_assert!(result.is_ok());
    }
}
```

### Phòng ngừa
- [ ] Constrained strategies (not `any::<String>()`)
- [ ] 1000+ cases for complex invariants
- [ ] `PROPTEST_CASES=100000` in CI
- Tool: `proptest`, `quickcheck`

---

## Pattern 04: Fuzzing Coverage Thấp

### Tên
Fuzzing Coverage Thấp (Low Fuzz Coverage)

### Phân loại
Testing / Fuzzing / Security

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```rust
// Only fuzzing happy path:
fuzz_target!(|data: &[u8]| {
    let _ = parse(data); // Ignores result — misses panics in error paths
});
// Unsafe code not fuzzed at all
```

### Phát hiện

```bash
rg --type rust "fuzz_target!" -n
rg --type rust "unsafe" -n --glob "!*test*"
rg "cargo-fuzz|libfuzzer" -n --glob "Cargo.toml"
```

### Giải pháp

❌ **BAD**
```rust
fuzz_target!(|data: &[u8]| { let _ = process(data); });
```

✅ **GOOD**
```rust
// Structured fuzzing with Arbitrary:
#[derive(Arbitrary, Debug)]
struct FuzzInput {
    data: Vec<u8>,
    mode: u8,
    offset: usize,
}

fuzz_target!(|input: FuzzInput| {
    // Fuzz both success and error paths:
    match process(&input.data, input.mode) {
        Ok(result) => {
            // Validate invariants on success:
            assert!(result.len() <= input.data.len() * 2);
        }
        Err(e) => {
            // Error should not panic, should be descriptive:
            let _ = format!("{}", e);
        }
    }
});
```

### Phòng ngừa
- [ ] `cargo-fuzz` for all parsing/deserialization code
- [ ] Structured inputs with `Arbitrary` derive
- [ ] Fuzz unsafe code especially
- Tool: `cargo-fuzz`, `afl.rs`, `honggfuzz-rs`

---

## Pattern 05: Benchmark Không Reliable

### Tên
Benchmark Không Reliable (Unreliable Criterion Benchmarks)

### Phân loại
Testing / Benchmark / Performance

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```rust
#[bench]
fn bench_sort(b: &mut Bencher) {
    let data = vec![3, 1, 2]; // Too small — measures overhead not sort
    b.iter(|| {
        let mut d = data.clone();
        d.sort(); // Compiler may optimize away
    });
}
```

### Phát hiện

```bash
rg --type rust "criterion|#\[bench\]" -n
rg --type rust "black_box" -n
rg --type rust "criterion_group!" -n
```

### Giải pháp

❌ **BAD**
```rust
b.iter(|| sort(&data)); // Result unused — compiler optimizes away
```

✅ **GOOD**
```rust
use criterion::{black_box, criterion_group, Criterion};

fn bench_sort(c: &mut Criterion) {
    let mut group = c.benchmark_group("sort");
    for size in [100, 1_000, 10_000] {
        let data: Vec<u32> = (0..size).rev().collect();
        group.bench_with_input(
            BenchmarkId::from_parameter(size),
            &data,
            |b, data| b.iter(|| {
                let mut d = data.clone();
                d.sort();
                black_box(&d) // Prevent optimization
            }),
        );
    }
    group.finish();
}
criterion_group!(benches, bench_sort);
```

### Phòng ngừa
- [ ] `criterion` crate (not built-in `#[bench]`)
- [ ] `black_box` to prevent dead code elimination
- [ ] Multiple input sizes for scaling analysis
- Tool: `criterion`, `iai` (instruction-count benchmarks)

---

## Pattern 06: Integration Test Isolation

### Tên
Integration Test Không Isolated (Shared State Between Tests)

### Phân loại
Testing / Integration / Isolation

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```rust
// tests/integration.rs
static DB: OnceLock<PgPool> = OnceLock::new();

#[test]
fn test_create_user() {
    let db = DB.get_or_init(|| create_pool());
    db.execute("INSERT INTO users VALUES (1, 'Alice')"); // Pollutes DB
}

#[test]
fn test_list_users() {
    let db = DB.get_or_init(|| create_pool());
    let users = db.query("SELECT * FROM users"); // Sees test_create_user's data!
}
```

### Phát hiện

```bash
rg --type rust "static.*Pool|static.*Connection" -n --glob "tests/*"
rg --type rust "OnceLock|lazy_static|once_cell" -n --glob "tests/*"
rg --type rust "#\[serial\]|serial_test" -n
```

### Giải pháp

❌ **BAD**: Shared mutable state between tests

✅ **GOOD**
```rust
// Per-test database with transaction rollback:
async fn with_test_db<F, Fut>(f: F) where F: FnOnce(PgPool) -> Fut, Fut: Future {
    let pool = create_test_pool().await;
    let mut tx = pool.begin().await.unwrap();
    // Run test in transaction:
    f(pool).await;
    tx.rollback().await.unwrap(); // Always rollback
}

#[tokio::test]
async fn test_create_user() {
    with_test_db(|pool| async move {
        let user = create_user(&pool, "Alice").await.unwrap();
        assert_eq!(user.name, "Alice");
    }).await;
    // Transaction rolled back — no pollution
}
```

### Phòng ngừa
- [ ] Transaction rollback per test
- [ ] `serial_test` crate for non-parallelizable tests
- [ ] Separate test database per CI run
- Tool: `sqlx::test`, `serial_test`

---

## Pattern 07: Test Helper Không Reusable

### Tên
Test Helper Không Reusable (Duplicated Test Setup)

### Phân loại
Testing / DRY / Helpers

### Mức nghiêm trọng
LOW 🟢

### Vấn đề

```rust
#[test]
fn test_order_1() {
    let db = PgPool::connect("postgres://...").await.unwrap();
    let user = User { id: 1, name: "Alice".into(), email: "a@b.com".into() };
    db.execute("INSERT INTO users ...").await.unwrap();
    // ... same setup in every test
}
```

### Phát hiện

```bash
rg --type rust "fn test_" -A 5 --glob "*test*" | rg "PgPool::connect|User \{"
rg --type rust "mod test_helpers|mod fixtures" -n
```

### Giải pháp

❌ **BAD**: Copy-pasted setup in every test

✅ **GOOD**
```rust
// tests/common/mod.rs
pub struct TestContext { pub db: PgPool, pub user: User }

impl TestContext {
    pub async fn new() -> Self {
        let db = PgPool::connect(&test_db_url()).await.unwrap();
        let user = create_test_user(&db).await;
        Self { db, user }
    }
}

pub fn test_user() -> User {
    User { id: 1, name: "Alice".into(), email: "alice@test.com".into() }
}

// In tests:
#[tokio::test]
async fn test_order() {
    let ctx = TestContext::new().await;
    let order = create_order(&ctx.db, ctx.user.id, "item").await.unwrap();
    assert_eq!(order.user_id, ctx.user.id);
}
```

### Phòng ngừa
- [ ] `tests/common/mod.rs` for shared helpers
- [ ] Builder pattern for test fixtures
- [ ] Reusable `TestContext` struct
- Tool: Rust test organization conventions

---

## Pattern 08: #[ignore] Quên Bỏ

### Tên
#[ignore] Quên Bỏ (Forgotten Ignored Tests)

### Phân loại
Testing / Maintenance / Coverage

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```rust
#[test]
#[ignore] // "Will fix later" — 6 months ago
fn test_complex_scenario() {
    // This test was failing, ignored, and forgotten
    // The bug it catches still exists
}
```

### Phát hiện

```bash
rg --type rust "#\[ignore\]" -n
rg --type rust "#\[ignore\]" -B 1 -A 3 -n
```

### Giải pháp

❌ **BAD**
```rust
#[ignore] // No reason, no ticket
fn test_flaky() { }
```

✅ **GOOD**
```rust
#[test]
#[ignore = "Requires external service — run with --ignored in CI nightly"]
fn test_external_api() { }

// CI config:
// Regular: cargo test
// Nightly: cargo test -- --ignored

// Or use feature flags:
#[test]
#[cfg(feature = "integration")]
fn test_with_real_db() { }
```

### Phòng ngừa
- [ ] Always add reason to `#[ignore = "reason"]`
- [ ] CI nightly runs `cargo test -- --ignored`
- [ ] Track ignored tests in issue tracker
- Tool: `cargo test -- --ignored`

---

## Pattern 09: Compile-Time Test Thiếu

### Tên
Compile-Time Test Thiếu (No Compile-Fail Tests)

### Phân loại
Testing / Type Safety / Compile

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```rust
// API claims Send + Sync safety, but no test verifies it
// API claims certain code WON'T compile, but no test verifies it
pub struct MyType { /* should be Send + Sync */ }
```

### Phát hiện

```bash
rg --type rust "trybuild|compile_fail|compile_error" -n
rg --type rust "assert_impl|is_send|is_sync" -n
```

### Giải pháp

❌ **BAD**: No compile-time guarantees tested

✅ **GOOD**
```rust
// Test that types implement expected traits:
#[test]
fn test_send_sync() {
    fn assert_send<T: Send>() {}
    fn assert_sync<T: Sync>() {}
    assert_send::<MyType>();
    assert_sync::<MyType>();
}

// Test that invalid code DOESN'T compile (trybuild):
// tests/ui/invalid.rs:
// use mylib::PrivateField;
// fn main() { let _ = PrivateField { inner: 42 }; } // Should fail

#[test]
fn compile_fail_tests() {
    let t = trybuild::TestCases::new();
    t.compile_fail("tests/ui/*.rs");
}
```

### Phòng ngừa
- [ ] `trybuild` for compile-fail tests
- [ ] Assert `Send`/`Sync` for public types
- [ ] Test trait bounds at compile time
- Tool: `trybuild`, `static_assertions`

---

## Pattern 10: Unsafe Code Không Fuzz

### Tên
Unsafe Code Không Fuzz (Unsafe Code Without Fuzzing)

### Phân loại
Testing / Safety / Unsafe

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```rust
pub unsafe fn decode(ptr: *const u8, len: usize) -> &[u8] {
    std::slice::from_raw_parts(ptr, len)
    // No fuzz testing → buffer overflows, UB undetected
}
// Unit tests only cover happy paths
```

### Phát hiện

```bash
rg --type rust "unsafe fn|unsafe \{" -n --glob "!*test*"
rg --type rust "fuzz_target!" -n
rg --type rust "miri" -n --glob "*.toml"
```

### Giải pháp

❌ **BAD**: Unsafe code with only unit tests

✅ **GOOD**
```rust
// 1. Fuzz the safe wrapper:
fuzz_target!(|data: &[u8]| {
    let _ = safe_decode(data); // Fuzz all possible inputs
});

// 2. Run Miri for UB detection:
// cargo +nightly miri test

// 3. Address sanitizer:
// RUSTFLAGS="-Z sanitizer=address" cargo test

// 4. Safe wrapper that validates:
pub fn safe_decode(data: &[u8]) -> Result<&str, DecodeError> {
    if data.is_empty() { return Err(DecodeError::Empty); }
    std::str::from_utf8(data).map_err(DecodeError::Utf8)
}
```

### Phòng ngừa
- [ ] Fuzz ALL unsafe code paths
- [ ] `cargo miri test` in CI
- [ ] Address/memory sanitizers in CI
- Tool: `cargo-fuzz`, `miri`, `sanitizers`
