# Domain 08: Hiệu Năng Và Mở Rộng (Performance & Scalability)

> Rust patterns liên quan đến performance: bounds checking, cache lines, monomorphization, allocation, I/O buffering.

---

## Pattern 01: Bounds Check Overhead

### Tên
Bounds Check Overhead (Chi Phí Kiểm Tra Biên Mảng)

### Phân loại
Performance / Array / Safety

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```rust
// Rust checks bounds on every index access:
fn sum(data: &[u32]) -> u32 {
    let mut total = 0;
    for i in 0..data.len() {
        total += data[i]; // ← bounds check on every iteration
    }
    total
}
// LLVM often eliminates these, but not always
// Especially with complex index expressions
```

### Phát hiện

```bash
rg --type rust "\[.*\]" -n | rg -v "//|let.*=.*\[|pub|fn|use|mod"
rg --type rust "get_unchecked" -n
```

### Giải pháp

❌ **BAD**
```rust
fn process(data: &[u8], indices: &[usize]) -> Vec<u8> {
    indices.iter().map(|&i| data[i]).collect() // bounds check per index
}
```

✅ **GOOD**
```rust
// Option 1: Iterator (no bounds check needed)
fn sum(data: &[u32]) -> u32 {
    data.iter().sum()
}

// Option 2: chunks/windows for batch processing
fn process_pairs(data: &[u32]) -> Vec<u32> {
    data.chunks_exact(2)
        .map(|chunk| chunk[0] + chunk[1]) // compiler knows chunk.len() == 2
        .collect()
}

// Option 3: assert bounds once (LLVM eliminates subsequent checks)
fn process_range(data: &[u8], start: usize, end: usize) -> u8 {
    assert!(end <= data.len());
    let slice = &data[start..end]; // one check here
    slice.iter().sum()              // no more checks
}
```

### Phòng ngừa
- [ ] Prefer iterators over index-based loops
- [ ] Use `chunks_exact`/`windows` for batch access
- [ ] `assert!` bounds once to help LLVM eliminate subsequent checks
- Tool: `cargo bench` + `criterion` for measurement

---

## Pattern 02: False Sharing

### Tên
False Sharing (Chia Sẻ Cache Line Giả)

### Phân loại
Performance / Cache / Multi-thread

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```
Cache line = 64 bytes
Thread A writes to counter_a (byte 0-7)
Thread B writes to counter_b (byte 8-15)
→ SAME cache line! Each write invalidates other CPU's cache
→ Massive slowdown despite no data sharing

┌─────────────────────────── Cache Line 64B ──────────────────┐
│  counter_a (Thread A writes)  │  counter_b (Thread B writes) │
└─────────────────────────────────────────────────────────────┘
        Both threads thrash each other's cache!
```

### Phát hiện

```bash
rg --type rust "AtomicU64|AtomicUsize|AtomicI64" -n
rg --type rust "struct.*\{" -A 10 | rg "Atomic"
rg --type rust "CachePadded|cache_padded|repr.*align" -n
```

### Giải pháp

❌ **BAD**
```rust
struct Counters {
    read_count: AtomicU64,   // Same cache line!
    write_count: AtomicU64,  // Same cache line!
}
```

✅ **GOOD**
```rust
use crossbeam_utils::CachePadded;

struct Counters {
    read_count: CachePadded<AtomicU64>,  // Own cache line
    write_count: CachePadded<AtomicU64>, // Own cache line
}

// Or manual alignment:
#[repr(align(64))]
struct AlignedCounter {
    value: AtomicU64,
}
```

### Phòng ngừa
- [ ] `CachePadded` for frequently written atomics from different threads
- [ ] `#[repr(align(64))]` for manual cache line alignment
- [ ] Profile with `perf stat -e cache-misses`
- Tool: `crossbeam-utils::CachePadded`

---

## Pattern 03: Monomorphization Bloat

### Tên
Monomorphization Bloat (Binary Phình To Do Generics)

### Phân loại
Performance / Compilation / Binary Size

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```rust
fn process<T: Display>(items: &[T]) { /* 100 lines */ }

// Called with 20 types → 20 copies of 100 lines each in binary
process::<String>(&strings);
process::<u32>(&nums);
process::<MyStruct>(&structs);
// ... × 20 = 2000 lines of machine code
// → Large binary, instruction cache pressure
```

