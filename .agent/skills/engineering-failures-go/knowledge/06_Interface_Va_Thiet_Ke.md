# Domain 06: Interface Và Thiết Kế (Interface & Design)

> Go patterns liên quan đến interface design, package organization, type system.

---

## Pattern 01: Interface Quá Lớn (Fat Interface)

### Tên
Interface Quá Lớn (Fat Interface)

### Phân loại
Design / Interface / ISP Violation

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```
type Repository interface {
    Create(ctx context.Context, entity Entity) error
    Update(ctx context.Context, id string, entity Entity) error
    Delete(ctx context.Context, id string) error
    FindByID(ctx context.Context, id string) (Entity, error)
    FindAll(ctx context.Context) ([]Entity, error)
    FindByName(ctx context.Context, name string) ([]Entity, error)
    Count(ctx context.Context) (int64, error)
    Exists(ctx context.Context, id string) (bool, error)
    BulkInsert(ctx context.Context, entities []Entity) error
    Search(ctx context.Context, query SearchQuery) ([]Entity, error)
}
       │
       ▼
  10 methods → Vi phạm Interface Segregation Principle
       │
       ├── Mock phức tạp trong tests
       ├── Implementations phải satisfy TẤT CẢ methods
       ├── Callers chỉ cần 1-2 methods nhưng depend whole interface
       └── Khó extend: thêm method = break ALL implementations
```

Go convention: interfaces should be small (1-3 methods). Standard library examples: `io.Reader` (1 method), `io.ReadWriter` (2 methods). Fat interfaces khó implement, mock, và maintain.

### Phát hiện

```bash
# Tìm interface definitions và count methods
rg --type go "type\s+\w+\s+interface" -A 20 -n

# Tìm interfaces có nhiều hơn 5 methods
rg --type go "type\s+\w+\s+interface\s*\{" -l

# Tìm mock files (dấu hiệu interface quá lớn → mock phức tạp)
rg --type go "type\s+Mock\w+\s+struct" -n
```

### Giải pháp

❌ **BAD**: Monolithic interface
```go
type UserService interface {
    Create(ctx context.Context, user User) error
    Update(ctx context.Context, id string, user User) error
    Delete(ctx context.Context, id string) error
    GetByID(ctx context.Context, id string) (User, error)
    List(ctx context.Context) ([]User, error)
    Search(ctx context.Context, q string) ([]User, error)
    SendEmail(ctx context.Context, id string, msg string) error
    ResetPassword(ctx context.Context, id string) error
}
```

✅ **GOOD**: Small, focused interfaces
```go
type UserReader interface {
    GetByID(ctx context.Context, id string) (User, error)
}

type UserWriter interface {
    Create(ctx context.Context, user User) error
    Update(ctx context.Context, id string, user User) error
}

type UserLister interface {
    List(ctx context.Context) ([]User, error)
    Search(ctx context.Context, q string) ([]User, error)
}

// Compose khi cần
type UserReadWriter interface {
    UserReader
    UserWriter
}

// Function chỉ nhận interface cần
func ProcessUser(r UserReader, id string) error {
    user, err := r.GetByID(context.Background(), id)
    // ...
}
```

### Phòng ngừa

- [ ] Interface 1-3 methods là ideal
- [ ] Define interfaces tại consumer, không tại provider
- [ ] Compose small interfaces thay vì monolith
- [ ] "Accept interfaces, return structs"
- Tool: `golangci-lint` với `interfacebloat` linter

---

## Pattern 02: Interface{} / Any Lạm Dụng

### Tên
Interface{} / Any Lạm Dụng (Empty Interface Abuse)

### Phân loại
Type System / Interface / Type Safety

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```
func Process(data interface{}) interface{} {
                    │                │
                    ▼                ▼
              Nhận bất kỳ      Trả bất kỳ
                    │
                    ▼
  caller phải type assert:
    result := Process(myData)
    val, ok := result.(string)  ← Runtime check
         │
         ├── ok = true  → tiếp tục
         └── ok = false → panic hoặc error handling
                          MẤT compile-time safety!
```

`interface{}` (Go 1.18+: `any`) chấp nhận mọi type, nhưng mất compile-time type checking. Phải dùng type assertions ở runtime, dễ panic nếu quên check.

