# Domain 02: Hệ Thống Phân Tán (Distributed Systems)

**Lĩnh vực:** .NET Engineering - Backend / Microservices
**Ngôn ngữ:** C#
**Tổng số patterns:** 12
**Cập nhật:** 2026-02-18

---

## Tổng Quan Domain

Hệ thống phân tán trong .NET là nơi ẩn chứa nhiều loại lỗi tinh vi nhất: từ socket exhaustion do dùng sai HttpClient, đến retry storm làm sập toàn bộ cluster, đến poison message làm tê liệt message queue. Các lỗi này thường chỉ xuất hiện ở môi trường production dưới tải thực tế và rất khó tái hiện trong dev.

```
PHÂN LOẠI MỨC ĐỘ NGHIÊM TRỌNG
================================
CRITICAL  - Có thể gây crash ứng dụng, socket/port exhaustion, cascade failure
HIGH      - Gây suy giảm hiệu năng nghiêm trọng, data inconsistency, queue block
MEDIUM    - Gây memory leak, false health status, DNS stale, snapshot overhead
LOW       - Code smell, vi phạm best practice
```

---

## Pattern 01: HttpClient Misuse

### 1. Tên
**HttpClient Misuse** (new HttpClient Per Request)

### 2. Phân Loại
- **Domain:** Distributed Systems
- **Subcategory:** Resource Management / Socket Exhaustion

### 3. Mức Nghiêm Trọng
**CRITICAL** - Gây socket exhaustion, port exhaustion, ứng dụng không thể kết nối mạng

### 4. Vấn Đề

`HttpClient` được thiết kế để tái sử dụng (reuse), không phải tạo mới cho mỗi request. Khi tạo mới `HttpClient` và `Dispose()` sau mỗi request, các socket ở trạng thái `TIME_WAIT` vẫn giữ port trong 240 giây. Với traffic đủ cao, toàn bộ ephemeral port range (49152–65535) bị cạn kiệt.

**Cơ chế gây lỗi:**

```
REQUEST RATE: 100 req/s
TIME_WAIT duration: 240 giây

Số socket bị giữ sau 4 phút:
100 req/s x 240s = 24,000 sockets TIME_WAIT

Ephemeral ports: ~16,383 (49152 - 65535)

24,000 > 16,383 → PORT EXHAUSTION!

TIMELINE:
  t=0s  ┌──────────────────────────────────────────────┐
        │ new HttpClient() → connect → Dispose()       │
        │ Socket vào TIME_WAIT (OS giữ 240s)           │
  t=4m  ├──────────────────────────────────────────────┤
        │ Tất cả ports đã bị dùng                      │
        │ SocketException: "Only one usage of each     │
        │ socket address is normally permitted"         │
  t=4m+ └──────────────────────────────────────────────┘
        ☠️ Application không thể mở connection mới
```

**Vấn đề thứ hai: DNS không được refresh**

Ngay cả khi dùng singleton `HttpClient`, nếu không dùng `IHttpClientFactory`, DNS TTL bị bỏ qua — HttpClient cache kết nối vĩnh viễn, không nhận biết được DNS changes (rolling deploy, blue-green).

```
DNS CACHING VỚI SINGLETON HttpClient:
┌─────────────────────────────────────────────────────────┐
│  t=0:   api.example.com → 10.0.0.1  (kết nối được)     │
│  t=30m: api.example.com → 10.0.0.2  (deploy mới)       │
│  HttpClient vẫn giữ connection pool đến 10.0.0.1       │
│  → Gửi request đến server đã retire                    │
│  → Connection refused / timeout                        │
└─────────────────────────────────────────────────────────┘
```

### 5. Phát Hiện Trong Mã Nguồn

**Dấu hiệu nhận biết:**
- `new HttpClient()` bên trong method (không phải constructor/DI)
- `using (var client = new HttpClient())` pattern
- Không đăng ký `IHttpClientFactory` trong DI container
- Log có `SocketException` hoặc `HttpRequestException` với "Only one usage"
- `netstat -an | grep TIME_WAIT` cho thấy hàng ngàn kết nối TIME_WAIT

**Regex patterns cho ripgrep:**

```bash
# Tìm new HttpClient() trong method body (không phải field/constructor)
rg "new HttpClient\(\)" --type cs

# Tìm using HttpClient pattern (guaranteed socket exhaustion)
rg "using\s*\(\s*var\s+\w+\s*=\s*new HttpClient" --type cs

# Tìm HttpClient được khai báo mà không qua IHttpClientFactory
rg "HttpClient\s+\w+\s*=\s*new" --type cs

# Tìm nơi không có IHttpClientFactory trong DI
rg "AddHttpClient|IHttpClientFactory" --type cs
```

### 6. Giải Pháp

| Tiêu chí | BAD (new per request) | GOOD (IHttpClientFactory) |
|---|---|---|
| Socket reuse | Không | Có (connection pooling) |
| DNS refresh | N/A | Có (PooledConnectionLifetime) |
| Cấu hình tập trung | Không | Có (Named/Typed clients) |
| Resilience (Polly) | Thủ công | Tích hợp sẵn |

**BAD - Tạo HttpClient mới mỗi request:**

```csharp
// ❌ BAD: Gây socket exhaustion
public class OrderService
{
    public async Task<Order> GetOrderAsync(int id)
    {
        // Tạo mới mỗi lần gọi → TIME_WAIT socket leak
        using var client = new HttpClient();
        client.BaseAddress = new Uri("https://api.example.com");
        var response = await client.GetAsync($"/orders/{id}");
        response.EnsureSuccessStatusCode();
        return await response.Content.ReadFromJsonAsync<Order>();
    }
}

// ❌ BAD: Singleton nhưng DNS không refresh
public class OrderService
{
    // DNS bị cache vĩnh viễn, không biết về rolling deploy
    private static readonly HttpClient _client = new HttpClient
    {
        BaseAddress = new Uri("https://api.example.com")
    };

    public async Task<Order> GetOrderAsync(int id)
    {
        var response = await _client.GetAsync($"/orders/{id}");
        return await response.Content.ReadFromJsonAsync<Order>();
    }
}
```

**GOOD - IHttpClientFactory với Typed Client:**

```csharp
// ✅ GOOD: Typed HttpClient với IHttpClientFactory

// 1. Đăng ký trong Program.cs / Startup.cs
builder.Services.AddHttpClient<IOrderApiClient, OrderApiClient>(client =>
{
    client.BaseAddress = new Uri("https://api.example.com");
    client.Timeout = TimeSpan.FromSeconds(30);
})
.ConfigurePrimaryHttpMessageHandler(() => new SocketsHttpHandler
{
    // DNS được refresh mỗi 5 phút — giải quyết vấn đề DNS stale
    PooledConnectionLifetime = TimeSpan.FromMinutes(5),
    PooledConnectionIdleTimeout = TimeSpan.FromMinutes(2),
    MaxConnectionsPerServer = 100,
})
.AddStandardResilienceHandler(); // .NET 8+ Polly integration

// 2. Typed Client
public interface IOrderApiClient
{
    Task<Order?> GetOrderAsync(int id, CancellationToken ct = default);
    Task<Order> CreateOrderAsync(CreateOrderRequest request, CancellationToken ct = default);
}

public class OrderApiClient : IOrderApiClient
{
    private readonly HttpClient _client;
    private readonly ILogger<OrderApiClient> _logger;

    // HttpClient được inject bởi IHttpClientFactory — đã có connection pooling
    public OrderApiClient(HttpClient client, ILogger<OrderApiClient> logger)
    {
        _client = client;
        _logger = logger;
    }

    public async Task<Order?> GetOrderAsync(int id, CancellationToken ct = default)
    {
        try
        {
            var response = await _client.GetAsync($"/orders/{id}", ct);

            if (response.StatusCode == HttpStatusCode.NotFound)
                return null;

            response.EnsureSuccessStatusCode();
            return await response.Content.ReadFromJsonAsync<Order>(cancellationToken: ct);
        }
        catch (HttpRequestException ex)
        {
            _logger.LogError(ex, "Failed to get order {OrderId}", id);
            throw;
        }
    }

    public async Task<Order> CreateOrderAsync(CreateOrderRequest request, CancellationToken ct = default)
    {
        var response = await _client.PostAsJsonAsync("/orders", request, ct);
        response.EnsureSuccessStatusCode();
        return await response.Content.ReadFromJsonAsync<Order>(cancellationToken: ct)
            ?? throw new InvalidOperationException("Server returned empty order");
    }
}

// 3. Sử dụng trong service
public class CheckoutService
{
    private readonly IOrderApiClient _orderClient;

    public CheckoutService(IOrderApiClient orderClient)
    {
        _orderClient = orderClient;
    }

    public async Task<Order> PlaceOrderAsync(CartItem[] items, CancellationToken ct)
    {
        var request = new CreateOrderRequest(items);
        return await _orderClient.CreateOrderAsync(request, ct);
    }
}
```

### 7. Phòng Ngừa

**Checklist:**
- [ ] Không có `new HttpClient()` trong method body
- [ ] Không có `using (var client = new HttpClient())` pattern
- [ ] Tất cả HttpClient được đăng ký qua `AddHttpClient<>()` hoặc `AddHttpClient(name)`
- [ ] `PooledConnectionLifetime` được set (mặc định là không giới hạn)
- [ ] Timeout được cấu hình (mặc định là 100 giây — quá dài)
- [ ] Typed client interface được mock trong unit test

**Roslyn Analyzer Rules:**

```csharp
// Thêm vào .editorconfig
dotnet_diagnostic.CA2000.severity = error   // Dispose objects before losing scope
dotnet_diagnostic.SYSLIB0014.severity = error // WebClient obsolete (HttpClient thay thế)

// Custom Analyzer: Phát hiện new HttpClient() trong method
// Cảnh báo: "Use IHttpClientFactory instead of new HttpClient()"
// DiagnosticId: HTTP001
```

---

## Pattern 02: Retry Storm

### 1. Tên
**Retry Storm** (Polly Misconfiguration / Thundering Herd on Retry)

### 2. Phân Loại
- **Domain:** Distributed Systems
- **Subcategory:** Resilience / Cascading Failure

### 3. Mức Nghiêm Trọng
**CRITICAL** - Gây cascade failure, làm sập dịch vụ đang recover, toàn bộ cluster bị ảnh hưởng

### 4. Vấn Đề

Retry policy được thêm vào với mục đích tăng resilience, nhưng khi cấu hình sai (không có jitter, quá nhiều retry, quá nhiều instance cùng retry), chúng tạo ra "Retry Storm" — làm cho dịch vụ đang cố gắng recover bị overwhelm bởi hàng loạt request đồng thời.

**Cơ chế Thundering Herd:**

```
SCENARIO: 500 instances, mỗi instance retry 3 lần sau 1 giây

t=0s:   Service A gặp timeout (tất cả 500 instances cùng lúc)
t=1s:   500 x 3 = 1,500 retry requests đồng loạt đến Service B
        ↑ Service B đang cố recover → bị overwhelm tiếp
t=2s:   1,500 requests tiếp tục retry → 4,500 requests
t=3s:   Service B hoàn toàn sập

KHÔNG CÓ JITTER:                    CÓ JITTER (exponential):
  Retry 1: tất cả sau 1.0s            Retry 1: mỗi instance sau 0.8s - 1.2s
  Retry 2: tất cả sau 2.0s            Retry 2: mỗi instance sau 1.5s - 2.5s
  Retry 3: tất cả sau 4.0s            Retry 3: mỗi instance sau 3.0s - 5.0s
  → Spike đồng loạt                   → Phân tán đều, Service B có thể recover
```

**Retry Storm với Polly cấu hình sai:**

```
CLIENT (500 pods)                SERVICE B
    │                                │
    │──── 500 req ──────────────────►│
    │                         ❌ timeout (overloaded)
    │◄─── timeout ────────────────── │
    │                                │
    │ [wait 1s — NO JITTER]          │ (đang cố recover, CPU cao)
    │                                │
    │──── 500 retry ────────────────►│
    │                         ❌ timeout (ngay lập tức)
    │◄─── timeout ────────────────── │
    │                                │
    │──── 500 retry ────────────────►│
    │                         ☠️ Service B crash hoàn toàn
```

### 5. Phát Hiện Trong Mã Nguồn

**Dấu hiệu nhận biết:**
- Polly `RetryPolicy` không có `WaitAndRetry` hoặc có delay cố định không có jitter
- Retry count lớn (>3) kết hợp với delay ngắn (<500ms)
- Không có Circuit Breaker kết hợp với Retry
- Log metric cho thấy traffic spike đồng thời sau mỗi lần downstream failure

