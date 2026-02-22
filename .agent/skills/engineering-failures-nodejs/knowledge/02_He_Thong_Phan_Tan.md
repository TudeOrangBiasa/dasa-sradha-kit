# Domain 02: Hệ Thống Phân Tán (Distributed Systems)

| Trường thông tin | Giá trị |
|-----------------|---------|
| **Tên miền** | Hệ Thống Phân Tán (Distributed Systems) |
| **Lĩnh vực** | Node.js / Distributed Architecture |
| **Số lượng pattern** | 12 |
| **Ngôn ngữ** | TypeScript |
| **Cập nhật** | 2026-02-18 |

---

## Tổng quan Hệ Thống Phân Tán

```
┌────────────────────────────────────────────────────────────────────┐
│                  DISTRIBUTED SYSTEM FAILURE MAP                    │
│                                                                    │
│   Client ──▶ [ Load Balancer ] ──▶ [ Service A ] ──▶ [ Cache ]   │
│                     │                    │               │         │
│                     │                    ▼               ▼         │
│                     │             [ Service B ] ──▶ [ DB Master ] │
│                     │                    │               │         │
│                     │                    ▼               ▼         │
│                     └──────────▶  [ Message Queue ] [ DB Replica]  │
│                                         │                          │
│                                         ▼                          │
│                                  [ Worker Pool ]                   │
│                                                                    │
│  Failure Zones:                                                    │
│  [1] Cache Stampede  [4] Lock Race    [7] Missing Ack             │
│  [2] Retry Storm     [5] Idempotency  [8] Pub/Sub Loss            │
│  [3] No Circuit Brkr [6] WS Reconnect [9] Rate Limit             │
│  [10] Sticky Session [11] Timeout Chain [12] Event Order          │
└────────────────────────────────────────────────────────────────────┘
```

---

## Pattern 01: Bầy Đàn Ồ Ạt (Thundering Herd / Cache Stampede)

### 1. Tên
**Bầy Đàn Ồ Ạt** (Thundering Herd / Cache Stampede)

### 2. Phân loại
- **Domain:** Distributed Systems / Caching
- **Subcategory:** Cache Invalidation, Race Condition

### 3. Mức nghiêm trọng
🟠 **HIGH** - Gây quá tải database đột ngột, có thể dẫn đến cascading failure

### 4. Vấn đề

Khi một cache key hết hạn, hàng nghìn request đồng thời đổ vào database để tái tạo cùng một giá trị. Mỗi request thấy cache miss, tất cả cùng query DB, kết quả là DB bị quá tải.

**Ví dụ thực tế:** Flash sale bắt đầu, cache product list hết hạn, 10.000 user cùng lúc request, 10.000 query đến DB.

```
CACHE STAMPEDE:

t=0: Cache key "hot_products" hết hạn
     │
     ├── Request 1 ──▶ Cache MISS ──▶ DB Query ─────▶ (xử lý 500ms)
     ├── Request 2 ──▶ Cache MISS ──▶ DB Query ─────▶ (xử lý 500ms)
     ├── Request 3 ──▶ Cache MISS ──▶ DB Query ─────▶ (xử lý 500ms)
     ├── ...          ...              ...
     └── Request N ──▶ Cache MISS ──▶ DB Query ─────▶ DB OVERLOAD!

GIẢI PHÁP (Mutex / Probabilistic Early Expiry):

t=0: Cache key sắp hết hạn
     │
     ├── Request 1 ──▶ Cache MISS ──▶ Acquire Lock ──▶ DB Query ──▶ Set Cache
     ├── Request 2 ──▶ Cache MISS ──▶ Wait Lock ──────▶ Cache HIT (stale data)
     ├── Request 3 ──▶ Cache MISS ──▶ Wait Lock ──────▶ Cache HIT (fresh data)
     └── Request N ──▶ Cache HIT  ──▶ Return immediately
```

### 5. Phát hiện trong mã nguồn

**Dấu hiệu nhận biết:**
- `cache.get()` không có lock/mutex protection trước khi gọi DB
- TTL cố định không có jitter (mọi key hết hạn cùng lúc)
- Không có stale-while-revalidate pattern
- Cache.get + DB query + Cache.set mà không dùng lock

**Regex patterns (ripgrep):**
```bash
# Tìm cache get không có lock protection
rg "cache\.get|redis\.get" --type ts -A 3 | grep -v "lock\|mutex\|setnx"

# Tìm TTL cố định (không có jitter)
rg "EX\s+\d+|expire\s*\(\s*\d+|ttl:\s*\d+" --type ts

# Tìm pattern cache miss -> DB query không có lock
rg "if\s*\(!cached\|if\s*\(result\s*===\s*null" --type ts -A 5

# Tìm Redis SETNX patterns (đã dùng lock)
rg "setnx|set.*NX|redlock|Redlock" --type ts
```

### 6. Giải pháp

| Tiêu chí | Cách sai | Cách đúng |
|---------|----------|-----------|
| Cache miss | Tất cả query DB cùng lúc | Dùng Redis SETNX lock |
| TTL | Cố định (stampede cùng lúc) | TTL + random jitter |
| Stale data | Reject request | Serve stale, revalidate async |
| Lock timeout | Không có | Có timeout + fallback |

```typescript
import { Redis } from 'ioredis'

const redis = new Redis()

// ❌ SAI: Không có lock, thundering herd xảy ra
async function getHotProductsBad(): Promise<Product[]> {
  const cached = await redis.get('hot_products')
  if (cached) return JSON.parse(cached)

  // Hàng nghìn request đồng thời đến đây!
  const products = await db.query('SELECT * FROM products WHERE hot = true')
  await redis.set('hot_products', JSON.stringify(products), 'EX', 300)
  return products
}

// ✅ ĐÚNG: Dùng mutex lock + stale-while-revalidate
const LOCK_TTL = 5 // seconds
const CACHE_TTL = 300 // seconds
const JITTER_MAX = 30 // seconds

function getTTLWithJitter(base: number): number {
  return base + Math.floor(Math.random() * JITTER_MAX)
}

async function getHotProductsGood(): Promise<Product[]> {
  const cacheKey = 'hot_products'
  const lockKey = `lock:${cacheKey}`

  // 1. Thử đọc cache trước
  const cached = await redis.get(cacheKey)
  if (cached) return JSON.parse(cached)

  // 2. Thử acquire lock (Redis SETNX)
  const lockAcquired = await redis.set(lockKey, '1', 'EX', LOCK_TTL, 'NX')

  if (!lockAcquired) {
    // 3a. Không có lock → chờ và retry (hoặc trả stale data)
    await new Promise(resolve => setTimeout(resolve, 100))
    const retryCache = await redis.get(cacheKey)
    if (retryCache) return JSON.parse(retryCache)
    // Fallback: trả empty hoặc stale data từ secondary cache
    return []
  }

  try {
    // 3b. Có lock → query DB và set cache
    const products = await db.query('SELECT * FROM products WHERE hot = true')
    const ttl = getTTLWithJitter(CACHE_TTL)
    await redis.set(cacheKey, JSON.stringify(products), 'EX', ttl)
    return products
  } finally {
    // 4. Luôn release lock
    await redis.del(lockKey)
  }
}

// ✅ NÂNG CAO: Probabilistic Early Expiry (PER)
// Tái tạo cache trước khi hết hạn, dựa trên xác suất
async function getWithPER<T>(
  key: string,
  fetcher: () => Promise<T>,
  ttl: number,
  beta: number = 1
): Promise<T> {
  const raw = await redis.get(key)

  if (raw) {
    const { value, expiry } = JSON.parse(raw) as { value: T; expiry: number }
    const remainingTTL = expiry - Date.now() / 1000
    const delta = -Math.log(Math.random()) * beta

    // Tái tạo sớm nếu xác suất đủ cao
    if (delta < remainingTTL) {
      return value
    }
  }

  // Cache miss hoặc cần tái tạo
  const value = await fetcher()
  const expiry = Date.now() / 1000 + ttl
  await redis.set(key, JSON.stringify({ value, expiry }), 'EX', ttl + 1)
  return value
}
```

### 7. Phòng ngừa

- [ ] Luôn dùng distributed lock (Redis SETNX / Redlock) cho cache miss handler
- [ ] Thêm random jitter vào TTL để tránh mass expiry cùng lúc
- [ ] Implement stale-while-revalidate: serve data cũ trong khi tái tạo
- [ ] Monitor cache hit rate; alert khi hit rate giảm đột ngột
- [ ] Dùng background job để warm up cache trước khi hết hạn

```javascript
// ESLint rule gợi ý (custom rule)
// Cảnh báo khi dùng redis.get mà không có lock pattern trong cùng function
// Có thể dùng eslint-plugin-custom hoặc comment lint
// eslint-disable-next-line no-cache-without-lock
```

---

## Pattern 02: Retry Storm

### 1. Tên
**Bão Thử Lại** (Retry Storm)

### 2. Phân loại
- **Domain:** Distributed Systems / Resilience
- **Subcategory:** Retry Logic, Cascading Failure

### 3. Mức nghiêm trọng
🔴 **CRITICAL** - Khuếch đại lưu lượng lên hàng nghìn lần, làm sụp đổ service đang recover

### 4. Vấn đề

Khi một service chậm hoặc lỗi, tất cả client retry ngay lập tức và đồng bộ. Lưu lượng nhân lên `N_clients × max_retries` lần đúng lúc service đang cố recover, khiến nó không bao giờ recover được.

**Ví dụ thực tế:** Payment service bị slow 2 giây, 1000 client retry 3 lần → 3000 request đổ vào, service càng chậm hơn, client retry thêm → vòng lặp vô tận.

```
RETRY STORM:

t=0: Payment service slow (latency 2s)
     │
     ├── 1000 clients gửi request
     │        │
     │        ▼ timeout sau 1s
     │   1000 clients RETRY immediately
     │        │
     │        ▼ (1000 + 1000 = 2000 concurrent requests)
     │   Service càng chậm hơn
     │        │
     │        ▼ timeout sau 1s
     │   2000 clients RETRY immediately
     │        │
     │        ▼ (2000 + 2000 = 4000 concurrent requests)
     │   SERVICE CRASH!
     │
     └── Không bao giờ recover được!

EXPONENTIAL BACKOFF + JITTER:

     Client 1: retry sau 1s, 2s, 4s, 8s (+ random 0-1s)
     Client 2: retry sau 1.3s, 2.7s, 5.1s (distributed)
     Client 3: retry sau 0.8s, 1.9s, 4.3s (staggered)
     ─────────────────────────────────────────────────▶
     Service load giảm dần, có thời gian recover
```

### 5. Phát hiện trong mã nguồn

**Dấu hiệu nhận biết:**
- Retry loop với `delay` cố định (hoặc không có delay)
- `for` / `while` retry không có exponential backoff
- Axios/fetch retry config không có jitter
- `retryDelay: 1000` (cố định) thay vì hàm tính toán