### Phát hiện

```bash
rg --type rust "fn\s+\w+<" -n | rg -v "test|spec"
cargo bloat --release -n 30  # Show largest functions
cargo bloat --release --crates  # Show size by crate
```

### Giải pháp

❌ **BAD**
```rust
fn serialize<W: Write>(writer: &mut W, data: &[u8]) {
    // Large function body — duplicated for every W type
    // BufWriter<File>, TcpStream, Vec<u8>, Cursor<&mut [u8]>, ...
}
```

✅ **GOOD**
```rust
// Inner function on dyn Write (one copy in binary)
fn serialize_inner(writer: &mut dyn Write, data: &[u8]) {
    // Large function body — single copy
}

// Thin generic wrapper for type safety
fn serialize<W: Write>(writer: &mut W, data: &[u8]) {
    serialize_inner(writer, data)
}

// Or: #[inline(never)] to prevent inlining of large generics
#[inline(never)]
fn large_generic_fn<T: Display>(item: &T) { /* ... */ }
```

### Phòng ngừa
- [ ] Move large logic into non-generic inner functions
- [ ] `&dyn Trait` for large function bodies
- [ ] `#[inline(never)]` for rarely-called large generics
- Tool: `cargo bloat`, `twiggy` for binary analysis

---

## Pattern 04: Dynamic Dispatch Không Cần Thiết

### Tên
Dynamic Dispatch Không Cần Thiết (Unnecessary vtable Lookup)

### Phân loại
Performance / Dispatch / Overhead

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```rust
fn process(handler: &dyn Handler) {
    for _ in 0..1_000_000 {
        handler.handle(item); // vtable lookup × 1M times
        // ← CPU cannot predict branch target
        // ← Cannot inline
    }
}
// In hot loops, vtable overhead is significant
```

### Phát hiện

```bash
rg --type rust "&dyn\s+\w+" -n
rg --type rust "Box<dyn\s+\w+" -n
rg --type rust "impl\s+\w+" -n  # Compare static vs dynamic dispatch usage
```

### Giải pháp

❌ **BAD** (dyn in hot path)
```rust
fn hot_loop(items: &[&dyn Processor]) {
    for item in items {
        item.process(); // vtable on every iteration
    }
}
```

✅ **GOOD** (static dispatch in hot path)
```rust
fn hot_loop<P: Processor>(items: &[P]) {
    for item in items {
        item.process(); // inlined, no vtable
    }
}

// Or: enum dispatch for known variants
enum AnyProcessor { TypeA(TypeA), TypeB(TypeB) }
impl Processor for AnyProcessor {
    fn process(&self) {
        match self {
            Self::TypeA(p) => p.process(),
            Self::TypeB(p) => p.process(),
        }
    }
}
```

### Phòng ngừa
- [ ] Static dispatch (`impl Trait`) in hot paths
- [ ] `dyn Trait` only for heterogeneous collections or plugin systems
- [ ] Enum dispatch for known variant sets
- Tool: `cargo bench` to measure dispatch overhead

---

## Pattern 05: Buffered I/O Thiếu

### Tên
Buffered I/O Thiếu (Unbuffered File/Network I/O)

### Phân loại
Performance / I/O / Buffering

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```rust
use std::fs::File;
use std::io::Write;

let mut file = File::create("output.txt")?;
for line in data {
    writeln!(file, "{}", line)?; // ← syscall per line!
}
// 1 million lines = 1 million syscalls
// Each syscall: user→kernel→user context switch
```

### Phát hiện

```bash
rg --type rust "File::(create|open)" -n
rg --type rust "BufWriter|BufReader" -n
rg --type rust "TcpStream" -n | rg -v "BufReader|BufWriter"
```

### Giải pháp

❌ **BAD**
```rust
let mut file = File::create("output.txt")?;
for i in 0..1_000_000 {
    writeln!(file, "{}", i)?; // 1M syscalls
}
```

✅ **GOOD**
```rust
use std::io::BufWriter;

let file = File::create("output.txt")?;
let mut writer = BufWriter::new(file); // Default 8KB buffer
for i in 0..1_000_000 {
    writeln!(writer, "{}", i)?; // Buffered — ~125 syscalls for 8KB buffer
}
writer.flush()?; // Don't forget!

// For reading:
let file = File::open("input.txt")?;
let reader = BufReader::new(file);
for line in reader.lines() {
    process(line?);
}
```