### Phát hiện

```bash
# Tìm interface{} usage
rg --type go "interface\{\}" -n

# Tìm any type usage (Go 1.18+)
rg --type go "\bany\b" -n --word-regexp

# Tìm map[string]interface{}
rg --type go "map\[string\]interface\{\}" -n

# Tìm type assertions (dấu hiệu dùng interface{})
rg --type go "\.\(\w" -n
```

### Giải pháp

❌ **BAD**: interface{} everywhere
```go
func Store(key string, value interface{}) { }
func Load(key string) interface{} { }

// Caller phải cast
val := Load("user")
user, ok := val.(*User) // Runtime check
if !ok {
    // Handle error...
}
```

✅ **GOOD**: Generics (Go 1.18+)
```go
func Store[T any](key string, value T) { }
func Load[T any](key string) (T, error) { }

// Type safe tại compile time
user, err := Load[*User]("user")
// Không cần type assertion!
```

✅ **GOOD**: Concrete types hoặc small interfaces
```go
type Cacheable interface {
    CacheKey() string
    CacheTTL() time.Duration
}

func Store(item Cacheable) error {
    key := item.CacheKey()
    ttl := item.CacheTTL()
    // Type safe, no assertion needed
}
```

### Phòng ngừa

- [ ] Dùng generics (Go 1.18+) thay interface{}
- [ ] Define small interface cho shared behavior
- [ ] Concrete types khi biết exact type
- [ ] Nếu phải dùng interface{}: ALWAYS comma-ok assert
- Tool: `golangci-lint` với `gochecknoglobals`

---

## Pattern 03: Nil Interface Trap

### Tên
Nil Interface Trap (Bẫy Nil Interface)

### Phân loại
Type System / Interface / Nil Semantics

### Mức nghiêm trọng
CRITICAL 🔴

### Vấn đề

```
Interface internal structure:
  ┌──────────────────────┐
  │  interface value      │
  │  ┌─────────┬────────┐│
  │  │  type    │ value  ││
  │  │ pointer  │pointer ││
  │  └─────────┴────────┘│
  └──────────────────────┘

Case 1: nil interface (cả 2 nil)
  var err error = nil
  │  type: nil, value: nil  │
  err == nil  → TRUE ✅

Case 2: interface chứa typed nil (BUG!)
  var p *MyError = nil
  var err error = p
  │  type: *MyError, value: nil  │
  err == nil  → FALSE! ❌

  Vì type pointer ≠ nil → interface ≠ nil
  DÙ value pointer = nil
```

Đây là bug phổ biến nhất liên quan đến Go interfaces. Interface variable `!= nil` khi chứa typed nil pointer, vì interface lưu cả type descriptor và value.

### Phát hiện

```bash
# Tìm function return typed nil pointer qua interface
rg --type go "return\s+\(\*\w+\)\(nil\)" -n

# Tìm pattern: var typed pointer + assign to interface
rg --type go "var\s+\w+\s+\*\w+\s*$" -n -A 3

# Tìm nil check trên interface return values
rg --type go "err\s*!=\s*nil|err\s*==\s*nil" -n

# Tìm functions return (SomeInterface, error) where SomeInterface could be typed nil
rg --type go "func.*\)\s*\(\*?\w+,\s*error\)" -n
```

### Giải pháp

❌ **BAD**: Return typed nil pointer
```go
type MyError struct { Code int }
func (e *MyError) Error() string { return fmt.Sprintf("code: %d", e.Code) }

func validate(s string) error {
    var err *MyError // typed nil pointer
    if len(s) == 0 {
        err = &MyError{Code: 400}
    }
    return err // BUG: khi s != "", returns interface{*MyError, nil}
    // err != nil → TRUE dù không có error!
}
```

✅ **GOOD**: Return nil directly
```go
func validate(s string) error {
    if len(s) == 0 {
        return &MyError{Code: 400}
    }
    return nil // Return nil interface, không typed nil
}
```

✅ **GOOD**: Check typed nil explicitly
```go
func isNil(i interface{}) bool {
    if i == nil {
        return true
    }
    v := reflect.ValueOf(i)
    switch v.Kind() {
    case reflect.Ptr, reflect.Map, reflect.Slice, reflect.Chan, reflect.Func:
        return v.IsNil()
    }
    return false
}
```