**Regex patterns cho ripgrep:**

```bash
# Tìm RetryPolicy không có jitter (delay cố định)
rg "WaitAndRetry.*TimeSpan\.(FromSeconds|FromMilliseconds)" --type cs

# Tìm Policy.Handle().Retry() không có wait
rg "\.Retry\(\d+\)" --type cs

# Tìm thiếu jitter (không có Random hoặc Jitter)
rg "AddResiliencePipeline|AddPolicyHandler" --type cs

# Tìm retry count quá cao
rg "retryCount\s*=\s*[5-9]|retryCount\s*=\s*\d{2}" --type cs
```

### 6. Giải Pháp

| Tiêu chí | BAD (fixed delay) | GOOD (exponential + jitter) |
|---|---|---|
| Retry delay | Cố định 1s | Exponential với jitter |
| Circuit breaker | Không | Có |
| Max retry | Không giới hạn | 3 lần |
| Bulkhead | Không | Có (max concurrency) |

**BAD - Retry không có jitter:**

```csharp
// ❌ BAD: Tạo Thundering Herd
var retryPolicy = Policy
    .Handle<HttpRequestException>()
    .WaitAndRetryAsync(
        retryCount: 5,                          // Quá nhiều
        sleepDurationProvider: _ => TimeSpan.FromSeconds(1)  // Cố định, không jitter
    );

// ❌ BAD: Polly v8 pipeline không có jitter
services.AddResiliencePipeline("order-api", builder =>
{
    builder.AddRetry(new RetryStrategyOptions
    {
        MaxRetryAttempts = 5,
        Delay = TimeSpan.FromSeconds(2),   // Cố định → Thundering Herd
        BackoffType = DelayBackoffType.Constant  // WORST: tất cả retry cùng lúc
    });
});
```

**GOOD - Exponential backoff với jitter và Circuit Breaker:**

```csharp
// ✅ GOOD: Cấu hình Polly v8 đúng cách

// Program.cs
builder.Services.AddHttpClient<IOrderApiClient, OrderApiClient>()
    .AddResiliencePipeline("order-api", pipelineBuilder =>
    {
        // 1. Retry với exponential backoff + jitter
        pipelineBuilder.AddRetry(new RetryStrategyOptions
        {
            MaxRetryAttempts = 3,   // Tối đa 3 lần
            BackoffType = DelayBackoffType.Exponential,  // 2^n * delay
            Delay = TimeSpan.FromMilliseconds(500),      // Base delay
            UseJitter = true,       // CRITICAL: phân tán retry, tránh thundering herd
            ShouldHandle = new PredicateBuilder()
                .Handle<HttpRequestException>()
                .Handle<TimeoutRejectedException>()
                // Không retry 4xx client errors (trừ 429 Too Many Requests)
                .HandleResult<HttpResponseMessage>(r =>
                    r.StatusCode >= HttpStatusCode.InternalServerError ||
                    r.StatusCode == HttpStatusCode.TooManyRequests),
            OnRetry = args =>
            {
                var logger = args.Context.ServiceProvider?.GetService<ILogger>();
                logger?.LogWarning(
                    "Retry {Attempt} after {Delay}ms due to {Outcome}",
                    args.AttemptNumber,
                    args.RetryDelay.TotalMilliseconds,
                    args.Outcome.Exception?.Message ?? args.Outcome.Result?.StatusCode.ToString()
                );
                return ValueTask.CompletedTask;
            }
        });

        // 2. Circuit Breaker — dừng retry khi service thực sự sập
        pipelineBuilder.AddCircuitBreaker(new CircuitBreakerStrategyOptions
        {
            FailureRatio = 0.5,                         // 50% failure rate
            SamplingDuration = TimeSpan.FromSeconds(30),
            MinimumThroughput = 10,                     // Ít nhất 10 requests mới tính
            BreakDuration = TimeSpan.FromSeconds(30),   // Mở circuit 30 giây
        });

        // 3. Timeout — mỗi attempt có timeout riêng
        pipelineBuilder.AddTimeout(TimeSpan.FromSeconds(10));
    });

// ✅ GOOD: Xử lý 429 Too Many Requests với Retry-After header
public class OrderApiClient : IOrderApiClient
{
    private readonly HttpClient _client;

    public async Task<Order?> GetOrderAsync(int id, CancellationToken ct)
    {
        var response = await _client.GetAsync($"/orders/{id}", ct);

        if (response.StatusCode == HttpStatusCode.TooManyRequests)
        {
            // Đọc Retry-After header nếu có
            var retryAfter = response.Headers.RetryAfter?.Delta ?? TimeSpan.FromSeconds(5);
            await Task.Delay(retryAfter, ct);
            // Polly sẽ retry tự động
            response.EnsureSuccessStatusCode();
        }

        if (response.StatusCode == HttpStatusCode.NotFound) return null;

        response.EnsureSuccessStatusCode();
        return await response.Content.ReadFromJsonAsync<Order>(cancellationToken: ct);
    }
}
```

**Công thức tính delay với jitter:**

```csharp
// Polly UseJitter = true tự động áp dụng:
// delay = base * 2^attempt * random(0.5, 1.5)
// Attempt 1: 500ms * 1 * [0.5-1.5] = 250ms - 750ms
// Attempt 2: 500ms * 2 * [0.5-1.5] = 500ms - 1500ms
// Attempt 3: 500ms * 4 * [0.5-1.5] = 1000ms - 3000ms
```

### 7. Phòng Ngừa

**Checklist:**
- [ ] Tất cả retry policy có `UseJitter = true` hoặc implement jitter thủ công
- [ ] `MaxRetryAttempts` <= 3 cho external services
- [ ] Retry kết hợp Circuit Breaker
- [ ] Không retry 4xx errors (trừ 429)
- [ ] Có timeout cho mỗi attempt
- [ ] Log retry attempt để monitor

**Roslyn Analyzer Rules:**

```csharp
// Custom Analyzer: Phát hiện RetryPolicy không có jitter
// DiagnosticId: POL001
// Message: "Retry policy without jitter can cause thundering herd. Set UseJitter = true"

// Custom Analyzer: Phát hiện RetryPolicy không kèm CircuitBreaker
// DiagnosticId: POL002
// Message: "Add CircuitBreaker to prevent retry storms when service is down"
```

---

## Pattern 03: Circuit Breaker Thiếu

### 1. Tên
**Circuit Breaker Thiếu** (Missing Circuit Breaker)

### 2. Phân Loại
- **Domain:** Distributed Systems
- **Subcategory:** Resilience / Cascading Failure Prevention

### 3. Mức Nghiêm Trọng
**HIGH** - Gây cascade failure, thread pool exhaustion, toàn bộ service bị kéo sập theo downstream failure

### 4. Vấn Đề

Khi một downstream service bị sập hoặc slow, mỗi request đến upstream service sẽ bị block chờ timeout. Không có Circuit Breaker, tất cả threads bị chiếm dụng chờ response từ service đã chết, gây thread pool exhaustion và làm toàn bộ upstream service không thể xử lý request mới.

**Cascade failure không có Circuit Breaker:**

```
UPSTREAM SERVICE              DOWNSTREAM SERVICE
      │                              │
      │                         ❌ SẬP (chậm/chết)
      │                              │
  req1│──────────────────────────────►│ timeout 30s...
  req2│──────────────────────────────►│ timeout 30s...
  req3│──────────────────────────────►│ timeout 30s...
  ...─│──────────────────────────────►│ timeout 30s...
      │
  [Thread pool exhausted — 0 threads còn lại]
      │
  req_new: "No available threads"
  ☠️ UPSTREAM CŨNG SẬP THEO
```

**Circuit Breaker State Machine:**

```
          failure rate cao              timeout hết hạn
[CLOSED] ─────────────────► [OPEN] ─────────────────► [HALF-OPEN]
   │                           │                           │
   │ request bình thường        │ fail-fast immediately     │ thử 1 request
   │ (monitor failure rate)     │ (không gọi downstream)    │ success → CLOSED
   │                            │                           │ fail → OPEN
   └────────────────────────────┴───────────────────────────┘
```

### 5. Phát Hiện Trong Mã Nguồn

**Dấu hiệu nhận biết:**
- Có retry policy nhưng không có circuit breaker
- Thread pool metrics cho thấy exhaustion khi downstream slow
- Tất cả requests bị timeout cùng lúc khi một service bị sập
- Không có `BrokenCircuitException` trong logs

**Regex patterns cho ripgrep:**

```bash
# Tìm AddRetry nhưng không có AddCircuitBreaker trong cùng file
rg "AddRetry" --type cs -l | xargs -I{} sh -c 'grep -L "AddCircuitBreaker\|CircuitBreaker" {}'

# Tìm Polly policy không có circuit breaker
rg "WaitAndRetryAsync" --type cs -l | xargs -I{} sh -c 'grep -L "CircuitBreaker" {}'

# Tìm HttpClient registration không có resilience
rg "AddHttpClient" --type cs -l | xargs -I{} sh -c 'grep -L "AddResiliencePipeline\|AddPolicyHandler" {}'
```

### 6. Giải Pháp

| Tiêu chí | BAD (no circuit breaker) | GOOD (với circuit breaker) |
|---|---|---|
| Downstream failure | Tất cả threads chờ | Fail-fast ngay lập tức |
| Recovery | Không tự động | Tự động thử lại sau BreakDuration |
| Thread pool | Exhausted | Được bảo vệ |
| Latency khi downstream down | 30s timeout | <1ms (immediate rejection) |

**BAD - Chỉ có retry, không có circuit breaker:**

```csharp
// ❌ BAD: Retry mà không có circuit breaker
// Khi service sập, sẽ retry 3 lần x 30s timeout = 90 giây blocked
services.AddHttpClient<IPaymentClient, PaymentClient>()
    .AddResiliencePipeline("payment", builder =>
    {
        builder.AddRetry(new RetryStrategyOptions
        {
            MaxRetryAttempts = 3,
            UseJitter = true
        });
        // ❌ Không có Circuit Breaker
        // Khi payment service sập, mỗi request tốn 90s để fail
    });
```

**GOOD - Retry + Circuit Breaker + Bulkhead:**

```csharp
// ✅ GOOD: Đầy đủ resilience pipeline

services.AddHttpClient<IPaymentClient, PaymentClient>()
    .AddResiliencePipeline("payment-pipeline", builder =>
    {
        // Thứ tự quan trọng: Timeout → Circuit Breaker → Retry → Timeout per attempt

        // 1. Total timeout (bao gồm tất cả retry)
        builder.AddTimeout(TimeSpan.FromSeconds(30));

        // 2. Circuit Breaker — phải đặt TRƯỚC retry
        builder.AddCircuitBreaker(new CircuitBreakerStrategyOptions
        {
            // Mở circuit khi 50% requests fail trong 30 giây
            FailureRatio = 0.5,
            SamplingDuration = TimeSpan.FromSeconds(30),
            MinimumThroughput = 5,      // Cần ít nhất 5 requests để tính

            // Giữ circuit mở 30 giây, sau đó thử lại
            BreakDuration = TimeSpan.FromSeconds(30),

            ShouldHandle = new PredicateBuilder()
                .Handle<HttpRequestException>()
                .Handle<TimeoutRejectedException>()
                .HandleResult<HttpResponseMessage>(r =>
                    r.StatusCode >= HttpStatusCode.InternalServerError),

            OnClosed = args =>
            {
                Console.WriteLine("Circuit CLOSED — payment service recovered");
                return ValueTask.CompletedTask;
            },
            OnOpened = args =>
            {
                Console.WriteLine(
                    "Circuit OPENED — payment service failing. Break for {0}s",
                    args.BreakDuration.TotalSeconds);
                return ValueTask.CompletedTask;
            },
            OnHalfOpened = _ =>
            {
                Console.WriteLine("Circuit HALF-OPEN — testing payment service");
                return ValueTask.CompletedTask;
            }
        });

        // 3. Retry (chỉ chạy khi circuit CLOSED hoặc HALF-OPEN)
        builder.AddRetry(new RetryStrategyOptions
        {
            MaxRetryAttempts = 3,
            BackoffType = DelayBackoffType.Exponential,
            Delay = TimeSpan.FromMilliseconds(300),
            UseJitter = true
        });

        // 4. Per-attempt timeout
        builder.AddTimeout(TimeSpan.FromSeconds(8));
    });

// Xử lý BrokenCircuitException trong caller
public class CheckoutService
{
    private readonly IPaymentClient _paymentClient;

    public async Task<PaymentResult> ProcessPaymentAsync(PaymentRequest request, CancellationToken ct)
    {
        try
        {
            return await _paymentClient.ChargeAsync(request, ct);
        }
        catch (BrokenCircuitException ex)
        {
            // Circuit đang mở — fail fast, không chờ timeout
            throw new ServiceUnavailableException(
                "Payment service is temporarily unavailable. Please try again later.", ex);
        }
        catch (IsolatedCircuitException ex)
        {
            throw new ServiceUnavailableException("Payment service is isolated.", ex);
        }
    }
}
```

