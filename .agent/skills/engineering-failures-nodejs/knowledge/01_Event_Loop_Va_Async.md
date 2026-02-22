# Domain 01: Vòng Lặp Sự Kiện & Bất Đồng Bộ (Event Loop & Async)

| Trường thông tin | Giá trị |
|-----------------|---------|
| **Tên miền** | Vòng Lặp Sự Kiện & Bất Đồng Bộ (Event Loop & Async) |
| **Lĩnh vực** | Node.js Runtime / Concurrency |
| **Số lượng pattern** | 18 |
| **Ngôn ngữ** | TypeScript / JavaScript |
| **Cập nhật** | 2026-02-18 |

---

## Tổng quan Event Loop Node.js

```
┌─────────────────────────────────────────────────────────────────┐
│                    NODE.JS EVENT LOOP                           │
│                                                                 │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐  │
│  │  timers  │───▶│ pending  │───▶│   idle   │───▶│   poll   │  │
│  │setTimeout│    │callbacks │    │ prepare  │    │  I/O cb  │  │
│  │setInterval    │          │    │          │    │          │  │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘  │
│       ▲                                                │        │
│       │          ┌──────────┐    ┌──────────┐         │        │
│       └──────────│  close   │◀───│  check   │◀────────┘        │
│                  │callbacks │    │setImmediat│                  │
│                  └──────────┘    └──────────┘                  │
│                                                                 │
│  Microtask Queue (ưu tiên cao nhất, chạy giữa các phase):       │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  process.nextTick()  ──▶  Promise.then()  ──▶  queueMicrotask │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Pattern 01: Event Loop Blocking

### 1. Tên
**Chặn Vòng Lặp Sự Kiện** (Event Loop Blocking)

### 2. Phân loại
- **Domain:** Event Loop / Performance
- **Subcategory:** CPU-Bound Operations, Synchronous Blocking

### 3. Mức nghiêm trọng
🔴 **CRITICAL** - Làm đóng băng toàn bộ ứng dụng, không xử lý được request mới

### 4. Vấn đề

Khi thực thi code đồng bộ nặng trong main thread, Event Loop bị chặn hoàn toàn. Node.js là single-threaded, mọi request phải chờ đợi task hiện tại hoàn thành.

**Ví dụ thực tế:** Tính toán Fibonacci, parse JSON lớn, regex phức tạp trên chuỗi lớn, vòng lặp hàng triệu phần tử.

```
TRƯỚC KHI BLOCKING:
┌──────────┐  ┌──────────┐  ┌──────────┐
│ Request 1│  │ Request 2│  │ Request 3│
│  ~10ms   │  │  ~10ms   │  │  ~10ms   │
└──────────┘  └──────────┘  └──────────┘
Tổng: 30ms

SAU KHI BLOCKING (CPU task 2000ms):
┌──────────┐  ┌────────────────────────────────────┐  ┌──────────┐
│ Request 1│  │     CPU Task (Blocking 2000ms)      │  │ Request 2│
│  ~10ms   │  │   ← Event loop FROZEN →             │  │  ~10ms   │
└──────────┘  └────────────────────────────────────┘  └──────────┘
Tổng: 2020ms  ← Request 2 phải chờ 2000ms!
```

### 5. Phát hiện trong mã nguồn

**Dấu hiệu nhận biết:**
- Vòng lặp `for/while` với hàng triệu iterations không có `await`
- Xử lý file/JSON lớn bằng `JSON.parse()` / `JSON.stringify()` đồng bộ
- Regex phức tạp trên input lớn không giới hạn
- `crypto` operations đồng bộ (`crypto.pbkdf2Sync`, `bcrypt.hashSync`)
- `fs.readFileSync` / `fs.writeFileSync` trong request handlers

**Regex patterns (ripgrep):**
```bash
# Tìm sync crypto operations
rg "pbkdf2Sync|hashSync|bcryptSync|scryptSync" --type ts --type js

# Tìm sync file operations trong handler (cần context)
rg "readFileSync|writeFileSync|existsSync|mkdirSync" --type ts --type js

# Tìm vòng lặp lớn (số > 100000)
rg "for.*[0-9]{6,}" --type ts --type js

# Tìm JSON.parse trên large data
rg "JSON\.parse\|JSON\.stringify" --type ts --type js -A 2
```

### 6. Giải pháp

| Tiêu chí | Cách sai (Blocking) | Cách đúng (Non-blocking) |
|---------|---------------------|--------------------------|
| CPU task | `fib(40)` in handler | Worker Thread |
| File I/O | `fs.readFileSync` | `fs.promises.readFile` |
| Crypto | `bcrypt.hashSync` | `bcrypt.hash` |
| Large JSON | `JSON.parse(bigStr)` | Stream parser |

```typescript
// ❌ SAI: Blocking event loop
import { createServer } from 'http'
import * as crypto from 'crypto'

function fibonacci(n: number): number {
  if (n <= 1) return n
  return fibonacci(n - 1) + fibonacci(n - 2)
}

createServer((req, res) => {
  // CHẶN EVENT LOOP ~2 giây!
  const result = fibonacci(42)
  // BLOCKING: mọi request khác phải chờ
  const hash = crypto.pbkdf2Sync('password', 'salt', 100000, 64, 'sha512')
  res.end(`${result}`)
}).listen(3000)
```

```typescript
// ✅ ĐÚNG: Sử dụng Worker Thread cho CPU-bound task
import { Worker, isMainThread, parentPort, workerData } from 'worker_threads'
import * as crypto from 'crypto'
import { createServer } from 'http'
import { promisify } from 'util'

const pbkdf2 = promisify(crypto.pbkdf2)

function runInWorker(fn: string, data: unknown): Promise<unknown> {
  return new Promise((resolve, reject) => {
    const worker = new Worker(
      `
      const { workerData, parentPort } = require('worker_threads');
      function fibonacci(n) {
        if (n <= 1) return n;
        return fibonacci(n - 1) + fibonacci(n - 2);
      }
      parentPort.postMessage(fibonacci(workerData.n));
      `,
      { eval: true, workerData: data }
    )
    worker.on('message', resolve)
    worker.on('error', reject)
  })
}

createServer(async (req, res) => {
  // ✅ Không chặn event loop - chạy trong Worker Thread
  const result = await runInWorker('fibonacci', { n: 42 })

  // ✅ Async crypto - không chặn
  const hash = await pbkdf2('password', 'salt', 100000, 64, 'sha512')

  res.end(`${result}`)
}).listen(3000)
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Tất cả crypto operations dùng async version
- [ ] File I/O dùng `fs.promises.*` thay vì `*Sync`
- [ ] CPU-bound tasks chạy trong Worker Thread Pool
- [ ] Dùng `clinic.js` hoặc `0x` để profile event loop lag
- [ ] Đặt `--max-old-space-size` phù hợp để tránh GC pause

**ESLint rules:**
```json
{
  "rules": {
    "no-restricted-syntax": [
      "error",
      {
        "selector": "CallExpression[callee.name='pbkdf2Sync']",
        "message": "Dùng pbkdf2 async thay vì pbkdf2Sync để tránh blocking"
      }
    ],
    "node/no-sync": ["warn", { "allowAtRootLevel": false }]
  }
}
```

---

## Pattern 02: Callback Hell

### 1. Tên
**Địa Ngục Callback** (Callback Hell)

### 2. Phân loại
- **Domain:** Async Patterns / Code Quality
- **Subcategory:** Nested Callbacks, Pyramid of Doom

### 3. Mức nghiêm trọng
🟡 **MEDIUM** - Gây khó đọc, khó debug, dễ gây lỗi logic và memory leak

### 4. Vấn đề

Callback lồng nhau nhiều tầng (pyramid of doom) khiến code khó đọc, khó xử lý lỗi nhất quán, và dễ quên gọi callback hoặc gọi nhiều lần.

```
Callback Hell structure:
doA(function(errA, resultA) {           ← Level 1
  if (errA) handleError(errA);
  doB(resultA, function(errB, resultB) { ← Level 2
    if (errB) handleError(errB);
    doC(resultB, function(errC, resultC) { ← Level 3
      if (errC) handleError(errC);
      doD(resultC, function(errD, resultD) { ← Level 4
        // Logic thực sự ở đây...
        // Khó maintain, khó test!
      });
    });
  });
});

Thay bằng Promise chain:
doA()
  .then(doB)    ← Flat, dễ đọc
  .then(doC)
  .then(doD)
  .catch(handleError)  ← Xử lý lỗi tập trung
```

### 5. Phát hiện trong mã nguồn

**Dấu hiệu nhận biết:**
- Hàm callback lồng nhau 3+ tầng
- Mỗi tầng có `if (err) return callback(err)`
- Xử lý lỗi không nhất quán giữa các tầng
- Biến được truyền qua nhiều closure lồng nhau

**Regex patterns (ripgrep):**
```bash
# Tìm callback lồng nhau (function trong function argument)
rg "function.*function.*function" --type js --type ts

# Tìm pattern err-first callback lồng nhau
rg "\(err,.*\{[\s\S]{0,200}\(err," --multiline --type js

# Tìm indentation sâu (dấu hiệu callback hell)
rg "^\s{24,}" --type js --type ts

# Tìm callback pattern cổ điển
rg "callback\(null," --type js --type ts -l
```

### 6. Giải pháp

| Tiêu chí | Callback Hell | Promise | Async/Await |
|---------|--------------|---------|-------------|
| Độ đọc | Khó | Trung bình | Tốt |
| Xử lý lỗi | Phân tán | `.catch()` | `try/catch` |
| Debug | Rất khó | Khó | Dễ |
| Stack trace | Không rõ | Một phần | Rõ ràng |

```typescript
// ❌ SAI: Callback Hell
import * as fs from 'fs'
import * as path from 'path'

function processUserData(userId: string, callback: (err: Error | null, result?: string) => void): void {
  fs.readFile(`users/${userId}.json`, 'utf-8', (err, userData) => {
    if (err) return callback(err)

    const user = JSON.parse(userData)
    fs.readFile(`configs/${user.configId}.json`, 'utf-8', (err2, configData) => {
      if (err2) return callback(err2)

      const config = JSON.parse(configData)
      fs.readFile(`templates/${config.templateId}.html`, 'utf-8', (err3, template) => {
        if (err3) return callback(err3)

        // Logic thực sự bị chôn vùi ở tầng 3!
        const result = template.replace('{{name}}', user.name)
        fs.writeFile(`output/${userId}.html`, result, (err4) => {
          if (err4) return callback(err4)
          callback(null, result) // Gọi callback 2 lần nếu không cẩn thận!
        })
      })
    })
  })
}
```

```typescript
// ✅ ĐÚNG: Async/Await với xử lý lỗi rõ ràng
import * as fs from 'fs/promises'

async function processUserData(userId: string): Promise<string> {
  // Flat, dễ đọc, xử lý lỗi tập trung
  const userData = await fs.readFile(`users/${userId}.json`, 'utf-8')
  const user = JSON.parse(userData)

  const configData = await fs.readFile(`configs/${user.configId}.json`, 'utf-8')
  const config = JSON.parse(configData)

  const template = await fs.readFile(`templates/${config.templateId}.html`, 'utf-8')

  const result = template.replace('{{name}}', user.name)
  await fs.writeFile(`output/${userId}.html`, result)

  return result
}

// Gọi với xử lý lỗi tập trung
async function main() {
  try {
    const result = await processUserData('user123')
    console.log('Done:', result.length, 'chars')
  } catch (error) {
    // Một nơi xử lý TẤT CẢ lỗi
    console.error('Process failed:', error)
  }
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Không lồng callback quá 2 tầng
- [ ] Promisify tất cả callback-based APIs
- [ ] Dùng `util.promisify` cho Node.js built-ins
- [ ] Xử lý lỗi tập trung bằng `try/catch` hoặc `.catch()`
- [ ] Tách logic thành các hàm async nhỏ

**ESLint rules:**
```json
{
  "rules": {
    "max-nested-callbacks": ["error", 2],
    "prefer-promise-reject-errors": "error",
    "node/prefer-promises/fs": "error",
    "node/prefer-promises/dns": "error"
  }
}
```

---

## Pattern 03: Unhandled Promise Rejection

### 1. Tên
**Promise Rejection Không Được Xử Lý** (Unhandled Promise Rejection)

### 2. Phân loại
- **Domain:** Error Handling / Promise
- **Subcategory:** Uncaught Exceptions, Process Stability

### 3. Mức nghiêm trọng
🔴 **CRITICAL** - Kể từ Node.js 15+, crash toàn bộ process. Trước đó gây silent failures và memory leak

### 4. Vấn đề

Khi một Promise bị reject mà không có `.catch()` hoặc `try/catch`, lỗi bị nuốt im lặng (Node.js <15) hoặc crash process (Node.js 15+). Đây là nguyên nhân hàng đầu gây crash production.

```
UNHANDLED REJECTION FLOW:
┌──────────────┐
│  async fn()  │──── throws error
└──────────────┘
       │
       ▼
