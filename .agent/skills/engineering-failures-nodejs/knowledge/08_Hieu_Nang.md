# Domain 08: Hiệu Năng Và Mở Rộng (Performance & Scalability)

> Node.js/TypeScript patterns liên quan đến performance: event loop blocking, memory leaks, clustering, V8 optimization.

---

## Pattern 01: Event Loop Blocking

### Tên
Event Loop Blocking (Chặn Event Loop Bằng Synchronous Code)

### Phân loại
Performance / Event Loop / Blocking

### Mức nghiêm trọng
CRITICAL 🔴

### Vấn đề

```
Event Loop: single thread handles ALL requests
Blocking operation → ALL other requests wait

Request A ──JSON.parse(100MB)──────────── Response A
Request B ──────────────wait──────────── wait───────── Response B
Request C ──────────────wait──────────── wait───────── Response C
                        ↑ 2 seconds blocked = ALL requests stalled
```

### Phát hiện

```bash
rg --type ts --type js "readFileSync|writeFileSync|existsSync" -n --glob "!*test*"
rg --type ts --type js "JSON\.parse\(|JSON\.stringify\(" -n
rg --type ts --type js "crypto\.(pbkdf2Sync|scryptSync|randomBytes)" -n
rg --type ts --type js "child_process.*execSync" -n
```

### Giải pháp

❌ **BAD**
```typescript
app.get('/process', (req, res) => {
  const data = fs.readFileSync('/large/file.json', 'utf-8'); // Blocks!
  const parsed = JSON.parse(data); // Blocks for large files!
  const hash = crypto.pbkdf2Sync(password, salt, 100000, 64, 'sha512'); // Blocks!
  res.json(parsed);
});
```

✅ **GOOD**
```typescript
import { createReadStream } from 'fs';
import { pipeline } from 'stream/promises';

app.get('/process', async (req, res) => {
  // Async file read:
  const data = await fs.promises.readFile('/large/file.json', 'utf-8');

  // Stream large JSON:
  const stream = createReadStream('/large/file.json');
  const parsed = await streamJSON(stream);

  // Async crypto:
  const hash = await new Promise<Buffer>((resolve, reject) =>
    crypto.pbkdf2(password, salt, 100000, 64, 'sha512', (err, key) =>
      err ? reject(err) : resolve(key)
    )
  );

  // Or use worker_threads for CPU-intensive work:
  const result = await runInWorker('./heavy-computation.js', data);
  res.json(result);
});
```

### Phòng ngừa
- [ ] NEVER use `*Sync` functions in server code
- [ ] `worker_threads` for CPU-intensive operations
- [ ] Stream large files instead of loading to memory
- Tool: `clinic doctor` to detect event loop blocking

---

## Pattern 02: Memory Leak

### Tên
Memory Leak (Rò Rỉ Bộ Nhớ Trong Long-Running Process)

### Phân loại
Performance / Memory / Leak

### Mức nghiêm trọng
CRITICAL 🔴

### Vấn đề

```
Server starts: 50MB RSS
After 1 hour: 200MB
After 24 hours: 1.5GB → OOM killed!

Common causes:
├── Event listeners not removed
├── Global caches without eviction
├── Closures capturing large objects
└── Timers not cleared
```

### Phát hiện

```bash
rg --type ts --type js "addEventListener|\.on\(" -n | rg -v "removeEventListener|\.off\("
rg --type ts --type js "setInterval|setTimeout" -n | rg -v "clearInterval|clearTimeout"
rg --type ts --type js "global\.\w+\s*=|globalThis\.\w+" -n
rg --type ts --type js "new Map\(\)|new Set\(\)|= \{\}" -n --glob "!*test*"
```

### Giải pháp

