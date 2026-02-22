# Domain 05: Quản Lý Tài Nguyên (Resource Management)

> Node.js patterns liên quan đến quản lý tài nguyên: memory, connections, file descriptors, processes.

| Thuộc tính | Giá trị |
|-----------|---------|
| **Lĩnh vực** | Quản Lý Tài Nguyên |
| **Số mẫu** | 12 |
| **Ngôn ngữ** | TypeScript / Node.js |
| **Ngày cập nhật** | 2026-02-18 |

---

## Tổng Quan

```
┌─────────────────────────────────────────────────────────────┐
│                    V8 MEMORY MODEL                          │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │  New Space    │  │  Old Space    │  │  Large Object    │  │
│  │  (Young Gen)  │  │  (Old Gen)    │  │  Space           │  │
│  │  ~4MB         │  │  ~1.5GB       │  │  >kMaxRegular    │  │
│  │              │  │              │  │  HeapObjectSize  │  │
│  │  Scavenge GC  │  │  Mark-Sweep   │  │                  │  │
│  │  (frequent)   │  │  Mark-Compact │  │  Never moved     │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │  Code Space   │  │  Map Space    │  │  External Memory │  │
│  │  (JIT code)   │  │  (hidden      │  │  (Buffer, WASM)  │  │
│  │              │  │   classes)    │  │  Không tính vào  │  │
│  │              │  │              │  │  heap limit      │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
└─────────────────────────────────────────────────────────────┘

12 Failure Patterns:
  RM-01  Memory Leak Qua Closure .............. CRITICAL
  RM-02  Connection Pool Exhaustion ........... CRITICAL
  RM-03  File Descriptor Leak ................. HIGH
  RM-04  Global Variable Memory ............... HIGH
  RM-05  Express Middleware Leak .............. MEDIUM
  RM-06  Child Process Zombie ................. HIGH
  RM-07  HTTP Agent Connection ................ MEDIUM
  RM-08  DNS Cache Thiếu ...................... MEDIUM
  RM-09  Large File Memory .................... HIGH
  RM-10  Timeout Thiếu Cho HTTP ............... HIGH
  RM-11  Redis Client Reconnect ............... MEDIUM
  RM-12  Buffer Pool Overflow ................. HIGH
```

---

## Pattern 01: Memory Leak Qua Closure

### Tên
Memory Leak Qua Closure (Closure-Based Memory Leak)

### Phân loại
Resource Management / Memory / V8 Heap

### Mức nghiêm trọng
CRITICAL 🔴

> Closure giữ reference tới large object ngay cả khi chỉ dùng 1 field nhỏ. V8 GC không thể thu hồi vì closure vẫn reachable. Heap grow liên tục → OOM crash trong production.

### Vấn đề

```
Luồng thực thi:

  Request Handler
       │
       ▼
  const bigData = fetchLargePayload()  ← 50MB object
       │
       ▼
  const callback = () => {
    console.log(bigData.status)  ← Chỉ dùng 1 field
  }                                ← Nhưng closure capture TOÀN BỘ bigData
       │
       ▼
  eventEmitter.on('check', callback)  ← Listener giữ closure
       │                                ← bigData KHÔNG BAO GIỜ được GC
       ▼
  1000 requests = 50GB leaked!

  V8 Heap:
  ┌────────────────────────────────────────┐
  │ Request 1: [bigData 50MB] ← closure   │
  │ Request 2: [bigData 50MB] ← closure   │
  │ Request 3: [bigData 50MB] ← closure   │
  │ ...                                    │
  │ Request N: heap > --max-old-space-size │
  │            → FATAL ERROR: OOM          │
  └────────────────────────────────────────┘
```

Closure trong JavaScript capture toàn bộ scope chain, không phải chỉ biến được sử dụng. Khi closure được gán làm event listener, timer callback, hoặc lưu trong cache, tất cả objects trong scope đều bị giữ lại.

### Phát hiện

Dấu hiệu nhận biết:
- RSS (Resident Set Size) tăng liên tục theo thời gian
- V8 heap snapshot cho thấy "retainers" là closures
- `process.memoryUsage().heapUsed` tăng dần sau mỗi request

```bash
# Tìm event listener đăng ký trong request handler
rg --type js --type ts "\.on\(|\.addEventListener\(" -B 5 | head -40

# Tìm closure capture large object
rg --type js --type ts "const \w+ = \(\) =>" -B 10 | head -40

# Tìm setInterval/setTimeout không clear
rg --type js --type ts "setInterval|setTimeout" --no-filename | head -20

# Tìm module-level cache không có eviction
rg --type js --type ts "^const \w+(Map|Cache|Store) = new Map" | head -20
```

### Giải pháp

| Vấn đề | Giải pháp |
|---------|-----------|
| Closure capture toàn bộ scope | Extract field trước khi tạo closure |
| Event listener không remove | WeakRef hoặc cleanup on disconnect |
| Timer không clear | AbortSignal hoặc cleanup pattern |

**BAD — Closure capture toàn bộ large object:**
```typescript
// BAD: closure giữ reference tới toàn bộ `response` (50MB)
app.get('/api/reports', async (req, res) => {
  const response = await fetchHugeReport(); // 50MB data

  const checkStatus = () => {
    // Chỉ dùng response.status nhưng capture TOÀN BỘ response
    return response.status === 'ready';
  };

  statusChecker.on('poll', checkStatus);
  // response 50MB KHÔNG BAO GIỜ được GC vì checkStatus giữ reference

  res.json({ id: response.id });
});
```

**GOOD — Extract field, giải phóng reference:**
```typescript
// GOOD: Extract field cần thiết, không capture large object
app.get('/api/reports', async (req, res) => {
  const response = await fetchHugeReport(); // 50MB data

  // Extract CHỈ field cần thiết
  const { status, id } = response;
  // response giờ có thể được GC vì không còn reference

  const checkStatus = () => {
    return status === 'ready'; // Chỉ capture primitive string
  };

  // Thêm cleanup mechanism
  const cleanup = () => {
    statusChecker.off('poll', checkStatus);
  };

  statusChecker.on('poll', checkStatus);

  // Auto-cleanup sau 5 phút
  const timer = setTimeout(cleanup, 5 * 60 * 1000);
  req.on('close', () => {
    cleanup();
    clearTimeout(timer);
  });

  res.json({ id });
});
```