### Phòng ngừa

- [ ] NEVER return typed nil pointer qua interface
- [ ] Return `nil` trực tiếp cho "no error" case
- [ ] Review functions return interface types
- [ ] Test nil checks: `assert.Nil(t, err)` (not `assert.Equal(t, nil, err)`)
- Tool: `nilaway` analyzer — static analysis cho nil safety
- Tool: `golangci-lint` với `nilnil` linter

---

## Pattern 04: Accept Interface Return Struct Vi Phạm

### Tên
Accept Interface Return Struct Vi Phạm (AIRT Principle Violation)

### Phân loại
Design / API / Go Idiom

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```
Go principle: "Accept interfaces, return structs"

❌ Ngược lại:
  func NewService(db *PostgresDB) ServiceInterface {
                  ^^^^^^^^^^^^^   ^^^^^^^^^^^^^^^^
                  concrete param  interface return
  }
       │
       ├── Param: concrete → caller phải dùng PostgresDB
       │   Không thể pass MockDB cho testing
       │
       └── Return: interface → caller không biết concrete type
           Mất access đến implementation-specific methods
           Khó debug (interface type trong stack trace)
```

### Phát hiện

```bash
# Tìm functions return interface types
rg --type go "func\s+\w+\(.*\)\s+\w+Interface" -n

# Tìm functions nhận concrete struct
rg --type go "func\s+\w+\(.*\*\w+DB" -n

# Tìm constructor patterns
rg --type go "func New\w+" -n -A 3
```

### Giải pháp

❌ **BAD**: Accept struct, return interface
```go
type Logger interface { Log(msg string) }
type FileLogger struct { path string }

func NewLogger(path string) Logger { // Returns interface
    return &FileLogger{path: path}
}

func Process(logger *FileLogger) { // Accepts concrete
    logger.Log("processing")
}
```

✅ **GOOD**: Accept interface, return struct
```go
type Logger interface { Log(msg string) }
type FileLogger struct { path string }

func NewFileLogger(path string) *FileLogger { // Returns concrete struct
    return &FileLogger{path: path}
}

func Process(logger Logger) { // Accepts interface
    logger.Log("processing")
}

// Testing: pass mock
type MockLogger struct { messages []string }
func (m *MockLogger) Log(msg string) { m.messages = append(m.messages, msg) }

func TestProcess(t *testing.T) {
    mock := &MockLogger{}
    Process(mock) // Works! MockLogger satisfies Logger interface
}
```

### Phòng ngừa

- [ ] Functions nhận interface parameters
- [ ] Constructors return concrete types (*Struct)
- [ ] Define interface tại consumer package
- [ ] Only return interface khi có nhiều implementations (factory)
- Tool: `golangci-lint` với `ireturn` linter

---

## Pattern 05: Package Cycle

### Tên
Package Cycle (Import Cycle Giữa Packages)

### Phân loại
Design / Package / Dependency

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```
package user                package order
  │                            │
  │ import "app/order"         │ import "app/user"
  │      │                     │      │
  └──────┤                     └──────┤
         ▼                            ▼
    COMPILER ERROR: import cycle not allowed

    user → order → user → order → ...
```

Go compiler strictly forbids import cycles. Khi 2 packages cần nhau, phải restructure dependencies.

### Phát hiện

```bash
# Go compiler sẽ báo lỗi trực tiếp
go build ./...
# "import cycle not allowed"

# Visualize dependencies
go list -f '{{join .Imports "\n"}}' ./...

# Tìm potential cycles bằng import analysis
rg --type go "import\s*\(" -A 20 -n | rg "\".*/(user|order|auth)\""
```

### Giải pháp

❌ **BAD**: Direct cycle
```go
// package user
import "app/order"
func GetUserOrders(id string) []order.Order { }

// package order
import "app/user"
func GetOrderUser(id string) user.User { }
```

✅ **GOOD**: Extract shared interface to third package
```go
// package domain (shared types)
type User struct { ID string; Name string }
type Order struct { ID string; UserID string }

// package user
import "app/domain"
func GetUser(id string) domain.User { }

// package order
import "app/domain"
func GetOrdersByUser(userID string) []domain.Order { }
```