**Regex patterns (ripgrep):**
```bash
# Tìm retry với delay cố định
rg "retryDelay:\s*\d+|retry.*delay.*\d+" --type ts

# Tìm retry loop không có backoff
rg "for.*retry|while.*retry|attempt.*retry" --type ts -A 5 | grep -v "backoff\|exponential"

# Tìm setTimeout cố định trong retry context
rg "setTimeout.*retry|retry.*setTimeout" --type ts -B 2 -A 2

# Tìm axios-retry hoặc p-retry config
rg "retries:\s*\d|axios-retry|p-retry" --type ts
```

### 6. Giải pháp

| Tiêu chí | Cách sai | Cách đúng |
|---------|----------|-----------|
| Delay | Cố định (1s) | Exponential (1s, 2s, 4s, 8s) |
| Jitter | Không có | Full jitter hoặc decorrelated |
| Max retries | Vô hạn | 3-5 lần tối đa |
| Retry điều kiện | Tất cả lỗi | Chỉ lỗi transient (5xx, network) |
| Max delay | Không giới hạn | Cap tại 30-60s |

```typescript
// ❌ SAI: Retry ngay lập tức, không có backoff, không có jitter
async function callPaymentServiceBad(payload: PaymentPayload): Promise<void> {
  const MAX_RETRIES = 5
  for (let attempt = 0; attempt < MAX_RETRIES; attempt++) {
    try {
      await axios.post('/payment', payload)
      return
    } catch (err) {
      if (attempt < MAX_RETRIES - 1) {
        await new Promise(resolve => setTimeout(resolve, 1000)) // Fixed 1s!
      }
    }
  }
  throw new Error('Payment failed after retries')
}

// ✅ ĐÚNG: Exponential backoff với full jitter
interface RetryConfig {
  maxRetries: number
  baseDelayMs: number
  maxDelayMs: number
  retryableStatuses: number[]
}

function calculateBackoffDelay(attempt: number, config: RetryConfig): number {
  // Exponential backoff: baseDelay * 2^attempt
  const exponential = config.baseDelayMs * Math.pow(2, attempt)
  // Cap tại maxDelay
  const capped = Math.min(exponential, config.maxDelayMs)
  // Full jitter: random trong [0, capped]
  return Math.random() * capped
}

function isRetryableError(error: unknown): boolean {
  if (axios.isAxiosError(error)) {
    const status = error.response?.status
    // Retry 5xx (server errors) và network errors, không retry 4xx (client errors)
    return !status || status >= 500
  }
  return true // Network error → retry
}

async function callPaymentServiceGood(payload: PaymentPayload): Promise<PaymentResult> {
  const config: RetryConfig = {
    maxRetries: 3,
    baseDelayMs: 500,
    maxDelayMs: 30_000,
    retryableStatuses: [500, 502, 503, 504]
  }

  let lastError: unknown

  for (let attempt = 0; attempt <= config.maxRetries; attempt++) {
    try {
      const response = await axios.post<PaymentResult>('/payment', payload, {
        timeout: 5000
      })
      return response.data
    } catch (err) {
      lastError = err

      if (!isRetryableError(err) || attempt === config.maxRetries) {
        break
      }

      const delay = calculateBackoffDelay(attempt, config)
      console.warn(`Payment attempt ${attempt + 1} failed, retrying in ${delay.toFixed(0)}ms`)
      await new Promise(resolve => setTimeout(resolve, delay))
    }
  }

  throw new Error(`Payment failed after ${config.maxRetries} retries: ${lastError}`)
}

// ✅ NÂNG CAO: Dùng p-retry library với decorrelated jitter
import pRetry from 'p-retry'

async function callPaymentServiceAdvanced(payload: PaymentPayload): Promise<PaymentResult> {
  return pRetry(
    async (attempt) => {
      const response = await axios.post<PaymentResult>('/payment', payload)
      return response.data
    },
    {
      retries: 3,
      factor: 2,
      minTimeout: 500,
      maxTimeout: 30_000,
      randomize: true, // Adds jitter automatically
      onFailedAttempt: (error) => {
        console.warn(`Attempt ${error.attemptNumber} failed. Retries left: ${error.retriesLeft}`)
      }
    }
  )
}
```

### 7. Phòng ngừa

- [ ] Luôn dùng exponential backoff, KHÔNG dùng fixed delay
- [ ] Thêm jitter (random) vào delay để tránh synchronized retries
- [ ] Giới hạn max retries (3-5) và max delay (30-60s)
- [ ] Chỉ retry lỗi transient (5xx, timeout), không retry 4xx
- [ ] Kết hợp với Circuit Breaker để dừng retry khi service down hoàn toàn
- [ ] Monitor retry rate; alert khi retry rate > threshold

```javascript
// ESLint: cảnh báo khi dùng setTimeout với giá trị cố định trong retry context
// eslint-disable-next-line no-fixed-retry-delay
```

---

## Pattern 03: Circuit Breaker Thiếu

### 1. Tên
**Thiếu Cầu Dao Ngắt Mạch** (Missing Circuit Breaker)

### 2. Phân loại
- **Domain:** Distributed Systems / Resilience
- **Subcategory:** Fault Tolerance, Cascading Failure Prevention

### 3. Mức nghiêm trọng
🟠 **HIGH** - Lỗi một service lan rộng sang toàn bộ hệ thống, gây cascading failure

### 4. Vấn đề

Khi service phụ thuộc (downstream) bị lỗi, service gọi nó vẫn tiếp tục chờ timeout trên mỗi request. Điều này tiêu thụ thread/connection pool và làm nghẽn toàn bộ service, dù downstream đã down hoàn toàn.

**Ví dụ thực tế:** SMS service down, mọi API request vẫn chờ 30s timeout trước khi trả lỗi. 100 concurrent request × 30s = connection pool cạn kiệt.

```
KHÔNG CÓ CIRCUIT BREAKER:

Service A ──▶ SMS Service (DOWN)
     │              │
     ├── Req 1 ──▶ timeout 30s ──▶ Error (30s wasted)
     ├── Req 2 ──▶ timeout 30s ──▶ Error (30s wasted)
     ├── Req 3 ──▶ timeout 30s ──▶ Error (30s wasted)
     └── ... (connection pool exhausted, Service A also fails)

CÓ CIRCUIT BREAKER (States: CLOSED → OPEN → HALF-OPEN):

CLOSED (bình thường):   req ──▶ SMS ──▶ response
  error rate > 50% ──▶ OPEN

OPEN (đã ngắt):         req ──▶ [CIRCUIT OPEN] ──▶ fail fast (0ms!)
  sau 30s ──▶ HALF-OPEN

HALF-OPEN (thử lại):    1 req ──▶ SMS
  success ──▶ CLOSED
  failure ──▶ OPEN
```

### 5. Phát hiện trong mã nguồn

**Dấu hiệu nhận biết:**
- HTTP calls đến external service không có circuit breaker wrapper
- Timeout dài (>10s) mà không có fallback
- Không có `opossum`, `cockatiel`, hoặc custom circuit breaker
- Không có health check / readiness probe cho dependencies

**Regex patterns (ripgrep):**
```bash
# Tìm HTTP calls không có circuit breaker
rg "axios\.(get|post|put|delete)|fetch\(" --type ts | grep -v "circuit\|breaker\|opossum"

# Tìm timeout dài không có fallback
rg "timeout:\s*[0-9]{5,}" --type ts

# Tìm opossum/circuit breaker đã được dùng
rg "opossum|CircuitBreaker|cockatiel|circuit" --type ts

# Tìm external service calls
rg "https?://|baseURL:" --type ts -A 2
```

### 6. Giải pháp

| Tiêu chí | Cách sai | Cách đúng |
|---------|----------|-----------|
| External call | Trực tiếp, không có bảo vệ | Wrap bằng Circuit Breaker |
| Failure detection | Chờ từng timeout | Đếm lỗi, mở circuit |
| Recovery | Manual | Tự động sau cooldown |
| Fallback | Không có | Có fallback response |

```typescript
import CircuitBreaker from 'opossum'

// ❌ SAI: Gọi trực tiếp không có circuit breaker
async function sendSmsBad(to: string, message: string): Promise<void> {
  // Nếu SMS service down, mỗi call chờ 30s!
  await axios.post('https://sms-provider.com/send', { to, message }, {
    timeout: 30_000
  })
}

// ✅ ĐÚNG: Wrap bằng Circuit Breaker (opossum)
async function sendSmsCore(to: string, message: string): Promise<void> {
  await axios.post('https://sms-provider.com/send', { to, message }, {
    timeout: 3_000 // Timeout ngắn hơn
  })
}

const smsBreaker = new CircuitBreaker(sendSmsCore, {
  timeout: 3000,           // Fail nếu > 3s
  errorThresholdPercentage: 50, // Mở circuit nếu 50% lỗi
  resetTimeout: 30_000,    // Thử lại sau 30s
  volumeThreshold: 5       // Cần ít nhất 5 request để đánh giá
})

// Fallback khi circuit mở
smsBreaker.fallback(async (to: string, message: string) => {
  console.warn(`Circuit OPEN: SMS queued for later delivery to ${to}`)
  await smsQueue.add({ to, message, retryAt: Date.now() + 60_000 })
})

// Monitor circuit state
smsBreaker.on('open', () => console.error('SMS Circuit OPENED - service degraded'))
smsBreaker.on('halfOpen', () => console.info('SMS Circuit HALF-OPEN - testing recovery'))
smsBreaker.on('close', () => console.info('SMS Circuit CLOSED - service recovered'))

async function sendSmsGood(to: string, message: string): Promise<void> {
  await smsBreaker.fire(to, message)
}

// ✅ NÂNG CAO: Circuit Breaker tự triển khai với metrics
type CircuitState = 'CLOSED' | 'OPEN' | 'HALF_OPEN'

class SimpleCircuitBreaker {
  private state: CircuitState = 'CLOSED'
  private failureCount = 0
  private lastFailureTime = 0
  private successCount = 0

  constructor(
    private readonly fn: (...args: unknown[]) => Promise<unknown>,
    private readonly options: {
      failureThreshold: number
      resetTimeout: number
      successThreshold: number
    }
  ) {}

  async fire(...args: unknown[]): Promise<unknown> {
    if (this.state === 'OPEN') {
      if (Date.now() - this.lastFailureTime > this.options.resetTimeout) {
        this.state = 'HALF_OPEN'
        this.successCount = 0
      } else {
        throw new Error('Circuit breaker is OPEN')
      }
    }

    try {
      const result = await this.fn(...args)
      this.onSuccess()
      return result
    } catch (err) {
      this.onFailure()
      throw err
    }
  }

  private onSuccess(): void {
    this.failureCount = 0
    if (this.state === 'HALF_OPEN') {
      this.successCount++
      if (this.successCount >= this.options.successThreshold) {
        this.state = 'CLOSED'
      }
    }
  }

  private onFailure(): void {
    this.failureCount++
    this.lastFailureTime = Date.now()
    if (this.failureCount >= this.options.failureThreshold) {
      this.state = 'OPEN'
    }
  }

  getState(): CircuitState {
    return this.state
  }
}
```