### 7. Phòng Ngừa

**Checklist:**
- [ ] Mọi external HTTP call đều có Circuit Breaker
- [ ] Circuit Breaker đặt TRƯỚC Retry trong pipeline
- [ ] `BrokenCircuitException` được xử lý riêng (không phải generic 500)
- [ ] Metrics circuit state được export (Prometheus/Grafana)
- [ ] Alert khi circuit ở trạng thái OPEN > 1 phút

**Roslyn Analyzer Rules:**

```csharp
// Custom Analyzer: Phát hiện AddRetry không kèm AddCircuitBreaker
// DiagnosticId: RES001
// Message: "Retry without CircuitBreaker can cause cascade failure. Add AddCircuitBreaker() to the pipeline"
```

---

## Pattern 04: Distributed Cache Stampede

### 1. Tên
**Distributed Cache Stampede** (Cache Thundering Herd / Dog-pile Effect)

### 2. Phân Loại
- **Domain:** Distributed Systems
- **Subcategory:** Caching / Concurrency

### 3. Mức Nghiêm Trọng
**HIGH** - Gây database overload đột ngột, tăng latency, có thể crash database khi cache hết hạn đồng loạt

### 4. Vấn Đề

Khi một cache entry hết hạn (hoặc bị xóa), hàng trăm request đồng thời cùng nhận được cache miss và đều cố gắng query database để rebuild cache. Database đột ngột nhận hàng trăm query phức tạp cùng lúc, gây overload.

**Cache Stampede flow:**

```
t=09:59:59.999  Cache key "popular_products" còn 1ms
                200 requests/second đang phục vụ từ cache

t=10:00:00.000  Cache EXPIRED!
                │
                ├── Req 001: cache miss → query DB...
                ├── Req 002: cache miss → query DB...
                ├── Req 003: cache miss → query DB...
                ├── ...
                └── Req 200: cache miss → query DB...

DATABASE: Nhận 200 queries phức tạp cùng lúc!
          (thay vì 0 queries/s khi cache hit)

          ┌────────────────────────────────┐
          │ CPU: 5% ────────────────► 95%  │
          │ Connections: 10 ─────────► 200 │
          │ Latency: 5ms ────────────► 30s │
          └────────────────────────────────┘
          ☠️ Database timeout / crash
```

### 5. Phát Hiện Trong Mã Nguồn

**Dấu hiệu nhận biết:**
- `GetOrSetAsync` pattern không có distributed lock
- Cache TTL đồng nhất cho tất cả keys (stampede tập thể)
- Database spike metrics trùng với cache expiry time
- Không có SemaphoreSlim hoặc distributed locking

**Regex patterns cho ripgrep:**

```bash
# Tìm GetAsync → không có lock → SetAsync pattern
rg "GetAsync.*cache.*\n.*null.*\n.*query|GetStringAsync" --type cs --multiline

# Tìm IDistributedCache không có lock
rg "IDistributedCache|IMemoryCache" --type cs -l | xargs grep -L "SemaphoreSlim\|IDistributedLock\|RedLock"

# Tìm cache TTL cố định (dễ gây synchronized expiry)
rg "AbsoluteExpirationRelativeToNow\s*=\s*TimeSpan\." --type cs
```

### 6. Giải Pháp

| Tiêu chí | BAD (no lock) | GOOD (với lock + jitter) |
|---|---|---|
| Cache miss handling | N requests → N DB queries | 1 request rebuild, rest chờ |
| TTL | Cố định (synchronized expiry) | Random jitter |
| Database load khi cache miss | Spike to N | Constant (1 query) |

**BAD - Cache miss không có lock:**

```csharp
// ❌ BAD: 100 requests cùng miss cache → 100 DB queries
public async Task<IEnumerable<Product>> GetPopularProductsAsync(CancellationToken ct)
{
    var cached = await _cache.GetStringAsync("popular_products", ct);
    if (cached != null)
        return JsonSerializer.Deserialize<IEnumerable<Product>>(cached)!;

    // 100 requests đều đến đây cùng lúc khi cache expire!
    var products = await _db.Products
        .Where(p => p.IsPopular)
        .OrderByDescending(p => p.SalesCount)
        .Take(50)
        .ToListAsync(ct);

    var options = new DistributedCacheEntryOptions
    {
        AbsoluteExpirationRelativeToNow = TimeSpan.FromMinutes(5) // Tất cả expire cùng lúc!
    };
    await _cache.SetStringAsync("popular_products", JsonSerializer.Serialize(products), options, ct);
    return products;
}
```

**GOOD - Cache với distributed lock và TTL jitter:**

```csharp
// ✅ GOOD: Chỉ 1 request rebuild cache, rest chờ kết quả

public class ProductCacheService
{
    private readonly IDistributedCache _cache;
    private readonly ApplicationDbContext _db;
    private readonly ILogger<ProductCacheService> _logger;
    private static readonly SemaphoreSlim _localLock = new(1, 1);
    private readonly Random _random = new();

    public async Task<IEnumerable<Product>> GetPopularProductsAsync(CancellationToken ct)
    {
        const string cacheKey = "popular_products";

        // 1. Thử đọc cache trước (fast path, không lock)
        var cached = await _cache.GetStringAsync(cacheKey, ct);
        if (cached != null)
            return JsonSerializer.Deserialize<IEnumerable<Product>>(cached)!;

        // 2. Cache miss — dùng local lock (cho single-instance)
        // Với multi-instance: dùng Redis distributed lock (RedLock.net)
        await _localLock.WaitAsync(ct);
        try
        {
            // 3. Double-check sau khi có lock (ai đó có thể đã rebuild)
            cached = await _cache.GetStringAsync(cacheKey, ct);
            if (cached != null)
                return JsonSerializer.Deserialize<IEnumerable<Product>>(cached)!;

            _logger.LogInformation("Cache miss for {Key}, rebuilding...", cacheKey);

            // 4. Chỉ 1 request query DB
            var products = await _db.Products
                .Where(p => p.IsPopular)
                .OrderByDescending(p => p.SalesCount)
                .Take(50)
                .AsNoTracking()
                .ToListAsync(ct);

            // 5. TTL jitter: 5 phút ± 30 giây (tránh synchronized expiry)
            var jitterSeconds = _random.Next(-30, 30);
            var ttl = TimeSpan.FromMinutes(5).Add(TimeSpan.FromSeconds(jitterSeconds));

            var options = new DistributedCacheEntryOptions
            {
                AbsoluteExpirationRelativeToNow = ttl
            };

            await _cache.SetStringAsync(
                cacheKey,
                JsonSerializer.Serialize(products),
                options,
                ct);

            return products;
        }
        finally
        {
            _localLock.Release();
        }
    }
}

// ✅ ADVANCED: Với RedLock.net cho multi-instance distributed lock
// Install: RedLock.net package
public class DistributedProductCacheService
{
    private readonly IDistributedCache _cache;
    private readonly ApplicationDbContext _db;
    private readonly IDistributedLockFactory _lockFactory; // RedLock

    public async Task<IEnumerable<Product>> GetPopularProductsAsync(CancellationToken ct)
    {
        const string cacheKey = "popular_products";
        const string lockKey = "lock:popular_products";

        var cached = await _cache.GetStringAsync(cacheKey, ct);
        if (cached != null)
            return JsonSerializer.Deserialize<IEnumerable<Product>>(cached)!;

        // Distributed lock với TTL 10 giây
        await using var redLock = await _lockFactory.CreateLockAsync(
            lockKey,
            TimeSpan.FromSeconds(10));

        if (!redLock.IsAcquired)
        {
            // Không lấy được lock → chờ một chút và đọc cache lại
            await Task.Delay(200, ct);
            var retryCache = await _cache.GetStringAsync(cacheKey, ct);
            return retryCache != null
                ? JsonSerializer.Deserialize<IEnumerable<Product>>(retryCache)!
                : [];
        }

        // Double-check sau khi có lock
        var doubleCheck = await _cache.GetStringAsync(cacheKey, ct);
        if (doubleCheck != null)
            return JsonSerializer.Deserialize<IEnumerable<Product>>(doubleCheck)!;

        var products = await _db.Products
            .Where(p => p.IsPopular)
            .Take(50)
            .AsNoTracking()
            .ToListAsync(ct);

        await _cache.SetStringAsync(cacheKey, JsonSerializer.Serialize(products),
            new DistributedCacheEntryOptions
            {
                AbsoluteExpirationRelativeToNow = TimeSpan.FromMinutes(5)
                    .Add(TimeSpan.FromSeconds(new Random().Next(-30, 30)))
            }, ct);

        return products;
    }
}
```

### 7. Phòng Ngừa

**Checklist:**
- [ ] Cache miss sử dụng lock (local SemaphoreSlim hoặc distributed RedLock)
- [ ] Double-check cache sau khi acquire lock
- [ ] TTL có jitter (±10-20% của base TTL)
- [ ] Không dùng TTL cố định giống nhau cho tất cả keys
- [ ] Monitor cache hit rate — alert khi hit rate giảm đột ngột

**Roslyn Analyzer Rules:**

```csharp
// Custom Analyzer: Phát hiện GetStringAsync → SetStringAsync không có lock
// DiagnosticId: CACHE001
// Message: "Cache get-set without lock may cause cache stampede. Use SemaphoreSlim or distributed lock"
```

---

## Pattern 05: gRPC Deadline Thiếu

### 1. Tên
**gRPC Deadline Thiếu** (Missing gRPC Deadline / Timeout)

### 2. Phân Loại
- **Domain:** Distributed Systems
- **Subcategory:** gRPC / Timeout Management

### 3. Mức Nghiêm Trọng
**CRITICAL** - Request chờ vô hạn, thread pool exhaustion, cascade failure

### 4. Vấn Đề

gRPC calls không có Deadline mặc định sẽ chờ vô hạn nếu server không trả lời. Khác với HTTP timeout, gRPC Deadline được truyền qua metadata đến server và có thể được propagate qua toàn bộ call chain. Thiếu Deadline làm toàn bộ chain bị treo.

**gRPC Deadline propagation:**

```
CLIENT          SERVICE A          SERVICE B          DATABASE
   │                │                   │                  │
   │──gRPC──────────►│                  │                  │
   │  (no deadline)  │──gRPC────────────►│                 │
   │                 │  (no deadline)    │──SQL─────────────►│
   │                 │                  │    (slow query)   │
   │                 │                  │                  ...
   │                 │                  │                  ...
   │  WAITING...     │  WAITING...      │  WAITING...      │ (60s, 120s, ...)
   │                 │                  │                  │
   [Thread blocked]  [Thread blocked]   [Thread blocked]
   ☠️ All threads exhausted across 3 services
```

### 5. Phát Hiện Trong Mã Nguồn

**Dấu hiệu nhận biết:**
- gRPC call không có `Deadline` trong `CallOptions`
- Không có `CancellationToken` propagation qua gRPC calls
- Thread pool metrics cho thấy gradual exhaustion
- gRPC health check không có timeout

**Regex patterns cho ripgrep:**

```bash
# Tìm gRPC call không có deadline
rg "\.GetAsync\(|\.PostAsync\(|AsyncUnaryCall\(" --type cs

# Tìm new CallOptions() không có deadline
rg "new CallOptions\(\)" --type cs

# Tìm gRPC client call không truyền headers/deadline
rg "client\.\w+Async\([^,)]*\)" --type cs

# Tìm gRPC channel không có deadline mặc định
rg "GrpcChannel\.ForAddress|GrpcChannel\.Create" --type cs -l | xargs grep -L "Deadline\|Timeout"
```

### 6. Giải Pháp

| Tiêu chí | BAD (no deadline) | GOOD (với deadline) |
|---|---|---|
| Slow server | Chờ vô hạn | Timeout sau N giây |
| Thread blocking | Vô hạn | Bị cancel, thread released |
| Deadline propagation | Không | Có (server biết cancel) |
| Resource cleanup | Không | Server dừng xử lý sớm |

**BAD - gRPC call không có deadline:**

