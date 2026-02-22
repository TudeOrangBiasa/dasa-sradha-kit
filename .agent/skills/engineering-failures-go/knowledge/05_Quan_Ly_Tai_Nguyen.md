# Domain 05: Quản Lý Tài Nguyên (Resource Management)

> Go patterns liên quan đến quản lý tài nguyên hệ thống: file handles, connections, memory.

---

## Pattern 01: HTTP Response Body Không Close

### Tên
HTTP Response Body Không Close (HTTP Response Body Not Closed)

### Phân loại
Network / HTTP Client / Resource Leak

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```
HTTP Request Flow:

  http.Get(url)
       │
       ▼
  resp, err := ...
       │
       ├── err != nil → return (OK, không có body)
       │
       └── err == nil
            │
            ▼
       resp.Body  ◄── io.ReadCloser giữ TCP connection
            │
            ├── Đọc body (ioutil.ReadAll / io.Copy)
            │        │
            │        └── Quên resp.Body.Close()
            │                    │
            │                    ▼
            │              fd (file descriptor) bị leak
            │              TCP connection không trả về pool
            │              OS hết file descriptor → "too many open files"
            │
            └── Không đọc body (chỉ check status code)
                         │
                         ▼
                   Body vẫn mở → connection không reuse
                   Transport pool bị cạn kiệt
```

Khi gọi `http.Get()` hoặc bất kỳ HTTP client method nào trả về `*http.Response`, trường `Body` là một `io.ReadCloser` giữ reference đến underlying TCP connection. Nếu không gọi `resp.Body.Close()`:

1. **File descriptor leak**: Mỗi response giữ một fd, OS có giới hạn (thường 1024 mặc định)
2. **Connection pool exhaustion**: `http.Transport` không thể tái sử dụng connection
3. **Memory leak**: Body buffer không được giải phóng
4. **Cascading failure**: Sau vài nghìn request, service không thể tạo connection mới

### Phát hiện

Dấu hiệu trong production:
- Log chứa `"too many open files"` hoặc `"socket: too many open files"`
- HTTP client timeout tăng dần theo thời gian
- `lsof -p <pid> | wc -l` cho thấy số fd tăng liên tục

```bash
# Tìm http.Get/Do/Post mà không có defer resp.Body.Close()
rg --type go -n "http\.(Get|Post|Head|Do)\(" -A 8 | grep -v "resp\.Body\.Close\|defer"

# Tìm response được gán nhưng body không close
rg --type go -n "resp, err := .*http\." -A 10

# Tìm pattern nguy hiểm: check status rồi return mà không close body
rg --type go -n "resp\.StatusCode" -B 3 -A 5

# Tìm tất cả file có http request nhưng thiếu Body.Close
rg --type go -l "http\.(Get|Post|Do)" | xargs -I{} sh -c \
  'rg -c "Body\.Close" {} | grep -q "^0$" && echo "MISSING CLOSE: {}"'
```

### Giải pháp

**BAD - Response body không được close:**
```go
package client

import (
    "encoding/json"
    "fmt"
    "net/http"
)

type UserProfile struct {
    ID    int64  `json:"id"`
    Name  string `json:"name"`
    Email string `json:"email"`
}

// BAD: body không được close trong nhiều trường hợp
func GetUserProfile(apiURL string, userID int64) (*UserProfile, error) {
    url := fmt.Sprintf("%s/api/users/%d", apiURL, userID)
    resp, err := http.Get(url)
    if err != nil {
        return nil, err
    }

    // BUG 1: Nếu status != 200, return mà không close body
    if resp.StatusCode != http.StatusOK {
        return nil, fmt.Errorf("unexpected status: %d", resp.StatusCode)
    }

    var profile UserProfile
    // BUG 2: Nếu json.Decode lỗi, body không được close
    if err := json.NewDecoder(resp.Body).Decode(&profile); err != nil {
        return nil, fmt.Errorf("decode response: %w", err)
    }

    // BUG 3: Body chỉ close ở happy path, nhưng không dùng defer
    resp.Body.Close()

    return &profile, nil
}

// BAD: Pattern phổ biến - chỉ check status code mà không close
func IsServiceHealthy(healthURL string) bool {
    resp, err := http.Get(healthURL)
    if err != nil {
        return false
    }
    // LEAK: body không được close, connection không được trả về pool
    return resp.StatusCode == http.StatusOK
}
```

**GOOD - Response body luôn được close đúng cách:**
```go
package client

import (
    "encoding/json"
    "fmt"
    "io"
    "net/http"
)

type UserProfile struct {
    ID    int64  `json:"id"`
    Name  string `json:"name"`
    Email string `json:"email"`
}

// GOOD: defer close ngay sau khi kiểm tra err
func GetUserProfile(apiURL string, userID int64) (*UserProfile, error) {
    url := fmt.Sprintf("%s/api/users/%d", apiURL, userID)
    resp, err := http.Get(url)
    if err != nil {
        return nil, fmt.Errorf("http get user %d: %w", userID, err)
    }
    // MUST: defer close ngay lập tức sau khi kiểm tra err
    defer resp.Body.Close()

    if resp.StatusCode != http.StatusOK {
        // Đọc body để lấy error message (và drain connection)
        body, _ := io.ReadAll(io.LimitReader(resp.Body, 1024))
        return nil, fmt.Errorf("unexpected status %d: %s", resp.StatusCode, string(body))
    }

    var profile UserProfile
    if err := json.NewDecoder(resp.Body).Decode(&profile); err != nil {
        return nil, fmt.Errorf("decode user profile: %w", err)
    }

    return &profile, nil
}

// GOOD: Health check với close đúng cách
func IsServiceHealthy(healthURL string) bool {
    resp, err := http.Get(healthURL)
    if err != nil {
        return false
    }
    defer resp.Body.Close()

    // Drain body để connection có thể reuse
    _, _ = io.Copy(io.Discard, resp.Body)

    return resp.StatusCode == http.StatusOK
}

// GOOD: Helper function đảm bảo luôn close + drain
func doRequest(client *http.Client, req *http.Request, target interface{}) error {
    resp, err := client.Do(req)
    if err != nil {
        return fmt.Errorf("do request: %w", err)
    }
    defer func() {
        // Drain remaining body trước khi close để reuse connection
        _, _ = io.Copy(io.Discard, resp.Body)
        resp.Body.Close()
    }()

    if resp.StatusCode < 200 || resp.StatusCode >= 300 {
        body, _ := io.ReadAll(io.LimitReader(resp.Body, 4096))
        return fmt.Errorf("status %d: %s", resp.StatusCode, string(body))
    }

    if target != nil {
        if err := json.NewDecoder(resp.Body).Decode(target); err != nil {
            return fmt.Errorf("decode response: %w", err)
        }
    }

    return nil
}
```

### Phòng ngừa

```
Checklist:
- [ ] Mỗi http.Get/Post/Do PHẢI có defer resp.Body.Close() ngay sau kiểm tra err
- [ ] Non-2xx response cũng phải close body (drain trước khi close)
- [ ] Dùng io.Copy(io.Discard, resp.Body) để drain connection cho reuse
- [ ] Giới hạn body size với io.LimitReader để tránh OOM
- [ ] Viết helper function doRequest() để đảm bảo consistency
```

```bash
# golangci-lint với bodyclose linter
golangci-lint run --enable=bodyclose ./...

# staticcheck phát hiện unclosed body
staticcheck ./...

# go vet cơ bản
go vet ./...

# Custom script kiểm tra trong CI
rg --type go "http\.(Get|Post|Head)\(" -l | while read f; do
  if ! rg -q "Body\.Close" "$f"; then
    echo "WARNING: $f has HTTP calls but no Body.Close"
  fi
done
```

---

## Pattern 02: File Handle Leak

### Tên
File Handle Leak (Rò Rỉ File Handle)

### Phân loại
OS / File System / Resource Leak

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```
Vòng đời File Handle:

  os.Open("data.csv")
       │
       ▼
  f, err := ...   ◄── OS cấp file descriptor (fd)
       │
       ├── err != nil → return (OK, fd chưa mở)
       │
       └── err == nil
            │
            ▼
      [đọc/ghi file]
            │
            ├── Quên f.Close()
            │       │
            │       ▼
            │   fd bị leak
            │   OS fd table đầy dần
            │   "too many open files" sau N lần
            │
            │   Trên Linux:
            │   ulimit -n = 1024 (mặc định)
            │   => 1024 file open = crash
            │
            └── f.Close() trong defer
                    │
                    ▼
                fd được trả về OS
                Tài nguyên giải phóng đúng cách

  Nguy hiểm đặc biệt khi:
  ┌──────────────────────────────────────┐
  │ for i := 0; i < 10000; i++ {        │
  │     f, _ := os.Open(files[i])       │
  │     // process without close        │  ◄── 10,000 fd leak
  │ }                                   │
  └──────────────────────────────────────┘
```

File handle (file descriptor) là tài nguyên hữu hạn của OS. Mỗi `os.Open()`, `os.Create()`, `os.OpenFile()` cấp một fd. Nếu không `Close()`, fd bị leak cho đến khi process thoát. Trên Linux, giới hạn mặc định thường là 1024 fd per process.

### Phát hiện

Dấu hiệu runtime:
- Error message: `"too many open files"`
- `ls /proc/<pid>/fd | wc -l` tăng dần
- `lsof -p <pid> | grep REG` cho thấy nhiều file mở

```bash
# Tìm os.Open/Create/OpenFile mà không có defer close
rg --type go -n "os\.(Open|Create|OpenFile)\(" -A 5 | grep -v "defer.*\.Close\|_test\.go"

# Tìm file handle được gán nhưng không close
rg --type go -n "f, err := os\.(Open|Create)" -A 8

# Tìm file open trong loop (nguy cơ cao nhất)
rg --type go -n "for.*\{" -A 10 | rg "os\.(Open|Create)"

# Kiểm tra tất cả file có open nhưng thiếu close
rg --type go -l "os\.(Open|Create|OpenFile)" | while read f; do
  opens=$(rg -c "os\.(Open|Create|OpenFile)" "$f")
  closes=$(rg -c "\.Close\(\)" "$f")
  if [ "$opens" -gt "$closes" ]; then
    echo "SUSPECT: $f (opens=$opens, closes=$closes)"
  fi
done
```

### Giải pháp

**BAD - File handle bị leak:**
```go
package processor

import (
    "bufio"
    "encoding/csv"
    "fmt"
    "os"
)

// BAD: file handle leak khi có lỗi giữa chừng
func ProcessCSV(filePath string) ([][]string, error) {
    f, err := os.Open(filePath)
    if err != nil {
        return nil, err
    }
    // MISSING: defer f.Close()

    reader := csv.NewReader(f)
    records, err := reader.ReadAll()
    if err != nil {
        return nil, err // LEAK: file không được close khi parse lỗi
    }

    f.Close() // Chỉ close ở happy path
    return records, nil
}

// BAD: leak trong loop - mỗi iteration leak 1 fd
func CountLinesInFiles(paths []string) (map[string]int, error) {
    result := make(map[string]int)

    for _, path := range paths {
        f, err := os.Open(path)
        if err != nil {
            return nil, err
        }

        scanner := bufio.NewScanner(f)
        count := 0
        for scanner.Scan() {
            count++
        }
        result[path] = count
        // LEAK: f.Close() quên gọi trong mỗi iteration
    }

    return result, nil
}

// BAD: file tạo nhưng write lỗi, không close
func WriteReport(outputPath string, data []byte) error {
    f, err := os.Create(outputPath)
    if err != nil {
        return err
    }

    _, err = f.Write(data)
    if err != nil {
        return fmt.Errorf("write failed: %w", err) // LEAK: f không close
    }

    return f.Close()
}
```