### Phòng ngừa
- [ ] ALWAYS wrap `File` in `BufReader`/`BufWriter`
- [ ] `BufWriter` for `TcpStream` writes
- [ ] `flush()` before close or at end
- Tool: `strace` to count syscalls

---

## Pattern 06: Allocator Contention

### Tên
Allocator Contention (Lock Contention Trong Multi-Thread Allocation)

### Phân loại
Performance / Memory / Multi-thread

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```
Default system allocator (glibc malloc): global lock
Many threads allocating simultaneously:

Thread 1 ──malloc──LOCK──wait────────alloc──
Thread 2 ──────────malloc──LOCK──wait──────alloc──
Thread 3 ──────────────────malloc──LOCK──wait──alloc──
                    ↑ All threads contend on same lock
```

### Phát hiện

```bash
rg --type rust "global_allocator|jemalloc|mimalloc|tikv-jemallocator" -n
rg --type rust "Vec::new\(\)|String::new\(\)" -n --glob "*thread*"
```

### Giải pháp

❌ **BAD**
```rust
// Default allocator with many threads doing frequent allocations
// No explicit allocator configured
fn worker(data: Vec<Item>) {
    let results: Vec<_> = data.into_iter().map(process).collect();
}
```

✅ **GOOD**
```rust
// Cargo.toml: tikv-jemallocator = "0.5"
use tikv_jemallocator::Jemalloc;

#[global_allocator]
static GLOBAL: Jemalloc = Jemalloc;

// Or mimalloc:
use mimalloc::MiMalloc;

#[global_allocator]
static GLOBAL: MiMalloc = MiMalloc;

// Reduce allocation in hot paths:
fn worker(data: Vec<Item>) -> Vec<Result> {
    let mut results = Vec::with_capacity(data.len()); // Pre-allocate
    for item in data {
        results.push(process(item));
    }
    results
}
```

### Phòng ngừa
- [ ] Use `jemalloc` or `mimalloc` for multi-threaded apps
- [ ] Pre-allocate with `with_capacity()`
- [ ] Reduce allocations in hot loops
- Tool: `DHAT` (valgrind), `perf stat`

---

## Pattern 07: String Allocation Thừa

### Tên
String Allocation Thừa (Unnecessary String Copies)

### Phân loại
Performance / String / Allocation

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```rust
fn greet(name: &str) -> String {
    format!("Hello, {}!", name) // Allocates new String every call
}

fn build_path(parts: &[&str]) -> String {
    let mut path = String::new();
    for part in parts {
        path = path + "/" + part; // ← New allocation per iteration!
    }
    path
}
```

### Phát hiện

```bash
rg --type rust "format!\(" -n
rg --type rust "\.to_string\(\)|\.to_owned\(\)" -n
rg --type rust "String::from\(" -n
rg --type rust "\+ &|\.push_str" -n
```

### Giải pháp

❌ **BAD**
```rust
let s = "hello".to_string() + " " + "world"; // 2 allocations
let owned = some_str.to_string(); // Unnecessary if only reading
```

✅ **GOOD**
```rust
// Use &str when not owning:
fn process(name: &str) { /* borrow, don't own */ }

// Use write! instead of format! for buffered output:
use std::fmt::Write;
let mut buf = String::with_capacity(256);
write!(buf, "Hello, {}!", name)?;

// Use Cow for maybe-owned:
use std::borrow::Cow;
fn normalize(input: &str) -> Cow<'_, str> {
    if input.contains(' ') {
        Cow::Owned(input.replace(' ', "_"))
    } else {
        Cow::Borrowed(input) // No allocation!
    }
}

// Pre-allocate for concatenation:
fn build_path(parts: &[&str]) -> String {
    let total_len: usize = parts.iter().map(|p| p.len() + 1).sum();
    let mut path = String::with_capacity(total_len);
    for part in parts {
        path.push('/');
        path.push_str(part);
    }
    path
}
```

### Phòng ngừa
- [ ] `&str` for read-only, `String` only when owning
- [ ] `Cow<str>` for conditional allocation
- [ ] `with_capacity()` for known sizes
- Tool: DHAT profiler for allocation tracking

---