```csharp
// ❌ BAD: Không có deadline — chờ vô hạn
public class InventoryService
{
    private readonly InventoryGrpc.InventoryGrpcClient _client;

    public async Task<StockLevel> GetStockAsync(int productId)
    {
        // ❌ Không có deadline, không có cancellation token
        var response = await _client.GetStockLevelAsync(new StockRequest
        {
            ProductId = productId
        });
        return new StockLevel(response.Quantity, response.Reserved);
    }
}
```

**GOOD - gRPC với deadline và CancellationToken:**

```csharp
// ✅ GOOD: gRPC với deadline đúng cách

// 1. Cấu hình gRPC channel với default deadline (Program.cs)
builder.Services.AddGrpcClient<InventoryGrpc.InventoryGrpcClient>(options =>
{
    options.Address = new Uri("https://inventory-service:5001");
})
.ConfigureChannel(options =>
{
    // Cấu hình HTTP handler với timeout cho kết nối
    options.HttpHandler = new SocketsHttpHandler
    {
        PooledConnectionIdleTimeout = Timeout.InfiniteTimeSpan,
        KeepAlivePingDelay = TimeSpan.FromSeconds(60),
        KeepAlivePingTimeout = TimeSpan.FromSeconds(30),
        EnableMultipleHttp2Connections = true
    };
})
.AddCallCredentials((context, metadata) =>
{
    // Thêm auth token
    return Task.CompletedTask;
})
.AddInterceptor<DeadlineInterceptor>(); // Global deadline interceptor

// 2. Interceptor tự động thêm deadline cho tất cả calls
public class DeadlineInterceptor : Interceptor
{
    private readonly TimeSpan _defaultDeadline = TimeSpan.FromSeconds(10);

    public override AsyncUnaryCall<TResponse> AsyncUnaryCall<TRequest, TResponse>(
        TRequest request,
        ClientInterceptorContext<TRequest, TResponse> context,
        AsyncUnaryCallContinuation<TRequest, TResponse> continuation)
    {
        // Thêm deadline nếu chưa có
        if (context.Options.Deadline == null)
        {
            var newOptions = context.Options.WithDeadline(
                DateTime.UtcNow.Add(_defaultDeadline));
            var newContext = new ClientInterceptorContext<TRequest, TResponse>(
                context.Method, context.Host, newOptions);
            return continuation(request, newContext);
        }

        return continuation(request, context);
    }
}

// 3. Sử dụng trong service với explicit deadline
public class InventoryService
{
    private readonly InventoryGrpc.InventoryGrpcClient _client;
    private readonly ILogger<InventoryService> _logger;

    public async Task<StockLevel> GetStockAsync(
        int productId,
        CancellationToken ct = default)
    {
        // Deadline = 5 giây từ bây giờ
        var deadline = DateTime.UtcNow.AddSeconds(5);

        try
        {
            var response = await _client.GetStockLevelAsync(
                new StockRequest { ProductId = productId },
                new CallOptions(
                    deadline: deadline,
                    cancellationToken: ct  // Propagate cancellation token
                ));

            return new StockLevel(response.Quantity, response.Reserved);
        }
        catch (RpcException ex) when (ex.StatusCode == StatusCode.DeadlineExceeded)
        {
            _logger.LogWarning(
                "gRPC call to inventory-service timed out after 5s for product {ProductId}",
                productId);
            throw new ServiceTimeoutException("Inventory service timeout", ex);
        }
        catch (RpcException ex) when (ex.StatusCode == StatusCode.Unavailable)
        {
            _logger.LogError(ex, "Inventory service unavailable");
            throw new ServiceUnavailableException("Inventory service unavailable", ex);
        }
    }

    // ✅ GOOD: Server-side — kiểm tra deadline trước khi làm việc nặng
    public override async Task<StockResponse> GetStockLevel(
        StockRequest request,
        ServerCallContext context)
    {
        // Server có thể kiểm tra deadline còn đủ không
        if (context.Deadline < DateTime.UtcNow.AddSeconds(1))
        {
            throw new RpcException(new Status(StatusCode.DeadlineExceeded,
                "Insufficient deadline for operation"));
        }

        // Propagate CancellationToken để dừng sớm nếu client cancel
        var ct = context.CancellationToken;

        var stock = await _db.StockLevels
            .Where(s => s.ProductId == request.ProductId)
            .FirstOrDefaultAsync(ct);  // Sẽ cancel nếu client deadline exceeded

        return new StockResponse { Quantity = stock?.Quantity ?? 0 };
    }
}
```

### 7. Phòng Ngừa

**Checklist:**
- [ ] Tất cả gRPC calls có `Deadline` trong `CallOptions`
- [ ] Dùng interceptor để tự động thêm default deadline
- [ ] `CancellationToken` được propagate qua toàn bộ call chain
- [ ] Server-side kiểm tra `context.Deadline` trước heavy operations
- [ ] Handle `StatusCode.DeadlineExceeded` riêng biệt

**Roslyn Analyzer Rules:**

```csharp
// Custom Analyzer: Phát hiện gRPC AsyncUnaryCall không có deadline
// DiagnosticId: GRPC001
// Message: "gRPC call without deadline will block indefinitely. Add Deadline to CallOptions"
```

---

## Pattern 06: SignalR Connection Leak

### 1. Tên
**SignalR Connection Leak** (SignalR Connection Resource Leak)

### 2. Phân Loại
- **Domain:** Distributed Systems
- **Subcategory:** SignalR / WebSocket / Resource Management

### 3. Mức Nghiêm Trọng
**HIGH** - Gây memory leak, server resource exhaustion, performance degradation

### 4. Vấn Đề

SignalR connections chiếm tài nguyên server (memory, file descriptors, connection state). Connection leak xảy ra khi: Hub không dọn dẹp state khi disconnect, client reconnect tạo connection mới nhưng state cũ không được xóa, hoặc groups không được cleanup.

**Connection Leak diagram:**

```
CLIENT CONNECTS/DISCONNECTS NHIỀU LẦN:

t=0:  Client A connect → ConnectionId: "abc123" → thêm vào _connections
t=5:  Client A disconnect (mạng yếu)
      → OnDisconnectedAsync() BỊ BỎ QUA → "abc123" vẫn trong _connections
t=10: Client A reconnect → ConnectionId: "def456" → thêm vào _connections
      → Bây giờ có 2 entries: "abc123" (dead) + "def456" (active)

Sau 1000 lần reconnect:
_connections = { "abc001", "abc002", ..., "abc999", "def001" }
               (999 dead connections đang chiếm memory)

Memory: 1KB/connection x 1000 = 1GB sau vài ngày
```

### 5. Phát Hiện Trong Mã Nguồn

**Dấu hiệu nhận biết:**
- Static `Dictionary` hoặc `ConcurrentDictionary` lưu ConnectionId trong Hub
- `OnDisconnectedAsync` không có cleanup logic
- Memory tăng dần theo thời gian và không giảm
- `HubContext` được inject vào singleton service

**Regex patterns cho ripgrep:**

```bash
# Tìm Hub với static dictionary (connection leak risk)
rg "static.*Dictionary|static.*ConcurrentDictionary" --type cs

# Tìm OnDisconnectedAsync không có remove/cleanup
rg "OnDisconnectedAsync" --type cs -A 10 | grep -L "Remove\|TryRemove\|unsubscribe"

# Tìm Hub không có OnDisconnectedAsync override
rg "class.*Hub" --type cs -l | xargs grep -L "OnDisconnectedAsync"

# Tìm Groups.AddToGroupAsync không có tương ứng RemoveFromGroupAsync
rg "AddToGroupAsync" --type cs -l | xargs grep -L "RemoveFromGroupAsync"
```

### 6. Giải Pháp

| Tiêu chí | BAD (memory leak) | GOOD (proper cleanup) |
|---|---|---|
| Connection tracking | Static dictionary, không cleanup | Concurrent dict với cleanup |
| OnDisconnected | Không implement / không cleanup | Full cleanup |
| Group management | Add without remove | Add + Remove on disconnect |
| State management | Per-connection static state | IHubContext + clean state |

**BAD - Hub với connection leak:**

```csharp
// ❌ BAD: Static dictionary không được cleanup
public class NotificationHub : Hub
{
    // Static → shared across requests → leak!
    private static readonly Dictionary<string, string> _userConnections = new();

    public override async Task OnConnectedAsync()
    {
        var userId = Context.User?.FindFirst("sub")?.Value;
        if (userId != null)
            _userConnections[userId] = Context.ConnectionId;  // Ghi đè, nhưng cũ vẫn còn
        await base.OnConnectedAsync();
    }

    // ❌ Không implement OnDisconnectedAsync → leak!
    // Khi client disconnect, entry vẫn tồn tại trong _userConnections

    public async Task SendToUser(string userId, string message)
    {
        if (_userConnections.TryGetValue(userId, out var connectionId))
            await Clients.Client(connectionId).SendAsync("ReceiveMessage", message);
    }
}
```

**GOOD - Hub với proper cleanup:**

```csharp
// ✅ GOOD: Proper connection lifecycle management

// 1. Service để track connections (singleton)
public interface IConnectionTracker
{
    void Add(string userId, string connectionId);
    void Remove(string userId, string connectionId);
    IReadOnlySet<string> GetConnections(string userId);
    bool HasConnections(string userId);
}

public class ConnectionTracker : IConnectionTracker
{
    // userId → Set<connectionId> (1 user có thể có nhiều connections/tabs)
    private readonly ConcurrentDictionary<string, ConcurrentHashSet<string>> _connections = new();

    public void Add(string userId, string connectionId)
    {
        _connections.GetOrAdd(userId, _ => new ConcurrentHashSet<string>())
                    .Add(connectionId);
    }

    public void Remove(string userId, string connectionId)
    {
        if (_connections.TryGetValue(userId, out var connections))
        {
            connections.Remove(connectionId);
            // Cleanup empty sets
            if (connections.IsEmpty)
                _connections.TryRemove(userId, out _);
        }
    }

    public IReadOnlySet<string> GetConnections(string userId)
    {
        return _connections.TryGetValue(userId, out var connections)
            ? connections
            : ImmutableHashSet<string>.Empty;
    }

    public bool HasConnections(string userId) =>
        _connections.ContainsKey(userId) && !_connections[userId].IsEmpty;
}

// 2. Hub với đầy đủ lifecycle
public class NotificationHub : Hub
{
    private readonly IConnectionTracker _tracker;
    private readonly ILogger<NotificationHub> _logger;

    public NotificationHub(IConnectionTracker tracker, ILogger<NotificationHub> logger)
    {
        _tracker = tracker;
        _logger = logger;
    }

    public override async Task OnConnectedAsync()
    {
        var userId = GetUserId();
        if (userId != null)
        {
            _tracker.Add(userId, Context.ConnectionId);

            // Join user-specific group để broadcast dễ hơn
            await Groups.AddToGroupAsync(Context.ConnectionId, $"user:{userId}");

            _logger.LogInformation(
                "User {UserId} connected with ConnectionId {ConnectionId}",
                userId, Context.ConnectionId);
        }

        await base.OnConnectedAsync();
    }

    public override async Task OnDisconnectedAsync(Exception? exception)
    {
        var userId = GetUserId();
        if (userId != null)
        {
            // CRITICAL: Cleanup tất cả state
            _tracker.Remove(userId, Context.ConnectionId);
            await Groups.RemoveFromGroupAsync(Context.ConnectionId, $"user:{userId}");

            _logger.LogInformation(
                "User {UserId} disconnected ConnectionId {ConnectionId}. Exception: {Ex}",
                userId, Context.ConnectionId, exception?.Message);
        }

        await base.OnDisconnectedAsync(exception);
    }

    private string? GetUserId() =>
        Context.User?.FindFirst("sub")?.Value ??
        Context.User?.FindFirst(ClaimTypes.NameIdentifier)?.Value;
}

// 3. Gửi notification qua IHubContext (không cần track connectionId)
public class NotificationService
{
    private readonly IHubContext<NotificationHub> _hubContext;
    private readonly IConnectionTracker _tracker;

    public async Task SendToUserAsync(string userId, string message, CancellationToken ct)
    {
        // Group-based broadcast — không cần track connectionId thủ công
        await _hubContext.Clients
            .Group($"user:{userId}")
            .SendAsync("ReceiveMessage", message, ct);
    }
}
```

### 7. Phòng Ngừa

**Checklist:**
- [ ] Luôn implement `OnDisconnectedAsync` với cleanup
- [ ] `OnDisconnectedAsync` cleanup phải mirror `OnConnectedAsync` setup
- [ ] Dùng Groups thay vì track ConnectionId thủ công
- [ ] Không dùng static Dictionary trong Hub
- [ ] Test reconnection scenarios
- [ ] Monitor SignalR connection count metrics

