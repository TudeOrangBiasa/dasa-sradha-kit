# Domain 02: Hệ Thống Phân Tán (Distributed Systems)

| Thuộc tính   | Giá trị                                      |
|--------------|----------------------------------------------|
| **Lĩnh vực** | Distributed Systems / Hệ thống phân tán      |
| **Ngôn ngữ** | Go (Golang)                                   |
| **Số mẫu**   | 12 patterns                                   |
| **Phiên bản**| Go 1.21+                                      |
| **Cập nhật** | 2026-02-18                                    |

---

## Mục lục

1. [gRPC Deadline Thiếu (Missing gRPC Deadline)](#pattern-01)
2. [Retry Storm](#pattern-02)
3. [Circuit Breaker Thiếu](#pattern-03)
4. [Distributed Lock Sai (Incorrect Distributed Lock)](#pattern-04)
5. [Idempotency Thiếu (Missing Idempotency)](#pattern-05)
6. [Service Discovery Cache](#pattern-06)
7. [Shard Rebalancing](#pattern-07)
8. [Message Queue Backpressure](#pattern-08)
9. [Split Brain](#pattern-09)
10. [Saga Compensation Thiếu](#pattern-10)
11. [Health Check Giả (Superficial Health Check)](#pattern-11)
12. [Connection Pool Stale](#pattern-12)

---

## Pattern 01: gRPC Deadline Thiếu {#pattern-01}

### 1. Tên
**gRPC Deadline Thiếu** (Missing gRPC Deadline)

### 2. Phân loại
Domain: Distributed Systems / Subcategory: gRPC, Timeout, Service Reliability

### 3. Mức nghiêm trọng
> CRITICAL - Khi gRPC call không có deadline, một service downstream bị chậm sẽ kéo theo toàn bộ chuỗi service phía trên bị block vô thời hạn. Goroutine, connection pool và memory bị giữ cho đến khi process bị kill hoặc OOM.

### 4. Vấn đề

Không đặt deadline trên gRPC call khiến client block vô hạn nếu server không phản hồi. Trong kiến trúc microservice dạng fan-out, một service chậm gây hiệu ứng domino toàn hệ thống.

```
Không có deadline - Hiệu ứng Domino:

  Client A --[gRPC, no deadline]--> Service B --[gRPC, no deadline]--> Service C
                                         |                                  |
                                    goroutine                          goroutine
                                    BLOCKED                            BLOCKED
                                    (forever)                          (forever)

  Service C bị chậm (DB slow):
    t=0s    Service C bắt đầu xử lý
    t=30s   Service C vẫn đang xử lý
    t=60s   Service B goroutine pool exhausted
    t=90s   Client A goroutine pool exhausted
    t=120s  OOM KILL toàn bộ chuỗi

Có deadline - Fail Fast:

  Client A --[deadline=5s]--> Service B --[deadline=4s]--> Service C
                                                                |
                                                         t=5s: DEADLINE_EXCEEDED
                                                         Error propagated up
                                                         Resources released immediately
```

Nguyên nhân phổ biến:
- Dùng `context.Background()` trực tiếp làm ctx khi gọi gRPC
- Truyền ctx từ request nhưng không đặt thêm deadline child
- Không propagate deadline headers khi gọi service khác
- Deadline không budget đủ cho retry và overhead mạng

### 5. Phát hiện trong mã nguồn

**Dấu hiệu trong code:**
- `context.Background()` hoặc `context.TODO()` được truyền trực tiếp vào gRPC call
- Không có `context.WithDeadline` hoặc `context.WithTimeout` trước khi gọi gRPC
- gRPC call trong goroutine không ràng buộc với parent context
- Import `google.golang.org/grpc` nhưng không import `"google.golang.org/grpc/codes"`

**Regex patterns (dùng với ripgrep):**

```bash
# Tìm gRPC call dùng context.Background() trực tiếp
rg "\..*Client\(context\.Background\(\)" --type go -n

# Tìm gRPC stub call không có deadline trong context
rg "ctx\s*:=\s*context\.Background\(\)" --type go -n -A 5

# Tìm gRPC call thiếu timeout
rg "grpc\.Dial|grpc\.NewClient" --type go -n

# Tìm file có gRPC nhưng không có WithDeadline/WithTimeout
rg --files-with-matches "grpc\." --type go | xargs rg -L "WithDeadline\|WithTimeout"

# Tìm context không có deadline truyền vào pb client method
rg "\.(Get|Create|Update|Delete|List)\(ctx\b" --type go -n
```

**Công cụ phát hiện runtime:**
```bash
# Kiểm tra gRPC interceptor có deadline enforcement không
rg "UnaryClientInterceptor\|StreamClientInterceptor" --type go -n

# Kiểm tra metrics deadline exceeded
# prometheus query: grpc_client_handled_total{grpc_code="DeadlineExceeded"}
```

### 6. Giải pháp

| Phương pháp | Trước (BAD) | Sau (GOOD) |
|-------------|-------------|------------|
| Context | `context.Background()` | `context.WithTimeout(ctx, 5*time.Second)` |
| Propagation | Tạo context mới | Inherit từ request context |
| Budget | Không tính | Deadline parent - overhead |
| Interceptor | Không có | Deadline enforcement interceptor |
| Error handling | Không check code | Check `codes.DeadlineExceeded` |

**Code BAD - gRPC call không có deadline:**
```go
// BAD: Dùng context.Background() - block vô hạn nếu server chết
func (s *OrderService) GetProduct(productID string) (*pb.Product, error) {
    ctx := context.Background() // NGUY HIỂM: không có deadline

    resp, err := s.productClient.GetProduct(ctx, &pb.GetProductRequest{
        ProductId: productID,
    })
    if err != nil {
        return nil, err
    }
    return resp, nil
}

// BAD: Propagate request context nhưng không thêm deadline
func (h *Handler) HandleOrder(w http.ResponseWriter, r *http.Request) {
    ctx := r.Context() // HTTP context không có gRPC deadline

    // gRPC call có thể block cho đến khi HTTP client timeout
    product, err := h.orderSvc.GetProduct(ctx, "prod-123")
    if err != nil {
        http.Error(w, err.Error(), 500)
        return
    }
    json.NewEncoder(w).Encode(product)
}
```

**Code GOOD - gRPC call với deadline đúng:**
```go
// GOOD: Luôn đặt deadline trước khi gọi gRPC
func (s *OrderService) GetProduct(ctx context.Context, productID string) (*pb.Product, error) {
    // Tạo child context với deadline budget
    // Trừ 500ms cho network overhead và retry
    callCtx, cancel := context.WithTimeout(ctx, 4500*time.Millisecond)
    defer cancel()

    resp, err := s.productClient.GetProduct(callCtx, &pb.GetProductRequest{
        ProductId: productID,
    })
    if err != nil {
        // Phân biệt timeout vs lỗi khác để có chiến lược retry phù hợp
        if status.Code(err) == codes.DeadlineExceeded {
            return nil, fmt.Errorf("product service timeout after 4.5s: %w", err)
        }
        return nil, fmt.Errorf("product service error: %w", err)
    }
    return resp, nil
}

// GOOD: Interceptor bắt buộc deadline trên mọi gRPC call
func DeadlineEnforcementInterceptor(
    defaultTimeout time.Duration,
) grpc.UnaryClientInterceptor {
    return func(
        ctx context.Context,
        method string,
        req, reply interface{},
        cc *grpc.ClientConn,
        invoker grpc.UnaryInvoker,
        opts ...grpc.CallOption,
    ) error {
        // Nếu context chưa có deadline, đặt deadline mặc định
        if _, ok := ctx.Deadline(); !ok {
            var cancel context.CancelFunc
            ctx, cancel = context.WithTimeout(ctx, defaultTimeout)
            defer cancel()
        }
        return invoker(ctx, method, req, reply, cc, opts...)
    }
}

// GOOD: Khởi tạo gRPC client với interceptor
func NewProductClient(addr string) (pb.ProductServiceClient, error) {
    conn, err := grpc.NewClient(addr,
        grpc.WithTransportCredentials(insecure.NewCredentials()),
        grpc.WithUnaryInterceptor(DeadlineEnforcementInterceptor(5*time.Second)),
    )
    if err != nil {
        return nil, err
    }
    return pb.NewProductServiceClient(conn), nil
}

// GOOD: Handler propagate context đúng
func (h *Handler) HandleOrder(w http.ResponseWriter, r *http.Request) {
    ctx := r.Context() // HTTP context (có deadline từ HTTP server)

    // OrderService sẽ tự đặt deadline child
    product, err := h.orderSvc.GetProduct(ctx, "prod-123")
    if err != nil {
        if status.Code(err) == codes.DeadlineExceeded {
            http.Error(w, "upstream timeout", http.StatusGatewayTimeout)
            return
        }
        http.Error(w, err.Error(), http.StatusInternalServerError)
        return
    }
    json.NewEncoder(w).Encode(product)
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Mọi gRPC call phải có `context.WithTimeout` hoặc `context.WithDeadline`
- [ ] Không bao giờ dùng `context.Background()` trực tiếp trong gRPC call production
- [ ] Deadline budget = parent deadline - network overhead (500ms) - retry time
- [ ] Cài `DeadlineEnforcementInterceptor` làm safety net mặc định
- [ ] Monitor metric `grpc_client_handled_total{grpc_code="DeadlineExceeded"}`
- [ ] Set `ReadHeaderTimeout`, `ReadTimeout`, `WriteTimeout` trên HTTP server
- [ ] Test với timeout simulation: `grpc.WithBlock()` + context cancel

**Go vet / staticcheck rules:**
```bash
# Vet cơ bản
go vet ./...

# Staticcheck - phát hiện context misuse
staticcheck -checks "SA1012,SA1014" ./...

# errcheck - đảm bảo lỗi gRPC được handle
errcheck -ignoretests ./...

# Custom lint với golangci-lint
golangci-lint run --enable contextcheck,noctx ./...
```

---

## Pattern 02: Retry Storm {#pattern-02}

### 1. Tên
**Retry Storm** (Cơn Bão Retry)

### 2. Phân loại
Domain: Distributed Systems / Subcategory: Retry, Resilience, Cascading Failure

### 3. Mức nghiêm trọng
> CRITICAL - Khi nhiều client đồng thời retry vào service đang gặp sự cố, lưu lượng retry khuếch đại vượt capacity bình thường nhiều lần. Service vừa phục hồi ngay lập tức bị đánh sập trở lại vì không thể xử lý lượng retry burst.

### 4. Vấn đề

Retry đồng bộ mà không có jitter (nhiễu thời gian ngẫu nhiên) và exponential backoff sẽ tạo ra thundering herd. Tất cả client cùng retry đúng cùng một thời điểm, tạo spike tải đột ngột.

```
Retry Storm - 1000 client cùng retry:

  t=0s:   Service DOWN
          1000 clients nhận lỗi, đều schedule retry sau 1s

  t=1s:   1000 requests HIT service cùng lúc
          Service vừa phục hồi --> BỊ ĐÁNH SẬP LẠI

  t=2s:   1000 retry lần 2 (fixed interval)
          Service DOWN --> 1000 requests nữa

  Pattern: Oscillation - không bao giờ phục hồi được

Với Exponential Backoff + Jitter:

  t=0s:   Service DOWN
          Client A: retry sau 1.3s (1s + 300ms jitter)
          Client B: retry sau 0.8s (1s - 200ms jitter)
          Client C: retry sau 1.7s (1s + 700ms jitter)
          ... 1000 clients spread ra trong window [0.5s, 2s]

  t=1s:   ~100 requests (spread đều, service có thể handle)
  t=2s:   ~200 requests (dần phục hồi)
  t=4s:   Service ổn định trở lại
```

Nguyên nhân phổ biến:
- Retry với interval cố định (fixed delay)
- Không có jitter trong retry logic
- Retry không có max attempts
- Retry trên lỗi không thể retry được (4xx client errors)
- Không phân biệt transient error vs permanent error

### 5. Phát hiện trong mã nguồn

**Dấu hiệu trong code:**
- `time.Sleep(fixedDuration)` trong retry loop
- `for i := 0; i < maxRetries; i++` không có backoff
- Retry trên tất cả lỗi kể cả `context.Canceled`
- Không có `math/rand` trong retry logic (thiếu jitter)
- Retry count không được monitor hoặc limit

**Regex patterns (dùng với ripgrep):**

```bash
# Tìm retry loop với fixed sleep
rg "for.*retry\|for.*attempt" --type go -n -A 3 | rg "time\.Sleep"

# Tìm retry không có jitter (thiếu rand)
rg -l "retry\|Retry" --type go | xargs rg -L "rand\."

# Tìm retry không có backoff
rg "time\.Sleep\(.*\*time\." --type go -n

# Tìm retry trên mọi lỗi (không check error type)
rg "for.*err != nil" --type go -n -A 5

# Tìm HTTP retry không check status code
rg "resp\.StatusCode" --type go -n -B 5 | rg "retry\|attempt"
```

### 6. Giải pháp

| Phương pháp | Trước (BAD) | Sau (GOOD) |
|-------------|-------------|------------|
| Delay | Fixed 1s | Exponential 2^n * base |
| Jitter | Không có | ±50% random spread |
| Max attempts | Không giới hạn | Max 3-5 lần |
| Error filter | Retry tất cả | Chỉ retry transient |
| Backoff cap | Không có | Tối đa 30s |

**Code BAD - Retry storm trigger:**
```go
// BAD: Fixed delay, retry mọi lỗi, không có jitter
func callServiceBad(url string) (*http.Response, error) {
    maxRetries := 5
    for i := 0; i < maxRetries; i++ {
        resp, err := http.Get(url)
        if err != nil {
            time.Sleep(1 * time.Second) // FIXED DELAY: tất cả client sleep 1s rồi cùng retry
            continue
        }
        if resp.StatusCode >= 500 {
            resp.Body.Close()
            time.Sleep(1 * time.Second) // FIXED DELAY: 1000 clients cùng thức dậy sau 1s
            continue
        }
        return resp, nil
    }
    return nil, fmt.Errorf("max retries exceeded")
}
```

**Code GOOD - Retry với exponential backoff và jitter:**
```go
// GOOD: Exponential backoff với full jitter
type RetryConfig struct {
    MaxAttempts int
    BaseDelay   time.Duration
    MaxDelay    time.Duration
    Multiplier  float64
}

var DefaultRetryConfig = RetryConfig{
    MaxAttempts: 3,
    BaseDelay:   500 * time.Millisecond,
    MaxDelay:    30 * time.Second,
    Multiplier:  2.0,
}

// isRetryable phân biệt lỗi có thể retry vs lỗi vĩnh viễn
func isRetryable(err error, statusCode int) bool {
    // Không retry context cancel/deadline
    if errors.Is(err, context.Canceled) || errors.Is(err, context.DeadlineExceeded) {
        return false
    }
    // Không retry client errors (4xx trừ 429)
    if statusCode >= 400 && statusCode < 500 && statusCode != 429 {
        return false
    }
    // Retry server errors (5xx) và network errors
    return true
}

// calculateBackoff tính delay với exponential backoff + full jitter
// Full jitter: random trong [0, min(maxDelay, base * multiplier^attempt)]
func calculateBackoff(cfg RetryConfig, attempt int) time.Duration {
    exp := math.Pow(cfg.Multiplier, float64(attempt))
    ceiling := time.Duration(float64(cfg.BaseDelay) * exp)
    if ceiling > cfg.MaxDelay {
        ceiling = cfg.MaxDelay
    }
    // Full jitter: random trong [0, ceiling]
    //nolint:gosec // jitter không cần crypto random
    jitter := time.Duration(rand.Int63n(int64(ceiling)))
    return jitter
}

func callServiceWithRetry(ctx context.Context, url string, cfg RetryConfig) (*http.Response, error) {
    var lastErr error
    for attempt := 0; attempt < cfg.MaxAttempts; attempt++ {
        if attempt > 0 {
            delay := calculateBackoff(cfg, attempt)
            select {
            case <-ctx.Done():
                return nil, fmt.Errorf("retry cancelled after %d attempts: %w", attempt, ctx.Err())
            case <-time.After(delay):
            }
        }

        req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
        if err != nil {
            return nil, err // Không retry: bad request
        }

        resp, err := http.DefaultClient.Do(req)
        if err != nil {
            if !isRetryable(err, 0) {
                return nil, err
            }
            lastErr = err
            continue
        }

        if resp.StatusCode < 500 && resp.StatusCode != 429 {
            return resp, nil // Thành công hoặc lỗi client - không retry
        }

        resp.Body.Close()
        lastErr = fmt.Errorf("server error: %d", resp.StatusCode)

        // Respect Retry-After header nếu có
        if retryAfter := resp.Header.Get("Retry-After"); retryAfter != "" {
            if d, err := time.ParseDuration(retryAfter + "s"); err == nil {
                select {
                case <-ctx.Done():
                    return nil, ctx.Err()
                case <-time.After(d):
                    continue
                }
            }
        }
    }
    return nil, fmt.Errorf("all %d attempts failed, last error: %w", cfg.MaxAttempts, lastErr)
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Dùng exponential backoff: `base * 2^attempt`
- [ ] Luôn thêm jitter: random trong `[0, backoff]` (full jitter) hoặc `[backoff/2, backoff]` (equal jitter)
- [ ] Giới hạn max attempts (3-5 cho external calls)
- [ ] Cap max delay (30s thường hợp lý)
- [ ] Không retry 4xx (trừ 429 Too Many Requests)
- [ ] Không retry khi `context.Canceled` hoặc `context.DeadlineExceeded`
- [ ] Monitor retry rate: nếu > 10% là dấu hiệu có vấn đề
- [ ] Dùng library chuẩn: `github.com/cenkalti/backoff/v4`

**Go vet / staticcheck rules:**
```bash
# Vet cơ bản
go vet ./...

# Kiểm tra error handling trong retry
errcheck ./...

# Staticcheck
staticcheck -checks "SA1015" ./...

# golangci-lint với exhaustive error check
golangci-lint run --enable exhaustive,wrapcheck ./...
```

---

## Pattern 03: Circuit Breaker Thiếu {#pattern-03}

### 1. Tên
**Circuit Breaker Thiếu** (Missing Circuit Breaker)

### 2. Phân loại
Domain: Distributed Systems / Subcategory: Resilience, Failure Isolation, Cascading Failure

### 3. Mức nghiêm trọng
> HIGH - Thiếu circuit breaker khiến mọi request đều phải chờ timeout khi downstream service down. Goroutine pool và connection pool bị cạn kiệt nhanh chóng, kéo cả service đang hoạt động tốt xuống theo.

### 4. Vấn đề

Không có circuit breaker, service gọi downstream bị down sẽ cứ tiếp tục thử kết nối cho đến khi timeout. Trong thời gian đó, tất cả goroutine xử lý request bị block, service mất khả năng phục vụ.

```
Không có Circuit Breaker:

  Normal:      A --> B (OK, 10ms)
  B bị down:   A --> B (TIMEOUT, 30s) --> A --> B (TIMEOUT, 30s) --> ...
                                                      ^
                                          Mỗi request block 30s
                                          100 req/s x 30s = 3000 goroutines blocked
                                          --> Resource exhaustion

Circuit Breaker - 3 trạng thái:

  CLOSED (bình thường)
    --> Lỗi < threshold --> vẫn CLOSED
    --> Lỗi >= threshold --> OPEN

  OPEN (ngắt mạch)
    --> Tất cả request fail ngay lập tức (fast fail)
    --> Sau timeout window --> HALF-OPEN

  HALF-OPEN (thử nghiệm)
    --> Cho 1 request qua
    --> Thành công --> CLOSED
    --> Thất bại --> OPEN lại

  CLOSED ---[failure rate >= 50%]---> OPEN
    ^                                    |
    |                              [wait 30s]
    |                                    |
    +----[success]---- HALF-OPEN <-------+
```

Nguyên nhân phổ biến:
- Gọi HTTP/gRPC downstream trực tiếp không có circuit breaker
- Dùng retry nhưng không có circuit breaker (retry khuếch đại tải)
- Circuit breaker có nhưng threshold quá cao
- Không monitor trạng thái circuit breaker

### 5. Phát hiện trong mã nguồn

**Dấu hiệu trong code:**
- HTTP client call không bọc trong circuit breaker
- Không import `gobreaker`, `hystrix-go`, hoặc `sony/gobreaker`
- Service gọi nhiều downstream nhưng không có isolation
- Không có fallback logic khi call fail

**Regex patterns (dùng với ripgrep):**

```bash
# Tìm HTTP client call không có circuit breaker
rg "http\.Get\|http\.Post\|client\.Do" --type go -n

# Kiểm tra có dùng circuit breaker library không
rg "gobreaker\|hystrix\|circuitbreaker" --type go -n

# Tìm file gọi external service thiếu fallback
rg --files-with-matches "http\.Client\|grpc\.Dial" --type go | \
  xargs rg -L "fallback\|Fallback\|ErrOpenState"

# Tìm service call trong handler không có circuit breaker
rg -A 10 "func.*Handler\|func.*Handle" --type go | rg "\.Get\|\.Post\|\.Do("
```

### 6. Giải pháp

| Phương pháp | Trước (BAD) | Sau (GOOD) |
|-------------|-------------|------------|
| Call trực tiếp | `client.Do(req)` | `cb.Execute(func() {...})` |
| Fail fast | Chờ timeout 30s | Fail ngay khi OPEN |
| Isolation | Không có | Circuit breaker per dependency |
| Fallback | Không có | Cache/default response |
| Monitoring | Không có | Export state metrics |

**Code BAD - Gọi downstream trực tiếp:**
```go
// BAD: Không có circuit breaker - mọi request block khi B down
func (s *Service) GetUserProfile(ctx context.Context, userID string) (*Profile, error) {
    url := fmt.Sprintf("http://user-service/users/%s", userID)
    req, _ := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)

    // Nếu user-service down, call này block đến khi ctx timeout
    resp, err := s.httpClient.Do(req)
    if err != nil {
        return nil, err
    }
    defer resp.Body.Close()

    var profile Profile
    json.NewDecoder(resp.Body).Decode(&profile)
    return &profile, nil
}
```

**Code GOOD - Circuit breaker với sony/gobreaker:**
```go
// GOOD: Circuit breaker wrapper quanh downstream call
import "github.com/sony/gobreaker/v2"

type UserServiceClient struct {
    httpClient *http.Client
    cb         *gobreaker.CircuitBreaker[*Profile]
    cache      *ProfileCache
}

func NewUserServiceClient(httpClient *http.Client, cache *ProfileCache) *UserServiceClient {
    st := gobreaker.Settings{
        Name:        "user-service",
        MaxRequests: 3,                // Số request được phép qua khi HALF-OPEN
        Interval:    10 * time.Second, // Reset counters sau mỗi interval khi CLOSED
        Timeout:     30 * time.Second, // Thời gian OPEN trước khi thử HALF-OPEN
        ReadyToTrip: func(counts gobreaker.Counts) bool {
            // Ngắt mạch khi >= 5 request và error rate >= 60%
            if counts.Requests < 5 {
                return false
            }
            failureRatio := float64(counts.TotalFailures) / float64(counts.Requests)
            return failureRatio >= 0.6
        },
        OnStateChange: func(name string, from, to gobreaker.State) {
            // Monitor state changes
            log.Printf("circuit breaker %s: %s -> %s", name, from, to)
            circuitBreakerStateGauge.WithLabelValues(name, to.String()).Set(1)
        },
    }

    cb := gobreaker.NewCircuitBreaker[*Profile](st)
    return &UserServiceClient{
        httpClient: httpClient,
        cb:         cb,
        cache:      cache,
    }
}

func (c *UserServiceClient) GetUserProfile(ctx context.Context, userID string) (*Profile, error) {
    result, err := c.cb.Execute(func() (*Profile, error) {
        url := fmt.Sprintf("http://user-service/users/%s", userID)
        req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
        if err != nil {
            return nil, err
        }

        resp, err := c.httpClient.Do(req)
        if err != nil {
            return nil, err
        }
        defer resp.Body.Close()

        if resp.StatusCode >= 500 {
            return nil, fmt.Errorf("user-service error: %d", resp.StatusCode)
        }

        var profile Profile
        if err := json.NewDecoder(resp.Body).Decode(&profile); err != nil {
            return nil, err
        }
        return &profile, nil
    })

    if err != nil {
        // Circuit breaker OPEN: fallback sang cache
        if errors.Is(err, gobreaker.ErrOpenState) {
            if cached, ok := c.cache.Get(userID); ok {
                log.Printf("circuit breaker open, using cached profile for user %s", userID)
                return cached, nil
            }
            return nil, fmt.Errorf("user-service unavailable and no cache available: %w", err)
        }
        return nil, err
    }

    // Update cache khi thành công
    c.cache.Set(userID, result)
    return result, nil
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Mỗi external dependency có circuit breaker riêng biệt
- [ ] Threshold phù hợp: 5+ requests, 50-60% failure rate
- [ ] Có fallback khi circuit OPEN (cache, default value, graceful degradation)
- [ ] Export circuit breaker state làm Prometheus metric
- [ ] Alert khi circuit OPEN kéo dài > 1 phút
- [ ] Test circuit breaker bằng chaos engineering (kill downstream)
- [ ] Dùng library: `github.com/sony/gobreaker/v2` hoặc `github.com/eapache/go-resiliency`

**Go vet / staticcheck rules:**
```bash
# Vet cơ bản
go vet ./...

# Staticcheck
staticcheck ./...

# Kiểm tra error wrapping đúng cách
golangci-lint run --enable errorlint,wrapcheck ./...

# Chaos testing với toxiproxy
go test -v -run TestCircuitBreaker ./...
```

---

## Pattern 04: Distributed Lock Sai {#pattern-04}

### 1. Tên
**Distributed Lock Sai** (Incorrect Distributed Lock)

### 2. Phân loại
Domain: Distributed Systems / Subcategory: Concurrency, Redis, Correctness

### 3. Mức nghiêm trọng
> CRITICAL - Lock phân tán sai có thể dẫn đến race condition giữa nhiều instance, gây mất dữ liệu, double processing, hoặc data corruption trong môi trường distributed.

### 4. Vấn đề

Distributed lock sai thường xảy ra do: lock không có TTL (process crash không release lock), release lock của process khác, hoặc không dùng atomic SET NX EX.

```
Lỗi phổ biến 1: Lock không có TTL
  Process A giữ lock --> Process A bị crash
  Lock KHÔNG BAO GIỜ được release
  --> Toàn bộ hệ thống bị deadlock trên resource đó

Lỗi phổ biến 2: Release nhầm lock
  t=0: Process A acquire lock (value="A", TTL=10s)
  t=5: Process A bị slow (GC pause 8s)
  t=10: Lock EXPIRED (TTL hết)
  t=11: Process B acquire lock (value="B")
  t=13: Process A resume, gọi DEL lock
        --> XÓA LOCK CỦA PROCESS B! Race condition!
  t=13: Process C acquire lock (value="C")
  t=13: Process B VÀ C đều giữ lock cùng lúc!

Giải pháp đúng với unique value:
  Process A: SET lock "uuid-A" EX 10 NX
  Process B: SET lock "uuid-B" EX 10 NX  --> FAIL (lock tồn tại)
  Process A release: kiểm tra value == "uuid-A" rồi mới DEL
                     (atomic bằng Lua script)
```

Nguyên nhân phổ biến:
- Dùng `SET key value` + `EXPIRE key ttl` (2 commands không atomic)
- Dùng `DEL key` không kiểm tra value
- TTL quá ngắn so với operation time
- Không dùng Lua script cho atomic check-and-delete

### 5. Phát hiện trong mã nguồn

**Dấu hiệu trong code:**
- `redis.Set(key, value)` rồi `redis.Expire(key, ttl)` riêng lẻ
- `redis.Del(lockKey)` không verify owner
- Lock value là constant string thay vì unique UUID
- Không có Lua script hoặc `redis.Eval` cho release

**Regex patterns (dùng với ripgrep):**

```bash
# Tìm SET và EXPIRE không atomic (2 lệnh riêng lẻ)
rg "\.Set\(.*\)\s*\n.*\.Expire\(" --type go -n --multiline

# Tìm DEL lock không check value
rg "\.Del\(.*lock\|\.Del\(.*Lock\|\.Del\(.*mutex" --type go -n

# Tìm lock value không có UUID
rg "lock.*:=.*\".*\"\|lockVal.*=.*\"" --type go -n

# Tìm distributed lock không dùng Lua
rg -l "redis.*lock\|Lock.*redis" --type go | xargs rg -L "Eval\|Script\|lua"

# Tìm SetNX không có TTL
rg "SetNX\|SETNX" --type go -n -A 3
```

### 6. Giải pháp

| Phương pháp | Trước (BAD) | Sau (GOOD) |
|-------------|-------------|------------|
| Atomic acquire | SET + EXPIRE (2 cmds) | SET NX EX (1 cmd) |
| Lock value | Constant string | UUID per process |
| Release | DEL key trực tiếp | Lua: check value rồi DEL |
| TTL | Không có hoặc quá ngắn | Đủ dài + watchdog |
| Library | Tự implement | `go-redis/redis` + Redlock |

**Code BAD - Distributed lock sai:**
```go
// BAD: SET và EXPIRE không atomic, DEL không verify owner
func acquireLockBad(rdb *redis.Client, lockKey string) bool {
    // NGUY HIỂM: 2 lệnh không atomic, crash giữa chừng -> no TTL
    err := rdb.Set(context.Background(), lockKey, "locked", 0).Err()
    if err != nil {
        return false
    }
    rdb.Expire(context.Background(), lockKey, 10*time.Second) // Có thể fail!
    return true
}

func releaseLockBad(rdb *redis.Client, lockKey string) {
    // NGUY HIỂM: Xóa lock của người khác nếu TTL đã hết và người khác đã acquire
    rdb.Del(context.Background(), lockKey)
}
```

**Code GOOD - Distributed lock đúng:**
```go
// GOOD: Distributed lock đúng với atomic operations
import (
    "github.com/google/uuid"
    "github.com/redis/go-redis/v9"
)

type DistributedLock struct {
    rdb     *redis.Client
    key     string
    value   string        // UUID unique per lock acquisition
    ttl     time.Duration
}

// Lua script để atomic check-and-delete
// Chỉ DEL nếu value khớp với owner
var releaseLockScript = redis.NewScript(`
    if redis.call("GET", KEYS[1]) == ARGV[1] then
        return redis.call("DEL", KEYS[1])
    else
        return 0
    end
`)

func AcquireLock(ctx context.Context, rdb *redis.Client, key string, ttl time.Duration) (*DistributedLock, error) {
    lockValue := uuid.New().String() // Unique per acquisition

    // SET key value EX seconds NX - atomic, chỉ set nếu key không tồn tại
    ok, err := rdb.SetNX(ctx, key, lockValue, ttl).Result()
    if err != nil {
        return nil, fmt.Errorf("redis SetNX error: %w", err)
    }
    if !ok {
        return nil, fmt.Errorf("lock %q already held", key)
    }

    return &DistributedLock{
        rdb:   rdb,
        key:   key,
        value: lockValue,
        ttl:   ttl,
    }, nil
}

func (l *DistributedLock) Release(ctx context.Context) error {
    // Lua script: atomic check value rồi DEL
    result, err := releaseLockScript.Run(ctx, l.rdb, []string{l.key}, l.value).Int()
    if err != nil {
        return fmt.Errorf("release lock script error: %w", err)
    }
    if result == 0 {
        // Lock đã bị expire hoặc bị người khác lấy - log nhưng không fail
        return fmt.Errorf("lock %q was not released: value mismatch or already expired", l.key)
    }
    return nil
}

// Watchdog: gia hạn TTL nếu operation còn đang chạy
func (l *DistributedLock) StartWatchdog(ctx context.Context) context.CancelFunc {
    watchCtx, cancel := context.WithCancel(ctx)
    go func() {
        ticker := time.NewTicker(l.ttl / 3) // Gia hạn sau mỗi 1/3 TTL
        defer ticker.Stop()
        for {
            select {
            case <-watchCtx.Done():
                return
            case <-ticker.C:
                // Chỉ gia hạn nếu vẫn là owner
                result, err := l.rdb.GetSet(ctx, l.key, l.value).Result()
                if err != nil || result != l.value {
                    return // Không còn là owner
                }
                l.rdb.Expire(ctx, l.key, l.ttl)
            }
        }
    }()
    return cancel
}

// Sử dụng
func processWithLock(ctx context.Context, rdb *redis.Client, resourceID string) error {
    lock, err := AcquireLock(ctx, rdb, "lock:"+resourceID, 30*time.Second)
    if err != nil {
        return fmt.Errorf("could not acquire lock: %w", err)
    }

    stopWatchdog := lock.StartWatchdog(ctx)
    defer func() {
        stopWatchdog()
        if releaseErr := lock.Release(context.Background()); releaseErr != nil {
            log.Printf("WARN: lock release failed: %v", releaseErr)
        }
    }()

    // Critical section
    return doWork(ctx, resourceID)
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Luôn dùng `SET NX EX` (1 atomic command) để acquire lock
- [ ] Lock value phải là UUID unique mỗi lần acquire
- [ ] Release lock bằng Lua script (atomic check-and-delete)
- [ ] TTL phải đủ dài hơn max operation time + buffer
- [ ] Implement watchdog nếu operation time không xác định
- [ ] Monitor lock acquisition failure rate
- [ ] Xem xét dùng Redlock algorithm cho multi-node Redis
- [ ] Dùng library: `github.com/go-redsync/redsync`

**Go vet / staticcheck rules:**
```bash
# Vet cơ bản
go vet ./...

# Staticcheck
staticcheck ./...

# Race detector - quan trọng cho concurrent code
go test -race ./...

# Kiểm tra redis usage patterns
golangci-lint run --enable contextcheck ./...
```

---

## Pattern 05: Idempotency Thiếu {#pattern-05}

### 1. Tên
**Idempotency Thiếu** (Missing Idempotency)

### 2. Phân loại
Domain: Distributed Systems / Subcategory: API Design, Data Consistency, Retry Safety

### 3. Mức nghiêm trọng
> HIGH - Thiếu idempotency cộng với retry logic dẫn đến xử lý trùng lặp: thanh toán bị charge 2 lần, đơn hàng tạo 2 lần, email gửi 2 lần. Rất khó debug và gây mất tiền thực sự.

### 4. Vấn đề

Retry là cần thiết để đảm bảo reliability, nhưng retry mà không có idempotency dẫn đến duplicate operations. Network glitch có thể khiến request được nhận nhưng response bị mất, client retry và operation thực hiện 2 lần.

```
Vấn đề: Request nhận được nhưng response bị mất

  Client --> [POST /payments] --> Server xử lý thành công
         <-- [Network error] <-- Response bị drop
  Client retry --> [POST /payments] --> Server xử lý LẦN 2!
                                        User bị charge 2 lần!

Idempotency Key giải quyết:

  Client --> [POST /payments, Idempotency-Key: uuid-abc] --> Server
                                                              |
                                                       Check key uuid-abc
                                                       Key chưa tồn tại
                                                       --> Xử lý, lưu key + result
         <-- [Network error] <--

  Client retry --> [POST /payments, Idempotency-Key: uuid-abc] --> Server
                                                                    |
                                                             Check key uuid-abc
                                                             Key ĐÃ TỒN TẠI
                                                             --> Trả về result cũ
                                                             Không xử lý lại!
```

Nguyên nhân phổ biến:
- API POST/PUT không kiểm tra idempotency key
- Message queue consumer không dedup message ID
- Scheduler job không check đã chạy chưa
- Database insert không dùng unique constraint

### 5. Phát hiện trong mã nguồn

**Dấu hiệu trong code:**
- POST handler không check `Idempotency-Key` header
- Message handler không lưu `message_id` đã xử lý
- `INSERT INTO` không có `ON CONFLICT DO NOTHING` hoặc `IGNORE`
- Scheduled job không lock hoặc check last run time

**Regex patterns (dùng với ripgrep):**

```bash
# Tìm POST handler không check idempotency key
rg -A 20 "func.*Post\|r\.Post\|router\.Post" --type go | rg -L "Idempotency\|idempotent\|idempotency"

# Tìm payment/order/email handler thiếu idempotency
rg -l "payment\|order\|email\|charge" --type go | xargs rg -L "idempotency\|idempotent\|dedup"

# Tìm message handler không lưu message ID
rg -A 10 "func.*HandleMessage\|func.*Consume\|func.*Process" --type go | rg -L "MessageId\|message_id\|msgID"

# Tìm INSERT không có conflict handling
rg "INSERT INTO" --type go -n | rg -v "ON CONFLICT\|IGNORE\|idempotent"
```

### 6. Giải pháp

| Phương pháp | Trước (BAD) | Sau (GOOD) |
|-------------|-------------|------------|
| API layer | Không check key | Check `Idempotency-Key` header |
| Storage | Không lưu key | Store key + result trong Redis/DB |
| Message queue | Không dedup | Check và store message ID |
| DB level | Plain INSERT | INSERT với unique constraint |
| TTL | Không có | Key TTL 24h-7 ngày |

**Code BAD - Không có idempotency:**
```go
// BAD: Mỗi lần gọi đều tạo payment mới
func (h *PaymentHandler) CreatePayment(w http.ResponseWriter, r *http.Request) {
    var req CreatePaymentRequest
    json.NewDecoder(r.Body).Decode(&req)

    // Không check idempotency - retry sẽ charge 2 lần!
    payment, err := h.paymentService.Charge(r.Context(), req.Amount, req.UserID)
    if err != nil {
        http.Error(w, err.Error(), 500)
        return
    }
    json.NewEncoder(w).Encode(payment)
}
```

**Code GOOD - Idempotency với Redis:**
```go
// GOOD: Idempotency key middleware
type IdempotencyStore struct {
    rdb *redis.Client
    ttl time.Duration
}

type idempotencyResult struct {
    StatusCode int    `json:"status_code"`
    Body       []byte `json:"body"`
}

func (s *IdempotencyStore) GetOrExecute(
    ctx context.Context,
    key string,
    execute func() (int, []byte, error),
) (int, []byte, error) {
    redisKey := "idempotency:" + key

    // Thử lấy kết quả đã cache
    cached, err := s.rdb.Get(ctx, redisKey).Bytes()
    if err == nil {
        var result idempotencyResult
        if err := json.Unmarshal(cached, &result); err == nil {
            return result.StatusCode, result.Body, nil // Trả về kết quả cũ
        }
    }

    // Chưa có: execute và lưu kết quả
    // Dùng lock để tránh concurrent execute với cùng key
    lockKey := "idempotency-lock:" + key
    lock, err := AcquireLock(ctx, s.rdb, lockKey, 30*time.Second)
    if err != nil {
        // Có concurrent request với cùng key - chờ và thử lại
        time.Sleep(100 * time.Millisecond)
        return s.GetOrExecute(ctx, key, execute)
    }
    defer lock.Release(ctx)

    // Double-check sau khi có lock
    cached, err = s.rdb.Get(ctx, redisKey).Bytes()
    if err == nil {
        var result idempotencyResult
        if err := json.Unmarshal(cached, &result); err == nil {
            return result.StatusCode, result.Body, nil
        }
    }

    // Execute thực sự
    statusCode, body, execErr := execute()
    if execErr != nil {
        return 0, nil, execErr
    }

    // Lưu kết quả với TTL
    resultData, _ := json.Marshal(idempotencyResult{
        StatusCode: statusCode,
        Body:       body,
    })
    s.rdb.Set(ctx, redisKey, resultData, s.ttl)

    return statusCode, body, nil
}

// GOOD: Payment handler với idempotency
func (h *PaymentHandler) CreatePayment(w http.ResponseWriter, r *http.Request) {
    idempotencyKey := r.Header.Get("Idempotency-Key")
    if idempotencyKey == "" {
        http.Error(w, "Idempotency-Key header required", http.StatusBadRequest)
        return
    }

    var req CreatePaymentRequest
    if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
        http.Error(w, "invalid request body", http.StatusBadRequest)
        return
    }

    statusCode, body, err := h.idempotency.GetOrExecute(
        r.Context(),
        idempotencyKey,
        func() (int, []byte, error) {
            payment, err := h.paymentService.Charge(r.Context(), req.Amount, req.UserID)
            if err != nil {
                return http.StatusInternalServerError, nil, err
            }
            body, err := json.Marshal(payment)
            if err != nil {
                return http.StatusInternalServerError, nil, err
            }
            return http.StatusCreated, body, nil
        },
    )
    if err != nil {
        http.Error(w, err.Error(), http.StatusInternalServerError)
        return
    }

    w.Header().Set("Content-Type", "application/json")
    w.WriteHeader(statusCode)
    w.Write(body)
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Mọi POST/PUT endpoint tạo/modify resource phải có idempotency key
- [ ] Message queue consumer phải track message ID đã xử lý
- [ ] Database có unique constraint trên business key
- [ ] Idempotency key TTL phù hợp với retry window (24h-7 ngày)
- [ ] Document rõ API nào yêu cầu idempotency key
- [ ] Test: gọi 2 lần với cùng key phải ra cùng kết quả
- [ ] Monitor: alert khi detect duplicate trong window

**Go vet / staticcheck rules:**
```bash
# Vet cơ bản
go vet ./...

# Kiểm tra error handling
errcheck ./...

# Integration test với duplicate call
go test -v -run TestIdempotency ./...

# Staticcheck
staticcheck ./...
```

---

## Pattern 06: Service Discovery Cache {#pattern-06}

### 1. Tên
**Service Discovery Cache** (Cache Service Discovery Không Làm Mới)

### 2. Phân loại
Domain: Distributed Systems / Subcategory: Service Discovery, DNS, Load Balancing

### 3. Mức nghiêm trọng
> MEDIUM - DNS cache stale khiến traffic vẫn gửi đến instance đã down hoặc được thay thế. Biểu hiện bằng lỗi connection refused lẻ tẻ, khó reproduce, thường bị nhầm với network flakiness.

### 4. Vấn đề

Go's DNS resolver và HTTP client cache DNS theo TTL, nhưng nhiều khi TTL bị ignore hoặc cache quá lâu. Khi scale down hoặc redeploy, HTTP client vẫn gửi request đến IP cũ đã không còn tồn tại.

```
Vấn đề DNS Cache stale:

  t=0:  Service B có IP 10.0.0.5
        HTTP client cache DNS: service-b.internal -> 10.0.0.5

  t=30m: Service B redeploy, IP mới: 10.0.0.8
         DNS TTL = 30s, nhưng Go HTTP transport cache lâu hơn

  t=31m: HTTP client vẫn dùng 10.0.0.5 (IP cũ!)
         --> connection refused / timeout

  t=?:   HTTP client refresh DNS (không xác định khi nào)
         --> Bắt đầu dùng 10.0.0.8

Kubernetes: Pod restart thay đổi IP
  ClusterIP ổn định nhưng nếu dùng Pod IP trực tiếp --> lỗi
  Endpoint update qua kube-proxy có độ trễ
```

Nguyên nhân phổ biến:
- `http.DefaultTransport` giữ connection pool với DNS cache mặc định
- Dùng Pod IP trực tiếp thay vì Service DNS
- DNS TTL quá cao cho môi trường dynamic
- Không config `DialContext` với DNS resolver ngắn hạn

### 5. Phát hiện trong mã nguồn

**Dấu hiệu trong code:**
- Dùng `http.DefaultClient` không config transport
- Hardcode IP address thay vì hostname
- `Transport.MaxIdleConnsPerHost` cao mà không có connection refresh
- Không có `DialContext` custom với DNS refresh

**Regex patterns (dùng với ripgrep):**

```bash
# Tìm hardcode IP address
rg "\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b" --type go -n | rg -v "//|127\.0\.0\.1|0\.0\.0\.0"

# Tìm http.DefaultClient (dùng default transport)
rg "http\.DefaultClient\b" --type go -n

# Tìm HTTP client không config DialContext
rg "http\.Client\{" --type go -n -A 10 | rg -L "DialContext\|DialTLS"

# Tìm transport không có DNS refresh
rg "&http\.Transport\{" --type go -n -A 15 | rg -L "DialContext"
```

### 6. Giải pháp

| Phương pháp | Trước (BAD) | Sau (GOOD) |
|-------------|-------------|------------|
| DNS cache | Default (lâu) | Short TTL resolver |
| Address | Hardcode IP | Service DNS hostname |
| Transport | Default | Custom với DialContext |
| Connection | Giữ lâu | MaxIdleConnsPerHost thấp |
| Refresh | Không có | DialContext re-resolve |

**Code BAD - DNS cache không refresh:**
```go
// BAD: http.DefaultClient cache DNS theo default behavior
var client = http.DefaultClient // Dùng default transport, DNS cache lâu

func callService(url string) (*http.Response, error) {
    return client.Get(url) // DNS không bao giờ được refresh
}

// BAD: Hardcode IP
const serviceURL = "http://10.0.0.5:8080/api" // IP sẽ thay đổi khi redeploy!
```

**Code GOOD - DNS resolver với TTL ngắn:**
```go
// GOOD: Custom transport với DialContext re-resolve DNS mỗi request
func NewHTTPClientWithDNSRefresh(timeout time.Duration) *http.Client {
    dialer := &net.Dialer{
        Timeout:   5 * time.Second,
        KeepAlive: 30 * time.Second,
        Resolver: &net.Resolver{
            PreferGo: true,
            Dial: func(ctx context.Context, network, address string) (net.Conn, error) {
                d := net.Dialer{
                    Timeout: 3 * time.Second,
                }
                return d.DialContext(ctx, "udp", "8.8.8.8:53") // Custom DNS server
            },
        },
    }

    transport := &http.Transport{
        // Re-resolve DNS mỗi khi tạo connection mới
        DialContext: func(ctx context.Context, network, addr string) (net.Conn, error) {
            // Tách host:port, resolve host
            host, port, err := net.SplitHostPort(addr)
            if err != nil {
                return dialer.DialContext(ctx, network, addr)
            }
            // Resolve DNS mỗi lần (bypass cache)
            addrs, err := net.DefaultResolver.LookupHost(ctx, host)
            if err != nil {
                return nil, err
            }
            if len(addrs) == 0 {
                return nil, fmt.Errorf("no addresses for host %s", host)
            }
            // Round-robin đơn giản
            addr = net.JoinHostPort(addrs[0], port)
            return dialer.DialContext(ctx, network, addr)
        },
        MaxIdleConns:        100,
        MaxIdleConnsPerHost: 10,
        IdleConnTimeout:     90 * time.Second,
        DisableKeepAlives:   false,
        // Không giữ connection pool quá lâu với service có IP thay đổi
        ResponseHeaderTimeout: timeout,
    }

    return &http.Client{
        Transport: transport,
        Timeout:   timeout,
    }
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Không hardcode IP address - luôn dùng DNS hostname
- [ ] Dùng Kubernetes Service DNS thay vì Pod IP
- [ ] Config DNS TTL thấp trong service discovery (30s-60s)
- [ ] Dùng custom DialContext để control DNS resolution
- [ ] Test DNS failover bằng cách restart downstream service
- [ ] Monitor connection error rate theo upstream hostname

**Go vet / staticcheck rules:**
```bash
# Vet cơ bản
go vet ./...

# Tìm hardcode IP
rg "\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b" --type go -n

# Staticcheck
staticcheck ./...
```

---

## Pattern 07: Shard Rebalancing {#pattern-07}

### 1. Tên
**Shard Rebalancing** (Mất Dữ Liệu Khi Rebalance Shard)

### 2. Phân loại
Domain: Distributed Systems / Subcategory: Sharding, Data Distribution, Consistency

### 3. Mức nghiêm trọng
> HIGH - Rebalancing shard không đúng cách gây mất request, đọc dữ liệu sai shard, hoặc inconsistency trong thời gian migration. User nhận được không tìm thấy dữ liệu hoặc dữ liệu cũ.

### 4. Vấn đề

Khi cluster thêm/bớt node, consistent hashing phải rebalance shard. Nếu client cache shard map cũ, request sẽ gửi đến sai node.

```
Simple modulo sharding - vấn đề khi scale:

  3 nodes: hash(key) % 3
  key="user123" --> hash=456 --> 456%3=0 --> Node 0

  Thêm node 4: hash(key) % 4
  key="user123" --> hash=456 --> 456%4=0 --> Node 0 (may mắn)
  key="user456" --> hash=789 --> 789%3=0 --> Node 0 (cũ)
                            --> 789%4=1 --> Node 1 (mới)
                            KHÁC NHAU! Đọc sai node!

Consistent Hashing - rebalance tối thiểu:

  Ring:  0 ... 100 ... 200 ... 300 ... 360
         Node0       Node1        Node2

  Thêm Node3 vào vị trí 150:
  Ring:  0 ... 100 ... 150 ... 200 ... 300 ... 360
         Node0        Node3  Node1        Node2

  Chỉ các key trong range [100, 150] phải migrate Node1 -> Node3
  Các key khác không thay đổi!
```

Nguyên nhân phổ biến:
- Dùng modulo sharding thay vì consistent hashing
- Client cache shard map không refresh khi topology thay đổi
- Không có migration strategy khi rebalance
- Write và Read dùng shard map khác nhau trong thời gian migration

### 5. Phát hiện trong mã nguồn

**Dấu hiệu trong code:**
- `hash % len(nodes)` - modulo sharding
- Shard map là variable không refresh
- Không có version check trên shard map
- Không handle `MOVED` hoặc redirect response từ cluster

**Regex patterns (dùng với ripgrep):**

```bash
# Tìm modulo sharding
rg "hash.*%.*len\|%.*nodes\|%.*shards\|%.*replicas" --type go -n

# Tìm shard map hardcode hoặc không refresh
rg "shardMap\|shards\s*=\s*\[\]" --type go -n

# Tìm consistent hash library usage
rg "consistent.*hash\|hashring\|rendezvous" --type go -n

# Kiểm tra có handle MOVED error không (Redis cluster)
rg -l "redis" --type go | xargs rg -L "MOVED\|ASK\|ClusterClient"
```

### 6. Giải pháp

| Phương pháp | Trước (BAD) | Sau (GOOD) |
|-------------|-------------|------------|
| Algorithm | Modulo `% N` | Consistent hashing |
| Shard map | Static | Dynamic với refresh |
| Migration | Không có | Double-write + gradual cutover |
| Error handling | Không có | Handle MOVED/redirect |
| Monitoring | Không có | Shard distribution metrics |

**Code BAD - Modulo sharding:**
```go
// BAD: Modulo sharding - vỡ khi thêm/bớt node
type ShardRouter struct {
    nodes []string
}

func (r *ShardRouter) GetNode(key string) string {
    h := fnv32(key)
    // NGUY HIỂM: Thêm node vào sẽ làm phần lớn key đi sai node
    return r.nodes[h%uint32(len(r.nodes))]
}
```

**Code GOOD - Consistent hashing:**
```go
// GOOD: Consistent hashing với virtual nodes
import "github.com/buraksezer/consistent"

type ConsistentShardRouter struct {
    mu   sync.RWMutex
    ring *consistent.Consistent
    cfg  consistent.Config
}

func NewConsistentShardRouter(nodes []string) *ConsistentShardRouter {
    cfg := consistent.Config{
        PartitionCount:    271,  // Số virtual partition (số nguyên tố tốt hơn)
        ReplicationFactor: 20,   // Virtual nodes per physical node
        Load:              1.25, // Load balancing factor
        Hasher:            hasher{},
    }

    r := consistent.New(nil, cfg)
    for _, node := range nodes {
        r.Add(consistent.NewMember(node))
    }

    return &ConsistentShardRouter{ring: r, cfg: cfg}
}

func (r *ConsistentShardRouter) GetNode(key string) string {
    r.mu.RLock()
    defer r.mu.RUnlock()
    member, err := r.ring.LocateKey([]byte(key))
    if err != nil {
        return ""
    }
    return member.String()
}

func (r *ConsistentShardRouter) AddNode(node string) {
    r.mu.Lock()
    defer r.mu.Unlock()
    r.ring.Add(consistent.NewMember(node))
    log.Printf("shard: added node %s, rebalancing...", node)
}

func (r *ConsistentShardRouter) RemoveNode(node string) {
    r.mu.Lock()
    defer r.mu.Unlock()
    r.ring.Remove(node)
    log.Printf("shard: removed node %s, rebalancing...", node)
}

// hasher implement consistent.Hasher interface
type hasher struct{}

func (h hasher) Sum64(data []byte) uint64 {
    f := fnv.New64()
    f.Write(data)
    return f.Sum64()
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Dùng consistent hashing thay vì modulo sharding
- [ ] Implement virtual nodes để phân phối đều hơn
- [ ] Shard map refresh tự động khi topology thay đổi
- [ ] Migration strategy: double-write, rồi gradual cutover
- [ ] Monitor shard distribution: alert khi imbalance > 20%
- [ ] Test rebalancing: thêm/bớt node và verify data còn đúng

**Go vet / staticcheck rules:**
```bash
# Vet cơ bản
go vet ./...

# Kiểm tra race condition trong shard router
go test -race ./...

# Staticcheck
staticcheck ./...
```

---

## Pattern 08: Message Queue Backpressure {#pattern-08}

### 1. Tên
**Message Queue Backpressure** (Thiếu Cơ Chế Giảm Tải Message Queue)

### 2. Phân loại
Domain: Distributed Systems / Subcategory: Message Queue, Flow Control, System Stability

### 3. Mức nghiêm trọng
> HIGH - Consumer xử lý chậm hơn producer gửi dẫn đến queue tràn, OOM, hoặc message bị drop. Trong worst case toàn bộ pipeline đình trệ và phải replay hàng triệu message.

### 4. Vấn đề

Không có backpressure, producer tiếp tục đẩy message khi consumer đang chậm. Queue in-memory tràn, disk queue đầy, hoặc consumer buffer cạn kiệt memory.

```
Không có Backpressure:

  Producer: 10,000 msg/s -----> Queue <----- Consumer: 100 msg/s
                                  |
                            Queue growth: +9,900 msg/s
                            t=1s:   9,900 msg
                            t=60s:  594,000 msg
                            t=10m:  5,940,000 msg
                            t=?:    OOM / Queue full / Message drop

Với Backpressure:

  Producer: 10,000 msg/s --> [THROTTLE] --> Queue <----- Consumer: 100 msg/s
                                  ^
                                  |
                            Queue depth > threshold
                            --> Signal producer to slow down
                            Producer: 100 msg/s (match consumer)
```

Nguyên nhân phổ biến:
- Consumer không report capacity về producer
- Goroutine per message không giới hạn (spawn không kiểm soát)
- Channel buffer không đủ, block producer
- Không monitor queue depth

### 5. Phát hiện trong mã nguồn

**Dấu hiệu trong code:**
- `for msg := range messages { go process(msg) }` - goroutine không giới hạn
- Channel buffer rất lớn hoặc unbounded
- Không có semaphore hoặc worker pool
- Consumer không có backpressure signal về upstream

**Regex patterns (dùng với ripgrep):**

```bash
# Tìm goroutine không giới hạn trong consumer loop
rg "for.*range.*\{" --type go -n -A 3 | rg "go func\|go process\|go handle"

# Tìm channel buffer rất lớn
rg "make\(chan.*[0-9]{4,}\)" --type go -n

# Tìm consumer không có worker pool
rg -l "kafka\|rabbitmq\|nats\|pubsub" --type go | xargs rg -L "semaphore\|WorkerPool\|workers"

# Tìm thiếu queue depth monitoring
rg -l "consumer\|Consumer\|Subscribe" --type go | xargs rg -L "Len\(\)\|depth\|backpressure"
```

### 6. Giải pháp

| Phương pháp | Trước (BAD) | Sau (GOOD) |
|-------------|-------------|------------|
| Concurrency | Goroutine per msg | Worker pool với semaphore |
| Buffer | Unbounded | Bounded channel |
| Throttle | Không có | Rate limiter + queue depth check |
| Signal | Không có | Backpressure về producer |
| Monitor | Không có | Queue depth metrics |

**Code BAD - Goroutine không giới hạn:**
```go
// BAD: Mỗi message tạo 1 goroutine mới - OOM khi queue nhiều
func consumeBad(messages <-chan Message) {
    for msg := range messages {
        go func(m Message) { // Goroutine không giới hạn!
            process(m)        // Nếu slow, goroutine tích lũy
        }(msg)
    }
}
```

**Code GOOD - Worker pool với backpressure:**
```go
// GOOD: Worker pool với semaphore và backpressure
type ConsumerPool struct {
    workers   int
    semaphore chan struct{}
    metrics   *ConsumerMetrics
}

func NewConsumerPool(workers int, metrics *ConsumerMetrics) *ConsumerPool {
    return &ConsumerPool{
        workers:   workers,
        semaphore: make(chan struct{}, workers), // Bounded concurrency
        metrics:   metrics,
    }
}

func (p *ConsumerPool) ConsumeWithBackpressure(
    ctx context.Context,
    messages <-chan Message,
    process func(context.Context, Message) error,
) error {
    var wg sync.WaitGroup

    for {
        select {
        case <-ctx.Done():
            wg.Wait()
            return ctx.Err()

        case msg, ok := <-messages:
            if !ok {
                wg.Wait()
                return nil
            }

            // Backpressure: block nếu đủ workers đang chạy
            select {
            case p.semaphore <- struct{}{}: // Acquire slot
            case <-ctx.Done():
                wg.Wait()
                return ctx.Err()
            }

            p.metrics.InFlight.Inc()
            wg.Add(1)
            go func(m Message) {
                defer func() {
                    <-p.semaphore // Release slot
                    p.metrics.InFlight.Dec()
                    wg.Done()
                }()

                if err := process(ctx, m); err != nil {
                    p.metrics.Errors.Inc()
                    log.Printf("message processing error: %v", err)
                }
                p.metrics.Processed.Inc()
            }(msg)
        }
    }
}

// GOOD: Rate limiter để control throughput
func consumeWithRateLimit(
    ctx context.Context,
    messages <-chan Message,
    maxRPS int,
) {
    limiter := rate.NewLimiter(rate.Limit(maxRPS), maxRPS/10)
    pool := NewConsumerPool(runtime.NumCPU()*2, newMetrics())

    pool.ConsumeWithBackpressure(ctx, messages, func(ctx context.Context, msg Message) error {
        // Đợi rate limiter trước khi xử lý
        if err := limiter.Wait(ctx); err != nil {
            return err
        }
        return processMessage(ctx, msg)
    })
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Dùng worker pool với size giới hạn thay vì goroutine per message
- [ ] Monitor queue depth và alert khi > 80% capacity
- [ ] Implement backpressure: block producer hoặc drop với signal
- [ ] Rate limiter trên consumer để không overwhelm downstream
- [ ] Dead letter queue cho message xử lý thất bại
- [ ] Test với load spike: producer nhanh hơn consumer 10x

**Go vet / staticcheck rules:**
```bash
# Vet cơ bản
go vet ./...

# Race detector
go test -race ./...

# Kiểm tra goroutine leak
go test -v -run TestConsumer ./... # Với goleak
staticcheck ./...
```

---

## Pattern 09: Split Brain {#pattern-09}

### 1. Tên
**Split Brain** (Phân Mảnh Cluster)

### 2. Phân loại
Domain: Distributed Systems / Subcategory: Consensus, High Availability, Data Consistency

### 3. Mức nghiêm trọng
> CRITICAL - Split brain xảy ra khi cluster bị chia thành 2 partition độc lập, cả 2 tin rằng mình là primary. Dẫn đến 2 node ghi dữ liệu khác nhau vào cùng resource, gây data corruption không thể tự recover.

### 4. Vấn đề

Network partition chia cluster làm 2 phần. Nếu cả 2 phần đều đủ điều kiện để bầu leader, cả 2 sẽ tiến hành ghi dữ liệu độc lập. Khi network phục hồi, dữ liệu bị conflict.

```
Split Brain scenario:

  Bình thường: Node1(Leader) <-> Node2 <-> Node3
  Network partition:
  [Node1] ||||| [Node2 <-> Node3]

  Node1: "Tôi là leader, tiếp tục ghi!"
         Write: user.balance = 1000
  Node2+3: "Node1 mất! Bầu Node2 làm leader!"
            Write: user.balance = 2000

  Khi network phục hồi:
  Node1: balance=1000
  Node2: balance=2000
  --> Data CONFLICT! Không biết cái nào đúng!

Giải pháp - Quorum/Majority:
  3 nodes: cần >= 2 votes để làm bất kỳ thao tác nào
  Partition [Node1] | [Node2, Node3]
  Node1: chỉ có 1 vote < 2 --> TỪ CHỐI GHI, step down
  Node2+3: có 2 votes >= 2 --> OK, bầu leader và ghi

  Không có split brain vì chỉ 1 partition có đa số!
```

Nguyên nhân phổ biến:
- Leader election không yêu cầu quorum
- Không có fencing token để prevent stale leader từ ghi
- Health check interval quá ngắn gây false positive
- Network timeout nhầm lẫn với node failure

### 5. Phát hiện trong mã nguồn

**Dấu hiệu trong code:**
- Leader election không kiểm tra quorum size
- Không có fencing token/epoch trong write path
- Leader tự quyết định không cần xác nhận từ follower
- Không implement STONITH (Shoot The Other Node In The Head)

**Regex patterns (dùng với ripgrep):**

```bash
# Tìm leader election không có quorum check
rg -A 10 "electLeader\|becomeLeader\|isLeader" --type go | rg -L "quorum\|majority\|votes"

# Tìm write không có epoch/term check
rg "func.*Write\|func.*Commit" --type go -n -A 10 | rg -L "epoch\|term\|fencing"

# Tìm consensus implementation
rg "raft\|etcd\|consensus\|leader" --type go -n

# Tìm distributed state không dùng consensus library
rg -l "leader\|primary\|master" --type go | xargs rg -L "etcd\|raft\|zookeeper\|consul"
```

### 6. Giải pháp

| Phương pháp | Trước (BAD) | Sau (GOOD) |
|-------------|-------------|------------|
| Election | Không cần quorum | Majority quorum required |
| Fencing | Không có | Epoch/term trong mọi write |
| Lease | Không có | Time-bound leader lease |
| Library | Tự implement | etcd, Raft (hashicorp/raft) |
| Monitoring | Không có | Leader change events + alerts |

**Code BAD - Leader election không an toàn:**
```go
// BAD: Leader election không có quorum
type Node struct {
    isLeader bool
}

func (n *Node) onLeaderTimeout() {
    // NGUY HIỂM: Tự phong mình làm leader không cần quorum
    n.isLeader = true
    n.startLeaderTasks()
}
```

**Code GOOD - Dùng etcd distributed lock làm leader election:**
```go
// GOOD: Leader election qua etcd (đảm bảo quorum)
import (
    clientv3 "go.etcd.io/etcd/client/v3"
    "go.etcd.io/etcd/client/v3/concurrency"
)

type LeaderElector struct {
    client    *clientv3.Client
    election  *concurrency.Election
    leaderKey string
    nodeID    string

    onLeader   func(ctx context.Context)
    onFollower func()
}

func NewLeaderElector(
    endpoints []string,
    leaderKey string,
    nodeID string,
) (*LeaderElector, error) {
    client, err := clientv3.New(clientv3.Config{
        Endpoints:   endpoints,
        DialTimeout: 5 * time.Second,
    })
    if err != nil {
        return nil, err
    }

    sess, err := concurrency.NewSession(client, concurrency.WithTTL(15))
    if err != nil {
        return nil, err
    }

    return &LeaderElector{
        client:    client,
        election:  concurrency.NewElection(sess, leaderKey),
        leaderKey: leaderKey,
        nodeID:    nodeID,
    }, nil
}

func (e *LeaderElector) Run(ctx context.Context) error {
    for {
        // Campaign blocks cho đến khi node này được bầu làm leader
        // etcd đảm bảo chỉ 1 node là leader (quorum-based)
        if err := e.election.Campaign(ctx, e.nodeID); err != nil {
            if ctx.Err() != nil {
                return nil
            }
            log.Printf("campaign error: %v, retrying...", err)
            time.Sleep(5 * time.Second)
            continue
        }

        log.Printf("node %s became leader", e.nodeID)
        leaderCtx, resignLeader := context.WithCancel(ctx)

        // Chạy leader tasks
        go e.runLeaderTasks(leaderCtx)

        // Watch: nếu mất lease, resign
        select {
        case <-ctx.Done():
            resignLeader()
            e.election.Resign(context.Background())
            return nil
        case <-leaderCtx.Done():
            // Leader tasks yêu cầu resign
        }

        // Resign và thử lại
        resignLeader()
        e.election.Resign(ctx)
        log.Printf("node %s resigned from leader", e.nodeID)
    }
}

func (e *LeaderElector) runLeaderTasks(ctx context.Context) {
    // Fencing token: lấy revision từ etcd để detect stale leader
    resp, err := e.client.Get(ctx, e.leaderKey)
    if err != nil {
        return
    }
    fencingToken := resp.Header.Revision

    // Dùng fencing token trong mọi write operation
    // Transaction chỉ thành công nếu revision khớp
    _, err = e.client.Txn(ctx).
        If(clientv3.Compare(clientv3.ModRevision(e.leaderKey), "=", fencingToken)).
        Then(clientv3.OpPut("data/key", "value")).
        Commit()
    if err != nil {
        log.Printf("write rejected: not leader or stale: %v", err)
    }
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Dùng consensus library có sẵn: etcd, Raft (hashicorp/raft), ZooKeeper
- [ ] Leader election phải yêu cầu majority quorum (> N/2 nodes)
- [ ] Implement fencing token: mọi write phải verify epoch/term
- [ ] Leader lease có TTL - tự động expire khi leader chết
- [ ] STONITH: prevent split brain bằng cách kill node khi uncertain
- [ ] Alert khi leader change xảy ra thường xuyên
- [ ] Test network partition với Toxiproxy hoặc tc qdisc

**Go vet / staticcheck rules:**
```bash
# Vet cơ bản
go vet ./...

# Race detector cho concurrent state
go test -race ./...

# Staticcheck
staticcheck ./...

# Chaos testing
# Dùng Toxiproxy để simulate network partition
```

---

## Pattern 10: Saga Compensation Thiếu {#pattern-10}

### 1. Tên
**Saga Compensation Thiếu** (Missing Saga Compensation)

### 2. Phân loại
Domain: Distributed Systems / Subcategory: Saga Pattern, Distributed Transaction, Data Consistency

### 3. Mức nghiêm trọng
> HIGH - Distributed transaction không có compensation để rollback khiến hệ thống rơi vào trạng thái không nhất quán khi một bước thất bại. Ví dụ: tiền đã bị trừ nhưng đơn hàng không được tạo.

### 4. Vấn đề

Trong microservice, không thể dùng ACID transaction truyền thống. Saga pattern thay thế bằng chuỗi local transaction + compensation transaction để rollback khi có lỗi.

```
Distributed Order Flow - KHÔNG CÓ Compensation:

  1. Deduct Payment: SUCCESS (trừ 500k)
  2. Create Order:   SUCCESS (order ID: 123)
  3. Reserve Stock:  FAIL    (hết hàng!)

  Kết quả: Khách bị trừ tiền nhưng không có hàng!
           Order 123 tồn tại nhưng stock không bị trừ
           DATA INCONSISTENCY!

Saga Pattern với Compensation:

  1. Deduct Payment:  SUCCESS T1 ---> (lưu compensation: refund payment)
  2. Create Order:    SUCCESS T2 ---> (lưu compensation: cancel order)
  3. Reserve Stock:   FAIL

  Compensation chain (ngược lại):
  C2. Cancel Order:    ROLLBACK T2
  C1. Refund Payment:  ROLLBACK T1

  Kết quả: Hệ thống trở về trạng thái nhất quán!
```

Nguyên nhân phổ biến:
- Gọi nhiều service sequentially không có rollback plan
- Compensation transaction không idempotent
- Không lưu saga state để resume khi process crash
- Compensation cũng có thể fail (không handle)

### 5. Phát hiện trong mã nguồn

**Dấu hiệu trong code:**
- Chuỗi service call không có error handler với rollback
- Không có compensation/rollback function cho mỗi step
- Không lưu saga execution log vào persistent storage
- Error handling chỉ return lỗi, không rollback đã làm

**Regex patterns (dùng với ripgrep):**

```bash
# Tìm chuỗi service call không có compensation
rg -A 30 "func.*Order\|func.*Transaction\|func.*Purchase" --type go | rg -L "rollback\|compensate\|Compensation"

# Tìm error handling không có cleanup
rg "if err != nil" --type go -n -A 3 | rg -L "rollback\|undo\|cancel\|compensate"

# Tìm saga implementation
rg "saga\|Saga\|compensation\|Compensation" --type go -n

# Tìm distributed transaction không dùng saga/outbox pattern
rg -l "service.*Call\|client.*Create\|client.*Deduct" --type go | \
  xargs rg -L "saga\|outbox\|compensat"
```

### 6. Giải pháp

| Phương pháp | Trước (BAD) | Sau (GOOD) |
|-------------|-------------|------------|
| Error handling | Return lỗi | Run compensation chain |
| Rollback | Không có | Compensation per step |
| Persistence | Không lưu state | Saga log trong DB |
| Idempotency | Không có | Compensation idempotent |
| Recovery | Manual | Auto-resume từ saga log |

**Code BAD - Không có compensation:**
```go
// BAD: Lỗi ở step 3 không rollback step 1, 2
func (s *OrderService) CreateOrder(ctx context.Context, req OrderRequest) error {
    if err := s.paymentSvc.Deduct(ctx, req.UserID, req.Amount); err != nil {
        return err
    }
    orderID, err := s.orderSvc.Create(ctx, req)
    if err != nil {
        // KHÔNG ROLLBACK PAYMENT! User mất tiền!
        return err
    }
    if err := s.stockSvc.Reserve(ctx, req.Items); err != nil {
        // KHÔNG ROLLBACK PAYMENT VÀ ORDER! DATA INCONSISTENCY!
        return err
    }
    return nil
}
```

**Code GOOD - Saga với compensation:**
```go
// GOOD: Saga orchestrator với compensation chain
type SagaStep struct {
    Name      string
    Execute   func(ctx context.Context, saga *SagaExecution) error
    Compensate func(ctx context.Context, saga *SagaExecution) error
}

type SagaExecution struct {
    ID          string
    CompletedSteps []string
    Data        map[string]interface{}
}

type SagaOrchestrator struct {
    steps  []SagaStep
    store  SagaStore // Persistent storage for saga state
}

func (o *SagaOrchestrator) Execute(ctx context.Context, data map[string]interface{}) error {
    execution := &SagaExecution{
        ID:   uuid.New().String(),
        Data: data,
    }

    // Lưu saga execution vào DB
    if err := o.store.Save(ctx, execution); err != nil {
        return err
    }

    var completedIdx int
    for i, step := range o.steps {
        if err := step.Execute(ctx, execution); err != nil {
            log.Printf("saga %s: step %s failed: %v, starting compensation", execution.ID, step.Name, err)
            // Chạy compensation ngược lại cho các step đã thành công
            o.compensate(ctx, execution, completedIdx)
            return fmt.Errorf("saga failed at step %s: %w", step.Name, err)
        }
        completedIdx = i
        execution.CompletedSteps = append(execution.CompletedSteps, step.Name)
        // Persist sau mỗi step thành công
        o.store.Save(ctx, execution)
    }

    execution.Data["status"] = "completed"
    o.store.Save(ctx, execution)
    return nil
}

func (o *SagaOrchestrator) compensate(ctx context.Context, exec *SagaExecution, lastCompleted int) {
    // Compensation chạy ngược từ step cuối cùng thành công
    for i := lastCompleted; i >= 0; i-- {
        step := o.steps[i]
        // Retry compensation với backoff - compensation phải idempotent
        for attempt := 0; attempt < 3; attempt++ {
            if err := step.Compensate(ctx, exec); err != nil {
                log.Printf("compensation step %s attempt %d failed: %v", step.Name, attempt+1, err)
                time.Sleep(time.Duration(attempt+1) * time.Second)
                continue
            }
            break
        }
    }
}

// Sử dụng
func NewOrderSaga(paymentSvc PaymentService, orderSvc OrderSvc, stockSvc StockService) *SagaOrchestrator {
    return &SagaOrchestrator{
        steps: []SagaStep{
            {
                Name: "deduct-payment",
                Execute: func(ctx context.Context, saga *SagaExecution) error {
                    txID, err := paymentSvc.Deduct(ctx, saga.Data["userID"].(string), saga.Data["amount"].(float64))
                    if err != nil {
                        return err
                    }
                    saga.Data["paymentTxID"] = txID // Lưu để compensation dùng
                    return nil
                },
                Compensate: func(ctx context.Context, saga *SagaExecution) error {
                    txID, ok := saga.Data["paymentTxID"].(string)
                    if !ok {
                        return nil // Chưa thực hiện, không cần compensate
                    }
                    return paymentSvc.Refund(ctx, txID) // Idempotent
                },
            },
            {
                Name: "create-order",
                Execute: func(ctx context.Context, saga *SagaExecution) error {
                    orderID, err := orderSvc.Create(ctx, saga.Data)
                    if err != nil {
                        return err
                    }
                    saga.Data["orderID"] = orderID
                    return nil
                },
                Compensate: func(ctx context.Context, saga *SagaExecution) error {
                    orderID, ok := saga.Data["orderID"].(string)
                    if !ok {
                        return nil
                    }
                    return orderSvc.Cancel(ctx, orderID) // Idempotent
                },
            },
            {
                Name: "reserve-stock",
                Execute: func(ctx context.Context, saga *SagaExecution) error {
                    return stockSvc.Reserve(ctx, saga.Data["items"])
                },
                Compensate: func(ctx context.Context, saga *SagaExecution) error {
                    return stockSvc.Release(ctx, saga.Data["items"]) // Idempotent
                },
            },
        },
    }
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Mỗi step trong distributed transaction phải có compensation function
- [ ] Compensation phải idempotent (có thể gọi nhiều lần an toàn)
- [ ] Lưu saga state vào persistent storage sau mỗi step
- [ ] Implement auto-recovery: resume saga từ saga log khi process restart
- [ ] Test: inject failure ở mỗi step và verify compensation chạy đúng
- [ ] Monitor: alert khi saga compensation rate cao
- [ ] Dùng Outbox pattern để đảm bảo message được gửi atomically với DB write

**Go vet / staticcheck rules:**
```bash
# Vet cơ bản
go vet ./...

# Kiểm tra error handling
errcheck ./...

# Integration test cho saga
go test -v -run TestSaga ./...

# Staticcheck
staticcheck ./...
```

---

## Pattern 11: Health Check Giả {#pattern-11}

### 1. Tên
**Health Check Giả** (Superficial Health Check)

### 2. Phân loại
Domain: Distributed Systems / Subcategory: Observability, Kubernetes, Service Reliability

### 3. Mức nghiêm trọng
> MEDIUM - Health check chỉ trả về 200 OK mà không verify các dependency thực sự khiến load balancer gửi traffic đến instance đang lỗi. Service được coi là healthy nhưng thực ra không thể phục vụ request.

### 4. Vấn đề

Health check đơn giản không verify DB, cache, và dependency khác. Instance có thể healthy về mặt process nhưng không thể xử lý request vì DB đã down.

```
Health Check Giả:

  /health --> HTTP 200 "OK"

  Nhưng thực tế:
  Instance A: /health 200 OK, nhưng DB connection pool EXHAUSTED
  Instance B: /health 200 OK, nhưng Redis UNREACHABLE
  Instance C: /health 200 OK, nhưng Disk FULL

  Load Balancer gửi traffic đến cả 3 instance
  --> Mọi request đều FAIL!

Health Check Thực Sự:

  /health/live   --> "Tôi đang sống" (process OK) --> Kubernetes liveness
  /health/ready  --> "Tôi sẵn sàng nhận traffic"  --> Kubernetes readiness
                   + Check DB connection
                   + Check Redis ping
                   + Check disk space
                   + Check dependency services
```

Nguyên nhân phổ biến:
- Health check chỉ return HTTP 200 không check gì
- Không phân biệt liveness vs readiness probe
- Không check database connection, cache, external APIs
- Timeout health check quá ngắn

### 5. Phát hiện trong mã nguồn

**Dấu hiệu trong code:**
- `/health` handler chỉ return `{"status":"ok"}` không check gì
- Không có `readyz` endpoint riêng biệt với dependency check
- Database ping không được gọi trong health check
- Health check timeout quá ngắn hoặc không có

**Regex patterns (dùng với ripgrep):**

```bash
# Tìm health check handler đơn giản (không check gì)
rg -A 5 "health\|/health\|healthz" --type go | rg "200\|OK\|ok" | rg -L "db\.\|ping\|Ping\|check"

# Tìm handler chỉ write OK
rg "w\.Write.*ok\|w\.WriteHeader.*200" --type go -n -B 5 | rg "health"

# Kiểm tra có liveness/readiness probe không
rg "live\|ready\|liveness\|readiness" --type go -n

# Tìm health check không ping database
rg -l "health" --type go | xargs rg -L "db\.Ping\|sql\.DB\|redis.*Ping"
```

### 6. Giải pháp

| Phương pháp | Trước (BAD) | Sau (GOOD) |
|-------------|-------------|------------|
| Liveness | Check process | `/healthz/live` - process alive |
| Readiness | Không có | `/healthz/ready` - dependencies OK |
| DB check | Không có | `db.PingContext` với timeout |
| Cache check | Không có | Redis PING |
| Response | `{"status":"ok"}` | Detailed component status |

**Code BAD - Health check giả:**
```go
// BAD: Health check không check gì cả
func healthHandler(w http.ResponseWriter, r *http.Request) {
    // Luôn trả về OK dù DB có down hay không!
    w.WriteHeader(http.StatusOK)
    w.Write([]byte(`{"status":"ok"}`))
}
```

**Code GOOD - Health check thực sự:**
```go
// GOOD: Liveness và Readiness probe riêng biệt
type HealthChecker struct {
    db    *sql.DB
    redis *redis.Client
}

type ComponentStatus struct {
    Status  string `json:"status"`
    Latency string `json:"latency,omitempty"`
    Error   string `json:"error,omitempty"`
}

type HealthResponse struct {
    Status     string                       `json:"status"`
    Components map[string]ComponentStatus   `json:"components,omitempty"`
    Version    string                       `json:"version"`
    Uptime     string                       `json:"uptime"`
}

// LivenessHandler: chỉ check process còn sống không
// Kubernetes restart nếu endpoint này fail
func (h *HealthChecker) LivenessHandler(w http.ResponseWriter, r *http.Request) {
    w.Header().Set("Content-Type", "application/json")
    w.WriteHeader(http.StatusOK)
    json.NewEncoder(w).Encode(HealthResponse{
        Status:  "alive",
        Version: version.BuildVersion,
    })
}

// ReadinessHandler: check tất cả dependency
// Kubernetes không gửi traffic nếu endpoint này fail
func (h *HealthChecker) ReadinessHandler(w http.ResponseWriter, r *http.Request) {
    ctx, cancel := context.WithTimeout(r.Context(), 5*time.Second)
    defer cancel()

    components := make(map[string]ComponentStatus)
    overallOK := true

    // Check database
    dbStart := time.Now()
    if err := h.db.PingContext(ctx); err != nil {
        components["database"] = ComponentStatus{
            Status: "unhealthy",
            Error:  err.Error(),
        }
        overallOK = false
    } else {
        components["database"] = ComponentStatus{
            Status:  "healthy",
            Latency: time.Since(dbStart).String(),
        }
    }

    // Check Redis
    redisStart := time.Now()
    if err := h.redis.Ping(ctx).Err(); err != nil {
        components["redis"] = ComponentStatus{
            Status: "unhealthy",
            Error:  err.Error(),
        }
        overallOK = false
    } else {
        components["redis"] = ComponentStatus{
            Status:  "healthy",
            Latency: time.Since(redisStart).String(),
        }
    }

    response := HealthResponse{
        Status:     "ready",
        Components: components,
        Version:    version.BuildVersion,
    }

    statusCode := http.StatusOK
    if !overallOK {
        response.Status = "not ready"
        statusCode = http.StatusServiceUnavailable
    }

    w.Header().Set("Content-Type", "application/json")
    w.WriteHeader(statusCode)
    json.NewEncoder(w).Encode(response)
}

// Đăng ký routes
func RegisterHealthRoutes(mux *http.ServeMux, checker *HealthChecker) {
    mux.HandleFunc("/healthz/live", checker.LivenessHandler)
    mux.HandleFunc("/healthz/ready", checker.ReadinessHandler)
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Phân biệt liveness probe và readiness probe
- [ ] Readiness probe phải check DB, Redis, và critical dependency
- [ ] Health check endpoint có timeout riêng (3-5s)
- [ ] Response chứa chi tiết từng component (hữu ích khi debug)
- [ ] Kubernetes `livenessProbe` và `readinessProbe` config đúng
- [ ] Alert khi readiness fail liên tục > 1 phút
- [ ] Test: kill dependency và verify health check phản ánh đúng

**Go vet / staticcheck rules:**
```bash
# Vet cơ bản
go vet ./...

# Staticcheck
staticcheck ./...

# Test health check với dependency down
go test -v -run TestHealthCheck ./...

# Kiểm tra timeout trên health check handler
golangci-lint run --enable contextcheck ./...
```

---

## Pattern 12: Connection Pool Stale {#pattern-12}

### 1. Tên
**Connection Pool Stale** (Connection Pool Bị Cũ / Không Còn Hợp Lệ)

### 2. Phân loại
Domain: Distributed Systems / Subcategory: Database, Connection Management, Reliability

### 3. Mức nghiêm trọng
> HIGH - Connection pool giữ connection cũ bị close bởi server (firewall timeout, DB restart, network reset). Khi dùng lại connection stale, nhận `broken pipe` hoặc `connection reset`. Biểu hiện lẻ tẻ rất khó debug.

### 4. Vấn đề

Database server có idle timeout. Firewall có TCP idle timeout. Nếu connection pool giữ connection lâu hơn timeout phía server, connection bị close ở server nhưng client không biết cho đến khi cố dùng.

```
Connection Stale Timeline:

  t=0:    Pool tạo connection. Firewall timeout = 10 phút.
  t=5min: Connection idle trong pool (không dùng)
  t=10min: Firewall silently close TCP connection
           Server-side connection closed
           Client pool KHÔNG BIẾT (vẫn nghĩ connection OK)

  t=11min: Request đến, pool dùng lại connection này
           Client gửi query
           --> "broken pipe" / "connection reset by peer"
           --> Request FAIL!
           --> User nhận lỗi 500 không giải thích được

Tần suất lỗi: Random, phụ thuộc vào idle time và load
Nguy hiểm: Khó reproduce, thường mất trong logs
```

Nguyên nhân phổ biến:
- `MaxIdleConns` và `ConnMaxIdleTime` không config
- `ConnMaxLifetime` quá dài hoặc không set
- Firewall/NAT timeout ngắn hơn idle time của pool
- Không có connection health check (ping trước khi dùng)

### 5. Phát hiện trong mã nguồn

**Dấu hiệu trong code:**
- `sql.Open` không set `SetConnMaxIdleTime` hoặc `SetConnMaxLifetime`
- `MaxIdleConns` không được config hoặc quá cao
- Không có retry khi nhận `broken pipe` error
- Database driver không có `ping` before use

**Regex patterns (dùng với ripgrep):**

```bash
# Tìm sql.Open không config pool
rg "sql\.Open\b" --type go -n -A 10 | rg -L "SetConnMaxIdleTime\|SetConnMaxLifetime\|SetMaxIdleConns"

# Tìm database setup không có pool config
rg "sql\.Open\|gorm\.Open\|pgxpool\.New" --type go -n

# Tìm pool config thiếu
rg "db\.SetMax\|db\.SetConn" --type go -n

# Tìm connection không có idle timeout
rg "MaxIdleConns\|MaxOpenConns" --type go -n -A 2 | rg -L "IdleTime\|Lifetime"
```

### 6. Giải pháp

| Phương pháp | Trước (BAD) | Sau (GOOD) |
|-------------|-------------|------------|
| MaxIdleConns | Mặc định (2) | Match số goroutine |
| ConnMaxIdleTime | Không set | < firewall timeout (e.g., 5 phút) |
| ConnMaxLifetime | Không set | Ngắn hơn server timeout (e.g., 30 phút) |
| MaxOpenConns | Không giới hạn | Giới hạn rõ ràng |
| Health check | Không có | `db.PingContext` sau error |

**Code BAD - Pool không config:**
```go
// BAD: Dùng default pool config - dễ bị stale connection
func connectDB(dsn string) (*sql.DB, error) {
    db, err := sql.Open("postgres", dsn)
    if err != nil {
        return nil, err
    }
    // Không set pool config gì cả!
    // MaxIdleConns=2 (default), ConnMaxIdleTime=0 (không expire!)
    // Firewall timeout 5 phút sẽ kill connection sau 5 phút idle
    // Nhưng pool giữ chúng mãi mãi --> stale connections!
    return db, nil
}
```

**Code GOOD - Pool config đúng:**
```go
// GOOD: Pool config đầy đủ, phù hợp với environment
type DBConfig struct {
    DSN                string
    MaxOpenConns       int
    MaxIdleConns       int
    ConnMaxIdleTime    time.Duration
    ConnMaxLifetime    time.Duration
}

func DefaultDBConfig(dsn string) DBConfig {
    return DBConfig{
        DSN:             dsn,
        MaxOpenConns:    25,                // Giới hạn tổng connection
        MaxIdleConns:    10,                // Giữ tối đa 10 idle connection
        ConnMaxIdleTime: 5 * time.Minute,   // Close idle conn sau 5 phút
                                            // (phải < firewall timeout, thường 10-15 phút)
        ConnMaxLifetime: 30 * time.Minute,  // Bắt buộc reconnect sau 30 phút
                                            // (bắt lấy DB password rotation, failover)
    }
}

func ConnectDB(cfg DBConfig) (*sql.DB, error) {
    db, err := sql.Open("postgres", cfg.DSN)
    if err != nil {
        return nil, fmt.Errorf("open db: %w", err)
    }

    db.SetMaxOpenConns(cfg.MaxOpenConns)
    db.SetMaxIdleConns(cfg.MaxIdleConns)
    db.SetConnMaxIdleTime(cfg.ConnMaxIdleTime)
    db.SetConnMaxLifetime(cfg.ConnMaxLifetime)

    // Verify connection ngay khi khởi động
    ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
    defer cancel()
    if err := db.PingContext(ctx); err != nil {
        return nil, fmt.Errorf("ping db: %w", err)
    }

    return db, nil
}

// GOOD: Retry query khi gặp stale connection error
func queryWithRetry(
    ctx context.Context,
    db *sql.DB,
    query string,
    args ...interface{},
) (*sql.Rows, error) {
    const maxAttempts = 2
    for attempt := 0; attempt < maxAttempts; attempt++ {
        rows, err := db.QueryContext(ctx, query, args...)
        if err == nil {
            return rows, nil
        }

        // Check nếu là stale connection error
        if isStaleConnectionError(err) && attempt == 0 {
            log.Printf("stale connection detected, retrying: %v", err)
            // Ping để force pool cleanup stale connections
            db.PingContext(ctx)
            continue
        }
        return nil, err
    }
    return nil, fmt.Errorf("query failed after %d attempts", maxAttempts)
}

func isStaleConnectionError(err error) bool {
    if err == nil {
        return false
    }
    msg := err.Error()
    return strings.Contains(msg, "broken pipe") ||
        strings.Contains(msg, "connection reset by peer") ||
        strings.Contains(msg, "EOF") ||
        strings.Contains(msg, "invalid connection")
}

// GOOD: Monitor pool stats
func recordDBPoolMetrics(db *sql.DB, poolName string) {
    go func() {
        ticker := time.NewTicker(30 * time.Second)
        defer ticker.Stop()
        for range ticker.C {
            stats := db.Stats()
            dbPoolOpenConns.WithLabelValues(poolName).Set(float64(stats.OpenConnections))
            dbPoolIdleConns.WithLabelValues(poolName).Set(float64(stats.Idle))
            dbPoolInUseConns.WithLabelValues(poolName).Set(float64(stats.InUse))
            dbPoolWaitCount.WithLabelValues(poolName).Set(float64(stats.WaitCount))
        }
    }()
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Luôn set `ConnMaxIdleTime` < firewall/NAT idle timeout
- [ ] Set `ConnMaxLifetime` để force reconnect định kỳ
- [ ] `MaxIdleConns` <= `MaxOpenConns`
- [ ] `MaxOpenConns` phải có giới hạn (không để 0 = unlimited)
- [ ] Verify connection ngay khi startup bằng `db.PingContext`
- [ ] Implement retry với stale connection detection
- [ ] Monitor pool stats: `db.Stats()` qua Prometheus
- [ ] Alert khi `WaitCount` tăng cao (pool exhaustion)
- [ ] Test: restart DB server và verify service recover

**Go vet / staticcheck rules:**
```bash
# Vet cơ bản
go vet ./...

# Kiểm tra database usage
staticcheck -checks "SA1019" ./...

# Kiểm tra error handling với sql
errcheck -ignoretests ./...

# golangci-lint
golangci-lint run --enable sqlclosecheck,rowserrcheck ./...

# Integration test với DB restart
go test -v -run TestDBReconnect ./...
```

---

*Domain 02 hoàn thành - 12 patterns về Hệ Thống Phân Tán*