### 7. Phòng ngừa

- [ ] Wrap tất cả external service calls bằng Circuit Breaker
- [ ] Cấu hình timeout ngắn (3-5s) cho mỗi external call
- [ ] Implement fallback logic (queue, cache, default response)
- [ ] Monitor circuit state và alert khi circuit mở
- [ ] Test circuit breaker bằng chaos engineering (kill downstream service)
- [ ] Document dependency health checks trong runbook

```javascript
// eslint rule gợi ý: warn khi axios/fetch không được wrap trong known CB pattern
// "no-unprotected-external-call": "warn"
```

---

## Pattern 04: Distributed Lock Sai (Incorrect Redis Lock)

### 1. Tên
**Khóa Phân Tán Sai** (Incorrect Distributed Lock / Redis SETNX Misuse)

### 2. Phân loại
- **Domain:** Distributed Systems / Concurrency
- **Subcategory:** Race Condition, Distributed Locking

### 3. Mức nghiêm trọng
🔴 **CRITICAL** - Race condition dẫn đến duplicate processing, data corruption, hoặc double payment

### 4. Vấn đề

Sử dụng `SETNX` + `EXPIRE` riêng lẻ (không atomic) tạo ra window race condition: nếu process crash giữa `SETNX` và `EXPIRE`, lock sẽ không bao giờ expire. Ngoài ra, không verify lock ownership trước khi release dẫn đến xóa nhầm lock của process khác.

**Ví dụ thực tế:** Cron job xử lý payment, hai instance cùng acquire lock, cùng charge credit card → double charge.

```
RACE CONDITION VỚI SETNX + EXPIRE RIÊNG LẺ:

Process A: SETNX "lock" "A" ──▶ OK (acquired)
Process A: [CRASH before EXPIRE!]
           "lock" key tồn tại mãi mãi ──▶ DEADLOCK!

RACE CONDITION KHI RELEASE:

t=0:  Process A: acquire lock (TTL=5s)
t=4:  Process A: đang xử lý (chậm)
t=5:  Lock expire! (TTL hết)
t=5:  Process B: acquire lock (TTL=5s)
t=6:  Process A: DEL "lock" ──▶ XÓA LOCK CỦA PROCESS B!
t=6:  Process C: acquire lock ──▶ 2 process đang chạy song song!
```

### 5. Phát hiện trong mã nguồn

**Dấu hiệu nhận biết:**
- `redis.setnx()` + `redis.expire()` ở 2 dòng riêng nhau
- `redis.del(lockKey)` không verify giá trị trước
- Không dùng Redlock library cho multi-node Redis
- Lock value là constant string thay vì unique ID

**Regex patterns (ripgrep):**
```bash
# Tìm setnx không kèm atomic set
rg "setnx\(" --type ts -A 3 | grep -v "set.*NX\|SET.*NX"

# Tìm expire sau setnx (non-atomic pattern)
rg "setnx|SETNX" --type ts -A 5

# Tìm del lock không check ownership
rg "\.del\(.*lock\|\.del\(.*Lock" --type ts -B 3

# Tìm Redlock đã dùng đúng
rg "redlock|Redlock|new Redlock" --type ts
```

### 6. Giải pháp

| Tiêu chí | Cách sai | Cách đúng |
|---------|----------|-----------|
| Acquire | `SETNX` + `EXPIRE` (2 commands) | `SET key value EX ttl NX` (atomic) |
| Lock value | `'1'` (constant) | `uuid()` (unique per holder) |
| Release | `DEL key` trực tiếp | Lua script: check + del atomically |
| Multi-node | Single Redis | Redlock (N/2+1 nodes) |

```typescript
import { Redis } from 'ioredis'
import { v4 as uuidv4 } from 'uuid'

const redis = new Redis()

// ❌ SAI: SETNX + EXPIRE không atomic, không verify ownership
async function acquireLockBad(lockKey: string, ttlMs: number): Promise<boolean> {
  const acquired = await redis.setnx(lockKey, '1') // Non-atomic!
  if (acquired) {
    await redis.expire(lockKey, ttlMs / 1000) // Crash ở đây → deadlock!
  }
  return acquired === 1
}

async function releaseLockBad(lockKey: string): Promise<void> {
  await redis.del(lockKey) // Có thể xóa lock của process khác!
}

// ✅ ĐÚNG: Atomic SET NX + Lua script để release
const RELEASE_LOCK_SCRIPT = `
  if redis.call("GET", KEYS[1]) == ARGV[1] then
    return redis.call("DEL", KEYS[1])
  else
    return 0
  end
`

async function acquireLockGood(
  lockKey: string,
  ttlMs: number
): Promise<string | null> {
  const lockValue = uuidv4() // Unique ID per lock holder
  // Atomic: SET key value EX ttl NX
  const result = await redis.set(lockKey, lockValue, 'PX', ttlMs, 'NX')
  return result === 'OK' ? lockValue : null
}

async function releaseLockGood(lockKey: string, lockValue: string): Promise<boolean> {
  // Atomic Lua script: check ownership + delete
  const result = await redis.eval(RELEASE_LOCK_SCRIPT, 1, lockKey, lockValue)
  return result === 1
}

// ✅ HELPER: withLock wrapper
async function withLock<T>(
  lockKey: string,
  ttlMs: number,
  fn: () => Promise<T>
): Promise<T> {
  const lockValue = await acquireLockGood(lockKey, ttlMs)
  if (!lockValue) {
    throw new Error(`Failed to acquire lock: ${lockKey}`)
  }

  try {
    return await fn()
  } finally {
    const released = await releaseLockGood(lockKey, lockValue)
    if (!released) {
      console.warn(`Lock ${lockKey} was not released (may have expired or been stolen)`)
    }
  }
}

// Usage
async function processPayment(orderId: string): Promise<void> {
  await withLock(`payment:${orderId}`, 30_000, async () => {
    const order = await db.findOrder(orderId)
    if (order.status === 'PAID') return // Idempotency check
    await chargeCard(order)
    await db.updateOrderStatus(orderId, 'PAID')
  })
}

// ✅ NÂNG CAO: Redlock cho multi-node Redis
import Redlock from 'redlock'

const redlock = new Redlock([redis1, redis2, redis3], {
  retryCount: 3,
  retryDelay: 200,
  retryJitter: 100
})

async function processPaymentMultiNode(orderId: string): Promise<void> {
  const lock = await redlock.acquire([`payment:${orderId}`], 30_000)
  try {
    await chargeCard(orderId)
  } finally {
    await lock.release()
  }
}
```

### 7. Phòng ngừa

- [ ] Luôn dùng `SET key value EX ttl NX` (atomic), không dùng SETNX + EXPIRE riêng
- [ ] Lock value phải là unique ID (UUID), không phải constant
- [ ] Release lock bằng Lua script để check ownership trước khi delete
- [ ] Dùng Redlock cho production với Redis Cluster
- [ ] Implement lock extension nếu task có thể chạy lâu hơn TTL
- [ ] Log và alert khi lock không release được (process crash)

```javascript
// Custom ESLint rule: cảnh báo khi dùng redis.setnx mà không có comment ATOMIC
// "no-nonatomic-lock": "error"
```

---

## Pattern 05: Idempotency Key Thiếu

### 1. Tên
**Thiếu Khóa Idempotency** (Missing Idempotency Key)

### 2. Phân loại
- **Domain:** Distributed Systems / API Design
- **Subcategory:** Duplicate Processing, Data Integrity

### 3. Mức nghiêm trọng
🟠 **HIGH** - Duplicate operations: double charge, double send email, trùng record trong DB

### 4. Vấn đề

Khi client retry request (do timeout, network error), server xử lý cùng một business operation nhiều lần nếu không có idempotency key. Đặc biệt nguy hiểm với payment, email sending, và tạo resource.

**Ví dụ thực tế:** Client gửi POST /payment, timeout sau 5s, retry → 2 payment được tạo, user bị charge 2 lần.

```
KHÔNG CÓ IDEMPOTENCY:

Client                    Server                    DB
  │                          │                       │
  ├──── POST /payment ──────▶│                       │
  │                          ├── INSERT payment ────▶│
  │                          │   (id=1, amount=100)  │
  │                 timeout  │                       │
  │◀──── (no response) ──────│                       │
  │                          │                       │
  ├──── POST /payment ──────▶│ (retry!)              │
  │     (same payload)       ├── INSERT payment ────▶│
  │                          │   (id=2, amount=100)  │ ← DUPLICATE!
  │◀──── 200 OK ─────────────│                       │

CÓ IDEMPOTENCY KEY:

  ├──── POST /payment ──────▶│ (Idempotency-Key: abc)
  │     (Key: abc)           ├── Check: key "abc" exists? NO
  │                          ├── INSERT payment (id=1)
  │                          ├── Store key "abc" → result
  │                 timeout  │
  ├──── POST /payment ──────▶│ (retry, same Key: abc)
  │     (Key: abc)           ├── Check: key "abc" exists? YES
  │                          ├── Return stored result
  │◀──── 200 OK (same) ──────│ (no duplicate!)
```

### 5. Phát hiện trong mã nguồn

**Dấu hiệu nhận biết:**
- POST endpoints tạo resource/payment không check idempotency
- Không có `Idempotency-Key` header processing
- INSERT vào DB không có unique constraint phòng duplicate
- Email/SMS sending không có dedup key

**Regex patterns (ripgrep):**
```bash
# Tìm POST handlers không có idempotency check
rg "router\.post|app\.post|@Post" --type ts -A 10 | grep -v "idempotency\|idempotent\|dedup"

# Tìm payment/charge endpoints
rg "payment|charge|invoice|billing" --type ts -i | grep -v "idempotency"

# Tìm email/sms sending không có dedup
rg "sendMail|sendSms|sendEmail|notif" --type ts -B 2 -A 2

# Tìm idempotency đã implement
rg "Idempotency-Key|idempotencyKey|idempotent" --type ts
```

### 6. Giải pháp

| Tiêu chí | Cách sai | Cách đúng |
|---------|----------|-----------|
| POST /payment | Không check duplicate | Check idempotency key trước |
| Key storage | Không có | Redis với TTL 24h |
| Response | Tạo mới mỗi lần | Return cached response nếu key tồn tại |
| Error case | Không distinguish | Phân biệt "đang xử lý" vs "đã xong" |

