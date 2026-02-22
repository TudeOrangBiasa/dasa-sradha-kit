# Domain 04: Toàn Vẹn Dữ Liệu (Data Integrity)

> Go patterns liên quan đến tính nhất quán và toàn vẹn của dữ liệu trong hệ thống.

---

## Pattern 01: SQL Transaction Không Commit/Rollback

### Tên
SQL Transaction Không Commit/Rollback

### Phân loại
Database / Transaction Management

### Mức nghiêm trọng
CRITICAL 🔴

### Vấn đề

```
Luồng thực thi:
  tx, _ := db.Begin()
       │
       ▼
  INSERT / UPDATE
       │
       ▼
  return err  ◄── Không gọi tx.Commit() hoặc tx.Rollback()
       │
       ▼
  Connection giữ lock mãi mãi
  Deadlock trong production
  Data không được ghi vào DB
```

Khi một transaction được mở bằng `db.Begin()` mà không có `commit` hoặc `rollback`, connection bị giữ trong pool cho đến khi timeout. Với tải cao, toàn bộ connection pool có thể bị chiếm bởi các transaction zombie.

### Phát hiện

Tìm kiếm transaction bắt đầu mà không có defer rollback:

```bash
# Tìm tất cả db.Begin() không có defer rollback ngay sau
rg --type go -n "db\.Begin\(\)" | grep -v "_test\.go"

# Tìm tx.Commit mà thiếu tx.Rollback đi kèm
rg --type go -n "tx\.Commit\(\)" -A 2 -B 10

# Tìm hàm nhận tx nhưng không rollback
rg --type go -n "func.*\*sql\.Tx" | head -20
```

### Giải pháp

**BAD - Transaction không được đóng đúng cách:**
```go
func transferMoney(db *sql.DB, from, to int64, amount float64) error {
    tx, err := db.Begin()
    if err != nil {
        return err
    }

    _, err = tx.Exec("UPDATE accounts SET balance = balance - $1 WHERE id = $2", amount, from)
    if err != nil {
        return err // BUG: tx không được rollback, connection bị leak
    }

    _, err = tx.Exec("UPDATE accounts SET balance = balance + $1 WHERE id = $2", amount, to)
    if err != nil {
        return err // BUG: tx không được rollback
    }

    return tx.Commit() // Chỉ commit, không có rollback path
}
```

**GOOD - Transaction được quản lý đúng cách:**
```go
func transferMoney(db *sql.DB, from, to int64, amount float64) error {
    tx, err := db.Begin()
    if err != nil {
        return fmt.Errorf("begin transaction: %w", err)
    }

    // MUST: defer rollback ngay sau Begin()
    // Nếu Commit() đã được gọi, Rollback() là no-op
    defer func() {
        if p := recover(); p != nil {
            _ = tx.Rollback()
            panic(p) // re-panic sau khi rollback
        }
    }()

    committed := false
    defer func() {
        if !committed {
            _ = tx.Rollback() // đảm bảo rollback nếu chưa commit
        }
    }()

    _, err = tx.Exec("UPDATE accounts SET balance = balance - $1 WHERE id = $2", amount, from)
    if err != nil {
        return fmt.Errorf("debit account %d: %w", from, err)
    }

    _, err = tx.Exec("UPDATE accounts SET balance = balance + $1 WHERE id = $2", amount, to)
    if err != nil {
        return fmt.Errorf("credit account %d: %w", to, err)
    }

    if err = tx.Commit(); err != nil {
        return fmt.Errorf("commit transaction: %w", err)
    }

    committed = true
    return nil
}

// Pattern helper tái sử dụng
func withTransaction(db *sql.DB, fn func(*sql.Tx) error) (err error) {
    tx, err := db.Begin()
    if err != nil {
        return err
    }

    defer func() {
        if p := recover(); p != nil {
            _ = tx.Rollback()
            panic(p)
        }
        if err != nil {
            _ = tx.Rollback()
        }
    }()

    err = fn(tx)
    if err != nil {
        return err
    }

    return tx.Commit()
}
```

### Phòng ngừa

```bash
# Chạy staticcheck để phát hiện transaction leak
go install honnef.co/go/tools/cmd/staticcheck@latest
staticcheck ./...

# Dùng go vet với shadow checker
go vet ./...

# Kiểm tra với golangci-lint
golangci-lint run --enable=exhaustruct,sqlclosecheck

# Trong test, dùng sqlmock để kiểm tra rollback
# github.com/DATA-DOG/go-sqlmock
mock.ExpectBegin()
mock.ExpectExec("UPDATE").WillReturnError(someErr)
mock.ExpectRollback() // xác nhận rollback được gọi
```

---

## Pattern 02: database/sql Connection Leak

### Tên
database/sql Connection Leak

### Phân loại
Database / Resource Management

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```
db.Query() trả về *sql.Rows
      │
      ▼
rows.Next() + rows.Scan()
      │
      ▼
  return err  ◄── rows.Close() không được gọi
      │
      ▼
Connection giữ trong pool
Pool cạn kiệt (max_open_connections)
Mọi request mới đều block
```

`*sql.Rows` giữ một database connection cho đến khi `Close()` được gọi. Nếu bỏ qua `defer rows.Close()`, connection bị leak mỗi lần query được thực thi.

### Phát hiện

```bash
# Tìm db.Query mà không có rows.Close
rg --type go -n "\.Query\(" -A 5 | grep -v "rows\.Close\|defer"

# Tìm rows được khai báo mà không close
rg --type go -n "rows, err := .*\.Query"

# Tìm QueryRow không scan kết quả
rg --type go -n "QueryRow\(" -A 3
```