**GOOD - File handle luôn được close đúng cách:**
```go
package processor

import (
    "bufio"
    "encoding/csv"
    "fmt"
    "os"
)

// GOOD: defer close ngay sau khi open
func ProcessCSV(filePath string) ([][]string, error) {
    f, err := os.Open(filePath)
    if err != nil {
        return nil, fmt.Errorf("open %s: %w", filePath, err)
    }
    defer f.Close() // MUST: close dù có lỗi hay không

    reader := csv.NewReader(f)
    records, err := reader.ReadAll()
    if err != nil {
        return nil, fmt.Errorf("parse csv %s: %w", filePath, err)
    }

    return records, nil
}

// GOOD: close trong mỗi iteration, dùng helper function
func CountLinesInFiles(paths []string) (map[string]int, error) {
    result := make(map[string]int)

    for _, path := range paths {
        count, err := countLines(path)
        if err != nil {
            return nil, fmt.Errorf("count lines in %s: %w", path, err)
        }
        result[path] = count
    }

    return result, nil
}

// Helper: file mở và đóng trong cùng function scope
func countLines(path string) (int, error) {
    f, err := os.Open(path)
    if err != nil {
        return 0, err
    }
    defer f.Close()

    scanner := bufio.NewScanner(f)
    count := 0
    for scanner.Scan() {
        count++
    }

    if err := scanner.Err(); err != nil {
        return 0, fmt.Errorf("scan: %w", err)
    }

    return count, nil
}

// GOOD: write file với proper error handling cho Close
func WriteReport(outputPath string, data []byte) (err error) {
    f, err := os.Create(outputPath)
    if err != nil {
        return fmt.Errorf("create %s: %w", outputPath, err)
    }

    // Defer close với error check
    defer func() {
        closeErr := f.Close()
        if err == nil {
            err = closeErr // trả về close error nếu write OK
        }
    }()

    _, err = f.Write(data)
    if err != nil {
        return fmt.Errorf("write %s: %w", outputPath, err)
    }

    // Sync để đảm bảo data đã flush xuống disk
    if err = f.Sync(); err != nil {
        return fmt.Errorf("sync %s: %w", outputPath, err)
    }

    return nil
}
```

### Phòng ngừa

```
Checklist:
- [ ] Mỗi os.Open/Create/OpenFile PHẢI có defer f.Close() ngay sau kiểm tra err
- [ ] Trong loop: extract thành function riêng để defer hoạt động đúng
- [ ] Write file: kiểm tra cả err từ Close() (data có thể chưa flush)
- [ ] Write file: gọi f.Sync() trước Close() cho critical data
- [ ] Test với ulimit -n thấp để phát hiện leak sớm
```

```bash
# golangci-lint kiểm tra file handle
golangci-lint run --enable=gosec,gocritic ./...

# go vet cơ bản
go vet ./...

# staticcheck
staticcheck ./...

# Test với giới hạn fd thấp (Linux/Mac)
ulimit -n 64 && go test ./... -count=1
```

---

## Pattern 03: DB Connection Pool Exhaustion

### Tên
DB Connection Pool Exhaustion (Cạn Kiệt Connection Pool Database)

### Phân loại
Database / Connection Management / Infrastructure

### Mức nghiêm trọng
CRITICAL 🔴

### Vấn đề

```
Connection Pool Architecture:

  Application            Connection Pool              Database
  ┌──────────┐          ┌──────────────┐          ┌──────────────┐
  │ Handler 1 │──req──▶ │ conn 1 [busy]│──────── ▶│              │
  │ Handler 2 │──req──▶ │ conn 2 [busy]│──────── ▶│   PostgreSQL │
  │ Handler 3 │──req──▶ │ conn 3 [busy]│──────── ▶│   / MySQL    │
  │ Handler 4 │──wait─▶ │ conn 4 [busy]│──────── ▶│              │
  │ Handler 5 │──wait─▶ │ conn 5 [busy]│──────── ▶│  max_conn    │
  │ Handler 6 │──wait─▶ │              │          │  = 100       │
  │    ...     │──wait─▶ │  Pool Full!  │          │              │
  │ Handler N │──wait─▶ │  MaxOpen = 5 │          │              │
  └──────────┘          └──────────────┘          └──────────────┘
       │                       │
       ▼                       ▼
  Tất cả handlers      Không còn connection
  bị block chờ         để phục vụ request
  → Request timeout     → Service down

  Nguyên nhân Pool Exhaustion:
  ┌────────────────────────────────────────────┐
  │ 1. MaxOpenConns quá cao → DB overload      │
  │ 2. MaxOpenConns quá thấp → app starve      │
  │ 3. Không set MaxOpenConns → unlimited!     │
  │ 4. Rows/Tx không close → conn stuck        │
  │ 5. MaxIdleConns < MaxOpenConns → churn     │
  │ 6. ConnMaxLifetime = 0 → stale connections │
  └────────────────────────────────────────────┘
```

`database/sql` trong Go dùng connection pool. Mặc định, `MaxOpenConns` = 0 (unlimited), nghĩa là application có thể mở hàng nghìn connection đến database, vượt quá `max_connections` của DB server. Ngược lại, nếu connection bị leak (rows/tx không close), pool cạn kiệt nhanh chóng.

### Phát hiện

Dấu hiệu trong production:
- Query timeout tăng dần
- `db.Stats().OpenConnections` tăng liên tục
- `db.Stats().WaitCount` > 0 và tăng
- Database log: `"too many connections"`
- Application log: `"context deadline exceeded"` khi query

```bash
# Tìm sql.Open mà không set pool parameters
rg --type go -n "sql\.Open\(" -A 20 | grep -v "SetMaxOpenConns\|SetMaxIdleConns\|SetConnMaxLifetime"

# Tìm nơi khởi tạo DB connection
rg --type go -n "sql\.Open\(" -l

# Kiểm tra có set pool config không
rg --type go -n "SetMaxOpenConns\|SetMaxIdleConns\|SetConnMaxLifetime"

# Tìm db.Query mà rows không close (gây connection leak)
rg --type go -n "\.Query\(" -A 5 | grep -v "rows\.Close\|defer\|QueryRow"

# Tìm transaction không rollback
rg --type go -n "\.Begin\(" -A 10 | grep -v "Rollback\|defer"
```

### Giải pháp

**BAD - Connection pool không được cấu hình đúng:**
```go
package database

import (
    "database/sql"
    "fmt"

    _ "github.com/lib/pq"
)

// BAD: không cấu hình pool, mặc định unlimited connections
func NewDB(dsn string) (*sql.DB, error) {
    db, err := sql.Open("postgres", dsn)
    if err != nil {
        return nil, err
    }

    // MISSING: SetMaxOpenConns - mặc định 0 = unlimited
    // MISSING: SetMaxIdleConns - mặc định 2 (quá thấp)
    // MISSING: SetConnMaxLifetime - mặc định 0 = never expire

    return db, nil
}

// BAD: cấu hình sai tỷ lệ
func NewDBBadConfig(dsn string) (*sql.DB, error) {
    db, err := sql.Open("postgres", dsn)
    if err != nil {
        return nil, err
    }

    db.SetMaxOpenConns(1000)  // Quá cao - vượt DB max_connections (100)
    db.SetMaxIdleConns(2)     // Quá thấp so với MaxOpen → connection churn
    // MISSING: SetConnMaxLifetime → stale connections

    return db, nil
}

// BAD: không monitor pool stats
func handleRequest(db *sql.DB) {
    // Không biết pool đang cạn kiệt
    rows, err := db.Query("SELECT * FROM orders WHERE status = $1", "pending")
    if err != nil {
        // err có thể là timeout vì pool cạn
        // nhưng không log pool stats để debug
        log.Printf("query failed: %v", err)
        return
    }
    defer rows.Close()
    // ...
}
```

**GOOD - Connection pool được cấu hình và giám sát đúng cách:**
```go
package database

import (
    "context"
    "database/sql"
    "fmt"
    "log"
    "time"

    _ "github.com/lib/pq"
)

type DBConfig struct {
    DSN             string
    MaxOpenConns    int
    MaxIdleConns    int
    ConnMaxLifetime time.Duration
    ConnMaxIdleTime time.Duration
}

func DefaultConfig(dsn string) DBConfig {
    return DBConfig{
        DSN:             dsn,
        MaxOpenConns:    25,              // Phù hợp cho hầu hết workload
        MaxIdleConns:    10,              // ~40% của MaxOpen
        ConnMaxLifetime: 30 * time.Minute, // Tránh stale connections
        ConnMaxIdleTime: 5 * time.Minute,  // Giải phóng idle connections
    }
}

// GOOD: cấu hình pool đầy đủ với health check
func NewDB(cfg DBConfig) (*sql.DB, error) {
    db, err := sql.Open("postgres", cfg.DSN)
    if err != nil {
        return nil, fmt.Errorf("open db: %w", err)
    }

    // Cấu hình pool
    db.SetMaxOpenConns(cfg.MaxOpenConns)
    db.SetMaxIdleConns(cfg.MaxIdleConns)
    db.SetConnMaxLifetime(cfg.ConnMaxLifetime)
    db.SetConnMaxIdleTime(cfg.ConnMaxIdleTime)

    // Ping để verify connection
    ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
    defer cancel()

    if err := db.PingContext(ctx); err != nil {
        db.Close()
        return nil, fmt.Errorf("ping db: %w", err)
    }

    return db, nil
}

// GOOD: monitor pool stats định kỳ
func MonitorPool(ctx context.Context, db *sql.DB, interval time.Duration) {
    ticker := time.NewTicker(interval)
    defer ticker.Stop()

    for {
        select {
        case <-ctx.Done():
            return
        case <-ticker.C:
            stats := db.Stats()
            log.Printf(
                "DB Pool: open=%d inuse=%d idle=%d wait_count=%d wait_duration=%s max_idle_closed=%d max_lifetime_closed=%d",
                stats.OpenConnections,
                stats.InUse,
                stats.Idle,
                stats.WaitCount,
                stats.WaitDuration,
                stats.MaxIdleClosed,
                stats.MaxLifetimeClosed,
            )

            // Alert nếu pool gần cạn
            if stats.InUse > stats.MaxOpenConnections*80/100 {
                log.Printf("WARNING: DB pool usage at %d%% (%d/%d)",
                    stats.InUse*100/stats.MaxOpenConnections,
                    stats.InUse,
                    stats.MaxOpenConnections,
                )
            }
        }
    }
}

// GOOD: cấu hình theo môi trường
func PoolSizeGuide() {
    // Rule of thumb:
    // MaxOpenConns = min(db_max_connections / num_app_instances, cpu_cores * 2 + effective_spindle_count)
    //
    // Ví dụ: DB max_connections=100, 4 app instances, 4 CPU cores
    // MaxOpenConns = min(100/4, 4*2+1) = min(25, 9) = 9
    //
    // MaxIdleConns = MaxOpenConns * 0.3~0.5
    // ConnMaxLifetime = 15~30 phút
    // ConnMaxIdleTime = 3~5 phút
}
```

### Phòng ngừa

```
Checklist:
- [ ] LUÔN set MaxOpenConns (không bao giờ để mặc định 0)
- [ ] MaxOpenConns = DB_max_connections / số_app_instances
- [ ] MaxIdleConns = 30-50% của MaxOpenConns
- [ ] ConnMaxLifetime = 15-30 phút
- [ ] ConnMaxIdleTime = 3-5 phút (Go 1.15+)
- [ ] Monitor db.Stats() và alert khi pool sắp cạn
- [ ] Mỗi Rows phải có defer rows.Close()
- [ ] Mỗi Tx phải có defer tx.Rollback()
```

```bash
# golangci-lint kiểm tra SQL resource
golangci-lint run --enable=sqlclosecheck,rowserrcheck,gocritic ./...

# Tìm sql.Open thiếu pool config
rg --type go "sql\.Open\(" -l | while read f; do
  if ! rg -q "SetMaxOpenConns" "$f"; then
    echo "WARNING: $f opens DB but missing SetMaxOpenConns"
  fi
done

# staticcheck
staticcheck ./...

# Monitor runtime (thêm vào prometheus metrics)
# sql_open_connections, sql_in_use, sql_wait_count, sql_wait_duration
```

---

## Pattern 04: Defer Trong Loop

### Tên
Defer Trong Loop (Defer Inside Loop)