**GOOD — WeakRef pattern cho long-lived listeners:**
```typescript
class SafeEventManager {
  private listeners = new Map<string, Set<WeakRef<Function>>>();
  private registry = new FinalizationRegistry<{ event: string; ref: WeakRef<Function> }>(
    ({ event, ref }) => {
      this.listeners.get(event)?.delete(ref);
    }
  );

  on(event: string, callback: Function): void {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, new Set());
    }
    const ref = new WeakRef(callback);
    this.listeners.get(event)!.add(ref);
    this.registry.register(callback, { event, ref });
  }

  emit(event: string, ...args: unknown[]): void {
    const refs = this.listeners.get(event);
    if (!refs) return;

    for (const ref of refs) {
      const fn = ref.deref();
      if (fn) {
        fn(...args);
      } else {
        refs.delete(ref); // Cleanup dead references
      }
    }
  }
}
```

### Phòng ngừa

- [ ] Không capture large object trong closure — extract fields trước
- [ ] Mọi `emitter.on()` phải có `emitter.off()` tương ứng
- [ ] Sử dụng `AbortSignal` để tự động cleanup timers và listeners
- [ ] Monitor heap growth: `node --inspect` + Chrome DevTools Memory tab
- [ ] Chạy clinic.js doctor để phát hiện memory leak: `clinic doctor -- node app.js`
- [ ] Set `--max-old-space-size` hợp lý và monitor với `process.memoryUsage()`

```bash
# Chạy với heap profiling
node --heap-prof --heap-prof-interval=512 app.js

# clinic.js heap profiling
npx clinic heapprofiler -- node app.js
```

---

## Pattern 02: Connection Pool Exhaustion

### Tên
Connection Pool Exhaustion (Cạn Kiệt Connection Pool)

### Phân loại
Resource Management / Database / Connection Pool

### Mức nghiêm trọng
CRITICAL 🔴

> Connections không được release về pool sau khi dùng. Pool đầy → requests mới bị block → timeout cascade → toàn bộ service down.

### Vấn đề

```
Pool Size = 10

  Request 1 ──► acquire() ──► connection 1  ──► query OK
                                                    │
                                              ERROR thrown!
                                                    │
                                              connection 1 KHÔNG release
                                              (vì error skip qua release code)

  ... lặp lại 9 lần nữa ...

  Request 11 ──► acquire() ──► TIMEOUT (30s)
  Request 12 ──► acquire() ──► TIMEOUT (30s)
  Request 13 ──► acquire() ──► TIMEOUT (30s)

  Pool Status:
  ┌──────────────────────────────────┐
  │ [1] LEAKED  [2] LEAKED          │
  │ [3] LEAKED  [4] LEAKED          │
  │ [5] LEAKED  [6] LEAKED          │
  │ [7] LEAKED  [8] LEAKED          │
  │ [9] LEAKED  [10] LEAKED         │
  │                                  │
  │ Available: 0 / 10               │
  │ Waiting:   247 requests          │
  │ Status:    💀 DEADLOCKED        │
  └──────────────────────────────────┘
```

### Phát hiện

```bash
# Tìm pool acquire không có release/destroy
rg --type js --type ts "pool\.(acquire|connect|getConnection)\(\)" -A 10 | head -40

# Tìm knex/prisma transaction không commit/rollback
rg --type js --type ts "\.transaction\(" -A 15 | head -40

# Tìm raw query không dùng pool correctly
rg --type js --type ts "new (Pool|Client)\(" | head -20

# Tìm connection thiếu error handling
rg --type js --type ts "await.*query\(" -B 3 | grep -v "try\|catch\|finally" | head -20
```

### Giải pháp

**BAD — Connection không release khi error:**
```typescript
// BAD: Nếu query throw error, connection KHÔNG được release
async function getUser(id: string) {
  const client = await pool.connect();
  const result = await client.query('SELECT * FROM users WHERE id = $1', [id]);
  client.release(); // KHÔNG BAO GIỜ chạy nếu query throw!
  return result.rows[0];
}
```

**GOOD — Luôn release trong finally:**
```typescript
// GOOD: finally đảm bảo connection LUÔN được release
async function getUser(id: string) {
  const client = await pool.connect();
  try {
    const result = await client.query('SELECT * FROM users WHERE id = $1', [id]);
    return result.rows[0];
  } catch (error) {
    // Destroy connection nếu có lỗi nghiêm trọng (connection corrupted)
    if (isConnectionError(error)) {
      client.release(true); // true = destroy, không return về pool
      throw error;
    }
    throw error;
  } finally {
    client.release(); // LUÔN release
  }
}
```

**GOOD — Pool wrapper với auto-release:**
```typescript
// GOOD: Helper đảm bảo connection luôn được release
async function withConnection<T>(
  pool: Pool,
  fn: (client: PoolClient) => Promise<T>
): Promise<T> {
  const client = await pool.connect();
  try {
    return await fn(client);
  } finally {
    client.release();
  }
}

// Sử dụng
const user = await withConnection(pool, async (client) => {
  const result = await client.query('SELECT * FROM users WHERE id = $1', [id]);
  return result.rows[0];
});
```

**GOOD — Pool monitoring:**
```typescript
import { Pool } from 'pg';

const pool = new Pool({
  max: 20,
  idleTimeoutMillis: 30000,
  connectionTimeoutMillis: 5000,
});

// Monitor pool health
setInterval(() => {
  console.log({
    total: pool.totalCount,
    idle: pool.idleCount,
    waiting: pool.waitingCount,
  });

  // Alert nếu pool gần đầy
  if (pool.waitingCount > 10) {
    logger.warn('Pool exhaustion warning', {
      waiting: pool.waitingCount,
      total: pool.totalCount,
    });
  }
}, 10000);

// Graceful shutdown
process.on('SIGTERM', async () => {
  await pool.end();
  process.exit(0);
});
```

### Phòng ngừa

- [ ] Mọi `pool.connect()` PHẢI có `finally { client.release() }`
- [ ] Sử dụng helper wrapper `withConnection()` để tự động release
- [ ] Set `connectionTimeoutMillis` hợp lý (5-10s, không để mặc định)
- [ ] Monitor pool metrics: `totalCount`, `idleCount`, `waitingCount`
- [ ] Set `max` pool size phù hợp (thường 10-20 cho Node.js single-thread)
- [ ] Graceful shutdown: `pool.end()` trước khi process exit

---

## Pattern 03: File Descriptor Leak

### Tên
File Descriptor Leak (Rò Rỉ File Descriptor)

### Phân loại
Resource Management / OS / File Descriptors

### Mức nghiêm trọng
HIGH 🟠