```typescript
import { Redis } from 'ioredis'
import { Request, Response, NextFunction } from 'express'

const redis = new Redis()
const IDEMPOTENCY_TTL = 86_400 // 24 hours

// ❌ SAI: Không có idempotency, duplicate payment xảy ra
async function createPaymentBad(req: Request, res: Response): Promise<void> {
  const { amount, cardToken, orderId } = req.body
  // Mỗi lần gọi đều tạo payment mới!
  const payment = await paymentService.charge({ amount, cardToken, orderId })
  res.json({ paymentId: payment.id })
}

// ✅ ĐÚNG: Idempotency middleware
interface IdempotencyRecord {
  status: 'processing' | 'completed' | 'failed'
  response?: unknown
  createdAt: number
}

async function idempotencyMiddleware(
  req: Request,
  res: Response,
  next: NextFunction
): Promise<void> {
  const idempotencyKey = req.headers['idempotency-key'] as string

  if (!idempotencyKey) {
    res.status(400).json({ error: 'Idempotency-Key header required' })
    return
  }

  const redisKey = `idempotency:${idempotencyKey}`
  const existing = await redis.get(redisKey)

  if (existing) {
    const record = JSON.parse(existing) as IdempotencyRecord

    if (record.status === 'processing') {
      res.status(409).json({ error: 'Request is being processed' })
      return
    }

    if (record.status === 'completed') {
      // Return cached response
      res.json(record.response)
      return
    }
  }

  // Mark as processing
  const record: IdempotencyRecord = { status: 'processing', createdAt: Date.now() }
  await redis.set(redisKey, JSON.stringify(record), 'EX', IDEMPOTENCY_TTL)

  // Intercept response to store it
  const originalJson = res.json.bind(res)
  res.json = (body: unknown) => {
    const completedRecord: IdempotencyRecord = {
      status: 'completed',
      response: body,
      createdAt: Date.now()
    }
    redis.set(redisKey, JSON.stringify(completedRecord), 'EX', IDEMPOTENCY_TTL)
    return originalJson(body)
  }

  next()
}

// Áp dụng middleware cho payment routes
app.post('/payment', idempotencyMiddleware, async (req: Request, res: Response) => {
  const { amount, cardToken, orderId } = req.body
  const payment = await paymentService.charge({ amount, cardToken, orderId })
  res.json({ paymentId: payment.id })
})

// ✅ NÂNG CAO: DB-level unique constraint kết hợp
// Migration SQL:
// ALTER TABLE payments ADD COLUMN idempotency_key VARCHAR(255) UNIQUE;
// CREATE UNIQUE INDEX idx_payments_idempotency ON payments(idempotency_key);

async function createPaymentWithDBGuard(
  idempotencyKey: string,
  payload: PaymentPayload
): Promise<Payment> {
  try {
    return await db.transaction(async (trx) => {
      // Unique constraint sẽ throw nếu duplicate
      return await trx('payments').insert({
        ...payload,
        idempotency_key: idempotencyKey,
        created_at: new Date()
      }).returning('*')
    })
  } catch (err) {
    if (isUniqueConstraintError(err)) {
      // Return existing payment
      return await db('payments').where({ idempotency_key: idempotencyKey }).first()
    }
    throw err
  }
}
```

### 7. Phòng ngừa

- [ ] Tất cả non-idempotent POST endpoints phải có Idempotency-Key support
- [ ] Store idempotency keys trong Redis với TTL hợp lý (24h)
- [ ] Thêm unique constraint tại DB layer làm safety net
- [ ] Document idempotency requirement trong API spec (OpenAPI)
- [ ] Client SDK tự động tạo và gửi idempotency key
- [ ] Alert khi phát hiện duplicate processing (log mining)

```javascript
// ESLint rule: warn khi POST handler không import/use idempotency middleware
// "require-idempotency-middleware": "warn"
```

---

## Pattern 06: WebSocket Reconnection

### 1. Tên
**Kết Nối Lại WebSocket Không Đúng** (WebSocket Reconnection Mishandling)

### 2. Phân loại
- **Domain:** Distributed Systems / Real-time Communication
- **Subcategory:** Connection Management, State Synchronization

### 3. Mức nghiêm trọng
🟠 **HIGH** - Mất tin nhắn, state không đồng bộ, memory leak từ zombie connections

### 4. Vấn đề

WebSocket connections có thể bị ngắt bất ngờ. Nếu client không reconnect đúng cách hoặc server không handle disconnect/reconnect, client sẽ miss events, có state lỗi thời, hoặc accumulate event listeners gây memory leak.

**Ví dụ thực tế:** Chat app, user mất mạng 10 giây, khi reconnect không nhận được tin nhắn đã gửi trong lúc offline.

```
RECONNECT SAI (tạo listener mới mỗi lần):

connect() ──▶ addEventListener('message', handler)  [1 listener]
disconnect
connect() ──▶ addEventListener('message', handler)  [2 listeners!]
disconnect
connect() ──▶ addEventListener('message', handler)  [3 listeners!]
             ... mỗi message được xử lý N lần! MEMORY LEAK!

RECONNECT ĐÚNG:

connect() ──▶ addEventListener('message', handler)  [1 listener]
disconnect ──▶ cleanup listeners
connect() ──▶ addEventListener('message', handler)  [1 listener]
             + fetch missed messages (sequence number)
```

### 5. Phát hiện trong mã nguồn

**Dấu hiệu nhận biết:**
- `addEventListener` trong hàm connect không remove listener khi disconnect
- Không có sequence number / last-event-id để fetch missed events
- Reconnect interval cố định (không exponential backoff)
- Không handle `onclose` event hoặc ping/pong heartbeat

**Regex patterns (ripgrep):**
```bash
# Tìm WebSocket không có cleanup
rg "new WebSocket|new ws\." --type ts -A 10 | grep -v "removeEventListener\|close()"

# Tìm addEventListener trong connect function
rg "addEventListener\('message'" --type ts -B 5

# Tìm reconnect logic
rg "onclose|on\('close'\)|reconnect" --type ts -A 5

# Tìm heartbeat/ping implementation
rg "ping|heartbeat|setInterval.*ws\|ws.*setInterval" --type ts
```

### 6. Giải pháp

| Tiêu chí | Cách sai | Cách đúng |
|---------|----------|-----------|
| Listener cleanup | Không remove | Remove trước reconnect |
| Reconnect delay | Cố định | Exponential backoff |
| Missed messages | Bỏ qua | Fetch với sequence number |
| Heartbeat | Không có | Ping/pong interval |
| Max reconnects | Vô hạn | Giới hạn + notify user |

```typescript
// ❌ SAI: Memory leak, không cleanup, không fetch missed events
class BadWebSocketClient {
  private ws: WebSocket | null = null

  connect(url: string): void {
    this.ws = new WebSocket(url)

    // PROBLEM: Mỗi lần connect thêm 1 listener, không cleanup!
    this.ws.addEventListener('message', (event) => {
      this.handleMessage(JSON.parse(event.data))
    })

    this.ws.onclose = () => {
      // Reconnect ngay lập tức, không có backoff!
      setTimeout(() => this.connect(url), 1000)
    }
  }

  private handleMessage(data: unknown): void {
    console.log('message:', data)
  }
}

// ✅ ĐÚNG: Proper cleanup, exponential backoff, sequence tracking
interface WebSocketMessage {
  seq: number
  type: string
  data: unknown
}

class RobustWebSocketClient {
  private ws: WebSocket | null = null
  private reconnectAttempt = 0
  private lastSeq = 0
  private heartbeatInterval: NodeJS.Timeout | null = null
  private readonly maxReconnectAttempts = 10
  private readonly baseReconnectDelay = 1000

  constructor(
    private readonly url: string,
    private readonly onMessage: (msg: WebSocketMessage) => void,
    private readonly onStatusChange: (status: 'connected' | 'disconnected' | 'failed') => void
  ) {}

  connect(): void {
    this.cleanup() // Cleanup trước khi tạo connection mới

    this.ws = new WebSocket(`${this.url}?lastSeq=${this.lastSeq}`)

    // Bind handlers một lần, cleanup trong disconnect
    const messageHandler = (event: MessageEvent): void => {
      const msg = JSON.parse(event.data) as WebSocketMessage
      // Bỏ qua duplicate messages
      if (msg.seq <= this.lastSeq) return
      this.lastSeq = msg.seq
      this.onMessage(msg)
    }

    const openHandler = (): void => {
      this.reconnectAttempt = 0
      this.onStatusChange('connected')
      this.startHeartbeat()
    }

    const closeHandler = (event: CloseEvent): void => {
      this.cleanup()
      this.onStatusChange('disconnected')
      if (event.code !== 1000) { // 1000 = normal close
        this.scheduleReconnect()
      }
    }

    const errorHandler = (): void => {
      this.cleanup()
    }

    this.ws.addEventListener('message', messageHandler)
    this.ws.addEventListener('open', openHandler)
    this.ws.addEventListener('close', closeHandler)
    this.ws.addEventListener('error', errorHandler)

    // Store handlers để cleanup sau
    ;(this.ws as unknown as Record<string, unknown>).__handlers = {
      message: messageHandler,
      open: openHandler,
      close: closeHandler,
      error: errorHandler
    }
  }

  private cleanup(): void {
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval)
      this.heartbeatInterval = null
    }

    if (this.ws) {
      const handlers = (this.ws as unknown as Record<string, unknown>).__handlers as Record<string, EventListener>
      if (handlers) {
        this.ws.removeEventListener('message', handlers.message)
        this.ws.removeEventListener('open', handlers.open)
        this.ws.removeEventListener('close', handlers.close)
        this.ws.removeEventListener('error', handlers.error)
      }
      if (this.ws.readyState !== WebSocket.CLOSED) {
        this.ws.close(1000)
      }
      this.ws = null
    }
  }

  private scheduleReconnect(): void {
    if (this.reconnectAttempt >= this.maxReconnectAttempts) {
      this.onStatusChange('failed')
      return
    }

    const delay = Math.min(
      this.baseReconnectDelay * Math.pow(2, this.reconnectAttempt),
      30_000
    ) * (0.5 + Math.random() * 0.5) // Add jitter

    this.reconnectAttempt++
    setTimeout(() => this.connect(), delay)
  }

  private startHeartbeat(): void {
    this.heartbeatInterval = setInterval(() => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify({ type: 'ping' }))
      }
    }, 30_000)
  }

  disconnect(): void {
    this.reconnectAttempt = this.maxReconnectAttempts // Prevent reconnect
    this.cleanup()
  }
}
```

### 7. Phòng ngừa

- [ ] Luôn cleanup event listeners trước khi tạo connection mới
- [ ] Implement exponential backoff cho reconnect
- [ ] Track sequence number để fetch missed messages khi reconnect
- [ ] Implement heartbeat (ping/pong) để detect zombie connections
- [ ] Giới hạn số lần reconnect và notify user khi thất bại
- [ ] Server phải buffer messages trong thời gian disconnect ngắn

```javascript
// ESLint: cảnh báo khi addEventListener trong function không có tương ứng removeEventListener
// "paired-add-remove-event-listener": "warn"
```

---

## Pattern 07: Queue Consumer Thiếu Ack (Missing Message Ack)

### 1. Tên
**Thiếu Xác Nhận Tin Nhắn** (Missing Message Acknowledgment)

### 2. Phân loại
- **Domain:** Distributed Systems / Message Queue
- **Subcategory:** Message Reliability, At-least-once Delivery