### Phân loại
Language Semantics / Resource Management / Memory

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```
Cách defer hoạt động:

  func example() {
      defer cleanup()      ◄── Thêm vào defer stack
      // ...
  }                        ◄── cleanup() chạy ở đây (khi function return)

  Vấn đề với defer trong loop:

  func processFiles(paths []string) {
      for _, p := range paths {      ──────────────────────────────┐
          f, _ := os.Open(p)         │ Iteration 1: open file 1   │
          defer f.Close()            │ defer #1 (sẽ chạy khi      │
          // process f               │ function return, KHÔNG      │
      }                              │ khi iteration kết thúc!)    │
      // ...                         ──────────────────────────────┘
  }
  // TẤT CẢ defer chạy ở đây!      ◄── Tất cả files close cùng lúc

  Tích lũy tài nguyên:
  ┌─────────────────────────────────────────────┐
  │ Iteration 1: open file 1 → defer stack [1]  │
  │ Iteration 2: open file 2 → defer stack [2,1]│
  │ Iteration 3: open file 3 → defer stack [3,2,1]
  │ ...                                          │
  │ Iteration N: open file N → defer stack [N..1]│
  │                                               │
  │ Tại thời điểm iteration N:                   │
  │   - N file descriptors đang mở              │
  │   - N defer closures trong stack            │
  │   - Memory: N * (fd + closure) bytes        │
  │   - Nếu N = 100,000 → OOM hoặc "too many   │
  │     open files"                              │
  └─────────────────────────────────────────────┘
```

`defer` trong Go thực thi khi surrounding function return, KHÔNG phải khi block (for, if) kết thúc. Khi đặt `defer` trong loop, tất cả deferred calls tích lũy cho đến khi function return. Với loop lớn, điều này gây:

1. **Resource accumulation**: Tất cả file/connection mở đồng thời
2. **Memory spike**: Defer closure objects tích lũy
3. **Delayed cleanup**: Resources chỉ được giải phóng khi function kết thúc

### Phát hiện

```bash
# Tìm defer bên trong for loop
rg --type go -n "defer" -B 5 | rg "for.*\{" -A 5 | rg "defer"

# Tìm pattern: for + open + defer close
rg --type go -n "for " -A 10 | rg "defer.*\.Close\(\)"

# Tìm defer trong loop với context cụ thể hơn
rg --type go -U "for\s.*\{[^}]*defer" --multiline

# Tìm defer trong tất cả loại loop
rg --type go -n "defer" -B 10 | rg "for\s|range\s"
```

### Giải pháp

**BAD - Defer tích lũy trong loop:**
```go
package importer

import (
    "encoding/json"
    "fmt"
    "os"
)

type Record struct {
    ID   string `json:"id"`
    Data string `json:"data"`
}

// BAD: defer trong loop - tất cả file mở đồng thời
func ImportAllJSON(paths []string) ([]Record, error) {
    var allRecords []Record

    for _, path := range paths {
        f, err := os.Open(path)
        if err != nil {
            return nil, fmt.Errorf("open %s: %w", path, err)
        }
        defer f.Close() // BUG: chỉ close khi function return!

        var records []Record
        if err := json.NewDecoder(f).Decode(&records); err != nil {
            return nil, fmt.Errorf("decode %s: %w", path, err)
        }
        allRecords = append(allRecords, records...)
    }
    // Tất cả len(paths) files đang mở ở đây
    // Close() chạy LIFO: paths[N-1].Close(), ..., paths[0].Close()

    return allRecords, nil
}

// BAD: defer rows.Close trong loop query
func FetchAllUserOrders(db *sql.DB, userIDs []int64) (map[int64][]Order, error) {
    result := make(map[int64][]Order)

    for _, uid := range userIDs {
        rows, err := db.Query("SELECT * FROM orders WHERE user_id = $1", uid)
        if err != nil {
            return nil, err
        }
        defer rows.Close() // BUG: connection giữ đến function return

        var orders []Order
        for rows.Next() {
            var o Order
            if err := rows.Scan(&o.ID, &o.UserID, &o.Amount); err != nil {
                return nil, err
            }
            orders = append(orders, o)
        }
        result[uid] = orders
    }

    return result, nil // Tất cả rows close ở đây - pool có thể cạn
}
```

**GOOD - Extract thành function hoặc close thủ công:**
```go
package importer

import (
    "encoding/json"
    "fmt"
    "os"
)

type Record struct {
    ID   string `json:"id"`
    Data string `json:"data"`
}

// GOOD: Extract function riêng - defer hoạt động đúng per-file
func ImportAllJSON(paths []string) ([]Record, error) {
    var allRecords []Record

    for _, path := range paths {
        records, err := importOneFile(path)
        if err != nil {
            return nil, fmt.Errorf("import %s: %w", path, err)
        }
        allRecords = append(allRecords, records...)
    }

    return allRecords, nil
}

func importOneFile(path string) ([]Record, error) {
    f, err := os.Open(path)
    if err != nil {
        return nil, err
    }
    defer f.Close() // Close ngay khi function này return

    var records []Record
    if err := json.NewDecoder(f).Decode(&records); err != nil {
        return nil, err
    }

    return records, nil
}

// GOOD: Dùng closure (anonymous function) khi không muốn tạo function riêng
func ImportAllJSONAlt(paths []string) ([]Record, error) {
    var allRecords []Record

    for _, path := range paths {
        records, err := func() ([]Record, error) {
            f, err := os.Open(path)
            if err != nil {
                return nil, err
            }
            defer f.Close() // Close khi closure return

            var records []Record
            if err := json.NewDecoder(f).Decode(&records); err != nil {
                return nil, err
            }
            return records, nil
        }()

        if err != nil {
            return nil, fmt.Errorf("import %s: %w", path, err)
        }
        allRecords = append(allRecords, records...)
    }

    return allRecords, nil
}

// GOOD: DB query trong loop - extract function
func FetchAllUserOrders(db *sql.DB, userIDs []int64) (map[int64][]Order, error) {
    result := make(map[int64][]Order)

    for _, uid := range userIDs {
        orders, err := fetchUserOrders(db, uid)
        if err != nil {
            return nil, fmt.Errorf("fetch orders for user %d: %w", uid, err)
        }
        result[uid] = orders
    }

    return result, nil
}

func fetchUserOrders(db *sql.DB, userID int64) ([]Order, error) {
    rows, err := db.Query("SELECT id, user_id, amount FROM orders WHERE user_id = $1", userID)
    if err != nil {
        return nil, err
    }
    defer rows.Close() // Close khi function này return

    var orders []Order
    for rows.Next() {
        var o Order
        if err := rows.Scan(&o.ID, &o.UserID, &o.Amount); err != nil {
            return nil, err
        }
        orders = append(orders, o)
    }

    if err := rows.Err(); err != nil {
        return nil, err
    }

    return orders, nil
}
```

### Phòng ngừa

```
Checklist:
- [ ] KHÔNG BAO GIỜ đặt defer trong for loop
- [ ] Extract loop body thành function riêng khi cần defer
- [ ] Hoặc dùng anonymous function (closure) bọc defer
- [ ] Review code khi thấy defer + for ở cùng function
- [ ] Linter phải cảnh báo defer trong loop
```

```bash
# golangci-lint với rule phát hiện defer trong loop
golangci-lint run --enable=gocritic ./...
# gocritic có check: deferInLoop

# staticcheck
staticcheck ./...

# go vet
go vet ./...

# Custom check bằng rg
rg --type go -U "for\s[^{]*\{[^}]*defer" --multiline -l
```

---

## Pattern 05: HTTP Client Không Reuse

### Tên
HTTP Client Không Reuse (HTTP Client Not Reused)

### Phân loại
Network / HTTP Client / Performance

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```
Mỗi http.Client mới = Transport mới = Connection pool mới:

  BAD: Tạo client mỗi request
  ┌─────────────────────────────────────────────┐
  │ Request 1: new Client → new Transport       │
  │            → TCP handshake → TLS handshake  │
  │            → Request → Response             │
  │            → Connection idle (không reuse)  │
  │                                             │
  │ Request 2: new Client → new Transport       │
  │            → TCP handshake → TLS handshake  │ ← Lặp lại!
  │            → Request → Response             │
  │            → Connection idle (không reuse)  │
  │                                             │
  │ Cost per request: ~100-300ms overhead       │
  │ Tổng N requests: N * (TCP + TLS + idle)    │
  └─────────────────────────────────────────────┘

  GOOD: Reuse client = Reuse connection pool
  ┌─────────────────────────────────────────────┐
  │ Client (shared) → Transport → Pool          │
  │                                             │
  │ Request 1: reuse conn → Request → Response  │
  │            → conn back to pool              │
  │                                             │
  │ Request 2: reuse conn → Request → Response  │ ← Reuse!
  │            → conn back to pool              │
  │                                             │
  │ Cost per request: ~1-5ms overhead           │
  │ TCP + TLS chỉ xảy ra 1 lần                │
  └─────────────────────────────────────────────┘
```

`http.Client` quản lý connection pool qua `http.Transport`. Tạo client mới mỗi request đồng nghĩa với tạo connection pool mới, mất hết benefit của HTTP keep-alive và connection reuse. Ngoài ra, transport cũ không được cleanup, gây leak goroutine (idle connection maintenance).

### Phát hiện

```bash
# Tìm http.Client{} được tạo trong function (không phải package-level)
rg --type go -n "http\.Client\{" -B 3 | grep -v "var.*http\.Client"

# Tìm &http.Client{} trong function body
rg --type go -n "&http\.Client\{" -B 5

# Tìm http.Get/Post (dùng DefaultClient - không có timeout!)
rg --type go -n "http\.(Get|Post|Head|PostForm)\(" | grep -v "_test\.go"

# Tìm Transport tạo mới trong function
rg --type go -n "http\.Transport\{" -B 3
```

### Giải pháp

**BAD - Tạo client mới mỗi request:**
```go
package gateway

import (
    "encoding/json"
    "fmt"
    "net/http"
    "time"
)

// BAD: Tạo client mới mỗi lần gọi
func FetchOrder(orderID string) (*Order, error) {
    // Mỗi lần gọi = client mới = transport mới = connection pool mới
    client := &http.Client{
        Timeout: 10 * time.Second,
    }

    resp, err := client.Get(fmt.Sprintf("https://api.orders.internal/v1/orders/%s", orderID))
    if err != nil {
        return nil, err
    }
    defer resp.Body.Close()

    var order Order
    if err := json.NewDecoder(resp.Body).Decode(&order); err != nil {
        return nil, err
    }
    return &order, nil
}

// BAD: Dùng http.Get() - default client không có timeout
func CheckHealth(url string) bool {
    // http.Get dùng http.DefaultClient:
    // - Timeout = 0 (không timeout!)
    // - Có thể hang vĩnh viễn
    resp, err := http.Get(url)
    if err != nil {
        return false
    }
    defer resp.Body.Close()
    return resp.StatusCode == 200
}
```