┌──────────────┐
│   Promise    │──── rejected
└──────────────┘
       │
       ▼ (không có .catch() hay try/catch)
┌──────────────────────────────────────┐
│  Node.js <15: Silent failure         │
│  Node.js 15+: UnhandledPromiseRejection │
│  → Process EXIT (code 1)             │
└──────────────────────────────────────┘

HANDLED REJECTION FLOW:
┌──────────────┐
│  async fn()  │──── throws error
└──────────────┘
       │
       ▼
┌──────────────┐
│   Promise    │──── rejected
└──────────────┘
       │
       ▼ (.catch() hoặc try/catch)
┌──────────────┐
│ Error handler│──── log, respond, recover
└──────────────┘
```

### 5. Phát hiện trong mã nguồn

**Dấu hiệu nhận biết:**
- Gọi async function mà không `await` và không `.catch()`
- Promise chain thiếu `.catch()` ở cuối
- `async` function được gọi trong event handler không có error handling
- `Promise.all/race` không có `.catch()`

**Regex patterns (ripgrep):**
```bash
# Tìm async function calls không có await (floating promise)
rg "^\s+[a-zA-Z]+\(.*\);" --type ts --type js | grep -v "await\|return\|throw"

# Tìm Promise chain thiếu .catch
rg "\.then\(" --type ts --type js -A 5 | grep -v "catch"

# Tìm async IIFE không có catch
rg "\(async \(\)" --type ts --type js -A 3

# Tìm Promise constructor với reject không được dùng
rg "new Promise\(\(resolve\)" --type ts --type js
```

### 6. Giải pháp

| Tiêu chí | Không xử lý | Có xử lý |
|---------|-------------|----------|
| Node.js 15+ | Process crash | Graceful error |
| Node.js <15 | Silent failure | Logged error |
| Debug | Gần như không thể | Stack trace rõ |
| Recovery | Không thể | Có thể retry |

```typescript
// ❌ SAI: Nhiều dạng unhandled rejection

// Dạng 1: Floating promise
async function fetchData(url: string): Promise<void> {
  const response = await fetch(url) // Nếu fetch throw → UNHANDLED!
  const data = await response.json()
  console.log(data)
}
fetchData('https://api.example.com/data') // ← Không await, không .catch()

// Dạng 2: Promise chain thiếu .catch()
fetch('https://api.example.com/users')
  .then(res => res.json())
  .then(data => processData(data))
  // ← Không có .catch()!

// Dạng 3: async trong forEach
const userIds = ['1', '2', '3']
userIds.forEach(async (id) => {
  await deleteUser(id) // UNHANDLED nếu deleteUser throw!
})
```

```typescript
// ✅ ĐÚNG: Xử lý đầy đủ

// Dạng 1: Luôn await hoặc .catch()
async function fetchData(url: string): Promise<void> {
  try {
    const response = await fetch(url)
    if (!response.ok) throw new Error(`HTTP ${response.status}`)
    const data = await response.json()
    console.log(data)
  } catch (error) {
    console.error('fetchData failed:', error)
    throw error // Re-throw nếu caller cần biết
  }
}

// Luôn handle khi gọi
await fetchData('https://api.example.com/data').catch(err => {
  console.error('Top-level error:', err)
})

// Dạng 2: Promise chain luôn có .catch()
fetch('https://api.example.com/users')
  .then(res => {
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    return res.json()
  })
  .then(data => processData(data))
  .catch(error => {
    console.error('Fetch users failed:', error)
  })

// Dạng 3: Dùng Promise.all thay vì forEach
const userIds = ['1', '2', '3']
try {
  await Promise.all(userIds.map(id => deleteUser(id)))
} catch (error) {
  console.error('Delete failed:', error)
}

// Global safety net (không thay thế proper handling)
process.on('unhandledRejection', (reason, promise) => {
  console.error('Unhandled Rejection at:', promise, 'reason:', reason)
  process.exit(1) // Fail fast thay vì silent failure
})
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Mọi async function call đều có `await` hoặc `.catch()`
- [ ] Mọi Promise chain kết thúc bằng `.catch()`
- [ ] Đăng ký `process.on('unhandledRejection')` làm safety net
- [ ] Dùng TypeScript strict mode để phát hiện floating promises
- [ ] Test error paths của mọi async function

**ESLint rules:**
```json
{
  "rules": {
    "@typescript-eslint/no-floating-promises": "error",
    "@typescript-eslint/no-misused-promises": "error",
    "promise/catch-or-return": "error",
    "promise/no-promise-in-callback": "warn"
  }
}
```

---

## Pattern 04: Async/Await Trong Loop

### 1. Tên
**Bất Đồng Bộ Trong Vòng Lặp** (Async/Await in Loop)

### 2. Phân loại
- **Domain:** Async Patterns / Performance
- **Subcategory:** Sequential vs Parallel Execution, Loop Patterns

### 3. Mức nghiêm trọng
🟠 **HIGH** - Gây performance degradation nghiêm trọng, tăng latency theo hệ số N

### 4. Vấn đề

Dùng `await` bên trong `for...of` / `forEach` biến các operations có thể chạy song song thành tuần tự. Với N operations mỗi cái mất T ms, tổng thời gian là N*T thay vì ~T.

```
SEQUENTIAL (sai): await trong for loop
┌─────┐  ┌─────┐  ┌─────┐  ┌─────┐
│Op 1 │  │Op 2 │  │Op 3 │  │Op 4 │
│100ms│──▶│100ms│──▶│100ms│──▶│100ms│
└─────┘  └─────┘  └─────┘  └─────┘
Tổng: 400ms ← CHẬM!

PARALLEL (đúng): Promise.all
┌─────┐
│Op 1 │
│100ms│
├─────┤
│Op 2 │───▶ Tất cả chạy đồng thời
│100ms│
├─────┤
│Op 3 │
│100ms│
├─────┤
│Op 4 │
│100ms│
└─────┘
Tổng: ~100ms ← NHANH HƠN 4x!
```

### 5. Phát hiện trong mã nguồn

**Dấu hiệu nhận biết:**
- `await` bên trong `for`, `for...of`, `for...in`
- `array.forEach(async () => {...})`
- Sequential DB queries có thể chạy parallel
- N+1 query problem trong ORM

**Regex patterns (ripgrep):**
```bash
# Tìm await trong for loop
rg "for.*\{[\s\S]{0,500}await" --multiline --type ts --type js

# Tìm forEach với async callback
rg "\.forEach\(async" --type ts --type js

# Tìm for...of với await
rg "for\s+(?:const|let|var)\s+\w+\s+of" --type ts --type js -A 3

# Tìm sequential awaits trên mảng
rg "await.*\[" --type ts --type js
```

### 6. Giải pháp

| Tiêu chí | await trong loop | Promise.all | Promise batch |
|---------|-----------------|-------------|---------------|
| Tốc độ | N * T ms | ~T ms | T * ceil(N/batch) |
| Memory | Thấp | Cao (N items) | Controllable |
| Error | Dừng ở item lỗi | Fail-fast | Per-batch |
| Use case | Dependencies | Independent | Large N, rate-limit |

```typescript
// ❌ SAI: Sequential - chậm hơn N lần
async function updateAllUsers(userIds: string[]): Promise<void> {
  for (const id of userIds) {
    await updateUser(id)  // Mỗi call đợi cái trước xong
  }
}

// ❌ SAI: forEach với async không hoạt động như mong đợi
async function badForEach(items: string[]): Promise<void> {
  items.forEach(async (item) => {
    await processItem(item) // forEach không đợi promises!
  })
  // Hàm này return trước khi processItem hoàn thành!
}
```

```typescript
// ✅ ĐÚNG: Parallel với Promise.all
async function updateAllUsers(userIds: string[]): Promise<void> {
  // Tất cả chạy đồng thời
  await Promise.all(userIds.map(id => updateUser(id)))
}

// ✅ ĐÚNG: Batch processing khi cần kiểm soát concurrency
async function updateInBatches(
  userIds: string[],
  batchSize: number = 10
): Promise<void> {
  for (let i = 0; i < userIds.length; i += batchSize) {
    const batch = userIds.slice(i, i + batchSize)
    await Promise.all(batch.map(id => updateUser(id)))
    // Optional: delay giữa các batch để tránh rate limit
    if (i + batchSize < userIds.length) {
      await new Promise(resolve => setTimeout(resolve, 100))
    }
  }
}

// ✅ ĐÚNG: Concurrency limiter với p-limit
import pLimit from 'p-limit'

async function updateWithLimit(userIds: string[]): Promise<void> {
  const limit = pLimit(5) // Tối đa 5 concurrent operations
  await Promise.all(
    userIds.map(id => limit(() => updateUser(id)))
  )
}

// ✅ ĐÚNG: Khi operations thực sự phụ thuộc nhau
async function processSequential(items: string[]): Promise<string[]> {
  const results: string[] = []
  for (const item of items) {
    const prev = results.at(-1) // Dùng kết quả trước
    const result = await processWithContext(item, prev)
    results.push(result)
  }
  return results
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Review tất cả `await` trong vòng lặp - có thực sự cần sequential không?
- [ ] Dùng `Promise.all` cho independent operations
- [ ] Dùng concurrency limiter (p-limit, bottleneck) cho rate-limited APIs
- [ ] Benchmark: đo thời gian sequential vs parallel
- [ ] Tránh N+1 query trong database (dùng batch queries)

**ESLint rules:**
```json
{
  "rules": {
    "no-await-in-loop": "warn",
    "@typescript-eslint/prefer-promise-reject-errors": "error"
  }
}
```

---

## Pattern 05: Promise.all Fail-Fast

### 1. Tên
**Promise.all Dừng Tất Cả Khi Một Cái Lỗi** (Promise.all Fail-Fast)

### 2. Phân loại
- **Domain:** Promise Combinators / Error Handling
- **Subcategory:** Partial Failure, Resilience

### 3. Mức nghiêm trọng
🟠 **HIGH** - Một lỗi nhỏ có thể hủy toàn bộ batch operation, gây data inconsistency

### 4. Vấn đề

`Promise.all` reject ngay khi BẤT KỲ promise nào reject (fail-fast). Các promise đang pending tiếp tục chạy nhưng kết quả bị bỏ qua. Điều này gây ra: partial completion không được track, data inconsistency, khó retry.

```
Promise.all FAIL-FAST:
P1: ───────────────────────── ✅ (2000ms)
P2: ─────── ❌ (500ms) ← Reject ngay tại đây!
P3: ──────────────────── ✅ (1500ms, nhưng bị bỏ qua!)

Promise.all reject ở 500ms → P3 hoàn thành nhưng bị bỏ qua!

