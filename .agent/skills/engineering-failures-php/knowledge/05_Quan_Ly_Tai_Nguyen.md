# Domain 05: Quản Lý Tài Nguyên (Resource Management)

> PHP patterns liên quan đến quản lý tài nguyên: database connections, file handles, memory, processes.

| Thuộc tính | Giá trị |
|-----------|---------|
| **Lĩnh vực** | Quản Lý Tài Nguyên |
| **Số mẫu** | 10 |
| **Ngôn ngữ** | PHP 8.x / Laravel / Symfony |
| **Ngày cập nhật** | 2026-02-18 |

---

## Pattern 01: DB Connection Không Close (PDO Persistent)

### Tên
DB Connection Không Close (PDO Persistent Connection Leak)

### Phân loại
Resource Management / Database / Connection Pool

### Mức nghiêm trọng
HIGH 🟠

> Persistent connection không release đúng cách → giữ connection mở vô thời hạn → "Too many connections" → toàn bộ app down.

### Vấn đề

```
PERSISTENT CONNECTION LEAK:

  Request 1: PDO(PERSISTENT=true) + BEGIN TRANSACTION
       │
       ▼
  Exception thrown! → Transaction KHÔNG rollback
       │
       ▼
  Connection #1 stuck (dirty state, lock held)

  Request 2 reuse Connection #1 → dirty transaction state!
  Request 3 → new Connection #2 (dirty cũng leak)
  ...
  Connection #100 → "Too many connections" ❌

  Pool: [DIRTY][DIRTY][DIRTY]...[DIRTY] = 100/100 stuck
```

### Phát hiện

```bash
# Tìm PDO persistent connection
rg --type php "ATTR_PERSISTENT\s*=>\s*true" -n

# Tìm beginTransaction không có rollBack trong catch
rg --type php "beginTransaction\(\)" -A 20 | grep -v "rollBack\|rollback"

# Tìm connection config
rg --type php "'persistent'\s*=>\s*true" -n
```

### Giải pháp

**BAD — Persistent connection không cleanup:**
```php
// BAD: Exception → transaction lock held forever
$pdo = new PDO($dsn, $user, $pass, [PDO::ATTR_PERSISTENT => true]);
$pdo->beginTransaction();
$pdo->exec("UPDATE accounts SET balance = balance - 100 WHERE id = 1");
// Exception here → transaction NEVER rolled back
$pdo->exec("UPDATE accounts SET balance = balance + 100 WHERE id = 2");
$pdo->commit();
```

**GOOD — Always cleanup in finally:**
```php
// GOOD: try/finally đảm bảo rollback
$pdo = new PDO($dsn, $user, $pass, [
    PDO::ATTR_PERSISTENT => false, // Prefer non-persistent
    PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
]);
$pdo->beginTransaction();
try {
    $pdo->exec("UPDATE accounts SET balance = balance - 100 WHERE id = 1");
    $pdo->exec("UPDATE accounts SET balance = balance + 100 WHERE id = 2");
    $pdo->commit();
} catch (\Throwable $e) {
    if ($pdo->inTransaction()) {
        $pdo->rollBack();
    }
    throw $e;
}
```

**GOOD — Laravel middleware reset dirty connections:**
```php
// app/Http/Middleware/ResetDatabaseState.php
class ResetDatabaseState
{
    public function handle(Request $request, Closure $next): Response
    {
        $pdo = DB::connection()->getPdo();
        if ($pdo->inTransaction()) {
            $pdo->rollBack();
            Log::warning('Found dirty persistent connection');
        }
        return $next($request);
    }
}
```

### Phòng ngừa

- [ ] Không dùng `PDO::ATTR_PERSISTENT` trừ khi có cleanup middleware
- [ ] Mọi `beginTransaction()` phải có `try/catch` với `rollBack()`
- [ ] Dùng connection pooler (ProxySQL, PgBouncer) thay persistent PDO
- [ ] Monitor `Threads_connected` trên MySQL

---

## Pattern 02: File Handle Leak