> Stream hoặc socket mở mà không close. OS có giới hạn file descriptors (thường 1024 mặc định). Khi hết → `EMFILE: too many open files`.

### Vấn đề

```
Mỗi lần mở file/socket/pipe:
  fd count: 1 → 2 → 3 → ... → 1024
                                  │
                                  ▼
                         EMFILE error!
                         Không mở được file nào nữa
                         HTTP server KHÔNG accept được connection mới

  ulimit -n = 1024 (default)

  ┌─────────────────────────────────────┐
  │ fd 0: stdin                         │
  │ fd 1: stdout                        │
  │ fd 2: stderr                        │
  │ fd 3: server socket                 │
  │ fd 4: leaked read stream            │
  │ fd 5: leaked read stream            │
  │ ...                                 │
  │ fd 1023: leaked read stream         │
  │ fd 1024: EMFILE! ❌                 │
  └─────────────────────────────────────┘
```

### Phát hiện

```bash
# Tìm createReadStream/createWriteStream không close
rg --type js --type ts "createReadStream|createWriteStream" -A 10 | head -40

# Tìm fs.open không có fs.close
rg --type js --type ts "fs\.open\(|fs\.promises\.open\(" -A 10 | head -30

# Tìm net.createServer/net.connect không handle close
rg --type js --type ts "net\.create|new net\.Socket" -A 10 | head -30

# Kiểm tra fd count của process đang chạy
# lsof -p $(pgrep -f "node app") | wc -l
```

### Giải pháp

**BAD — Stream không close khi error:**
```typescript
// BAD: Nếu pipeline fail, readStream có thể không được close
app.get('/download/:file', (req, res) => {
  const stream = fs.createReadStream(`/uploads/${req.params.file}`);
  stream.pipe(res);
  // Nếu client disconnect giữa chừng → stream vẫn mở!
});
```

**GOOD — Proper stream cleanup:**
```typescript
import { pipeline } from 'node:stream/promises';

// GOOD: pipeline tự động cleanup tất cả streams khi error hoặc complete
app.get('/download/:file', async (req, res) => {
  const filePath = path.join(UPLOAD_DIR, path.basename(req.params.file));

  // Validate path
  if (!filePath.startsWith(UPLOAD_DIR)) {
    return res.status(403).send('Forbidden');
  }

  const stream = fs.createReadStream(filePath);

  try {
    await pipeline(stream, res);
  } catch (error) {
    // pipeline đã cleanup stream, chỉ cần log
    if ((error as NodeJS.ErrnoException).code !== 'ERR_STREAM_PREMATURE_CLOSE') {
      logger.error('Download failed', { error, file: req.params.file });
    }
  }
});
```

**GOOD — File handle với using (Node.js 22+):**
```typescript
// GOOD: Symbol.asyncDispose tự động close file handle
async function processFile(filePath: string): Promise<string[]> {
  await using handle = await fs.promises.open(filePath, 'r');
  const content = await handle.readFile('utf-8');
  return content.split('\n');
  // handle tự động close ở đây, kể cả khi throw error
}
```

### Phòng ngừa

- [ ] Sử dụng `pipeline()` thay vì `.pipe()` — tự động cleanup
- [ ] Sử dụng `await using` (Node.js 22+) cho file handles
- [ ] Mọi `createReadStream` phải handle event `error` và `close`
- [ ] Set ulimit cao hơn cho production: `ulimit -n 65536`
- [ ] Monitor fd count: `process.getActiveResourcesInfo()`

```bash
# ESLint rule: no-floating-promises (stream operations)
# clinic.js: npx clinic bubbleprof -- node app.js
```

---

## Pattern 04: Global Variable Memory

### Tên
Global Variable Memory Growth (Module-Level Cache Tăng Vô Hạn)

### Phân loại
Resource Management / Memory / Cache

### Mức nghiêm trọng
HIGH 🟠

> Module-level Map/Object dùng làm cache nhưng không có eviction policy. Cache grow vô hạn → heap exhaustion.

### Vấn đề

```
Module loaded (singleton):
  const cache = new Map()

  Request 1: cache.set(key1, data1)    size: 1
  Request 2: cache.set(key2, data2)    size: 2
  ...
  Request 1M: cache.set(keyN, dataN)   size: 1,000,000
                                            │
                                            ▼
                                       OOM CRASH!

  Heap Usage Over Time:

  Memory │         ╱
         │        ╱
         │       ╱
         │      ╱
         │     ╱
         │    ╱  ← Linear growth = LEAK
         │   ╱
         │  ╱
         │ ╱
         │╱
         └────────────────────► Time
```

### Phát hiện

```bash
# Tìm module-level Map/Set/Object cache
rg --type js --type ts "^(export )?(const|let|var) \w+ = new (Map|Set|WeakMap)\(" | head -20

# Tìm module-level object literal cache
rg --type js --type ts "^(export )?(const|let|var) \w+(Cache|Store|Registry|Map) = \{" | head -20

# Tìm cache.set không có cache.delete / clear / eviction
rg --type js --type ts "\.set\(" --no-filename | head -30
```

### Giải pháp

**BAD — Unbounded cache:**
```typescript
// BAD: Cache grow vô hạn, không có eviction
const userCache = new Map<string, User>();

export async function getUser(id: string): Promise<User> {
  if (userCache.has(id)) {
    return userCache.get(id)!;
  }
  const user = await db.users.findById(id);
  userCache.set(id, user); // Chỉ thêm, KHÔNG BAO GIỜ xóa!
  return user;
}
```

**GOOD — LRU cache với giới hạn:**
```typescript
import { LRUCache } from 'lru-cache';

const userCache = new LRUCache<string, User>({
  max: 1000,               // Tối đa 1000 entries
  ttl: 5 * 60 * 1000,      // TTL 5 phút
  maxSize: 50 * 1024 * 1024, // Max 50MB tổng
  sizeCalculation: (value) => JSON.stringify(value).length,
  dispose: (value, key, reason) => {
    logger.debug('Cache evicted', { key, reason });
  },
});

export async function getUser(id: string): Promise<User> {
  const cached = userCache.get(id);
  if (cached) return cached;

  const user = await db.users.findById(id);
  userCache.set(id, user);
  return user;
}

// Monitor cache health
setInterval(() => {
  logger.info('Cache stats', {
    size: userCache.size,
    calculatedSize: userCache.calculatedSize,
  });
}, 60000);
```

### Phòng ngừa