**GOOD - Reuse client, cấu hình transport đúng cách:**
```go
package gateway

import (
    "context"
    "encoding/json"
    "fmt"
    "io"
    "net"
    "net/http"
    "time"
)

// GOOD: Package-level client, reuse across all requests
var orderClient = NewHTTPClient(30*time.Second, 100, 10)

func NewHTTPClient(timeout time.Duration, maxConnsPerHost, maxIdleConns int) *http.Client {
    transport := &http.Transport{
        // Connection pool settings
        MaxIdleConns:        maxIdleConns * 10, // Total idle conns
        MaxIdleConnsPerHost: maxIdleConns,       // Per-host idle conns
        MaxConnsPerHost:     maxConnsPerHost,     // Per-host max conns
        IdleConnTimeout:     90 * time.Second,

        // Timeouts cho connection setup
        DialContext: (&net.Dialer{
            Timeout:   5 * time.Second,
            KeepAlive: 30 * time.Second,
        }).DialContext,
        TLSHandshakeTimeout:   5 * time.Second,
        ResponseHeaderTimeout: 10 * time.Second,
        ExpectContinueTimeout: 1 * time.Second,

        // Enable HTTP/2
        ForceAttemptHTTP2: true,
    }

    return &http.Client{
        Timeout:   timeout,
        Transport: transport,
    }
}

// GOOD: Reuse shared client
func FetchOrder(ctx context.Context, orderID string) (*Order, error) {
    url := fmt.Sprintf("https://api.orders.internal/v1/orders/%s", orderID)

    req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
    if err != nil {
        return nil, fmt.Errorf("create request: %w", err)
    }

    resp, err := orderClient.Do(req)
    if err != nil {
        return nil, fmt.Errorf("fetch order %s: %w", orderID, err)
    }
    defer func() {
        _, _ = io.Copy(io.Discard, resp.Body)
        resp.Body.Close()
    }()

    if resp.StatusCode != http.StatusOK {
        body, _ := io.ReadAll(io.LimitReader(resp.Body, 1024))
        return nil, fmt.Errorf("order API status %d: %s", resp.StatusCode, body)
    }

    var order Order
    if err := json.NewDecoder(resp.Body).Decode(&order); err != nil {
        return nil, fmt.Errorf("decode order: %w", err)
    }

    return &order, nil
}

// GOOD: Health check với context và shared client
func CheckHealth(ctx context.Context, url string) bool {
    req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
    if err != nil {
        return false
    }

    resp, err := orderClient.Do(req)
    if err != nil {
        return false
    }
    defer func() {
        _, _ = io.Copy(io.Discard, resp.Body)
        resp.Body.Close()
    }()

    return resp.StatusCode == http.StatusOK
}
```

### Phòng ngừa

```
Checklist:
- [ ] KHÔNG tạo http.Client{} trong function body (trừ trường hợp đặc biệt)
- [ ] Dùng package-level hoặc struct-level shared client
- [ ] KHÔNG dùng http.Get/Post/Head (default client không có timeout)
- [ ] Cấu hình Transport: MaxIdleConns, MaxConnsPerHost, timeouts
- [ ] Luôn dùng http.NewRequestWithContext (context propagation)
- [ ] Drain body trước khi close để reuse connection
```

```bash
# golangci-lint kiểm tra HTTP client usage
golangci-lint run --enable=noctx,bodyclose ./...
# noctx: phát hiện http request không dùng context

# Tìm http.Get/Post usage (nên thay bằng client.Do)
rg --type go "http\.(Get|Post|Head|PostForm)\(" | grep -v "_test\.go"

# staticcheck
staticcheck ./...
```

---

## Pattern 06: TCP Connection Leak

### Tên
TCP Connection Leak (Rò Rỉ TCP Connection)

### Phân loại
Network / TCP / Connection Management

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```
HTTP/1.1 Keep-Alive và Connection Reuse:

  Client                              Server
    │                                   │
    │── GET /api/data ─────────────────▶│
    │◀─ 200 OK + Body ─────────────────│
    │                                   │
    │   Connection: keep-alive          │
    │   Body phải được đọc hết         │
    │   để connection reuse!            │
    │                                   │

  Khi body KHÔNG đọc hết:
  ┌─────────────────────────────────────────────┐
  │ resp.Body chứa data chưa đọc               │
  │      │                                      │
  │      ▼                                      │
  │ resp.Body.Close() gọi nhưng:               │
  │   - Data chưa đọc vẫn trong buffer         │
  │   - Transport không biết body đã xong      │
  │   - Connection KHÔNG thể reuse             │
  │   - Connection bị đóng (close)             │
  │      │                                      │
  │      ▼                                      │
  │ Request tiếp theo:                          │
  │   - Phải tạo TCP connection mới            │
  │   - TCP handshake: ~1 RTT                  │
  │   - TLS handshake: ~2 RTT                  │
  │   - Tổng overhead: 100-300ms               │
  │                                             │
  │ Với high-throughput service:                │
  │   - 10,000 req/s × 200ms overhead          │
  │   - = Cần 2,000 concurrent connections     │
  │   - = Port exhaustion, TIME_WAIT flood     │
  └─────────────────────────────────────────────┘
```

Trong Go HTTP client, connection chỉ được tái sử dụng nếu response body được đọc hết VÀ close. Nếu chỉ close mà không drain body, transport phải đóng TCP connection và tạo connection mới cho request tiếp theo. Điều này gây performance degradation nghiêm trọng và có thể dẫn đến port exhaustion.

### Phát hiện

Dấu hiệu:
- `netstat -an | grep TIME_WAIT | wc -l` rất cao
- Số TCP connection tăng liên tục dù traffic ổn định
- HTTP latency tăng do TCP/TLS handshake mỗi request

```bash
# Tìm resp.Body.Close() mà không có drain trước đó
rg --type go -n "resp\.Body\.Close\(\)" -B 5 | grep -v "io\.Copy\|io\.ReadAll\|ioutil\.ReadAll\|Discard"

# Tìm pattern: check status → return error mà không drain body
rg --type go -n "resp\.StatusCode" -A 5 | rg "return.*err"

# Tìm nơi close body nhưng có thể chưa đọc hết
rg --type go -n "defer resp\.Body\.Close" -A 10

# Kiểm tra runtime
# ss -s | grep TIME-WAIT (trên Linux)
# netstat -an | grep TIME_WAIT | wc -l
```

### Giải pháp

**BAD - Body không được drain trước khi close:**
```go
package httpclient

import (
    "encoding/json"
    "fmt"
    "net/http"
)

// BAD: body không drain → connection không reuse
func GetUserStatus(client *http.Client, url string) (string, error) {
    resp, err := client.Get(url)
    if err != nil {
        return "", err
    }
    defer resp.Body.Close() // Close nhưng không drain!

    if resp.StatusCode == http.StatusNotFound {
        return "not_found", nil // Body chưa đọc → connection không reuse
    }

    if resp.StatusCode != http.StatusOK {
        return "", fmt.Errorf("status: %d", resp.StatusCode) // Body chưa đọc
    }

    var result struct {
        Status string `json:"status"`
    }
    if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
        return "", err // Body đọc dở → connection không reuse
    }

    return result.Status, nil
}

// BAD: chỉ lấy header, body bị bỏ qua
func GetContentType(client *http.Client, url string) (string, error) {
    resp, err := client.Get(url)
    if err != nil {
        return "", err
    }
    defer resp.Body.Close()
    // LEAK: body không drain → mỗi request tạo connection mới
    return resp.Header.Get("Content-Type"), nil
}
```

**GOOD - Luôn drain body trước khi close:**
```go
package httpclient

import (
    "encoding/json"
    "fmt"
    "io"
    "net/http"
)

// drainAndClose đảm bảo body luôn được drain trước khi close
func drainAndClose(body io.ReadCloser) {
    _, _ = io.Copy(io.Discard, body)
    body.Close()
}

// GOOD: body luôn được drain
func GetUserStatus(client *http.Client, url string) (string, error) {
    resp, err := client.Get(url)
    if err != nil {
        return "", fmt.Errorf("get %s: %w", url, err)
    }
    defer drainAndClose(resp.Body)

    if resp.StatusCode == http.StatusNotFound {
        return "not_found", nil // Body sẽ được drain bởi defer
    }

    if resp.StatusCode != http.StatusOK {
        // Đọc body error để log (giới hạn size)
        errBody, _ := io.ReadAll(io.LimitReader(resp.Body, 1024))
        return "", fmt.Errorf("status %d: %s", resp.StatusCode, string(errBody))
    }

    var result struct {
        Status string `json:"status"`
    }
    if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
        return "", fmt.Errorf("decode: %w", err)
    }

    return result.Status, nil
}

// GOOD: chỉ cần header → dùng HEAD request hoặc drain body
func GetContentType(client *http.Client, url string) (string, error) {
    // Option 1: HEAD request (không có body)
    resp, err := client.Head(url)
    if err != nil {
        return "", fmt.Errorf("head %s: %w", url, err)
    }
    defer resp.Body.Close() // HEAD response thường không có body

    return resp.Header.Get("Content-Type"), nil
}

// GOOD: Helper cho tất cả HTTP calls
func doJSON[T any](client *http.Client, req *http.Request) (*T, error) {
    resp, err := client.Do(req)
    if err != nil {
        return nil, fmt.Errorf("do request: %w", err)
    }
    defer func() {
        // Luôn drain body dù đã đọc hay chưa
        _, _ = io.Copy(io.Discard, resp.Body)
        resp.Body.Close()
    }()

    if resp.StatusCode < 200 || resp.StatusCode >= 300 {
        body, _ := io.ReadAll(io.LimitReader(resp.Body, 4096))
        return nil, fmt.Errorf("status %d: %s", resp.StatusCode, body)
    }

    var result T
    if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
        return nil, fmt.Errorf("decode: %w", err)
    }

    return &result, nil
}
```

### Phòng ngừa

```
Checklist:
- [ ] Luôn drain body: io.Copy(io.Discard, resp.Body) trước Close
- [ ] Viết helper drainAndClose() dùng chung
- [ ] Dùng HEAD request khi chỉ cần headers
- [ ] Giới hạn body size khi đọc: io.LimitReader(resp.Body, maxSize)
- [ ] Monitor TIME_WAIT count và TCP connection churn
- [ ] Dùng HTTP/2 khi có thể (multiplexing giảm connection overhead)
```

```bash
# golangci-lint với bodyclose
golangci-lint run --enable=bodyclose ./...

# Tìm Close() mà không có drain
rg --type go -n "Body\.Close" -B 3 | grep -v "Discard\|ReadAll\|Copy"

# Monitor TCP connections (Linux)
# watch -n1 'ss -s | grep -E "TCP|estab|timewait"'

# go vet
go vet ./...
```

---

## Pattern 07: Temp File Không Cleanup

### Tên
Temp File Không Cleanup (Temporary File Not Cleaned Up)

### Phân loại
OS / File System / Disk Management

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```
Vòng đời Temp File:

  os.CreateTemp("", "upload-*.dat")
       │
       ▼
  /tmp/upload-123456.dat  ◄── File tạo trên disk
       │
       ├── Xử lý xong
       │       │
       │       ├── GOOD: os.Remove(f.Name()) → file xóa
       │       │
       │       └── BAD: quên Remove
       │               │
       │               ▼
       │         File ở lại /tmp mãi mãi
       │         (trừ khi OS cleanup tmpdir)
       │
       └── Lỗi giữa chừng
               │
               └── BAD: return err mà không cleanup
                       │
                       ▼
                 Orphaned temp file trên disk

  Tích lũy theo thời gian:
  ┌─────────────────────────────────────────┐
  │  Day 1:  100 temp files =    10 MB     │
  │  Day 7:  700 temp files =    70 MB     │
  │  Day 30: 3000 temp files =   300 MB    │
  │  Day 90: orphaned files lấp đầy /tmp   │
  │           → disk full                   │
  │           → service crash               │
  │           → other services on same host │
  │             cũng bị ảnh hưởng           │
  └─────────────────────────────────────────┘
```

`os.CreateTemp()` tạo file tạm trên disk nhưng KHÔNG tự xóa khi process kết thúc (khác với tmpfs mount). Nếu không có `defer os.Remove(f.Name())`, temp files tích lũy dần và cuối cùng lấp đầy disk.

### Phát hiện

Dấu hiệu:
- `/tmp` hoặc temp directory đầy dần
- `du -sh /tmp` tăng liên tục
- Disk usage alert từ monitoring

```bash
# Tìm os.CreateTemp mà không có os.Remove
rg --type go -n "os\.CreateTemp\|ioutil\.TempFile" -A 10 | grep -v "os\.Remove\|defer"

# Tìm tất cả file tạo temp
rg --type go -n "os\.CreateTemp\|ioutil\.TempFile" -l

# Tìm os.MkdirTemp mà không cleanup
rg --type go -n "os\.MkdirTemp\|ioutil\.TempDir" -A 10 | grep -v "os\.RemoveAll\|defer"

# Kiểm tra temp files trên server
# ls -la /tmp/ | grep -E "upload|tmp|temp" | wc -l
# find /tmp -name "*.dat" -mtime +1 -ls
```

### Giải pháp