**Roslyn Analyzer Rules:**

```csharp
// Custom Analyzer: Hub có OnConnectedAsync nhưng không có OnDisconnectedAsync
// DiagnosticId: SIGNALR001
// Message: "Hub has OnConnectedAsync but missing OnDisconnectedAsync. Resource leak likely"

// Custom Analyzer: Static Dictionary/ConcurrentDictionary trong Hub class
// DiagnosticId: SIGNALR002
// Message: "Static collection in Hub can cause memory leak. Use IConnectionTracker singleton service"
```

---

## Pattern 07: Message Queue Poison Message

### 1. Tên
**Message Queue Poison Message** (Poison Message / Infinite Retry Loop)

### 2. Phân Loại
- **Domain:** Distributed Systems
- **Subcategory:** Message Queue / Error Handling

### 3. Mức Nghiêm Trọng
**HIGH** - Gây infinite retry loop, consumer bị block, queue backlog tăng, toàn bộ processing bị đình trệ

### 4. Vấn Đề

Poison message là message mà consumer không thể xử lý thành công, thường do data corruption, schema mismatch, hoặc dependency không khả dụng. Nếu không có dead letter queue (DLQ) và retry limit, message được retry vô hạn, block consumer và ngăn các message hợp lệ phía sau được xử lý.

**Poison Message flow:**

```
QUEUE:  [M1_VALID] [M2_POISON] [M3_VALID] [M4_VALID] ...

Consumer nhận M2_POISON:
  Attempt 1: ❌ Exception → Message quay lại queue (đầu hàng)
  Attempt 2: ❌ Exception → Message quay lại queue
  Attempt 3: ❌ Exception → Message quay lại queue
  ...
  Attempt ∞: ❌ Exception → Message quay lại queue (mãi mãi)

Trong khi đó:
  M3_VALID, M4_VALID... đang chờ phía sau M2_POISON
  Consumer bị chiếm 100% thời gian xử lý M2_POISON
  Queue backlog tăng dần đến hết memory

  ┌─────────────────────────────────────────────────┐
  │ Queue depth: 1 → 100 → 10,000 → 1,000,000     │
  │ Processing rate: 100msg/s → 0 msg/s             │
  │ Consumer CPU: 100% (chỉ xử lý 1 poison msg)    │
  └─────────────────────────────────────────────────┘
```

### 5. Phát Hiện Trong Mã Nguồn

**Dấu hiệu nhận biết:**
- Message handler không có retry limit / dead letter queue
- Azure Service Bus: không cấu hình `MaxDeliveryCount`
- RabbitMQ: không có `x-dead-letter-exchange`
- Kafka: không có `MaxPollIntervalMs` và error topic
- Queue depth tăng nhưng processed message count không tăng

**Regex patterns cho ripgrep:**

```bash
# Tìm Azure Service Bus không có dead letter handling
rg "ServiceBusProcessor|ServiceBusClient" --type cs -l | xargs grep -L "DeadLetter\|deadLetter"

# Tìm RabbitMQ consumer không có error handling
rg "BasicConsume|EventingBasicConsumer" --type cs -l | xargs grep -L "BasicNack\|DeadLetter\|x-dead-letter"

# Tìm message handler không có retry limit
rg "IMessageHandler\|ConsumeContext\|IConsumer" --type cs -l | xargs grep -L "DeliveryCount\|MaxDelivery\|RetryCount"

# Tìm catch-all exception không forward đến DLQ
rg "catch.*Exception" --type cs -B 5 | grep -v "DeadLetter\|Nack\|Reject"
```

### 6. Giải Pháp

| Tiêu chí | BAD (no DLQ) | GOOD (với DLQ + retry limit) |
|---|---|---|
| Poison message | Infinite retry loop | N retries → DLQ |
| Queue health | Blocked by poison | Other messages processed normally |
| Debugging | Impossible | DLQ có full message + exception info |
| Recovery | Manual restart | Requeue from DLQ khi fixed |

**BAD - Không có DLQ, retry vô hạn:**

```csharp
// ❌ BAD: Azure Service Bus không có dead letter handling
public class OrderProcessor : IHostedService
{
    private ServiceBusProcessor? _processor;

    public async Task StartAsync(CancellationToken ct)
    {
        var client = new ServiceBusClient(connectionString);
        _processor = client.CreateProcessor("orders");  // ❌ Không set MaxAutoLockRenewalDuration, MaxConcurrentCalls

        _processor.ProcessMessageAsync += async args =>
        {
            // ❌ Exception → message quay lại queue → retry vô hạn
            var order = JsonSerializer.Deserialize<Order>(args.Message.Body)!;
            await ProcessOrderAsync(order);
            await args.CompleteMessageAsync(args.Message);
        };

        _processor.ProcessErrorAsync += args =>
        {
            Console.WriteLine(args.Exception.Message);
            return Task.CompletedTask;
            // ❌ Không abandon, không dead letter
        };

        await _processor.StartProcessingAsync(ct);
    }
}
```

**GOOD - Azure Service Bus với DLQ và retry limit:**

```csharp
// ✅ GOOD: Azure Service Bus với proper error handling

// 1. Cấu hình queue khi tạo (MaxDeliveryCount = 3)
// az servicebus queue create --max-delivery-count 3 --name orders ...

// 2. Processor với đầy đủ error handling
public class OrderProcessor : IHostedService
{
    private readonly ServiceBusClient _client;
    private readonly ILogger<OrderProcessor> _logger;
    private ServiceBusProcessor? _processor;

    public async Task StartAsync(CancellationToken ct)
    {
        _processor = _client.CreateProcessor("orders", new ServiceBusProcessorOptions
        {
            MaxConcurrentCalls = 5,
            AutoCompleteMessages = false,   // Tự quản lý complete/abandon/deadletter
            MaxAutoLockRenewalDuration = TimeSpan.FromMinutes(5),
            ReceiveMode = ServiceBusReceiveMode.PeekLock
        });

        _processor.ProcessMessageAsync += HandleMessageAsync;
        _processor.ProcessErrorAsync += HandleErrorAsync;

        await _processor.StartProcessingAsync(ct);
    }

    private async Task HandleMessageAsync(ProcessMessageEventArgs args)
    {
        var message = args.Message;
        var deliveryCount = message.DeliveryCount;

        try
        {
            _logger.LogInformation(
                "Processing message {MessageId}, attempt {Attempt}",
                message.MessageId, deliveryCount);

            Order? order;
            try
            {
                order = JsonSerializer.Deserialize<Order>(message.Body);
            }
            catch (JsonException ex)
            {
                // Data corruption → dead letter ngay, không retry
                _logger.LogError(ex, "Message {MessageId} has invalid JSON, dead-lettering",
                    message.MessageId);
                await args.DeadLetterMessageAsync(
                    message,
                    deadLetterReason: "InvalidJsonFormat",
                    deadLetterErrorDescription: ex.Message);
                return;
            }

            if (order == null)
            {
                await args.DeadLetterMessageAsync(message, "NullOrder", "Deserialized to null");
                return;
            }

            await ProcessOrderAsync(order, args.CancellationToken);

            // Thành công → complete (xóa khỏi queue)
            await args.CompleteMessageAsync(message, args.CancellationToken);
        }
        catch (TransientException ex)
        {
            // Lỗi tạm thời (network, DB timeout) → abandon để retry
            _logger.LogWarning(ex,
                "Transient error for message {MessageId} (attempt {Attempt}), abandoning",
                message.MessageId, deliveryCount);

            // Khi DeliveryCount đạt MaxDeliveryCount, Service Bus tự dead-letter
            await args.AbandonMessageAsync(message,
                new Dictionary<string, object> { ["LastError"] = ex.Message });
        }
        catch (Exception ex)
        {
            // Lỗi không thể retry → dead letter ngay
            _logger.LogError(ex,
                "Unrecoverable error for message {MessageId}, dead-lettering",
                message.MessageId);

            await args.DeadLetterMessageAsync(
                message,
                deadLetterReason: ex.GetType().Name,
                deadLetterErrorDescription: ex.Message);
        }
    }

    private Task HandleErrorAsync(ProcessErrorEventArgs args)
    {
        _logger.LogError(args.Exception,
            "Service Bus error on {EntityPath}: {ErrorSource}",
            args.EntityPath, args.ErrorSource);
        return Task.CompletedTask;
    }

    public async Task StopAsync(CancellationToken ct)
    {
        if (_processor != null)
            await _processor.StopProcessingAsync(ct);
    }
}

// 3. DLQ Monitor — xử lý messages trong dead letter queue
public class DeadLetterQueueMonitor : BackgroundService
{
    private readonly ServiceBusClient _client;
    private readonly IAlertService _alertService;

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        var dlqPath = ServiceBusAdministrationClient.FormatDeadLetterPath("orders");
        var receiver = _client.CreateReceiver(dlqPath);

        while (!stoppingToken.IsCancellationRequested)
        {
            var messages = await receiver.ReceiveMessagesAsync(
                maxMessages: 10,
                maxWaitTime: TimeSpan.FromSeconds(5),
                cancellationToken: stoppingToken);

            foreach (var message in messages)
            {
                _alertService.Alert(
                    $"Dead letter: {message.DeadLetterReason} - {message.MessageId}");

                // Tùy theo reason: có thể fix và requeue, hoặc log và complete
                await receiver.CompleteMessageAsync(message, stoppingToken);
            }
        }
    }
}
```

### 7. Phòng Ngừa

**Checklist:**
- [ ] Message queue có `MaxDeliveryCount` / retry limit được cấu hình
- [ ] Dead Letter Queue được thiết lập cho mọi queue
- [ ] Phân biệt transient errors (abandon) vs permanent errors (dead-letter)
- [ ] DLQ được monitor và alert
- [ ] JSON deserialization failures được dead-letter ngay (không retry)
- [ ] DLQ có retention policy phù hợp để debug

**Roslyn Analyzer Rules:**

```csharp
// Custom Analyzer: ServiceBusProcessor không có DeadLetterMessageAsync
// DiagnosticId: MQ001
// Message: "Message handler without dead-letter handling will cause infinite retry loop"
```

---

## Pattern 08: Saga Pattern Compensation Thiếu

### 1. Tên
**Saga Pattern Compensation Thiếu** (Missing Saga Compensation in MassTransit/NServiceBus)

### 2. Phân Loại
- **Domain:** Distributed Systems
- **Subcategory:** Saga / Distributed Transaction / Data Consistency

### 3. Mức Nghiêm Trọng
**HIGH** - Gây data inconsistency, orphaned records, partial transaction state không được rollback

### 4. Vấn Đề

Saga pattern chia distributed transaction thành nhiều local transactions, mỗi bước có thể rollback bằng compensating transaction. Nếu thiếu compensation, khi step N+1 fail, các step 1..N đã commit sẽ không được rollback, dẫn đến data inconsistency.

**Saga không có compensation:**

```
ORDER SAGA: CreateOrder → ReserveInventory → ChargePayment → ConfirmOrder

  Step 1: CreateOrder     ✅ SUCCESS (Order #123 tạo)
  Step 2: ReserveInventory ✅ SUCCESS (10 items reserved)
  Step 3: ChargePayment   ❌ FAIL (card declined)

  KHÔNG CÓ COMPENSATION:
  - Order #123 vẫn tồn tại trong DB (status: PENDING mãi mãi)
  - 10 items vẫn bị reserve (inventory stuck)
  - Customer không được charge
  - System state: INCONSISTENT

  ┌──────────────────────────────────────────────┐
  │ Order: PENDING (không bao giờ complete/cancel)│
  │ Inventory: -10 items (stuck reserved)         │
  │ Payment: NOT_CHARGED                          │
  │ Customer: Confused                            │
  └──────────────────────────────────────────────┘
```

**Saga với compensation (Choreography):**

```
  Step 1: CreateOrder     ✅ → emit OrderCreated
  Step 2: ReserveInventory ✅ → emit InventoryReserved
  Step 3: ChargePayment   ❌ → emit PaymentFailed
                                    │
                      ┌─────────────┴────────────┐
                      ▼                          ▼
              ReleaseInventory            CancelOrder
              (compensation step 2)      (compensation step 1)
```

### 5. Phát Hiện Trong Mã Nguồn

**Dấu hiệu nhận biết:**
- MassTransit Saga không có `Compensate<>` handlers
- Saga state machine thiếu fault handling cho mỗi step
- `IStateMachineActivity` không có `Faulted` state
- Orphaned records tăng trong production DB

**Regex patterns cho ripgrep:**