### Tên
File Handle Leak (Rò Rỉ File Handle)

### Phân loại
Resource Management / File System / File Descriptor

### Mức nghiêm trọng
HIGH 🟠

> `fopen()` không `fclose()` khi exception → file descriptor leak. Queue workers chạy lâu → tích lũy → "Too many open files".

### Vấn đề

```
Queue Worker (chạy liên tục):

  Job 1: fopen() → exception → fclose() SKIPPED    FD: 1
  Job 2: fopen() → exception → fclose() SKIPPED    FD: 2
  ...
  Job 1024: fopen() → "Too many open files" ❌

  File Lock:
  Process A: fopen() + LOCK_EX → exception
             fclose() SKIPPED → lock HELD FOREVER
  Process B: fopen() + LOCK_EX → BLOCKED forever!
```

### Phát hiện

```bash
# Tìm fopen không có fclose trong finally
rg --type php "fopen\s*\(" -n

# Tìm flock không có LOCK_UN
rg --type php "flock\s*\(" -n | grep -v "LOCK_UN"

# Tìm file operations trong queue jobs
rg --type php "fopen\s*\(" app/Jobs/ -n
```

### Giải pháp

**BAD — fclose skipped on exception:**
```php
// BAD: Exception → fclose() never called
$handle = fopen($path, 'w');
fputcsv($handle, $header);
foreach ($records as $record) {
    fputcsv($handle, $record); // Exception here → leak!
}
fclose($handle);
```

**GOOD — RAII wrapper:**
```php
// GOOD: Helper đảm bảo cleanup
function withFile(string $path, string $mode, callable $fn): mixed
{
    $handle = fopen($path, $mode);
    if ($handle === false) {
        throw new \RuntimeException("Cannot open: {$path}");
    }
    try {
        return $fn($handle);
    } finally {
        fclose($handle);
    }
}

// Sử dụng
withFile($path, 'w', function ($handle) use ($records): void {
    fputcsv($handle, ['ID', 'Name', 'Email']);
    foreach ($records as $record) {
        fputcsv($handle, $record);
    }
});
```

### Phòng ngừa

- [ ] Mọi `fopen()` phải có `fclose()` trong `finally`
- [ ] Mọi `flock()` phải có `LOCK_UN` trong `finally`
- [ ] Queue jobs dùng RAII wrapper, không `fopen()` trực tiếp
- [ ] Set `ulimit -n 65535` cho worker processes

---

## Pattern 03: Memory Limit Exceed (Large File)

### Tên
Memory Limit Exceed (Vượt Giới Hạn Bộ Nhớ Khi Xử Lý File Lớn)

### Phân loại
Resource Management / Memory / Stream Processing

### Mức nghiêm trọng
CRITICAL 🔴

> `file_get_contents()` cho file lớn load toàn bộ vào RAM → "Allowed memory size exhausted" → process crash.

### Vấn đề

```
file_get_contents('500MB.csv'):
  ┌─────────────────────────────────┐
  │ PHP Process RAM                  │
  │ ┌─────────────────────────┐     │
  │ │ 500MB string in memory  │     │
  │ │ + explode() = +500MB    │     │
  │ │ = 1GB RAM cho 500MB file│     │
  │ │ memory_limit=256M → FATAL│    │
  │ └─────────────────────────┘     │
  └─────────────────────────────────┘

Stream processing:
  ┌─────────────────────────────────┐
  │ PHP Process RAM                  │
  │ ┌────────┐                      │
  │ │ 8KB buf│ ← 1 dòng tại 1 lúc  │
  │ └────────┘                      │
  │ Peak: ~2MB cho file 500MB       │
  └─────────────────────────────────┘
```

### Phát hiện

```bash
# Tìm file_get_contents với variable path
rg --type php "file_get_contents\s*\(\s*\\\$" -n

# Tìm Eloquent get() không chunk/lazy
rg --type php "->get\(\)" app/ -n | grep -v "chunk\|cursor\|lazy"

# Tìm tăng memory_limit (triệu chứng)
rg --type php "ini_set.*memory_limit" -n
```