### Giải pháp

**BAD - Rows không được đóng:**
```go
func getUserNames(db *sql.DB) ([]string, error) {
    rows, err := db.Query("SELECT name FROM users WHERE active = true")
    if err != nil {
        return nil, err
    }
    // MISSING: defer rows.Close()

    var names []string
    for rows.Next() {
        var name string
        if err := rows.Scan(&name); err != nil {
            return nil, err // LEAK: rows không được close khi có lỗi
        }
        names = append(names, name)
    }

    return names, rows.Err()
    // LEAK: rows không được close khi hàm return thành công
}
```

**GOOD - Rows được quản lý đúng:**
```go
func getUserNames(db *sql.DB) ([]string, error) {
    rows, err := db.Query("SELECT name FROM users WHERE active = true")
    if err != nil {
        return nil, fmt.Errorf("query users: %w", err)
    }
    defer rows.Close() // MUST: luôn defer ngay sau khi kiểm tra err

    var names []string
    for rows.Next() {
        var name string
        if err := rows.Scan(&name); err != nil {
            return nil, fmt.Errorf("scan user name: %w", err)
        }
        names = append(names, name)
    }

    // MUST: kiểm tra lỗi sau vòng lặp
    if err := rows.Err(); err != nil {
        return nil, fmt.Errorf("iterate rows: %w", err)
    }

    return names, nil
}

// Cấu hình pool đúng cách
func newDB(dsn string) (*sql.DB, error) {
    db, err := sql.Open("postgres", dsn)
    if err != nil {
        return nil, err
    }

    // Cấu hình pool để phát hiện leak sớm
    db.SetMaxOpenConns(25)
    db.SetMaxIdleConns(5)
    db.SetConnMaxLifetime(5 * time.Minute)
    db.SetConnMaxIdleTime(1 * time.Minute)

    return db, nil
}
```

### Phòng ngừa

```bash
# sqlclosecheck linter phát hiện rows/stmt không được close
go install github.com/ryanrolds/sqlclosecheck@latest
golangci-lint run --enable=sqlclosecheck

# Monitor connection pool trong runtime
go func() {
    for range time.Tick(30 * time.Second) {
        stats := db.Stats()
        log.Printf("DB Pool: open=%d idle=%d in_use=%d wait=%d",
            stats.OpenConnections,
            stats.Idle,
            stats.InUse,
            stats.WaitCount,
        )
    }
}()

# Đặt DB_MAX_OPEN_CONNS thấp trong test để phát hiện leak nhanh
db.SetMaxOpenConns(5)
```

---

## Pattern 03: NULL Handling Thiếu

### Tên
NULL Handling Thiếu

### Phân loại
Database / Data Integrity

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```
DB Column: VARCHAR NULL
      │
      ▼
Scan vào: var name string
      │
      ▼
sql: Scan error: converting NULL to string is unsupported
      │
      ▼
Panic hoặc dữ liệu sai
```

Go's `database/sql` không tự động xử lý NULL khi scan vào các kiểu cơ bản. Cần dùng `sql.NullString`, `sql.NullInt64`, v.v. hoặc pointer types.

### Phát hiện

```bash
# Tìm Scan với string thay vì sql.NullString
rg --type go -n "\.Scan\(" -A 5 | grep "&name\|&email\|&phone\|&address"

# Tìm column nullable trong schema mà code không dùng sql.Null*
rg --type go -n "sql\.Null"

# Tìm nơi dùng string trực tiếp từ DB
rg --type go -n "var.*string\n.*rows\.Scan" --multiline
```

### Giải pháp

**BAD - Scan NULL vào string thường:**
```go
type User struct {
    ID    int64
    Name  string
    Email string // NULLABLE trong DB
    Phone string // NULLABLE trong DB
}

func getUser(db *sql.DB, id int64) (*User, error) {
    var u User
    err := db.QueryRow(
        "SELECT id, name, email, phone FROM users WHERE id = $1", id,
    ).Scan(&u.ID, &u.Name, &u.Email, &u.Phone)
    // PANIC khi email hoặc phone là NULL trong DB
    if err != nil {
        return nil, err
    }
    return &u, nil
}
```

**GOOD - Dùng sql.Null* hoặc pointer:**
```go
// Cách 1: Dùng sql.Null types
type UserRow struct {
    ID    int64
    Name  string
    Email sql.NullString
    Phone sql.NullString
}

func getUser(db *sql.DB, id int64) (*User, error) {
    var row UserRow
    err := db.QueryRow(
        "SELECT id, name, email, phone FROM users WHERE id = $1", id,
    ).Scan(&row.ID, &row.Name, &row.Email, &row.Phone)
    if err != nil {
        return nil, fmt.Errorf("get user %d: %w", id, err)
    }

    u := &User{
        ID:   row.ID,
        Name: row.Name,
    }
    if row.Email.Valid {
        u.Email = row.Email.String
    }
    if row.Phone.Valid {
        u.Phone = row.Phone.String
    }
    return u, nil
}

// Cách 2: Dùng pointer types
type User struct {
    ID    int64
    Name  string
    Email *string // nil khi NULL
    Phone *string // nil khi NULL
}

func getUserPtr(db *sql.DB, id int64) (*User, error) {
    var u User
    err := db.QueryRow(
        "SELECT id, name, email, phone FROM users WHERE id = $1", id,
    ).Scan(&u.ID, &u.Name, &u.Email, &u.Phone)
    if err != nil {
        return nil, fmt.Errorf("get user %d: %w", id, err)
    }
    return &u, nil
}

// Cách 3: Helper function
func nullString(s string) sql.NullString {
    return sql.NullString{String: s, Valid: s != ""}
}
```