- [ ] KHÔNG dùng bare `Map`/`Set` làm cache — luôn dùng `lru-cache`
- [ ] Set `max` entries và `ttl` cho mọi cache
- [ ] Monitor cache size qua metrics
- [ ] Sử dụng external cache (Redis) cho data lớn
- [ ] WeakMap chỉ dùng khi key là object và lifecycle gắn với key

---

## Pattern 05: Express Middleware Leak

### Tên
Express Middleware Memory Leak (Middleware Gắn Data Vào Request)

### Phân loại
Resource Management / Memory / Framework

### Mức nghiêm trọng
MEDIUM 🟡

> Middleware thêm large data vào `req` object. Nếu response chậm hoặc long-polling, data tồn tại suốt lifetime của request.

### Vấn đề

```
Middleware chain:
  req ──► authMiddleware: req.user = {...}        +2KB
      ──► dataMiddleware: req.fullReport = {...}  +5MB  ← PROBLEM!
      ──► logMiddleware:  req.auditLog = [...]    +1MB  ← PROBLEM!
      ──► handler:        res.json(small)

  Nếu 100 concurrent requests:
  100 × (5MB + 1MB) = 600MB chỉ cho middleware data!
```

### Phát hiện

```bash
# Tìm middleware gán data lớn vào req
rg --type js --type ts "req\.\w+ = " --no-filename | head -30

# Tìm middleware fetch data và gán vào req
rg --type js --type ts "req\.\w+ = await" | head -20
```

### Giải pháp

**BAD — Fetch large data trong middleware:**
```typescript
// BAD: Mỗi request load 5MB vào memory qua middleware
app.use(async (req, res, next) => {
  req.fullPermissions = await loadAllPermissions(req.user.id); // 5MB
  req.companyData = await loadCompanyTree(req.user.companyId); // 3MB
  next();
});
```

**GOOD — Lazy loading, chỉ fetch khi cần:**
```typescript
// GOOD: Lazy getter, chỉ load khi handler thực sự cần
app.use((req, res, next) => {
  let permissions: Permission[] | null = null;
  let companyData: CompanyTree | null = null;

  Object.defineProperty(req, 'fullPermissions', {
    get: async () => {
      if (!permissions) {
        permissions = await loadAllPermissions(req.user.id);
      }
      return permissions;
    },
  });

  Object.defineProperty(req, 'companyData', {
    get: async () => {
      if (!companyData) {
        companyData = await loadCompanyTree(req.user.companyId);
      }
      return companyData;
    },
  });

  next();
});
```

### Phòng ngừa

- [ ] Không gán large objects vào `req` trong middleware
- [ ] Sử dụng lazy loading pattern cho data lớn
- [ ] Chỉ gán IDs/references nhỏ vào `req`, fetch data trong handler khi cần
- [ ] Set request timeout để tránh request tồn tại quá lâu

---

## Pattern 06: Child Process Zombie

### Tên
Child Process Zombie (Process Con Trở Thành Zombie)

### Phân loại
Resource Management / OS / Process

### Mức nghiêm trọng
HIGH 🟠

> `child_process.spawn()` hoặc `exec()` tạo process con nhưng không handle event `exit`, `error`, `close`. Process con kết thúc nhưng entry vẫn tồn tại trong process table → zombie accumulation.

### Vấn đề

```
Parent (Node.js)
    │
    ├── spawn('ffmpeg', [...]) → PID 1234
    │       │
    │       ▼
    │   ffmpeg finishes (exit code 0)
    │   Nhưng parent KHÔNG gọi wait()
    │   → PID 1234 trở thành ZOMBIE
    │
    ├── spawn('ffmpeg', [...]) → PID 1235  ← zombie
    ├── spawn('ffmpeg', [...]) → PID 1236  ← zombie
    │   ...
    └── PID limit reached → Cannot fork!

  $ ps aux | grep Z
  USER  PID  STAT COMMAND
  node  1234  Z   [ffmpeg] <defunct>
  node  1235  Z   [ffmpeg] <defunct>
  node  1236  Z   [ffmpeg] <defunct>
```

### Phát hiện

```bash
# Tìm spawn/exec không handle exit/error events
rg --type js --type ts "spawn\(|exec\(|execFile\(" -A 10 | head -40

# Tìm child process không có .on('exit') hoặc .on('error')
rg --type js --type ts "child_process" | head -20

# Kiểm tra zombie processes
# ps aux | awk '$8 ~ /Z/ {print}'
```

### Giải pháp

**BAD — Spawn không handle lifecycle:**
```typescript
// BAD: Không handle exit, error, close events
import { spawn } from 'node:child_process';

app.post('/convert', async (req, res) => {
  const proc = spawn('ffmpeg', ['-i', inputPath, '-f', 'mp4', outputPath]);
  res.json({ status: 'processing' });
  // proc trở thành zombie khi ffmpeg kết thúc!
});
```

**GOOD — Proper child process management:**
```typescript
import { spawn } from 'node:child_process';

function runCommand(
  cmd: string,
  args: string[],
  options: { timeout?: number; signal?: AbortSignal } = {}
): Promise<{ code: number; stdout: string; stderr: string }> {
  return new Promise((resolve, reject) => {
    const proc = spawn(cmd, args, {
      signal: options.signal,
      timeout: options.timeout ?? 30000,
      stdio: ['ignore', 'pipe', 'pipe'],
    });

    const stdout: Buffer[] = [];
    const stderr: Buffer[] = [];

    proc.stdout.on('data', (chunk) => stdout.push(chunk));
    proc.stderr.on('data', (chunk) => stderr.push(chunk));

    proc.on('error', (error) => {
      reject(new Error(`Process error: ${error.message}`));
    });

    proc.on('close', (code, signal) => {
      resolve({
        code: code ?? -1,
        stdout: Buffer.concat(stdout).toString(),
        stderr: Buffer.concat(stderr).toString(),
      });
    });
  });
}

// Sử dụng với AbortController
app.post('/convert', async (req, res) => {
  const controller = new AbortController();

  // Cancel nếu client disconnect
  req.on('close', () => controller.abort());

  try {
    const result = await runCommand('ffmpeg', ['-i', inputPath, '-f', 'mp4', outputPath], {
      timeout: 60000,
      signal: controller.signal,
    });

    if (result.code !== 0) {
      return res.status(500).json({ error: result.stderr });
    }
    res.json({ status: 'done' });
  } catch (error) {
    res.status(500).json({ error: 'Conversion failed' });
  }
});
```

### Phòng ngừa