```bash
# Tìm MassTransit Saga không có compensation
rg "MassTransitStateMachine|StateMachine" --type cs -l | xargs grep -L "Compensate\|Faulted\|compensation"

# Tìm During(state) không có Fault<> handler
rg "During\(" --type cs -A 10 | grep -v "Fault\|Compensate"

# Tìm saga activity không có compensation
rg "IStateMachineActivity" --type cs -l | xargs grep -L "Compensate"

# Tìm NServiceBus saga không có compensation
rg "ISaga\|IAmStartedByMessages" --type cs -l | xargs grep -L "Compensating\|compensation"
```

### 6. Giải Pháp

| Tiêu chí | BAD (no compensation) | GOOD (với compensation) |
|---|---|---|
| Step N+1 fail | Step 1..N committed, not rolled back | Compensation events emitted |
| Data state | Inconsistent (orphaned records) | Eventually consistent |
| Recovery | Manual DB fixes | Automatic compensation |
| Idempotency | Không | Có (compensation idempotent) |

**BAD - MassTransit Saga không có compensation:**

```csharp
// ❌ BAD: Saga không handle failures
public class OrderSaga : MassTransitStateMachine<OrderSagaState>
{
    public OrderSaga()
    {
        Initially(
            When(OrderSubmitted)
                .Then(ctx => ctx.Saga.OrderId = ctx.Message.OrderId)
                .TransitionTo(WaitingForInventory)
                .Publish(ctx => new ReserveInventoryCommand(ctx.Saga.OrderId))
        );

        During(WaitingForInventory,
            When(InventoryReserved)
                .TransitionTo(WaitingForPayment)
                .Publish(ctx => new ChargePaymentCommand(ctx.Saga.OrderId))
            // ❌ Không handle InventoryReservationFailed
        );

        During(WaitingForPayment,
            When(PaymentCharged)
                .TransitionTo(Completed)
                .Publish(ctx => new ConfirmOrderCommand(ctx.Saga.OrderId))
            // ❌ Không handle PaymentFailed → orphaned inventory reservation
        );
    }
}
```

**GOOD - MassTransit Saga với đầy đủ compensation:**

```csharp
// ✅ GOOD: Saga với compensation cho mọi failure

public class OrderSagaState : SagaStateMachineInstance
{
    public Guid CorrelationId { get; set; }
    public string CurrentState { get; set; } = null!;
    public Guid OrderId { get; set; }
    public string? FailureReason { get; set; }
    public bool InventoryReserved { get; set; }
    public bool PaymentCharged { get; set; }
}

public class OrderSaga : MassTransitStateMachine<OrderSagaState>
{
    // States
    public State WaitingForInventory { get; private set; } = null!;
    public State WaitingForPayment { get; private set; } = null!;
    public State CompensatingPayment { get; private set; } = null!;
    public State CompensatingInventory { get; private set; } = null!;
    public State Completed { get; private set; } = null!;
    public State Failed { get; private set; } = null!;

    // Events
    public Event<OrderSubmitted> OrderSubmitted { get; private set; } = null!;
    public Event<InventoryReserved> InventoryReserved { get; private set; } = null!;
    public Event<InventoryReservationFailed> InventoryFailed { get; private set; } = null!;
    public Event<PaymentCharged> PaymentCharged { get; private set; } = null!;
    public Event<PaymentFailed> PaymentFailed { get; private set; } = null!;
    public Event<PaymentRefunded> PaymentRefunded { get; private set; } = null!;
    public Event<InventoryReleased> InventoryReleased { get; private set; } = null!;

    public OrderSaga()
    {
        InstanceState(x => x.CurrentState);

        // Step 1: Start saga
        Initially(
            When(OrderSubmitted)
                .Then(ctx =>
                {
                    ctx.Saga.OrderId = ctx.Message.OrderId;
                    ctx.Saga.InventoryReserved = false;
                    ctx.Saga.PaymentCharged = false;
                })
                .TransitionTo(WaitingForInventory)
                .Publish(ctx => new ReserveInventoryCommand(ctx.Saga.OrderId))
        );

        // Step 2: Inventory reservation
        During(WaitingForInventory,
            When(InventoryReserved)
                .Then(ctx => ctx.Saga.InventoryReserved = true)
                .TransitionTo(WaitingForPayment)
                .Publish(ctx => new ChargePaymentCommand(ctx.Saga.OrderId)),

            // ✅ COMPENSATION: Inventory fail → cancel order (no prior steps to undo)
            When(InventoryFailed)
                .Then(ctx => ctx.Saga.FailureReason = ctx.Message.Reason)
                .TransitionTo(Failed)
                .Publish(ctx => new CancelOrderCommand(ctx.Saga.OrderId, ctx.Saga.FailureReason!))
        );

        // Step 3: Payment
        During(WaitingForPayment,
            When(PaymentCharged)
                .Then(ctx => ctx.Saga.PaymentCharged = true)
                .TransitionTo(Completed)
                .Publish(ctx => new ConfirmOrderCommand(ctx.Saga.OrderId)),

            // ✅ COMPENSATION: Payment fail → release inventory, then cancel order
            When(PaymentFailed)
                .Then(ctx => ctx.Saga.FailureReason = ctx.Message.Reason)
                .TransitionTo(CompensatingInventory)
                .Publish(ctx => new ReleaseInventoryCommand(ctx.Saga.OrderId))
        );

        // Compensating step: Release inventory
        During(CompensatingInventory,
            When(InventoryReleased)
                .Then(ctx => ctx.Saga.InventoryReserved = false)
                .TransitionTo(Failed)
                .Publish(ctx => new CancelOrderCommand(ctx.Saga.OrderId, ctx.Saga.FailureReason!))
        );

        SetCompletedWhenFinalized();
    }
}

// Compensation commands phải idempotent!
public class ReleaseInventoryConsumer : IConsumer<ReleaseInventoryCommand>
{
    private readonly IInventoryRepository _repo;

    public async Task Consume(ConsumeContext<ReleaseInventoryCommand> context)
    {
        var reservation = await _repo.FindReservationAsync(context.Message.OrderId);
        if (reservation == null)
        {
            // ✅ Idempotent: Không có gì để release → vẫn publish success
            await context.Publish(new InventoryReleased(context.Message.OrderId));
            return;
        }

        await _repo.ReleaseReservationAsync(reservation.Id);
        await context.Publish(new InventoryReleased(context.Message.OrderId));
    }
}
```

### 7. Phòng Ngừa

**Checklist:**
- [ ] Mỗi saga step có failure handler tương ứng
- [ ] Compensation actions là idempotent (safe to retry)
- [ ] Saga state machine có `Failed` terminal state
- [ ] Compensation events được log để audit
- [ ] Timeout handler cho từng step (phòng saga bị stuck)
- [ ] Saga state được persist (không lưu trong memory)

**Roslyn Analyzer Rules:**

```csharp
// Custom Analyzer: MassTransit During() block không có failure handler
// DiagnosticId: SAGA001
// Message: "Saga state During() block missing failure/fault handler. Add compensation logic"
```

---

## Pattern 09: Health Check Giả

### 1. Tên
**Health Check Giả** (Superficial Health Check / Always-Healthy Check)

### 2. Phân Loại
- **Domain:** Distributed Systems
- **Subcategory:** Observability / Health Monitoring

### 3. Mức Nghiêm Trọng
**MEDIUM** - Gây false confidence, load balancer gửi traffic đến instance không healthy, incidents không được phát hiện sớm

### 4. Vấn Đề

Health check trả về `Healthy` mà không thực sự kiểm tra các dependency quan trọng (database, cache, external APIs). Load balancer tin tưởng health check và tiếp tục gửi traffic đến instance đang bị degraded.

**Superficial Health Check:**

```
LOAD BALANCER          APP INSTANCE               DATABASE
      │                      │                        │
      │──── GET /health ─────►│                       │
      │                       │ return Healthy         │
      │◄─── 200 OK ───────────│  (không check DB)     │
      │                       │                       ❌ DB Down!
      │──── Route traffic ────►│                       │
      │                       │──── SQL query ─────────►│
      │                       │◄─── Connection refused──│
      │◄─── 500 Error ────────│                        │

Load balancer tiếp tục gửi traffic → 100% requests fail
```

### 5. Phát Hiện Trong Mã Nguồn

**Dấu hiệu nhận biết:**
- `AddCheck` trả về `HealthCheckResult.Healthy()` unconditionally
- Health check không có database ping
- Health check không kiểm tra Redis/cache connectivity
- `/health` endpoint luôn 200 không phụ thuộc trạng thái dependency

**Regex patterns cho ripgrep:**

```bash
# Tìm health check luôn trả về Healthy
rg "HealthCheckResult\.Healthy\(\)" --type cs -B 5 | grep -v "try\|catch\|if\|await"

# Tìm AddHealthChecks không có dependency checks
rg "AddHealthChecks" --type cs -A 3 | grep -v "AddDbContextCheck\|AddRedis\|AddUrlGroup\|AddCheck"

# Tìm health check implementation không có actual check
rg "IHealthCheck" --type cs -l | xargs grep -L "await\|TryAsync\|ping\|Connection"
```

### 6. Giải Pháp

| Tiêu chí | BAD (always healthy) | GOOD (meaningful checks) |
|---|---|---|
| Database | Không check | Ping query (SELECT 1) |
| Redis/Cache | Không check | PING command |
| External API | Không check | HEAD request đến /health |
| Kết quả | Always 200 | Phản ánh thực tế |

**BAD - Health check giả:**

```csharp
// ❌ BAD: Luôn trả về Healthy — vô nghĩa
builder.Services.AddHealthChecks()
    .AddCheck("api", () => HealthCheckResult.Healthy());  // Không check gì

// ❌ BAD: Custom check không thực sự check
public class DatabaseHealthCheck : IHealthCheck
{
    public Task<HealthCheckResult> CheckHealthAsync(
        HealthCheckContext context, CancellationToken ct)
    {
        // ❌ Không thực sự kết nối database!
        return Task.FromResult(HealthCheckResult.Healthy("Database is healthy"));
    }
}
```

**GOOD - Meaningful health checks:**

```csharp
// ✅ GOOD: Health checks thực sự kiểm tra dependencies

// Program.cs
builder.Services.AddHealthChecks()
    // Database check
    .AddDbContextCheck<ApplicationDbContext>(
        name: "database",
        failureStatus: HealthStatus.Unhealthy,
        tags: ["db", "critical"])

    // Redis check
    .AddRedis(
        builder.Configuration.GetConnectionString("Redis")!,
        name: "redis",
        failureStatus: HealthStatus.Degraded,
        tags: ["cache"])

    // External API check
    .AddUrlGroup(
        new Uri("https://payment-api.example.com/health"),
        name: "payment-api",
        failureStatus: HealthStatus.Degraded,
        timeout: TimeSpan.FromSeconds(5),
        tags: ["external"])

    // Custom check
    .AddCheck<MessageQueueHealthCheck>(
        "message-queue",
        failureStatus: HealthStatus.Unhealthy,
        tags: ["queue", "critical"]);

// Health check endpoints
app.MapHealthChecks("/health/live", new HealthCheckOptions
{
    // Liveness: chỉ check app đang chạy (không check dependencies)
    Predicate = _ => false,  // Không filter — chỉ trả về app status
    ResultStatusCodes =
    {
        [HealthStatus.Healthy] = StatusCodes.Status200OK,
        [HealthStatus.Degraded] = StatusCodes.Status200OK,  // App vẫn chạy dù degraded
        [HealthStatus.Unhealthy] = StatusCodes.Status503ServiceUnavailable
    }
});

app.MapHealthChecks("/health/ready", new HealthCheckOptions
{
    // Readiness: check tất cả dependencies, chỉ ready khi tất cả healthy/degraded
    Predicate = check => check.Tags.Contains("critical"),
    ResponseWriter = UIResponseWriter.WriteHealthCheckUIResponse
});

app.MapHealthChecks("/health/detail", new HealthCheckOptions
{
    ResponseWriter = UIResponseWriter.WriteHealthCheckUIResponse,
    // Chỉ expose cho internal monitoring, không cho public
});

// Custom health check thực sự
public class MessageQueueHealthCheck : IHealthCheck
{
    private readonly IServiceBusClient _serviceBus;

    public async Task<HealthCheckResult> CheckHealthAsync(
        HealthCheckContext context, CancellationToken ct)
    {
        try
        {
            // Thực sự check connectivity
            var properties = await _serviceBus.GetQueueRuntimePropertiesAsync(
                "orders", ct);

            var data = new Dictionary<string, object>
            {
                ["active_messages"] = properties.ActiveMessageCount,
                ["dead_letter_messages"] = properties.DeadLetterMessageCount
            };

            // Cảnh báo khi dead letter queue tăng cao
            if (properties.DeadLetterMessageCount > 100)
            {
                return HealthCheckResult.Degraded(
                    $"High dead letter count: {properties.DeadLetterMessageCount}",
                    data: data);
            }

            return HealthCheckResult.Healthy("Message queue healthy", data);
        }
        catch (Exception ex)
        {
            return HealthCheckResult.Unhealthy(
                "Cannot connect to message queue",
                exception: ex);
        }
    }
}
```