### Phòng ngừa

```bash
# Dùng sqlc để generate type-safe code từ SQL schema
# sqlc tự động handle nullable columns
go install github.com/sqlc-dev/sqlc/cmd/sqlc@latest
sqlc generate

# Dùng go vet với nilness checker
go vet -nilness ./...

# Test với NULL data
func TestGetUserWithNullEmail(t *testing.T) {
    db.Exec("INSERT INTO users (id, name, email) VALUES (1, 'Test', NULL)")
    user, err := getUser(db, 1)
    assert.NoError(t, err)
    assert.Empty(t, user.Email)
}
```

---

## Pattern 04: JSON Marshaling Zero Value vs Null

### Tên
JSON Marshaling Zero Value vs Null

### Phân loại
Serialization / API Contract

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```
Go struct field: int (zero value = 0)
      │
      ▼
json.Marshal với omitempty
      │
      ▼
Field "count": 0 → bị omit hoàn toàn
      │
      ▼
API client nhận {} thay vì {"count": 0}
Không phân biệt được "không có data" vs "data = 0"
```

Go không phân biệt giữa "field không tồn tại" và "field có giá trị zero". Điều này gây ra API contract không rõ ràng, đặc biệt với `omitempty`.

### Phát hiện

```bash
# Tìm struct dùng omitempty với kiểu số hoặc bool
rg --type go -n 'omitempty' -A 0 | grep -v "string\|String"

# Tìm json tag với omitempty trên numeric fields
rg --type go -n 'json:".*omitempty"' -B 1 | grep "int\|float\|bool"

# Tìm marshal/unmarshal không dùng pointer
rg --type go -n "json\.Marshal\|json\.Unmarshal" -A 5
```

### Giải pháp

**BAD - omitempty xóa zero values hợp lệ:**
```go
type OrderStats struct {
    TotalOrders   int     `json:"total_orders,omitempty"`   // 0 bị xóa
    TotalRevenue  float64 `json:"total_revenue,omitempty"`  // 0.0 bị xóa
    IsProcessing  bool    `json:"is_processing,omitempty"`  // false bị xóa
    ErrorMsg      string  `json:"error_msg,omitempty"`      // "" bị xóa (OK)
}

// {"total_orders": 0} → marshal → {}
// API client không biết là 0 hay là field không tồn tại
```

**GOOD - Dùng pointer để phân biệt null vs zero:**
```go
// Cách 1: Pointer cho optional fields
type OrderStats struct {
    TotalOrders  *int     `json:"total_orders"`  // null vs 0 rõ ràng
    TotalRevenue *float64 `json:"total_revenue"` // null vs 0.0 rõ ràng
    IsProcessing *bool    `json:"is_processing"` // null vs false rõ ràng
    ErrorMsg     string   `json:"error_msg,omitempty"` // string OK với omitempty
}

func newOrderStats(total int, revenue float64, processing bool) OrderStats {
    return OrderStats{
        TotalOrders:  &total,
        TotalRevenue: &revenue,
        IsProcessing: &processing,
    }
}

// Cách 2: Dùng encoding/json với custom marshaler
type NullableInt struct {
    Value int
    Valid bool // false = null
}

func (n NullableInt) MarshalJSON() ([]byte, error) {
    if !n.Valid {
        return []byte("null"), nil
    }
    return json.Marshal(n.Value)
}

func (n *NullableInt) UnmarshalJSON(data []byte) error {
    if string(data) == "null" {
        n.Valid = false
        return nil
    }
    n.Valid = true
    return json.Unmarshal(data, &n.Value)
}

// Cách 3: Dùng thư viện như go-json hoặc jsoniter
// Hoặc dùng map[string]any khi cần dynamic fields
```

### Phòng ngừa

```bash
# Test round-trip marshaling
func TestZeroValueMarshal(t *testing.T) {
    stats := OrderStats{TotalOrders: intPtr(0)}
    data, _ := json.Marshal(stats)
    assert.Contains(t, string(data), `"total_orders":0`)

    var got OrderStats
    json.Unmarshal(data, &got)
    assert.NotNil(t, got.TotalOrders)
    assert.Equal(t, 0, *got.TotalOrders)
}

# Dùng json schema validation để enforce contract
# Hoặc protobuf/grpc để tránh JSON ambiguity
```

---

## Pattern 05: time.Time Timezone Confusion

### Tên
time.Time Timezone Confusion

### Phân loại
Data Integrity / Temporal

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```
Server: UTC+0
DB lưu: "2024-01-15 09:00:00" (không có timezone)
      │
      ▼
time.Parse("2006-01-02 15:04:05", "2024-01-15 09:00:00")
      │
      ▼
Go interpret là UTC
      │
      ▼
Client: UTC+9 (Tokyo)
Hiển thị: "2024-01-15 18:00:00" JST ← SAI
Thực tế:  "2024-01-15 09:00:00" JST ← ĐÚNG
```

Go `time.Time` chứa timezone. Khi parse mà không chỉ định timezone, Go dùng UTC. Khi lưu vào DB mà không cẩn thận, thông tin timezone bị mất.

### Phát hiện