Promise.allSettled (giải pháp):
P1: ───────────────────────── ✅ fulfilled
P2: ─────── ❌ rejected
P3: ──────────────────── ✅ fulfilled

allSettled chờ TẤT CẢ → trả về [{status, value/reason}, ...]
```

### 5. Phát hiện trong mã nguồn

**Dấu hiệu nhận biết:**
- `Promise.all` với operations có thể fail independently
- Batch operations (email, notification, update nhiều records)
- Operations không phụ thuộc nhau nhưng dùng `Promise.all`
- Không kiểm tra từng kết quả của `Promise.all`

**Regex patterns (ripgrep):**
```bash
# Tìm Promise.all usage
rg "Promise\.all\(" --type ts --type js -A 5

# Tìm Promise.all mà không có allSettled
rg "Promise\.all\b" --type ts --type js | grep -v "allSettled"

# Tìm batch operations
rg "sendEmail|sendNotification|bulkUpdate" --type ts --type js -B 3 -A 10
```

### 6. Giải pháp

| Combinator | Behavior | Use When |
|-----------|---------|----------|
| `Promise.all` | Fail-fast khi có 1 reject | Tất cả phải thành công |
| `Promise.allSettled` | Chờ tất cả, trả về status | Independent operations |
| `Promise.race` | Resolve/reject với cái đầu tiên | Timeout, fastest wins |
| `Promise.any` | Resolve với cái đầu tiên thành công | Fallback, redundancy |

```typescript
// ❌ SAI: Promise.all cho operations độc lập
async function sendNotifications(userIds: string[]): Promise<void> {
  // Nếu 1 trong 1000 users có email lỗi → TẤT CẢ bị hủy!
  await Promise.all(userIds.map(id => sendEmail(id)))
}
```

```typescript
// ✅ ĐÚNG: Promise.allSettled cho operations độc lập
async function sendNotifications(userIds: string[]): Promise<{
  sent: string[]
  failed: Array<{ id: string; reason: string }>
}> {
  const results = await Promise.allSettled(
    userIds.map(async (id) => {
      await sendEmail(id)
      return id
    })
  )

  const sent: string[] = []
  const failed: Array<{ id: string; reason: string }> = []

  results.forEach((result, index) => {
    if (result.status === 'fulfilled') {
      sent.push(result.value)
    } else {
      failed.push({
        id: userIds[index],
        reason: result.reason instanceof Error
          ? result.reason.message
          : String(result.reason)
      })
    }
  })

  // Log failures nhưng không throw
  if (failed.length > 0) {
    console.error(`${failed.length}/${userIds.length} notifications failed`, failed)
  }

  return { sent, failed }
}