- [ ] Mọi `spawn()`/`exec()` PHẢI handle `error` và `close` events
- [ ] Set `timeout` cho child processes
- [ ] Sử dụng `AbortSignal` để cancel khi không cần nữa
- [ ] Limit concurrent child processes (semaphore pattern)
- [ ] Monitor zombie count: `ps aux | awk '$8 ~ /Z/'`

---

## Pattern 07: HTTP Agent Connection

### Tên
HTTP Agent Connection Flood (Agent Connection Không Kiểm Soát)

### Phân loại
Resource Management / Network / HTTP Agent

### Mức nghiêm trọng
MEDIUM 🟡

> Node.js HTTP Agent mặc định có `maxSockets = Infinity` (từ Node 12+). Khi gọi external API dưới tải cao → mở quá nhiều TCP connections → overwhelm target server hoặc exhaust local ports.

### Vấn đề

```
Node.js app (100 concurrent requests to API)
    │
    ├── TCP connection 1 → api.example.com:443
    ├── TCP connection 2 → api.example.com:443
    ├── TCP connection 3 → api.example.com:443
    │   ...
    ├── TCP connection 100 → api.example.com:443
    │
    └── maxSockets = Infinity (default!)
        → 100 TCP connections mở cùng lúc
        → Target server reject/rate-limit
        → Local ephemeral ports exhaustion (>65535)
```

### Phát hiện

```bash
# Tìm HTTP/HTTPS requests không set agent options
rg --type js --type ts "https?\.request\(|https?\.get\(" | head -20

# Tìm fetch/axios không giới hạn concurrency
rg --type js --type ts "axios\.(get|post|put)|fetch\(" | head -30

# Tìm custom agent configuration
rg --type js --type ts "new https?\.Agent\(" | head -10
```

### Giải pháp

**BAD — Default agent, không giới hạn:**
```typescript
// BAD: maxSockets = Infinity, mỗi request tạo TCP connection mới
import https from 'node:https';

async function callExternalAPI(data: unknown): Promise<unknown> {
  const response = await fetch('https://api.example.com/endpoint', {
    method: 'POST',
    body: JSON.stringify(data),
  });
  return response.json();
}
```

**GOOD — Custom agent với giới hạn:**
```typescript
import https from 'node:https';
import http from 'node:http';

// GOOD: Shared agent với connection limits
const httpsAgent = new https.Agent({
  maxSockets: 50,           // Max 50 concurrent connections per host
  maxTotalSockets: 200,     // Max 200 total connections
  maxFreeSockets: 10,       // Keep 10 idle connections
  keepAlive: true,          // Reuse connections
  keepAliveMsecs: 30000,    // Keep-alive ping interval
  timeout: 10000,           // Socket timeout
});

const httpAgent = new http.Agent({
  maxSockets: 50,
  maxTotalSockets: 200,
  keepAlive: true,
});

// Sử dụng với fetch (Node.js 18+)
async function callExternalAPI(data: unknown): Promise<unknown> {
  const response = await fetch('https://api.example.com/endpoint', {
    method: 'POST',
    body: JSON.stringify(data),
    // @ts-expect-error -- Node.js specific option
    dispatcher: httpsAgent,
    signal: AbortSignal.timeout(10000),
  });
  return response.json();
}
```

### Phòng ngừa

- [ ] Tạo shared HTTP Agent với `maxSockets` hợp lý (20-100)
- [ ] Enable `keepAlive: true` để reuse connections
- [ ] Set socket `timeout` cho mọi request
- [ ] Sử dụng `undici` Pool cho high-performance use cases
- [ ] Monitor open socket count

---

## Pattern 08: DNS Cache Thiếu

### Tên
DNS Cache Thiếu (Missing DNS Caching)

### Phân loại
Resource Management / Network / DNS

### Mức nghiêm trọng
MEDIUM 🟡

> Node.js mặc định KHÔNG cache DNS lookups. Mỗi HTTP request trigger DNS resolution → tăng latency 5-50ms mỗi request, tăng load lên DNS server.

### Vấn đề

```
Mỗi fetch('https://api.example.com/...'):
  1. DNS lookup: api.example.com → 203.0.113.5  (5-50ms)
  2. TCP handshake                               (10ms)
  3. TLS handshake                               (20ms)
  4. HTTP request/response                       (50ms)

  Không cache DNS:
  Request 1: DNS(50ms) + TCP + TLS + HTTP = 130ms
  Request 2: DNS(50ms) + TCP + TLS + HTTP = 130ms  ← DNS lặp lại!
  Request 3: DNS(50ms) + TCP + TLS + HTTP = 130ms  ← DNS lặp lại!

  Với cache DNS:
  Request 1: DNS(50ms) + TCP + TLS + HTTP = 130ms
  Request 2: cache(0ms) + TCP + TLS + HTTP = 80ms  ← 38% nhanh hơn
  Request 3: cache(0ms) + TCP + TLS + HTTP = 80ms
```

### Phát hiện

```bash
# Kiểm tra xem có dns caching package không
rg --type js --type ts "cacheable-lookup|dns-cache" | head -10

# Tìm http agent configuration
rg --type js --type ts "lookup:|dns\.resolve|dns\.lookup" | head -10
```

### Giải pháp

**BAD — Không DNS cache:**
```typescript
// BAD: Mỗi request trigger DNS lookup
const response = await fetch('https://api.example.com/data');
```

**GOOD — DNS caching với cacheable-lookup:**
```typescript
import CacheableLookup from 'cacheable-lookup';
import https from 'node:https';

const cacheable = new CacheableLookup({
  maxTtl: 300,      // Cache 5 phút
  fallbackDuration: 60, // Fallback cache 1 phút khi DNS fail
});

// Install globally cho tất cả requests
cacheable.install(https.globalAgent);

// Hoặc cấu hình per-agent
const agent = new https.Agent({
  keepAlive: true,
  maxSockets: 50,
  lookup: cacheable.lookup,
});
```

### Phòng ngừa

- [ ] Install `cacheable-lookup` hoặc tương đương
- [ ] Set DNS TTL phù hợp (thường 60-300 giây)
- [ ] Kết hợp với `keepAlive: true` để giảm DNS lookups
- [ ] Monitor DNS resolution time qua metrics

---

## Pattern 09: Large File Memory

### Tên
Large File Memory Load (Đọc File Lớn Vào Memory)

### Phân loại
Resource Management / Memory / File I/O

### Mức nghiêm trọng
HIGH 🟠

> Sử dụng `fs.readFile()` cho file lớn load toàn bộ vào memory. File 500MB → V8 heap cần 500MB+ → OOM cho process.