```bash
# Tìm time.Parse không dùng UTC hoặc timezone cụ thể
rg --type go -n "time\.Parse\(" | grep -v "time\.UTC\|time\.Local\|time\.FixedZone"

# Tìm time.Now() không convert timezone
rg --type go -n "time\.Now\(\)" -A 2

# Tìm thao tác so sánh time mà không cùng timezone
rg --type go -n "\.Before\(\|\.After\(\|\.Equal\(" -B 3

# Tìm time.ParseInLocation
rg --type go -n "time\.ParseInLocation"
```

### Giải pháp

**BAD - Mất thông tin timezone:**
```go
// Hàm lưu appointment time
func saveAppointment(db *sql.DB, timeStr string) error {
    // WRONG: Parse không chỉ định timezone
    t, err := time.Parse("2006-01-02 15:04:05", timeStr)
    if err != nil {
        return err
    }
    // t.Location() = UTC (mặc định)

    _, err = db.Exec("INSERT INTO appointments (scheduled_at) VALUES ($1)", t)
    return err
    // DB lưu UTC value nhưng user nhập theo Tokyo time → sai 9 giờ
}

// So sánh time sai timezone
func isExpired(deadline time.Time) bool {
    return time.Now().After(deadline) // time.Now() là local, deadline có thể là UTC
}
```

**GOOD - Timezone được xử lý rõ ràng:**
```go
// Luôn dùng UTC internally
func saveAppointment(db *sql.DB, timeStr string, userTZ string) error {
    loc, err := time.LoadLocation(userTZ) // ví dụ: "Asia/Tokyo"
    if err != nil {
        return fmt.Errorf("invalid timezone %q: %w", userTZ, err)
    }

    // Parse với timezone của user
    t, err := time.ParseInLocation("2006-01-02 15:04:05", timeStr, loc)
    if err != nil {
        return fmt.Errorf("parse time %q: %w", timeStr, err)
    }

    // Convert sang UTC trước khi lưu
    tUTC := t.UTC()

    _, err = db.Exec("INSERT INTO appointments (scheduled_at) VALUES ($1)", tUTC)
    return err
}

// So sánh time đúng cách
func isExpired(deadline time.Time) bool {
    // Dùng time.Now().UTC() hoặc convert deadline sang UTC
    return time.Now().UTC().After(deadline.UTC())
}

// Helper: luôn trả về UTC
func nowUTC() time.Time {
    return time.Now().UTC()
}

// Hiển thị cho user: convert từ UTC sang timezone của user
func formatForUser(t time.Time, userTZ string) (string, error) {
    loc, err := time.LoadLocation(userTZ)
    if err != nil {
        return "", err
    }
    return t.In(loc).Format("2006-01-02 15:04:05"), nil
}

// Trong main/init: set timezone server
func init() {
    // Đảm bảo server luôn chạy UTC
    if tz := os.Getenv("TZ"); tz == "" {
        os.Setenv("TZ", "UTC")
    }
}
```

### Phòng ngừa

```bash
# Linter cho timezone issues
golangci-lint run --enable=gocritic

# Test với nhiều timezone
func TestAppointmentTimezone(t *testing.T) {
    timezones := []string{"UTC", "Asia/Tokyo", "America/New_York", "Europe/London"}
    for _, tz := range timezones {
        t.Run(tz, func(t *testing.T) {
            // Verify round-trip không mất timezone info
        })
    }
}

# Dùng TIMESTAMPTZ (PostgreSQL) thay vì TIMESTAMP để DB lưu timezone
# CREATE TABLE events (created_at TIMESTAMPTZ NOT NULL DEFAULT NOW())

# Trong Docker/Kubernetes, set timezone:
# ENV TZ=UTC
```

---

## Pattern 06: Map Concurrent Write (Fatal)

### Tên
Map Concurrent Write

### Phân loại
Concurrency / Data Integrity

### Mức nghiêm trọng
CRITICAL 🔴

### Vấn đề

```
Goroutine 1              Goroutine 2
    │                        │
map["key1"] = "val1"    map["key2"] = "val2"
    │         ↕ concurrent write │
    └────────────────────────────┘
              │
              ▼
  fatal error: concurrent map writes
  SIGABRT → Program crash
  Không recover được (không phải panic)
```

Go runtime phát hiện concurrent map write và gọi `throw()` trực tiếp, không phải `panic()`. Điều này có nghĩa là `recover()` không thể bắt được lỗi này - chương trình sẽ crash ngay lập tức.

### Phát hiện

```bash
# Chạy với race detector (QUAN TRỌNG NHẤT)
go test -race ./...
go run -race main.go

# Tìm map được dùng trong goroutine mà không có mutex
rg --type go -n "go func" -A 10 | grep "map\["

# Tìm global map
rg --type go -n "^var.*map\["

# Tìm map trong struct không có sync.Mutex
rg --type go -n "map\[" -B 5 | grep -v "sync\.Mutex\|sync\.RWMutex"
```

### Giải pháp

**BAD - Concurrent write vào map không được bảo vệ:**
```go
// Cache không thread-safe
var cache = map[string]string{}

func handleRequest(key, value string) {
    go func() {
        cache[key] = value // FATAL: concurrent map write
    }()

    result := cache[key] // FATAL: concurrent map read/write
    fmt.Println(result)
}

// Worker pool chia sẻ map
func processItems(items []Item) {
    results := make(map[string]int)

    var wg sync.WaitGroup
    for _, item := range items {
        wg.Add(1)
        go func(i Item) {
            defer wg.Done()
            results[i.Key] = compute(i) // FATAL: concurrent write
        }(item)
    }
    wg.Wait()
}
```