❌ **BAD**
```typescript
// Global cache grows forever:
const cache = new Map<string, any>();
app.get('/user/:id', async (req, res) => {
  if (!cache.has(req.params.id)) {
    cache.set(req.params.id, await db.getUser(req.params.id));
  }
  res.json(cache.get(req.params.id)); // Cache never evicted!
});

// Event listener leak:
class Worker {
  start() {
    process.on('message', this.handleMessage); // Added each time start() called!
  }
}
```

✅ **GOOD**
```typescript
// LRU cache with size limit:
import { LRUCache } from 'lru-cache';
const cache = new LRUCache<string, User>({ max: 1000, ttl: 300_000 });

// WeakRef for optional caching:
const weakCache = new Map<string, WeakRef<object>>();

// Clean up event listeners:
class Worker {
  private handler = this.handleMessage.bind(this);

  start() {
    process.on('message', this.handler);
  }

  stop() {
    process.off('message', this.handler); // Remove listener!
  }
}

// Clear timers:
const timer = setInterval(poll, 5000);
process.on('SIGTERM', () => clearInterval(timer));
```

### Phòng ngừa
- [ ] LRU cache with size/TTL limits
- [ ] Remove event listeners on cleanup
- [ ] Clear intervals/timeouts
- Tool: `--inspect` + Chrome DevTools heap snapshot, `clinic heapprofile`

---

## Pattern 03: JSON Parse/Stringify Large Objects

### Tên
JSON Parse/Stringify Large Objects (V8 Main Thread Blocked)

### Phân loại
Performance / JSON / CPU

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```typescript
// 50MB JSON string:
const data = JSON.parse(hugeString); // Blocks event loop for seconds!
const output = JSON.stringify(hugeObject); // Same problem!
// V8 JSON parser is single-threaded, synchronous
```

### Phát hiện

```bash
rg --type ts --type js "JSON\.(parse|stringify)\(" -n
rg --type ts --type js "stream.*json|JSONStream|stream-json" -n
```

### Giải pháp

❌ **BAD**
```typescript
const response = await fetch(url);
const text = await response.text();
const data = JSON.parse(text); // 100MB parse blocks event loop
```

✅ **GOOD**
```typescript
// Option 1: Streaming JSON parser
import { parser } from 'stream-json';
import { streamArray } from 'stream-json/streamers/StreamArray';

const pipeline = createReadStream('large.json')
  .pipe(parser())
  .pipe(streamArray());

for await (const { value } of pipeline) {
  processItem(value); // Process one item at a time
}

// Option 2: Worker thread for large JSON
import { Worker } from 'worker_threads';

async function parseInWorker(jsonString: string) {
  return new Promise((resolve, reject) => {
    const worker = new Worker('./json-worker.js', {
      workerData: jsonString,
    });
    worker.on('message', resolve);
    worker.on('error', reject);
  });
}
```

### Phòng ngừa
- [ ] Stream large JSON files
- [ ] Worker threads for large JSON parsing
- [ ] Paginate API responses to avoid large payloads
- Tool: `stream-json`, `worker_threads`

---

## Pattern 04: Cluster Module Sai Config

### Tên
Cluster Module Sai Config (Incorrect Multi-Process Setup)

### Phân loại
Performance / Scaling / Process

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```typescript
// Single process = single CPU core used
// 8-core server using only 1 core = 87.5% wasted
// Or: cluster.fork() without proper management
// Worker crashes → not restarted → gradually lose capacity
```

### Phát hiện

```bash
rg --type ts --type js "cluster\.(fork|isMaster|isPrimary)" -n
rg --type ts --type js "pm2|PM2" -n --glob "*.json" --glob "*.config.*"
rg --type ts --type js "worker_threads" -n
```

### Giải pháp

❌ **BAD**
```typescript
// Only 1 process:
app.listen(3000);

// Or: no worker restart on crash:
import cluster from 'cluster';
if (cluster.isPrimary) {
  for (let i = 0; i < 4; i++) cluster.fork();
  // Worker crashes → not replaced!
}
```