### 7. Phòng Ngừa

**Checklist:**
- [ ] Health check thực sự kết nối và query mỗi dependency
- [ ] Phân biệt liveness (`/health/live`) và readiness (`/health/ready`)
- [ ] Timeout cho mỗi check (không chờ vô hạn)
- [ ] Critical vs non-critical dependencies được phân loại
- [ ] Health check response có detail để debug

**Roslyn Analyzer Rules:**

```csharp
// Custom Analyzer: IHealthCheck.CheckHealthAsync không có await
// DiagnosticId: HEALTH001
// Message: "Health check with no await may not actually test dependencies. Ensure async I/O is performed"
```

---

## Pattern 10: Service Discovery DNS Caching

### 1. Tên
**Service Discovery DNS Caching** (Stale DNS Cache / DNS TTL Ignored)

### 2. Phân Loại
- **Domain:** Distributed Systems
- **Subcategory:** Service Discovery / DNS

### 3. Mức Nghiêm Trọng
**MEDIUM** - Gây traffic đến retired instances, rolling deploy không hoạt động đúng, sticky connections

### 4. Vấn Đề

.NET mặc định cache DNS resolution vĩnh viễn (hoặc rất lâu). Khi service discovery thay đổi IP (Kubernetes pod restart, blue-green deploy, scaling), .NET tiếp tục gửi traffic đến IP cũ cho đến khi process restart.

**DNS Stale Cache diagram:**

```
KUBERNETES DEPLOY: v1 → v2

  t=0:   api-service → 10.0.0.10 (v1 pod)
         .NET DNS cache: { "api-service": "10.0.0.10" }
         Requests: đến v1 ✅

  t=5m:  v2 pod start → 10.0.0.11
         v1 pod terminate (10.0.0.10 không còn)
         .NET DNS cache: { "api-service": "10.0.0.10" } ← STALE!

  t=5m+: .NET gửi requests đến 10.0.0.10 (đã bị terminate)
         Connection refused / timeout

  Kubernetes DNS TTL: 5-30 giây
  .NET default cache: Vô hạn (hoặc phụ thuộc OS)
```

### 5. Phát Hiện Trong Mã Nguồn

**Dấu hiệu nhận biết:**
- `SocketsHttpHandler` không set `PooledConnectionLifetime`
- `HttpClient` singleton không có connection lifetime giới hạn
- Errors tăng sau rolling deploy nhưng hết sau pod restart
- Consul/Kubernetes service mesh có thay đổi nhưng .NET không nhận

**Regex patterns cho ripgrep:**

```bash
# Tìm SocketsHttpHandler không có PooledConnectionLifetime
rg "SocketsHttpHandler" --type cs -A 10 | grep -v "PooledConnectionLifetime"

# Tìm HttpClient configuration không có lifetime
rg "AddHttpClient|ConfigurePrimaryHttpMessageHandler" --type cs -l | xargs grep -L "PooledConnectionLifetime"

# Tìm HttpClient static singleton (no DNS refresh)
rg "static.*HttpClient|static readonly.*HttpClient" --type cs
```

### 6. Giải Pháp

| Tiêu chí | BAD (no DNS refresh) | GOOD (với lifetime limit) |
|---|---|---|
| DNS cache | Vô hạn | Giới hạn (ví dụ 5 phút) |
| Rolling deploy | Connections đến old pod | Connections refresh sau TTL |
| IHttpClientFactory | Không | Có (tự quản lý lifetime) |

**BAD - DNS cache vô hạn:**

```csharp
// ❌ BAD: Static HttpClient, DNS không bao giờ refresh
private static readonly HttpClient _client = new HttpClient
{
    BaseAddress = new Uri("http://api-service")
};

// ❌ BAD: IHttpClientFactory nhưng không set PooledConnectionLifetime
builder.Services.AddHttpClient<IApiClient, ApiClient>(client =>
{
    client.BaseAddress = new Uri("http://api-service");
});
// Mặc định: connections không có lifetime limit → DNS stale
```

**GOOD - DNS refresh với PooledConnectionLifetime:**

```csharp
// ✅ GOOD: SocketsHttpHandler với PooledConnectionLifetime

builder.Services.AddHttpClient<IApiClient, ApiClient>(client =>
{
    client.BaseAddress = new Uri("http://api-service");
    client.Timeout = TimeSpan.FromSeconds(30);
})
.ConfigurePrimaryHttpMessageHandler(() => new SocketsHttpHandler
{
    // Connections được recycle sau 5 phút → DNS được re-resolve
    PooledConnectionLifetime = TimeSpan.FromMinutes(5),

    // Connections idle quá 2 phút sẽ bị đóng
    PooledConnectionIdleTimeout = TimeSpan.FromMinutes(2),

    // Keep-alive để detect dead connections nhanh hơn
    KeepAlivePingDelay = TimeSpan.FromSeconds(60),
    KeepAlivePingTimeout = TimeSpan.FromSeconds(30),
    KeepAlivePingPolicy = HttpKeepAlivePingPolicy.WithActiveRequests,

    MaxConnectionsPerServer = 50,
    EnableMultipleHttp2Connections = true
});

// ✅ ADVANCED: Với Consul service discovery
builder.Services.AddHttpClient<IApiClient, ApiClient>()
    .ConfigureHttpClient((sp, client) =>
    {
        // Consul resolve service address dynamically
        var consulClient = sp.GetRequiredService<IConsulClient>();
        // Address được resolve per-request thông qua handler
    })
    .AddHttpMessageHandler<ConsulServiceDiscoveryHandler>();

public class ConsulServiceDiscoveryHandler : DelegatingHandler
{
    private readonly IConsulClient _consul;

    protected override async Task<HttpResponseMessage> SendAsync(
        HttpRequestMessage request, CancellationToken ct)
    {
        // Re-resolve DNS per request (hoặc per N requests với cache ngắn)
        var services = await _consul.Health.Service("api-service", ct);
        var service = services.Response.First();
        request.RequestUri = new UriBuilder(request.RequestUri!)
        {
            Host = service.Service.Address,
            Port = service.Service.Port
        }.Uri;

        return await base.SendAsync(request, ct);
    }
}
```

### 7. Phòng Ngừa

**Checklist:**
- [ ] `SocketsHttpHandler.PooledConnectionLifetime` được set (khuyến nghị 2-5 phút)
- [ ] Không dùng static `HttpClient` singleton không có lifetime control
- [ ] Sau rolling deploy, monitor error rate cho DNS-related errors
- [ ] Kubernetes: cấu hình `ndots` và DNS TTL phù hợp

**Roslyn Analyzer Rules:**

```csharp
// Custom Analyzer: SocketsHttpHandler không có PooledConnectionLifetime
// DiagnosticId: DNS001
// Message: "SocketsHttpHandler without PooledConnectionLifetime causes DNS stale cache. Set PooledConnectionLifetime"

// Custom Analyzer: Static HttpClient singleton
// DiagnosticId: DNS002
// Message: "Static HttpClient singleton won't refresh DNS. Use IHttpClientFactory"
```

---

## Pattern 11: Idempotency Thiếu

### 1. Tên
**Idempotency Thiếu** (Missing Idempotency Key / Non-idempotent Operations)

### 2. Phân Loại
- **Domain:** Distributed Systems
- **Subcategory:** API Design / Data Consistency

### 3. Mức Nghiêm Trọng
**HIGH** - Gây duplicate transactions, double charges, duplicate orders khi client retry

### 4. Vấn Đề

Khi network timeout xảy ra, client không biết request có được xử lý thành công hay không và thường retry. Nếu operation không idempotent, retry tạo ra duplicate records — đặc biệt nguy hiểm với payment, order creation.

**Duplicate charge diagram:**

```
CLIENT                    PAYMENT SERVICE           BANK
  │                             │                     │
  │──── POST /charge ──────────►│                     │
  │                             │──── charge $100 ───►│
  │                             │                     │ ✅ SUCCESS
  │  ← timeout (network issue)  │◄─── charged ────────│
  │  (không nhận được response) │                     │
  │                             │                     │
  │ [Client nghĩ: request failed, retry]               │
  │                             │                     │
  │──── POST /charge ──────────►│ (same request)       │
  │                             │──── charge $100 ───►│
  │                             │                     │ ✅ SUCCESS (AGAIN!)
  │◄─── 200 OK ─────────────────│◄─── charged ────────│
  │                             │                     │
  Customer bị charge $200 thay vì $100!
```

### 5. Phát Hiện Trong Mã Nguồn

**Dấu hiệu nhận biết:**
- POST endpoints không có `Idempotency-Key` header support
- Không có unique constraint trên idempotency key trong DB
- Payment/order endpoints không có duplicate detection
- Client code có retry nhưng không gửi idempotency key

**Regex patterns cho ripgrep:**

```bash
# Tìm POST endpoint không check idempotency
rg "\[HttpPost\]" --type cs -A 10 | grep -v "Idempotency\|idempotency\|X-Idempotency\|idempotent"

# Tìm payment/charge operations không có idempotency
rg "charge|payment|CreateOrder|PlaceOrder" --type cs -i -l | xargs grep -iL "idempotency\|idempotent"

# Tìm retry logic không gửi idempotency key
rg "Retry\|retry" --type cs -l | xargs grep -L "IdempotencyKey\|idempotency-key"
```

### 6. Giải Pháp

| Tiêu chí | BAD (no idempotency) | GOOD (idempotency key) |
|---|---|---|
| Duplicate request | Duplicate record | Same result returned |
| Payment | Double charge | Charged once |
| Order | Duplicate order | Single order |
| Network retry | Data corruption | Safe |

**BAD - Không có idempotency:**

```csharp
// ❌ BAD: Không idempotent — retry gây double charge
[HttpPost("charge")]
public async Task<IActionResult> ChargeAsync([FromBody] ChargeRequest request)
{
    // ❌ Không check duplicate — mỗi request tạo transaction mới
    var result = await _paymentService.ChargeAsync(request.Amount, request.CardToken);
    return Ok(new { TransactionId = result.Id });
}
```

**GOOD - Idempotency key pattern:**

```csharp
// ✅ GOOD: Idempotent endpoint

// 1. DB: Unique constraint trên idempotency_key
// CREATE UNIQUE INDEX idx_idempotency_key ON payment_transactions(idempotency_key);

// 2. Controller với idempotency
[HttpPost("charge")]
public async Task<IActionResult> ChargeAsync(
    [FromHeader(Name = "Idempotency-Key")] string? idempotencyKey,
    [FromBody] ChargeRequest request,
    CancellationToken ct)
{
    if (string.IsNullOrWhiteSpace(idempotencyKey))
        return BadRequest("Idempotency-Key header is required");

    if (!Guid.TryParse(idempotencyKey, out var key))
        return BadRequest("Idempotency-Key must be a valid GUID");

    var result = await _paymentService.ChargeAsync(key, request, ct);

    // Trả về kết quả giống nhau cho duplicate requests
    return result.IsNew
        ? CreatedAtAction(nameof(GetTransaction), new { id = result.TransactionId }, result)
        : Ok(result); // Duplicate — trả về kết quả cũ
}

// 3. Service với idempotency check
public class PaymentService : IPaymentService
{
    private readonly ApplicationDbContext _db;
    private readonly IBankGateway _bank;

    public async Task<ChargeResult> ChargeAsync(
        Guid idempotencyKey,
        ChargeRequest request,
        CancellationToken ct)
    {
        // Check existing idempotency key
        var existing = await _db.PaymentTransactions
            .FirstOrDefaultAsync(t => t.IdempotencyKey == idempotencyKey, ct);

        if (existing != null)
        {
            // Duplicate request — return stored result
            return new ChargeResult(
                TransactionId: existing.Id,
                Amount: existing.Amount,
                Status: existing.Status,
                IsNew: false);
        }

        // New request — process and store
        var bankResult = await _bank.ChargeAsync(request.Amount, request.CardToken, ct);

        var transaction = new PaymentTransaction
        {
            IdempotencyKey = idempotencyKey,
            Amount = request.Amount,
            CardToken = request.CardToken,
            Status = bankResult.Success ? "CHARGED" : "FAILED",
            BankTransactionId = bankResult.TransactionId,
            CreatedAt = DateTime.UtcNow
        };

        try
        {
            _db.PaymentTransactions.Add(transaction);
            await _db.SaveChangesAsync(ct);
        }
        catch (DbUpdateException ex) when (IsUniqueConstraintViolation(ex))
        {
            // Race condition: another request với cùng idempotency key đã được lưu
            // Đọc lại kết quả đó
            var concurrent = await _db.PaymentTransactions
                .FirstAsync(t => t.IdempotencyKey == idempotencyKey, ct);
            return new ChargeResult(concurrent.Id, concurrent.Amount, concurrent.Status, false);
        }

        return new ChargeResult(transaction.Id, transaction.Amount, transaction.Status, true);
    }

    private static bool IsUniqueConstraintViolation(DbUpdateException ex) =>
        ex.InnerException?.Message.Contains("UNIQUE") == true ||
        ex.InnerException?.Message.Contains("duplicate key") == true;
}
```

