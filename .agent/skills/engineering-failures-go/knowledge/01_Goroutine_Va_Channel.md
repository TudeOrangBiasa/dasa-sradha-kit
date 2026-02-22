# Domain 01: Goroutine & Channel (Goroutine và Kênh Giao Tiếp)

| Thuộc tính   | Giá trị                                      |
|--------------|----------------------------------------------|
| **Lĩnh vực** | Go Concurrency / Lập trình đồng thời          |
| **Ngôn ngữ** | Go (Golang)                                   |
| **Số mẫu**   | 18 patterns                                   |
| **Phiên bản**| Go 1.18+                                      |
| **Cập nhật** | 2026-02-18                                    |

---

## Mục lục

1. [Goroutine Leak](#pattern-01)
2. [Channel Deadlock](#pattern-02)
3. [Bầy Đàn Ồ Ạt (Thundering Herd)](#pattern-03)
4. [Race Condition](#pattern-04)
5. [Select Không Default](#pattern-05)
6. [Channel Direction Thiếu](#pattern-06)
7. [WaitGroup Sai Vị Trí](#pattern-07)
8. [Context Cancel Bỏ Qua](#pattern-08)
9. [Mutex Copy](#pattern-09)
10. [Channel Nil Send](#pattern-10)
11. [Goroutine Trong Loop](#pattern-11)
12. [Timer Leak](#pattern-12)
13. [Semaphore Không Đúng](#pattern-13)
14. [Done Channel Không Đóng](#pattern-14)
15. [Panic Trong Goroutine](#pattern-15)
16. [errgroup Thiếu](#pattern-16)
17. [Atomic Và Mutex Trộn](#pattern-17)
18. [Pool Exhaustion](#pattern-18)

---

## Pattern 01: Goroutine Leak {#pattern-01}

### 1. Tên
**Goroutine Rò Rỉ** (Goroutine Leak)

### 2. Phân loại
Domain: Goroutine & Channel / Subcategory: Memory Management, Lifecycle

### 3. Mức nghiêm trọng
> CRITICAL - Goroutine bị rò rỉ tích lũy theo thời gian, gây tăng bộ nhớ liên tục và cuối cùng OOM (Out of Memory). Thường xuất hiện trong production sau nhiều giờ hoạt động.

### 4. Vấn đề

Goroutine rò rỉ xảy ra khi goroutine được khởi tạo nhưng không bao giờ kết thúc vì nó đang chờ trên một channel hoặc operation không bao giờ hoàn thành. Goroutine không bị GC thu hồi nếu vẫn còn đang chạy - GC chỉ thu hồi bộ nhớ của goroutine đã thoát.

```
Vòng đời Goroutine bình thường:
  main() ---> go worker() ---> [work done] ---> EXIT  (bộ nhớ giải phóng)

Goroutine Leak:
  main() ---> go worker() ---> [blocked on ch] ---> NEVER EXIT
                               ^
                               |
                          ch không bao giờ nhận giá trị
                          => goroutine treo mãi mãi

Tích lũy theo thời gian:
  t=0:   10 goroutines
  t=1h:  1,010 goroutines  (+1000 leaked)
  t=2h:  2,010 goroutines  (+1000 leaked)
  t=Nh:  RAM exhausted => OOM KILL
```

Nguyên nhân phổ biến:
- Goroutine chờ đọc từ channel không bao giờ có dữ liệu
- Goroutine chờ ghi vào channel không bao giờ có người đọc
- Goroutine chờ lock không bao giờ được nhả
- Goroutine chờ HTTP response từ server đã down

### 5. Phát hiện trong mã nguồn

**Dấu hiệu trong code:**
- `go func()` không có cơ chế dừng (context, done channel)
- Channel được truyền vào goroutine không có guarantee sẽ nhận giá trị
- HTTP handler tạo goroutine không cleanup khi request kết thúc
- `for` loop vô hạn trong goroutine không có exit condition

**Regex patterns (dùng với ripgrep):**

```bash
# Tìm goroutine không có context hoặc done channel
rg "go func\(\)" --type go -n

# Tìm goroutine với channel nhưng không có select/default
rg "go func\(.*chan" --type go -n

# Tìm goroutine trong HTTP handler (nguy cơ cao)
rg -A 5 "func.*http\.ResponseWriter" --type go | rg "go func"

# Tìm goroutine thiếu cơ chế cancel
rg "go func\(\)\s*\{" --type go -n

# Tìm channel receive không có timeout
rg "<-\w+\s*$" --type go -n
```

**Công cụ phát hiện runtime:**
```bash
# Kiểm tra số goroutine đang chạy
go tool pprof http://localhost:6060/debug/pprof/goroutine

# Goleak - phát hiện goroutine leak trong tests
go get go.uber.org/goleak
```

### 6. Giải pháp

| Phương pháp | Trước (BAD) | Sau (GOOD) |
|-------------|-------------|------------|
| Context | Không có | Luôn truyền ctx |
| Done channel | Không có | Thêm done chan |
| Timeout | Không có | Thêm time.After |
| Cleanup | Không có | defer close(ch) |

**Code BAD - Goroutine bị leak:**
```go
// BAD: goroutine này sẽ bị leak nếu không có ai đọc ch
func processRequest(data []byte) {
    ch := make(chan Result)

    go func() {
        result := heavyComputation(data)
        ch <- result // BLOCKED nếu caller đã return!
    }()

    select {
    case result := <-ch:
        handleResult(result)
    case <-time.After(100 * time.Millisecond):
        return // Caller return, goroutine bị LEAK
    }
}

// BAD: goroutine trong vòng lặp không có cách dừng
func startWorker() {
    go func() {
        for {
            doWork() // Vòng lặp vô hạn, không có exit
        }
    }()
}
```

**Code GOOD - Goroutine được quản lý đúng:**
```go
// GOOD: Dùng buffered channel để tránh goroutine block
func processRequest(data []byte) {
    ch := make(chan Result, 1) // buffered: goroutine không bị block

    go func() {
        result := heavyComputation(data)
        ch <- result // Không block vì buffered
    }()

    select {
    case result := <-ch:
        handleResult(result)
    case <-time.After(100 * time.Millisecond):
        return // goroutine sẽ hoàn thành và tự thoát
    }
}

// GOOD: Goroutine với context để có thể cancel
func startWorker(ctx context.Context) {
    go func() {
        for {
            select {
            case <-ctx.Done():
                return // Thoát khi context bị cancel
            default:
                doWork()
            }
        }
    }()
}

// GOOD: Dùng goleak trong tests
func TestMyFunc(t *testing.T) {
    defer goleak.VerifyNone(t) // Kiểm tra leak sau test

    ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
    defer cancel()

    startWorker(ctx)
    // ... test logic
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Mỗi `go func()` phải có cơ chế kết thúc rõ ràng (context.Done, done channel)
- [ ] Channel blocking phải có timeout hoặc buffering
- [ ] Test phải dùng `goleak.VerifyNone(t)` để phát hiện leak
- [ ] HTTP handler không tạo goroutine sống lâu hơn request
- [ ] Dùng `runtime.NumGoroutine()` trong metrics để monitor

**Go vet / staticcheck rules:**
```bash
# Kiểm tra goroutine issues
go vet ./...

# Staticcheck kiểm tra goroutine patterns
staticcheck -checks "SA1012,SA2000,SA2001" ./...

# goleak tích hợp vào test suite
go test -race ./...  # Luôn chạy với -race flag
```

---

## Pattern 02: Channel Deadlock {#pattern-02}

### 1. Tên
**Kênh Bế Tắc** (Channel Deadlock)

### 2. Phân loại
Domain: Goroutine & Channel / Subcategory: Synchronization, Blocking

### 3. Mức nghiêm trọng
> CRITICAL - Deadlock làm dừng hoàn toàn chương trình. Go runtime phát hiện được deadlock ở main goroutine và panic với "all goroutines are asleep - deadlock!". Deadlock trong goroutine con khó phát hiện hơn.

### 4. Vấn đề

Deadlock xảy ra khi hai hoặc nhiều goroutine đang chờ nhau, không ai có thể tiến hành. Với channel, deadlock thường xảy ra khi:
- Gửi vào unbuffered channel nhưng không có goroutine nào đang nhận
- Nhận từ channel nhưng không có goroutine nào gửi

```
Circular Wait (Deadlock):
  Goroutine A  ---> send to ch1 ---> WAIT
       ^                                |
       |                                v
  Goroutine B  <--- recv from ch1 <-- WAIT
       |
       v
  send to ch2 ---> WAIT (không có ai nhận ch2)

Unbuffered Channel Deadlock:
  main goroutine:
    ch := make(chan int)
    ch <- 42          // BLOCK: không có receiver
    <-ch              // Không bao giờ tới đây
  => "all goroutines are asleep - deadlock!"
```

### 5. Phát hiện trong mã nguồn

**Dấu hiệu trong code:**
- Gửi và nhận trên cùng channel trong cùng goroutine
- Unbuffered channel gửi trước khi spawn goroutine nhận
- Hai goroutine gửi cho nhau đồng thời

**Regex patterns:**

```bash
# Tìm send và receive trên cùng một channel trong cùng block
rg "(\w+)\s*<-.*\n.*<-\1" --type go -n

# Tìm unbuffered channel send không có go func trước đó
rg "make\(chan\s+\w+\)" --type go -n

# Tìm channel operations không có select
rg "^\s*\w+\s*<-\s*\w+" --type go -n

# Tìm deadlock pattern: send trước, recv sau, cùng scope
rg -B2 -A5 "make\(chan " --type go | rg -A3 "<-"
```

### 6. Giải pháp

| Tình huống | BAD | GOOD |
|-----------|-----|------|
| Unbuffered send | Send trong main, không có receiver | Spawn goroutine trước |
| Self-deadlock | Send và recv trong cùng goroutine | Dùng goroutine riêng |
| Circular wait | A->B->A | Phá vòng, dùng select |

**Code BAD:**
```go
// BAD: Deadlock - gửi vào unbuffered channel trong main
func main() {
    ch := make(chan int)
    ch <- 42  // DEADLOCK: không có receiver
    fmt.Println(<-ch)
}

// BAD: Deadlock trong goroutine - khó phát hiện
func deadlockInGoroutine() {
    ch1 := make(chan int)
    ch2 := make(chan int)

    go func() {
        ch1 <- 1  // Gửi ch1, chờ ch2
        <-ch2
    }()

    go func() {
        ch2 <- 2  // Gửi ch2, chờ ch1
        <-ch1
    }()

    time.Sleep(time.Second) // Cả hai goroutine đều block
}
```

**Code GOOD:**
```go
// GOOD: Spawn goroutine receiver trước khi send
func main() {
    ch := make(chan int)

    go func() {
        fmt.Println(<-ch) // Receiver sẵn sàng
    }()

    ch <- 42 // Bây giờ có receiver, không deadlock
}

// GOOD: Dùng buffered channel khi không cần sync ngay
func withBufferedChannel() {
    ch := make(chan int, 1) // Buffer size 1
    ch <- 42               // Không block
    fmt.Println(<-ch)      // Lấy ra bình thường
}

// GOOD: Phá circular wait bằng select với timeout
func noCircularWait() {
    ch1 := make(chan int, 1)
    ch2 := make(chan int, 1)

    go func() {
        select {
        case ch1 <- 1:
        case <-time.After(time.Second):
            return // Timeout, không deadlock
        }
    }()

    go func() {
        select {
        case ch2 <- 2:
        case <-time.After(time.Second):
            return
        }
    }()
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Luôn spawn goroutine receiver trước khi send vào unbuffered channel
- [ ] Xem xét dùng buffered channel khi send/recv không cần đồng bộ chặt
- [ ] Dùng `select` với `time.After` để tránh block vĩnh viễn
- [ ] Chạy `go test -race` và `go test -timeout 30s` để phát hiện deadlock
- [ ] Vẽ sơ đồ luồng dữ liệu trước khi code khi logic phức tạp

**Go vet / staticcheck rules:**
```bash
go vet ./...                    # Phát hiện deadlock đơn giản
go test -timeout 30s ./...      # Test sẽ timeout nếu deadlock
go test -race ./...             # Race detector
```

---

## Pattern 03: Bầy Đàn Ồ Ạt (Thundering Herd) {#pattern-03}

### 1. Tên
**Bầy Đàn Ồ Ạt** (Thundering Herd Problem)

### 2. Phân loại
Domain: Goroutine & Channel / Subcategory: Performance, Resource Contention

### 3. Mức nghiêm trọng
> HIGH - Khi nhiều goroutine đồng loạt cạnh tranh tài nguyên sau khi chúng được đánh thức cùng lúc, gây spike CPU/memory và có thể làm sập hệ thống.

### 4. Vấn đề

Thundering Herd xảy ra khi một sự kiện (ví dụ: cache miss, mutex unlock) đánh thức hàng trăm/nghìn goroutine cùng lúc, tất cả cùng tranh nhau cùng tài nguyên. Hầu hết sẽ thất bại, retry, lại gây thêm tải.

```
Thundering Herd với Cache Miss:

Cache MISS ──────────────────────────────────┐
                                             v
1000 goroutines đang chờ         ┌─── goroutine_1 ──> DB query
đều được đánh thức cùng lúc ────>│─── goroutine_2 ──> DB query  (1000 queries đồng thời!)
                                 │─── goroutine_3 ──> DB query
                                 └─── goroutine_N ──> DB query
                                                         │
                                              DB bị quá tải, timeout
                                                         │
                                            Tất cả goroutine retry
                                                         │
                                              Lại Thundering Herd!
```

### 5. Phát hiện trong mã nguồn

**Dấu hiệu trong code:**
- `sync.Cond.Broadcast()` đánh thức nhiều goroutine cùng lúc
- Cache với nhiều goroutine cùng chờ kết quả
- Retry logic không có jitter (random delay)

**Regex patterns:**

```bash
# Tìm Broadcast có thể gây thundering herd
rg "\.Broadcast\(\)" --type go -n

# Tìm cache lookup không có singleflight
rg "cache\.Get\|map\[" --type go -n | rg -v "singleflight"

# Tìm retry không có jitter
rg "time\.Sleep.*Retry\|Retry.*time\.Sleep" --type go -n

# Tìm goroutine pool không giới hạn
rg "go func\(\)" --type go -n | rg -v "semaphore\|limit\|pool"
```

### 6. Giải pháp

| Vấn đề | BAD | GOOD |
|--------|-----|------|
| Cache miss | Nhiều goroutine cùng query DB | Dùng singleflight |
| Retry | Tất cả retry cùng lúc | Exponential backoff + jitter |
| Wake-up | Broadcast đánh thức tất cả | Signal đánh thức từng cái |

**Code BAD:**
```go
// BAD: Thundering herd khi cache miss
var cache = map[string]string{}
var mu sync.RWMutex

func getValue(key string) string {
    mu.RLock()
    if val, ok := cache[key]; ok {
        mu.RUnlock()
        return val
    }
    mu.RUnlock()

    // 1000 goroutine đều tới đây cùng lúc khi cache miss!
    val := fetchFromDB(key) // 1000 DB queries!

    mu.Lock()
    cache[key] = val
    mu.Unlock()

    return val
}
```

**Code GOOD:**
```go
// GOOD: Dùng golang.org/x/sync/singleflight
import "golang.org/x/sync/singleflight"

var (
    cache  = map[string]string{}
    mu     sync.RWMutex
    group  singleflight.Group
)

func getValue(key string) (string, error) {
    mu.RLock()
    if val, ok := cache[key]; ok {
        mu.RUnlock()
        return val, nil
    }
    mu.RUnlock()

    // Chỉ 1 goroutine thực sự gọi DB, phần còn lại chờ kết quả
    val, err, _ := group.Do(key, func() (interface{}, error) {
        return fetchFromDB(key)
    })
    if err != nil {
        return "", err
    }

    result := val.(string)
    mu.Lock()
    cache[key] = result
    mu.Unlock()

    return result, nil
}

// GOOD: Exponential backoff với jitter
import "math/rand"

func retryWithJitter(fn func() error, maxRetries int) error {
    for i := 0; i < maxRetries; i++ {
        if err := fn(); err == nil {
            return nil
        }
        // Exponential backoff: 100ms, 200ms, 400ms...
        base := time.Duration(100<<uint(i)) * time.Millisecond
        // Jitter: thêm ngẫu nhiên 0-100ms để tránh các goroutine retry cùng lúc
        jitter := time.Duration(rand.Intn(100)) * time.Millisecond
        time.Sleep(base + jitter)
    }
    return fmt.Errorf("max retries exceeded")
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Dùng `singleflight` cho cache miss hoặc expensive computation
- [ ] Retry luôn có jitter (random delay)
- [ ] Giới hạn số goroutine đồng thời bằng semaphore
- [ ] Monitor số lượng goroutine và DB connections
- [ ] Dùng circuit breaker khi downstream bị quá tải

**Go vet / staticcheck rules:**
```bash
staticcheck -checks "SA1015" ./...  # Kiểm tra sleep patterns
go test -race ./...
```

---

## Pattern 04: Race Condition {#pattern-04}

### 1. Tên
**Điều Kiện Tranh Chấp** (Race Condition)

### 2. Phân loại
Domain: Goroutine & Channel / Subcategory: Data Safety, Synchronization

### 3. Mức nghiêm trọng
> CRITICAL - Race condition gây ra dữ liệu sai, crash không xác định, và lỗi rất khó tái hiện. Có thể dẫn đến security vulnerabilities khi xảy ra trong authentication/authorization code.

### 4. Vấn đề

Race condition xảy ra khi hai hoặc nhiều goroutine truy cập cùng một biến, ít nhất một goroutine đang ghi, mà không có đồng bộ hóa. Kết quả phụ thuộc vào timing của CPU scheduler - không xác định và không thể đoán trước.

```
Race Condition Timeline:

Goroutine A:  READ counter(=5) ─────────────────> counter+1 ──> WRITE counter=6
                                    |
Goroutine B:              READ counter(=5) ──> counter+1 ──> WRITE counter=6

Kết quả: counter = 6 (thay vì 7!)
"Lost Update" - một lần ghi bị mất

Memory Model Go:
  Goroutine A  ──> writes to x  ──[no sync]──> NOT visible to B
  Goroutine B  ──> reads x      ──[sees stale value]──> BUG
```

### 5. Phát hiện trong mã nguồn

**Dấu hiệu trong code:**
- Biến global hoặc shared được đọc/ghi trong nhiều goroutine
- Slice, map được modify concurrent
- Struct fields được access không có mutex

**Regex patterns:**

```bash
# Tìm biến global có thể bị race
rg "^var\s+\w+\s+" --type go -n

# Tìm map access không có mutex
rg "map\[" --type go -n | rg -v "sync\.Map\|mu\."

# Tìm append trong goroutine (nguy hiểm nếu share slice)
rg "go func.*\{" -A 10 --type go | rg "append\("

# Tìm struct field access trực tiếp không có lock
rg "\.\w+\s*[+\-]?=\s*" --type go | rg -v "mu\.\|Lock\(\)\|RLock\(\)"

# Tìm closure capture biến mutable
rg "go func\(\)" -A 5 --type go | rg "\w+\s*="
```

### 6. Giải pháp

| Phương pháp | Khi dùng | Trade-off |
|------------|---------|-----------|
| sync.Mutex | Nhiều fields cần bảo vệ cùng nhau | Lock overhead |
| sync.RWMutex | Nhiều đọc, ít ghi | Phức tạp hơn |
| sync/atomic | Số nguyên đơn giản | Chỉ cho primitive types |
| sync.Map | Map với nhiều goroutine | Slower than plain map |
| Channel | Ownership transfer | Thay đổi architecture |

**Code BAD:**
```go
// BAD: Race condition trên counter
var counter int

func incrementBad() {
    for i := 0; i < 1000; i++ {
        go func() {
            counter++ // DATA RACE! Read-Modify-Write không atomic
        }()
    }
}

// BAD: Race condition trên map
var cache = make(map[string]int)

func cacheBad(key string, val int) {
    go func() {
        cache[key] = val // DATA RACE! concurrent map write
    }()
    _ = cache[key] // DATA RACE! concurrent map read/write
}
```

**Code GOOD:**
```go
// GOOD: Dùng atomic cho counter đơn giản
import "sync/atomic"

var counter int64

func incrementGood() {
    for i := 0; i < 1000; i++ {
        go func() {
            atomic.AddInt64(&counter, 1) // Thread-safe
        }()
    }
}

// GOOD: Dùng sync.Mutex cho struct phức tạp
type SafeCounter struct {
    mu    sync.Mutex
    count int
    name  string
}

func (c *SafeCounter) Increment() {
    c.mu.Lock()
    defer c.mu.Unlock()
    c.count++
}

func (c *SafeCounter) Value() int {
    c.mu.Lock()
    defer c.mu.Unlock()
    return c.count
}

// GOOD: sync.Map cho concurrent map
var safeCache sync.Map

func cacheGood(key string, val int) {
    safeCache.Store(key, val)
    if v, ok := safeCache.Load(key); ok {
        fmt.Println(v.(int))
    }
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] LUÔN chạy `go test -race ./...` trước khi commit
- [ ] Không bao giờ đọc/ghi biến shared mà không có sync
- [ ] Dùng atomic cho primitive, mutex cho struct
- [ ] Không share map giữa goroutine trừ khi dùng sync.Map
- [ ] Áp dụng "share memory by communicating" - dùng channel thay vì shared memory

**Go vet / staticcheck rules:**
```bash
go test -race ./...              # LUÔN chạy với -race
go vet ./...
staticcheck -checks "SA2001" ./...
```

---

## Pattern 05: Select Không Default {#pattern-05}

### 1. Tên
**Select Thiếu Nhánh Mặc Định** (Select Without Default)

### 2. Phân loại
Domain: Goroutine & Channel / Subcategory: Flow Control, Blocking

### 3. Mức nghiêm trọng
> MEDIUM - Gây block goroutine không mong muốn trong các tình huống cần non-blocking check. Có thể dẫn đến deadlock hoặc performance degradation.

### 4. Vấn đề

`select` trong Go block goroutine cho đến khi ít nhất một case sẵn sàng. Khi muốn non-blocking check (thử lấy từ channel, nếu không có thì làm việc khác), thiếu `default` case sẽ gây block không mong muốn.

```
Select Blocking Flow:

select {              select {
case v := <-ch:       case v := <-ch:
    process(v)            process(v)
}                     default:
  |                       // Không có data, làm việc khác
  v                   }
BLOCKED nếu           |
ch trống              v
                   TIẾP TỤC ngay lập tức
```

### 5. Phát hiện trong mã nguồn

**Regex patterns:**

```bash
# Tìm select không có default trong vòng lặp (nguy hiểm nhất)
rg -B2 -A 15 "for\s*\{" --type go | rg -A 10 "select\s*\{"  | rg -v "default"

# Tìm select chỉ có một case (có thể đơn giản hóa hoặc cần default)
rg -c "case" --type go | rg ":1$"

# Tìm select trong polling loop
rg "for.*\{.*select" --type go -n
```

### 6. Giải pháp

| Tình huống | Cần default? | Lý do |
|-----------|-------------|-------|
| Non-blocking try | Có | Tránh block |
| Polling loop | Có | Cho phép tiếp tục |
| Wait for multiple | Không | Cần block |
| Context done check | Thường có | Avoid stuck |

**Code BAD:**
```go
// BAD: Non-blocking check nhưng lại block
func tryReceive(ch chan int) (int, bool) {
    select {
    case v := <-ch: // Block nếu ch trống!
        return v, true
    }
    return 0, false // Không bao giờ tới đây
}

// BAD: Polling loop bị block mỗi iteration
func pollWork(workCh chan Work) {
    for {
        select {
        case work := <-workCh: // Block cho đến khi có work
            process(work)
        }
        // Không thể làm việc khác giữa các lần poll
    }
}
```

**Code GOOD:**
```go
// GOOD: Non-blocking receive với default
func tryReceive(ch chan int) (int, bool) {
    select {
    case v := <-ch:
        return v, true
    default:
        return 0, false // Return ngay nếu không có data
    }
}

// GOOD: Polling loop với default để có thể làm việc khác
func pollWork(workCh chan Work, ctx context.Context) {
    for {
        select {
        case <-ctx.Done():
            return // Thoát khi cancel
        case work := <-workCh:
            process(work)
        default:
            // Không có work, có thể làm việc maintenance
            doMaintenance()
            time.Sleep(10 * time.Millisecond) // Tránh busy loop
        }
    }
}

// GOOD: Non-blocking send
func trySend(ch chan int, val int) bool {
    select {
    case ch <- val:
        return true
    default:
        return false // Channel đầy, bỏ qua
    }
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Khi cần non-blocking check, luôn thêm `default` case
- [ ] Polling loop luôn có `default` với sleep để tránh busy-wait
- [ ] `default` trong select không nên rỗng - phải có logic hoặc sleep
- [ ] Dùng `context.Done()` thay vì `default` khi cần cancel

**Go vet / staticcheck rules:**
```bash
go vet ./...
staticcheck ./...
```

---

## Pattern 06: Channel Direction Thiếu {#pattern-06}

### 1. Tên
**Thiếu Hướng Channel** (Missing Channel Direction)

### 2. Phân loại
Domain: Goroutine & Channel / Subcategory: API Design, Type Safety

### 3. Mức nghiêm trọng
> MEDIUM - Thiếu type safety dẫn đến bug khó phát hiện: goroutine consumer có thể vô tình gửi vào channel, hoặc producer đọc từ channel. Compiler không thể bắt lỗi này.

### 4. Vấn đề

Go cho phép chỉ định hướng của channel parameter trong function signature: `chan<- T` (send-only) và `<-chan T` (receive-only). Không chỉ định hướng làm mất đi type safety và documentation value của hàm.

```
Channel Direction:

chan T    = bidirectional (có thể send VÀ receive)
chan<- T  = send-only     (chỉ có thể send)
<-chan T  = receive-only  (chỉ có thể receive)

API không rõ ràng:
  func process(ch chan int) // Không rõ: send hay receive?

API rõ ràng:
  func produce(ch chan<- int) // Chỉ send vào ch
  func consume(ch <-chan int) // Chỉ nhận từ ch
```

### 5. Phát hiện trong mã nguồn

**Regex patterns:**

```bash
# Tìm function nhận chan T không có direction
rg "func\s+\w+\(.*\bchan\s+\w+" --type go -n | rg -v "chan<-\|<-chan"

# Tìm method với channel param không có direction
rg "\(.*\bchan\s+[A-Z]\w*" --type go -n

# Tìm goroutine start với channel không typed
rg "go\s+\w+\(.*chan\b" --type go -n
```

### 6. Giải pháp

| Pattern | BAD | GOOD |
|---------|-----|------|
| Producer | `func(ch chan int)` | `func(ch chan<- int)` |
| Consumer | `func(ch chan int)` | `func(ch <-chan int)` |
| Pipeline | `func(in chan int, out chan int)` | `func(in <-chan int, out chan<- int)` |

**Code BAD:**
```go
// BAD: Không có direction - ambiguous API
func producer(ch chan int) {
    ch <- 42 // Ai biết đây là producer?
}

func consumer(ch chan int) {
    <-ch // Ai biết đây là consumer?
}

// Lỗi có thể xảy ra:
func buggyFunction(ch chan int) {
    // Có thể vô tình làm ngược
    val := <-ch  // Oops! Đây là producer mà lại receive
    ch <- val    // Double oops!
}
```

**Code GOOD:**
```go
// GOOD: Direction rõ ràng
func producer(ch chan<- int) {
    ch <- 42          // OK: send-only
    // <-ch           // Compile error! Cannot receive from send-only channel
}

func consumer(ch <-chan int) {
    val := <-ch       // OK: receive-only
    // ch <- 42       // Compile error! Cannot send to receive-only channel
    _ = val
}

// GOOD: Pipeline với direction rõ ràng
func pipeline(in <-chan int, out chan<- int) {
    for val := range in {
        out <- val * 2
    }
    close(out)
}

// GOOD: Generator pattern
func generate(ctx context.Context, nums ...int) <-chan int {
    out := make(chan int)
    go func() {
        defer close(out)
        for _, n := range nums {
            select {
            case <-ctx.Done():
                return
            case out <- n:
            }
        }
    }()
    return out // Caller chỉ có receive-only channel
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Mọi function nhận channel parameter phải chỉ rõ direction
- [ ] Dùng `chan<-` cho producer functions
- [ ] Dùng `<-chan` cho consumer functions
- [ ] Hàm trả về channel thường trả `<-chan T` (caller chỉ cần receive)
- [ ] Code review check: function nào nhận `chan T` bidirectional?

**Go vet / staticcheck rules:**
```bash
staticcheck -checks "S1003" ./...
go vet ./...
# golangci-lint có rule revive với channel-naming
golangci-lint run --enable revive
```

---

## Pattern 07: WaitGroup Sai Vị Trí {#pattern-07}

### 1. Tên
**WaitGroup Dùng Sai Vị Trí** (WaitGroup Misuse)

### 2. Phân loại
Domain: Goroutine & Channel / Subcategory: Synchronization, Lifecycle Management

### 3. Mức nghiêm trọng
> CRITICAL - WaitGroup sai dẫn đến: (1) panic "sync: WaitGroup is reused before previous Wait has returned", (2) Wait() return sớm trước khi goroutine hoàn thành, (3) data corruption.

### 4. Vấn đề

`sync.WaitGroup` có 3 method: `Add()`, `Done()`, `Wait()`. Thứ tự và vị trí gọi các method này rất quan trọng. Lỗi phổ biến nhất là gọi `Add()` bên trong goroutine thay vì trước khi spawn goroutine.

```
WaitGroup Lifecycle:
  Add(n) ──> spawn goroutine ──> Done() x n ──> Wait() unblocks

BAD - Add() trong goroutine:
  Wait() <── có thể return ngay ─── Add() chưa được gọi
  main goroutine                    go func() {
      wg.Wait()  // Return sớm!        wg.Add(1) // Quá muộn!
                                        defer wg.Done()
                                    }()

GOOD - Add() trước goroutine:
  main goroutine:
      wg.Add(1)    // Add TRƯỚC khi spawn
      go func() {
          defer wg.Done()
          doWork()
      }()
      wg.Wait()    // Chờ đúng
```

### 5. Phát hiện trong mã nguồn

**Regex patterns:**

```bash
# Tìm wg.Add() bên trong go func (SAI!)
rg "go func" -A 5 --type go | rg "\.Add\("

# Tìm WaitGroup không có defer Done
rg "\.Add\(1\)" --type go -B 2 -A 10 | rg -v "defer.*\.Done\(\)"

# Tìm wg được pass by value (sẽ bị copy - BUG!)
rg "func.*sync\.WaitGroup[^*]" --type go -n

# Tìm Wait() trước Add() trong sequential code
rg "\.Wait\(\)" --type go -n
```

### 6. Giải pháp

| Lỗi | BAD | GOOD |
|-----|-----|------|
| Add trong goroutine | `go func() { wg.Add(1) }` | `wg.Add(1); go func()` |
| Pass by value | `func f(wg sync.WaitGroup)` | `func f(wg *sync.WaitGroup)` |
| Thiếu defer Done | `wg.Done()` ở cuối | `defer wg.Done()` |
| Reuse trước Wait | Dùng lại wg | Tạo wg mới |

**Code BAD:**
```go
// BAD: Add() bên trong goroutine - race condition!
func badWaitGroup() {
    var wg sync.WaitGroup

    for i := 0; i < 5; i++ {
        go func(i int) {
            wg.Add(1)    // SAI! Add() có thể chưa được gọi khi Wait() chạy
            defer wg.Done()
            fmt.Println(i)
        }(i)
    }

    wg.Wait() // Có thể return sớm vì Add chưa được gọi!
}

// BAD: Pass WaitGroup by value
func doWork(wg sync.WaitGroup, id int) { // SAI! Copy, Done() không ảnh hưởng original
    defer wg.Done()
    time.Sleep(time.Millisecond)
}
```

**Code GOOD:**
```go
// GOOD: Add() TRƯỚC khi spawn goroutine
func goodWaitGroup() {
    var wg sync.WaitGroup

    for i := 0; i < 5; i++ {
        wg.Add(1)     // Add TRƯỚC khi go func
        go func(i int) {
            defer wg.Done()  // defer đảm bảo Done() luôn được gọi
            fmt.Println(i)
        }(i)
    }

    wg.Wait()
}

// GOOD: Pass WaitGroup by pointer
func doWork(wg *sync.WaitGroup, id int) {
    defer wg.Done()
    time.Sleep(time.Millisecond)
    fmt.Printf("Worker %d done\n", id)
}

func main() {
    var wg sync.WaitGroup

    for i := 0; i < 5; i++ {
        wg.Add(1)
        go doWork(&wg, i) // Pass pointer
    }

    wg.Wait()
    fmt.Println("All workers done")
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] `wg.Add(1)` phải gọi TRƯỚC `go func()`, không phải bên trong
- [ ] Luôn dùng `defer wg.Done()` để đảm bảo Done được gọi kể cả khi panic
- [ ] Truyền WaitGroup bằng pointer (`*sync.WaitGroup`)
- [ ] Không reuse WaitGroup khi chưa có Wait() trả về
- [ ] Ưu tiên dùng `errgroup.Group` thay vì WaitGroup khi cần xử lý error

**Go vet / staticcheck rules:**
```bash
go vet ./...         # go vet kiểm tra WaitGroup copy
go test -race ./...
staticcheck ./...
```

---

## Pattern 08: Context Cancel Bỏ Qua {#pattern-08}

### 1. Tên
**Bỏ Qua Context Cancel** (Ignoring Context Cancellation)

### 2. Phân loại
Domain: Goroutine & Channel / Subcategory: Resource Management, Graceful Shutdown

### 3. Mức nghiêm trọng
> HIGH - Context cancel bị bỏ qua dẫn đến goroutine tiếp tục chạy sau khi không cần thiết, lãng phí tài nguyên, và ngăn graceful shutdown.

### 4. Vấn đề

`context.Context` là cơ chế chính để signal cancellation trong Go. Khi `ctx.Done()` bị đóng (do timeout, deadline, hoặc cancel), goroutine phải thoát. Không kiểm tra `ctx.Done()` nghĩa là goroutine tiếp tục chạy vô ích.

```
Context Propagation Tree:

context.Background()
    └── ctx (với cancel)
            ├── goroutine A  ──> kiểm tra ctx.Done() ──> THOÁT khi cancel
            ├── goroutine B  ──> KHÔNG kiểm tra ──────> VẪN CHẠY sau cancel
            └── HTTP request ──> ctx bị cancel khi client disconnect
                                  goroutine vẫn query DB, compute...
```

### 5. Phát hiện trong mã nguồn

**Regex patterns:**

```bash
# Tìm function nhận context nhưng không dùng ctx.Done()
rg "func.*ctx context\.Context" --type go -A 20 | rg -v "ctx\.Done\(\)\|ctx\.Err\(\)"

# Tìm vòng lặp với ctx nhưng không check Done
rg "for\s*\{" -A 10 --type go | rg "ctx" | rg -v "Done\|Err"

# Tìm context được tạo nhưng cancel không được defer
rg "context\.With" --type go -A 2 | rg -v "defer.*cancel"

# Tìm HTTP handler không propagate context
rg "http\.Request" --type go -A 10 | rg "go func" | rg -v "r\.Context\(\)"
```

### 6. Giải pháp

| Tình huống | BAD | GOOD |
|-----------|-----|------|
| Loop | Không check ctx | `select { case <-ctx.Done(): return }` |
| IO operation | Dùng operation không-context | Dùng operation với context |
| cancel() | Không defer cancel | `defer cancel()` |
| HTTP | Không dùng r.Context() | Propagate r.Context() |

**Code BAD:**
```go
// BAD: Bỏ qua context trong vòng lặp
func processItems(ctx context.Context, items []Item) {
    for _, item := range items {
        // ctx bị cancel nhưng vẫn tiếp tục xử lý!
        processItem(item)
    }
}

// BAD: Cancel không được defer
func fetchData() ([]byte, error) {
    ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
    // MISSING: defer cancel() => context leak!
    return http.Get(ctx, "https://api.example.com/data")
}

// BAD: Goroutine không nhận context
func startBackgroundWork() {
    go func() {
        for {
            doWork() // Chạy mãi mãi, không thể cancel
        }
    }()
}
```

**Code GOOD:**
```go
// GOOD: Kiểm tra context trong vòng lặp
func processItems(ctx context.Context, items []Item) error {
    for _, item := range items {
        select {
        case <-ctx.Done():
            return ctx.Err() // Thoát khi cancel
        default:
            if err := processItem(ctx, item); err != nil {
                return err
            }
        }
    }
    return nil
}

// GOOD: Luôn defer cancel
func fetchData(ctx context.Context) ([]byte, error) {
    ctx, cancel := context.WithTimeout(ctx, 5*time.Second)
    defer cancel() // LUÔN defer cancel để tránh context leak

    req, err := http.NewRequestWithContext(ctx, "GET", "https://api.example.com/data", nil)
    if err != nil {
        return nil, err
    }
    resp, err := http.DefaultClient.Do(req)
    if err != nil {
        return nil, err
    }
    defer resp.Body.Close()
    return io.ReadAll(resp.Body)
}

// GOOD: Background worker với context
func startBackgroundWork(ctx context.Context) {
    go func() {
        ticker := time.NewTicker(time.Second)
        defer ticker.Stop()

        for {
            select {
            case <-ctx.Done():
                return // Graceful shutdown
            case <-ticker.C:
                doWork()
            }
        }
    }()
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Mọi `context.WithCancel/Timeout/Deadline` phải có `defer cancel()`
- [ ] Long-running operations phải nhận và check context
- [ ] Vòng lặp vô hạn phải có `case <-ctx.Done(): return`
- [ ] HTTP handler dùng `r.Context()` để propagate đến downstream
- [ ] Database queries phải dùng context-aware methods

**Go vet / staticcheck rules:**
```bash
staticcheck -checks "SA1012,SA4006" ./...
go vet ./...
# Dùng golangci-lint với contextcheck linter
golangci-lint run --enable contextcheck
```

---

## Pattern 09: Mutex Copy {#pattern-09}

### 1. Tên
**Sao Chép Mutex** (Mutex Copy)

### 2. Phân loại
Domain: Goroutine & Channel / Subcategory: Synchronization, Value Semantics

### 3. Mức nghiêm trọng
> CRITICAL - Copy mutex sau khi đã dùng dẫn đến mutex bị copy ở trạng thái locked, gây deadlock không xác định và rất khó debug.

### 4. Vấn đề

`sync.Mutex` và `sync.RWMutex` phải KHÔNG BAO GIỜ bị copy sau khi lần đầu sử dụng. Struct chứa mutex nếu được pass by value hoặc assign sẽ copy cả trạng thái của mutex. Nếu mutex đang locked khi copy, bản copy sẽ bắt đầu ở trạng thái locked và không thể unlock.

```
Mutex State khi Copy:

Original struct:
  type Counter struct {
      mu    sync.Mutex  ← trạng thái: unlocked (0)
      count int
  }

Sau khi Lock và Copy:
  c.mu.Lock()
  copy := *c          // copy.mu ở trạng thái: LOCKED!
  c.mu.Unlock()       // Original unlock OK

  copy.mu.Lock()      // DEADLOCK! copy.mu đã locked, không ai unlock
```

### 5. Phát hiện trong mã nguồn

**Regex patterns:**

```bash
# Tìm struct chứa mutex được pass by value
rg "func.*\b\w+\s+\w+[^*]" --type go | rg "sync\."

# Tìm assignment của struct chứa mutex
rg ":=\s*\*\w+\|=\s*\*\w+" --type go -n

# go vet sẽ bắt hầu hết trường hợp này
go vet ./...

# Tìm method receiver value (không phải pointer) trên struct có mutex
rg "func\s*\(\w+\s+[A-Z]\w*\)" --type go -n
```

### 6. Giải pháp

| Lỗi | BAD | GOOD |
|-----|-----|------|
| Pass by value | `func(c Counter)` | `func(c *Counter)` |
| Assign | `c2 := *c1` | Không copy, dùng pointer |
| Return | `return *structWithMutex` | Trả về pointer |

**Code BAD:**
```go
type Counter struct {
    mu    sync.Mutex
    count int
}

// BAD: Receiver là value type - mỗi call sẽ copy mutex!
func (c Counter) BadIncrement() {
    c.mu.Lock()   // Lock trên bản COPY, không lock original!
    defer c.mu.Unlock()
    c.count++     // Thay đổi bản copy, không ảnh hưởng original!
}

// BAD: Pass by value
func processCounter(c Counter) { // Copy toàn bộ Counter kể cả mutex!
    c.mu.Lock()
    defer c.mu.Unlock()
    fmt.Println(c.count)
}

// BAD: Copy struct có mutex
func copySomeCounter(c *Counter) Counter {
    return *c // Copy mutex! CỰC KỲ NGUY HIỂM
}
```

**Code GOOD:**
```go
type Counter struct {
    mu    sync.Mutex
    count int
}

// GOOD: Pointer receiver
func (c *Counter) Increment() {
    c.mu.Lock()
    defer c.mu.Unlock()
    c.count++ // Thay đổi original
}

func (c *Counter) Value() int {
    c.mu.Lock()
    defer c.mu.Unlock()
    return c.count
}

// GOOD: Pass by pointer
func processCounter(c *Counter) {
    c.mu.Lock()
    defer c.mu.Unlock()
    fmt.Println(c.count)
}

// GOOD: Nếu cần "copy" dữ liệu, copy từng field thủ công
func snapshot(c *Counter) int {
    c.mu.Lock()
    defer c.mu.Unlock()
    return c.count // Chỉ copy giá trị, không copy mutex
}

// GOOD: Dùng noCopy helper để detect trong go vet
type noCopy struct{}
func (*noCopy) Lock()   {}
func (*noCopy) Unlock() {}

type SafeStruct struct {
    _    noCopy // go vet sẽ báo lỗi nếu struct này bị copy
    mu   sync.Mutex
    data int
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Struct chứa mutex phải LUÔN dùng pointer receiver
- [ ] Không bao giờ assign `c2 := *c1` nếu c1 chứa mutex
- [ ] Không return struct chứa mutex by value
- [ ] Dùng `go vet` - nó phát hiện mutex copy
- [ ] Thêm `noCopy` field vào struct quan trọng

**Go vet / staticcheck rules:**
```bash
go vet ./...    # go vet có copylocks analyzer, bắt mutex copy
staticcheck -checks "SA2001" ./...
```

---

## Pattern 10: Channel Nil Send {#pattern-10}

### 1. Tên
**Gửi/Nhận Trên Channel Nil** (Nil Channel Operations)

### 2. Phân loại
Domain: Goroutine & Channel / Subcategory: Channel Semantics, Runtime Panic

### 3. Mức nghiêm trọng
> CRITICAL - Send hoặc receive trên nil channel block mãi mãi. Close trên nil channel gây panic. Những lỗi này thường không rõ ràng khi channel được set nil có điều kiện.

### 4. Vấn đề

Semantics của nil channel trong Go:
- `nil channel <- value` → block mãi mãi
- `<- nil channel` → block mãi mãi
- `close(nil channel)` → panic
- Trong select, nil channel case bị bỏ qua (hành vi có ích!)

```
Nil Channel Behavior:

var ch chan int  // ch == nil

Send:  ch <- 42    → block forever (goroutine leak!)
Recv:  <-ch        → block forever (goroutine leak!)
Close: close(ch)   → panic: close of nil channel

Trong select:
  select {
  case v := <-nilCh:    // Bị bỏ qua hoàn toàn (useful!)
      process(v)
  case <-activeCh:
      doSomething()
  }
```

### 5. Phát hiện trong mã nguồn

**Regex patterns:**

```bash
# Tìm channel có thể nil được dùng trong send/recv
rg "var\s+\w+\s+chan" --type go -n

# Tìm close() có thể gọi trên nil channel
rg "close\(\w+\)" --type go -n

# Tìm channel được set nil có điều kiện
rg "\bch\s*=\s*nil\b\|\bch\s*==\s*nil\b" --type go -n

# Tìm channel return từ function có thể nil
rg "return\s+nil\b" --type go -n | rg "chan\|channel"
```

### 6. Giải pháp

| Operation | Nil Channel | Hành vi | Cần làm |
|-----------|------------|---------|---------|
| Send | `ch <- v` | Block mãi | Kiểm tra nil trước |
| Receive | `<-ch` | Block mãi | Kiểm tra nil trước |
| Close | `close(ch)` | PANIC | Kiểm tra nil trước |
| Select case | Tự động skip | OK - hữu ích | Có thể dùng có chủ ý |

**Code BAD:**
```go
// BAD: Channel có thể nil khi close
func worker(done chan struct{}) {
    close(done) // PANIC nếu done == nil!
}

// BAD: Conditional channel dẫn đến nil send
func processConditional(useChannel bool) {
    var ch chan int
    if useChannel {
        ch = make(chan int)
    }

    // Nếu useChannel == false, ch vẫn nil
    ch <- 42 // Block mãi nếu ch nil!
}
```

**Code GOOD:**
```go
// GOOD: Kiểm tra nil trước khi close
func safeClose(ch chan struct{}) {
    if ch != nil {
        close(ch)
    }
}

// GOOD: Dùng sync.Once để đảm bảo close chỉ một lần
type SafeChannel struct {
    ch   chan struct{}
    once sync.Once
}

func (sc *SafeChannel) Close() {
    sc.once.Do(func() {
        close(sc.ch)
    })
}

// GOOD: Khai thác nil channel trong select để "disable" case
func merge(ctx context.Context, ch1, ch2 <-chan int) <-chan int {
    out := make(chan int)
    go func() {
        defer close(out)
        for ch1 != nil || ch2 != nil {
            select {
            case <-ctx.Done():
                return
            case v, ok := <-ch1:
                if !ok {
                    ch1 = nil // Disable ch1 case trong select
                    continue
                }
                out <- v
            case v, ok := <-ch2:
                if !ok {
                    ch2 = nil // Disable ch2 case trong select
                    continue
                }
                out <- v
            }
        }
    }()
    return out
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Luôn khởi tạo channel bằng `make()` trước khi dùng
- [ ] Kiểm tra nil trước khi close channel
- [ ] Dùng `sync.Once` để đảm bảo close chỉ một lần
- [ ] Khai thác nil channel trong select để disable cases một cách có chủ ý
- [ ] Tránh return nil channel từ function trừ khi được document rõ ràng

**Go vet / staticcheck rules:**
```bash
go vet ./...
staticcheck -checks "SA4006" ./...
go test -race ./...
```

---

## Pattern 11: Goroutine Trong Loop {#pattern-11}

### 1. Tên
**Goroutine Capture Biến Loop** (Loop Variable Capture in Goroutines)

### 2. Phân loại
Domain: Goroutine & Channel / Subcategory: Closure Semantics, Variable Capture

### 3. Mức nghiêm trọng
> HIGH - Trước Go 1.22: tất cả goroutine trong loop tham chiếu đến CÙNG biến loop, không phải giá trị của nó tại thời điểm spawn. Kết quả: tất cả goroutine thấy cùng một giá trị (thường là giá trị cuối cùng).

### 4. Vấn đề

Trước Go 1.22, biến vòng lặp `for` được chia sẻ qua các iteration. Closure trong goroutine capture địa chỉ biến, không phải giá trị. Khi goroutine thực sự chạy, vòng lặp đã hoàn thành và biến đã có giá trị cuối.

```
Closure Capture Problem (trước Go 1.22):

for i := 0; i < 3; i++ {     Bộ nhớ:
    go func() {               ┌─────────────────┐
        fmt.Println(i)  ──────│ addr_i → i=0,1,2│→3 (sau loop)
    }()                       └─────────────────┘
}
Kết quả: in ra "3 3 3" thay vì "0 1 2"

Vì:
  t=0: i=0, spawn goroutine_0 (capture &i)
  t=1: i=1, spawn goroutine_1 (capture &i)
  t=2: i=2, spawn goroutine_2 (capture &i)
  t=3: loop done, i=3
  goroutine_0 chạy: đọc *(&i) = 3!
  goroutine_1 chạy: đọc *(&i) = 3!
  goroutine_2 chạy: đọc *(&i) = 3!
```

### 5. Phát hiện trong mã nguồn

**Regex patterns:**

```bash
# Tìm goroutine trong for loop dùng biến loop (trước Go 1.22)
rg -B 2 "go func\(\)" --type go | rg "for\s"

# Tìm closure trong loop dùng biến ngoài (i, j, v, item, etc.)
rg "for\s+\w+.*:=\s*range\|for\s+\w+\s*:=\s*0" -A 10 --type go | rg "go func\(\)\s*\{"

# Tìm goroutine capture range variable
rg "for\s+\w+,\s*\w+\s*:=\s*range" -A 5 --type go | rg "go func"

# Kiểm tra Go version (Go 1.22+ fix issue này)
rg "^go\s+1\." go.mod
```

### 6. Giải pháp

| Go Version | BAD | GOOD |
|-----------|-----|------|
| < 1.22 | Capture biến loop | Pass làm parameter |
| >= 1.22 | - | Tự động fix, nhưng vẫn nên explicit |

**Code BAD (trước Go 1.22):**
```go
// BAD: Tất cả goroutine print "5" (giá trị cuối i)
func badLoopCapture() {
    var wg sync.WaitGroup
    for i := 0; i < 5; i++ {
        wg.Add(1)
        go func() {
            defer wg.Done()
            fmt.Println(i) // Capture &i, không capture value!
        }()
    }
    wg.Wait()
}

// BAD: Range variable capture
func badRangeCapture() {
    items := []string{"a", "b", "c"}
    for _, item := range items {
        go func() {
            fmt.Println(item) // Luôn in "c"!
        }()
    }
}
```

**Code GOOD:**
```go
// GOOD: Pass biến loop làm parameter
func goodLoopCapture() {
    var wg sync.WaitGroup
    for i := 0; i < 5; i++ {
        wg.Add(1)
        go func(i int) { // i là parameter riêng, không phải capture
            defer wg.Done()
            fmt.Println(i) // In đúng giá trị
        }(i) // Pass giá trị tại thời điểm spawn
    }
    wg.Wait()
}

// GOOD: Shadow variable (alternative)
func goodRangeCapture() {
    items := []string{"a", "b", "c"}
    var wg sync.WaitGroup
    for _, item := range items {
        item := item // Shadow: tạo biến mới trong scope này
        wg.Add(1)
        go func() {
            defer wg.Done()
            fmt.Println(item) // In đúng
        }()
    }
    wg.Wait()
}

// NOTE: Go 1.22+ tự động fix loop variable semantics
// Vẫn nên dùng explicit parameter để code rõ ràng hơn
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Kiểm tra phiên bản Go trong go.mod
- [ ] Trước Go 1.22: LUÔN pass loop variable làm parameter cho goroutine
- [ ] Sau Go 1.22: vẫn nên dùng explicit parameter cho rõ ràng
- [ ] Code review: tìm pattern `for ... { go func() { ... loopVar ... } }` không có parameter
- [ ] Chạy `go test -race` để phát hiện race condition do vấn đề này

**Go vet / staticcheck rules:**
```bash
go vet ./...    # Cảnh báo loop variable capture
staticcheck -checks "SA4013" ./...
go test -race ./...
```

---

## Pattern 12: Timer Leak {#pattern-12}

### 1. Tên
**Rò Rỉ Timer** (Timer Leak)

### 2. Phân loại
Domain: Goroutine & Channel / Subcategory: Resource Management, Memory

### 3. Mức nghiêm trọng
> HIGH - Timer không được dọn dẹp tiêu thụ tài nguyên runtime (goroutine và memory cho mỗi timer). `time.After()` trong vòng lặp tạo timer mới mỗi iteration mà không bao giờ được GC cho đến khi fire.

### 4. Vấn đề

`time.After(d)` tạo một timer và trả về channel. Timer này không thể bị GC cho đến khi nó fire (sau khoảng thời gian `d`). Nếu dùng trong vòng lặp hoặc trong select mà case khác được chọn, timer cũ bị bỏ nhưng vẫn chiếm tài nguyên đến khi hết hạn.

```
Timer Leak trong Loop:

for {
    select {
    case <-time.After(1 * time.Minute):  // Tạo timer mới mỗi iteration!
        doTimeout()
    case data := <-ch:                    // Nếu data đến, timer cũ bị bỏ
        process(data)                     // Nhưng timer vẫn chạy thêm 1 phút!
    }
}

Sau 1000 iterations với 1 phút timeout:
  Có thể có 1000 timer objects đang pending trong runtime
  Mỗi timer chiếm ~200 bytes
  1000 * 200 = 200KB liên tục bị rò rỉ
```

### 5. Phát hiện trong mã nguồn

**Regex patterns:**

```bash
# Tìm time.After trong select (dễ leak)
rg "time\.After" --type go -n

# Tìm time.After trong for loop (nguy hiểm nhất)
rg "for\s*\{" -A 10 --type go | rg "time\.After"

# Tìm time.NewTimer không có Stop()
rg "time\.NewTimer" --type go -A 20 | rg -v "\.Stop\(\)"

# Tìm time.After không phải trong select one-shot
rg "time\.After\(" --type go -B 3 | rg "for\|select"
```

### 6. Giải pháp

| Tình huống | BAD | GOOD |
|-----------|-----|------|
| One-shot timeout | `time.After()` | OK nếu không trong loop |
| Loop timeout | `time.After()` trong loop | `time.NewTimer` + Reset |
| Ticker | `time.After` trong loop | `time.NewTicker` |

**Code BAD:**
```go
// BAD: time.After trong select loop - timer leak!
func badTimerLoop(ch <-chan Data) {
    for {
        select {
        case <-time.After(5 * time.Second): // Tạo timer mới mỗi lần!
            fmt.Println("timeout")
        case data := <-ch:
            process(data) // Timer cũ bị bỏ nhưng vẫn chạy 5 giây
        }
    }
}
```

**Code GOOD:**
```go
// GOOD: Dùng time.NewTimer và reset đúng cách
func goodTimerLoop(ctx context.Context, ch <-chan Data) {
    timer := time.NewTimer(5 * time.Second) // Tạo một lần
    defer timer.Stop()                       // Cleanup khi hàm return

    for {
        select {
        case <-ctx.Done():
            return
        case <-timer.C:
            fmt.Println("timeout")
            timer.Reset(5 * time.Second) // Reuse timer
        case data := <-ch:
            // Reset timer đúng cách
            if !timer.Stop() {
                // Drain channel nếu timer đã fire
                select {
                case <-timer.C:
                default:
                }
            }
            timer.Reset(5 * time.Second)
            process(data)
        }
    }
}

// GOOD: Dùng time.NewTicker thay vì time.After trong loop
func goodTicker(ctx context.Context) {
    ticker := time.NewTicker(5 * time.Second)
    defer ticker.Stop() // Cleanup bắt buộc!

    for {
        select {
        case <-ctx.Done():
            return
        case <-ticker.C:
            doPeriodicWork()
        }
    }
}

// GOOD: time.After chỉ dùng cho one-shot (ngoài loop)
func oneShot() {
    select {
    case <-time.After(5 * time.Second): // OK: không có loop
        fmt.Println("timeout")
    case result := <-someChannel:
        handle(result)
    }
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Không dùng `time.After()` trong vòng lặp
- [ ] Dùng `time.NewTimer()` trong vòng lặp, `defer timer.Stop()`
- [ ] Dùng `time.NewTicker()` cho periodic work, `defer ticker.Stop()`
- [ ] Khi reset Timer: Stop() trước, drain channel nếu cần, rồi Reset()
- [ ] Monitor số lượng goroutine để phát hiện timer leak

**Go vet / staticcheck rules:**
```bash
staticcheck -checks "SA1015" ./...  # Cảnh báo time.After trong select loop
go vet ./...
```

---

## Pattern 13: Semaphore Không Đúng {#pattern-13}

### 1. Tên
**Semaphore Dùng Sai Cách** (Incorrect Semaphore Implementation)

### 2. Phân loại
Domain: Goroutine & Channel / Subcategory: Concurrency Control, Resource Limiting

### 3. Mức nghiêm trọng
> MEDIUM - Semaphore sai dẫn đến: không giới hạn được concurrency, deadlock, hoặc goroutine leak. Ảnh hưởng đến stability và performance.

### 4. Vấn đề

Semaphore trong Go thường được implement bằng buffered channel. Lỗi phổ biến: acquire và release không pair đúng, không có `defer` cho release, hoặc panic sau acquire mà không release.

```
Semaphore Pattern đúng:
  sem := make(chan struct{}, N)  // Capacity = N concurrent ops

  Acquire: sem <- struct{}{}    // Block nếu đã có N goroutine chạy
  Release: <-sem                // Giải phóng slot

Lỗi thường gặp:
  Acquire không release → goroutine tiếp theo block mãi
  Release trước khi acquire → semaphore "âm"
  Panic giữa acquire và release → deadlock
```

### 5. Phát hiện trong mã nguồn

**Regex patterns:**

```bash
# Tìm semaphore pattern (buffered channel as semaphore)
rg "make\(chan struct\{\},\s*\d+" --type go -n

# Tìm sem acquire không có defer release
rg "sem\s*<-\|<-\s*sem" --type go -A 5 | rg -v "defer"

# Tìm goroutine pool implementation
rg "make\(chan.*\d+\)" --type go -B 2 -A 10 | rg "go func"
```

### 6. Giải pháp

| Pattern | BAD | GOOD |
|---------|-----|------|
| Release | Không defer | `defer func() { <-sem }()` |
| Panic safety | Không có | defer đảm bảo release |
| Overflow | Không check | Buffered channel tự block |

**Code BAD:**
```go
// BAD: Release không được defer - panic hoặc early return sẽ cause leak
func badSemaphore(sem chan struct{}, work func()) {
    sem <- struct{}{}   // Acquire
    work()              // Nếu work() panic, sem không được release!
    <-sem               // Release (có thể không được gọi)
}

// BAD: Semaphore không đúng direction
var sem = make(chan struct{}, 10)

func worker() {
    <-sem               // WRONG: Nhận từ sem để "acquire"?
    defer func() {
        sem <- struct{}{} // WRONG: Gửi vào sem để "release"?
    }()
    doWork()
}
// Convention sai: không nhất quán, khó đọc
```

**Code GOOD:**
```go
// GOOD: Semaphore đúng với defer
var sem = make(chan struct{}, 10) // Max 10 concurrent goroutines

func goodWorker(id int) {
    sem <- struct{}{}      // Acquire (block nếu full)
    defer func() {
        <-sem              // Release khi done (kể cả khi panic)
    }()

    doWork(id)
}

// GOOD: Dùng golang.org/x/sync/semaphore (weighted semaphore)
import "golang.org/x/sync/semaphore"

func withWeightedSemaphore(ctx context.Context, tasks []Task) error {
    sem := semaphore.NewWeighted(10) // Max weight 10

    var g errgroup.Group
    for _, task := range tasks {
        task := task
        if err := sem.Acquire(ctx, 1); err != nil {
            return err // Context cancelled
        }
        g.Go(func() error {
            defer sem.Release(1) // Luôn release
            return processTask(ctx, task)
        })
    }
    return g.Wait()
}

// GOOD: Simple concurrent limiter
func limitedConcurrency(ctx context.Context, items []string, maxConc int) {
    sem := make(chan struct{}, maxConc)
    var wg sync.WaitGroup

    for _, item := range items {
        item := item
        sem <- struct{}{} // Acquire
        wg.Add(1)
        go func() {
            defer func() {
                <-sem // Release
                wg.Done()
            }()
            process(item)
        }()
    }

    wg.Wait()
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Luôn `defer` release semaphore ngay sau khi acquire
- [ ] Dùng `golang.org/x/sync/semaphore` cho production code
- [ ] Test với race detector để verify semaphore correct
- [ ] Monitor goroutine count để verify semaphore đang hoạt động
- [ ] Consistent convention: `sem <- struct{}{}` = acquire, `<-sem` = release

**Go vet / staticcheck rules:**
```bash
go vet ./...
go test -race ./...
staticcheck ./...
```

---

## Pattern 14: Done Channel Không Đóng {#pattern-14}

### 1. Tên
**Done Channel Không Được Đóng** (Unclosed Done Channel)

### 2. Phân loại
Domain: Goroutine & Channel / Subcategory: Signaling, Goroutine Lifecycle

### 3. Mức nghiêm trọng
> HIGH - Goroutine chờ trên done channel sẽ không bao giờ nhận được signal để thoát, dẫn đến goroutine leak vĩnh viễn.

### 4. Vấn đề

Done channel là pattern phổ biến để signal goroutine dừng lại. Khi cần nhiều goroutine cùng nhận signal dừng, `close(done)` là cách đúng (tất cả receiver đều nhận zero value). Nhưng nếu quên close hoặc close sai goroutine, tất cả goroutine chờ sẽ bị leak.

```
Done Channel Signaling:

Gửi vào done:             Close done:
  done <- struct{}{}        close(done)
  └── Chỉ 1 goroutine       └── TẤT CẢ goroutine
      nhận được signal           nhận được signal (broadcast)

Khi nào dùng gì:
  Send: 1-to-1 signal       Close: 1-to-many signal (broadcast)

Unclosed done channel:
  goroutine_1 waiting on <-done  ──> LEAK
  goroutine_2 waiting on <-done  ──> LEAK
  goroutine_3 waiting on <-done  ──> LEAK
  // done channel không bao giờ được close
```

### 5. Phát hiện trong mã nguồn

**Regex patterns:**

```bash
# Tìm done channel pattern
rg "done\s*:?=\s*make\(chan" --type go -n

# Tìm goroutine chờ done nhưng done không được close
rg "<-done\b\|<-\s*done\b" --type go -n

# Tìm function tạo goroutine không return close function
rg "func\s+start\w*\(" --type go -A 20 | rg "go func" | rg -v "close\|cancel"

# Tìm done channel không có close() gọi
rg "chan struct\{\}" --type go -B 5 -A 30 | rg -v "close("
```

### 6. Giải pháp

| Tình huống | Pattern | Implementation |
|-----------|---------|----------------|
| 1 goroutine | Send signal | `done <- struct{}{}` |
| N goroutines | Broadcast | `close(done)` |
| Cancel + cleanup | Context | `context.WithCancel` |

**Code BAD:**
```go
// BAD: Done channel không được close - goroutine leak!
func startWorkers() {
    done := make(chan struct{})

    for i := 0; i < 5; i++ {
        go func(id int) {
            for {
                select {
                case <-done: // Chờ signal
                    return
                default:
                    doWork(id)
                }
            }
        }(i)
    }

    // ... sau một thời gian ...
    // QUÊN close(done)! Tất cả 5 goroutine bị LEAK!
}

// BAD: Send thay vì close khi có nhiều goroutine
func stopAllWorkers(done chan struct{}) {
    done <- struct{}{} // Chỉ dừng 1 goroutine, 4 cái còn lại LEAK!
}
```

**Code GOOD:**
```go
// GOOD: close(done) để broadcast đến tất cả goroutine
func startWorkers() {
    done := make(chan struct{})
    var wg sync.WaitGroup

    for i := 0; i < 5; i++ {
        wg.Add(1)
        go func(id int) {
            defer wg.Done()
            for {
                select {
                case <-done:
                    return // Nhận signal từ close(done)
                default:
                    doWork(id)
                }
            }
        }(i)
    }

    // Signal tất cả goroutine dừng
    close(done)      // Broadcast - tất cả goroutine nhận được
    wg.Wait()        // Chờ tất cả goroutine kết thúc
}

// GOOD: Dùng context (cách Go idiom nhất)
func startWorkersWithContext(ctx context.Context) {
    var wg sync.WaitGroup

    for i := 0; i < 5; i++ {
        wg.Add(1)
        go func(id int) {
            defer wg.Done()
            for {
                select {
                case <-ctx.Done():
                    return // Cancel từ context
                default:
                    doWork(id)
                }
            }
        }(i)
    }

    wg.Wait()
}

// GOOD: Return cancel function để caller control
func startService(ctx context.Context) (stop func(), done <-chan struct{}) {
    stopCh := make(chan struct{})
    doneCh := make(chan struct{})

    go func() {
        defer close(doneCh)
        for {
            select {
            case <-ctx.Done():
                return
            case <-stopCh:
                return
            default:
                doWork()
            }
        }
    }()

    return func() { close(stopCh) }, doneCh
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Với N goroutines, dùng `close(done)` không phải `done <- value`
- [ ] Luôn ưu tiên `context.Context` thay vì done channel
- [ ] Hàm tạo goroutine phải trả về stop/cancel function
- [ ] Dùng `sync.WaitGroup` kết hợp để đảm bảo goroutine đã thoát
- [ ] Test goroutine cleanup bằng `goleak.VerifyNone(t)`

**Go vet / staticcheck rules:**
```bash
go vet ./...
go test -race ./...
# goleak để detect goroutine leak trong tests
```

---

## Pattern 15: Panic Trong Goroutine {#pattern-15}

### 1. Tên
**Panic Không Được Xử Lý Trong Goroutine** (Unhandled Panic in Goroutine)

### 2. Phân loại
Domain: Goroutine & Channel / Subcategory: Error Handling, Fault Tolerance

### 3. Mức nghiêm trọng
> CRITICAL - Panic trong bất kỳ goroutine nào mà không được recover sẽ làm crash toàn bộ process. Điều này đặc biệt nguy hiểm trong server application.

### 4. Vấn đề

Không giống như error, panic trong goroutine lan truyền ngược lên call stack của goroutine đó. Nếu không có `recover()` trong goroutine, panic sẽ terminate toàn bộ program. Main goroutine không thể recover panic từ goroutine con.

```
Panic Propagation:

main goroutine ──> go worker() ──> panic("something wrong")
                                        |
                                   Không có recover()
                                        |
                                   Propagate up goroutine's stack
                                        |
                                   CRASH ENTIRE PROGRAM
                                   (kể cả main goroutine)

So sánh với error:
  error ──> return err ──> caller xử lý ──> chương trình tiếp tục
  panic ──> crash NOW ──> toàn bộ process chết
```

### 5. Phát hiện trong mã nguồn

**Regex patterns:**

```bash
# Tìm goroutine không có recover
rg "go func\(\)" -A 20 --type go | rg -v "recover\(\)"

# Tìm panic() calls trong goroutine context
rg "panic\(" --type go -n

# Tìm goroutine call bên ngoài mà không wrap recover
rg "go\s+\w+\(" --type go -n | rg -v "safe\|Safe\|Recover"

# Tìm http handler không có recover middleware
rg "http\.HandleFunc\|http\.Handle" --type go -A 5 | rg -v "recover\|middleware"
```

### 6. Giải pháp

| Tình huống | BAD | GOOD |
|-----------|-----|------|
| Goroutine | Không có recover | defer recover() |
| HTTP server | Không có middleware | Recovery middleware |
| Worker pool | Không handle panic | Wrap trong safeGo |

**Code BAD:**
```go
// BAD: Panic trong goroutine crash toàn bộ program
func startWorker() {
    go func() {
        // Nếu processItem() panic => PROGRAM CRASH!
        processItem(nil) // nil pointer dereference = panic
    }()
}

// BAD: HTTP handler không có recovery
func handler(w http.ResponseWriter, r *http.Request) {
    data := getDataFromNilPointer() // Panic!
    fmt.Fprint(w, data)             // Không bao giờ tới đây
}                                   // Server crash!
```

**Code GOOD:**
```go
// GOOD: Helper function bắt panic và convert thành error
func safeGo(fn func() error) <-chan error {
    errCh := make(chan error, 1)
    go func() {
        defer func() {
            if r := recover(); r != nil {
                // Convert panic thành error
                err := fmt.Errorf("panic recovered: %v\n%s", r, debug.Stack())
                errCh <- err
            }
            close(errCh)
        }()
        errCh <- fn()
    }()
    return errCh
}

// Sử dụng safeGo
func startWorker() {
    errCh := safeGo(func() error {
        return processItem(nil)
    })

    if err := <-errCh; err != nil {
        log.Printf("Worker error: %v", err)
    }
}

// GOOD: Recovery middleware cho HTTP server
func recoveryMiddleware(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        defer func() {
            if r := recover(); r != nil {
                log.Printf("Panic recovered: %v\n%s", r, debug.Stack())
                http.Error(w, "Internal Server Error", http.StatusInternalServerError)
            }
        }()
        next.ServeHTTP(w, r)
    })
}

// GOOD: Worker pool với panic recovery
type WorkerPool struct {
    jobs chan func()
    wg   sync.WaitGroup
}

func (p *WorkerPool) runWorker() {
    defer p.wg.Done()
    for job := range p.jobs {
        func() {
            defer func() {
                if r := recover(); r != nil {
                    log.Printf("Job panicked: %v", r)
                    // Goroutine tiếp tục chạy job tiếp theo
                }
            }()
            job()
        }()
    }
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Mọi goroutine long-running phải có `defer recover()`
- [ ] HTTP server phải dùng recovery middleware
- [ ] Worker pool phải wrap panic per job
- [ ] Log stack trace khi recover để debug
- [ ] Convert panic thành error để caller có thể handle
- [ ] Không dùng blank `recover()` - luôn log thông tin về panic

**Go vet / staticcheck rules:**
```bash
go vet ./...
staticcheck ./...
# golangci-lint với paniccheck
golangci-lint run --enable errcheck
```

---

## Pattern 16: errgroup Thiếu {#pattern-16}

### 1. Tên
**Thiếu Dùng errgroup** (Missing errgroup Usage)

### 2. Phân loại
Domain: Goroutine & Channel / Subcategory: Error Handling, Concurrency Patterns

### 3. Mức nghiêm trọng
> MEDIUM - Không dùng errgroup dẫn đến code phức tạp, error từ goroutine bị bỏ qua, và thiếu cancellation khi một goroutine lỗi.

### 4. Vấn đề

Khi chạy nhiều goroutine concurrent và cần thu thập error, pattern thủ công với WaitGroup + error channel dễ có bug: bỏ sót error, goroutine tiếp tục chạy khi một cái đã lỗi, hoặc không có cơ chế cancel.

```
Manual Pattern (dễ bug):
  var errs []error
  var mu sync.Mutex
  var wg sync.WaitGroup

  for _, task := range tasks {
      wg.Add(1)
      go func(t Task) {
          defer wg.Done()
          if err := process(t); err != nil {
              mu.Lock()
              errs = append(errs, err)
              mu.Unlock()
              // Các goroutine khác KHÔNG BIẾT có lỗi, vẫn chạy tiếp!
          }
      }(task)
  }
  wg.Wait()

errgroup Pattern (đúng):
  g, ctx := errgroup.WithContext(ctx)
  for _, task := range tasks {
      t := task
      g.Go(func() error {
          return process(ctx, t) // ctx bị cancel khi có lỗi đầu tiên
      })
  }
  err := g.Wait() // Trả về lỗi đầu tiên (hoặc nil)
```

### 5. Phát hiện trong mã nguồn

**Regex patterns:**

```bash
# Tìm WaitGroup với error collection thủ công
rg "var.*\[\]error" --type go -B 5 -A 10 | rg "wg\.\|WaitGroup"

# Tìm error channel thủ công
rg "make\(chan error" --type go -n

# Tìm errgroup import (code dùng đúng rồi)
rg "errgroup" --type go -n

# Tìm goroutine pattern với WaitGroup mà không có errgroup
rg "sync\.WaitGroup" --type go -A 20 | rg "go func" | rg -v "errgroup"
```

### 6. Giải pháp

| Tình huống | BAD | GOOD |
|-----------|-----|------|
| Thu error | Manual mutex + slice | `errgroup.Group` |
| Cancel on first error | Không có | `errgroup.WithContext` |
| Limit concurrency | Manual semaphore | `errgroup.Group + sem` |

**Code BAD:**
```go
// BAD: Manual error collection, dễ bug và phức tạp
func processAllBad(ctx context.Context, tasks []Task) error {
    var (
        wg   sync.WaitGroup
        mu   sync.Mutex
        errs []error
    )

    for _, task := range tasks {
        task := task
        wg.Add(1)
        go func() {
            defer wg.Done()
            if err := process(ctx, task); err != nil {
                mu.Lock()
                errs = append(errs, err) // Goroutine khác không biết lỗi này!
                mu.Unlock()
            }
        }()
    }

    wg.Wait()
    if len(errs) > 0 {
        return fmt.Errorf("multiple errors: %v", errs)
    }
    return nil
}
```

**Code GOOD:**
```go
// GOOD: errgroup tự động cancel context khi có lỗi đầu tiên
import "golang.org/x/sync/errgroup"

func processAllGood(ctx context.Context, tasks []Task) error {
    g, ctx := errgroup.WithContext(ctx)

    for _, task := range tasks {
        task := task // Capture loop variable
        g.Go(func() error {
            // ctx bị cancel nếu goroutine khác trả lỗi
            return process(ctx, task)
        })
    }

    // Chờ tất cả và trả về lỗi đầu tiên (hoặc nil)
    return g.Wait()
}

// GOOD: errgroup với giới hạn concurrency
func processWithLimit(ctx context.Context, tasks []Task, limit int) error {
    g, ctx := errgroup.WithContext(ctx)
    g.SetLimit(limit) // Chỉ N goroutine cùng lúc (Go 1.20+)

    for _, task := range tasks {
        task := task
        g.Go(func() error {
            return process(ctx, task)
        })
    }

    return g.Wait()
}

// GOOD: Thu thập kết quả với errgroup
func fetchAll(ctx context.Context, ids []int) ([]Result, error) {
    results := make([]Result, len(ids))
    g, ctx := errgroup.WithContext(ctx)

    for i, id := range ids {
        i, id := i, id // Capture
        g.Go(func() error {
            result, err := fetchOne(ctx, id)
            if err != nil {
                return fmt.Errorf("fetch %d: %w", id, err)
            }
            results[i] = result // Safe: mỗi goroutine ghi vào index khác
            return nil
        })
    }

    if err := g.Wait(); err != nil {
        return nil, err
    }
    return results, nil
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Khi chạy concurrent goroutines cần collect error → dùng `errgroup`
- [ ] Cần cancel khi một goroutine lỗi → `errgroup.WithContext`
- [ ] Giới hạn concurrency → `g.SetLimit(n)` (Go 1.20+)
- [ ] Không tự viết WaitGroup + mutex + error slice khi errgroup đủ dùng
- [ ] Import: `golang.org/x/sync/errgroup`

**Go vet / staticcheck rules:**
```bash
go vet ./...
staticcheck ./...
golangci-lint run
```

---

## Pattern 17: Atomic Và Mutex Trộn {#pattern-17}

### 1. Tên
**Trộn Lẫn Atomic và Mutex** (Mixing Atomic and Mutex)

### 2. Phân loại
Domain: Goroutine & Channel / Subcategory: Synchronization, Data Integrity

### 3. Mức nghiêm trọng
> HIGH - Trộn atomic operations và mutex protection trên cùng biến tạo ra false sense of security. Atomic bảo vệ một operation, mutex bảo vệ critical section. Dùng cả hai không nhất quán dẫn đến race condition.

### 4. Vấn đề

Atomic operations (`sync/atomic`) đảm bảo một operation đơn lẻ là atomic. Mutex bảo vệ một đoạn code (critical section). Trộn lẫn: một goroutine dùng atomic load, goroutine khác dùng mutex để update cùng biến, tạo ra race condition vì chúng dùng hai cơ chế đồng bộ khác nhau.

```
Mixed Sync - Race Condition:

Goroutine A:                    Goroutine B:
  atomic.LoadInt64(&counter)      mu.Lock()
  // Đọc atomically               counter += delta  // Không atomic
  // Nhưng giữa Load và +1        counter = newVal  // Có thể race với Load!
  atomic.AddInt64(&counter, 1)    mu.Unlock()

Vấn đề: atomic.Load và mutex.Lock không phối hợp với nhau!
  atomic chỉ đảm bảo memory ordering cho chính nó
  mutex chỉ bảo vệ code trong Lock/Unlock block
```

### 5. Phát hiện trong mã nguồn

**Regex patterns:**

```bash
# Tìm file dùng cả atomic và mutex trên cùng biến
rg "atomic\." --type go -l | xargs -I{} rg "sync\.Mutex" {}

# Tìm mixed sync patterns
rg "atomic\.Load\|atomic\.Store" --type go -B 5 -A 5 | rg "mu\.Lock\|mu\.Unlock"

# Tìm biến dùng cả atomic và non-atomic access
rg "atomic\.\w+\(&\w+" --type go -n

# Tìm struct với cả atomic field và mutex bảo vệ field khác
rg "int64\b\|int32\b" --type go -B 3 | rg "atomic\.\|sync\.Mutex"
```

### 6. Giải pháp

| Trường hợp | Dùng | Không dùng |
|-----------|------|-----------|
| Đếm đơn giản | `atomic.AddInt64` | Mutex |
| Đọc/ghi struct | Mutex | Atomic |
| Flag boolean | `atomic.Bool` | Mutex |
| Nhiều field liên quan | Mutex (bảo vệ cả group) | Atomic riêng lẻ |

**Code BAD:**
```go
// BAD: Trộn atomic và mutex trên cùng struct
type MixedCounter struct {
    mu    sync.Mutex
    count int64
}

func (c *MixedCounter) Add(delta int64) {
    c.mu.Lock()
    c.count += delta // Dùng mutex
    c.mu.Unlock()
}

func (c *MixedCounter) Load() int64 {
    return atomic.LoadInt64(&c.count) // Dùng atomic! RACE với mu.Lock path!
}

// BAD: Dùng cả hai không nhất quán
var counter int64

func incrementMixed() {
    atomic.AddInt64(&counter, 1) // Goroutine A dùng atomic
}

func resetMixed() {
    mu.Lock()
    counter = 0 // Goroutine B dùng mutex - RACE với atomic!
    mu.Unlock()
}
```

**Code GOOD:**
```go
// GOOD: Chỉ dùng atomic
type AtomicCounter struct {
    count atomic.Int64 // Go 1.19+ atomic types
}

func (c *AtomicCounter) Add(delta int64) {
    c.count.Add(delta)
}

func (c *AtomicCounter) Load() int64 {
    return c.count.Load()
}

// GOOD: Chỉ dùng mutex (nhất quán)
type MutexCounter struct {
    mu    sync.Mutex
    count int64
}

func (c *MutexCounter) Add(delta int64) {
    c.mu.Lock()
    defer c.mu.Unlock()
    c.count += delta
}

func (c *MutexCounter) Load() int64 {
    c.mu.Lock()
    defer c.mu.Unlock()
    return c.count
}

// GOOD: Nhiều fields cùng bảo vệ bởi một mutex
type Stats struct {
    mu      sync.RWMutex
    count   int64
    total   float64
    lastSeen time.Time
}

func (s *Stats) Record(value float64) {
    s.mu.Lock()
    defer s.mu.Unlock()
    s.count++
    s.total += value
    s.lastSeen = time.Now()
    // Tất cả fields được update atomically trong cùng lock
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Chọn một cơ chế: atomic HOẶC mutex - không trộn lẫn cho cùng dữ liệu
- [ ] Atomic cho: đếm, flag boolean, pointer swap đơn giản
- [ ] Mutex cho: struct phức tạp, nhiều fields liên quan nhau
- [ ] Dùng `atomic.Bool`, `atomic.Int64` (Go 1.19+) thay vì primitive với atomic functions
- [ ] Document rõ ràng cơ chế sync nào bảo vệ field nào trong struct

**Go vet / staticcheck rules:**
```bash
go test -race ./...    # Race detector sẽ bắt mixed sync bugs
go vet ./...
staticcheck ./...
```

---

## Pattern 18: Pool Exhaustion {#pattern-18}

### 1. Tên
**Cạn Kiệt Pool Tài Nguyên** (Resource Pool Exhaustion)

### 2. Phân loại
Domain: Goroutine & Channel / Subcategory: Resource Management, Performance

### 3. Mức nghiêm trọng
> HIGH - Pool exhaustion gây tất cả goroutine block chờ tài nguyên (DB connection, HTTP connection), làm chương trình freeze hoàn toàn dưới tải cao.

### 4. Vấn đề

Pool (connection pool, worker pool) có kích thước giới hạn. Khi tất cả resources được sử dụng và goroutine mới cần tài nguyên, chúng bị block chờ. Nếu số goroutine chờ vượt quá capacity, system freeze. `sync.Pool` trong Go có semantics khác (GC có thể drain pool).

```
Pool Exhaustion:

DB Connection Pool (size=10):
  conn_1 ──> goroutine_1 (đang dùng, không trả)
  conn_2 ──> goroutine_2 (đang dùng, không trả)
  ...
  conn_10 ──> goroutine_10 (đang dùng, không trả)

  goroutine_11 ──> TryGetConn() ──> BLOCK!
  goroutine_12 ──> TryGetConn() ──> BLOCK!
  ...
  goroutine_100 ──> TryGetConn() ──> BLOCK!

  => Tất cả request mới bị treo
  => HTTP server không response
  => Load balancer timeout
  => Cascade failure!

sync.Pool (khác!):
  sync.Pool KHÔNG giữ lại objects sau GC
  Chỉ dùng để giảm allocation, không phải connection pool
```

### 5. Phát hiện trong mã nguồn

**Regex patterns:**

```bash
# Tìm database pool không có timeout
rg "sql\.Open\|db\.Ping" --type go -B 2 -A 10 | rg -v "SetMaxOpenConns\|SetMaxIdleConns\|SetConnMaxLifetime"

# Tìm HTTP client không có timeout
rg "http\.Client\|&http\.Client" --type go -A 5 | rg -v "Timeout"

# Tìm sync.Pool dùng sai (object lớn, connection...)
rg "sync\.Pool" --type go -A 10 | rg "sql\|http\|conn\|socket"

# Tìm goroutine pool không có limit
rg "go func\(\)" --type go -n | rg -v "sem\|limit\|pool\|worker"

# Tìm defer rows.Close() bị thiếu (connection không được trả)
rg "sql\.Query\|\.QueryRow\|\.Prepare" --type go -A 5 | rg -v "defer.*Close\(\)"
```

### 6. Giải pháp

| Loại Pool | BAD | GOOD |
|----------|-----|------|
| DB connections | Không giới hạn, không timeout | SetMaxOpenConns + SetConnMaxLifetime |
| HTTP client | Default client (không limit) | Custom client với limits |
| Worker pool | Unlimited goroutines | Semaphore hoặc worker pool |
| sync.Pool | Dùng cho connections | Chỉ dùng cho reusable objects |

**Code BAD:**
```go
// BAD: DB pool không được cấu hình
func setupDB() *sql.DB {
    db, _ := sql.Open("postgres", dsn)
    // Không set limits! Default = unlimited connections
    return db
}

// BAD: Connection leak - rows không được close
func queryUsersLeak(db *sql.DB) {
    rows, err := db.Query("SELECT id, name FROM users")
    if err != nil {
        return
    }
    // KHÔNG có defer rows.Close()!
    // Connection không được trả về pool!
    for rows.Next() {
        var u User
        rows.Scan(&u.ID, &u.Name)
        process(u)
    }
    // Connection bị giữ cho đến khi GC (rất lâu!)
}

// BAD: HTTP client unlimited
func fetchAll(urls []string) {
    for _, url := range urls {
        go func(u string) {
            // Default http.Client, không limit connections!
            resp, _ := http.Get(u) // Tạo connection mới không kiểm soát!
            defer resp.Body.Close()
        }(url)
    }
}
```

**Code GOOD:**
```go
// GOOD: DB pool được cấu hình đúng
func setupDB() *sql.DB {
    db, err := sql.Open("postgres", dsn)
    if err != nil {
        log.Fatal(err)
    }

    db.SetMaxOpenConns(25)                 // Tối đa 25 connections mở
    db.SetMaxIdleConns(10)                 // Tối đa 10 idle connections
    db.SetConnMaxLifetime(5 * time.Minute) // Connection sống tối đa 5 phút
    db.SetConnMaxIdleTime(2 * time.Minute) // Idle connection tối đa 2 phút

    return db
}

// GOOD: Luôn defer rows.Close()
func queryUsers(ctx context.Context, db *sql.DB) ([]User, error) {
    rows, err := db.QueryContext(ctx, "SELECT id, name FROM users")
    if err != nil {
        return nil, err
    }
    defer rows.Close() // LUÔN defer Close để trả connection về pool

    var users []User
    for rows.Next() {
        var u User
        if err := rows.Scan(&u.ID, &u.Name); err != nil {
            return nil, err
        }
        users = append(users, u)
    }
    return users, rows.Err()
}

// GOOD: HTTP client với limits
var httpClient = &http.Client{
    Timeout: 30 * time.Second,
    Transport: &http.Transport{
        MaxIdleConns:        100,              // Tổng idle connections
        MaxIdleConnsPerHost: 10,               // Idle connections per host
        MaxConnsPerHost:     10,               // Max connections per host
        IdleConnTimeout:     90 * time.Second,
        TLSHandshakeTimeout: 10 * time.Second,
        DisableCompression:  false,
    },
}

// GOOD: Worker pool với giới hạn
func processURLs(ctx context.Context, urls []string) error {
    g, ctx := errgroup.WithContext(ctx)
    g.SetLimit(10) // Tối đa 10 goroutine cùng lúc

    for _, url := range urls {
        url := url
        g.Go(func() error {
            resp, err := httpClient.Get(url)
            if err != nil {
                return err
            }
            defer resp.Body.Close()
            return processResponse(resp)
        })
    }

    return g.Wait()
}

// GOOD: sync.Pool đúng cách (chỉ cho reusable objects, không phải connections)
var bufPool = sync.Pool{
    New: func() interface{} {
        return new(bytes.Buffer)
    },
}

func processData(data []byte) string {
    buf := bufPool.Get().(*bytes.Buffer)
    buf.Reset() // Reset trước khi dùng
    defer bufPool.Put(buf)

    buf.Write(data)
    return buf.String()
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Luôn cấu hình `SetMaxOpenConns`, `SetMaxIdleConns`, `SetConnMaxLifetime` cho DB
- [ ] Luôn `defer rows.Close()` sau `db.Query()`
- [ ] Dùng `QueryContext` với context để có timeout
- [ ] HTTP client phải có `Timeout` và `Transport` limits
- [ ] Giới hạn goroutine concurrent bằng semaphore hoặc `errgroup.SetLimit`
- [ ] Monitor pool metrics: `db.Stats()`, goroutine count, connection count
- [ ] `sync.Pool` chỉ cho byte buffers, string builders - KHÔNG cho connections

**Go vet / staticcheck rules:**
```bash
go vet ./...
staticcheck -checks "SA1019" ./...
go test -race ./...
# sqlvet để kiểm tra SQL queries
go install github.com/houqp/sqlvet@latest && sqlvet .
```

---

## Tóm tắt nhanh

| # | Pattern | Mức độ | Công cụ phát hiện | Fix chính |
|---|---------|--------|-------------------|-----------|
| 01 | Goroutine Leak | CRITICAL | goleak, pprof | Context + done channel |
| 02 | Channel Deadlock | CRITICAL | go test -timeout | Buffered / receiver trước |
| 03 | Thundering Herd | HIGH | pprof | singleflight + jitter |
| 04 | Race Condition | CRITICAL | go test -race | Mutex / atomic |
| 05 | Select No Default | MEDIUM | manual review | Thêm default case |
| 06 | Channel Direction | MEDIUM | go vet | chan<- / <-chan |
| 07 | WaitGroup Misuse | CRITICAL | go vet | Add() trước go func |
| 08 | Context Ignored | HIGH | golangci-lint | defer cancel(), ctx.Done() |
| 09 | Mutex Copy | CRITICAL | go vet (copylocks) | Pointer receiver |
| 10 | Nil Channel | CRITICAL | go vet | Khởi tạo, kiểm tra nil |
| 11 | Loop Capture | HIGH | go vet | Pass như parameter |
| 12 | Timer Leak | HIGH | staticcheck SA1015 | NewTimer + Stop |
| 13 | Semaphore Wrong | MEDIUM | go test -race | defer release |
| 14 | Done Not Closed | HIGH | goleak | close(done) |
| 15 | Goroutine Panic | CRITICAL | testing | defer recover() |
| 16 | Missing errgroup | MEDIUM | manual review | errgroup.Group |
| 17 | Atomic+Mutex Mix | HIGH | go test -race | Chọn một cơ chế |
| 18 | Pool Exhaustion | HIGH | pprof, db.Stats() | SetMaxConns + defer Close |

## Lệnh kiểm tra nhanh

```bash
# Bộ lệnh kiểm tra đầy đủ
go build ./...                          # Build check
go vet ./...                            # Vet check
go test -race ./...                     # Race detector
go test -timeout 60s ./...              # Timeout check (phát hiện deadlock)
staticcheck ./...                       # Advanced static analysis
golangci-lint run                       # Meta linter

# Profile goroutines trong production
curl http://localhost:6060/debug/pprof/goroutine?debug=2

# Kiểm tra goroutine count
curl http://localhost:6060/debug/pprof/goroutine | grep "goroutine "
```