**GOOD - Dùng sync.RWMutex hoặc sync.Map:**
```go
// Cách 1: sync.RWMutex (read nhiều, write ít)
type SafeCache struct {
    mu    sync.RWMutex
    store map[string]string
}

func NewSafeCache() *SafeCache {
    return &SafeCache{store: make(map[string]string)}
}

func (c *SafeCache) Set(key, value string) {
    c.mu.Lock()
    defer c.mu.Unlock()
    c.store[key] = value
}

func (c *SafeCache) Get(key string) (string, bool) {
    c.mu.RLock() // Read lock cho concurrent reads
    defer c.mu.RUnlock()
    v, ok := c.store[key]
    return v, ok
}

// Cách 2: sync.Map (nhiều goroutine write vào keys khác nhau)
var cache sync.Map

func handleRequest(key, value string) {
    cache.Store(key, value)

    if v, ok := cache.Load(key); ok {
        fmt.Println(v)
    }
}

// Cách 3: Channel-based (actor pattern)
type cacheMsg struct {
    key   string
    value string
    resp  chan string
}

type CacheActor struct {
    store map[string]string
    ch    chan cacheMsg
}

func NewCacheActor() *CacheActor {
    ca := &CacheActor{
        store: make(map[string]string),
        ch:    make(chan cacheMsg, 100),
    }
    go ca.run()
    return ca
}

func (ca *CacheActor) run() {
    for msg := range ca.ch {
        if msg.value != "" {
            ca.store[msg.key] = msg.value
        } else if msg.resp != nil {
            msg.resp <- ca.store[msg.key]
        }
    }
}

// Worker pool an toàn: collect results sau
func processItemsSafe(items []Item) map[string]int {
    type result struct {
        key   string
        value int
    }

    resultCh := make(chan result, len(items))

    var wg sync.WaitGroup
    for _, item := range items {
        wg.Add(1)
        go func(i Item) {
            defer wg.Done()
            resultCh <- result{key: i.Key, value: compute(i)}
        }(item)
    }

    go func() {
        wg.Wait()
        close(resultCh)
    }()

    // Collect ở goroutine duy nhất
    results := make(map[string]int)
    for r := range resultCh {
        results[r.key] = r.value
    }
    return results
}
```

### Phòng ngừa

```bash
# Race detector là công cụ QUAN TRỌNG NHẤT
go build -race -o myapp .
go test -race -count=1 ./...

# Chạy với race detector trong CI
# .github/workflows/test.yml:
# run: go test -race -timeout=30s ./...

# go vet cũng phát hiện một số race conditions
go vet ./...

# Linting
golangci-lint run --enable=godot,gochecknoglobals

# Tránh global mutable state
# Đặt state trong struct, không dùng package-level variables
```

---

## Pattern 07: Slice Append Gotcha (Shared Underlying Array)

### Tên
Slice Append Gotcha (Shared Underlying Array)

### Phân loại
Data Integrity / Memory

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```
original := []int{1, 2, 3, 4, 5}
s1 := original[:3]   // [1, 2, 3] → cap=5, shares array
s2 := original[2:5]  // [3, 4, 5] → cap=3, shares array
      │
      ▼
s1 = append(s1, 99)  // s1 = [1, 2, 3, 99]
      │
      ▼
original = [1, 2, 3, 99, 5]  ← BIẾN ĐỔI KHÔNG MONG MUỐN!
s2 = [3, 99, 5]              ← BIẾN ĐỔI KHÔNG MONG MUỐN!
```

Slice trong Go là view của array. Khi slice chưa full capacity, `append` ghi vào array gốc, ảnh hưởng đến tất cả slice khác cùng chia sẻ array.

### Phát hiện

```bash
# Tìm slice operation tiềm ẩn sharing
rg --type go -n "\[:.*\]" | grep "append"

# Tìm function nhận slice và append
rg --type go -n "func.*\[\]" -A 10 | grep "append"

# Tìm reslice trước append
rg --type go -n "s\[:\|s\[0:" -A 3 | grep "append"
```

### Giải pháp

**BAD - Append ghi đè vào shared array:**
```go
func processAndFilter(data []int) ([]int, []int) {
    evens := data[:0] // Reslice với cùng underlying array
    odds := make([]int, 0)

    for _, v := range data {
        if v%2 == 0 {
            evens = append(evens, v) // MODIFY data gốc!
        } else {
            odds = append(odds, v)
        }
    }
    return evens, odds
}

// Ví dụ thực tế: function nhận slice, caller bị surprise
func addDefault(items []string) []string {
    return append(items, "default") // Có thể ghi vào caller's array!
}

func main() {
    items := make([]string, 2, 5) // len=2, cap=5
    items[0] = "a"
    items[1] = "b"

    result := addDefault(items)
    fmt.Println(items)  // [a b] ← OK
    fmt.Println(result) // [a b default]

    // Nhưng items[2] đã bị ghi, nếu sau đó items = items[:3]:
    items = items[:3]
    fmt.Println(items)  // [a b default] ← Surprise!
}
```