### 7. Phòng Ngừa

**Checklist:**
- [ ] Tất cả state-changing endpoints (POST, PUT, DELETE) có `Idempotency-Key` support
- [ ] DB có unique index trên idempotency_key column
- [ ] Xử lý race condition (unique constraint violation)
- [ ] Client SDK tự động gửi `Idempotency-Key` header khi retry
- [ ] Idempotency key có expiry (xóa sau 24h-7 ngày)

**Roslyn Analyzer Rules:**

```csharp
// Custom Analyzer: HttpPost endpoint không có Idempotency-Key check
// DiagnosticId: API001
// Message: "POST endpoint without idempotency key may cause duplicate operations on retry"
```

---

## Pattern 12: Event Sourcing Snapshot Thiếu

### 1. Tên
**Event Sourcing Snapshot Thiếu** (Missing Event Sourcing Snapshots)

### 2. Phân Loại
- **Domain:** Distributed Systems
- **Subcategory:** Event Sourcing / CQRS / Performance

### 3. Mức Nghiêm Trọng
**MEDIUM** - Gây hiệu năng suy giảm nghiêm trọng khi event store tích lũy nhiều events, aggregate load thời gian tăng tuyến tính

### 4. Vấn Đề

Event Sourcing rebuild aggregate state bằng cách replay tất cả events từ đầu. Khi số events tăng lên (hàng nghìn, hàng triệu), mỗi lần load aggregate tốn O(n) thời gian — toàn bộ hệ thống bị chậm dần theo thời gian.

**Event replay không có snapshot:**

```
AGGREGATE: OrderAggregate
Event store sau 2 năm:

OrderCreated         [event #1]
OrderItemAdded       [event #2]
OrderItemAdded       [event #3]
...
OrderItemModified    [event #1,000]
OrderShipped         [event #1,001]
OrderDelivered       [event #1,002]

Load aggregate:
  t=0:   Replay 1,002 events...
  t=5s:  State ready (5 giây!)
  ↑ Không thể chấp nhận

GROWTH PATTERN:
  Year 1: 100 events/aggregate → load 100ms
  Year 2: 1,000 events/aggregate → load 1s
  Year 3: 10,000 events/aggregate → load 10s
  → Hệ thống ngày càng chậm hơn theo thời gian
```

**Với Snapshot:**

```
SNAPSHOT (event #1,000): { state lúc event #1,000 }

Load aggregate sau snapshot:
  1. Load snapshot (1 DB query)
  2. Replay chỉ events #1,001 đến #1,002 (2 events)
  Total: ~5ms thay vì 5s
```

### 5. Phát Hiện Trong Mã Nguồn

**Dấu hiệu nhận biết:**
- Event sourcing không có snapshot table hoặc snapshot logic
- Load time tăng tuyến tính theo số events
- `ReadAllEvents` / `GetEventsAsync` luôn đọc từ version 0
- Không có `SnapshotInterval` configuration

**Regex patterns cho ripgrep:**

```bash
# Tìm event sourcing không có snapshot
rg "IEventStore\|EventStore\|AggregateRoot" --type cs -l | xargs grep -L "Snapshot\|snapshot"

# Tìm ReadEvents từ version 0 luôn (không check snapshot)
rg "ReadEventsAsync\|GetEvents" --type cs -A 5 | grep "version\s*=\s*0\|fromVersion:\s*0"

# Tìm aggregate load không có snapshot check
rg "LoadAsync\|HydrateAsync\|ReplayEvents" --type cs -l | xargs grep -L "snapshot"
```

### 6. Giải Pháp

| Tiêu chí | BAD (no snapshot) | GOOD (với snapshot) |
|---|---|---|
| Event replay | Tất cả events từ đầu | Từ snapshot + ít events |
| Load time | O(n) theo số events | O(1) + O(k) với k nhỏ |
| Storage | Chỉ event store | Event store + snapshot store |
| Snapshot creation | Không | Mỗi N events |

**BAD - Event sourcing không có snapshot:**

```csharp
// ❌ BAD: Luôn replay tất cả events từ đầu
public class OrderRepository
{
    private readonly IEventStore _eventStore;

    public async Task<Order> LoadAsync(Guid orderId, CancellationToken ct)
    {
        // ❌ Luôn đọc tất cả events từ version 0
        var events = await _eventStore.ReadEventsAsync(orderId, fromVersion: 0, ct);

        var order = new Order();
        foreach (var @event in events)
            order.Apply(@event);  // 10,000 events → 10,000 Apply calls

        return order;
    }
}
```

**GOOD - Event sourcing với snapshot:**

```csharp
// ✅ GOOD: Snapshot pattern

// 1. Snapshot model
public record AggregateSnapshot(
    Guid AggregateId,
    long Version,
    string AggregateType,
    string StateJson,
    DateTime CreatedAt
);

// 2. Repository với snapshot support
public class OrderRepository
{
    private readonly IEventStore _eventStore;
    private readonly ISnapshotStore _snapshotStore;
    private const int SnapshotInterval = 100; // Tạo snapshot mỗi 100 events

    public async Task<Order> LoadAsync(Guid orderId, CancellationToken ct)
    {
        // 1. Thử load snapshot gần nhất
        var snapshot = await _snapshotStore.GetLatestAsync(orderId, ct);

        Order order;
        long fromVersion;

        if (snapshot != null)
        {
            // Restore từ snapshot
            order = JsonSerializer.Deserialize<Order>(snapshot.StateJson)!;
            fromVersion = snapshot.Version + 1;  // Chỉ cần events sau snapshot
        }
        else
        {
            order = new Order();
            fromVersion = 0;
        }

        // 2. Replay chỉ events sau snapshot
        var events = await _eventStore.ReadEventsAsync(orderId, fromVersion, ct);
        foreach (var @event in events)
            order.Apply(@event);

        return order;
    }

    public async Task SaveAsync(Order order, CancellationToken ct)
    {
        var uncommittedEvents = order.GetUncommittedEvents();
        await _eventStore.AppendEventsAsync(order.Id, uncommittedEvents, ct);
        order.ClearUncommittedEvents();

        // Tạo snapshot nếu đến SnapshotInterval
        if (order.Version % SnapshotInterval == 0)
        {
            var snapshot = new AggregateSnapshot(
                AggregateId: order.Id,
                Version: order.Version,
                AggregateType: nameof(Order),
                StateJson: JsonSerializer.Serialize(order),
                CreatedAt: DateTime.UtcNow
            );
            await _snapshotStore.SaveAsync(snapshot, ct);
        }
    }
}

// 3. Snapshot store implementation
public class SnapshotStore : ISnapshotStore
{
    private readonly ApplicationDbContext _db;

    public async Task<AggregateSnapshot?> GetLatestAsync(Guid aggregateId, CancellationToken ct)
    {
        return await _db.AggregateSnapshots
            .Where(s => s.AggregateId == aggregateId)
            .OrderByDescending(s => s.Version)
            .FirstOrDefaultAsync(ct);
    }

    public async Task SaveAsync(AggregateSnapshot snapshot, CancellationToken ct)
    {
        // Upsert snapshot — chỉ giữ snapshot mới nhất (hoặc N snapshots)
        var existing = await _db.AggregateSnapshots
            .FirstOrDefaultAsync(s =>
                s.AggregateId == snapshot.AggregateId &&
                s.Version == snapshot.Version, ct);

        if (existing == null)
            _db.AggregateSnapshots.Add(snapshot);

        await _db.SaveChangesAsync(ct);

        // Cleanup old snapshots (giữ 3 snapshots gần nhất)
        var oldSnapshots = await _db.AggregateSnapshots
            .Where(s => s.AggregateId == snapshot.AggregateId)
            .OrderByDescending(s => s.Version)
            .Skip(3)
            .ToListAsync(ct);

        if (oldSnapshots.Any())
        {
            _db.AggregateSnapshots.RemoveRange(oldSnapshots);
            await _db.SaveChangesAsync(ct);
        }
    }
}

// 4. Background job để tạo snapshots cho aggregates cũ
public class SnapshotMaintenanceJob : BackgroundService
{
    private readonly OrderRepository _repo;
    private readonly IEventStore _eventStore;

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        while (!stoppingToken.IsCancellationRequested)
        {
            // Tìm aggregates có nhiều events sau snapshot cuối
            var candidates = await _eventStore.GetAggregatesNeedingSnapshot(
                minEventsSinceSnapshot: 100,
                stoppingToken);

            foreach (var aggregateId in candidates)
            {
                var order = await _repo.LoadAsync(aggregateId, stoppingToken);
                await _repo.SaveAsync(order, stoppingToken);  // Save trigger snapshot creation
            }

            await Task.Delay(TimeSpan.FromHours(1), stoppingToken);
        }
    }
}
```

### 7. Phòng Ngừa

**Checklist:**
- [ ] Snapshot table/collection được thiết kế từ đầu
- [ ] `SnapshotInterval` được cấu hình (khuyến nghị 50-200 events)
- [ ] Load logic: check snapshot trước, replay từ snapshot version
- [ ] Background job tạo snapshot cho aggregates cũ
- [ ] Monitor: load time per aggregate theo thời gian
- [ ] Snapshot store cleanup (không giữ snapshot vô hạn)

**Roslyn Analyzer Rules:**

```csharp
// Custom Analyzer: ReadEventsAsync với fromVersion: 0 trong LoadAsync
// DiagnosticId: ES001
// Message: "Always replaying from version 0 without snapshot check will degrade performance over time"

// Custom Analyzer: Event sourcing repository không có snapshot reference
// DiagnosticId: ES002
// Message: "Event sourcing repository should implement snapshots for aggregates with many events"
```

---

## Tóm Tắt Domain 02

| # | Pattern | Mức độ | Tác động chính |
|---|---------|--------|----------------|
| 01 | HttpClient Misuse | CRITICAL | Socket/port exhaustion |
| 02 | Retry Storm | CRITICAL | Cascade failure khi retry |
| 03 | Circuit Breaker Thiếu | HIGH | Thread pool exhaustion |
| 04 | Distributed Cache Stampede | HIGH | Database overload khi cache expire |
| 05 | gRPC Deadline Thiếu | CRITICAL | Request chờ vô hạn |
| 06 | SignalR Connection Leak | HIGH | Memory leak, resource exhaustion |
| 07 | Message Queue Poison Message | HIGH | Queue blocked, processing dừng |
| 08 | Saga Compensation Thiếu | HIGH | Data inconsistency |
| 09 | Health Check Giả | MEDIUM | False confidence, incidents không phát hiện |
| 10 | Service Discovery DNS Caching | MEDIUM | Stale connections sau deploy |
| 11 | Idempotency Thiếu | HIGH | Duplicate transactions, double charge |
| 12 | Event Sourcing Snapshot Thiếu | MEDIUM | Performance O(n) theo events |

### Quick Diagnostic Commands

```bash
# Check HttpClient misuse
rg "new HttpClient\(\)" --type cs

# Check Retry without Circuit Breaker
rg "AddRetry\|WaitAndRetryAsync" --type cs

# Check gRPC without deadline
rg "GrpcClient\|AsyncUnaryCall" --type cs

# Check SignalR connection leak
rg "class.*Hub" --type cs -l | xargs grep -L "OnDisconnectedAsync"

# Check missing DLQ
rg "ServiceBusProcessor\|BasicConsume" --type cs -l | xargs grep -L "DeadLetter\|BasicNack"

# Check missing idempotency
rg "\[HttpPost\]" --type cs -l | xargs grep -L "Idempotency"
```