### Giải pháp

**BAD — Load toàn bộ vào memory:**
```php
// BAD: 200MB file → 400MB+ RAM
$content = file_get_contents($csvPath);
$lines = explode("\n", $content);
foreach ($lines as $line) {
    User::create(str_getcsv($line));
}
```

**GOOD — Stream processing:**
```php
// GOOD: ~2MB RAM cho file bất kỳ kích thước
$handle = fopen($csvPath, 'r');
try {
    fgetcsv($handle); // Skip header
    $batch = [];
    while (($row = fgetcsv($handle)) !== false) {
        $batch[] = ['name' => $row[0], 'email' => $row[1], 'created_at' => now()];
        if (count($batch) >= 500) {
            User::insert($batch);
            $batch = [];
        }
    }
    if ($batch) User::insert($batch);
} finally {
    fclose($handle);
}
```

**GOOD — Laravel lazy() cho Eloquent:**
```php
// GOOD: Generator-based, 1 record at a time
Order::whereMonth('created_at', $month)
    ->lazy(500)
    ->each(function (Order $order) use ($handle): void {
        fputcsv($handle, [$order->id, $order->total]);
    });
```

### Phòng ngừa

- [ ] KHÔNG dùng `file_get_contents()` cho user uploads
- [ ] Dùng `fopen()`/`fgets()` hoặc `SplFileObject` cho file > 10MB
- [ ] Eloquent: `chunk()`, `lazy()`, `cursor()` thay `get()`
- [ ] Set `memory_limit` hợp lý (128M-256M), KHÔNG tăng lên 1G

---

## Pattern 04: Curl Handle Reuse Thiếu

### Tên
Curl Handle Reuse Thiếu (Missing cURL Handle Reuse)

### Phân loại
Resource Management / Network / HTTP Client

### Mức nghiêm trọng
MEDIUM 🟡

> Tạo curl handle mới mỗi request → TCP/TLS handshake mỗi lần → chậm và lãng phí resource.

### Vấn đề

```
Không reuse (N requests):
  Request 1: DNS + TCP + TLS + HTTP = 150ms
  Request 2: DNS + TCP + TLS + HTTP = 150ms
  Request 3: DNS + TCP + TLS + HTTP = 150ms
  Total: N × 150ms

Reuse handle (keep-alive):
  Request 1: DNS + TCP + TLS + HTTP = 150ms
  Request 2: HTTP only = 30ms (connection reused)
  Request 3: HTTP only = 30ms
  Total: 150ms + (N-1) × 30ms ← 5x faster
```

### Phát hiện

```bash
# Tìm curl_init trong loop
rg --type php "curl_init\(\)" -n

# Tìm Guzzle client tạo mới mỗi lần
rg --type php "new\s+(Client|GuzzleHttp)" -n
```

### Giải pháp

**BAD — New handle mỗi request:**
```php
// BAD: DNS + TCP + TLS mỗi lần
foreach ($urls as $url) {
    $ch = curl_init($url);
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    $response = curl_exec($ch);
    curl_close($ch); // Connection closed, next request starts from scratch
}
```

**GOOD — Reuse handle + Guzzle shared client:**
```php
// GOOD: Reuse curl handle
$ch = curl_init();
curl_setopt_array($ch, [
    CURLOPT_RETURNTRANSFER => true,
    CURLOPT_TCP_KEEPALIVE => 1,
    CURLOPT_TIMEOUT => 10,
]);
try {
    foreach ($urls as $url) {
        curl_setopt($ch, CURLOPT_URL, $url);
        $response = curl_exec($ch); // Connection reused!
    }
} finally {
    curl_close($ch);
}

// GOOD: Shared Guzzle client (singleton in DI)
class ApiService
{
    public function __construct(
        private readonly Client $httpClient // Injected singleton
    ) {}

    public function fetchData(string $endpoint): array
    {
        $response = $this->httpClient->get($endpoint);
        return json_decode($response->getBody()->getContents(), true);
    }
}

// Laravel service provider
$this->app->singleton(Client::class, fn() => new Client([
    'base_uri' => config('services.api.url'),
    'timeout' => 10,
    'connect_timeout' => 5,
]));
```