**GOOD - Copy để tránh shared array:**
```go
// Cách 1: copy() rõ ràng
func processAndFilterSafe(data []int) ([]int, []int) {
    evens := make([]int, 0, len(data)/2+1)
    odds := make([]int, 0, len(data)/2+1)

    for _, v := range data {
        if v%2 == 0 {
            evens = append(evens, v)
        } else {
            odds = append(odds, v)
        }
    }
    return evens, odds // Hoàn toàn độc lập với data gốc
}

// Cách 2: Dùng full slice expression để giới hạn capacity
func addDefault(items []string) []string {
    // items[:len(items):len(items)] → cap = len = len(items)
    // append sẽ buộc phải allocate array mới
    limited := items[:len(items):len(items)]
    return append(limited, "default")
}

// Cách 3: Clone slice trước khi xử lý
func cloneSlice[T any](s []T) []T {
    if s == nil {
        return nil
    }
    clone := make([]T, len(s))
    copy(clone, s)
    return clone
}

// Cách 4: Dùng slices package (Go 1.21+)
import "slices"

func processSafe(data []int) []int {
    working := slices.Clone(data) // Luôn allocate mới
    // ... xử lý working
    return working
}
```

### Phòng ngừa

```bash
# Dùng go vet để phát hiện một số slice issues
go vet ./...

# Test với slice sharing scenarios
func TestNoSharedArray(t *testing.T) {
    original := []int{1, 2, 3, 4, 5}
    originalCopy := slices.Clone(original)

    result, _ := processAndFilterSafe(original)
    _ = result

    // Verify original không bị thay đổi
    assert.Equal(t, originalCopy, original)
}

# Dùng race detector cùng với unit test
go test -race ./...

# Code review: cảnh giác với pattern data[:0] và reslice
```

---

## Pattern 08: Struct Alignment Waste

### Tên
Struct Alignment Waste

### Phân loại
Performance / Memory

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```
Struct layout không tối ưu:
struct {
    a bool    // 1 byte + 7 padding
    b int64   // 8 bytes
    c bool    // 1 byte + 7 padding
    d int32   // 4 bytes + 4 padding
}
Total: 32 bytes (thực tế chỉ cần 14 bytes!)

Struct layout tối ưu:
struct {
    b int64  // 8 bytes
    d int32  // 4 bytes
    a bool   // 1 byte
    c bool   // 1 byte + 2 padding
}
Total: 16 bytes
```

Go compiler thêm padding để align các fields theo kích thước của chúng. Thứ tự khai báo fields ảnh hưởng trực tiếp đến kích thước struct trong memory.

### Phát hiện

```bash
# Dùng fieldalignment để phát hiện và sửa
go install golang.org/x/tools/go/analysis/passes/fieldalignment/cmd/fieldalignment@latest
fieldalignment ./...

# Tìm struct lớn có thể tối ưu
rg --type go -n "^type.*struct" -A 20

# Kiểm tra size bằng unsafe.Sizeof
go run - << 'EOF'
package main
import (
    "fmt"
    "unsafe"
)
type Bad struct {
    A bool
    B int64
    C bool
    D int32
}
type Good struct {
    B int64
    D int32
    A bool
    C bool
}
func main() {
    fmt.Printf("Bad:  %d bytes\n", unsafe.Sizeof(Bad{}))
    fmt.Printf("Good: %d bytes\n", unsafe.Sizeof(Good{}))
}
EOF
```

### Giải pháp

**BAD - Struct không được align tốt:**
```go
// Wastes 18 bytes out of 32
type UserEvent struct {
    Processed bool      // 1 + 7 padding
    Timestamp int64     // 8
    Retried   bool      // 1 + 3 padding
    UserID    int32     // 4
    Active    bool      // 1 + 7 padding
    SessionID int64     // 8
    // Total: 40 bytes
}

// Struct có nhiều bool fields rải rác
type Config struct {
    EnableA bool   // 1 + 7 padding
    MaxSize int64  // 8
    EnableB bool   // 1 + 7 padding
    Timeout int64  // 8
    EnableC bool   // 1 + 7 padding
    // Total: 40 bytes (chỉ cần 27 bytes)
}
```

**GOOD - Fields sắp xếp theo kích thước giảm dần:**
```go
// Sắp xếp: 8-byte → 4-byte → 2-byte → 1-byte
type UserEvent struct {
    Timestamp int64  // 8 bytes
    SessionID int64  // 8 bytes
    UserID    int32  // 4 bytes
    Processed bool   // 1 byte
    Retried   bool   // 1 byte
    Active    bool   // 1 byte + 1 padding
    // Total: 24 bytes (tiết kiệm 16 bytes!)
}

type Config struct {
    MaxSize int64  // 8 bytes
    Timeout int64  // 8 bytes
    EnableA bool   // 1 byte
    EnableB bool   // 1 byte
    EnableC bool   // 1 byte + 5 padding
    // Total: 24 bytes (tiết kiệm 16 bytes!)
}

// Tự động fix với fieldalignment tool
// fieldalignment -fix ./...
```

### Phòng ngừa

```bash
# Thêm vào Makefile
lint:
    fieldalignment ./...
    golangci-lint run

# golangci-lint với maligned/govet plugin
golangci-lint run --enable=govet

# Thêm vào CI pipeline
- name: Check struct alignment
  run: fieldalignment ./...

# Với struct lớn trong hot path, đo lường tác động
func BenchmarkUserEvent(b *testing.B) {
    events := make([]UserEvent, 1000000)
    b.ResetTimer()
    for i := 0; i < b.N; i++ {
        _ = events[i%len(events)]
    }
}
```

---

## Pattern 09: encoding/binary Endian Sai

### Tên
encoding/binary Endian Sai

### Phân loại
Data Integrity / Serialization

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```
Ghi (Server A - Little Endian x86):
int32(258) = 0x00000102
Little Endian bytes: [02 01 00 00]
      │
      ▼
Đọc (Server B - Big Endian hoặc Network):
binary.BigEndian.Uint32([02 01 00 00])
= 0x02010000 = 33620992 ← SỐ SAI HOÀN TOÀN!

Network byte order = Big Endian (theo chuẩn TCP/IP)
```