**BAD - Temp file không được cleanup:**
```go
package upload

import (
    "fmt"
    "io"
    "net/http"
    "os"
)

// BAD: temp file không được xóa sau khi xử lý
func HandleUpload(w http.ResponseWriter, r *http.Request) {
    file, _, err := r.FormFile("document")
    if err != nil {
        http.Error(w, "bad request", http.StatusBadRequest)
        return
    }
    defer file.Close()

    // Tạo temp file để lưu upload
    tmp, err := os.CreateTemp("", "upload-*.pdf")
    if err != nil {
        http.Error(w, "internal error", http.StatusInternalServerError)
        return
    }
    // MISSING: defer os.Remove(tmp.Name())

    if _, err := io.Copy(tmp, file); err != nil {
        tmp.Close()
        // BUG: return mà không xóa temp file
        http.Error(w, "write failed", http.StatusInternalServerError)
        return
    }
    tmp.Close()

    // Xử lý file...
    if err := processDocument(tmp.Name()); err != nil {
        // BUG: temp file vẫn ở trên disk
        http.Error(w, "process failed", http.StatusInternalServerError)
        return
    }

    // Quên xóa temp file ở happy path
    w.WriteHeader(http.StatusOK)
}

// BAD: temp directory không cleanup
func ExtractArchive(archivePath string) ([]string, error) {
    tmpDir, err := os.MkdirTemp("", "extract-*")
    if err != nil {
        return nil, err
    }
    // MISSING: defer os.RemoveAll(tmpDir)

    // Extract vào tmpDir...
    files, err := doExtract(archivePath, tmpDir)
    if err != nil {
        return nil, err // LEAK: tmpDir và contents ở lại disk
    }

    return files, nil
}
```

**GOOD - Temp file luôn được cleanup:**
```go
package upload

import (
    "fmt"
    "io"
    "net/http"
    "os"
)

// GOOD: defer remove ngay sau khi tạo temp file
func HandleUpload(w http.ResponseWriter, r *http.Request) {
    file, header, err := r.FormFile("document")
    if err != nil {
        http.Error(w, "bad request", http.StatusBadRequest)
        return
    }
    defer file.Close()

    // Validate file size
    if header.Size > 50*1024*1024 { // 50MB max
        http.Error(w, "file too large", http.StatusRequestEntityTooLarge)
        return
    }

    // Tạo temp file
    tmp, err := os.CreateTemp("", "upload-*.pdf")
    if err != nil {
        http.Error(w, "internal error", http.StatusInternalServerError)
        return
    }
    tmpPath := tmp.Name()

    // MUST: defer remove ngay sau khi tạo
    defer os.Remove(tmpPath)

    // Copy upload vào temp file
    if _, err := io.Copy(tmp, file); err != nil {
        tmp.Close()
        http.Error(w, "write failed", http.StatusInternalServerError)
        return
    }

    // Close trước khi process (flush data)
    if err := tmp.Close(); err != nil {
        http.Error(w, "close failed", http.StatusInternalServerError)
        return
    }

    // Xử lý file - temp file tự cleanup dù thành công hay thất bại
    if err := processDocument(tmpPath); err != nil {
        http.Error(w, "process failed", http.StatusInternalServerError)
        return // defer os.Remove sẽ cleanup
    }

    w.WriteHeader(http.StatusOK)
}

// GOOD: temp directory với proper cleanup
func ExtractArchive(archivePath string) (extractedFiles []string, err error) {
    tmpDir, err := os.MkdirTemp("", "extract-*")
    if err != nil {
        return nil, fmt.Errorf("create temp dir: %w", err)
    }
    defer os.RemoveAll(tmpDir) // Cleanup toàn bộ directory

    files, err := doExtract(archivePath, tmpDir)
    if err != nil {
        return nil, fmt.Errorf("extract: %w", err)
    }

    // Copy files ra nơi khác trước khi tmpDir bị xóa
    var finalPaths []string
    for _, f := range files {
        destPath, err := copyToStorage(f)
        if err != nil {
            return nil, fmt.Errorf("copy to storage: %w", err)
        }
        finalPaths = append(finalPaths, destPath)
    }

    return finalPaths, nil
}

// GOOD: Helper pattern cho temp file lifecycle
func withTempFile(pattern string, fn func(f *os.File) error) error {
    tmp, err := os.CreateTemp("", pattern)
    if err != nil {
        return fmt.Errorf("create temp: %w", err)
    }

    // Cleanup: close + remove
    defer func() {
        tmp.Close()
        os.Remove(tmp.Name())
    }()

    return fn(tmp)
}
```

### Phòng ngừa

```
Checklist:
- [ ] Mỗi os.CreateTemp PHẢI có defer os.Remove(f.Name()) ngay sau
- [ ] Mỗi os.MkdirTemp PHẢI có defer os.RemoveAll(dir) ngay sau
- [ ] Close file TRƯỚC khi process (flush data ra disk)
- [ ] Validate file size trước khi write vào temp
- [ ] Viết helper withTempFile() cho pattern lặp lại
- [ ] Cron job cleanup temp files cũ (safety net)
```

```bash
# golangci-lint
golangci-lint run --enable=gocritic,gosec ./...

# Tìm CreateTemp thiếu Remove
rg --type go "CreateTemp\|TempFile" -l | while read f; do
  creates=$(rg -c "CreateTemp\|TempFile" "$f")
  removes=$(rg -c "os\.Remove" "$f")
  if [ "$creates" -gt "$removes" ]; then
    echo "SUSPECT: $f (creates=$creates, removes=$removes)"
  fi
done

# Cron job cleanup (production safety net)
# 0 */6 * * * find /tmp -name "upload-*" -mmin +360 -delete
# 0 */6 * * * find /tmp -name "extract-*" -type d -mmin +360 -exec rm -rf {} +
```

---

## Pattern 08: CGo Memory Leak

### Tên
CGo Memory Leak (Rò Rỉ Bộ Nhớ CGo)

### Phân loại
CGo / Memory Management / FFI

### Mức nghiêm trọng
CRITICAL 🔴

### Vấn đề

```
Go Memory vs C Memory:

  Go Heap (managed by GC)          C Heap (manual management)
  ┌──────────────────────┐         ┌──────────────────────┐
  │                      │         │                      │
  │  var s = "hello"     │         │  cs := C.CString(s)  │
  │  → GC tự giải phóng  │         │  → malloc() trong C  │
  │                      │         │  → GC KHÔNG biết!    │
  │  make([]byte, 1024)  │         │  → PHẢI gọi C.free() │
  │  → GC tự giải phóng  │         │  → Nếu quên → LEAK  │
  │                      │         │                      │
  └──────────────────────┘         └──────────────────────┘
         │                                │
         ▼                                ▼
    GC tracks & frees              Developer MUST free
    automatically                  manually with C.free()

  Lifecycle của C.CString:

  Go string "hello"
       │
       ▼
  C.CString("hello")
       │
       ▼
  malloc(6) trong C heap  ◄── 6 bytes (5 + null terminator)
       │
       ├── C.free(unsafe.Pointer(cs))  → Memory giải phóng ✓
       │
       └── Quên C.free()
               │
               ▼
          Memory leak mãi mãi
          GC không thể thu hồi
          Process RSS tăng vô hạn
          → OOM kill sau vài giờ/ngày
```

Khi dùng CGo, Go GC KHÔNG quản lý memory được allocate bởi C runtime. `C.CString()` gọi `malloc()` bên C, và developer PHẢI gọi `C.free()` để giải phóng. Đây là nguyên nhân phổ biến nhất gây memory leak trong Go applications dùng CGo.

### Phát hiện

Dấu hiệu:
- Process RSS tăng liên tục mà GC không thu hồi
- `runtime.MemStats.Sys` ổn định nhưng OS RSS tăng
- `pprof heap` cho thấy Go heap nhỏ nhưng process memory lớn

```bash
# Tìm C.CString mà không có C.free
rg --type go -n "C\.CString\(" -A 5 | grep -v "C\.free\|defer"

# Tìm tất cả CGo allocation
rg --type go -n "C\.CString\|C\.CBytes\|C\.malloc" -l

# Tìm C.CString mà không có C.free trong cùng function
rg --type go -n "C\.CString\(" -l | while read f; do
  cstrings=$(rg -c "C\.CString" "$f")
  cfrees=$(rg -c "C\.free" "$f")
  if [ "$cstrings" -gt "$cfrees" ]; then
    echo "LEAK SUSPECT: $f (CString=$cstrings, free=$cfrees)"
  fi
done

# Tìm CGo import
rg --type go -n "import \"C\"" -l
```

### Giải pháp

**BAD - C memory không được free:**
```go
package crypto

/*
#include <stdlib.h>
#include <string.h>
#include <openssl/evp.h>
#include <openssl/sha.h>

unsigned char* hash_sha256(const char* input, int len) {
    unsigned char* digest = (unsigned char*)malloc(SHA256_DIGEST_LENGTH);
    SHA256((unsigned char*)input, len, digest);
    return digest;
}

void encrypt_data(const char* key, const char* plaintext, char* out) {
    // ... encryption logic ...
}
*/
import "C"
import (
    "fmt"
    "unsafe"
)

// BAD: C.CString leak - không free
func HashPassword(password string) ([]byte, error) {
    cPassword := C.CString(password) // malloc() trong C
    // MISSING: defer C.free(unsafe.Pointer(cPassword))

    result := C.hash_sha256(cPassword, C.int(len(password)))
    // MISSING: defer C.free(unsafe.Pointer(result))

    // Copy result vào Go slice
    hash := C.GoBytes(unsafe.Pointer(result), C.SHA256_DIGEST_LENGTH)

    return hash, nil
    // cPassword và result leak mãi mãi
}

// BAD: leak trong loop - nhanh chóng OOM
func EncryptBatch(key string, plaintexts []string) error {
    cKey := C.CString(key) // malloc
    // MISSING: C.free cho cKey

    for _, pt := range plaintexts {
        cPT := C.CString(pt) // malloc mỗi iteration
        // MISSING: C.free cho cPT

        var outBuf [1024]C.char
        C.encrypt_data(cKey, cPT, &outBuf[0])
        // cPT leak mỗi iteration!
    }

    return nil
}
```

**GOOD - C memory luôn được free đúng cách:**
```go
package crypto

/*
#include <stdlib.h>
#include <string.h>
#include <openssl/evp.h>
#include <openssl/sha.h>

unsigned char* hash_sha256(const char* input, int len) {
    unsigned char* digest = (unsigned char*)malloc(SHA256_DIGEST_LENGTH);
    SHA256((unsigned char*)input, len, digest);
    return digest;
}

void encrypt_data(const char* key, const char* plaintext, char* out) {
    // ... encryption logic ...
}
*/
import "C"
import (
    "fmt"
    "unsafe"
)

// GOOD: tất cả C allocations đều có defer free
func HashPassword(password string) ([]byte, error) {
    cPassword := C.CString(password)
    defer C.free(unsafe.Pointer(cPassword)) // MUST: free ngay sau allocate

    result := C.hash_sha256(cPassword, C.int(len(password)))
    if result == nil {
        return nil, fmt.Errorf("hash failed")
    }
    defer C.free(unsafe.Pointer(result)) // MUST: free return value từ C

    // Copy vào Go memory trước khi C memory được free
    hash := C.GoBytes(unsafe.Pointer(result), C.SHA256_DIGEST_LENGTH)

    return hash, nil // defer sẽ free cPassword và result
}

// GOOD: free trong mỗi iteration
func EncryptBatch(key string, plaintexts []string) error {
    cKey := C.CString(key)
    defer C.free(unsafe.Pointer(cKey))

    for _, pt := range plaintexts {
        if err := encryptOne(cKey, pt); err != nil {
            return fmt.Errorf("encrypt %q: %w", pt, err)
        }
    }

    return nil
}

// Helper: encapsulate C allocation/free
func encryptOne(cKey *C.char, plaintext string) error {
    cPT := C.CString(plaintext)
    defer C.free(unsafe.Pointer(cPT)) // Free khi function return

    var outBuf [1024]C.char
    C.encrypt_data(cKey, cPT, &outBuf[0])

    return nil
}

// GOOD: Helper pattern cho CGo string conversion
func withCString(s string, fn func(*C.char)) {
    cs := C.CString(s)
    defer C.free(unsafe.Pointer(cs))
    fn(cs)
}

// Usage:
// withCString(password, func(cs *C.char) {
//     C.some_c_function(cs)
// })
```