### Phòng ngừa

- [ ] Sử dụng shared Guzzle client (singleton) thay vì `new Client()` mỗi lần
- [ ] Nếu dùng curl trực tiếp, reuse handle cho multiple requests
- [ ] Enable `TCP_KEEPALIVE` cho long-lived connections
- [ ] Batch requests với `curl_multi_*` hoặc Guzzle Pool

---

## Pattern 05: Stream Wrapper Misuse

### Tên
Stream Wrapper Misuse (Sử Dụng Sai PHP Stream)

### Phân loại
Resource Management / I/O / Streams

### Mức nghiêm trọng
MEDIUM 🟡

> `php://input` đọc nhiều lần (chỉ đọc được 1 lần), stream filter sai, output buffering conflict.

### Vấn đề

```
php://input lifecycle:

  POST request body = "{"name":"John"}"

  Lần 1: file_get_contents('php://input') → '{"name":"John"}' ✅
  Lần 2: file_get_contents('php://input') → '' ❌ (đã đọc hết!)

  Middleware A: $body = file_get_contents('php://input')  ← OK
  Middleware B: $body = file_get_contents('php://input')  ← EMPTY!
  Controller:  $body = file_get_contents('php://input')   ← EMPTY!
```

### Phát hiện

```bash
# Tìm php://input đọc nhiều lần
rg --type php "php://input" -n

# Tìm stream filter usage
rg --type php "stream_filter_(append|prepend)" -n
```

### Giải pháp

**BAD — Đọc php://input nhiều lần:**
```php
// BAD: Middleware A đọc hết, controller nhận empty
// Middleware
$rawBody = file_get_contents('php://input'); // Đọc lần 1 OK
$logger->info('Request body', ['body' => $rawBody]);

// Controller
$body = file_get_contents('php://input'); // Lần 2 → EMPTY!
$data = json_decode($body, true); // null!
```

**GOOD — Cache body, dùng framework request object:**
```php
// GOOD: Laravel — dùng $request object (đã cache body)
class MyController extends Controller
{
    public function store(Request $request): JsonResponse
    {
        $data = $request->validated(); // Body đã được cache bởi framework
        return response()->json($data);
    }
}

// GOOD: Nếu cần raw body, cache thủ công
class RawBodyMiddleware
{
    public function handle(Request $request, Closure $next): Response
    {
        // Đọc 1 lần và lưu vào request attribute
        $request->attributes->set('raw_body', file_get_contents('php://input'));
        return $next($request);
    }
}

// Controller sử dụng cached body
$rawBody = $request->attributes->get('raw_body');
```

### Phòng ngừa

- [ ] Không gọi `file_get_contents('php://input')` nhiều lần
- [ ] Dùng framework request object (đã cache nội bộ)
- [ ] Nếu cần raw body, cache trong middleware 1 lần duy nhất
- [ ] Dùng `php://temp` thay `php://memory` cho data lớn

---

## Pattern 06: Process Fork Zombie

### Tên
Process Fork Zombie (Process Con Trở Thành Zombie)

### Phân loại
Resource Management / OS / Process

### Mức nghiêm trọng
HIGH 🟠

> `pcntl_fork()` tạo child process nhưng không `pcntl_wait()` → zombie tích lũy → PID exhaustion.

### Vấn đề

```
Parent (PHP CLI)
    │
    ├── pcntl_fork() → child PID 1234
    │       │
    │       ▼
    │   Task done, exit(0)
    │   Nhưng parent KHÔNG gọi pcntl_wait()
    │   → PID 1234 = ZOMBIE <defunct>
    │
    ├── fork() → PID 1235 zombie
    ├── fork() → PID 1236 zombie
    │   ...
    └── fork() → Cannot fork: Resource temporarily unavailable!
```

### Phát hiện