## Pattern 08: Iterator Collect Thừa

### Tên
Iterator Collect Thừa (Collecting When Iterating Suffices)

### Phân loại
Performance / Iterator / Allocation

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```rust
let names: Vec<String> = users
    .iter()
    .map(|u| u.name.clone())
    .collect();  // Allocates Vec

let total: u32 = names
    .iter()
    .map(|n| n.len() as u32)
    .sum();
// Two passes + one unnecessary Vec allocation
```

### Phát hiện

```bash
rg --type rust "\.collect::<Vec" -n
rg --type rust "\.collect\(\)" -n
rg --type rust "\.collect::<" -n
```

### Giải pháp

❌ **BAD**
```rust
let filtered: Vec<_> = items.iter().filter(|x| x.active).collect();
let first = filtered.first(); // Collected all just for first!
```

✅ **GOOD**
```rust
// Chain iterators — no intermediate allocation:
let total: u32 = users
    .iter()
    .map(|u| u.name.len() as u32)
    .sum(); // Single pass, zero allocation

// Find first without collecting:
let first = items.iter().find(|x| x.active);

// Only collect when you need the Vec:
let results: Vec<_> = items
    .iter()
    .filter(|x| x.active)
    .map(|x| x.transform())
    .collect(); // OK — need all results
```

### Phòng ngừa
- [ ] Chain iterators instead of collecting intermediate results
- [ ] `find`, `any`, `all`, `sum`, `count` consume without collecting
- [ ] Only `collect()` when you need the resulting collection
- Tool: Clippy `needless_collect` lint

---

## Pattern 09: Zero-Copy Parsing Thiếu

### Tên
Zero-Copy Parsing Thiếu (Copying Data Instead Of Borrowing)

### Phân loại
Performance / Parsing / Allocation

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```rust
#[derive(Deserialize)]
struct Config {
    name: String,     // Owns data — copies from source
    host: String,     // Owns data — copies from source
    path: String,     // Owns data — copies from source
}
// Parsing a 10MB config: allocates ~10MB for String copies
```

### Phát hiện

```bash
rg --type rust "Deserialize" -A 5 | rg "String|Vec<u8>"
rg --type rust "nom|winnow|pest" -n
rg --type rust "Cow<.*str>" -n
```

### Giải pháp

❌ **BAD**
```rust
fn parse_headers(raw: &str) -> Vec<(String, String)> {
    raw.lines()
        .filter_map(|line| line.split_once(':'))
        .map(|(k, v)| (k.to_string(), v.trim().to_string())) // Allocates!
        .collect()
}
```

✅ **GOOD**
```rust
// Zero-copy: borrow from source
fn parse_headers(raw: &str) -> Vec<(&str, &str)> {
    raw.lines()
        .filter_map(|line| line.split_once(':'))
        .map(|(k, v)| (k, v.trim())) // Zero allocation!
        .collect()
}

// Serde zero-copy:
#[derive(Deserialize)]
struct Config<'a> {
    #[serde(borrow)]
    name: &'a str,    // Borrows from source buffer
    #[serde(borrow)]
    host: Cow<'a, str>, // Borrows unless escaping needed
}
```

### Phòng ngừa
- [ ] Borrow from source data (`&str`, `&[u8]`) when possible
- [ ] `serde(borrow)` for zero-copy deserialization
- [ ] `Cow<str>` when borrowing is sometimes possible
- Tool: `criterion` benchmarks comparing allocation counts

---

## Pattern 10: Compile Time Quá Lâu

### Tên
Compile Time Quá Lâu (Excessive Compilation Time From Generics)

### Phân loại
Performance / Compilation / Developer Experience

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```
cargo build: 5 minutes for small project
→ Heavy use of generics → monomorphization explosion
→ Proc macros recompile every time
→ Large dependency tree
→ Single crate with everything
```

### Phát hiện

```bash
cargo build --timings  # HTML report of compile times
cargo bloat --time -j 1  # Time per crate
rg --type rust "#\[derive\(" -c  # Count derive macros
```

### Giải pháp

❌ **BAD**
```toml
# All code in one huge crate
# Heavy proc macros everywhere
# Debug build with full optimization
```