### Vấn đề

```
fs.readFile('large-export.csv')
       │
       ▼
  Allocate Buffer 500MB trong V8 heap
       │
       ▼
  V8 Old Space: 1.5GB (default limit)
  500MB file + 500MB processing = OOM!

  Concurrent requests:
  User 1: readFile(200MB) ─┐
  User 2: readFile(200MB) ─┼── Total: 600MB+ heap usage
  User 3: readFile(200MB) ─┘   → FATAL ERROR: OOM
```

### Phát hiện

```bash
# Tìm readFile/readFileSync (potential large file)
rg --type js --type ts "readFile(Sync)?\(" | head -20

# Tìm Buffer.from với large data sources
rg --type js --type ts "Buffer\.(from|alloc)\(" | head -20

# Tìm response.data (axios) cho large responses
rg --type js --type ts "response\.data" -B 5 | head -30
```

### Giải pháp

**BAD — Load toàn bộ file vào memory:**
```typescript
// BAD: 500MB file → 500MB+ trong V8 heap
app.get('/export/:id', async (req, res) => {
  const data = await fs.promises.readFile(`/exports/${req.params.id}.csv`);
  res.setHeader('Content-Type', 'text/csv');
  res.send(data);
});
```

**GOOD — Stream processing:**
```typescript
import { pipeline } from 'node:stream/promises';
import { createReadStream } from 'node:fs';
import { Transform } from 'node:stream';

// GOOD: Stream file, memory usage = buffer size (~64KB)
app.get('/export/:id', async (req, res) => {
  const filePath = path.join(EXPORT_DIR, `${req.params.id}.csv`);

  // Kiểm tra file tồn tại
  try {
    await fs.promises.access(filePath);
  } catch {
    return res.status(404).json({ error: 'Export not found' });
  }

  const stat = await fs.promises.stat(filePath);

  res.setHeader('Content-Type', 'text/csv');
  res.setHeader('Content-Length', stat.size);
  res.setHeader('Content-Disposition', `attachment; filename="${req.params.id}.csv"`);

  const readStream = createReadStream(filePath, {
    highWaterMark: 64 * 1024, // 64KB chunks
  });

  try {
    await pipeline(readStream, res);
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code !== 'ERR_STREAM_PREMATURE_CLOSE') {
      logger.error('Stream error', { error });
    }
  }
});
```

**GOOD — Stream processing cho CSV transformation:**
```typescript
import { createReadStream } from 'node:fs';
import { Transform } from 'node:stream';
import { pipeline } from 'node:stream/promises';
import csv from 'csv-parse';

// GOOD: Process CSV row by row, memory = 1 row at a time
async function processLargeCSV(filePath: string): Promise<number> {
  let processedCount = 0;

  const parser = csv.parse({ columns: true });

  const processor = new Transform({
    objectMode: true,
    transform(row, _encoding, callback) {
      processedCount++;
      // Process từng row, không giữ tất cả trong memory
      processRow(row)
        .then(() => callback())
        .catch(callback);
    },
  });

  await pipeline(
    createReadStream(filePath),
    parser,
    processor
  );

  return processedCount;
}
```

### Phòng ngừa

- [ ] KHÔNG dùng `readFile` cho file > 10MB — dùng `createReadStream`
- [ ] Sử dụng `pipeline()` cho stream chaining
- [ ] Set `highWaterMark` phù hợp (16KB - 256KB)
- [ ] Limit upload size trong middleware
- [ ] Monitor heap usage: `process.memoryUsage().heapUsed`

---

## Pattern 10: Timeout Thiếu Cho HTTP

### Tên
Timeout Thiếu Cho HTTP Request (Missing HTTP Timeout)

### Phân loại
Resource Management / Network / Timeout

### Mức nghiêm trọng
HIGH 🟠

> HTTP request gọi external service không set timeout. Nếu service treo → request chờ vô hạn → connection pool cạn kiệt → toàn bộ app bị block.

### Vấn đề

```
Node.js app ──────── fetch('https://slow-api.com/data') ──────►
                     │
                     │  Không có timeout
                     │  slow-api.com treo / không respond
                     │
                     ▼
              Chờ... 1 phút
              Chờ... 5 phút
              Chờ... 30 phút
              Chờ... vĩnh viễn!

  Connection pool:
  [WAITING] [WAITING] [WAITING] [WAITING] [WAITING]
  All connections waiting → New requests BLOCKED
```

### Phát hiện

```bash
# Tìm fetch không có timeout/signal
rg --type js --type ts "fetch\(" -A 5 | grep -v "timeout\|signal\|AbortSignal" | head -20

# Tìm axios không có timeout config
rg --type js --type ts "axios\.(get|post|put|delete)\(" -A 5 | grep -v "timeout" | head -20

# Tìm http.request không có timeout
rg --type js --type ts "http\.request\(|https\.request\(" -A 10 | grep -v "timeout" | head -20
```

### Giải pháp

**BAD — Fetch không timeout:**
```typescript
// BAD: Nếu API treo, request chờ vĩnh viễn
async function getExternalData(id: string) {
  const response = await fetch(`https://api.example.com/data/${id}`);
  return response.json();
}
```

**GOOD — AbortSignal.timeout:**
```typescript
// GOOD: Timeout 10 giây, tự động abort
async function getExternalData(id: string): Promise<ExternalData> {
  const response = await fetch(`https://api.example.com/data/${id}`, {
    signal: AbortSignal.timeout(10_000), // 10 giây
    headers: { 'Accept': 'application/json' },
  });

  if (!response.ok) {
    throw new Error(`API error: ${response.status}`);
  }

  return response.json();
}
```

**GOOD — Multi-level timeout:**
```typescript
// GOOD: Connection timeout + response timeout + total timeout
import { Agent } from 'undici';

const apiAgent = new Agent({
  connect: {
    timeout: 5_000,    // Connection timeout: 5s
  },
  bodyTimeout: 30_000,  // Body download timeout: 30s
  headersTimeout: 10_000, // Headers timeout: 10s
});