```bash
# Tìm pcntl_fork không có pcntl_wait
rg --type php "pcntl_fork\(\)" -n

# Tìm pcntl_wait/pcntl_waitpid
rg --type php "pcntl_wait" -n

# Kiểm tra zombie processes
# ps aux | awk '$8 ~ /Z/ {print}'
```

### Giải pháp

**BAD — Fork không wait:**
```php
// BAD: Child trở thành zombie
for ($i = 0; $i < 10; $i++) {
    $pid = pcntl_fork();
    if ($pid === 0) {
        // Child process
        doWork($i);
        exit(0);
    }
    // Parent tiếp tục fork, KHÔNG wait!
}
```

**GOOD — Signal handler + wait:**
```php
// GOOD: Reap children properly
pcntl_async_signals(true);
pcntl_signal(SIGCHLD, function () {
    // Reap ALL finished children (non-blocking)
    while (pcntl_waitpid(-1, $status, WNOHANG) > 0) {
        // Child reaped, no zombie
    }
});

$maxWorkers = 4;
$activeWorkers = 0;

foreach ($tasks as $task) {
    // Wait nếu đã đủ workers
    while ($activeWorkers >= $maxWorkers) {
        pcntl_waitpid(-1, $status);
        $activeWorkers--;
    }

    $pid = pcntl_fork();
    if ($pid === 0) {
        doWork($task);
        exit(0);
    }
    $activeWorkers++;
}

// Wait for remaining children
while ($activeWorkers > 0) {
    pcntl_waitpid(-1, $status);
    $activeWorkers--;
}
```

### Phòng ngừa

- [ ] Mọi `pcntl_fork()` phải có `pcntl_wait()` hoặc `SIGCHLD` handler
- [ ] Giới hạn concurrent children (semaphore pattern)
- [ ] Prefer `symfony/process` hoặc queue workers thay fork thủ công
- [ ] Monitor zombie count: `ps aux | awk '$8~/Z/'`

---

## Pattern 07: OPcache Invalidation

### Tên
OPcache Invalidation Thiếu (Missing OPcache Invalidation)

### Phân loại
Resource Management / Cache / Bytecode

### Mức nghiêm trọng
MEDIUM 🟡

> Deploy code mới nhưng OPcache vẫn serve bytecode cũ → behavior không đồng nhất, bugs ẩn.

### Vấn đề

```
Deploy flow:

  1. Upload code mới (git pull / rsync)
  2. OPcache vẫn giữ bytecode cũ
  3. Request → PHP serve CODE CŨ!
  4. Sau opcache.revalidate_freq (mặc định 2s) → recheck
  5. Nhưng nếu opcache.validate_timestamps=0 (production) → KHÔNG BAO GIỜ update!

  Server A: code mới (OPcache cleared)  → version 2.0
  Server B: code cũ (OPcache stale)     → version 1.0
  → Users thấy behavior khác nhau tùy server!
```

### Phát hiện

```bash
# Kiểm tra OPcache config
rg --type php "opcache" /etc/php/ -rn 2>/dev/null

# Tìm deploy script thiếu opcache_reset
rg "opcache_reset\|opcache_invalidate" deploy/ -rn
```

### Giải pháp

**BAD — Deploy không clear OPcache:**
```bash
# BAD: Deploy script không reset OPcache
git pull origin main
composer install --no-dev
php artisan migrate
# OPcache vẫn serve code cũ!
```

**GOOD — Deploy có clear OPcache:**
```bash
# GOOD: Deploy script với OPcache reset
git pull origin main
composer install --no-dev
php artisan migrate

# Clear OPcache qua CLI (nếu cùng SAPI)
php -r "opcache_reset();"

# Hoặc qua HTTP endpoint (cho php-fpm)
curl -s http://localhost/opcache-reset.php

# Hoặc reload php-fpm (reset toàn bộ)
sudo systemctl reload php8.3-fpm
```

