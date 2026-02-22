# Domain 11: Triển Khai Và Build (Deployment & Build)

> Rust patterns liên quan đến deployment: debug builds, feature flags, cross-compilation, linking, build scripts, binary size, CI.

---

## Pattern 01: Debug Build Trong Production

### Tên
Debug Build Trong Production (Unoptimized Binary in Production)

### Phân loại
Deployment / Build / Performance

### Mức nghiêm trọng
CRITICAL 🔴

### Vấn đề

```
cargo build        → target/debug/app   (no optimizations, debug symbols, SLOW)
cargo build --release → target/release/app (optimized, fast)

Production running debug build:
- 10-100x slower than release
- Binary 5-10x larger
- Debug assertions enabled
```

### Phát hiện

```bash
rg "cargo build" -n --glob "Dockerfile" | rg -v "\-\-release"
rg "target/debug" -n --glob "Dockerfile"
rg "\[profile\.release\]" -n --glob "Cargo.toml"
```

### Giải pháp

❌ **BAD**
```dockerfile
RUN cargo build
COPY target/debug/app /usr/local/bin/
```

✅ **GOOD**
```dockerfile
FROM rust:1.77 AS builder
WORKDIR /app
COPY . .
RUN cargo build --release

FROM debian:bookworm-slim
COPY --from=builder /app/target/release/app /usr/local/bin/
CMD ["app"]
```

```toml
# Cargo.toml — optimize release profile:
[profile.release]
opt-level = 3
lto = true
codegen-units = 1
strip = true
```

### Phòng ngừa
- [ ] Always `--release` in production builds
- [ ] CI enforces release profile
- [ ] `profile.release` configured in Cargo.toml
- Tool: `cargo build --release`, Docker multi-stage

---

## Pattern 02: Feature Flag Combination Untested

### Tên
Feature Flag Combination Untested (Cargo Feature Matrix)

### Phân loại
Deployment / Features / Testing

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```toml
[features]
default = ["json"]
json = ["serde_json"]
xml = ["quick-xml"]
async = ["tokio"]
# 2^3 = 8 combinations — only "default" tested in CI
```

```rust
#[cfg(feature = "json")]
fn parse_json() { ... }

#[cfg(all(feature = "json", feature = "async"))]
fn parse_json_async() { ... } // Never tested — compile error hidden
```

### Phát hiện

```bash
rg --type toml "\[features\]" -A 10 -n --glob "Cargo.toml"
rg --type rust "#\[cfg\(feature" -n
rg "cargo-hack|feature-powerset" -n --glob "*.yml"
```

### Giải pháp

❌ **BAD**
```yaml
# CI: Only tests default features
- run: cargo test
```

✅ **GOOD**
```yaml
# CI: Test feature powerset
- run: cargo install cargo-hack
- run: cargo hack test --feature-powerset --depth 2

# Or test key combinations:
- run: cargo test --no-default-features
- run: cargo test --all-features
- run: cargo test --features json
- run: cargo test --features "json,async"
```

### Phòng ngừa
- [ ] `cargo-hack` for feature powerset testing
- [ ] Test `--no-default-features` and `--all-features`
- [ ] Document feature combinations in README
- Tool: `cargo-hack`, `cargo-all-features`

---

## Pattern 03: Cross-Compilation Sai Target

### Tên
Cross-Compilation Sai Target (Wrong Target Triple)

### Phân loại
Deployment / Cross-Compile / Architecture

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```bash
# Building on macOS for Linux:
cargo build --release --target x86_64-unknown-linux-gnu
# Error: linking with `cc` failed — no cross-linker installed
# Or: binary runs but segfaults due to glibc mismatch
```

### Phát hiện

```bash
rg "\-\-target" -n --glob "*.yml" --glob "Makefile"
rg "cross" -n --glob "Cargo.toml" --glob "Cross.toml"
rg "x86_64|aarch64|musl|gnu" -n --glob "*.yml"
```

### Giải pháp

❌ **BAD**
```bash
cargo build --target x86_64-unknown-linux-gnu  # No linker configured
```

✅ **GOOD**
```bash
# Use cross for Docker-based cross-compilation:
cargo install cross
cross build --release --target x86_64-unknown-linux-musl

# Or musl for static linking (no glibc dependency):
rustup target add x86_64-unknown-linux-musl
cargo build --release --target x86_64-unknown-linux-musl
```

```toml
# .cargo/config.toml:
[target.x86_64-unknown-linux-musl]
linker = "x86_64-linux-musl-gcc"
```