### Phòng ngừa

```
Checklist:
- [ ] Mỗi C.CString() PHẢI có defer C.free(unsafe.Pointer(...)) ngay sau
- [ ] Mỗi C.CBytes() PHẢI có defer C.free(unsafe.Pointer(...)) ngay sau
- [ ] Return value từ C function nếu là pointer → PHẢI free
- [ ] Trong loop: extract function riêng hoặc free trong mỗi iteration
- [ ] Viết helper withCString() cho pattern lặp lại
- [ ] Monitor RSS vs Go heap size (RSS >> heap = C leak)
- [ ] Dùng valgrind hoặc AddressSanitizer cho CGo code
```

```bash
# golangci-lint
golangci-lint run --enable=gocritic,gosec ./...

# Tìm CGo files cần review
rg --type go "import \"C\"" -l

# Custom check: CString phải có C.free
rg --type go "C\.CString" -l | while read f; do
  echo "=== Checking $f ==="
  rg -n "C\.CString\|C\.free" "$f"
done

# Build với memory sanitizer (nếu hỗ trợ)
# CGO_ENABLED=1 go test -msan ./...

# Dùng valgrind (Linux)
# CGO_ENABLED=1 go build -o app .
# valgrind --leak-check=full ./app
```

---

## Pattern 09: Context Leak

### Tên
Context Leak (Rò Rỉ Context)

### Phân loại
Concurrency / Context / Resource Management

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```
Context Tree:

  context.Background()
       │
       ├── WithCancel() → ctx1, cancel1
       │       │
       │       ├── WithTimeout() → ctx2, cancel2
       │       │       │
       │       │       └── goroutine đợi ctx2.Done()
       │       │
       │       └── WithValue() → ctx3 (không cần cancel)
       │
       └── WithDeadline() → ctx4, cancel4
               │
               └── goroutine đợi ctx4.Done()

  Khi cancel function KHÔNG được gọi:
  ┌──────────────────────────────────────────────┐
  │ ctx, cancel := context.WithCancel(parent)    │
  │      │                                       │
  │      ▼                                       │
  │ Go runtime tạo:                              │
  │   - goroutine theo dõi parent cancellation   │
  │   - timer (cho WithTimeout/WithDeadline)     │
  │   - channel (ctx.Done())                     │
  │                                              │
  │ Nếu cancel() không được gọi:                │
  │   - Goroutine theo dõi parent → LEAK         │
  │   - Timer không stop → memory tích lũy       │
  │   - Resources giữ cho đến parent cancel     │
  │   - Nếu parent = Background() → NEVER freed │
  │                                              │
  │ Hậu quả:                                    │
  │   - Goroutine count tăng dần                │
  │   - Memory tăng dần                          │
  │   - Cuối cùng OOM                           │
  └──────────────────────────────────────────────┘
```

`context.WithCancel`, `context.WithTimeout`, và `context.WithDeadline` đều trả về cancel function. Nếu không gọi cancel, resources bên trong context (goroutines, timers) bị leak cho đến khi parent context bị cancel. Với `context.Background()` làm parent, resources KHÔNG BAO GIỜ được giải phóng.

### Phát hiện

Dấu hiệu:
- Goroutine count tăng dần (pprof goroutine profile)
- `context.propagateCancel` xuất hiện trong goroutine stack
- Memory tăng chậm theo thời gian

```bash
# Tìm WithCancel/WithTimeout/WithDeadline mà không có defer cancel
rg --type go -n "context\.With(Cancel|Timeout|Deadline)\(" -A 3 | grep -v "defer.*cancel\|defer.*stop"

# Tìm cancel function bị ignore (assign to _)
rg --type go -n "_, _ = context\.With\|_ = context\.With"

# Tìm context tạo mà cancel không được gọi
rg --type go -n "context\.With(Cancel|Timeout|Deadline)" -l

# Tìm pattern: tạo context nhưng discard cancel
rg --type go -n ",\s*_\s*:?=\s*context\.With"
```

### Giải pháp

**BAD - Cancel function không được gọi:**
```go
package service

import (
    "context"
    "database/sql"
    "fmt"
    "net/http"
    "time"
)

// BAD: cancel function bị discard
func GetUser(db *sql.DB, userID int64) (*User, error) {
    ctx, _ := context.WithTimeout(context.Background(), 5*time.Second)
    // BUG: cancel function bị bỏ qua bằng _
    // Timer và goroutine leak cho đến khi timeout

    row := db.QueryRowContext(ctx, "SELECT id, name FROM users WHERE id = $1", userID)
    var user User
    if err := row.Scan(&user.ID, &user.Name); err != nil {
        return nil, err
    }
    return &user, nil
}

// BAD: cancel function lưu nhưng không gọi ở tất cả paths
func FetchData(client *http.Client, url string) ([]byte, error) {
    ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)

    req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
    if err != nil {
        return nil, err // LEAK: cancel không được gọi
    }

    resp, err := client.Do(req)
    if err != nil {
        return nil, err // LEAK: cancel không được gọi
    }
    defer resp.Body.Close()

    // Chỉ cancel ở happy path
    cancel()

    body, err := io.ReadAll(resp.Body)
    if err != nil {
        return nil, err
    }

    return body, nil
}

// BAD: context trong goroutine mà không cancel khi goroutine xong
func ProcessAsync(parentCtx context.Context, data []byte) {
    ctx, cancel := context.WithCancel(parentCtx)
    // MISSING: cancel không bao giờ được gọi

    go func() {
        // Làm việc với ctx
        result := process(ctx, data)
        saveResult(result)
        // BUG: cancel() không gọi khi goroutine hoàn thành
    }()
}
```

**GOOD - Cancel function luôn được gọi qua defer:**
```go
package service

import (
    "context"
    "database/sql"
    "fmt"
    "io"
    "net/http"
    "time"
)

// GOOD: defer cancel ngay sau khi tạo context
func GetUser(db *sql.DB, userID int64) (*User, error) {
    ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
    defer cancel() // MUST: luôn defer cancel ngay lập tức

    row := db.QueryRowContext(ctx, "SELECT id, name FROM users WHERE id = $1", userID)
    var user User
    if err := row.Scan(&user.ID, &user.Name); err != nil {
        return nil, fmt.Errorf("scan user %d: %w", userID, err)
    }
    return &user, nil
}

// GOOD: defer cancel ở đầu function
func FetchData(client *http.Client, url string) ([]byte, error) {
    ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
    defer cancel() // Cancel ở mọi exit path

    req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
    if err != nil {
        return nil, fmt.Errorf("create request: %w", err)
    }

    resp, err := client.Do(req)
    if err != nil {
        return nil, fmt.Errorf("do request: %w", err)
    }
    defer func() {
        _, _ = io.Copy(io.Discard, resp.Body)
        resp.Body.Close()
    }()

    if resp.StatusCode != http.StatusOK {
        return nil, fmt.Errorf("status %d", resp.StatusCode)
    }

    body, err := io.ReadAll(io.LimitReader(resp.Body, 10*1024*1024))
    if err != nil {
        return nil, fmt.Errorf("read body: %w", err)
    }

    return body, nil
}

// GOOD: context cho goroutine với cancel khi xong
func ProcessAsync(parentCtx context.Context, data []byte) <-chan error {
    ctx, cancel := context.WithCancel(parentCtx)
    errCh := make(chan error, 1)

    go func() {
        defer cancel() // Cancel khi goroutine hoàn thành

        result, err := process(ctx, data)
        if err != nil {
            errCh <- fmt.Errorf("process: %w", err)
            return
        }

        if err := saveResult(ctx, result); err != nil {
            errCh <- fmt.Errorf("save: %w", err)
            return
        }

        errCh <- nil
    }()

    return errCh
}

// GOOD: context cho long-running operation với cleanup
func RunWorker(parentCtx context.Context) error {
    ctx, cancel := context.WithCancel(parentCtx)
    defer cancel() // Cleanup khi worker thoát

    for {
        select {
        case <-ctx.Done():
            return ctx.Err()
        default:
            if err := doWork(ctx); err != nil {
                return fmt.Errorf("work failed: %w", err)
            }
        }
    }
}
```

### Phòng ngừa

```
Checklist:
- [ ] Mỗi context.WithCancel/Timeout/Deadline PHẢI có defer cancel() ngay sau
- [ ] KHÔNG BAO GIỜ discard cancel function (gán cho _)
- [ ] Gọi cancel() là idempotent - gọi nhiều lần cũng OK
- [ ] Trong goroutine: defer cancel() ở đầu goroutine body
- [ ] go vet cảnh báo lostcancel
```

```bash
# go vet phát hiện lost cancel (built-in check!)
go vet ./...
# go vet có check: lostcancel - phát hiện context cancel bị bỏ qua

# golangci-lint
golangci-lint run --enable=contextcheck,govet ./...

# staticcheck
staticcheck ./...
# SA4031: cancel function not called

# Tìm bằng rg để double-check
rg --type go "context\.With(Cancel|Timeout|Deadline)" -n | grep -v "defer\|cancel()"
```

---

## Pattern 10: Ticker Không Stop

### Tên
Ticker Không Stop (Ticker Not Stopped)

### Phân loại
Concurrency / Timer / Resource Leak

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```
Ticker vs Timer:

  time.NewTicker(1s)           time.NewTimer(5s)
       │                            │
       ▼                            ▼
  tick mỗi 1s vô hạn         fire 1 lần sau 5s
  [1s] → [2s] → [3s] → ...   [5s] → done
       │                            │
       ▼                            ▼
  PHẢI Stop() khi xong        Tự dọn sau khi fire
  Nếu không → goroutine +     (nhưng vẫn nên Stop
  timer leak mãi mãi          nếu không dùng)

  Ticker internal:
  ┌──────────────────────────────────────────┐
  │ time.NewTicker(interval)                 │
  │      │                                   │
  │      ▼                                   │
  │  Runtime tạo:                            │
  │    - timer goroutine (background)        │
  │    - channel C (buffered, size 1)        │
  │    - Gửi time.Time vào C mỗi interval   │
  │                                          │
  │  Nếu không Stop():                       │
  │    - Timer goroutine chạy mãi mãi       │
  │    - Channel C giữ reference             │
  │    - GC không thu hồi                    │
  │    - Mỗi ticker = 1 goroutine leak       │
  │                                          │
  │  Ví dụ: ticker trong HTTP handler        │
  │    1000 req/s × 1 ticker/req             │
  │    = 1000 ticker leak/s                  │
  │    = 3,600,000 goroutines/hour           │
  │    → OOM                                │
  └──────────────────────────────────────────┘
```

`time.NewTicker` tạo một ticker gửi tick vào channel định kỳ. Khác với `time.Timer`, ticker KHÔNG tự dừng. Nếu không gọi `ticker.Stop()`, timer goroutine và channel bị leak vĩnh viễn.

### Phát hiện

```bash
# Tìm time.NewTicker mà không có Stop
rg --type go -n "time\.NewTicker\(" -A 10 | grep -v "\.Stop\(\)\|defer"

# Tìm ticker được tạo nhưng không stop
rg --type go -n "time\.NewTicker" -l | while read f; do
  tickers=$(rg -c "NewTicker" "$f")
  stops=$(rg -c "\.Stop\(\)" "$f")
  if [ "$tickers" -gt "$stops" ]; then
    echo "SUSPECT: $f (NewTicker=$tickers, Stop=$stops)"
  fi
done

# Tìm time.Tick (không trả về ticker, KHÔNG THỂ stop!)
rg --type go -n "time\.Tick\(" | grep -v "_test\.go"

# Tìm ticker trong HTTP handler (nguy cơ cao)
rg --type go -n "time\.NewTicker\|time\.Tick" -B 10 | rg "func.*Handler\|func.*ServeHTTP"
```