// ✅ ĐÚNG: Promise.all khi tất cả PHẢI thành công (transaction-like)
async function createUserWithProfile(data: UserData): Promise<User> {
  // Nếu bất kỳ step nào fail → rollback tất cả → dùng Promise.all
  const [user, profile, settings] = await Promise.all([
    createUser(data),
    createProfile(data),
    createSettings(data),
  ])
  return { ...user, profile, settings }
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Xác định: operations có độc lập không? → `allSettled`
- [ ] Xác định: tất cả phải thành công? → `Promise.all`
- [ ] Log và track partial failures
- [ ] Implement retry logic cho failed operations
- [ ] Consider idempotency cho retry safety

**ESLint rules:**
```json
{
  "rules": {
    "promise/no-promise-in-callback": "warn",
    "promise/always-return": "error"
  }
}
```

---

## Pattern 06: Floating Promise

### 1. Tên
**Promise Lơ Lửng** (Floating Promise)

### 2. Phân loại
- **Domain:** Promise / Error Handling
- **Subcategory:** Fire-and-Forget, Untracked Async

### 3. Mức nghiêm trọng
🟠 **HIGH** - Gây unhandled rejection, memory leak, và race conditions khó debug

### 4. Vấn đề

"Floating promise" là promise được tạo ra nhưng không được `await`, không có `.catch()`, và không được lưu vào biến để track. Kết quả là errors bị nuốt, và không biết khi nào operation hoàn thành.

```
FLOATING PROMISE:
┌──────────────────────────────────────┐
│  function handler() {                │
│    someAsyncOp()  ← FLOATING!        │
│    //  ↑ promise được tạo nhưng      │
│    //    không được track            │
│    return response  ← Return ngay!   │
│  }                                   │
└──────────────────────────────────────┘
                │
                ▼
┌──────────────────────────────────────┐
│  500ms sau: someAsyncOp() throw!     │
│  → UnhandledRejection hoặc           │
│  → Silent failure                   │
│  → Response đã gửi rồi, không thể   │
│    báo lỗi cho client               │
└──────────────────────────────────────┘
```

### 5. Phát hiện trong mã nguồn

**Dấu hiệu nhận biết:**
- Gọi async function không có `await` ở đầu dòng
- `async` trong event listeners mà không wrap
- Promise-returning function trong middleware không được handled
- `setTimeout`/`setInterval` callbacks với async operations

**Regex patterns (ripgrep):**
```bash
# Tìm statement-level async calls (không await, không assign)
rg "^\s+(?!await|return|const|let|var|throw)[a-zA-Z_$][a-zA-Z0-9_$.]*\([^)]*\);" --type ts --type js

# Tìm async function calls trong event handlers
rg "on\(['\"].*['\"],\s*async" --type ts --type js

# Tìm setTimeout với async
rg "setTimeout\(async" --type ts --type js

# Tìm potential floating promises
rg "^\s+[a-zA-Z]+\.[a-zA-Z]+\(.*\)$" --type ts --type js
```

### 6. Giải pháp

| Pattern | Vấn đề | Giải pháp |
|--------|--------|----------|
| `fn()` không await | Floating | `await fn()` hoặc `void fn()` explicit |
| `arr.forEach(async)` | Untracked | `await Promise.all(arr.map(async))` |
| `on('event', async)` | Unhandled rejection | Wrap với error handler |
| Fire-and-forget intentional | Floating | `void fn().catch(logger.error)` |

```typescript
// ❌ SAI: Nhiều dạng floating promise
class UserService {
  async updateUser(id: string, data: UserData): Promise<void> {
    await this.db.update(id, data)

    // FLOATING: không await, không catch, không void
    this.emailService.sendUpdateNotification(id)  // ← FLOATING!
    this.auditLog.record('update', id)            // ← FLOATING!
    this.cache.invalidate(`user:${id}`)           // ← FLOATING!
  }
}

// ❌ SAI: async forEach
eventEmitter.on('data', async (event) => {
  processEvent(event)  // ← FLOATING trong async context!
})
```

```typescript
// ✅ ĐÚNG: Explicit về intent

class UserService {
  async updateUser(id: string, data: UserData): Promise<void> {
    await this.db.update(id, data)

    // Option 1: Await tất cả (user phải chờ)
    await Promise.all([
      this.emailService.sendUpdateNotification(id),
      this.auditLog.record('update', id),
      this.cache.invalidate(`user:${id}`),
    ])

    // Option 2: Fire-and-forget EXPLICIT với error handling
    void this.emailService.sendUpdateNotification(id)
      .catch(err => this.logger.error('Email notification failed', err))

    void this.cache.invalidate(`user:${id}`)
      .catch(err => this.logger.warn('Cache invalidation failed', err))

    // Option 3: Background queue (production preferred)
    this.queue.enqueue('send-notification', { userId: id })
  }
}

// ✅ ĐÚNG: Event handler với proper error handling
eventEmitter.on('data', (event) => {
  // Wrap async trong non-async handler
  processEvent(event).catch(err => {
    console.error('Event processing failed:', err)
  })
})

// ✅ ĐÚNG: Type helper để mark intentional fire-and-forget
function fireAndForget(promise: Promise<unknown>, label: string): void {
  promise.catch(err => console.error(`[FireAndForget:${label}]`, err))
}

// Sử dụng:
fireAndForget(this.cache.invalidate(key), 'cache-invalidate')
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Dùng TypeScript với `@typescript-eslint/no-floating-promises`
- [ ] Luôn explicit: `await`, `void`, hoặc assign to variable
- [ ] Fire-and-forget phải có `.catch()` logging
- [ ] Tránh `async` trong `forEach`, dùng `Promise.all + map`
- [ ] Review tất cả event handlers có async operations

**ESLint rules:**
```json
{
  "rules": {
    "@typescript-eslint/no-floating-promises": ["error", {
      "ignoreVoid": true,
      "ignoreIIFE": false
    }],
    "@typescript-eslint/no-misused-promises": ["error", {
      "checksVoidReturn": true,
      "checksConditionals": true
    }]
  }
}
```

---

## Pattern 07: Microtask Starvation

### 1. Tên
**Đói Microtask** (Microtask Starvation)

### 2. Phân loại
- **Domain:** Event Loop / Microtasks
- **Subcategory:** Infinite Queue, Starvation

### 3. Mức nghiêm trọng
🔴 **CRITICAL** - Làm đóng băng event loop vĩnh viễn, I/O callbacks không bao giờ được thực thi

### 4. Vấn đề

Microtask queue (Promise callbacks, `process.nextTick`) được xử lý đến khi RỖNG trước khi Event Loop chuyển sang phase tiếp theo. Nếu microtask tạo ra microtask mới vô tận → Event Loop không bao giờ thoát khỏi microtask phase → I/O, timers, và mọi thứ khác ĐÓNG BĂNG.

```
MICROTASK STARVATION:
┌─────────────────────────────────────────────────────────────────┐
│  Event Loop Phase: Poll (waiting for I/O)                      │
│                           │                                     │
│                           ▼                                     │
│  Microtask Queue: [P1] → [P2] → [P3] → [P4] → ... ∞          │
│                    ↑      │      │      │                       │
│                    │      │      │      │                       │
│                    └──────┴──────┴──────┘                       │
│                    Mỗi microtask tạo microtask mới!             │
│                                                                 │
│  ❌ Timers KHÔNG bao giờ được gọi                               │
│  ❌ I/O callbacks KHÔNG bao giờ được gọi                        │
│  ❌ HTTP requests KHÔNG bao giờ được xử lý                      │
│  → Server ĐÓNG BĂNG                                            │
└─────────────────────────────────────────────────────────────────┘
```

### 5. Phát hiện trong mã nguồn

**Dấu hiệu nhận biết:**
- `process.nextTick` gọi đệ quy chính nó
- Promise chain vô hạn (`.then()` luôn trả về promise mới)
- `queueMicrotask` trong vòng lặp vô hạn
- Recursive async function không có base case rõ ràng

**Regex patterns (ripgrep):**
```bash
# Tìm nextTick gọi chính nó
rg "nextTick.*nextTick|nextTick\([^)]*\)" --type ts --type js -A 5

# Tìm recursive async patterns
rg "async function \w+.*\{[\s\S]{0,500}\1" --multiline --type ts

# Tìm queueMicrotask usage
rg "queueMicrotask" --type ts --type js -A 5

# Tìm infinite while loop với await
rg "while\s*\(true\)[\s\S]{0,200}await" --multiline --type ts --type js
```

### 6. Giải pháp

| Tình huống | Microtask (SAI) | Macrotask (ĐÚNG) |
|-----------|----------------|-----------------|
| Polling | `nextTick` loop | `setInterval` |
| Recursive async | Unlimited recursion | Depth limit + `setImmediate` |
| Event processing | Microtask chain | `setImmediate` between batches |
| Yielding | `process.nextTick` | `setImmediate` hoặc `setTimeout(0)` |

```typescript
// ❌ SAI: Microtask starvation với nextTick đệ quy
function pollForData(): void {
  process.nextTick(() => {
    if (!hasData()) {
      pollForData()  // ← Tạo microtask mới vô hạn!
    }
  })
  // Event loop không bao giờ thoát khỏi microtask phase!
}

// ❌ SAI: Promise chain vô hạn
async function infiniteProcessor(): Promise<void> {
  await processOne()
  return infiniteProcessor()  // ← Microtask recursion!
}
```

```typescript
// ✅ ĐÚNG: Dùng setImmediate/setTimeout để yield cho event loop
function pollForData(): void {
  setImmediate(() => {  // ← Macrotask, event loop có thể xử lý I/O
    if (!hasData()) {
      pollForData()
    }
  })
}

// ✅ ĐÚNG: Infinite processor với yield point
async function infiniteProcessor(): Promise<void> {
  while (true) {
    await processOne()

    // Yield để event loop xử lý I/O và timers
    await new Promise<void>(resolve => setImmediate(resolve))

    // Hoặc: setTimeout(resolve, 0) nếu cần delay
  }
}

// ✅ ĐÚNG: Batched processing với yield
async function processBatch(items: string[]): Promise<void> {
  const YIELD_EVERY = 100 // Yield mỗi 100 items

  for (let i = 0; i < items.length; i++) {
    await processItem(items[i])

    if (i % YIELD_EVERY === 0 && i !== 0) {
      // Yield cho event loop
      await new Promise<void>(resolve => setImmediate(resolve))
    }
  }
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Tránh `process.nextTick` đệ quy - dùng `setImmediate` thay
- [ ] Infinite loops phải có `await setImmediate()` yield points
- [ ] Giới hạn độ sâu đệ quy async
- [ ] Monitor event loop lag bằng `perf_hooks`
- [ ] Alert khi event loop lag > 100ms

**ESLint rules:**
```json
{
  "rules": {
    "no-restricted-globals": [
      "error",
      {
        "name": "queueMicrotask",
        "message": "Cân nhắc dùng setImmediate để tránh microtask starvation"
      }
    ]
  }
}
```

---

## Pattern 08: Timer Drift

### 1. Tên
**Trượt Thời Gian Timer** (Timer Drift)

### 2. Phân loại
- **Domain:** Timers / Precision
- **Subcategory:** Scheduling, Timing Accuracy

### 3. Mức nghiêm trọng
🟡 **MEDIUM** - Gây incorrect scheduling, data inconsistency trong time-sensitive operations

### 4. Vấn đề

`setInterval` không đảm bảo chính xác thời gian. Nếu callback mất nhiều thời gian hơn interval, các callbacks bị stack up. Thêm vào đó, event loop blocking gây ra timer drift tích lũy theo thời gian.

```
TIMER DRIFT:
Target: mỗi 1000ms một lần

Thực tế với event loop blocking:
0ms    ┤──── callback 1 (50ms) ────┤
1000ms ┤──── callback 2 (200ms) ──────────┤
2000ms ┤── callback 3 gọi trễ 200ms ──┤  ← DRIFT!
3200ms ┤────── callback 4 ─────────────────┤ ← Drift tích lũy!

Drift tích lũy = Σ(processing_time) qua thời gian
→ Schedule bị lệch ngày càng nhiều
```

### 5. Phát hiện trong mã nguồn

**Dấu hiệu nhận biết:**
- `setInterval` với callbacks có thể mất thời gian khác nhau
- Không có drift compensation
- Cron jobs dựa trên `setInterval` cho precision-sensitive tasks
- Không check nếu previous callback đang chạy

**Regex patterns (ripgrep):**
```bash
# Tìm setInterval usage
rg "setInterval\(" --type ts --type js -A 10

# Tìm setInterval với async callback
rg "setInterval\(async" --type ts --type js

# Tìm potential drift không được compensate
rg "setInterval\([^,]+,\s*[0-9]+" --type ts --type js
```

### 6. Giải pháp

| Approach | Drift | Overlap | Use Case |
|---------|-------|---------|----------|
| `setInterval` | Có | Có | Simple, non-critical |
| Adaptive `setTimeout` | Không | Không | Precision scheduling |
| `setTimeout` + measure | Compensated | Không | Medium precision |
| External cron (node-cron) | Không | Configurable | Production jobs |

```typescript
// ❌ SAI: setInterval không compensate drift
class DataPoller {
  start(): void {
    setInterval(async () => {
      // Nếu fetchData mất 800ms và interval là 1000ms
      // → effective interval chỉ còn 200ms!
      await this.fetchData()
    }, 1000)
  }
}
```

```typescript
// ✅ ĐÚNG: Adaptive setTimeout với drift compensation
class DataPoller {
  private isRunning = false
  private readonly intervalMs: number

  constructor(intervalMs: number = 1000) {
    this.intervalMs = intervalMs
  }

  async start(): Promise<void> {
    this.isRunning = true
    await this.scheduleNext(0)
  }

  private async scheduleNext(elapsedMs: number): Promise<void> {
    if (!this.isRunning) return

    const delay = Math.max(0, this.intervalMs - elapsedMs)
    await new Promise(resolve => setTimeout(resolve, delay))

    if (!this.isRunning) return

    const start = Date.now()
    try {
      await this.fetchData()
    } catch (error) {
      console.error('Poll failed:', error)
    }
    const elapsed = Date.now() - start

    // Compensate drift: trừ thời gian đã mất
    await this.scheduleNext(elapsed)
  }

  stop(): void {
    this.isRunning = false
  }

  private async fetchData(): Promise<void> {
    // Implementation
  }
}

// ✅ ĐÚNG: Kiểm tra overlap cho long-running tasks
class SafePoller {
  private isProcessing = false

  start(): void {
    setInterval(async () => {
      if (this.isProcessing) {
        console.warn('Previous poll still running, skipping')
        return
      }
      this.isProcessing = true
      try {
        await this.heavyTask()
      } finally {
        this.isProcessing = false
      }
    }, 5000)
  }
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Dùng adaptive `setTimeout` thay vì `setInterval` cho precision tasks
- [ ] Implement overlap detection cho long-running callbacks
- [ ] Dùng `node-cron` hoặc external scheduler cho cron jobs
- [ ] Monitor actual vs expected execution times
- [ ] Log drift metrics trong production

**ESLint rules:**
```json
{
  "rules": {
    "no-restricted-globals": [
      "warn",
      {
        "name": "setInterval",
        "message": "Cân nhắc dùng adaptive setTimeout để tránh timer drift"
      }
    ]
  }
}
```

---

## Pattern 09: Async Constructor

### 1. Tên
**Constructor Bất Đồng Bộ** (Async Constructor)

### 2. Phân loại
- **Domain:** OOP Patterns / Async
- **Subcategory:** Initialization, Class Design

### 3. Mức nghiêm trọng
🟡 **MEDIUM** - Gây object ở trạng thái chưa sẵn sàng, dẫn đến race conditions và errors khó debug

### 4. Vấn đề

JavaScript constructors không thể là `async`. Nếu object cần async initialization (kết nối DB, load config), nhiều developer cố gắng dùng patterns không an toàn như gọi async trong constructor mà không await, hoặc dùng flag `isReady`.

```
ASYNC CONSTRUCTOR PROBLEM:
┌─────────────────────────────────────────┐
│  constructor() {                         │
│    this.init()  ← FLOATING PROMISE!     │
│  }                                       │
│                                          │
│  async init() {                          │
│    this.db = await connectDB()           │
│  }                                       │
└─────────────────────────────────────────┘
         │
         ▼
new MyService()  ← Object tạo xong
     │
     ▼
service.query()  ← this.db === undefined! CRASH!
     │
     ▼ (500ms sau)
init() hoàn thành  ← Quá muộn!
```

### 5. Phát hiện trong mã nguồn

**Dấu hiệu nhận biết:**
- `async` method được gọi trong `constructor()`
- `this.isReady` / `this.initialized` flag patterns
- `if (!this.initialized) throw` ở đầu mọi method
- Promise stored in `this.initPromise` mà không được await đúng cách

**Regex patterns (ripgrep):**
```bash
# Tìm async calls trong constructor
rg "constructor\([\s\S]{0,500}this\.\w+\(\)" --multiline --type ts --type js

# Tìm isReady/initialized patterns
rg "this\.(isReady|initialized|isInitialized)\s*=" --type ts --type js

# Tìm init methods được gọi không await trong constructor
rg "constructor\([^)]*\)\s*\{[^}]*this\.init\(\)" --type ts --type js
```

### 6. Giải pháp

| Pattern | An toàn | Rõ ràng | Testable |
|--------|--------|---------|---------|
| Async init trong constructor | Không | Không | Khó |
| Static factory method | Có | Có | Dễ |
| Builder pattern | Có | Có | Dễ |
| Lazy initialization | Có | Trung bình | Trung bình |

```typescript
// ❌ SAI: Async initialization trong constructor
class DatabaseService {
  private db!: Database

  constructor() {
    // NGUY HIỂM: floating promise, db có thể chưa sẵn sàng!
    this.initialize()
  }

  private async initialize(): Promise<void> {
    this.db = await createConnection()
  }

  async query(sql: string): Promise<unknown[]> {
    return this.db.execute(sql)  // db có thể undefined!
  }
}

const service = new DatabaseService()
await service.query('SELECT 1')  // Race condition!
```

```typescript
// ✅ ĐÚNG: Static factory method pattern
class DatabaseService {
  private constructor(private readonly db: Database) {}

  // Factory method - duy nhất cách tạo instance
  static async create(config: DbConfig): Promise<DatabaseService> {
    const db = await createConnection(config)
    return new DatabaseService(db)
  }

  async query(sql: string): Promise<unknown[]> {
    return this.db.execute(sql)  // db LUÔN sẵn sàng
  }

  async close(): Promise<void> {
    await this.db.close()
  }
}

// Sử dụng:
const service = await DatabaseService.create(config)
const results = await service.query('SELECT 1')

// ✅ ĐÚNG: Lazy initialization pattern (cho singleton)
class LazyDatabaseService {
  private dbPromise: Promise<Database> | null = null

  private getDb(): Promise<Database> {
    if (!this.dbPromise) {
      this.dbPromise = createConnection(this.config)
    }
    return this.dbPromise
  }

  async query(sql: string): Promise<unknown[]> {
    const db = await this.getDb()  // Khởi tạo lần đầu tiên
    return db.execute(sql)
  }
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Không bao giờ gọi async methods trong constructor
- [ ] Dùng static factory methods cho async initialization
- [ ] Hoặc lazy initialization pattern cho singleton services
- [ ] Đảm bảo constructor chỉ làm synchronous setup
- [ ] Document rõ ràng cách khởi tạo class

**ESLint rules:**
```json
{
  "rules": {
    "@typescript-eslint/no-floating-promises": "error"
  }
}
```

---

## Pattern 10: EventEmitter Memory Leak

### 1. Tên
**Rò Rỉ Bộ Nhớ EventEmitter** (EventEmitter Memory Leak)

### 2. Phân loại
- **Domain:** EventEmitter / Memory Management
- **Subcategory:** Listener Accumulation, Resource Cleanup

### 3. Mức nghiêm trọng
🟠 **HIGH** - Gây memory leak dần dần, cuối cùng crash process hoặc severe performance degradation

### 4. Vấn đề

Khi add listener vào EventEmitter mà không remove khi không cần nữa, số lượng listener tăng vô hạn. Node.js warn khi > 10 listeners (MaxListenersExceededWarning) nhưng không tự remove.

```
EVENTEMITTER MEMORY LEAK:
Request 1:  emitter.on('data', handler1)  → 1 listener
Request 2:  emitter.on('data', handler2)  → 2 listeners
Request 3:  emitter.on('data', handler3)  → 3 listeners
...
Request 100: emitter.on('data', handler100) → 100 listeners!
            → MaxListenersExceededWarning
            → Memory tăng theo thời gian
            → Mỗi event gọi 100 handlers!

GC không thể collect handlers vì:
handlers → closures → references to large objects
→ Memory leak chain!
```

### 5. Phát hiện trong mã nguồn

**Dấu hiệu nhận biết:**
- `emitter.on()` trong loops hoặc request handlers mà không `off()`
- Không dùng `once()` khi chỉ cần nghe một lần
- Không cleanup trong `componentWillUnmount` / `useEffect` cleanup
- Warning: "MaxListenersExceededWarning: Possible EventEmitter memory leak"

**Regex patterns (ripgrep):**
```bash
# Tìm emitter.on mà không có cleanup
rg "\.on\(['\"]" --type ts --type js -B 5 -A 5 | grep -v "off\|removeListener\|once"

# Tìm setMaxListeners (thường dùng để hide leak thay vì fix)
rg "setMaxListeners" --type ts --type js

# Tìm EventEmitter patterns trong classes
rg "extends EventEmitter|new EventEmitter" --type ts --type js -A 20

# Tìm potential listener accumulation
rg "\.on\(" --type ts --type js | wc -l
```

### 6. Giải pháp

| Technique | When to Use |
|----------|-------------|
| `emitter.once()` | Nghe một lần duy nhất |
| `emitter.off()` / `removeListener()` | Cleanup khi không cần |
| WeakRef cho handlers | Handler cần GC khi object bị GC |
| `AbortSignal` | Cancel listener theo signal |

```typescript
// ❌ SAI: Listener accumulation
class ConnectionManager {
  private emitter = new EventEmitter()

  handleRequest(): void {
    // Mỗi request add một listener mới, không bao giờ remove!
    this.emitter.on('data', (data) => {
      this.processData(data)
    })
  }
}
```

```typescript
// ✅ ĐÚNG: Proper cleanup với AbortController pattern
class ConnectionManager {
  private emitter = new EventEmitter()

  handleRequest(signal?: AbortSignal): void {
    const handler = (data: unknown) => {
      this.processData(data)
    }

    this.emitter.on('data', handler)

    // Cleanup khi done
    const cleanup = () => {
      this.emitter.off('data', handler)
    }

    if (signal) {
      signal.addEventListener('abort', cleanup, { once: true })
    }

    // Return cleanup function
    return cleanup
  }

  // ✅ ĐÚNG: Dùng once() khi chỉ cần 1 lần
  waitForConnection(): Promise<void> {
    return new Promise((resolve, reject) => {
      this.emitter.once('connected', resolve)   // Tự remove sau khi gọi!
      this.emitter.once('error', reject)         // Tự remove sau khi gọi!

      // Timeout để tránh leak nếu event không bao giờ fire
      const timeout = setTimeout(() => {
        this.emitter.off('connected', resolve)
        this.emitter.off('error', reject)
        reject(new Error('Connection timeout'))
      }, 30_000)

      // Cleanup timeout khi event fire
      this.emitter.once('connected', () => clearTimeout(timeout))
    })
  }
}

// ✅ ĐÚNG: React/Node.js cleanup pattern
class ServiceWithCleanup {
  private readonly listeners = new Map<string, (...args: unknown[]) => void>()

  attach(emitter: EventEmitter): void {
    const dataHandler = (data: unknown) => this.onData(data)
    const errorHandler = (err: Error) => this.onError(err)

    emitter.on('data', dataHandler)
    emitter.on('error', errorHandler)

    // Track để cleanup
    this.listeners.set('data', dataHandler)
    this.listeners.set('error', errorHandler)
  }

  detach(emitter: EventEmitter): void {
    for (const [event, handler] of this.listeners) {
      emitter.off(event, handler)
    }
    this.listeners.clear()
  }
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Mọi `on()` phải có `off()` tương ứng trong cleanup
- [ ] Dùng `once()` khi chỉ cần nghe một lần
- [ ] Track tất cả listeners trong class để cleanup trong destructor
- [ ] Đặt `emitter.setMaxListeners(n)` hợp lý và có chủ ý
- [ ] Monitor process memory và listener counts

**ESLint rules:**
```json
{
  "rules": {
    "no-restricted-syntax": [
      "warn",
      {
        "selector": "CallExpression[callee.property.name='setMaxListeners'][arguments.0.value=0]",
        "message": "setMaxListeners(0) disable warnings thay vì fix leak thực sự"
      }
    ]
  }
}
```

---

## Pattern 11: Stream Backpressure Bỏ Qua

### 1. Tên
**Bỏ Qua Áp Lực Ngược Luồng** (Stream Backpressure Ignored)

### 2. Phân loại
- **Domain:** Streams / Memory Management
- **Subcategory:** Data Flow, Buffer Overflow

### 3. Mức nghiêm trọng
🟠 **HIGH** - Gây out-of-memory crash khi source nhanh hơn destination

### 4. Vấn đề

Streams có cơ chế backpressure để kiểm soát tốc độ: destination báo source "chậm lại" khi buffer đầy. Bỏ qua signal này gây buffer overflow và OOM crash.

```
BACKPRESSURE IGNORED:
Fast Source ──────▶ Buffer ──────▶ Slow Destination
  1GB/s              ↑              100MB/s
                 OVERFLOW!
                 (900MB/s tích lũy)
                 → OOM crash

WITH BACKPRESSURE:
Fast Source ──▶ Buffer ──▶ Slow Destination
  wait!          OK         100MB/s
   ↑─────────────────────────┘
   drain event signals "ready for more"
```

### 5. Phát hiện trong mã nguồn

**Dấu hiệu nhận biết:**
- Ignore return value của `stream.write()` (nên check `false`)
- Không listen `drain` event sau khi `write()` returns `false`
- Không dùng `pipe()` (pipe tự handle backpressure)
- Manual `push()` vào readable stream không check `highWaterMark`

**Regex patterns (ripgrep):**
```bash
# Tìm stream.write không check return value
rg "\.write\(" --type ts --type js | grep -v "if\|=\|return\|await"

# Tìm streams mà không có pipe hoặc drain handler
rg "createReadStream|createWriteStream" --type ts --type js -A 20 | grep -v "pipe\|drain"

# Tìm manual write trong loop
rg "for.*\{[\s\S]{0,200}\.write\(" --multiline --type ts --type js
```

### 6. Giải pháp

| Approach | Backpressure | Complexity |
|---------|-------------|-----------|
| Manual write/drain | Manual | Cao |
| `stream.pipe()` | Automatic | Thấp |
| `stream.pipeline()` | Automatic + cleanup | Thấp |
| Async iterator | Natural | Trung bình |

```typescript
// ❌ SAI: Bỏ qua backpressure
import * as fs from 'fs'

const readable = fs.createReadStream('huge-file.txt')
const writable = fs.createWriteStream('output.txt')

readable.on('data', (chunk) => {
  writable.write(chunk)  // Không check return! Buffer có thể overflow!
})
```

```typescript
// ✅ ĐÚNG: Dùng pipeline (recommended)
import { pipeline } from 'stream/promises'
import * as fs from 'fs'
import { Transform } from 'stream'
import * as zlib from 'zlib'

async function processFile(input: string, output: string): Promise<void> {
  // pipeline tự handle backpressure VÀ cleanup khi error!
  await pipeline(
    fs.createReadStream(input),
    zlib.createGzip(),
    fs.createWriteStream(output)
  )
}

// ✅ ĐÚNG: Manual write với backpressure handling
async function writeWithBackpressure(
  writable: NodeJS.WritableStream,
  data: Buffer
): Promise<void> {
  const canContinue = writable.write(data)

  if (!canContinue) {
    // Chờ drain signal trước khi write thêm
    await new Promise<void>((resolve, reject) => {
      writable.once('drain', resolve)
      writable.once('error', reject)
    })
  }
}

// ✅ ĐÚNG: Async iterator (Node.js 10+)
async function processStream(
  readable: NodeJS.ReadableStream,
  writable: NodeJS.WritableStream
): Promise<void> {
  for await (const chunk of readable) {
    await writeWithBackpressure(writable, chunk as Buffer)
  }
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Luôn dùng `stream.pipeline()` thay vì manual pipe
- [ ] Nếu manual write, check return value và xử lý `drain`
- [ ] Set `highWaterMark` phù hợp với memory constraints
- [ ] Monitor stream buffer size trong production
- [ ] Test với large data để verify backpressure hoạt động

**ESLint rules:**
```json
{
  "rules": {
    "no-restricted-syntax": [
      "warn",
      {
        "selector": "CallExpression[callee.property.name='pipe']",
        "message": "Cân nhắc dùng stream.pipeline() thay vì .pipe() để có error handling và backpressure tốt hơn"
      }
    ]
  }
}
```

---

## Pattern 12: Race Condition Async

### 1. Tên
**Điều Kiện Tranh Đua Bất Đồng Bộ** (Async Race Condition)

### 2. Phân loại
- **Domain:** Concurrency / State Management
- **Subcategory:** Shared State, Non-deterministic Order

### 3. Mức nghiêm trọng
🟠 **HIGH** - Gây data corruption, inconsistent state, bugs chỉ xuất hiện intermittently

### 4. Vấn đề

Race condition xảy ra khi nhiều async operations đọc và ghi shared state mà không có synchronization. Kết quả phụ thuộc vào thứ tự hoàn thành không xác định.

```
RACE CONDITION:
Thời gian:  0ms    50ms   100ms  150ms  200ms

Op A (read): ┤──── read(counter=0) ────▶│
                                         │── write(counter=1) ──▶│
Op B (read): ┤──────────── read(counter=0) ──────────────────────▶│
                                                                    │── write(counter=1) ──▶│

Kết quả mong đợi: counter = 2
Kết quả thực tế:  counter = 1  ← LOST UPDATE!

Bước A đọc 0, tính 0+1=1, ghi 1
Bước B đọc 0 (trước khi A ghi), tính 0+1=1, ghi 1 → OVERWRITE!
```

### 5. Phát hiện trong mã nguồn

**Dấu hiệu nhận biết:**
- Đọc giá trị, tính toán, ghi lại mà không atomic
- Shared mutable state được access từ nhiều async operations
- Test fails intermittently (flaky tests)
- Bugs chỉ xuất hiện dưới load cao

**Regex patterns (ripgrep):**
```bash
# Tìm read-modify-write patterns
rg "await.*read|await.*get[\s\S]{0,200}await.*write|await.*set|await.*update" --multiline --type ts --type js

# Tìm shared state modification
rg "this\.\w+\s*[+\-]?=|this\.\w+\+\+|this\.\w+--" --type ts --type js

# Tìm concurrent state access
rg "Promise\.all[\s\S]{0,500}this\.\w+" --multiline --type ts --type js
```

### 6. Giải pháp

| Mechanism | Use Case | Overhead |
|----------|---------|---------|
| Mutex/Lock | General purpose | Thấp |
| Atomic operations | Counter, flag | Rất thấp |
| Database transactions | DB state | Trung bình |
| Redis WATCH | Distributed | Cao |
| Message queue | Serialization | Cao |

```typescript
// ❌ SAI: Race condition trên shared counter
class Counter {
  private value = 0

  async increment(): Promise<void> {
    const current = await this.getValue()  // Read: 0
    await delay(10)  // Simulate async work
    await this.setValue(current + 1)  // Write: 1 (lost update nếu concurrent!)
  }
}

// Concurrent: 2 calls cùng lúc
counter.increment()  // Reads 0, writes 1
counter.increment()  // Reads 0 (before first writes!), writes 1
// Result: 1 thay vì 2!
```

```typescript
// ✅ ĐÚNG: Mutex để serialize access
class Mutex {
  private queue: Array<() => void> = []
  private locked = false

  async acquire(): Promise<() => void> {
    return new Promise((resolve) => {
      const tryLock = () => {
        if (!this.locked) {
          this.locked = true
          resolve(() => this.release())
        } else {
          this.queue.push(tryLock)
        }
      }
      tryLock()
    })
  }

  private release(): void {
    const next = this.queue.shift()
    if (next) {
      next()
    } else {
      this.locked = false
    }
  }
}

class SafeCounter {
  private value = 0
  private mutex = new Mutex()

  async increment(): Promise<void> {
    const release = await this.mutex.acquire()
    try {
      const current = await this.getValue()
      await delay(10)
      await this.setValue(current + 1)
    } finally {
      release()  // LUÔN release, kể cả khi có exception
    }
  }
}

// ✅ ĐÚNG: Atomic database operation
class DatabaseCounter {
  async increment(id: string): Promise<number> {
    // Atomic: read-modify-write trong một transaction
    const result = await this.db.query(
      'UPDATE counters SET value = value + 1 WHERE id = $1 RETURNING value',
      [id]
    )
    return result.rows[0].value
  }
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Identify tất cả shared mutable state
- [ ] Dùng database transactions cho state cần atomicity
- [ ] Implement mutex/lock cho in-process shared state
- [ ] Prefer immutable patterns và event sourcing
- [ ] Load test để phát hiện race conditions

**ESLint rules:**
```json
{
  "rules": {
    "require-atomic-updates": "error"
  }
}
```

---

## Pattern 13: Zalgo (Sync/Async Inconsistency)

### 1. Tên
**Zalgo - Bất Nhất Giữa Đồng Bộ và Bất Đồng Bộ** (Zalgo: Sync/Async Inconsistency)

### 2. Phân loại
- **Domain:** API Design / Async
- **Subcategory:** Releasing Zalgo, Predictability

### 3. Mức nghiêm trọng
🟠 **HIGH** - Gây race conditions và bugs cực kỳ khó debug vì behavior không predictable

### 4. Vấn đề

"Releasing Zalgo" là khi một function đôi khi gọi callback synchronously và đôi khi asynchronously tùy thuộc vào điều kiện. Caller không thể biết code sau `fn()` có chạy trước hay sau callback.

```
ZALGO - UNPREDICTABLE BEHAVIOR:

fetchUser(id, callback):
  Cache hit:  callback() ← SYNC (ngay lập tức!)
  Cache miss: network request → callback() ← ASYNC (sau này)

Caller:
  state = 'before'
  fetchUser(id, (user) => {
    // Khi cache hit: 'before'  (state chưa thay đổi!)
    // Khi cache miss: 'after'  (state đã thay đổi!)
    console.log(state)  ← UNPREDICTABLE!
  })
  state = 'after'

→ Behavior khác nhau với cùng code!
→ Race condition cực kỳ khó reproduce
```

### 5. Phát hiện trong mã nguồn

**Dấu hiệu nhận biết:**
- Function có `if (cached) callback(cached)` sync và `fetch(...).then(callback)` async
- `if` condition quyết định sync hay async path
- Callback có thể được gọi từ nhiều code path khác nhau về timing

**Regex patterns (ripgrep):**
```bash
# Tìm sync callback trong if với async trong else
rg "callback\([^)]*\)[\s\S]{0,100}async\|fetch\|await" --multiline --type ts --type js

# Tìm potential Zalgo: return trong if + async sau
rg "if.*\{[^}]*callback[^}]*\}[\s\S]{0,300}callback" --multiline --type ts --type js

# Tìm mixed sync/async patterns
rg "(?:callback|resolve)\([^)]*\);\s*\n(?!.*return)" --type ts --type js
```

### 6. Giải pháp

| Rule | Description |
|------|-------------|
| Always sync | Callback luôn sync (fine nếu không có I/O) |
| Always async | Callback luôn async, dùng `process.nextTick` hoặc `Promise.resolve()` |
| Use Promise | Promise API tự handle timing predictably |

```typescript
// ❌ SAI: Zalgo - sync khi cache hit, async khi cache miss
function fetchUser(
  id: string,
  callback: (err: Error | null, user?: User) => void
): void {
  const cached = cache.get(id)
  if (cached) {
    callback(null, cached)  // SYNC! ← Zalgo released!
    return
  }

  // ASYNC
  db.findUser(id).then(user => {
    cache.set(id, user)
    callback(null, user)
  }).catch(err => callback(err))
}
```

```typescript
// ✅ ĐÚNG: Luôn async bằng cách wrap sync path
function fetchUser(
  id: string,
  callback: (err: Error | null, user?: User) => void
): void {
  const cached = cache.get(id)
  if (cached) {
    // Defer để luôn async
    process.nextTick(() => callback(null, cached))
    return
  }

  db.findUser(id).then(user => {
    cache.set(id, user)
    callback(null, user)
  }).catch(err => callback(err))
}

// ✅ TỐT NHẤT: Dùng Promise API (tự đảm bảo async)
async function fetchUser(id: string): Promise<User> {
  const cached = cache.get(id)
  if (cached) {
    return cached  // Promise.resolve(cached) - luôn microtask
  }

  const user = await db.findUser(id)
  cache.set(id, user)
  return user
}

// ✅ ĐÚNG: Đảm bảo consistent async với helper
function alwaysAsync<T>(
  value: T | Promise<T>
): Promise<T> {
  return Promise.resolve(value)
}

function fetchUserSafe(id: string): Promise<User> {
  const cached = cache.get(id)
  if (cached) {
    return alwaysAsync(cached)  // Guaranteed async
  }
  return db.findUser(id)
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Functions phải luôn sync HOẶC luôn async, không trộn lẫn
- [ ] Wrap sync paths bằng `process.nextTick()` hoặc `Promise.resolve()`
- [ ] Prefer Promise API vì tự đảm bảo async behavior
- [ ] Viết tests để verify timing (check order of operations)
- [ ] Document rõ ràng: "This function is always asynchronous"

**ESLint rules:**
```json
{
  "rules": {
    "consistent-return": "error",
    "@typescript-eslint/promise-function-async": "error"
  }
}
```

---

## Pattern 14: AbortController Thiếu

### 1. Tên
**Thiếu AbortController** (Missing AbortController)

### 2. Phân loại
- **Domain:** Async Cancellation / Resource Management
- **Subcategory:** Long-running Operations, Request Cancellation

### 3. Mức nghiêm trọng
🟡 **MEDIUM** - Gây resource waste, memory leak, và phantom operations sau khi user đã cancel

### 4. Vấn đề

Khi không implement cancellation, long-running async operations tiếp tục chạy dù không còn cần thiết (user navigation, request timeout, component unmount). Gây CPU waste, memory leak, và có thể gây side effects không mong muốn.

```
KHÔNG CÓ ABORT:
User click "Search" ──▶ Fetch starts (takes 5s)
User click "Cancel" ──▶ Fetch CONTINUES!
                        (5s sau) Response arrives
                        → Ghi vào UI đã không còn show
                        → State update cho component đã unmount
                        → Memory/CPU wasted

VỚI ABORT:
User click "Search" ──▶ Fetch starts
                         AbortController.signal passed to fetch
User click "Cancel" ──▶ controller.abort()
                        → Fetch cancelled IMMEDIATELY
                        → Network connection closed
                        → No state update
```

### 5. Phát hiện trong mã nguồn

**Dấu hiệu nhận biết:**
- `fetch()` calls không truyền `signal`
- Long-running operations (search, export, import) không có cancel mechanism
- React `useEffect` với async không cleanup
- WebSocket connections không có abort logic

**Regex patterns (ripgrep):**
```bash
# Tìm fetch mà không có signal
rg "fetch\([^)]*\)" --type ts --type js | grep -v "signal"

# Tìm useEffect với async không có cleanup
rg "useEffect\(async" --type ts --type js -A 20 | grep -v "return\|cleanup\|abort"

# Tìm long-running ops không có cancel
rg "async function.*(search|export|import|process)" --type ts --type js -A 30 | grep -v "AbortController\|signal"
```

### 6. Giải pháp

| Scenario | Solution |
|---------|---------|
| fetch requests | Pass `signal` to fetch |
| React useEffect | Create controller, abort on cleanup |
| Node.js operations | Pass signal through call chain |
| Manual cancellation | Check signal.aborted periodically |

```typescript
// ❌ SAI: Không có cancellation
async function searchUsers(query: string): Promise<User[]> {
  const response = await fetch(`/api/users?q=${query}`)
  // Nếu component unmount → response vẫn về, state update crash!
  return response.json()
}
```

```typescript
// ✅ ĐÚNG: AbortController cho fetch
async function searchUsers(
  query: string,
  signal?: AbortSignal
): Promise<User[]> {
  const response = await fetch(`/api/users?q=${query}`, { signal })

  if (!response.ok) throw new Error(`HTTP ${response.status}`)
  return response.json()
}

// ✅ ĐÚNG: React hook với proper cleanup
function useSearch(query: string) {
  const [results, setResults] = useState<User[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<Error | null>(null)

  useEffect(() => {
    if (!query) return

    const controller = new AbortController()
    setLoading(true)
    setError(null)

    searchUsers(query, controller.signal)
      .then(setResults)
      .catch(err => {
        if (err.name !== 'AbortError') {  // Ignore abort errors
          setError(err)
        }
      })
      .finally(() => setLoading(false))

    // Cleanup: abort khi query thay đổi hoặc component unmount
    return () => controller.abort()
  }, [query])

  return { results, loading, error }
}

// ✅ ĐÚNG: AbortController cho long operations
async function processLargeFile(
  filePath: string,
  signal: AbortSignal
): Promise<void> {
  const lines = await readLines(filePath)

  for (const line of lines) {
    // Check abort trước mỗi item
    if (signal.aborted) {
      throw new DOMException('Processing aborted', 'AbortError')
    }
    await processLine(line)
  }
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Tất cả fetch calls có tham số `signal`
- [ ] React effects có async operations phải cleanup với abort
- [ ] Long-running operations accept `AbortSignal` parameter
- [ ] Check `signal.aborted` trong loops dài
- [ ] Handle `AbortError` separately từ các errors khác

**ESLint rules:**
```json
{
  "rules": {
    "no-restricted-syntax": [
      "warn",
      {
        "selector": "CallExpression[callee.name='fetch'][arguments.length=1]",
        "message": "Cân nhắc truyền AbortSignal vào fetch để support cancellation"
      }
    ]
  }
}
```

---

## Pattern 15: Worker Thread Overhead

### 1. Tên
**Chi Phí Worker Thread Không Cần Thiết** (Unnecessary Worker Thread Overhead)

### 2. Phân loại
- **Domain:** Worker Threads / Performance
- **Subcategory:** Over-engineering, Thread Communication Cost

### 3. Mức nghiêm trọng
🟡 **MEDIUM** - Gây performance regression khi overhead cao hơn lợi ích, tăng complexity

### 4. Vấn đề

Worker Threads có overhead: thread creation (~50ms), data serialization (structured clone), inter-thread communication. Cho tasks nhỏ hoặc I/O-bound, overhead lớn hơn lợi ích. Ngược lại, không dùng Worker cho CPU-heavy tasks gây event loop blocking.

```
WORKER OVERHEAD ANALYSIS:
Task duration: 5ms (quá nhỏ)
Thread creation: ~50ms
Data serialization: ~10ms
Total overhead: ~60ms

Dùng Worker: 5ms + 60ms = 65ms  ← CHẬM HƠN!
Không dùng:  5ms                 ← NHANH HƠN!

Task duration: 2000ms (CPU-bound)
Thread creation: ~50ms
Data serialization: ~10ms

Dùng Worker: 2000ms (parallel, không block main thread)
Không dùng:  2000ms + block event loop!  ← TỆ HƠN!
```

### 5. Phát hiện trong mã nguồn

**Dấu hiệu nhận biết:**
- Worker được tạo cho mỗi request (không reuse)
- Small/fast operations trong Worker
- I/O operations trong Worker (I/O đã non-blocking, không cần Worker)
- Không dùng Worker Pool

**Regex patterns (ripgrep):**
```bash
# Tìm Worker creation
rg "new Worker\(" --type ts --type js -A 20

# Tìm Worker trong request handlers (không reuse!)
rg "router\.|app\.|handler[\s\S]{0,500}new Worker" --multiline --type ts --type js

# Tìm potential CPU tasks không có Worker
rg "fibonacci|factorial|sha256|encrypt|compress|parse" --type ts --type js -B 5 | grep -v "Worker\|worker"
```

### 6. Giải pháp

| Task Type | Duration | Solution |
|---------|---------|---------|
| I/O bound (DB, network) | Any | Native async, no Worker needed |
| CPU-bound small | < 100ms | Main thread OK |
| CPU-bound medium | 100ms - 1s | Worker Thread |
| CPU-bound large | > 1s | Worker Pool |

```typescript
// ❌ SAI: Worker cho mọi thứ (over-engineering)
async function addNumbers(a: number, b: number): Promise<number> {
  return new Promise((resolve) => {
    const worker = new Worker(
      `parentPort.postMessage(workerData.a + workerData.b)`,
      { eval: true, workerData: { a, b } }
    )
    worker.on('message', resolve)
    // 50ms+ overhead cho phép tính 1ms!
  })
}

// ❌ SAI: Không reuse Worker (tạo mới mỗi request)
app.post('/process', async (req, res) => {
  const worker = new Worker('./processor.js')  // Tạo mới mỗi request!
  // ...
})
```

```typescript
// ✅ ĐÚNG: Worker Pool để reuse threads
import { Worker } from 'worker_threads'
import { EventEmitter } from 'events'

class WorkerPool extends EventEmitter {
  private workers: Worker[] = []
  private idleWorkers: Worker[] = []
  private taskQueue: Array<{
    data: unknown
    resolve: (value: unknown) => void
    reject: (err: Error) => void
  }> = []

  constructor(
    private readonly workerFile: string,
    private readonly poolSize: number = 4
  ) {
    super()
    this.initialize()
  }

  private initialize(): void {
    for (let i = 0; i < this.poolSize; i++) {
      const worker = new Worker(this.workerFile)

      worker.on('message', (result) => {
        const task = this.taskQueue.shift()
        if (task) {
          task.resolve(result)
          // Worker sẵn sàng cho task tiếp theo
          this.processNext(worker)
        } else {
          this.idleWorkers.push(worker)  // Trả về pool
        }
      })

      worker.on('error', (err) => {
        const task = this.taskQueue.shift()
        task?.reject(err)
      })

      this.idleWorkers.push(worker)
    }
  }

  private processNext(worker: Worker): void {
    const task = this.taskQueue.shift()
    if (task) {
      worker.postMessage(task.data)
    } else {
      this.idleWorkers.push(worker)
    }
  }

  run(data: unknown): Promise<unknown> {
    return new Promise((resolve, reject) => {
      const worker = this.idleWorkers.shift()
      if (worker) {
        this.taskQueue.push({ data, resolve, reject })
        worker.postMessage(data)
      } else {
        this.taskQueue.push({ data, resolve, reject })
      }
    })
  }
}

// Sử dụng: pool tồn tại suốt app, reuse workers
const pool = new WorkerPool('./heavy-computation.js', 4)

app.post('/compute', async (req, res) => {
  const result = await pool.run(req.body)
  res.json(result)
})

// ✅ ĐÚNG: Chỉ dùng Worker cho tasks thực sự CPU-heavy (>100ms)
function shouldUseWorker(estimatedMs: number): boolean {
  const WORKER_OVERHEAD_MS = 60
  return estimatedMs > WORKER_OVERHEAD_MS * 2  // 2x overhead là safe threshold
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Benchmark task duration: > 100ms mới cân nhắc Worker
- [ ] Luôn dùng Worker Pool, không tạo Worker per-request
- [ ] I/O-bound tasks: dùng native async, không cần Worker
- [ ] Monitor Worker creation rate trong production
- [ ] Giới hạn pool size bằng `os.cpus().length`

**ESLint rules:**
```json
{
  "rules": {
    "no-restricted-syntax": [
      "warn",
      {
        "selector": "NewExpression[callee.name='Worker']",
        "message": "Đảm bảo Worker được dùng trong pool pattern, không tạo per-request"
      }
    ]
  }
}
```

---

## Pattern 16: Async Iterator Leak

### 1. Tên
**Rò Rỉ Async Iterator** (Async Iterator Leak)

### 2. Phân loại
- **Domain:** Async Iteration / Resource Management
- **Subcategory:** Generator Cleanup, for-await-of

### 3. Mức nghiêm trọng
🟠 **HIGH** - Gây resource leak: file handles, DB connections, network connections không được đóng

### 4. Vấn đề

Khi `for await...of` loop bị break, throw, hoặc return sớm, generator's `return()` method phải được gọi để cleanup. Nếu không cleanup, resources (file handles, DB cursors, network streams) bị leak.

```
ASYNC ITERATOR LIFECYCLE:
Generator.next() ──▶ yield value ──▶ consumer
Generator.next() ──▶ yield value ──▶ consumer
Generator.next() ──▶ yield value ──▶ consumer

NORMAL completion:
Generator.next() ──▶ {done: true}  ──▶ finally block runs ✅

EARLY exit (break/throw/return):
break ──▶ Generator.return() PHẢI được gọi!
         → Nếu không: finally block KHÔNG chạy!
         → File/DB cursor/stream LEAK!

for await...of TỰ GỌI Generator.return() khi break
Nhưng: manual iterator.next() KHÔNG tự cleanup!
```

### 5. Phát hiện trong mã nguồn

**Dấu hiệu nhận biết:**
- Async generators mở resources (files, DB connections)
- `break` trong `for await...of` mà không wrap với `try/finally`
- Manual iteration (`iterator.next()`) không có cleanup
- Async generator wrapping streams mà không forward `return()`

**Regex patterns (ripgrep):**
```bash
# Tìm async generators với resources
rg "async function\*" --type ts --type js -A 20 | grep -v "finally\|try\|close\|cleanup"

# Tìm for-await-of với early exit
rg "for await.*of[\s\S]{0,500}break\|return\|throw" --multiline --type ts --type js

# Tìm manual async iteration
rg "\[Symbol\.asyncIterator\]" --type ts --type js -A 30

# Tìm generators mà mở connections
rg "async function\*[\s\S]{0,500}createConnection\|readFile\|cursor" --multiline --type ts --type js
```

### 6. Giải pháp

| Pattern | Cleanup Guarantee |
|--------|------------------|
| `for await...of` | Automatic (gọi `return()`) |
| `try/finally` trong generator | Guaranteed |
| Manual iteration + try/finally | Manual nhưng safe |
| AsyncDisposable (Stage 3) | Automatic |

```typescript
// ❌ SAI: Resource leak khi early exit
async function* readLines(filePath: string): AsyncGenerator<string> {
  const fileHandle = await fs.open(filePath, 'r')
  // Nếu consumer break sớm, fileHandle KHÔNG được đóng!
  for await (const line of fileHandle.readLines()) {
    yield line
  }
  await fileHandle.close()  // Không chạy nếu bị break!
}

async function processFirst10Lines(filePath: string): Promise<void> {
  let count = 0
  for await (const line of readLines(filePath)) {
    console.log(line)
    if (++count >= 10) break  // LEAK: fileHandle vẫn mở!
  }
}
```

```typescript
// ✅ ĐÚNG: Dùng try/finally để đảm bảo cleanup
async function* readLines(filePath: string): AsyncGenerator<string> {
  const fileHandle = await fs.open(filePath, 'r')
  try {
    for await (const line of fileHandle.readLines()) {
      yield line
    }
  } finally {
    // LUÔN chạy: dù complete, break, throw, hoặc return
    await fileHandle.close()
    console.log(`File ${filePath} closed properly`)
  }
}

// ✅ ĐÚNG: AsyncDisposable pattern (Node.js 18+)
class DatabaseCursor implements AsyncDisposable {
  private cursor: DBCursor

  constructor(cursor: DBCursor) {
    this.cursor = cursor
  }

  async *[Symbol.asyncIterator](): AsyncGenerator<Row> {
    try {
      while (await this.cursor.hasNext()) {
        yield await this.cursor.next()
      }
    } finally {
      await this.cursor.close()
    }
  }

  async [Symbol.asyncDispose](): Promise<void> {
    await this.cursor.close()
  }
}

// await using (Stage 3 proposal, TypeScript 5.2+)
async function queryDatabase(): Promise<void> {
  await using cursor = new DatabaseCursor(await db.query('SELECT *'))

  for await (const row of cursor) {
    if (row.id > 100) break  // cursor.close() tự động gọi!
  }
}

// ✅ ĐÚNG: Manual iteration với cleanup
async function safeManualIteration(
  iter: AsyncIterator<string>
): Promise<string[]> {
  const results: string[] = []
  try {
    while (true) {
      const { value, done } = await iter.next()
      if (done) break
      results.push(value)
      if (results.length >= 10) break
    }
  } finally {
    // Gọi return() để cleanup generator
    await iter.return?.()
  }
  return results
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Mọi async generator mở resources phải wrap với `try/finally`
- [ ] Test early-exit scenarios (break, throw sau N items)
- [ ] Dùng `using` / `await using` khi TypeScript 5.2+ và Node.js 18+
- [ ] Manual iteration phải gọi `iterator.return()` trong finally
- [ ] Monitor file descriptor và connection counts

**ESLint rules:**
```json
{
  "rules": {
    "require-yield": "error",
    "no-unreachable": "error"
  }
}
```

---

## Pattern 17: Promise Chain Memory

### 1. Tên
**Rò Rỉ Bộ Nhớ Promise Chain** (Promise Chain Memory Leak)

### 2. Phân loại
- **Domain:** Memory Management / Promise
- **Subcategory:** Retained References, GC Prevention

### 3. Mức nghiêm trọng
🟡 **MEDIUM** - Gây memory tăng dần theo thời gian, cuối cùng OOM crash

### 4. Vấn đề

Promise chains giữ references đến tất cả intermediate values cho đến khi chain hoàn thành. Trong long-running chains hoặc recursive promises, memory không được release. Thêm vào đó, circular references giữa promises và closures ngăn GC.

```
PROMISE CHAIN MEMORY RETENTION:
┌────────────────────────────────────────────────────────────┐
│  P1.then(fn1)                                              │
│     │                                                       │
│     ▼ fn1 returns P2 (holds reference to P1 result!)       │
│  P2.then(fn2)                                              │
│     │                                                       │
│     ▼ fn2 returns P3 (holds reference to P1, P2 results!)  │
│  P3.then(fn3)                                              │
│                                                             │
│  Memory: result1 + result2 + result3 all alive!            │
│  (không được GC cho đến khi chain resolve)                 │
│                                                             │
│  Với N-step chain: O(N) memory retained!                   │
└────────────────────────────────────────────────────────────┘
```

### 5. Phát hiện trong mã nguồn

**Dấu hiệu nhận biết:**
- Long promise chains (10+ `.then()`)
- Large objects truyền qua nhiều `.then()` steps
- Recursive promises không có termination
- Promises stored trong long-lived data structures

**Regex patterns (ripgrep):**
```bash
# Tìm long promise chains
rg "\.then\([\s\S]{0,50}\)\.then\([\s\S]{0,50}\)\.then\([\s\S]{0,50}\)\.then" --type ts --type js

# Tìm recursive promise patterns
rg "return.*\.(then|call)\(.*\)" --type ts --type js -B 5 | grep "function\|=>"

# Tìm large data trong promises
rg "resolve\(.*\b(?:allData|results|items|rows)\b" --type ts --type js

# Tìm Promise stored trong arrays/maps
rg "(?:promises|pendingOps|queue)\.(push|set)\(.*Promise\|fetch\|async" --type ts --type js
```

### 6. Giải pháp

| Technique | Memory Impact | Complexity |
|----------|--------------|-----------|
| Intermediate variable null-out | Giảm đáng kể | Thấp |
| Stream instead of accumulate | O(1) thay O(N) | Trung bình |
| Chunked processing | Bounded | Trung bình |
| WeakMap cho caching | GC-friendly | Thấp |

```typescript
// ❌ SAI: Giữ tất cả data trong memory
async function processAllRecords(): Promise<SummaryResult> {
  const allRecords = await db.findAll()  // 100,000 records in memory!

  return allRecords
    .map(record => transformRecord(record))     // 2x memory!
    .filter(record => record.isValid)           // Still large
    .reduce((acc, record) => merge(acc, record), {})
}

// ❌ SAI: Promise chain giữ intermediate large results
function processLargeData(data: LargeObject): Promise<Result> {
  return processStep1(data)
    .then(largeResult1 => {              // largeResult1 in memory
      return processStep2(largeResult1)
        .then(largeResult2 => {          // largeResult1 & largeResult2 in memory!
          return processStep3(largeResult2)
            .then(largeResult3 => {      // All 3 in memory!
              return summarize(largeResult3)
            })
        })
    })
}
```

```typescript
// ✅ ĐÚNG: Stream processing - O(1) memory
import { pipeline, Transform } from 'stream/promises'

async function processAllRecords(): Promise<SummaryResult> {
  let summary: SummaryResult = { count: 0, total: 0 }

  await pipeline(
    db.createReadStream(),  // Stream từ DB
    new Transform({
      objectMode: true,
      transform(record, _, callback) {
        // Process một record, không giữ tất cả trong memory
        if (isValidRecord(record)) {
          summary.count++
          summary.total += record.value
        }
        callback()  // Không push ra - chỉ aggregate
      }
    })
  )

  return summary
}

// ✅ ĐÚNG: Async/await thay vì nested chains
async function processLargeData(data: LargeObject): Promise<Result> {
  // Mỗi step: kết quả trước được GC sau khi step sau xong
  const step1 = await processStep1(data)
  // data vẫn referenced, step1 được dùng và release

  const step2 = await processStep2(step1)
  // step1 có thể được GC sau đây nếu không có reference khác

  const step3 = await processStep3(step2)
  // step2 có thể được GC

  return summarize(step3)
}

// ✅ ĐÚNG: WeakMap cho caching để không ngăn GC
const cache = new WeakMap<object, ProcessedResult>()

function getCachedResult(key: object): ProcessedResult | undefined {
  return cache.get(key)
  // Key bị GC → entry tự động removed!
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Dùng streaming cho large datasets thay vì load all into memory
- [ ] Prefer `async/await` over nested `.then()` chains
- [ ] Clear references đến large objects khi không cần
- [ ] Dùng `WeakMap`/`WeakSet` cho caches
- [ ] Monitor heap usage với `process.memoryUsage()`

**ESLint rules:**
```json
{
  "rules": {
    "prefer-destructuring": "warn",
    "@typescript-eslint/prefer-promise-reject-errors": "error"
  }
}
```

---

## Pattern 18: setImmediate vs nextTick

### 1. Tên
**Nhầm Lẫn setImmediate và process.nextTick** (setImmediate vs nextTick Confusion)

### 2. Phân loại
- **Domain:** Event Loop / Timer APIs
- **Subcategory:** Scheduling, Microtask vs Macrotask

### 3. Mức nghiêm trọng
🟡 **MEDIUM** - Gây bugs tinh tế, thứ tự thực thi không mong đợi, và tiềm năng gây microtask starvation

### 4. Vấn đề

`process.nextTick()` và `setImmediate()` đều hoãn thực thi nhưng ở các phase KHÁC NHAU của event loop. Nhầm lẫn chúng gây thứ tự thực thi sai và potential starvation.

```
EVENT LOOP EXECUTION ORDER:
┌──────────────────────────────────────────────────────────────┐
│  1. Synchronous code                                         │
│     ↓                                                        │
│  2. process.nextTick() callbacks (Microtask Queue 1)        │
│     ↓ (ALL nextTick callbacks before moving on)             │
│  3. Promise.resolve().then() callbacks (Microtask Queue 2)  │
│     ↓ (ALL promise callbacks before moving on)              │
│  4. setImmediate() callbacks (check phase - Macrotask)      │
│     ↓                                                        │
│  5. setTimeout(fn, 0) callbacks (timers phase - Macrotask)  │
└──────────────────────────────────────────────────────────────┘

nextTick runs BEFORE Promise.then!
nextTick STARVES event loop if recursive!
setImmediate yields PROPERLY to event loop!
```

### 5. Phát hiện trong mã nguồn

**Dấu hiệu nhận biết:**
- Dùng `nextTick` thay vì `setImmediate` cho yielding
- Mix `nextTick` và `setImmediate` mà không hiểu sự khác biệt
- Recursive `nextTick` (pattern 07: Microtask Starvation)
- Expect `setImmediate` chạy trước `setTimeout(fn, 0)` (không guaranteed)

**Regex patterns (ripgrep):**
```bash
# Tìm tất cả nextTick và setImmediate usage
rg "process\.nextTick|setImmediate" --type ts --type js -B 2 -A 5

# Tìm nextTick dùng cho yielding (nên là setImmediate)
rg "process\.nextTick\(\(\)" --type ts --type js -A 10

# Tìm mixed usage
rg "nextTick|setImmediate" --type ts --type js -l | xargs grep -l "nextTick" | xargs grep -l "setImmediate"

# Tìm setTimeout(fn, 0) - thường nên là setImmediate
rg "setTimeout\([^,]+,\s*0\)" --type ts --type js
```

### 6. Giải pháp

| API | Phase | Priority | Use When |
|-----|-------|---------|---------|
| `process.nextTick()` | Microtask | Cao nhất | Cần chạy TRƯỚC bất kỳ I/O nào |
| `Promise.resolve().then()` | Microtask | Cao | Standard async deferral |
| `setImmediate()` | Check phase | Thấp | Yield sau I/O callbacks |
| `setTimeout(fn, 0)` | Timers phase | Thấp | Similar to setImmediate, less predictable |
| `queueMicrotask()` | Microtask | Cao | Modern microtask deferral |

```typescript
// Để hiểu thứ tự thực thi:
console.log('1: sync start')

process.nextTick(() => console.log('4: nextTick'))

Promise.resolve().then(() => console.log('5: promise'))

setImmediate(() => console.log('6: setImmediate'))

setTimeout(() => console.log('7: setTimeout 0'), 0)

console.log('2: sync end')

// Output ORDER:
// 1: sync start
// 2: sync end
// 4: nextTick        ← Trước promise!
// 5: promise
// 6: setImmediate    ← Sau tất cả microtasks
// 7: setTimeout 0
```

```typescript
// ❌ SAI: Dùng nextTick để yield (nguy hiểm!)
async function processItems(items: string[]): Promise<void> {
  for (const item of items) {
    await new Promise<void>(resolve => process.nextTick(resolve))
    // nextTick: KHÔNG yield cho I/O!
    // Nếu loop dài: microtask starvation!
    processItem(item)
  }
}

// ❌ SAI: Dùng nextTick cho "deferred initialization" trong constructor
class Service {
  constructor() {
    process.nextTick(() => {
      this.initialize()  // Chạy sau sync code, TRƯỚC I/O!
      // Có thể gây vấn đề nếu initialize cần I/O
    })
  }
}
```

```typescript
// ✅ ĐÚNG: Chọn đúng API cho mục đích

// Khi cần chạy SAU sync code nhưng TRƯỚC I/O callbacks:
// → process.nextTick() (rare, specific use case)
function emitEventAfterInit(emitter: EventEmitter): void {
  process.nextTick(() => {
    emitter.emit('ready')  // Emit sau constructor return, trước bất kỳ I/O nào
  })
}

// Khi cần yield cho event loop (I/O, timers):
// → setImmediate() (preferred)
async function processWithYield(items: string[]): Promise<void> {
  for (let i = 0; i < items.length; i++) {
    processItem(items[i])

    // Yield mỗi 100 items để event loop xử lý I/O
    if (i % 100 === 0) {
      await new Promise<void>(resolve => setImmediate(resolve))
    }
  }
}

// Khi cần async deferral trong code path:
// → Promise.resolve().then() (most readable)
async function alwaysAsync<T>(fn: () => T): Promise<T> {
  await Promise.resolve()  // Defer sang microtask queue
  return fn()
}

// Decision helper:
function deferWithCorrectAPI(
  callback: () => void,
  purpose: 'before-io' | 'after-io' | 'microtask'
): void {
  switch (purpose) {
    case 'before-io':
      process.nextTick(callback)  // Microtask, trước I/O
      break
    case 'after-io':
      setImmediate(callback)       // Check phase, sau I/O
      break
    case 'microtask':
      queueMicrotask(callback)     // Standard microtask
      break
  }
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Hiểu rõ event loop phases trước khi dùng timing APIs
- [ ] Prefer `setImmediate` cho yielding trong loops
- [ ] Dùng `nextTick` chỉ khi cần chạy trước bất kỳ I/O nào
- [ ] Tránh recursive `nextTick` (dùng `setImmediate` thay)
- [ ] Viết tests verify execution order khi order matters

**ESLint rules:**
```json
{
  "rules": {
    "no-restricted-globals": [
      "warn",
      {
        "name": "setImmediate",
        "message": "Đảm bảo bạn hiểu sự khác biệt giữa setImmediate và process.nextTick"
      }
    ]
  }
}
```

---

## Tổng Kết Domain 01

| # | Pattern | Mức độ | Impact chính |
|---|---------|--------|-------------|
| 01 | Event Loop Blocking | 🔴 CRITICAL | Freeze toàn bộ app |
| 02 | Callback Hell | 🟡 MEDIUM | Code quality |
| 03 | Unhandled Promise Rejection | 🔴 CRITICAL | Process crash |
| 04 | Async/Await Trong Loop | 🟠 HIGH | N*T performance hit |
| 05 | Promise.all Fail-Fast | 🟠 HIGH | Data inconsistency |
| 06 | Floating Promise | 🟠 HIGH | Silent failures |
| 07 | Microtask Starvation | 🔴 CRITICAL | Freeze event loop |
| 08 | Timer Drift | 🟡 MEDIUM | Schedule inaccuracy |
| 09 | Async Constructor | 🟡 MEDIUM | Race condition |
| 10 | EventEmitter Memory Leak | 🟠 HIGH | Memory leak |
| 11 | Stream Backpressure Ignored | 🟠 HIGH | OOM crash |
| 12 | Race Condition Async | 🟠 HIGH | Data corruption |
| 13 | Zalgo | 🟠 HIGH | Unpredictable bugs |
| 14 | AbortController Thiếu | 🟡 MEDIUM | Resource waste |
| 15 | Worker Thread Overhead | 🟡 MEDIUM | Performance regression |
| 16 | Async Iterator Leak | 🟠 HIGH | Resource leak |
| 17 | Promise Chain Memory | 🟡 MEDIUM | Memory leak |
| 18 | setImmediate vs nextTick | 🟡 MEDIUM | Execution order bugs |

### Ưu tiên xử lý theo mức nghiêm trọng:
1. **🔴 CRITICAL (fix ngay):** #01, #03, #07
2. **🟠 HIGH (fix trong sprint này):** #04, #05, #06, #10, #11, #12, #13, #16
3. **🟡 MEDIUM (tech debt):** #02, #08, #09, #14, #15, #17, #18

### Quick Detection Commands:
```bash
# Chạy tất cả detection patterns
rg "pbkdf2Sync|readFileSync|hashSync" --type ts --type js          # Pattern 01
rg "\.on\(['\"]" --type ts --type js | grep -v "off\|once"        # Pattern 10
rg "new Worker\(" --type ts --type js                              # Pattern 15
rg "process\.nextTick|setImmediate" --type ts --type js           # Pattern 18
rg "fetch\([^)]*\)" --type ts --type js | grep -v "signal"       # Pattern 14
rg "for await.*of" --type ts --type js -A 10 | grep "break"      # Pattern 16
```