✅ **GOOD**
```typescript
// PM2 ecosystem config (recommended):
// ecosystem.config.js
module.exports = {
  apps: [{
    name: 'api',
    script: './dist/server.js',
    instances: 'max',        // Use all CPU cores
    exec_mode: 'cluster',
    max_memory_restart: '500M',
    env_production: {
      NODE_ENV: 'production',
    },
  }],
};

// Or manual cluster with restart:
import cluster from 'cluster';
import os from 'os';

if (cluster.isPrimary) {
  const numCPUs = os.cpus().length;
  for (let i = 0; i < numCPUs; i++) {
    cluster.fork();
  }
  cluster.on('exit', (worker, code) => {
    logger.warn({ pid: worker.process.pid, code }, 'Worker died, restarting');
    cluster.fork(); // Replace dead worker
  });
}
```

### Phòng ngừa
- [ ] PM2 for production process management
- [ ] Restart workers on crash
- [ ] Match instances to CPU cores
- Tool: PM2, `cluster` module

---

## Pattern 05: Connection Pool Thiếu

### Tên
Connection Pool Thiếu (Creating New Connection Per Request)

### Phân loại
Performance / Database / Connection

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```typescript
app.get('/users', async (req, res) => {
  const client = new Client(dbConfig); // New connection!
  await client.connect();               // TCP handshake + auth
  const result = await client.query('SELECT * FROM users');
  await client.end();                    // Connection closed
  res.json(result.rows);
});
// Each request: ~50ms connection overhead
// Under load: connection exhaustion
```

### Phát hiện

```bash
rg --type ts --type js "new Client\(|new Pool\(|createPool\(|createConnection\(" -n
rg --type ts --type js "\.connect\(\)" -n
rg --type ts --type js "pool" -i -n --glob "*db*" --glob "*database*"
```

### Giải pháp

❌ **BAD**
```typescript
async function query(sql: string) {
  const client = new pg.Client(config);
  await client.connect();
  const result = await client.query(sql);
  await client.end();
  return result;
}
```

✅ **GOOD**
```typescript
// Shared connection pool (created once):
const pool = new pg.Pool({
  host: process.env.DB_HOST,
  max: 20,                    // Max connections in pool
  idleTimeoutMillis: 30000,   // Close idle connections after 30s
  connectionTimeoutMillis: 5000, // Fail fast if can't connect
});

async function query(sql: string, params?: any[]) {
  const result = await pool.query(sql, params);
  return result; // Connection automatically returned to pool
}

// Graceful shutdown:
process.on('SIGTERM', async () => {
  await pool.end();
});
```

### Phòng ngừa
- [ ] ALWAYS use connection pools
- [ ] Pool size: 2-5x CPU cores
- [ ] Connection timeout + idle timeout
- Tool: `pg-pool`, Prisma, TypeORM pool configs

---

## Pattern 06: Buffer Concatenation Sai

### Tên
Buffer Concatenation Sai (Inefficient Buffer Building)

### Phân loại
Performance / Buffer / Allocation

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```typescript
let result = Buffer.alloc(0);
for (const chunk of chunks) {
  result = Buffer.concat([result, chunk]); // Copies ENTIRE buffer each time!
  // O(n²) — same as string += in loop
}
```

### Phát hiện

```bash
rg --type ts --type js "Buffer\.concat" -n
rg --type ts --type js "Buffer\.alloc\(0\)" -n
```

### Giải pháp

❌ **BAD**
```typescript
let data = Buffer.alloc(0);
stream.on('data', (chunk: Buffer) => {
  data = Buffer.concat([data, chunk]); // Quadratic!
});
```

✅ **GOOD**
```typescript
// Collect chunks, concat once:
const chunks: Buffer[] = [];
stream.on('data', (chunk: Buffer) => {
  chunks.push(chunk); // O(1) per chunk
});
stream.on('end', () => {
  const data = Buffer.concat(chunks); // Single allocation
});

// Or use pipeline for streams:
import { pipeline } from 'stream/promises';
await pipeline(source, transform, destination);
```