✅ **GOOD**: Dependency inversion via interface
```go
// package order
type UserGetter interface {
    GetUser(id string) (User, error) // Define interface tại consumer
}

type Service struct {
    users UserGetter // Inject dependency
}

// package user implements order.UserGetter implicitly
```

### Phòng ngừa

- [ ] Package dependencies: directed acyclic graph (DAG)
- [ ] Shared types: extract to `domain/`, `model/`, hoặc `types/` package
- [ ] Dependency inversion: define interfaces at consumer
- [ ] `internal/` package cho implementation details
- Tool: `go vet` — catches import cycles at build
- Tool: `godepgraph` — visualize dependency graph

---

## Pattern 06: God Package

### Tên
God Package (Package Chứa Mọi Thứ)

### Phân loại
Design / Package / Organization

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```
app/
├── utils/              ← God package!
│   ├── string.go       (string helpers)
│   ├── http.go         (HTTP helpers)
│   ├── database.go     (DB helpers)
│   ├── crypto.go       (crypto helpers)
│   ├── config.go       (config loader)
│   ├── logger.go       (logging)
│   └── errors.go       (error types)
│        │
│        └── 7 files, 0 cohesion
│            Mọi package import utils → high coupling
│            Thay đổi utils = ảnh hưởng tất cả
```

Packages `utils`, `common`, `helpers`, `shared` thường trở thành dumping ground cho code không biết đặt đâu. Vi phạm single responsibility, high coupling.

### Phát hiện

```bash
# Tìm imports từ utils/common/helpers
rg --type go "\".*/(utils|common|helpers|shared|misc)\"" -n

# Count imports của utils package
rg --type go "\".*utils\"" -c

# Tìm utils package definition
rg --type go "package utils|package common|package helpers" -l
```

### Giải pháp

❌ **BAD**: Dumping ground package
```go
package utils

func HashPassword(pwd string) string { }
func FormatDate(t time.Time) string { }
func SendEmail(to, msg string) error { }
func ParseJSON(r io.Reader) (map[string]any, error) { }
```

✅ **GOOD**: Organize by domain/responsibility
```go
app/
├── crypto/
│   └── hash.go         // HashPassword, VerifyPassword
├── email/
│   └── sender.go       // SendEmail, TemplateEmail
├── httputil/
│   └── json.go         // ParseJSON, WriteJSON
└── timeutil/
    └── format.go       // FormatDate, ParseDate
```

### Phòng ngừa

- [ ] Package name = noun mô tả responsibility
- [ ] Không có package `utils`, `common`, `helpers`
- [ ] Mỗi package: single responsibility
- [ ] Nếu package >10 files → split theo sub-domain
- Ref: Standard library style: `net/http`, `encoding/json`, `crypto/sha256`

---

## Pattern 07: Init() Lạm Dụng

### Tên
Init() Lạm Dụng (Init Function Abuse)

### Phân loại
Design / Initialization / Side Effects

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```
package database

func init() {
    db, err := sql.Open("postgres", os.Getenv("DB_URL"))
    if err != nil {
        panic(err)  ← Panic at import time!
    }
    globalDB = db
}
       │
       ▼
  Runs when package imported:
  import "app/database"  ← init() fires immediately
       │
       ├── Side effect: DB connection created
       ├── No error handling: panic kills process
       ├── No control over timing
       ├── No way to pass config/options
       ├── Testing: cannot mock DB
       └── Import order: init() order undefined between packages
```

`init()` chạy tự động khi package được import. Không có control over timing, error handling, hay dependency injection. Dễ gây crash ở import time.

### Phát hiện

```bash
# Tìm tất cả init() functions
rg --type go "func init\(\)" -n

# Tìm init() có side effects (DB, HTTP, file)
rg --type go "func init\(\)" -A 20 | rg "(sql\.Open|http\.(Get|Post)|os\.(Open|Create)|panic)"

# Tìm global variables set trong init()
rg --type go "func init\(\)" -A 10 | rg "\w+\s*="
```

### Giải pháp

❌ **BAD**: init() with side effects
```go
var db *sql.DB
var logger *log.Logger
var config *Config

func init() {
    var err error
    config = loadConfig() // File I/O at import
    db, err = sql.Open("postgres", config.DBURL) // DB connect at import
    if err != nil { panic(err) } // Crash at import
    logger = log.New(os.Stdout, "", log.LstdFlags)
}
```