async function getExternalData(id: string): Promise<ExternalData> {
  const controller = new AbortController();

  // Total timeout: 45 giây
  const totalTimeout = setTimeout(() => controller.abort(), 45_000);

  try {
    const response = await fetch(`https://api.example.com/data/${id}`, {
      signal: controller.signal,
      // @ts-expect-error -- undici dispatcher
      dispatcher: apiAgent,
    });

    if (!response.ok) {
      throw new Error(`API error: ${response.status}`);
    }

    return await response.json();
  } finally {
    clearTimeout(totalTimeout);
  }
}
```

### Phòng ngừa

- [ ] Mọi HTTP request PHẢI có timeout (connection + total)
- [ ] Sử dụng `AbortSignal.timeout()` cho fetch
- [ ] Set default timeout trong axios instance: `axios.create({ timeout: 10000 })`
- [ ] Multi-level timeout: connect < headers < body < total
- [ ] Circuit breaker cho external dependencies

---

## Pattern 11: Redis Client Reconnect

### Tên
Redis Client Reconnect Thiếu (Missing Redis Auto-Reconnect)

### Phân loại
Resource Management / Cache / Connection

### Mức nghiêm trọng
MEDIUM 🟡

> Redis client disconnect (network blip, Redis restart) nhưng không có auto-reconnect strategy. App tiếp tục gọi Redis → errors → cache miss storm → DB overload.

### Vấn đề

```
App ──── Redis Client ──── Redis Server
              │
              │  Network blip / Redis restart
              │
              ▼
         DISCONNECTED
              │
              │  App tiếp tục gọi Redis
              │
              ▼
         Error: Connection closed
         Error: Connection closed
         Error: Connection closed
              │
              ▼
         Cache miss → DB query
         Cache miss → DB query    ← Storm!
         Cache miss → DB query
              │
              ▼
         DB OVERLOADED
```

### Phát hiện

```bash
# Tìm Redis client creation
rg --type js --type ts "new Redis\(|createClient\(|ioredis" | head -10

# Tìm thiếu reconnect config
rg --type js --type ts "retryStrategy|reconnectOnError|retry_strategy" | head -10

# Tìm thiếu error handler cho Redis
rg --type js --type ts "redis.*\.on\('error'" | head -10
```

### Giải pháp

**BAD — Redis client không handle disconnect:**
```typescript
// BAD: Không retry, không error handling
import Redis from 'ioredis';

const redis = new Redis({
  host: 'redis.example.com',
  port: 6379,
});

// Không handle connection errors
// Không có reconnect strategy
```

**GOOD — Resilient Redis client:**
```typescript
import Redis from 'ioredis';

const redis = new Redis({
  host: process.env.REDIS_HOST ?? 'localhost',
  port: Number(process.env.REDIS_PORT ?? 6379),
  password: process.env.REDIS_PASSWORD,

  // Reconnect strategy
  retryStrategy: (times: number) => {
    if (times > 10) {
      logger.error('Redis: max retries reached, giving up');
      return null; // Stop retrying
    }
    // Exponential backoff: 100ms, 200ms, 400ms, ..., max 30s
    const delay = Math.min(100 * Math.pow(2, times - 1), 30000);
    logger.warn(`Redis: reconnecting in ${delay}ms (attempt ${times})`);
    return delay;
  },

  // Auto-reconnect on specific errors
  reconnectOnError: (err: Error) => {
    const targetErrors = ['READONLY', 'ECONNRESET', 'ETIMEDOUT'];
    return targetErrors.some((e) => err.message.includes(e));
  },

  maxRetriesPerRequest: 3,
  enableReadyCheck: true,
  lazyConnect: false,
});

// Event handlers
redis.on('connect', () => logger.info('Redis: connected'));
redis.on('ready', () => logger.info('Redis: ready'));
redis.on('error', (err) => logger.error('Redis: error', { error: err.message }));
redis.on('close', () => logger.warn('Redis: connection closed'));
redis.on('reconnecting', (delay: number) => {
  logger.info(`Redis: reconnecting in ${delay}ms`);
});

// Graceful cache fallback
async function getCached<T>(
  key: string,
  fallback: () => Promise<T>,
  ttl = 300
): Promise<T> {
  try {
    const cached = await redis.get(key);
    if (cached) return JSON.parse(cached);
  } catch (error) {
    // Redis down → fallback to source, không crash
    logger.warn('Redis get failed, using fallback', { key, error });
  }

  const data = await fallback();

  // Try to cache, nhưng không fail nếu Redis down
  try {
    await redis.setex(key, ttl, JSON.stringify(data));
  } catch {
    // Silent fail — cache miss acceptable
  }

  return data;
}
```

### Phòng ngừa

- [ ] Cấu hình `retryStrategy` với exponential backoff
- [ ] Handle tất cả Redis events: `connect`, `ready`, `error`, `close`
- [ ] Implement cache fallback — app vẫn hoạt động khi Redis down
- [ ] Set `maxRetriesPerRequest` để tránh request chờ quá lâu
- [ ] Health check endpoint kiểm tra Redis connection status

---

## Pattern 12: Buffer Pool Overflow

### Tên
Buffer Pool Overflow (V8 Heap Grow Do Buffer Allocation)

### Phân loại
Resource Management / Memory / Buffer

### Mức nghiêm trọng
HIGH 🟠

> Tạo Buffer lớn liên tục (image processing, file upload, crypto operations). Buffer > 8KB allocated trong V8 Old Space, không dễ GC. Heap grow dần → OOM.

### Vấn đề

```
Image processing service:

  Request 1: Buffer.alloc(10MB)  → Old Space
  Request 2: Buffer.alloc(10MB)  → Old Space
  ...
  V8 Old Space keeps growing

  V8 Heap:
  ┌───────────────────────────────────┐
  │ Old Space                         │
  │ ┌─────┐ ┌─────┐ ┌─────┐         │
  │ │10MB │ │10MB │ │10MB │ ...      │
  │ │Buf1 │ │Buf2 │ │Buf3 │         │
  │ └─────┘ └─────┘ └─────┘         │
  │                                   │
  │ GC chạy nhưng Buffers vẫn        │
  │ reachable (trong processing)      │
  │                                   │
  │ Concurrent processing =           │
  │ N × 10MB simultaneously!          │
  └───────────────────────────────────┘
```

### Phát hiện

```bash
# Tìm large Buffer allocation
rg --type js --type ts "Buffer\.(alloc|allocUnsafe|from)\(" | head -20

# Tìm accumulation pattern (push to array)
rg --type js --type ts "\.push\(.*[Bb]uffer\|chunks\.push\|buffers\.push" | head -20