### Giải pháp

**BAD - Ticker không được stop:**
```go
package monitor

import (
    "fmt"
    "log"
    "net/http"
    "time"
)

// BAD: time.Tick trong package scope - không thể stop
var metricsCh = time.Tick(30 * time.Second) // LEAK: không có cách stop

// BAD: ticker trong goroutine không stop
func StartMetricsCollector() {
    ticker := time.NewTicker(10 * time.Second)
    // MISSING: defer ticker.Stop()

    go func() {
        for range ticker.C {
            collectMetrics()
        }
    }()
    // Nếu function này được gọi nhiều lần,
    // mỗi lần tạo 1 ticker leak
}

// BAD: ticker trong HTTP handler - leak mỗi request
func LongPollHandler(w http.ResponseWriter, r *http.Request) {
    ticker := time.NewTicker(1 * time.Second)
    // MISSING: ticker.Stop()

    flusher, ok := w.(http.Flusher)
    if !ok {
        http.Error(w, "streaming not supported", 500)
        return // LEAK: ticker không stop
    }

    for i := 0; i < 30; i++ {
        select {
        case <-ticker.C:
            fmt.Fprintf(w, "data: heartbeat %d\n\n", i)
            flusher.Flush()
        case <-r.Context().Done():
            return // LEAK: ticker không stop khi client disconnect
        }
    }
    // ticker vẫn chạy sau khi handler return
}
```

**GOOD - Ticker luôn được stop:**
```go
package monitor

import (
    "context"
    "fmt"
    "log"
    "net/http"
    "time"
)

// GOOD: ticker với proper lifecycle management
func StartMetricsCollector(ctx context.Context) {
    ticker := time.NewTicker(10 * time.Second)

    go func() {
        defer ticker.Stop() // MUST: stop khi goroutine thoát

        for {
            select {
            case <-ctx.Done():
                log.Println("metrics collector stopped")
                return
            case <-ticker.C:
                if err := collectMetrics(); err != nil {
                    log.Printf("collect metrics: %v", err)
                }
            }
        }
    }()
}

// GOOD: ticker trong HTTP handler với cleanup
func LongPollHandler(w http.ResponseWriter, r *http.Request) {
    ticker := time.NewTicker(1 * time.Second)
    defer ticker.Stop() // MUST: stop khi handler return

    flusher, ok := w.(http.Flusher)
    if !ok {
        http.Error(w, "streaming not supported", 500)
        return // ticker.Stop() được gọi bởi defer
    }

    for i := 0; i < 30; i++ {
        select {
        case <-ticker.C:
            fmt.Fprintf(w, "data: heartbeat %d\n\n", i)
            flusher.Flush()
        case <-r.Context().Done():
            // Client disconnect - cleanup
            return // ticker.Stop() được gọi bởi defer
        }
    }
}

// GOOD: Reusable pattern cho periodic tasks
func RunPeriodic(ctx context.Context, interval time.Duration, task func(ctx context.Context) error) error {
    ticker := time.NewTicker(interval)
    defer ticker.Stop()

    // Chạy task ngay lập tức lần đầu
    if err := task(ctx); err != nil {
        return fmt.Errorf("initial run: %w", err)
    }

    for {
        select {
        case <-ctx.Done():
            return ctx.Err()
        case <-ticker.C:
            if err := task(ctx); err != nil {
                log.Printf("periodic task error: %v", err)
                // Tiếp tục chạy dù có lỗi
            }
        }
    }
}

// GOOD: Reset ticker khi cần thay đổi interval
func AdaptiveCollector(ctx context.Context) {
    interval := 10 * time.Second
    ticker := time.NewTicker(interval)
    defer ticker.Stop()

    for {
        select {
        case <-ctx.Done():
            return
        case <-ticker.C:
            load := getSystemLoad()

            // Điều chỉnh interval theo load
            newInterval := interval
            if load > 0.8 {
                newInterval = 30 * time.Second
            } else if load < 0.3 {
                newInterval = 5 * time.Second
            }

            if newInterval != interval {
                interval = newInterval
                ticker.Reset(interval) // Go 1.15+: reset thay vì tạo mới
            }

            collectMetrics()
        }
    }
}
```

### Phòng ngừa

```
Checklist:
- [ ] Mỗi time.NewTicker PHẢI có defer ticker.Stop()
- [ ] KHÔNG dùng time.Tick() ngoại trừ trong main/init (không thể stop)
- [ ] Ticker trong goroutine: defer Stop ở đầu goroutine
- [ ] Dùng context để control lifecycle của ticker goroutine
- [ ] Prefer ticker.Reset() (Go 1.15+) thay vì tạo mới khi đổi interval
```

```bash
# go vet
go vet ./...

# golangci-lint
golangci-lint run --enable=gocritic ./...

# staticcheck - phát hiện time.Tick usage
staticcheck ./...
# SA1015: Using time.Tick in a function that is not main or init

# Tìm time.Tick (nên thay bằng NewTicker)
rg --type go "time\.Tick\(" | grep -v "_test\.go"
```

---

## Pattern 11: Pprof Endpoint Production

### Tên
Pprof Endpoint Exposed Trong Production (Pprof Endpoint Exposed in Production)

### Phân loại
Security / Debugging / Information Disclosure

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```
net/http/pprof tự đăng ký routes vào DefaultServeMux:

  import _ "net/http/pprof"    ◄── Side effect import!
       │
       ▼
  init() tự đăng ký:
    /debug/pprof/              ◄── Index: list tất cả profiles
    /debug/pprof/cmdline       ◄── Command line arguments
    /debug/pprof/profile       ◄── CPU profile (30s mặc định)
    /debug/pprof/symbol        ◄── Symbol lookup
    /debug/pprof/trace         ◄── Execution trace
    /debug/pprof/heap          ◄── Heap memory profile
    /debug/pprof/goroutine     ◄── All goroutine stacks
    /debug/pprof/allocs        ◄── Memory allocation profile
    /debug/pprof/block         ◄── Block profile
    /debug/pprof/mutex         ◄── Mutex contention profile
    /debug/pprof/threadcreate  ◄── Thread creation profile

  Thông tin bị lộ:
  ┌──────────────────────────────────────────────┐
  │ 1. /debug/pprof/goroutine                    │
  │    → Stack traces với function names          │
  │    → Internal package paths                   │
  │    → Business logic flow                      │
  │                                               │
  │ 2. /debug/pprof/heap                          │
  │    → Memory layout của application            │
  │    → Có thể chứa sensitive data trong memory │
  │                                               │
  │ 3. /debug/pprof/cmdline                       │
  │    → Command line arguments                   │
  │    → Có thể chứa secrets, DB passwords       │
  │                                               │
  │ 4. /debug/pprof/profile                       │
  │    → CPU profile gây load tăng                │
  │    → DoS vector (30s CPU profiling)           │
  │                                               │
  │ 5. /debug/pprof/trace                         │
  │    → Execution trace chi tiết                 │
  │    → Timing information cho timing attacks    │
  └──────────────────────────────────────────────┘
```

Package `net/http/pprof` sử dụng side-effect import (`import _ "net/http/pprof"`) để tự đăng ký debug handlers vào `http.DefaultServeMux`. Nếu production server dùng `DefaultServeMux` hoặc pprof handlers được đăng ký vào production router, attacker có thể truy cập thông tin nhạy cảm và gây DoS.

### Phát hiện

```bash
# Tìm pprof import
rg --type go -n "\"net/http/pprof\""

# Tìm pprof handlers đăng ký vào router
rg --type go -n "pprof\.(Index|Cmdline|Profile|Symbol|Trace)"

# Tìm runtime/pprof usage (ít nguy hiểm hơn nhưng vẫn cần review)
rg --type go -n "\"runtime/pprof\""

# Tìm debug endpoint trong router
rg --type go -n "/debug/" | grep -v "_test\.go"

# Kiểm tra DefaultServeMux usage (pprof tự đăng ký vào đây)
rg --type go -n "http\.ListenAndServe\|http\.DefaultServeMux" | grep -v "_test\.go"

# Kiểm tra từ bên ngoài (production)
# curl -s http://production:8080/debug/pprof/ | head -5
```

### Giải pháp

**BAD - Pprof exposed trong production:**
```go
package main

import (
    "log"
    "net/http"

    _ "net/http/pprof" // BUG: side-effect import đăng ký routes
)

func main() {
    http.HandleFunc("/api/health", healthHandler)
    http.HandleFunc("/api/users", usersHandler)

    // BUG: DefaultServeMux có pprof routes từ import
    // Attacker truy cập: http://production:8080/debug/pprof/
    log.Fatal(http.ListenAndServe(":8080", nil)) // nil = DefaultServeMux
}

// BAD: pprof đăng ký vào production router
func setupRouter() *http.ServeMux {
    mux := http.NewServeMux()
    mux.HandleFunc("/api/health", healthHandler)

    // BUG: debug endpoints trong production router
    mux.HandleFunc("/debug/pprof/", pprof.Index)
    mux.HandleFunc("/debug/pprof/cmdline", pprof.Cmdline)
    mux.HandleFunc("/debug/pprof/profile", pprof.Profile)

    return mux
}
```

**GOOD - Pprof trên port riêng, chỉ enable khi cần:**
```go
package main

import (
    "context"
    "log"
    "net/http"
    "os"
    "time"
)

func main() {
    // Production router - KHÔNG có pprof
    prodMux := http.NewServeMux()
    prodMux.HandleFunc("/api/health", healthHandler)
    prodMux.HandleFunc("/api/users", usersHandler)

    prodServer := &http.Server{
        Addr:         ":8080",
        Handler:      prodMux,
        ReadTimeout:  15 * time.Second,
        WriteTimeout: 15 * time.Second,
    }

    // Debug server trên port riêng, chỉ listen localhost
    if os.Getenv("ENABLE_PPROF") == "true" {
        go startDebugServer()
    }

    log.Fatal(prodServer.ListenAndServe())
}

func startDebugServer() {
    // Import pprof chỉ trong file này (hoặc build tag)
    // Và chỉ bind localhost
    debugMux := http.NewServeMux()

    // Đăng ký pprof handlers vào debug mux riêng
    debugMux.HandleFunc("/debug/pprof/", pprofIndex)
    debugMux.HandleFunc("/debug/pprof/cmdline", pprofCmdline)
    debugMux.HandleFunc("/debug/pprof/profile", pprofProfile)
    debugMux.HandleFunc("/debug/pprof/symbol", pprofSymbol)
    debugMux.HandleFunc("/debug/pprof/trace", pprofTrace)

    debugServer := &http.Server{
        Addr:    "127.0.0.1:6060", // CHỈ localhost
        Handler: debugMux,
    }

    log.Printf("debug server listening on %s", debugServer.Addr)
    if err := debugServer.ListenAndServe(); err != nil {
        log.Printf("debug server error: %v", err)
    }
}

// GOOD: Dùng build tags để loại bỏ pprof khỏi production binary
// File: debug_pprof.go
// //go:build debug
// package main
// import _ "net/http/pprof"

// File: debug_nopprof.go
// //go:build !debug
// package main
// (empty - không import pprof)
```

```go
// GOOD: Middleware bảo vệ debug endpoints
package middleware

import (
    "net/http"
    "strings"
)

// DebugAuth middleware yêu cầu authentication cho debug endpoints
func DebugAuth(token string, next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        if strings.HasPrefix(r.URL.Path, "/debug/") {
            authHeader := r.Header.Get("Authorization")
            if authHeader != "Bearer "+token {
                http.Error(w, "unauthorized", http.StatusUnauthorized)
                return
            }
        }
        next.ServeHTTP(w, r)
    })
}

// Usage:
// debugToken := os.Getenv("DEBUG_TOKEN")
// handler := middleware.DebugAuth(debugToken, debugMux)
```

### Phòng ngừa