✅ **GOOD**
```toml
# Cargo.toml — optimize deps in dev builds
[profile.dev.package."*"]
opt-level = 2  # Optimize dependencies, not your code

# Split into workspace with multiple crates
[workspace]
members = ["core", "api", "worker", "shared"]

# Use dynamic linking in dev
[profile.dev]
# opt-level = 0  # default, fast compilation
```

```rust
// Reduce generic instantiations:
// Instead of: fn process<T: AsRef<str>>(s: T)
// Use: fn process(s: &str)  // When generic not needed

// Use type erasure for large generic functions:
fn large_fn(writer: &mut dyn Write) { /* single copy */ }
```

### Phòng ngừa
- [ ] Workspace with small, focused crates
- [ ] `cargo build --timings` to find bottlenecks
- [ ] Minimize proc macro usage in hot crates
- Tool: `sccache` for caching, `mold`/`lld` for fast linking

---

## Pattern 11: SIMD Alignment Sai

### Tên
SIMD Alignment Sai (Unaligned SIMD Access)

### Phân loại
Performance / SIMD / Alignment

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```rust
// SIMD operations require aligned data:
// SSE: 16-byte alignment
// AVX: 32-byte alignment
// If data unaligned → fallback to scalar or crash (on some archs)
```

### Phát hiện

```bash
rg --type rust "std::arch|core::arch|simd" -n
rg --type rust "repr.*align|align_to" -n
rg --type rust "_mm256_|_mm_|_mm512_" -n
```

### Giải pháp

❌ **BAD**
```rust
unsafe {
    let ptr = data.as_ptr();
    let simd = _mm256_load_ps(ptr as *const f32); // Requires 32-byte alignment!
    // If data not aligned → SEGFAULT on some CPUs
}
```

✅ **GOOD**
```rust
// Use aligned type:
#[repr(align(32))]
struct AlignedData([f32; 8]);

// Or use unaligned load (slightly slower but safe):
unsafe {
    let simd = _mm256_loadu_ps(ptr as *const f32); // Unaligned OK
}

// Or use portable SIMD (nightly):
#![feature(portable_simd)]
use std::simd::f32x8;
let simd = f32x8::from_slice(&data[..8]);
```

### Phòng ngừa
- [ ] `#[repr(align(N))]` for SIMD data types
- [ ] Use `_loadu_` (unaligned) unless alignment guaranteed
- [ ] Prefer `std::simd` (portable) over arch-specific intrinsics
- Tool: `cargo-asm` to inspect generated assembly

---

## Pattern 12: Branch Prediction Hints

### Tên
Branch Prediction Hints Sai (Incorrect Likely/Unlikely Annotations)

### Phân loại
Performance / CPU / Branch Prediction

### Mức nghiêm trọng
LOW 🟢

### Vấn đề

```rust
// On nightly:
#[cold]
fn error_path() { /* rarely called */ }

// Programmer assumes hot/cold paths incorrectly:
if unlikely(condition) {  // Actually condition is true 90% of time!
    hot_path();           // Misplaced — this IS the hot path
} else {
    cold_path();
}
```

### Phát hiện

```bash
rg --type rust "#\[cold\]|#\[inline\(always\)\]" -n
rg --type rust "likely|unlikely" -n
rg --type rust "core::intrinsics" -n
```

### Giải pháp

❌ **BAD**
```rust
#[inline(always)] // Forces inlining even when harmful (binary bloat)
fn large_function() { /* 200 lines */ }

#[cold]
fn actually_hot_function() { /* called frequently! */ }
```

✅ **GOOD**
```rust
// Let compiler decide for most code
fn normal_function() { /* no annotation needed */ }

// Only annotate when profiling confirms:
#[cold]
#[inline(never)]
fn handle_error(e: &Error) { /* truly rare path */ }

#[inline] // Suggest (not force) inlining for small hot functions
fn is_valid(c: u8) -> bool { c.is_ascii_alphanumeric() }

// Profile-guided optimization (PGO) is better than manual hints:
// RUSTFLAGS="-Cprofile-generate=/tmp/pgo" cargo build --release
// # Run workload
// RUSTFLAGS="-Cprofile-use=/tmp/pgo/merged.profdata" cargo build --release
```

### Phòng ngừa
- [ ] Profile before adding hints
- [ ] `#[cold]` only for truly rare error paths
- [ ] `#[inline(always)]` almost never needed
- Tool: PGO (profile-guided optimization) instead of manual hints