# Tìm Buffer.concat (potential large allocation)
rg --type js --type ts "Buffer\.concat\(" | head -20
```

### Giải pháp

**BAD — Accumulate buffers trong memory:**
```typescript
// BAD: Collect tất cả chunks vào memory rồi process
app.post('/upload', async (req, res) => {
  const chunks: Buffer[] = [];

  req.on('data', (chunk: Buffer) => {
    chunks.push(chunk); // Accumulate tất cả vào memory
  });

  req.on('end', () => {
    const fullBuffer = Buffer.concat(chunks); // Duplicate toàn bộ!
    processImage(fullBuffer); // Thêm 1 copy nữa
    // 3x memory: chunks + concat + processing
  });
});
```

**GOOD — Stream processing, limit concurrency:**
```typescript
import { pipeline } from 'node:stream/promises';
import { Transform } from 'node:stream';
import pLimit from 'p-limit';

// Limit concurrent heavy operations
const processLimit = pLimit(3); // Max 3 concurrent image processes

app.post('/upload', async (req, res) => {
  // Limit upload size
  const MAX_SIZE = 10 * 1024 * 1024; // 10MB
  let receivedBytes = 0;

  const sizeChecker = new Transform({
    transform(chunk: Buffer, _encoding, callback) {
      receivedBytes += chunk.length;
      if (receivedBytes > MAX_SIZE) {
        callback(new Error('File too large'));
        return;
      }
      callback(null, chunk);
    },
  });

  try {
    // Stream to temp file instead of memory
    const tempPath = path.join(TEMP_DIR, `upload-${Date.now()}`);
    const writeStream = fs.createWriteStream(tempPath);

    await pipeline(req, sizeChecker, writeStream);

    // Process with concurrency limit
    const result = await processLimit(() => processImageFile(tempPath));

    res.json(result);
  } catch (error) {
    if ((error as Error).message === 'File too large') {
      return res.status(413).json({ error: 'File exceeds 10MB limit' });
    }
    res.status(500).json({ error: 'Upload failed' });
  }
});
```

**GOOD — ObjectPool cho reusable buffers:**
```typescript
class BufferPool {
  private pool: Buffer[] = [];
  private readonly bufferSize: number;
  private readonly maxPoolSize: number;

  constructor(bufferSize: number, maxPoolSize = 10) {
    this.bufferSize = bufferSize;
    this.maxPoolSize = maxPoolSize;
  }

  acquire(): Buffer {
    const buf = this.pool.pop();
    if (buf) {
      buf.fill(0); // Clear previous data
      return buf;
    }
    return Buffer.alloc(this.bufferSize);
  }

  release(buf: Buffer): void {
    if (buf.length === this.bufferSize && this.pool.length < this.maxPoolSize) {
      this.pool.push(buf);
    }
    // Nếu pool đầy, buffer sẽ được GC bình thường
  }
}

// Sử dụng
const imageBufferPool = new BufferPool(1024 * 1024); // 1MB buffers

async function processChunk(data: Buffer): Promise<void> {
  const workBuffer = imageBufferPool.acquire();
  try {
    data.copy(workBuffer);
    await doProcessing(workBuffer);
  } finally {
    imageBufferPool.release(workBuffer); // Trả lại pool
  }
}
```

### Phòng ngừa

- [ ] Stream processing thay vì accumulate toàn bộ vào memory
- [ ] Limit concurrent heavy operations với `p-limit`
- [ ] Limit upload/download size trong middleware
- [ ] Sử dụng Buffer pool cho repeated allocations
- [ ] Monitor V8 heap: `process.memoryUsage()` metrics
- [ ] Set `--max-old-space-size` phù hợp với available RAM

```bash
# Monitor memory usage
node --max-old-space-size=2048 --expose-gc app.js

# Heap snapshot
node --inspect app.js
# Chrome DevTools → Memory → Take Heap Snapshot
```

---

## Bảng Tóm Tắt

| Code | Pattern | Mức độ | Tác động chính |
|------|---------|--------|----------------|
| RM-01 | Memory Leak Qua Closure | 🔴 CRITICAL | OOM crash, heap exhaustion |
| RM-02 | Connection Pool Exhaustion | 🔴 CRITICAL | Service down, request timeout |
| RM-03 | File Descriptor Leak | 🟠 HIGH | EMFILE error, cannot accept connections |
| RM-04 | Global Variable Memory | 🟠 HIGH | Gradual heap growth → OOM |
| RM-05 | Express Middleware Leak | 🟡 MEDIUM | High memory per request |
| RM-06 | Child Process Zombie | 🟠 HIGH | PID exhaustion, resource waste |
| RM-07 | HTTP Agent Connection | 🟡 MEDIUM | Port exhaustion, target overload |
| RM-08 | DNS Cache Thiếu | 🟡 MEDIUM | Unnecessary latency per request |
| RM-09 | Large File Memory | 🟠 HIGH | OOM on large file processing |
| RM-10 | Timeout Thiếu Cho HTTP | 🟠 HIGH | Connection pool exhaustion, cascade failure |
| RM-11 | Redis Client Reconnect | 🟡 MEDIUM | Cache miss storm → DB overload |
| RM-12 | Buffer Pool Overflow | 🟠 HIGH | V8 heap growth → OOM |

## Quick Scan Script

```bash
#!/bin/bash
echo "=== Node.js Resource Management Audit ==="

echo -e "\n--- RM-01: Closure Memory Leak ---"
rg --type js --type ts "\.on\(|\.addEventListener\(" -c 2>/dev/null | sort -t: -k2 -rn | head -5

echo -e "\n--- RM-02: Connection Pool ---"
rg --type js --type ts "pool\.(acquire|connect|getConnection)\(\)" -c 2>/dev/null

echo -e "\n--- RM-03: File Descriptor ---"
rg --type js --type ts "createReadStream|createWriteStream" -c 2>/dev/null

echo -e "\n--- RM-04: Global Cache ---"
rg --type js --type ts "^(export )?(const|let) \w+ = new (Map|Set)\(" 2>/dev/null

echo -e "\n--- RM-06: Child Process ---"
rg --type js --type ts "spawn\(|exec\(|execFile\(" -c 2>/dev/null

echo -e "\n--- RM-09: Large File Read ---"
rg --type js --type ts "readFile(Sync)?\(" 2>/dev/null | grep -v node_modules

echo -e "\n--- RM-10: HTTP Timeout ---"
rg --type js --type ts "fetch\(" -A 5 2>/dev/null | grep -v "timeout\|signal\|AbortSignal" | head -10

echo -e "\n--- RM-12: Buffer Accumulation ---"
rg --type js --type ts "\.push\(.*[Bb]uffer\|Buffer\.concat\(" 2>/dev/null

echo -e "\n=== Scan Complete ==="
```