### Phòng ngừa
- [ ] `cross` tool for cross-compilation
- [ ] `musl` target for static binaries
- [ ] CI builds match deployment target
- Tool: `cross`, `cargo-zigbuild`

---

## Pattern 04: Static vs Dynamic Linking

### Tên
Static vs Dynamic Linking Issues

### Phân loại
Deployment / Linking / Runtime

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```
Binary built on Ubuntu 22.04 (glibc 2.35)
Deployed to Ubuntu 20.04 (glibc 2.31)
→ Runtime error: /lib/x86_64-linux-gnu/libc.so.6: version `GLIBC_2.34' not found
```

### Phát hiện

```bash
rg "musl|static|dynamic" -n --glob "Cargo.toml" --glob ".cargo/config*"
rg "ldd|readelf" -n --glob "Makefile" --glob "*.sh"
```

### Giải pháp

❌ **BAD**: Dynamic linking to system glibc

✅ **GOOD**
```bash
# Static linking with musl:
cargo build --release --target x86_64-unknown-linux-musl
# Result: fully static binary, runs on any Linux

# Verify:
file target/x86_64-unknown-linux-musl/release/app
# → ELF 64-bit LSB executable, statically linked

ldd target/x86_64-unknown-linux-musl/release/app
# → not a dynamic executable
```

```dockerfile
FROM rust:1.77 AS builder
RUN rustup target add x86_64-unknown-linux-musl
COPY . .
RUN cargo build --release --target x86_64-unknown-linux-musl

FROM scratch
COPY --from=builder /app/target/x86_64-unknown-linux-musl/release/app /app
CMD ["/app"]
```

### Phòng ngừa
- [ ] `musl` target for portable binaries
- [ ] `scratch` Docker image for minimal containers
- [ ] Verify with `ldd` before deployment
- Tool: `musl-tools`, `cargo-auditable`

---

## Pattern 05: Strip Symbols Quên

### Tên
Strip Symbols Quên (Debug Symbols in Release Binary)

### Phân loại
Deployment / Binary Size / Security

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```
release binary: 50MB (with debug symbols)
stripped binary: 5MB
Debug symbols expose: function names, file paths, internal structure
```

### Phát hiện

```bash
rg "strip|symbols" -n --glob "Cargo.toml"
rg "\[profile\.release\]" -A 5 -n --glob "Cargo.toml"
```

### Giải pháp

❌ **BAD**
```toml
[profile.release]
# No strip — 50MB binary with symbols
```

✅ **GOOD**
```toml
[profile.release]
strip = true        # Strip symbols
lto = true          # Link-time optimization
codegen-units = 1   # Better optimization (slower compile)
opt-level = "z"     # Optimize for size (or 3 for speed)
panic = "abort"     # Smaller binary (no unwind tables)
```

### Phòng ngừa
- [ ] `strip = true` in release profile
- [ ] Separate debug symbols for crash analysis
- [ ] `panic = "abort"` if unwind not needed
- Tool: `cargo-bloat`, `cargo-size`

---

## Pattern 06: Build Script Side Effects

### Tên
Build Script Side Effects (build.rs Issues)

### Phân loại
Deployment / Build / Reproducibility

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```rust
// build.rs:
fn main() {
    let output = Command::new("git").args(["rev-parse", "HEAD"]).output().unwrap();
    // Fails in Docker (no git), depends on build environment
    // Non-deterministic: different hash each build
    println!("cargo:rustc-env=GIT_HASH={}", String::from_utf8(output.stdout).unwrap());
}
```

### Phát hiện

```bash
rg "build\.rs" -n --glob "Cargo.toml"
rg "Command::new|std::process" -n --glob "build.rs"
rg "cargo:rustc-env|cargo:rerun-if" -n --glob "build.rs"
```

### Giải pháp

❌ **BAD**
```rust
// build.rs: depends on system tools, network, etc.
Command::new("curl").arg("https://api.example.com/version")...
```

✅ **GOOD**
```rust
// build.rs:
fn main() {
    // Only rerun when needed:
    println!("cargo:rerun-if-changed=proto/");
    println!("cargo:rerun-if-env-changed=GIT_HASH");

    // Fallback for missing tools:
    let git_hash = std::env::var("GIT_HASH").unwrap_or_else(|_| {
        Command::new("git").args(["rev-parse", "--short", "HEAD"])
            .output().ok()
            .and_then(|o| String::from_utf8(o.stdout).ok())
            .unwrap_or_else(|| "unknown".to_string())
    });
    println!("cargo:rustc-env=GIT_HASH={}", git_hash.trim());
}
```

### Phòng ngừa
- [ ] `cargo:rerun-if-changed` to limit rebuilds
- [ ] Fallbacks for missing build tools
- [ ] No network calls in build scripts
- Tool: `cargo:rerun-if-changed`, env vars

---

## Pattern 07: Workspace Dependency Conflicts

### Tên
Workspace Dependency Conflicts (Version Mismatch)

### Phân loại
Deployment / Dependencies / Workspace

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```toml
# crate-a/Cargo.toml
serde = "1.0.190"