### 3. Mức nghiêm trọng
🔴 **CRITICAL** - Mất message hoàn toàn hoặc xử lý vô hạn, business logic không được thực thi

### 4. Vấn đề

Với RabbitMQ/SQS, khi consumer nhận message nhưng không ack (xác nhận), message bị requeue sau timeout. Nếu consumer ack ngay khi nhận (trước khi xử lý xong), message bị mất khi process crash giữa chừng. Nếu không ack sau khi xử lý xong, message bị requeue vô hạn.

**Ví dụ thực tế:** Order processing worker nhận message, ack ngay, crash khi đang gọi inventory API → order tồn tại trong DB nhưng inventory không được trừ.

```
ACK NGAY (message loss khi crash):

Consumer ──▶ Receive msg ──▶ ACK ──▶ [CRASH] ──▶ msg mất hoàn toàn!
                  ↑
           Queue đã xóa msg

KHÔNG ACK (infinite requeue):

Consumer ──▶ Receive msg ──▶ Process... ──▶ [No ACK] ──▶ Requeue after timeout
Consumer ──▶ Receive msg ──▶ Process... ──▶ [No ACK] ──▶ Requeue after timeout
                                                          (vòng lặp vô tận!)

ĐÚNG (ack sau khi xử lý thành công):

Consumer ──▶ Receive msg ──▶ Process... ──▶ SUCCESS ──▶ ACK ──▶ msg removed
                                        ──▶ FAILURE ──▶ NACK (requeue with limit)
```

### 5. Phát hiện trong mã nguồn

**Dấu hiệu nhận biết:**
- `channel.ack(msg)` trước khi processing logic hoàn thành
- Consumer không có try/catch với `channel.nack()`
- `noAck: true` trong consume options (auto-ack)
- Không có dead letter queue (DLQ) configuration

**Regex patterns (ripgrep):**
```bash
# Tìm noAck: true (auto-acknowledge, dangerous)
rg "noAck:\s*true|{ noAck" --type ts

# Tìm ack trước processing (ack không nằm trong try block sau xử lý)
rg "channel\.ack\|msg\.ack\|message\.ack" --type ts -B 5

# Tìm consumer không có nack
rg "channel\.consume|\.subscribe\(" --type ts -A 20 | grep -v "nack\|reject"

# Tìm dead letter queue config
rg "deadLetterExchange|DLQ|dead.letter|dlq" --type ts
```

### 6. Giải pháp

| Tiêu chí | Cách sai | Cách đúng |
|---------|----------|-----------|
| Ack timing | Ack ngay khi nhận | Ack SAU khi xử lý thành công |
| Error handling | Không nack | Nack với requeue=false sau max retries |
| noAck | true | false (manual ack) |
| DLQ | Không có | Có Dead Letter Queue |

```typescript
import amqp, { Channel, ConsumeMessage } from 'amqplib'

// ❌ SAI: Ack ngay, mất message khi crash
async function startConsumerBad(): Promise<void> {
  const conn = await amqp.connect('amqp://localhost')
  const channel = await conn.createChannel()

  await channel.consume('orders', async (msg) => {
    if (!msg) return

    // ACK NGAY → nếu crash ở dưới, message mất!
    channel.ack(msg)

    const order = JSON.parse(msg.content.toString())
    await processOrder(order) // Nếu lỗi ở đây → data inconsistency!
  })
}

// ❌ SAI: noAck: true (auto-acknowledge)
async function startConsumerAutoAck(): Promise<void> {
  const channel = await conn.createChannel()
  // Mọi message tự động ack khi deliver, không thể nack!
  await channel.consume('orders', handler, { noAck: true })
}

// ✅ ĐÚNG: Ack sau khi xử lý thành công, nack khi lỗi
const MAX_RETRIES = 3

async function startConsumerGood(): Promise<void> {
  const conn = await amqp.connect('amqp://localhost')
  const channel = await conn.createChannel()

  // Setup Dead Letter Queue
  await channel.assertExchange('orders.dlx', 'direct')
  await channel.assertQueue('orders.dlq', { durable: true })
  await channel.bindQueue('orders.dlq', 'orders.dlx', 'dead')

  // Main queue với DLX config
  await channel.assertQueue('orders', {
    durable: true,
    arguments: {
      'x-dead-letter-exchange': 'orders.dlx',
      'x-dead-letter-routing-key': 'dead',
      'x-message-ttl': 60_000 // 1 minute per retry
    }
  })

  // Prefetch: chỉ nhận 1 message tại một thời điểm
  await channel.prefetch(1)

  await channel.consume('orders', async (msg: ConsumeMessage | null) => {
    if (!msg) return

    const retryCount = (msg.properties.headers?.['x-retry-count'] as number) || 0

    try {
      const order = JSON.parse(msg.content.toString()) as Order
      await processOrder(order) // Xử lý trước

      // ACK chỉ sau khi thành công
      channel.ack(msg)
    } catch (err) {
      console.error('Order processing failed:', err)

      if (retryCount < MAX_RETRIES) {
        // NACK + requeue với retry count tăng lên
        channel.nack(msg, false, false) // false, false = không requeue vào main queue
        // Republish với retry count header
        await channel.publish('', 'orders', msg.content, {
          persistent: true,
          headers: { 'x-retry-count': retryCount + 1 }
        })
      } else {
        // Max retries exceeded → send to DLQ (no requeue)
        console.error(`Message sent to DLQ after ${MAX_RETRIES} retries`)
        channel.nack(msg, false, false)
      }
    }
  }, { noAck: false }) // Manual acknowledgment!
}

// ✅ SQS equivalent
import { SQSClient, DeleteMessageCommand, ChangeMessageVisibilityCommand } from '@aws-sdk/client-sqs'

async function processSQSMessage(
  message: SQSMessage,
  queueUrl: string
): Promise<void> {
  const sqs = new SQSClient({})

  try {
    await processOrder(JSON.parse(message.Body!))

    // Delete message (= ACK in SQS)
    await sqs.send(new DeleteMessageCommand({
      QueueUrl: queueUrl,
      ReceiptHandle: message.ReceiptHandle!
    }))
  } catch (err) {
    // Extend visibility timeout để retry sau
    await sqs.send(new ChangeMessageVisibilityCommand({
      QueueUrl: queueUrl,
      ReceiptHandle: message.ReceiptHandle!,
      VisibilityTimeout: 60 // Sẽ reappear sau 60s
    }))
    throw err
  }
}
```

### 7. Phòng ngừa

- [ ] Luôn dùng manual ack (`noAck: false`), ACK chỉ sau khi xử lý thành công
- [ ] Implement NACK với Dead Letter Queue cho failed messages
- [ ] Set `prefetch(1)` để không nhận quá nhiều message cùng lúc
- [ ] Monitor DLQ size; alert khi DLQ có messages
- [ ] Implement idempotency trong consumer (handle duplicate delivery)
- [ ] Test consumer crash scenario (kill process giữa chừng)

```javascript
// ESLint: cảnh báo khi channel.ack() không nằm trong try block sau processing logic
// "ack-after-processing": "error"
```

---

## Pattern 08: Pub/Sub Message Loss

### 1. Tên
**Mất Tin Nhắn Pub/Sub** (Pub/Sub Message Loss)

### 2. Phân loại
- **Domain:** Distributed Systems / Messaging
- **Subcategory:** Event-driven Architecture, Message Durability

### 3. Mức nghiêm trọng
🟠 **HIGH** - Events bị mất, downstream services bị thiếu thông tin, data inconsistency

### 4. Vấn đề

Redis Pub/Sub không lưu trữ message: subscriber phải online khi message được publish, nếu offline sẽ miss tất cả. Ngoài ra, nếu không có acknowledgment, publisher không biết subscriber có nhận được không.

**Ví dụ thực tế:** User service publish "user.created" event, email service đang restart → email chào mừng không bao giờ được gửi.

```
REDIS PUB/SUB (Fire-and-forget, message loss):

Publisher ──▶ PUBLISH "user.created" {userId: 123}
                │
                ├── Email Service (ONLINE)   ──▶ Nhận được
                ├── Audit Service (RESTARTING) ──▶ MẤT!
                └── Analytics (OFFLINE)        ──▶ MẤT!

PERSISTENT EVENT STREAM (Redis Streams / Kafka):

Publisher ──▶ XADD stream "user.created" {userId: 123}
              (Message lưu trong stream)
                │
                ├── Email Service (ONLINE)    ──▶ Đọc từ stream, ACK
                ├── Audit Service (sau restart) ──▶ Đọc từ lastId, không mất!
                └── Analytics (sau khi online)  ──▶ Đọc từ checkpoint, không mất!
```

### 5. Phát hiện trong mã nguồn

**Dấu hiệu nhận biết:**
- Dùng `redis.publish()` / `redis.subscribe()` cho critical events
- Không có message persistence (Redis Streams, Kafka, RabbitMQ)
- Không track consumer position / offset
- Không có replay mechanism cho missed events

**Regex patterns (ripgrep):**
```bash
# Tìm Redis Pub/Sub usage
rg "redis\.publish|redis\.subscribe|\.publish\(|\.subscribe\(" --type ts

# Tìm Redis Streams (đúng cách)
rg "xadd|xread|xreadgroup|XADD|XREAD" --type ts

# Tìm Kafka consumer với offset tracking
rg "commitOffsets|consumer\.commit|offset" --type ts

# Tìm event emitter không persistent
rg "EventEmitter|eventEmitter\.emit" --type ts -A 3
```

### 6. Giải pháp

| Tiêu chí | Cách sai | Cách đúng |
|---------|----------|-----------|
| Storage | Redis Pub/Sub (volatile) | Redis Streams / Kafka / RabbitMQ |
| Delivery | Fire-and-forget | At-least-once với ACK |
| Subscriber state | Không track | Consumer group + offset |
| Missed events | Mất vĩnh viễn | Replay từ checkpoint |