Khi đọc/ghi binary data, endianness phải nhất quán ở cả hai đầu. Sai endian dẫn đến dữ liệu bị đọc sai hoàn toàn, đặc biệt nguy hiểm trong giao tiếp mạng hoặc file format.

### Phát hiện

```bash
# Tìm dùng LittleEndian trong network code
rg --type go -n "binary\.LittleEndian"

# Tìm dùng BigEndian trong file format code (nếu spec dùng LE)
rg --type go -n "binary\.BigEndian"

# Tìm binary.Read/Write mà không rõ endian
rg --type go -n "binary\.Read\|binary\.Write" -B 3

# Tìm manual byte manipulation
rg --type go -n "byte\(.*>>" | grep "16\|24\|32"
```

### Giải pháp

**BAD - Endian không nhất quán:**
```go
// Writer dùng LittleEndian
func writePacket(w io.Writer, msgID uint32, payload []byte) error {
    header := make([]byte, 8)
    binary.LittleEndian.PutUint32(header[0:4], msgID)
    binary.LittleEndian.PutUint32(header[4:8], uint32(len(payload)))

    if _, err := w.Write(header); err != nil {
        return err
    }
    _, err := w.Write(payload)
    return err
}

// Reader dùng BigEndian - SẼ ĐỌC SAI!
func readPacket(r io.Reader) (uint32, []byte, error) {
    header := make([]byte, 8)
    if _, err := io.ReadFull(r, header); err != nil {
        return 0, nil, err
    }

    msgID := binary.BigEndian.Uint32(header[0:4])   // ĐỌC SAI!
    length := binary.BigEndian.Uint32(header[4:8])  // ĐỌC SAI!

    payload := make([]byte, length)
    if _, err := io.ReadFull(r, payload); err != nil {
        return 0, nil, err
    }
    return msgID, payload, nil
}
```

**GOOD - Endian nhất quán và được định nghĩa rõ ràng:**
```go
// Định nghĩa rõ ràng byte order cho protocol
// Network protocols thường dùng BigEndian (network byte order)
var networkByteOrder = binary.BigEndian

// Hoặc dùng constant để dễ thay đổi
const protocolByteOrder = binary.BigEndian

type Packet struct {
    MsgID   uint32
    Payload []byte
}

func writePacket(w io.Writer, p Packet) error {
    header := struct {
        MsgID  uint32
        Length uint32
    }{
        MsgID:  p.MsgID,
        Length: uint32(len(p.Payload)),
    }

    // Dùng binary.Write với endian cố định
    if err := binary.Write(w, networkByteOrder, header); err != nil {
        return fmt.Errorf("write header: %w", err)
    }

    if _, err := w.Write(p.Payload); err != nil {
        return fmt.Errorf("write payload: %w", err)
    }
    return nil
}

func readPacket(r io.Reader) (Packet, error) {
    var header struct {
        MsgID  uint32
        Length uint32
    }

    // Dùng cùng byte order
    if err := binary.Read(r, networkByteOrder, &header); err != nil {
        return Packet{}, fmt.Errorf("read header: %w", err)
    }

    payload := make([]byte, header.Length)
    if _, err := io.ReadFull(r, payload); err != nil {
        return Packet{}, fmt.Errorf("read payload: %w", err)
    }

    return Packet{MsgID: header.MsgID, Payload: payload}, nil
}

// Helper: document endian choice
// NetworkByteOrder theo RFC 791 (Internet Protocol)
// FileByteOrder cho binary file format cụ thể
```

### Phòng ngừa

```bash
# Test với round-trip encoding
func TestPacketEndian(t *testing.T) {
    original := Packet{MsgID: 258, Payload: []byte("hello")}

    var buf bytes.Buffer
    err := writePacket(&buf, original)
    require.NoError(t, err)

    got, err := readPacket(&buf)
    require.NoError(t, err)

    assert.Equal(t, original.MsgID, got.MsgID)
    assert.Equal(t, original.Payload, got.Payload)
}

# Test với giá trị biên
func TestEndianBoundary(t *testing.T) {
    values := []uint32{0, 1, 256, 257, 65535, 65536, math.MaxUint32}
    for _, v := range values {
        // verify round-trip
    }
}

# Document endian choice trong package comment
// Package protocol implements binary framing using Big-Endian byte order
// (network byte order per RFC 791).
```

---

## Pattern 10: Data Race Trên Shared Map

### Tên
Data Race Trên Shared Map

### Phân loại
Concurrency / Data Integrity

### Mức nghiêm trọng
CRITICAL 🔴

### Vấn đề

```
Goroutine 1 (HTTP handler):     Goroutine 2 (background worker):
      │                                │
  v := cache["key"]              cache["key"] = newValue
      │              ↕ DATA RACE       │
      └──────────────────────────────────┘
              │
              ▼
  Race detector: DATA RACE
  Undefined behavior:
    - Crash
    - Corrupted data
    - Infinite loop trong Go map internal
    - Security vulnerability
```

Data race khác với concurrent map write ở chỗ: một goroutine đọc trong khi goroutine khác đang ghi. Không có đảm bảo atomic nào trong Go map, nên ngay cả đọc/ghi đồng thời cũng là undefined behavior.

### Phát hiện