# crate-b/Cargo.toml
serde = "1.0.195"

# Two different versions compiled — bloated binary, potential conflicts
```

### Phát hiện

```bash
rg "workspace" -n --glob "Cargo.toml"
rg "\[workspace\.dependencies\]" -n --glob "Cargo.toml"
```

### Giải pháp

❌ **BAD**: Each crate specifies its own dependency versions

✅ **GOOD**
```toml
# Root Cargo.toml:
[workspace]
members = ["crate-a", "crate-b"]

[workspace.dependencies]
serde = { version = "1.0", features = ["derive"] }
tokio = { version = "1", features = ["full"] }

# crate-a/Cargo.toml:
[dependencies]
serde = { workspace = true }
tokio = { workspace = true }
```

### Phòng ngừa
- [ ] `[workspace.dependencies]` for shared versions
- [ ] `cargo deny` for duplicate detection
- [ ] Single version per dependency across workspace
- Tool: `cargo-deny`, `cargo-udeps`

---

## Pattern 08: Binary Size Bloat

### Tên
Binary Size Bloat (Unnecessarily Large Binary)

### Phân loại
Deployment / Size / Optimization

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```
Simple HTTP server: 80MB binary
Causes:
- Debug symbols not stripped
- Monomorphization bloat (generics)
- Too many dependencies
- No LTO
```

### Phát hiện

```bash
rg "\[profile\.release\]" -A 10 -n --glob "Cargo.toml"
rg "\[dependencies\]" -A 20 -n --glob "Cargo.toml"
```

### Giải pháp

❌ **BAD**: Default release profile, no size optimization

✅ **GOOD**
```toml
[profile.release]
strip = true
lto = true
codegen-units = 1
opt-level = "z"     # Size optimization
panic = "abort"

[profile.release-small]
inherits = "release"
opt-level = "z"
```

```bash
# Analyze what's taking space:
cargo install cargo-bloat
cargo bloat --release --crates
cargo bloat --release -n 20  # Top 20 functions by size

# Remove unused dependencies:
cargo install cargo-udeps
cargo +nightly udeps
```

### Phòng ngừa
- [ ] `cargo-bloat` to find size culprits
- [ ] `cargo-udeps` to remove unused deps
- [ ] Feature flags to exclude unused functionality
- Tool: `cargo-bloat`, `cargo-udeps`, `cargo-diet`

---

## Pattern 09: CI Cache Invalidation

### Tên
CI Cache Invalidation Sai (Slow CI Builds)

### Phân loại
Deployment / CI / Performance

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```yaml
# GitHub Actions: No caching — full rebuild every time
steps:
  - run: cargo build --release  # 10-30 minutes
  - run: cargo test             # Rebuilds everything again
```

### Phát hiện

```bash
rg "cache|sccache|cargo-cache" -n --glob "*.yml"
rg "target/" -n --glob ".gitignore"
rg "CARGO_HOME|CARGO_TARGET_DIR" -n --glob "*.yml"
```

### Giải pháp

❌ **BAD**: No cache, or cache key too broad

✅ **GOOD**
```yaml
# .github/workflows/ci.yml:
- uses: actions/cache@v4
  with:
    path: |
      ~/.cargo/registry/index/
      ~/.cargo/registry/cache/
      ~/.cargo/git/db/
      target/
    key: ${{ runner.os }}-cargo-${{ hashFiles('**/Cargo.lock') }}
    restore-keys: ${{ runner.os }}-cargo-

# Or use sccache for distributed caching:
- uses: mozilla-actions/sccache-action@v0.0.4
- run: cargo build --release
  env:
    SCCACHE_GHA_ENABLED: "true"
    RUSTC_WRAPPER: "sccache"
```

### Phòng ngừa
- [ ] Cache `~/.cargo` and `target/` directories
- [ ] Hash `Cargo.lock` for cache key
- [ ] `sccache` for shared compile cache
- Tool: `sccache`, `cargo-cache`, GitHub Actions cache