```typescript
import { Redis } from 'ioredis'

const redis = new Redis()

// ❌ SAI: Redis Pub/Sub - message bị mất khi subscriber offline
async function publishUserCreatedBad(userId: string): Promise<void> {
  // Nếu không có subscriber nào đang listen → message biến mất!
  await redis.publish('user:events', JSON.stringify({
    type: 'user.created',
    userId,
    timestamp: Date.now()
  }))
}

// ❌ SAI: Subscriber có thể miss events
async function subscribeUserEventsBad(): Promise<void> {
  await redis.subscribe('user:events')
  redis.on('message', (channel, message) => {
    // Không có ACK, không biết đã xử lý chưa
    processUserEvent(JSON.parse(message))
  })
}

// ✅ ĐÚNG: Redis Streams với Consumer Groups
const STREAM_NAME = 'user:events'
const GROUP_NAME = 'email-service'
const CONSUMER_NAME = `consumer-${process.pid}`

async function publishUserCreatedGood(userId: string): Promise<void> {
  // XADD: message được lưu trong stream, durable
  const messageId = await redis.xadd(
    STREAM_NAME,
    '*', // Auto-generate ID
    'type', 'user.created',
    'userId', userId,
    'timestamp', Date.now().toString()
  )
  console.log(`Published event ${messageId}`)
}

async function setupConsumerGroup(): Promise<void> {
  try {
    // Tạo consumer group, đọc từ đầu stream ('0') hoặc chỉ mới ('$')
    await redis.xgroup('CREATE', STREAM_NAME, GROUP_NAME, '0', 'MKSTREAM')
  } catch (err) {
    if ((err as Error).message.includes('BUSYGROUP')) {
      console.log('Consumer group already exists')
    } else {
      throw err
    }
  }
}

async function consumeUserEventsGood(): Promise<void> {
  await setupConsumerGroup()

  while (true) {
    // Đọc messages chưa được xử lý (pending)
    const results = await redis.xreadgroup(
      'GROUP', GROUP_NAME, CONSUMER_NAME,
      'COUNT', 10,
      'BLOCK', 5000, // Wait 5s nếu không có message
      'STREAMS', STREAM_NAME, '>' // '>' = chỉ messages chưa deliver
    ) as Array<[string, Array<[string, string[]]>]> | null

    if (!results) continue

    for (const [, messages] of results) {
      for (const [messageId, fields] of messages) {
        const event: Record<string, string> = {}
        for (let i = 0; i < fields.length; i += 2) {
          event[fields[i]] = fields[i + 1]
        }

        try {
          await processUserEvent(event)
          // ACK message sau khi xử lý thành công
          await redis.xack(STREAM_NAME, GROUP_NAME, messageId)
        } catch (err) {
          console.error(`Failed to process event ${messageId}:`, err)
          // Không ACK → message sẽ remain pending, có thể claim lại sau
        }
      }
    }

    // Claim pending messages (from crashed consumers)
    await claimPendingMessages()
  }
}

async function claimPendingMessages(): Promise<void> {
  // Claim messages pending > 5 minutes (probably from dead consumers)
  const pending = await redis.xpending(STREAM_NAME, GROUP_NAME, '-', '+', 10) as Array<[string, string, number, number]>

  for (const [messageId, , idleTime] of pending) {
    if (idleTime > 300_000) { // 5 minutes
      await redis.xclaim(STREAM_NAME, GROUP_NAME, CONSUMER_NAME, 300_000, messageId)
    }
  }
}
```

### 7. Phòng ngừa

- [ ] Không dùng Redis Pub/Sub cho critical business events
- [ ] Dùng Redis Streams, Kafka, hoặc RabbitMQ (có persistence)
- [ ] Implement consumer groups để track processing state
- [ ] Handle pending messages từ crashed consumers (claim)
- [ ] Monitor consumer lag (messages chưa được xử lý)
- [ ] Implement event replay capability từ specific offset

```javascript
// ESLint: cảnh báo khi dùng redis.publish/subscribe thay vì streams
// "no-volatile-pubsub": "warn"
```

---

## Pattern 09: Rate Limiting Distributed

### 1. Tên
**Rate Limiting Phân Tán Không Đúng** (Distributed Rate Limiting Failure)

### 2. Phân loại
- **Domain:** Distributed Systems / API Security
- **Subcategory:** Throttling, Abuse Prevention

### 3. Mức nghiêm trọng
🟡 **MEDIUM** - API bị lạm dụng, chi phí tăng, ảnh hưởng user hợp lệ

### 4. Vấn đề

Rate limiting chỉ dùng in-memory (local) sẽ thất bại khi scale ngang. Với 10 instance, mỗi instance cho phép 100 req/min → tổng 1000 req/min, gấp 10 lần giới hạn mong muốn.

**Ví dụ thực tế:** API limit 100 req/min per user, nhưng 3 pods → user có thể gửi 300 req/min.

```
IN-MEMORY RATE LIMIT (thất bại khi scale):

User gửi 300 requests:
  ├── Pod 1: 100 req → nhận cả 100 (limit local = 100)
  ├── Pod 2: 100 req → nhận cả 100 (limit local = 100)
  └── Pod 3: 100 req → nhận cả 100 (limit local = 100)
  Tổng: 300 requests qua được! (mong muốn: 100)

DISTRIBUTED RATE LIMIT (Redis):

User gửi 300 requests:
  ├── Pod 1: 100 req → check Redis counter → 100/100 → nhận 100
  ├── Pod 2: 100 req → check Redis counter → 100/100 → reject tất cả
  └── Pod 3: 100 req → check Redis counter → 100/100 → reject tất cả
  Tổng: đúng 100 requests qua! ✓
```

### 5. Phát hiện trong mã nguồn

**Dấu hiệu nhận biết:**
- `Map<string, number>` hoặc `rateLimit = {}` trong-memory không dùng Redis
- Rate limiter không shared giữa instances
- Không có Redis-backed rate limiter library
- `express-rate-limit` không có `store` config (dùng MemoryStore mặc định)

**Regex patterns (ripgrep):**
```bash
# Tìm express-rate-limit không có store (dùng MemoryStore)
rg "rateLimit\(\|rateLimiter\(" --type ts -A 10 | grep -v "store:\|redis\|Redis"

# Tìm in-memory counter
rg "new Map\(\)|requestCount|hitCount" --type ts -A 3

# Tìm Redis rate limiter đúng cách
rg "rate-limit-redis|redis-rate-limit|ioredis.*limit" --type ts

# Tìm sliding window hoặc token bucket
rg "sliding.*window|token.*bucket|leaky.*bucket" --type ts
```

### 6. Giải pháp

| Tiêu chí | Cách sai | Cách đúng |
|---------|----------|-----------|
| Storage | In-memory (local) | Redis (shared) |
| Algorithm | Fixed window | Sliding window / Token bucket |
| Scale | Không hoạt động khi scale | Đúng dù N instances |
| Key | IP only | userId + IP + endpoint |

```typescript
import { Redis } from 'ioredis'
import { Request, Response, NextFunction } from 'express'

const redis = new Redis()

// ❌ SAI: In-memory rate limit, thất bại khi scale
const requestCounts = new Map<string, { count: number; resetAt: number }>()

function rateLimitBad(limit: number, windowMs: number) {
  return (req: Request, res: Response, next: NextFunction): void => {
    const key = req.ip!
    const now = Date.now()
    const record = requestCounts.get(key)

    if (!record || now > record.resetAt) {
      requestCounts.set(key, { count: 1, resetAt: now + windowMs })
      next()
      return
    }

    if (record.count >= limit) {
      res.status(429).json({ error: 'Rate limit exceeded' })
      return
    }

    record.count++
    next()
  }
}

// ✅ ĐÚNG: Redis-backed sliding window rate limiter
const SLIDING_WINDOW_SCRIPT = `
  local key = KEYS[1]
  local now = tonumber(ARGV[1])
  local window = tonumber(ARGV[2])
  local limit = tonumber(ARGV[3])

  -- Remove old entries outside window
  redis.call('ZREMRANGEBYSCORE', key, '-inf', now - window)

  -- Count current entries
  local current = redis.call('ZCARD', key)

  if current < limit then
    -- Add new request
    redis.call('ZADD', key, now, now .. math.random())
    redis.call('EXPIRE', key, math.ceil(window / 1000))
    return 1  -- Allowed
  else
    return 0  -- Rejected
  end
`

function rateLimitGood(limit: number, windowMs: number) {
  return async (req: Request, res: Response, next: NextFunction): Promise<void> => {
    const userId = (req as Request & { user?: { id: string } }).user?.id || req.ip!
    const endpoint = req.path
    const key = `ratelimit:${userId}:${endpoint}`
    const now = Date.now()

    const result = await redis.eval(
      SLIDING_WINDOW_SCRIPT,
      1,
      key,
      now.toString(),
      windowMs.toString(),
      limit.toString()
    ) as number

    if (result === 0) {
      // Add rate limit headers
      res.setHeader('X-RateLimit-Limit', limit)
      res.setHeader('X-RateLimit-Remaining', 0)
      res.setHeader('Retry-After', Math.ceil(windowMs / 1000))
      res.status(429).json({
        error: 'Rate limit exceeded',
        retryAfter: Math.ceil(windowMs / 1000)
      })
      return
    }

    const remaining = await redis.zcard(key)
    res.setHeader('X-RateLimit-Limit', limit)
    res.setHeader('X-RateLimit-Remaining', Math.max(0, limit - remaining))
    next()
  }
}

// ✅ NÂNG CAO: Dùng rate-limit-redis với express-rate-limit
import rateLimit from 'express-rate-limit'
import RedisStore from 'rate-limit-redis'

const apiLimiter = rateLimit({
  windowMs: 60_000, // 1 minute
  max: 100,
  standardHeaders: true,
  legacyHeaders: false,
  store: new RedisStore({
    sendCommand: (...args: string[]) => redis.call(...args)
  }),
  keyGenerator: (req) => {
    const userId = (req as Request & { user?: { id: string } }).user?.id || req.ip!
    return `${userId}:${req.path}`
  }
})

app.use('/api/', apiLimiter)
```

### 7. Phòng ngừa

- [ ] Luôn dùng Redis-backed store cho rate limiting trong distributed environment
- [ ] Dùng sliding window algorithm thay vì fixed window
- [ ] Rate limit theo userId (authenticated) + IP (unauthenticated)
- [ ] Set appropriate rate limit headers (X-RateLimit-*)
- [ ] Implement tiered limits (per user, per IP, per endpoint)
- [ ] Monitor rate limit hit rate để tune limits

```javascript
// ESLint: cảnh báo khi express-rate-limit không có store config
// "distributed-rate-limit-required": "warn"
```

---

## Pattern 10: Session Sticky Dependency

### 1. Tên
**Phụ Thuộc Sticky Session** (Session Sticky Dependency)

### 2. Phân loại
- **Domain:** Distributed Systems / Session Management
- **Subcategory:** Stateful Services, Load Balancing

### 3. Mức nghiêm trọng
🟠 **HIGH** - Session mất khi pod restart, load balancer đổi pod → user bị logout giữa chừng

### 4. Vấn đề

Lưu session data trong-memory (hoặc file cục bộ) làm service stateful. Khi load balancer route request đến pod khác, session không tồn tại ở đó → user bị logout hoặc state bị mất.

**Ví dụ thực tế:** User đang điền form nhiều bước, session lưu in-memory, pod restart/scale → session mất, user phải làm lại từ đầu.

```
STICKY SESSION VẤN ĐỀ:

Request 1 ──▶ Pod A (session: {userId: 1, step: 3})
Request 2 ──▶ Pod B (session: {} ← không có! Pod B không biết gì)
              "Unauthorized" / state lost!

                    LB Route mới
                         │
User ─────────────────▶ ─┼──▶ Pod A (session ok)
                         │         ↑ POD CRASH!
                         └──▶ Pod B (no session!)

STATELESS SESSION (Redis):

Request 1 ──▶ Pod A ──▶ Redis (save session)
Request 2 ──▶ Pod B ──▶ Redis (load same session) ──▶ OK!
Request 3 ──▶ Pod C ──▶ Redis (load same session) ──▶ OK!
```