**GOOD — Laravel deploy command:**
```php
// GOOD: Artisan command
Artisan::call('optimize:clear'); // Clear all caches including OPcache

// routes/web.php (chỉ dùng internal, protect bằng IP whitelist)
Route::get('/opcache-reset', function () {
    if (!in_array(request()->ip(), ['127.0.0.1', '::1'])) {
        abort(403);
    }
    opcache_reset();
    return response()->json(['status' => 'ok']);
});
```

### Phòng ngừa

- [ ] Deploy script PHẢI có `opcache_reset()` hoặc `php-fpm reload`
- [ ] Set `opcache.validate_timestamps=1` ở dev, `=0` ở production
- [ ] Dùng file-based OPcache preloading cho performance (`opcache.preload`)
- [ ] Zero-downtime deploy: symlink swap + php-fpm reload

---

## Pattern 08: Temp File Cleanup Thiếu

### Tên
Temp File Cleanup Thiếu (Temp Files Not Cleaned Up)

### Phân loại
Resource Management / File System / Temp Files

### Mức nghiêm trọng
MEDIUM 🟡

> `tempnam()` / `tmpfile()` tạo temp file nhưng không `unlink()` → disk space grow dần → disk full.

### Vấn đề

```
Upload processing:

  Request 1: tempnam() → /tmp/php_abc123  (10MB)
  Request 2: tempnam() → /tmp/php_def456  (10MB)
  ...
  Request 10000: /tmp 100GB full!
                 → "No space left on device" ❌
                 → Toàn bộ server affected!
```

### Phát hiện

```bash
# Tìm tempnam/sys_get_temp_dir không có unlink
rg --type php "tempnam\(|sys_get_temp_dir\(\)" -n

# Tìm tmpfile() (tự cleanup khi fclose, nhưng exception có thể skip)
rg --type php "tmpfile\(\)" -n

# Kiểm tra /tmp usage
# du -sh /tmp/
```

### Giải pháp

**BAD — Temp file không cleanup:**
```php
// BAD: Exception → temp file orphaned
$tmpPath = tempnam(sys_get_temp_dir(), 'export_');
file_put_contents($tmpPath, $csvContent);
$this->uploadToS3($tmpPath); // Exception → file leaked!
unlink($tmpPath); // Never reached
```

**GOOD — Try/finally cleanup:**
```php
// GOOD: Temp file luôn được cleanup
$tmpPath = tempnam(sys_get_temp_dir(), 'export_');
try {
    file_put_contents($tmpPath, $csvContent);
    $this->uploadToS3($tmpPath);
} finally {
    if (file_exists($tmpPath)) {
        unlink($tmpPath);
    }
}

// GOOD: Helper class
class TempFile
{
    private string $path;

    public function __construct(string $prefix = 'app_')
    {
        $this->path = tempnam(sys_get_temp_dir(), $prefix);
    }

    public function getPath(): string { return $this->path; }

    public function __destruct()
    {
        if (file_exists($this->path)) {
            unlink($this->path);
        }
    }
}

// Auto-cleanup khi ra khỏi scope
$tmp = new TempFile('export_');
file_put_contents($tmp->getPath(), $content);
$this->uploadToS3($tmp->getPath());
// $tmp destroyed → file deleted
```

### Phòng ngừa

- [ ] Mọi `tempnam()` phải có `unlink()` trong `finally`
- [ ] Dùng TempFile wrapper class cho auto-cleanup
- [ ] Cron job: `find /tmp -name 'app_*' -mmin +60 -delete`
- [ ] Monitor /tmp disk usage

---

## Pattern 09: Shared Memory Leak

### Tên
Shared Memory Leak (Rò Rỉ Shared Memory)

### Phân loại
Resource Management / IPC / Shared Memory

### Mức nghiêm trọng
HIGH 🟠

> `shmop_open()` / `shm_attach()` tạo shared memory segment nhưng không release → tích lũy → system memory exhaustion.

### Vấn đề

```
Shared Memory Segments:

  Process 1: shmop_open() → segment #1 (1MB)
  Process 2: shmop_open() → segment #2 (1MB)
  ...
  Không shmop_delete() → segments tồn tại SAU KHI process exit!

  $ ipcs -m
  ------ Shared Memory Segments --------
  key        shmid      owner      perms      bytes
  0x00001234 1          www-data   666        1048576
  0x00001235 2          www-data   666        1048576
  ... (hàng trăm segments!)

  System RAM: dần dần bị chiếm hết bởi orphan segments
```