```
Checklist:
- [ ] KHÔNG import net/http/pprof trong production code
- [ ] Dùng build tags: //go:build debug cho pprof import
- [ ] Pprof server PHẢI bind 127.0.0.1 (localhost only)
- [ ] Pprof server trên port riêng biệt (ví dụ: 6060)
- [ ] Nếu cần pprof trong production: authentication required
- [ ] KHÔNG dùng http.DefaultServeMux cho production server
- [ ] CI/CD kiểm tra pprof import trong production builds
```

```bash
# Tìm pprof import trong non-debug files
rg --type go "\"net/http/pprof\"" | grep -v "_test\.go\|debug"

# Kiểm tra DefaultServeMux usage
rg --type go "http\.ListenAndServe\(.*nil\)" | grep -v "_test\.go"

# golangci-lint
golangci-lint run --enable=gosec ./...

# Kiểm tra port binding
rg --type go "ListenAndServe\|Listen\(" | grep -v "127\.0\.0\.1\|localhost" | grep "debug\|pprof"

# Security scan với gosec
gosec -include=G114 ./...
# G114: Use of net/http serve function without timeout
```

---

## Pattern 12: Finalizer Abuse

### Tên
Finalizer Abuse (Lạm Dụng Finalizer)

### Phân loại
Runtime / GC / Resource Management

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```
runtime.SetFinalizer hoạt động:

  obj := &MyResource{conn: openConn()}
       │
       ▼
  runtime.SetFinalizer(obj, func(r *MyResource) {
      r.conn.Close()      ◄── Chạy khi GC thu hồi obj
  })
       │
       ▼
  obj không còn reference
       │
       ▼
  GC cycle N: đánh dấu unreachable
       │
       ▼
  GC cycle N+1: chạy finalizer  ◄── Ít nhất 2 GC cycles!
       │
       ▼
  GC cycle N+2: thực sự thu hồi memory

  Vấn đề với Finalizer:
  ┌──────────────────────────────────────────────────┐
  │ 1. KHÔNG đảm bảo thời gian chạy                 │
  │    - GC có thể chạy sau vài giây hoặc vài phút │
  │    - Resources giữ quá lâu                       │
  │                                                   │
  │ 2. KHÔNG đảm bảo chạy (!)                        │
  │    - os.Exit() → finalizers KHÔNG chạy           │
  │    - Panic (nếu không recover) → có thể không   │
  │    - Program crash → không chạy                  │
  │                                                   │
  │ 3. Kéo dài GC cycle                              │
  │    - Objects có finalizer tồn tại thêm 1 GC cycle│
  │    - Tăng memory pressure                         │
  │    - GC pause time tăng                           │
  │                                                   │
  │ 4. Ordering không đảm bảo                        │
  │    - Nếu A reference B, finalizer A có thể chạy │
  │      trước hoặc sau finalizer B                  │
  │    - B có thể đã bị thu hồi khi A finalizer chạy│
  │                                                   │
  │ 5. Single goroutine                               │
  │    - Tất cả finalizers chạy trên 1 goroutine     │
  │    - Finalizer chậm block tất cả finalizers khác │
  └──────────────────────────────────────────────────┘
```

`runtime.SetFinalizer` được thiết kế cho các trường hợp đặc biệt (như `os.File` sử dụng nội bộ). Dùng finalizer để quản lý resources (connections, file handles) là anti-pattern vì không đảm bảo khi nào (hoặc có) finalizer sẽ chạy.

### Phát hiện

```bash
# Tìm SetFinalizer usage
rg --type go -n "runtime\.SetFinalizer\(" -A 5

# Tìm SetFinalizer cho resource cleanup
rg --type go -n "SetFinalizer" -A 10 | rg "Close\|Release\|Free\|Destroy"

# Tìm tất cả file sử dụng SetFinalizer
rg --type go -n "runtime\.SetFinalizer" -l

# Kiểm tra xem có explicit Close method không
rg --type go -n "SetFinalizer" -B 20 | rg "func.*Close\(\)"
```

### Giải pháp

**BAD - Dùng finalizer để quản lý resources:**
```go
package pool

import (
    "database/sql"
    "fmt"
    "net"
    "runtime"
)

type Connection struct {
    conn net.Conn
    db   *sql.DB
}

// BAD: dùng finalizer để close connection
func NewConnection(addr string, db *sql.DB) (*Connection, error) {
    conn, err := net.Dial("tcp", addr)
    if err != nil {
        return nil, err
    }

    c := &Connection{conn: conn, db: db}

    // BUG: finalizer không đảm bảo chạy
    runtime.SetFinalizer(c, func(c *Connection) {
        c.conn.Close() // Có thể không bao giờ chạy!
        c.db.Close()   // os.Exit() → không chạy
    })

    return c, nil
}

// BAD: không có explicit Close method
// Người dùng phải "hy vọng" GC sẽ cleanup

// BAD: finalizer cho file handle
type CachedFile struct {
    f    *os.File
    data []byte
}

func OpenCachedFile(path string) (*CachedFile, error) {
    f, err := os.Open(path)
    if err != nil {
        return nil, err
    }

    cf := &CachedFile{f: f}
    runtime.SetFinalizer(cf, func(cf *CachedFile) {
        cf.f.Close() // Quá chậm - file handle giữ qua nhiều GC cycles
    })

    return cf, nil
}
```

**GOOD - Explicit Close pattern thay vì finalizer:**
```go
package pool

import (
    "database/sql"
    "fmt"
    "net"
    "sync"
)

type Connection struct {
    conn   net.Conn
    db     *sql.DB
    mu     sync.Mutex
    closed bool
}

// GOOD: constructor không dùng finalizer
func NewConnection(addr string, db *sql.DB) (*Connection, error) {
    conn, err := net.Dial("tcp", addr)
    if err != nil {
        return nil, fmt.Errorf("dial %s: %w", addr, err)
    }

    return &Connection{conn: conn, db: db}, nil
}

// GOOD: explicit Close method - caller chịu trách nhiệm gọi
func (c *Connection) Close() error {
    c.mu.Lock()
    defer c.mu.Unlock()

    if c.closed {
        return nil // idempotent
    }
    c.closed = true

    var errs []error
    if err := c.conn.Close(); err != nil {
        errs = append(errs, fmt.Errorf("close conn: %w", err))
    }
    if err := c.db.Close(); err != nil {
        errs = append(errs, fmt.Errorf("close db: %w", err))
    }

    if len(errs) > 0 {
        return fmt.Errorf("close connection: %v", errs)
    }
    return nil
}

// GOOD: implement io.Closer interface
var _ io.Closer = (*Connection)(nil)

// GOOD: Usage pattern
func ProcessData(addr string, db *sql.DB) error {
    conn, err := NewConnection(addr, db)
    if err != nil {
        return err
    }
    defer conn.Close() // Explicit cleanup

    // ... use conn
    return nil
}

// GOOD: Pool pattern với lifecycle management
type ConnectionPool struct {
    conns []*Connection
    mu    sync.Mutex
}

func (p *ConnectionPool) Close() error {
    p.mu.Lock()
    defer p.mu.Unlock()

    var errs []error
    for _, conn := range p.conns {
        if err := conn.Close(); err != nil {
            errs = append(errs, err)
        }
    }
    p.conns = nil

    if len(errs) > 0 {
        return fmt.Errorf("close pool: %v", errs)
    }
    return nil
}

// GOOD: Nếu thực sự cần safety net, dùng finalizer CHỈ để log warning
type SafeResource struct {
    handle  int
    closed  bool
    stack   string // stack trace khi tạo
}

func NewSafeResource() *SafeResource {
    r := &SafeResource{
        handle: acquireHandle(),
        stack:  string(debug.Stack()),
    }

    // Finalizer CHỈ để phát hiện leak, KHÔNG để cleanup
    runtime.SetFinalizer(r, func(r *SafeResource) {
        if !r.closed {
            // LOG WARNING, không cleanup
            log.Printf("RESOURCE LEAK: SafeResource not closed! Created at:\n%s", r.stack)
        }
    })

    return r
}

func (r *SafeResource) Close() error {
    r.closed = true
    runtime.SetFinalizer(r, nil) // Remove finalizer
    releaseHandle(r.handle)
    return nil
}
```

### Phòng ngừa

```
Checklist:
- [ ] KHÔNG dùng SetFinalizer để quản lý resources (file, conn, etc.)
- [ ] Luôn cung cấp explicit Close() method implementing io.Closer
- [ ] Caller PHẢI gọi defer obj.Close() sau khi tạo
- [ ] Close() phải idempotent (gọi nhiều lần không lỗi)
- [ ] SetFinalizer CHỈ dùng cho: leak detection (log warning), KHÔNG cleanup
- [ ] Nếu dùng SetFinalizer: remove nó trong Close() với SetFinalizer(obj, nil)
```

```bash
# Tìm tất cả SetFinalizer usage
rg --type go -n "runtime\.SetFinalizer" -A 5

# golangci-lint
golangci-lint run --enable=gocritic,govet ./...

# go vet
go vet ./...

# staticcheck
staticcheck ./...

# Review: mỗi type có SetFinalizer phải có Close()
rg --type go "SetFinalizer" -l | while read f; do
  echo "=== $f ==="
  rg -n "SetFinalizer\|func.*Close\(\)" "$f"
done
```

---

## Tổng kết

| # | Pattern | Severity | Detection Tool |
|---|---------|----------|----------------|
| 01 | HTTP Response Body Không Close | 🟠 HIGH | `bodyclose` linter |
| 02 | File Handle Leak | 🟠 HIGH | `gosec`, `gocritic` |
| 03 | DB Connection Pool Exhaustion | 🔴 CRITICAL | `sqlclosecheck`, monitoring |
| 04 | Defer Trong Loop | 🟠 HIGH | `gocritic` (deferInLoop) |
| 05 | HTTP Client Không Reuse | 🟡 MEDIUM | `noctx` linter |
| 06 | TCP Connection Leak | 🟠 HIGH | `bodyclose` linter |
| 07 | Temp File Không Cleanup | 🟡 MEDIUM | `gosec`, custom script |
| 08 | CGo Memory Leak | 🔴 CRITICAL | valgrind, ASan |
| 09 | Context Leak | 🟠 HIGH | `go vet` (lostcancel) |
| 10 | Ticker Không Stop | 🟡 MEDIUM | `staticcheck` (SA1015) |
| 11 | Pprof Endpoint Production | 🟠 HIGH | `gosec` (G114) |
| 12 | Finalizer Abuse | 🟡 MEDIUM | manual review, `rg` |

### Quick Scan Script

```bash
#!/bin/bash
# Scan tất cả resource management issues trong Go project

echo "=== Resource Management Scan ==="

echo -e "\n--- HTTP Body Close ---"
rg --type go "http\.(Get|Post|Do)\(" -l | while read f; do
  if ! rg -q "Body\.Close" "$f"; then
    echo "  WARN: $f missing Body.Close"
  fi
done

echo -e "\n--- File Handle ---"
rg --type go "os\.(Open|Create)\(" -A 3 | grep -B1 -v "defer\|Close"

echo -e "\n--- DB Pool Config ---"
rg --type go "sql\.Open\(" -l | while read f; do
  if ! rg -q "SetMaxOpenConns" "$f"; then
    echo "  WARN: $f missing SetMaxOpenConns"
  fi
done

echo -e "\n--- Defer in Loop ---"
rg --type go -U "for\s[^{]*\{[^}]*defer" --multiline -l

echo -e "\n--- Context Cancel ---"
rg --type go "context\.With(Cancel|Timeout|Deadline)" -n | grep -v "defer.*cancel"

echo -e "\n--- Pprof Import ---"
rg --type go "\"net/http/pprof\"" | grep -v "_test\.go"

echo -e "\n--- CGo CString ---"
rg --type go "C\.CString" -l | while read f; do
  cs=$(rg -c "C\.CString" "$f")
  cf=$(rg -c "C\.free" "$f")
  if [ "${cs:-0}" -gt "${cf:-0}" ]; then
    echo "  WARN: $f CString=$cs free=$cf"
  fi
done

echo -e "\n--- Ticker Stop ---"
rg --type go "NewTicker\|time\.Tick\(" | grep -v "Stop\|_test\.go"

echo -e "\n=== Done ==="
```