```bash
# PHẢI chạy race detector
go test -race -count=1 ./...
go run -race cmd/server/main.go

# Tìm global map được modify
rg --type go -n "^var.*= map\["

# Tìm map trong HTTP handler (thường chạy concurrent)
rg --type go -n "func.*Handler\|func.*ServeHTTP" -A 20 | grep "map\["

# Tìm map trong goroutine
rg --type go -n "go func" -A 15 | grep "map\["

# Tìm map write không có lock
rg --type go -n "\[.*\] =" | grep -v "test\|_test"
```

### Giải pháp

**BAD - Data race trong HTTP server:**
```go
// Package-level cache - nguy hiểm
var sessionCache = map[string]Session{}
var requestCounts = map[string]int{}

func handleAPI(w http.ResponseWriter, r *http.Request) {
    token := r.Header.Get("Authorization")

    // DATA RACE: read trong khi goroutine khác có thể write
    session, ok := sessionCache[token]
    if !ok {
        http.Error(w, "unauthorized", http.StatusUnauthorized)
        return
    }

    // DATA RACE: write concurrent với reads
    requestCounts[session.UserID]++

    // ... handle request
}

func refreshSessions() {
    for {
        time.Sleep(5 * time.Minute)
        newSessions := fetchSessions()
        // DATA RACE: reassign map while handlers read
        sessionCache = newSessions
    }
}
```

**GOOD - Thread-safe implementations:**
```go
// Cách 1: sync.RWMutex cho read-heavy workloads
type SessionCache struct {
    mu    sync.RWMutex
    store map[string]Session
}

func NewSessionCache() *SessionCache {
    return &SessionCache{store: make(map[string]Session)}
}

func (c *SessionCache) Get(token string) (Session, bool) {
    c.mu.RLock() // Multiple concurrent reads allowed
    defer c.mu.RUnlock()
    s, ok := c.store[token]
    return s, ok
}

func (c *SessionCache) Set(token string, s Session) {
    c.mu.Lock() // Exclusive write lock
    defer c.mu.Unlock()
    c.store[token] = s
}

func (c *SessionCache) Replace(newStore map[string]Session) {
    c.mu.Lock()
    defer c.mu.Unlock()
    c.store = newStore
}

// Cách 2: sync.Map cho write-heavy hoặc sharded access
type RequestCounter struct {
    counts sync.Map // map[string]*atomic.Int64
}

func (rc *RequestCounter) Increment(userID string) {
    actual, _ := rc.counts.LoadOrStore(userID, new(atomic.Int64))
    actual.(*atomic.Int64).Add(1)
}

func (rc *RequestCounter) Get(userID string) int64 {
    if v, ok := rc.counts.Load(userID); ok {
        return v.(*atomic.Int64).Load()
    }
    return 0
}

// Cách 3: Per-request context thay vì shared state
type Handler struct {
    sessionCache *SessionCache
    reqCounter   *RequestCounter
}

func (h *Handler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
    token := r.Header.Get("Authorization")

    session, ok := h.sessionCache.Get(token)
    if !ok {
        http.Error(w, "unauthorized", http.StatusUnauthorized)
        return
    }

    h.reqCounter.Increment(session.UserID)

    // ... handle request
}

// Cách 4: Immutable snapshot pattern
type AtomicCache[K comparable, V any] struct {
    ptr atomic.Pointer[map[K]V]
}

func (c *AtomicCache[K, V]) Load() map[K]V {
    if p := c.ptr.Load(); p != nil {
        return *p
    }
    return nil
}

func (c *AtomicCache[K, V]) Store(m map[K]V) {
    c.ptr.Store(&m) // Store pointer to new map (immutable swap)
}
```

### Phòng ngừa

```bash
# Race detector là bắt buộc trong CI
# .github/workflows/ci.yml:
- name: Test with race detector
  run: go test -race -timeout=60s -count=1 ./...

# Benchmark với race detector để phát hiện production-like races
go test -race -bench=. ./...

# Dùng go vet
go vet ./...

# Golangci-lint rules
golangci-lint run --enable=gocritic,godot,gochecknoglobals

# Tránh package-level mutable state
# Thay vì: var globalCache = map[string]string{}
# Dùng: type Server struct { cache *SafeCache }

# Sử dụng atomic operations cho simple counters
var requestCount atomic.Int64
requestCount.Add(1)
count := requestCount.Load()
```

---

## Tóm Tắt

| # | Pattern | Mức độ | Công cụ Phát Hiện |
|---|---------|--------|-------------------|
| 01 | SQL Transaction Không Commit/Rollback | CRITICAL 🔴 | staticcheck, sqlclosecheck |
| 02 | database/sql Connection Leak | HIGH 🟠 | sqlclosecheck, db.Stats() |
| 03 | NULL Handling Thiếu | HIGH 🟠 | sqlc, unit test |
| 04 | JSON Marshaling Zero Value vs Null | MEDIUM 🟡 | unit test round-trip |
| 05 | time.Time Timezone Confusion | HIGH 🟠 | gocritic, unit test |
| 06 | Map Concurrent Write | CRITICAL 🔴 | go test -race |
| 07 | Slice Append Gotcha | HIGH 🟠 | go vet, unit test |
| 08 | Struct Alignment Waste | MEDIUM 🟡 | fieldalignment |
| 09 | encoding/binary Endian Sai | HIGH 🟠 | unit test round-trip |
| 10 | Data Race Trên Shared Map | CRITICAL 🔴 | go test -race |

### Quick Commands

```bash
# Chạy tất cả detectors
go test -race -count=1 ./...
go vet ./...
fieldalignment ./...
staticcheck ./...
golangci-lint run --enable=sqlclosecheck,gocritic,gochecknoglobals
```