### Phát hiện

```bash
# Tìm shmop/shm usage
rg --type php "shmop_open\|shm_attach\|shm_put_var" -n

# Tìm thiếu shmop_delete/shm_remove
rg --type php "shmop_delete\|shm_remove\|shm_detach" -n

# Kiểm tra shared memory segments trên server
# ipcs -m | grep www-data
```

### Giải pháp

**BAD — Shared memory không cleanup:**
```php
// BAD: Segment tồn tại sau khi process exit
$shm = shmop_open(ftok(__FILE__, 'a'), 'c', 0666, 1024);
shmop_write($shm, $data, 0);
// Process exit → segment ORPHANED!
```

**GOOD — Proper lifecycle management:**
```php
// GOOD: Cleanup segment khi done
$key = ftok(__FILE__, 'a');
$shm = shmop_open($key, 'c', 0666, 1024);
try {
    shmop_write($shm, $data, 0);
    // ... use shared memory
} finally {
    shmop_delete($shm); // Mark for deletion
    shmop_close($shm);  // Close handle
}

// GOOD: Prefer APCu/Redis over raw shared memory
// APCu tự quản lý memory lifecycle
apcu_store('cache_key', $data, 300); // TTL 300s
$cached = apcu_fetch('cache_key');
```

### Phòng ngừa

- [ ] Prefer APCu hoặc Redis thay shmop (tự quản lý lifecycle)
- [ ] Mọi `shmop_open()` phải có `shmop_delete()` + `shmop_close()` trong `finally`
- [ ] Cron job: `ipcrm -M <key>` cleanup orphan segments
- [ ] Monitor: `ipcs -m` kiểm tra leaked segments

---

## Pattern 10: Redis Connection Pool Exhaustion

### Tên
Redis Connection Pool Exhaustion (Cạn Kiệt Redis Connection Pool)

### Phân loại
Resource Management / Cache / Connection Pool

### Mức nghiêm trọng
CRITICAL 🔴

> Redis connections không close/return pool → pool full → cache requests timeout → fallback to DB → DB overload → cascade failure.

### Vấn đề

```
Redis Pool (max 10):

  Request 1: $redis = new Redis(); connect()    Pool: 1/10
  Request 2: $redis = new Redis(); connect()    Pool: 2/10
  ...
  Request 10: connect()                         Pool: 10/10
  Request 11: connect() → TIMEOUT!              Pool: FULL
       │
       ▼
  Cache miss → DB query (slow)
  + 100 concurrent requests = DB OVERLOAD!

  Root cause: connections không close() hoặc
  phpredis extension leak khi exception
```

### Phát hiện

```bash
# Tìm Redis connection tạo mới mỗi request
rg --type php "new\s+Redis\(\)" -n

# Tìm Redis không close
rg --type php "\\\$redis->connect\(" -A 20 | grep -v "close\|disconnect"

# Tìm Predis client tạo mới
rg --type php "new\s+Predis\\\\Client" -n

# Kiểm tra Redis connections
# redis-cli info clients
```

### Giải pháp

**BAD — New connection mỗi request:**
```php
// BAD: Mỗi function call tạo Redis connection mới
function getCachedUser(int $id): ?array
{
    $redis = new Redis();
    $redis->connect('127.0.0.1', 6379);
    $cached = $redis->get("user:{$id}");
    // $redis KHÔNG close! Connection leaked khi function return
    return $cached ? json_decode($cached, true) : null;
}
```