### Phòng ngừa
- [ ] Collect chunks in array, `concat` once at end
- [ ] Use `stream.pipeline()` for stream processing
- [ ] Avoid growing buffers in loops
- Tool: Benchmark with `Buffer.byteLength`

---

## Pattern 07: Crypto Sync Blocking

### Tên
Crypto Sync Blocking (Synchronous Crypto Blocks Event Loop)

### Phân loại
Performance / Crypto / Blocking

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```typescript
// pbkdf2Sync with 100,000 iterations:
const hash = crypto.pbkdf2Sync(password, salt, 100000, 64, 'sha512');
// Blocks event loop for ~100ms!
// 10 concurrent logins = 1 second queue
```

### Phát hiện

```bash
rg --type ts --type js "pbkdf2Sync|scryptSync|randomFillSync" -n
rg --type ts --type js "crypto\.\w+Sync\(" -n
rg --type ts --type js "hashSync|compareSync" -n
```

### Giải pháp

❌ **BAD**
```typescript
const hash = crypto.pbkdf2Sync(password, salt, 100000, 64, 'sha512');
const bytes = crypto.randomFillSync(Buffer.alloc(32));
```

✅ **GOOD**
```typescript
// Async versions (use libuv thread pool):
const hash = await new Promise<Buffer>((resolve, reject) =>
  crypto.pbkdf2(password, salt, 100000, 64, 'sha512', (err, key) =>
    err ? reject(err) : resolve(key)
  )
);

// Or promisified:
import { promisify } from 'util';
const pbkdf2 = promisify(crypto.pbkdf2);
const hash = await pbkdf2(password, salt, 100000, 64, 'sha512');

// bcrypt — async by default:
import bcrypt from 'bcrypt';
const hashed = await bcrypt.hash(password, 12);
const match = await bcrypt.compare(password, hashed);
```

### Phòng ngừa
- [ ] NEVER use `*Sync` crypto functions in server code
- [ ] Use async versions or promisify
- [ ] bcrypt/argon2 libraries are async by default
- Tool: ESLint custom rule to ban `*Sync`

---

## Pattern 08: Response Compression Thiếu

### Tên
Response Compression Thiếu (Uncompressed HTTP Responses)

### Phân loại
Performance / HTTP / Bandwidth

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```
API response: 500KB JSON
With gzip: ~50KB (90% reduction!)
Without compression: 10x bandwidth, 10x slower on slow networks
```

### Phát hiện

```bash
rg --type ts --type js "compression|compress" -n --glob "*app*" --glob "*server*"
rg --type ts --type js "Content-Encoding|gzip|brotli|deflate" -n
```

### Giải pháp

❌ **BAD**
```typescript
const app = express();
// No compression middleware
app.get('/data', (req, res) => {
  res.json(largeDataset); // 500KB uncompressed
});
```

✅ **GOOD**
```typescript
import compression from 'compression';

const app = express();
app.use(compression({
  threshold: 1024,  // Only compress >1KB
  level: 6,         // Balanced speed/compression
  filter: (req, res) => {
    if (req.headers['x-no-compression']) return false;
    return compression.filter(req, res);
  },
}));

// Better: let reverse proxy (nginx) handle compression:
// nginx.conf:
// gzip on;
// gzip_types application/json text/plain application/javascript;
// gzip_min_length 1000;
```

### Phòng ngừa
- [ ] `compression` middleware for Express
- [ ] Or nginx/CDN handles compression
- [ ] Brotli for better compression ratio
- Tool: `compression` npm package, nginx gzip

---

## Pattern 09: Middleware Overhead

### Tên
Middleware Overhead (Unnecessary Middleware Per Request)