✅ **GOOD**: Explicit initialization
```go
type App struct {
    DB     *sql.DB
    Logger *log.Logger
    Config *Config
}

func NewApp(cfg *Config) (*App, error) {
    db, err := sql.Open("postgres", cfg.DBURL)
    if err != nil {
        return nil, fmt.Errorf("connecting to database: %w", err)
    }
    return &App{
        DB:     db,
        Logger: log.New(os.Stdout, "", log.LstdFlags),
        Config: cfg,
    }, nil
}
```

### Phòng ngừa

- [ ] init() chỉ cho: register drivers, set constants
- [ ] KHÔNG: I/O, network, panic trong init()
- [ ] Explicit constructors: `NewXxx()` functions
- [ ] Dependency injection thay global state
- Tool: `golangci-lint` với `gochecknoinits` linter

---

## Pattern 08: Exported Nhưng Không Dùng

### Tên
Exported Nhưng Không Dùng (Over-Exported API)

### Phân loại
Design / API / Encapsulation

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```
package user

// ALL exported (uppercase) — public API quá rộng
type UserRepository struct { ... }     ← exported
type UserDTO struct { ... }            ← exported
type UserMapper struct { ... }         ← exported  (internal detail!)
func MapToDTO(u User) UserDTO { ... }  ← exported  (internal detail!)
func ValidateEmail(s string) bool { }  ← exported  (utility!)
       │
       ▼
  External packages depend on ALL exported types
  → Breaking changes khi refactor internal implementation
  → API surface lớn = maintenance burden
```

### Phát hiện

```bash
# Tìm exported functions
rg --type go "^func [A-Z]" -n

# Tìm exported types
rg --type go "^type [A-Z]" -n

# Tìm exported vars/consts
rg --type go "^var [A-Z]|^const [A-Z]" -n

# Check internal/ usage
rg --type go "internal/" -n
```

### Giải pháp

❌ **BAD**: Over-exported
```go
package user

type User struct { ID string; Name string }
type UserRepository struct { db *sql.DB }
type UserMapper struct {}
type UserDTO struct { ID string; Name string; CreatedAt string }

func NewRepository(db *sql.DB) *UserRepository { }
func MapToDTO(u User) UserDTO { }
func ValidateEmail(s string) bool { }
```

✅ **GOOD**: Minimal exports, use internal/
```go
package user

// Only export what consumers need
type User struct { ID string; Name string }
type Repository struct { db *sql.DB }

func NewRepository(db *sql.DB) *Repository { }

// Internal details: unexported
type userDTO struct { id string; name string }
func mapToDTO(u User) userDTO { }
func validateEmail(s string) bool { }
```

### Phòng ngừa

- [ ] Export minimum: types và functions callers need
- [ ] `internal/` package cho implementation details
- [ ] Unexported (lowercase) by default, export khi có use case
- [ ] Review exports khi adding to package
- Tool: `golangci-lint` với `unused` linter

---

## Pattern 09: Struct Embedding Sai

### Tên
Struct Embedding Sai (Incorrect Struct Embedding)

### Phân loại
Type System / Struct / Composition

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```
type Base struct { /* interface embedded */ }

type Server struct {
    http.Handler        ← Embedded interface!
    name string
}

s := Server{name: "web"}
s.ServeHTTP(w, r)       ← PANIC!
       │
       ▼
  http.Handler is nil (never set)
  Method promotion: Server.ServeHTTP exists
  But underlying Handler is nil → nil pointer dereference

  Compiler: no error (method exists via embedding)
  Runtime: PANIC!
```

Struct embedding promotes methods từ embedded type. Nếu embed interface, methods tồn tại nhưng gọi sẽ panic vì interface receiver là nil.

### Phát hiện

```bash
# Tìm struct embedded interfaces
rg --type go "type\s+\w+\s+struct\s*\{" -A 10 | rg "^\s+\w+\.\w+$|^\s+\w+$" | grep -v "func\|var\|const"

# Tìm embedded types (không có field name)
rg --type go "^\s+\w+\s*$" -n

# Tìm interface embedded trong struct
rg --type go "type\s+\w+\s+struct" -A 10 | rg "\w+Interface|\w+er\b"
```