**GOOD — Singleton connection + Laravel Redis facade:**
```php
// GOOD: Singleton Redis connection
class RedisConnection
{
    private static ?Redis $instance = null;

    public static function getInstance(): Redis
    {
        if (self::$instance === null || !self::$instance->isConnected()) {
            self::$instance = new Redis();
            self::$instance->connect(
                config('database.redis.default.host'),
                (int) config('database.redis.default.port')
            );
            self::$instance->setOption(Redis::OPT_READ_TIMEOUT, 5);
        }
        return self::$instance;
    }
}

// GOOD: Laravel Redis facade (connection pooling built-in)
use Illuminate\Support\Facades\Redis;

function getCachedUser(int $id): ?array
{
    // Laravel quản lý connection pool tự động
    $cached = Redis::get("user:{$id}");
    return $cached ? json_decode($cached, true) : null;
}

// GOOD: Cache helper với fallback
function cachedQuery(string $key, int $ttl, callable $fallback): mixed
{
    try {
        $cached = Redis::get($key);
        if ($cached !== null) {
            return json_decode($cached, true);
        }
    } catch (\RedisException $e) {
        // Redis down → fallback to DB, không crash
        Log::warning('Redis unavailable', ['error' => $e->getMessage()]);
    }

    $data = $fallback();

    try {
        Redis::setex($key, $ttl, json_encode($data));
    } catch (\RedisException) {
        // Silent fail — cache miss acceptable
    }

    return $data;
}
```

### Phòng ngừa

- [ ] Dùng framework Redis (Laravel Redis, Symfony Cache) thay raw `new Redis()`
- [ ] Singleton pattern cho Redis connection
- [ ] Implement cache fallback — app hoạt động khi Redis down
- [ ] Monitor Redis `connected_clients` và `blocked_clients`
- [ ] Set `maxclients` hợp lý trong `redis.conf`

---

## Bảng Tóm Tắt

| # | Pattern | Mức độ | Tác động chính |
|---|---------|--------|----------------|
| 01 | DB Connection Không Close | 🟠 HIGH | Too many connections, service down |
| 02 | File Handle Leak | 🟠 HIGH | Too many open files, worker crash |
| 03 | Memory Limit Exceed | 🔴 CRITICAL | OOM fatal error, process crash |
| 04 | Curl Handle Reuse Thiếu | 🟡 MEDIUM | Performance degradation |
| 05 | Stream Wrapper Misuse | 🟡 MEDIUM | Empty request body, data loss |
| 06 | Process Fork Zombie | 🟠 HIGH | PID exhaustion, cannot fork |
| 07 | OPcache Invalidation | 🟡 MEDIUM | Stale code, inconsistent behavior |
| 08 | Temp File Cleanup Thiếu | 🟡 MEDIUM | Disk full, server-wide impact |
| 09 | Shared Memory Leak | 🟠 HIGH | System memory exhaustion |
| 10 | Redis Connection Pool | 🔴 CRITICAL | Cache down → DB overload |

## Quick Scan Script

```bash
#!/bin/bash
echo "=== PHP Resource Management Audit ==="

echo -e "\n--- RM-01: PDO Persistent ---"
rg --type php "ATTR_PERSISTENT\s*=>\s*true" 2>/dev/null

echo -e "\n--- RM-02: File Handle ---"
rg --type php "fopen\s*\(" -c 2>/dev/null | sort -t: -k2 -rn | head -5

echo -e "\n--- RM-03: Large File Load ---"
rg --type php "file_get_contents\s*\(\s*\\\$" 2>/dev/null

echo -e "\n--- RM-04: Curl Handle ---"
rg --type php "curl_init\(\)" -c 2>/dev/null

echo -e "\n--- RM-05: php://input ---"
rg --type php "php://input" 2>/dev/null

echo -e "\n--- RM-06: Process Fork ---"
rg --type php "pcntl_fork" 2>/dev/null

echo -e "\n--- RM-07: OPcache ---"
rg --type php "opcache_reset\|opcache_invalidate" 2>/dev/null

echo -e "\n--- RM-09: Shared Memory ---"
rg --type php "shmop_open\|shm_attach" 2>/dev/null

echo -e "\n--- RM-10: Redis Connection ---"
rg --type php "new\s+Redis\(\)" 2>/dev/null

echo -e "\n=== Scan Complete ==="
```