### Phân loại
Performance / Express / Middleware

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```typescript
app.use(bodyParser.json({ limit: '50mb' })); // Parses ALL requests
app.use(bodyParser.urlencoded());              // Even GET requests
app.use(cors());                               // Even internal requests
app.use(helmet());                             // 15 headers on every response
app.use(morgan('combined'));                    // Logs every request
app.use(session({...}));                        // Session lookup for stateless API
```

### Phát hiện

```bash
rg --type ts --type js "app\.use\(" -n --glob "*app*" --glob "*server*"
rg --type ts --type js "bodyParser|body-parser|express\.json" -n
```

### Giải pháp

❌ **BAD**
```typescript
// Everything applied globally:
app.use(express.json({ limit: '50mb' }));
app.use(session({ store: redisStore }));
app.use(passport.initialize());
```

✅ **GOOD**
```typescript
// Global — lightweight only:
app.use(compression());
app.use(helmet());

// Route-specific middleware:
const apiRouter = express.Router();
apiRouter.use(express.json({ limit: '1mb' }));
apiRouter.use(authMiddleware);

const uploadRouter = express.Router();
uploadRouter.use(express.json({ limit: '50mb' }));

app.use('/api', apiRouter);
app.use('/upload', uploadRouter);
app.use('/health', (req, res) => res.json({ status: 'ok' })); // No middleware!
```

### Phòng ngừa
- [ ] Apply middleware to specific routes, not globally
- [ ] Smaller body limits per route
- [ ] Health check bypasses all middleware
- Tool: Express request timing

---

## Pattern 10: Hot Code Path Allocation

### Tên
Hot Code Path Allocation (V8 Hidden Class Deoptimization)

### Phân loại
Performance / V8 / Optimization

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```typescript
function createPoint(x: number, y: number) {
  const p: any = {};
  p.x = x;           // Hidden class transition 1
  p.y = y;           // Hidden class transition 2
  if (x > 0) p.z = 0; // CONDITIONAL property → deopt!
  return p;
}
// V8 can't optimize: object shape varies between calls
```

### Phát hiện

```bash
rg --type ts --type js "delete\s+\w+\.\w+" -n
rg --type ts --type js ":\s*any\s*=" -n
# node --trace-deopt app.js | grep "deoptimiz"
```

### Giải pháp

❌ **BAD**
```typescript
function processItem(item: any) {
  const result: any = {};
  result.id = item.id;
  if (item.name) result.name = item.name; // Varying shape!
  delete result.temp; // delete triggers deopt!
  return result;
}
```

✅ **GOOD**
```typescript
// Consistent object shape:
interface ProcessedItem {
  id: number;
  name: string | null;
}

function processItem(item: RawItem): ProcessedItem {
  return {
    id: item.id,
    name: item.name ?? null, // Always has name property
  };
}

// Pre-define object shape:
class Point {
  x: number;
  y: number;
  z: number;
  constructor(x: number, y: number, z: number = 0) {
    this.x = x;
    this.y = y;
    this.z = z; // Always present
  }
}
```

### Phòng ngừa
- [ ] Consistent object shapes (same properties, same order)
- [ ] NEVER use `delete` on objects in hot paths
- [ ] TypeScript interfaces enforce consistent shape
- Tool: `node --trace-deopt`, V8 profiler

---

## Pattern 11: Static File Serving Thiếu

### Tên
Static File Serving Thiếu (Express Serves Static Files)

### Phân loại
Performance / HTTP / Static

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```typescript
app.use(express.static('public')); // Node.js serves static files
// Node.js: single-threaded, interprets each request
// nginx/CDN: optimized C code, sendfile(), caching headers
// 10x-100x performance difference for static assets
```

### Phát hiện

```bash
rg --type ts --type js "express\.static\(|serve-static" -n
rg "location.*static|proxy_pass" -n --glob "nginx*"
```

### Giải pháp

❌ **BAD**
```typescript
// Node.js serves everything including static files:
app.use(express.static('public'));
app.use('/uploads', express.static('uploads'));
```