### Giải pháp

❌ **BAD**: Embed interface in struct
```go
type Cache struct {
    sync.Locker // Embedded interface — nil by default!
    data map[string]string
}

c := Cache{data: make(map[string]string)}
c.Lock() // PANIC: nil Locker
```

✅ **GOOD**: Named field with concrete type
```go
type Cache struct {
    mu   sync.Mutex // Concrete type, zero-value usable
    data map[string]string
}

func (c *Cache) Get(key string) string {
    c.mu.Lock()
    defer c.mu.Unlock()
    return c.data[key]
}
```

✅ **GOOD**: Embed struct (not interface)
```go
type Base struct {
    CreatedAt time.Time
    UpdatedAt time.Time
}

type User struct {
    Base  // Embed concrete struct — safe
    Name  string
    Email string
}
// user.CreatedAt works correctly
```

### Phòng ngừa

- [ ] NEVER embed interfaces in structs (trừ khi intentional partial impl)
- [ ] Embed concrete structs cho field promotion
- [ ] Named fields cho interface dependencies
- [ ] Test zero-value behavior
- Tool: `go vet` — detects some nil method calls

---

## Pattern 10: Singleton Global

### Tên
Singleton Global (Global Variable Thay DI)

### Phân loại
Design / Dependency / Global State

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```
package db

var DB *sql.DB  ← Global singleton

func init() {
    DB, _ = sql.Open("postgres", os.Getenv("DB_URL"))
}

// Used everywhere:
package user
import "app/db"
func GetUser(id string) (User, error) {
    return db.DB.QueryRow("SELECT ...")  ← Implicit dependency
}
       │
       ├── Testing: cannot replace DB in tests
       ├── Race condition: concurrent access to DB pointer
       ├── Hidden dependency: function signature hides DB usage
       └── Configuration: DB URL fixed at init time
```

### Phát hiện

```bash
# Tìm package-level var declarations
rg --type go "^var\s+[A-Z]\w+\s" -n

# Tìm global singletons (common names)
rg --type go "var\s+(DB|Logger|Config|Cache|Client)\s" -n

# Tìm sync.Once pattern (singleton init)
rg --type go "sync\.Once" -n -A 5

# Tìm package-level assignments
rg --type go "^var\s+\w+\s*=\s*" -n
```

### Giải pháp

❌ **BAD**: Global singleton
```go
var db *sql.DB
func GetDB() *sql.DB {
    if db == nil { db = connectDB() }
    return db
}
```

✅ **GOOD**: Constructor injection
```go
type UserService struct {
    db *sql.DB
}

func NewUserService(db *sql.DB) *UserService {
    return &UserService{db: db}
}

func (s *UserService) GetUser(ctx context.Context, id string) (User, error) {
    row := s.db.QueryRowContext(ctx, "SELECT ...", id)
    // Explicit dependency, testable
}
```

✅ **GOOD**: Functional options pattern
```go
type Option func(*Server)

func WithDB(db *sql.DB) Option {
    return func(s *Server) { s.db = db }
}

func NewServer(opts ...Option) *Server {
    s := &Server{}
    for _, opt := range opts {
        opt(s)
    }
    return s
}
```

### Phòng ngừa

- [ ] Constructor injection cho dependencies
- [ ] Functional options cho configurable structs
- [ ] No package-level mutable variables
- [ ] sync.Once chỉ khi thực sự cần lazy init
- Tool: `golangci-lint` với `gochecknoglobals` linter

---

## Pattern 11: Type Assertion Không Check

### Tên
Type Assertion Không Check (Unchecked Type Assertion)

### Phân loại
Type System / Interface / Assertion

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```
var i interface{} = "hello"

// Single-value assertion — PANIC nếu sai type!
val := i.(int)  ← PANIC: interface is string, not int
       │
       ▼
  panic: interface conversion:
    interface {} is string, not int
       │
       └── Process crash! No recovery possible
           (trừ khi có recover() trong defer)
```

Type assertion dạng `v := x.(Type)` sẽ panic nếu x không phải Type. Phải dùng comma-ok pattern `v, ok := x.(Type)` để check an toàn.