### 5. Phát hiện trong mã nguồn

**Dấu hiệu nhận biết:**
- `express-session` không có Redis store (dùng MemoryStore)
- Global variables lưu user state (`const sessions = {}`)
- File-based session storage
- Session data không được serialize/deserialize từ external store

**Regex patterns (ripgrep):**
```bash
# Tìm express-session không có store (MemoryStore)
rg "session\(\{" --type ts -A 10 | grep -v "store:\|redis\|Redis\|connect-redis"

# Tìm in-memory session storage
rg "const sessions|let sessions|sessions\[|sessions\.set" --type ts

# Tìm connect-redis đúng cách
rg "connect-redis|RedisStore|redis.*session" --type ts

# Tìm JWT (stateless alternative)
rg "jsonwebtoken|jwt\.sign|jwt\.verify" --type ts
```

### 6. Giải pháp

| Tiêu chí | Cách sai | Cách đúng |
|---------|----------|-----------|
| Storage | MemoryStore (local) | Redis Store (shared) |
| State | Stateful pod | Stateless pod |
| Failover | Session mất khi crash | Session persist |
| Scale | Cần sticky routing | Free to route anywhere |

```typescript
import session from 'express-session'
import { createClient } from 'redis'
import connectRedis from 'connect-redis'
import jwt from 'jsonwebtoken'

// ❌ SAI: MemoryStore (mặc định) - không work khi scale
const app = express()

app.use(session({
  secret: 'my-secret',
  resave: false,
  saveUninitialized: false,
  // Không có store: → dùng MemoryStore, chỉ hoạt động trên 1 instance!
  cookie: { secure: true, maxAge: 86_400_000 }
}))

// ✅ ĐÚNG: Redis Store - shared across all instances
const RedisStore = connectRedis(session)
const redisClient = createClient({ url: process.env.REDIS_URL })

await redisClient.connect()

app.use(session({
  store: new RedisStore({ client: redisClient }),
  secret: process.env.SESSION_SECRET!,
  resave: false,
  saveUninitialized: false,
  cookie: {
    secure: process.env.NODE_ENV === 'production',
    httpOnly: true,
    maxAge: 86_400_000 // 24h
  }
}))

// ✅ NÂNG CAO: JWT (stateless, không cần Redis cho session)
interface JWTPayload {
  userId: string
  role: string
  iat: number
  exp: number
}

const JWT_SECRET = process.env.JWT_SECRET!
const JWT_EXPIRY = '24h'

function signToken(payload: Omit<JWTPayload, 'iat' | 'exp'>): string {
  return jwt.sign(payload, JWT_SECRET, { expiresIn: JWT_EXPIRY })
}

function verifyToken(token: string): JWTPayload {
  return jwt.verify(token, JWT_SECRET) as JWTPayload
}

// JWT Middleware
function jwtMiddleware(req: Request, res: Response, next: NextFunction): void {
  const authHeader = req.headers.authorization
  if (!authHeader?.startsWith('Bearer ')) {
    res.status(401).json({ error: 'No token provided' })
    return
  }

  const token = authHeader.slice(7)
  try {
    const payload = verifyToken(token)
    ;(req as Request & { user: JWTPayload }).user = payload
    next()
  } catch {
    res.status(401).json({ error: 'Invalid or expired token' })
  }
}

// Token rotation (refresh token pattern)
async function refreshToken(refreshToken: string): Promise<{ accessToken: string }> {
  // Verify refresh token (lưu trong Redis để có thể revoke)
  const stored = await redis.get(`refresh:${refreshToken}`)
  if (!stored) throw new Error('Invalid refresh token')

  const { userId, role } = JSON.parse(stored) as JWTPayload
  const accessToken = signToken({ userId, role })
  return { accessToken }
}
```

### 7. Phòng ngừa

- [ ] Không bao giờ dùng MemoryStore trong production
- [ ] Dùng Redis Store cho session-based auth, hoặc JWT cho stateless
- [ ] Thiết kế service stateless từ đầu
- [ ] Test với multiple instances (docker-compose scale)
- [ ] Implement token rotation cho JWT (refresh token)
- [ ] Monitor session store availability (Redis down → auth down)

```javascript
// ESLint: cảnh báo khi express-session không có store config
// "no-memory-session-store": "error"
```

---

## Pattern 11: Service Mesh Timeout Chain

### 1. Tên
**Chuỗi Timeout Service Mesh** (Service Mesh Timeout Chain)

### 2. Phân loại
- **Domain:** Distributed Systems / Microservices
- **Subcategory:** Timeout Propagation, Cascading Failure

### 3. Mức nghiêm trọng
🔴 **CRITICAL** - Request bị kill giữa chừng bởi upstream timeout, downstream vẫn tiếp tục xử lý gây resource waste và data inconsistency

### 4. Vấn đề

Trong chuỗi microservices (A → B → C → D), nếu timeout không được set đúng thứ tự giảm dần, upstream có thể timeout và cancel request trong khi downstream vẫn đang xử lý (và commit data). Kết quả: A thấy timeout, nhưng D đã commit transaction → inconsistent state.

**Ví dụ thực tế:** API Gateway timeout 5s, Service A timeout 10s, Service B xử lý 7s → Gateway báo lỗi cho client, nhưng B đã tạo xong record trong DB.

```
TIMEOUT CHAIN SAI:

API GW (timeout=5s) ──▶ Service A (timeout=10s) ──▶ Service B (timeout=30s)
    │                         │                           │
    │                         │                           ▼
    │                     t=5s: GW                  (processing... 7s)
    │◀── 504 timeout ────  cancel req                     │
    │                                                     ▼
    │                                              (commit to DB at t=7s)
    │                                              DATA EXISTS in B's DB
    │                                              But client sees ERROR!

TIMEOUT CHAIN ĐÚNG (decreasing timeout):

API GW (timeout=10s) ──▶ Service A (timeout=8s) ──▶ Service B (timeout=6s)
    │                         │                           │
    │                         │                           ▼
    │                         │                      t=6s: B times out
    │                         │                      B cleanup + rollback
    │                         ▼
    │                    t=8s: A times out (if B slow)
    │                    A cleanup + rollback
    │◀── 504 timeout ────
    │                    Client sees error, data consistent
```

### 5. Phát hiện trong mã nguồn

**Dấu hiệu nhận biết:**
- Timeout upstream >= timeout downstream (sai thứ tự)
- Không pass deadline/context qua service calls
- Không cleanup/rollback khi context bị cancel
- Không truyền `x-request-timeout` header

**Regex patterns (ripgrep):**
```bash
# Tìm timeout configs
rg "timeout:\s*\d+|TIMEOUT\s*=\s*\d+" --type ts -n

# Tìm AbortController usage (đúng cách)
rg "AbortController|AbortSignal|signal:" --type ts

# Tìm context cancellation handling
rg "req\.on\('close'\|signal\.aborted\|abortSignal" --type ts

# Tìm axios timeout config
rg "axios\.create\|axiosInstance" --type ts -A 5 | grep -v "timeout"
```

### 6. Giải pháp

| Tiêu chí | Cách sai | Cách đúng |
|---------|----------|-----------|
| Timeout order | GW(5s) < A(10s) < B(30s) | GW(10s) > A(8s) > B(6s) |
| Context | Không truyền | Truyền AbortSignal / deadline |
| Cleanup | Không rollback | Rollback khi signal abort |
| Propagation | Hard-coded timeout | Decreasing timeout budget |

```typescript
import axios from 'axios'
import { Request, Response } from 'express'

// ❌ SAI: Timeout không được cấu hình đúng thứ tự
const SERVICE_A_TIMEOUT = 10_000 // 10s
const API_GATEWAY_TIMEOUT = 5_000  // 5s < A → gateway timeout trước A!

async function handleRequestBad(req: Request, res: Response): Promise<void> {
  try {
    const result = await axios.post('http://service-a/process', req.body, {
      timeout: SERVICE_A_TIMEOUT // GW đã timeout rồi, A vẫn chờ!
    })
    res.json(result.data)
  } catch (err) {
    res.status(504).json({ error: 'Gateway timeout' })
  }
}

// ✅ ĐÚNG: Decreasing timeout + AbortSignal propagation
interface RequestContext {
  requestId: string
  deadline: number // Unix timestamp
  signal: AbortSignal
}

function createRequestContext(timeoutMs: number): RequestContext & { controller: AbortController } {
  const controller = new AbortController()
  const deadline = Date.now() + timeoutMs

  // Auto-abort when deadline reached
  setTimeout(() => controller.abort(), timeoutMs)

  return {
    requestId: crypto.randomUUID(),
    deadline,
    signal: controller.signal,
    controller
  }
}

function getRemainingTimeout(ctx: RequestContext): number {
  const remaining = ctx.deadline - Date.now()
  return Math.max(0, remaining - 500) // 500ms buffer for network overhead
}

// Gateway layer (outermost - largest timeout)
async function gatewayHandler(req: Request, res: Response): Promise<void> {
  const ctx = createRequestContext(10_000) // 10s total budget

  req.on('close', () => ctx.controller.abort()) // Client disconnected

  try {
    const result = await callServiceA(req.body, ctx)
    res.json(result)
  } catch (err) {
    if ((err as Error).name === 'AbortError' || (err as Error).name === 'CanceledError') {
      res.status(504).json({ error: 'Request timeout' })
    } else {
      res.status(500).json({ error: 'Internal error' })
    }
  }
}

// Service A (middle layer - smaller timeout)
async function callServiceA(payload: unknown, ctx: RequestContext): Promise<unknown> {
  const remainingMs = getRemainingTimeout(ctx)
  if (remainingMs <= 0) throw new Error('Deadline exceeded before calling Service A')

  const response = await axios.post('http://service-a/process', payload, {
    timeout: Math.min(remainingMs, 8_000), // Cap at 8s (less than gateway's 10s)
    signal: ctx.signal, // Propagate abort signal!
    headers: {
      'x-request-id': ctx.requestId,
      'x-deadline': ctx.deadline.toString()
    }
  })

  return response.data
}

// Service B (innermost - smallest timeout)
async function callServiceB(payload: unknown, ctx: RequestContext): Promise<unknown> {
  const remainingMs = getRemainingTimeout(ctx)
  if (remainingMs <= 0) throw new Error('Deadline exceeded before calling Service B')

  // Use remaining time budget, max 6s
  const timeout = Math.min(remainingMs, 6_000)

  const controller = new AbortController()
  ctx.signal.addEventListener('abort', () => controller.abort())
  setTimeout(() => controller.abort(), timeout)

  const response = await fetch('http://service-b/execute', {
    method: 'POST',
    body: JSON.stringify(payload),
    signal: controller.signal
  })

  if (!response.ok) throw new Error(`Service B error: ${response.status}`)
  return response.json()
}

// Express middleware: extract deadline from header (when acting as downstream)
function deadlineMiddleware(req: Request, res: Response, next: NextFunction): void {
  const deadline = parseInt(req.headers['x-deadline'] as string)

  if (deadline) {
    const remainingMs = deadline - Date.now()
    if (remainingMs <= 0) {
      res.status(504).json({ error: 'Deadline already exceeded' })
      return
    }

    const controller = new AbortController()
    setTimeout(() => {
      controller.abort()
      // Cleanup in-flight operations
    }, remainingMs)

    ;(req as Request & { abortSignal: AbortSignal }).abortSignal = controller.signal
  }

  next()
}
```