✅ **GOOD**
```nginx
# nginx handles static files:
server {
    location /static/ {
        alias /var/www/public/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    location /api/ {
        proxy_pass http://node-backend:3000;
    }
}
```

```typescript
// Node.js only handles API:
app.use('/api', apiRouter);
// Static files served by nginx/CDN
```

### Phòng ngừa
- [ ] nginx or CDN for static files
- [ ] Node.js only for dynamic API requests
- [ ] Cache headers for static assets
- Tool: nginx, CloudFront, Cloudflare

---

## Pattern 12: HTTP/2 Thiếu

### Tên
HTTP/2 Thiếu (Not Enabling HTTP/2)

### Phân loại
Performance / HTTP / Protocol

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```
HTTP/1.1:                          HTTP/2:
├── 6 connections per domain       ├── 1 connection, multiplexed
├── Head-of-line blocking          ├── No HOL blocking
├── No header compression          ├── HPACK header compression
├── No server push                 ├── Server push available
└── Text protocol                  └── Binary protocol
```

### Phát hiện

```bash
rg --type ts --type js "http2|createSecureServer" -n
rg --type ts --type js "createServer\(|\.listen\(" -n
rg "http2|h2" -n --glob "nginx*"
```

### Giải pháp

❌ **BAD**
```typescript
import http from 'http';
const server = http.createServer(app);
server.listen(3000); // HTTP/1.1 only
```

✅ **GOOD**
```typescript
// Node.js native HTTP/2:
import http2 from 'http2';
import fs from 'fs';

const server = http2.createSecureServer({
  key: fs.readFileSync('key.pem'),
  cert: fs.readFileSync('cert.pem'),
});

// Or: let nginx/load balancer handle HTTP/2:
// nginx.conf:
// listen 443 ssl http2;
// Most common approach — nginx terminates HTTP/2,
// proxies HTTP/1.1 to Node.js backend
```

### Phòng ngừa
- [ ] Enable HTTP/2 at reverse proxy level
- [ ] TLS required for HTTP/2 in browsers
- [ ] Reduces connection overhead significantly
- Tool: nginx `http2` directive, `h2spec` for testing

---

## Pattern 13: Regex Not Precompiled

### Tên
Regex Not Precompiled (Creating Regex Per Request)

### Phân loại
Performance / Regex / Compilation

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```typescript
app.get('/validate', (req, res) => {
  const emailRegex = new RegExp('^[\\w.-]+@[\\w.-]+\\.\\w+$'); // Compiled per request!
  const isValid = emailRegex.test(req.query.email);
  res.json({ valid: isValid });
});
```

### Phát hiện

```bash
rg --type ts --type js "new RegExp\(" -n
rg --type ts --type js "new RegExp" -B 3 -n | rg "(function|=>|app\.|router\.)"
```

### Giải pháp

❌ **BAD**
```typescript
function validate(input: string): boolean {
  return new RegExp('^\\d{4}-\\d{2}-\\d{2}$').test(input); // Per call
}
```

✅ **GOOD**
```typescript
// Module-level — compiled once:
const DATE_REGEX = /^\d{4}-\d{2}-\d{2}$/;
const EMAIL_REGEX = /^[\w.-]+@[\w.-]+\.\w+$/;

function validateDate(input: string): boolean {
  return DATE_REGEX.test(input);
}

// For dynamic patterns — cache:
const regexCache = new Map<string, RegExp>();
function getRegex(pattern: string): RegExp {
  let regex = regexCache.get(pattern);
  if (!regex) {
    regex = new RegExp(pattern);
    regexCache.set(pattern, regex);
  }
  return regex;
}
```

### Phòng ngừa
- [ ] Regex literals (`/pattern/`) at module level
- [ ] Cache dynamically created regex
- [ ] Avoid `new RegExp()` in hot paths
- Tool: ESLint `prefer-regex-literals`