### Phát hiện

```bash
# Tìm single-value type assertions (không có ok check)
rg --type go "\w+\s*:=\s*\w+\.\([A-Z]" -n

# Tìm type assertions trong function calls
rg --type go "\.\((\*?\w+)\)" -n

# Tìm comma-ok pattern (safe — reference)
rg --type go ",\s*ok\s*:=.*\.\(" -n

# Tìm type switches (safe alternative)
rg --type go "switch.*\.\(type\)" -n
```

### Giải pháp

❌ **BAD**: Unchecked assertion
```go
func processValue(v interface{}) string {
    return v.(string) // PANIC nếu v không phải string
}
```

✅ **GOOD**: Comma-ok pattern
```go
func processValue(v interface{}) (string, error) {
    s, ok := v.(string)
    if !ok {
        return "", fmt.Errorf("expected string, got %T", v)
    }
    return s, nil
}
```

✅ **GOOD**: Type switch
```go
func processValue(v interface{}) string {
    switch val := v.(type) {
    case string:
        return val
    case int:
        return strconv.Itoa(val)
    case fmt.Stringer:
        return val.String()
    default:
        return fmt.Sprintf("%v", v)
    }
}
```

### Phòng ngừa

- [ ] ALWAYS dùng comma-ok: `v, ok := x.(Type)`
- [ ] Type switch cho multiple type handling
- [ ] Generics (Go 1.18+) thay type assertions
- Tool: `golangci-lint` với `forcetypeassert` linter
- Tool: `go vet` — warns about some unsafe assertions

---

## Pattern 12: Constructor Thiếu

### Tên
Constructor Thiếu (Missing Constructor)

### Phân loại
Design / Initialization / Zero Value

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```
type Server struct {
    host    string
    port    int
    timeout time.Duration
    logger  *log.Logger
    db      *sql.DB
}

// Direct construction — invalid!
s := Server{}
s.Start()  ← host="", port=0, timeout=0, logger=nil
       │
       ▼
  Zero values gây bugs:
  - host="" → listen on all interfaces
  - port=0 → random port
  - timeout=0 → no timeout (hang forever)
  - logger=nil → nil pointer dereference
  - db=nil → nil pointer dereference
```

Khi struct có required fields hoặc zero values không hợp lệ, cần constructor `NewXxx()` để validate và set defaults. Direct struct literal `Struct{}` bypass validation.

### Phát hiện

```bash
# Tìm structs không có constructor
rg --type go "type\s+\w+\s+struct" -l | xargs -I{} sh -c \
  'echo "=== {} ===" && rg "func New" {} || echo "NO CONSTRUCTOR"'

# Tìm direct struct instantiation
rg --type go "\w+\{\}" -n

# Tìm existing constructors
rg --type go "func New\w+\(" -n
```

### Giải pháp

❌ **BAD**: Direct instantiation, no validation
```go
s := &Server{host: "localhost"}
// port, timeout, logger, db all zero/nil — bugs waiting
```

✅ **GOOD**: Constructor with validation
```go
func NewServer(host string, port int, db *sql.DB, opts ...Option) (*Server, error) {
    if host == "" {
        return nil, errors.New("host is required")
    }
    if port <= 0 || port > 65535 {
        return nil, errors.New("invalid port")
    }
    if db == nil {
        return nil, errors.New("db is required")
    }

    s := &Server{
        host:    host,
        port:    port,
        db:      db,
        timeout: 30 * time.Second, // sensible default
        logger:  log.Default(),     // sensible default
    }

    for _, opt := range opts {
        opt(s)
    }
    return s, nil
}
```

✅ **GOOD**: Unexported fields enforce constructor usage
```go
type server struct { // unexported struct
    host string
    port int
}

func NewServer(host string, port int) *server {
    return &server{host: host, port: port}
}
// External packages MUST use NewServer — cannot create server{} directly
```

### Phòng ngừa

- [ ] `NewXxx()` constructor cho structs với required fields
- [ ] Validate required fields trong constructor
- [ ] Set sensible defaults cho optional fields
- [ ] Functional options cho complex configuration
- [ ] Unexported struct type nếu muốn enforce constructor
- Tool: `golangci-lint` — custom linter rules