### 7. Phòng ngừa

- [ ] Document timeout budget: Gateway > A > B > C (decreasing)
- [ ] Truyền AbortSignal/deadline qua tất cả service calls
- [ ] Service phải cleanup và rollback khi nhận abort signal
- [ ] Propagate `x-request-id` và `x-deadline` headers
- [ ] Test timeout scenarios: kill service giữa chừng, verify upstream behavior
- [ ] Monitor p95/p99 latency per service để tune timeout values

```javascript
// ESLint: cảnh báo khi axios call không có signal option
// "propagate-abort-signal": "warn"
```

---

## Pattern 12: Event Ordering

### 1. Tên
**Thứ Tự Sự Kiện Sai** (Event Ordering / Out-of-order Events)

### 2. Phân loại
- **Domain:** Distributed Systems / Event-driven Architecture
- **Subcategory:** Event Ordering, Consistency

### 3. Mức nghiêm trọng
🟠 **HIGH** - State không nhất quán, business logic sai do xử lý events không đúng thứ tự

### 4. Vấn đề

Trong distributed systems, events có thể arrive out-of-order do network latency, parallel processing, hoặc retry logic. Xử lý events không đúng thứ tự dẫn đến state sai: xử lý "order.cancelled" trước "order.created" → order không tồn tại để cancel.

**Ví dụ thực tế:** User tạo và hủy order nhanh chóng. "cancelled" event đến trước "created" event do retry → hệ thống không tìm thấy order để cancel, order cuối cùng vẫn ở trạng thái "active".

```
OUT-OF-ORDER EVENTS:

Timeline thực tế:      t=1 order.created
                       t=2 order.cancelled

Network delivery:      t=5 order.cancelled  ←── đến trước!
                       t=8 order.created    ←── đến sau

Consumer xử lý:
  t=5: Process "cancelled" → Order not found! (skip)
  t=8: Process "created"   → Order created with status ACTIVE
                             ← BUG: đáng lẽ phải CANCELLED!

GIẢI PHÁP (Sequence Number + Out-of-order Buffer):

  t=5: Nhận "cancelled" (seq=2) → seq=1 chưa xử lý → buffer
  t=8: Nhận "created"   (seq=1) → xử lý seq=1 (created)
                                → xử lý seq=2 từ buffer (cancelled)
                                → Final state: CANCELLED ✓
```

### 5. Phát hiện trong mã nguồn

**Dấu hiệu nhận biết:**
- Event handler không check sequence number / timestamp order
- Consumer không có out-of-order buffer
- Multiple consumer instances xử lý cùng partition (Kafka)
- Không có idempotency check kết hợp sequence number

**Regex patterns (ripgrep):**
```bash
# Tìm event handler không check ordering
rg "on\('.*event'\|addEventListener\|\.subscribe" --type ts -A 10 | grep -v "seq\|sequence\|order\|version"

# Tìm event với timestamp nhưng không sort
rg "event\.timestamp|createdAt|\.timestamp" --type ts -B 2 -A 5

# Tìm Kafka consumer group config (ordering đảm bảo per partition)
rg "partitions\|partition\|groupId" --type ts -A 5

# Tìm sequence number tracking
rg "sequence\|lastSeq\|expectedSeq\|version" --type ts
```

### 6. Giải pháp

| Tiêu chí | Cách sai | Cách đúng |
|---------|----------|-----------|
| Processing | Xử lý ngay khi nhận | Check sequence, buffer nếu out-of-order |
| State update | Overwrite | Version check (optimistic locking) |
| Kafka | Multiple consumer threads per partition | 1 consumer per partition |
| Event design | Không có sequence | Sequence number + aggregateId |

```typescript
// ❌ SAI: Xử lý event ngay, không check ordering
async function processOrderEventBad(event: OrderEvent): Promise<void> {
  if (event.type === 'order.created') {
    await db.insert('orders', { id: event.orderId, status: 'ACTIVE' })
  } else if (event.type === 'order.cancelled') {
    // Nếu đến trước order.created → order không tồn tại!
    await db.update('orders', event.orderId, { status: 'CANCELLED' })
  }
}

// ✅ ĐÚNG: Sequence number + out-of-order buffer
interface OrderEvent {
  aggregateId: string  // orderId
  sequence: number     // monotonically increasing per aggregate
  type: 'order.created' | 'order.updated' | 'order.cancelled'
  payload: unknown
  timestamp: number
}

class OrderEventProcessor {
  // Buffer: aggregateId → sorted pending events
  private pendingEvents = new Map<string, OrderEvent[]>()
  // Last processed sequence per aggregate
  private lastProcessed = new Map<string, number>()

  async processEvent(event: OrderEvent): Promise<void> {
    const { aggregateId, sequence } = event
    const lastSeq = this.lastProcessed.get(aggregateId) ?? 0

    if (sequence <= lastSeq) {
      // Duplicate or already processed
      console.warn(`Duplicate event seq=${sequence} for ${aggregateId}, skipping`)
      return
    }

    if (sequence !== lastSeq + 1) {
      // Out-of-order: buffer for later
      console.warn(`Out-of-order event seq=${sequence} (expected ${lastSeq + 1}) for ${aggregateId}`)
      this.bufferEvent(event)
      return
    }

    // Process in-order event
    await this.applyEvent(event)
    this.lastProcessed.set(aggregateId, sequence)

    // Process buffered events that are now in-order
    await this.flushBuffer(aggregateId)
  }

  private bufferEvent(event: OrderEvent): void {
    const buffer = this.pendingEvents.get(event.aggregateId) ?? []
    buffer.push(event)
    buffer.sort((a, b) => a.sequence - b.sequence)
    this.pendingEvents.set(event.aggregateId, buffer)
  }

  private async flushBuffer(aggregateId: string): Promise<void> {
    const buffer = this.pendingEvents.get(aggregateId) ?? []
    const lastSeq = this.lastProcessed.get(aggregateId) ?? 0

    while (buffer.length > 0 && buffer[0].sequence === lastSeq + 1) {
      const nextEvent = buffer.shift()!
      await this.applyEvent(nextEvent)
      this.lastProcessed.set(aggregateId, nextEvent.sequence)
    }

    if (buffer.length === 0) {
      this.pendingEvents.delete(aggregateId)
    } else {
      this.pendingEvents.set(aggregateId, buffer)
    }
  }

  private async applyEvent(event: OrderEvent): Promise<void> {
    switch (event.type) {
      case 'order.created':
        await db.insert('orders', {
          id: event.aggregateId,
          status: 'ACTIVE',
          version: event.sequence
        })
        break

      case 'order.cancelled':
        // Optimistic locking: chỉ update nếu version đúng
        const updated = await db.updateWhere('orders',
          { id: event.aggregateId, version: event.sequence - 1 },
          { status: 'CANCELLED', version: event.sequence }
        )
        if (!updated) {
          throw new Error(`Optimistic lock failed for order ${event.aggregateId}`)
        }
        break
    }
  }
}

// ✅ NÂNG CAO: Kafka - đảm bảo ordering per partition
// Dùng aggregateId làm partition key → same order luôn đến same partition
async function produceOrderEvent(event: OrderEvent): Promise<void> {
  await kafkaProducer.send({
    topic: 'order-events',
    messages: [{
      key: event.aggregateId, // Partition key = orderId
      value: JSON.stringify(event),
      headers: { sequence: event.sequence.toString() }
    }]
  })
}

// Kafka consumer: 1 consumer per partition → ordering guaranteed
const consumer = kafka.consumer({ groupId: 'order-processor' })

await consumer.subscribe({ topic: 'order-events' })
await consumer.run({
  eachMessage: async ({ message }) => {
    const event = JSON.parse(message.value!.toString()) as OrderEvent
    await processor.processEvent(event)
  }
  // eachMessage processes messages sequentially within a partition
})
```

### 7. Phòng ngừa

- [ ] Thêm sequence number vào mọi event (per aggregate)
- [ ] Implement out-of-order buffer với timeout để release stuck events
- [ ] Dùng aggregateId làm Kafka partition key để đảm bảo ordering
- [ ] Implement optimistic locking (version field) trong DB
- [ ] Monitor buffer size; alert khi events stuck quá lâu
- [ ] Test out-of-order scenarios bằng chaos testing

```javascript
// ESLint: cảnh báo khi event handler không check sequence/version
// "require-event-sequence-check": "warn"
```

---

## Tổng kết Domain 02

| # | Pattern | Mức độ | Giải pháp chính |
|---|---------|--------|-----------------|
| 01 | Thundering Herd | HIGH | Redis mutex + TTL jitter |
| 02 | Retry Storm | CRITICAL | Exponential backoff + jitter |
| 03 | Circuit Breaker Thiếu | HIGH | opossum / custom CB |
| 04 | Distributed Lock Sai | CRITICAL | SET NX atomic + Lua release |
| 05 | Idempotency Thiếu | HIGH | Redis key + DB unique constraint |
| 06 | WebSocket Reconnect | HIGH | Cleanup listeners + backoff |
| 07 | Missing Message Ack | CRITICAL | Manual ack + DLQ |
| 08 | Pub/Sub Message Loss | HIGH | Redis Streams / Kafka |
| 09 | Rate Limit Distributed | MEDIUM | Redis sliding window |
| 10 | Sticky Session | HIGH | Redis store / JWT stateless |
| 11 | Timeout Chain | CRITICAL | Decreasing timeout + AbortSignal |
| 12 | Event Ordering | HIGH | Sequence number + buffer |

```
PRIORITY MATRIX:

CRITICAL (Fix ngay):
  ├── Retry Storm         → thêm exponential backoff + jitter
  ├── Distributed Lock    → dùng atomic SET NX + Lua
  ├── Missing Ack         → manual ack + DLQ
  └── Timeout Chain       → decreasing timeout + AbortSignal

HIGH (Fix trong sprint):
  ├── Thundering Herd     → Redis mutex
  ├── Circuit Breaker     → opossum wrapper
  ├── Idempotency         → Redis + DB constraint
  ├── WebSocket Reconnect → cleanup + backoff
  ├── Pub/Sub Loss        → Redis Streams
  ├── Sticky Session      → Redis store
  └── Event Ordering      → sequence number

MEDIUM (Backlog):
  └── Rate Limit          → Redis sliding window
```
