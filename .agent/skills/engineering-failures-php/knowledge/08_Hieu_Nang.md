# Domain 08: Hiệu Năng Và Mở Rộng (Performance & Scalability)

> PHP/Laravel patterns liên quan đến performance: N+1 queries, caching, eager loading, queue, OPcache.

---

## Pattern 01: N+1 Query

### Tên
N+1 Query (Truy Vấn N+1 Trong Eloquent)

### Phân loại
Performance / Database / ORM

### Mức nghiêm trọng
CRITICAL 🔴

### Vấn đề

```php
$posts = Post::all(); // 1 query
foreach ($posts as $post) {
    echo $post->author->name; // N queries (1 per post!)
}
// 100 posts = 101 queries
// 10,000 posts = 10,001 queries → page timeout
```

### Phát hiện

```bash
rg --type php "->all\(\)|::all\(\)" -n
rg --type php "foreach.*->.*->.*->" -n
rg --type php "preventLazyLoading" -n
```

### Giải pháp

❌ **BAD**
```php
$orders = Order::all();
foreach ($orders as $order) {
    $customer = $order->customer->name;     // N queries
    $items = $order->items->count();        // N more queries
}
```

✅ **GOOD**
```php
// Eager load relationships:
$orders = Order::with(['customer', 'items'])->get(); // 3 queries total
foreach ($orders as $order) {
    $customer = $order->customer->name;     // Already loaded
    $items = $order->items->count();        // Already loaded
}

// Prevent lazy loading in development:
Model::preventLazyLoading(!app()->isProduction());

// Select only needed columns:
$orders = Order::with(['customer:id,name', 'items:id,order_id,quantity'])
    ->select('id', 'customer_id', 'total')
    ->get();
```

### Phòng ngừa
- [ ] `Model::preventLazyLoading()` in `AppServiceProvider`
- [ ] Always `with()` for relationships used in loops
- [ ] Laravel Debugbar to detect N+1
- Tool: `barryvdh/laravel-debugbar`, `beyondcode/laravel-query-detector`

---

## Pattern 02: Missing Database Indexes

### Tên
Missing Database Indexes (Thiếu Index Cho Cột Truy Vấn)

### Phân loại
Performance / Database / Index

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```php
// Migration:
$table->string('email'); // No index!

// Query:
User::where('email', $email)->first();
// → Full table scan on 1M rows = seconds
// With index: milliseconds
```

### Phát hiện

```bash
rg --type php "->where\(|->whereIn\(|->orderBy\(" -n
rg --type php "->index\(|->unique\(" -n
rg --type php "->foreign\(" -n
```

### Giải pháp

❌ **BAD**
```php
Schema::create('orders', function (Blueprint $table) {
    $table->string('status');       // Queried but no index
    $table->foreignId('user_id');   // FK but no index
    $table->timestamp('created_at'); // Sorted but no index
});
```

✅ **GOOD**
```php
Schema::create('orders', function (Blueprint $table) {
    $table->string('status')->index();
    $table->foreignId('user_id')->constrained()->index();
    $table->timestamp('created_at')->index();
    // Composite index for common query pattern:
    $table->index(['user_id', 'status', 'created_at']);
});
```

### Phòng ngừa
- [ ] Index all columns used in `WHERE`, `ORDER BY`, `JOIN`
- [ ] Composite indexes for common query patterns
- [ ] `EXPLAIN` to verify index usage
- Tool: `EXPLAIN ANALYZE` in MySQL/PostgreSQL

---

## Pattern 03: Query Trong Loop

### Tên
Query Trong Loop (Database Query Inside Loop)

### Phân loại
Performance / Database / Loop

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```php
foreach ($userIds as $id) {
    $user = User::find($id);        // Query per iteration
    $user->update(['active' => true]); // Another query per iteration
}
// 1000 users = 2000 queries
```

### Phát hiện

```bash
rg --type php "foreach.*\{" -A 5 | rg "(::find|::where|->save|->update|->delete)"
rg --type php "for\s*\(.*\{" -A 5 | rg "DB::|Eloquent|::find"
```

### Giải pháp

❌ **BAD**
```php
foreach ($emails as $email) {
    $exists = User::where('email', $email)->exists(); // N queries
}
```

✅ **GOOD**
```php
// Bulk operations:
User::whereIn('id', $userIds)->update(['active' => true]); // 1 query

// Batch check existence:
$existingEmails = User::whereIn('email', $emails)->pluck('email')->toArray();
$newEmails = array_diff($emails, $existingEmails);

// Chunk for large datasets:
User::where('active', false)->chunk(1000, function ($users) {
    foreach ($users as $user) {
        $user->deactivate();
    }
});

// Bulk insert:
$records = collect($data)->map(fn($item) => [
    'name' => $item['name'],
    'created_at' => now(),
]);
User::insert($records->toArray()); // Single query
```

### Phòng ngừa
- [ ] `whereIn()` for batch lookups
- [ ] `update()` with conditions for batch updates
- [ ] `chunk()` for processing large datasets
- Tool: Laravel Debugbar query count

---

## Pattern 04: OPcache Thiếu

### Tên
OPcache Thiếu (PHP OPcache Not Configured)

### Phân loại
Performance / PHP / Compilation

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```
Without OPcache:
Request → Parse PHP → Compile to opcodes → Execute → Response
                      ↑ Repeated EVERY request!

With OPcache:
Request → Execute cached opcodes → Response
          ↑ 3-5x faster
```

### Phát hiện

```bash
rg "opcache" -n --glob "*.ini"
rg "opcache\.enable" -n --glob "*.ini"
rg "opcache" -n --glob "Dockerfile*"
```

### Giải pháp

❌ **BAD**
```ini
; php.ini
opcache.enable=0  ; Disabled!
; Or: not configured at all
```

✅ **GOOD**
```ini
; php.ini — Production:
opcache.enable=1
opcache.memory_consumption=256
opcache.max_accelerated_files=20000
opcache.validate_timestamps=0     ; Don't check file changes (deploy clears cache)
opcache.interned_strings_buffer=16
opcache.jit=1255                  ; PHP 8.0+ JIT
opcache.jit_buffer_size=256M

; Laravel: preload framework files
opcache.preload=/var/www/app/bootstrap/preload.php
opcache.preload_user=www-data
```

### Phòng ngừa
- [ ] `opcache.enable=1` in production
- [ ] `validate_timestamps=0` + clear on deploy
- [ ] JIT enabled (PHP 8.0+)
- Tool: `opcache_get_status()`, `php -m | grep opcache`

---

## Pattern 05: Cache Thiếu

### Tên
Cache Thiếu (No Application Caching Strategy)

### Phân loại
Performance / Cache / Strategy

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```php
// Every request:
$config = DB::table('settings')->get();           // DB query
$categories = Category::with('children')->get();   // Complex query
$exchangeRate = Http::get('api.exchange.com/rate'); // External API call
// All repeated on EVERY request, even though data rarely changes
```

### Phát hiện

```bash
rg --type php "Cache::(get|put|remember|forget)" -n
rg --type php "->remember\(|->rememberForever\(" -n
rg --type php "CACHE_DRIVER|CACHE_STORE" -n --glob ".env*"
```

### Giải pháp

❌ **BAD**
```php
// No caching — DB hit every request:
public function getSettings(): Collection
{
    return DB::table('settings')->get();
}
```

✅ **GOOD**
```php
public function getSettings(): Collection
{
    return Cache::remember('app.settings', 3600, function () {
        return DB::table('settings')->get();
    });
}

// Cache with tags for easy invalidation:
public function getCategories(): Collection
{
    return Cache::tags(['categories'])->remember('categories.tree', 3600, function () {
        return Category::with('children')->get();
    });
}

// Invalidate on update:
public function updateCategory(Category $category, array $data): void
{
    $category->update($data);
    Cache::tags(['categories'])->flush();
}
```

### Phòng ngừa
- [ ] Cache expensive queries and API calls
- [ ] Use Redis/Memcached for production (not `file`)
- [ ] Invalidation strategy: tags, TTL, event-based
- Tool: Laravel Cache, Redis

---

## Pattern 06: Queue Thiếu

### Tên
Queue Thiếu (Synchronous Heavy Operations)

### Phân loại
Performance / Queue / Async

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```php
// In controller — all synchronous:
public function register(Request $request)
{
    $user = User::create($request->validated());
    Mail::send(new WelcomeEmail($user));         // 2-3 seconds
    Http::post('analytics.api/track', [...]);    // 1-2 seconds
    $this->generateAvatar($user);                // 3-5 seconds
    return response()->json($user);
    // Total: 6-10 seconds response time!
}
```

### Phát hiện

```bash
rg --type php "Mail::send\(|Http::post\(|Http::get\(" -n --glob "*Controller*"
rg --type php "dispatch\(|->dispatch\(\)" -n
rg --type php "ShouldQueue" -n
rg --type php "QUEUE_CONNECTION" -n --glob ".env*"
```

### Giải pháp

❌ **BAD**
```php
// Sending email synchronously in request:
Mail::send(new OrderConfirmation($order)); // Blocks for 2-3s
```

✅ **GOOD**
```php
public function register(Request $request)
{
    $user = User::create($request->validated());

    // Queue async jobs:
    SendWelcomeEmail::dispatch($user);
    TrackAnalytics::dispatch('user.registered', $user->id);
    GenerateAvatar::dispatch($user);

    return response()->json($user); // Responds in ~50ms
}

// Job class:
class SendWelcomeEmail implements ShouldQueue
{
    use Dispatchable, InteractsWithQueue, Queueable, SerializesModels;

    public function __construct(private User $user) {}

    public function handle(): void
    {
        Mail::to($this->user)->send(new WelcomeEmail($this->user));
    }

    public int $tries = 3;
    public int $backoff = 60;
}
```

### Phòng ngừa
- [ ] Queue emails, API calls, heavy processing
- [ ] `ShouldQueue` interface for all non-critical jobs
- [ ] Redis/SQS for production queue driver
- Tool: `php artisan queue:work`, Laravel Horizon

---

## Pattern 07: Chunking Thiếu Cho Large Dataset

### Tên
Chunking Thiếu (Loading All Records Into Memory)

### Phân loại
Performance / Memory / Dataset

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```php
$users = User::all(); // 1 million users loaded into memory!
// PHP memory limit: 128MB/256MB → FATAL ERROR
// Even if memory enough: GC overhead, slow processing
```

### Phát hiện

```bash
rg --type php "::all\(\)" -n
rg --type php "->get\(\)" -n | rg -v "->paginate\(|->chunk\(|->first\(|->find\("
rg --type php "->chunk\(|->chunkById\(|->lazy\(|->cursor\(" -n
```

### Giải pháp

❌ **BAD**
```php
// Export all users:
$users = User::all();
foreach ($users as $user) {
    $csv->addRow($user->toArray());
}
```

✅ **GOOD**
```php
// Option 1: chunk() — fixed memory usage
User::chunk(1000, function ($users) use ($csv) {
    foreach ($users as $user) {
        $csv->addRow($user->toArray());
    }
});

// Option 2: lazy() — generator-based (even less memory)
foreach (User::lazy(1000) as $user) {
    $csv->addRow($user->toArray());
}

// Option 3: cursor() — one row at a time (minimum memory)
foreach (User::cursor() as $user) {
    $csv->addRow($user->toArray());
}
```

### Phòng ngừa
- [ ] NEVER `::all()` on large tables
- [ ] `chunk()` / `chunkById()` for batch processing
- [ ] `lazy()` for streaming
- [ ] `cursor()` for minimum memory

---

## Pattern 08: Select * Thừa

### Tên
Select * Thừa (Selecting All Columns)

### Phân loại
Performance / Database / Query

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```php
$users = User::all(); // SELECT * FROM users
// Table has: id, name, email, bio (TEXT 10KB), avatar (BLOB), preferences (JSON)
// Only need: id, name
// Transferring 10KB × 10,000 rows = 100MB of unnecessary data
```

### Phát hiện

```bash
rg --type php "::all\(\)|->get\(\)" -n | rg -v "->select\("
rg --type php "->select\(" -n
rg --type php "->pluck\(" -n
```

### Giải pháp

❌ **BAD**
```php
$users = User::where('active', true)->get(); // SELECT * — all columns
$names = $users->pluck('name'); // Only needed name!
```

✅ **GOOD**
```php
// Select only needed columns:
$users = User::where('active', true)
    ->select('id', 'name', 'email')
    ->get();

// Even better — pluck directly:
$names = User::where('active', true)->pluck('name');

// For relationships:
$orders = Order::with(['customer:id,name,email'])
    ->select('id', 'customer_id', 'total', 'status')
    ->get();
```

### Phòng ngừa
- [ ] Always `select()` specific columns
- [ ] `pluck()` for single column
- [ ] Avoid loading TEXT/BLOB columns unnecessarily
- Tool: Laravel Debugbar query analysis

---

## Pattern 09: Session/File Cache Driver Production

### Tên
Session/File Cache Driver (File-Based Cache In Production)

### Phân loại
Performance / Cache / Driver

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```ini
# .env (production):
CACHE_DRIVER=file    # ← Disk I/O for every cache operation!
SESSION_DRIVER=file  # ← Disk I/O for every request!
QUEUE_CONNECTION=sync # ← No actual queueing!
```

### Phát hiện

```bash
rg "CACHE_DRIVER|SESSION_DRIVER|QUEUE_CONNECTION" -n --glob ".env*"
rg "REDIS_HOST|REDIS_PORT" -n --glob ".env*"
```

### Giải pháp

❌ **BAD**
```ini
CACHE_DRIVER=file
SESSION_DRIVER=file
QUEUE_CONNECTION=sync
```

✅ **GOOD**
```ini
# Production .env:
CACHE_DRIVER=redis
SESSION_DRIVER=redis
QUEUE_CONNECTION=redis

REDIS_HOST=redis-cluster.internal
REDIS_PORT=6379
REDIS_PASSWORD=secure-password
```

### Phòng ngừa
- [ ] Redis for cache, session, queue in production
- [ ] `file` driver only for development
- [ ] `sync` queue driver only for development
- Tool: `redis-cli info`, Laravel Horizon

---

## Pattern 10: Middleware Overhead

### Tên
Middleware Overhead (Too Many Middleware Per Request)

### Phân loại
Performance / HTTP / Middleware

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```php
// Every API request goes through 15 middleware:
// 1. EncryptCookies (API doesn't use cookies)
// 2. VerifyCsrfToken (API uses Bearer token)
// 3. ShareErrorsFromSession (API is stateless)
// → Unnecessary overhead per request
```

### Phát hiện

```bash
rg --type php "protected.*middleware" -n --glob "*Kernel*"
rg --type php "->middleware\(" -n
rg --type php "Route::middleware\(" -n
```

### Giải pháp

❌ **BAD**
```php
// All middleware applied to API routes:
Route::middleware(['web', 'auth', 'throttle', ...])
    ->group(function () {
        Route::apiResource('users', UserController::class);
    });
```

✅ **GOOD**
```php
// Separate middleware groups:
// api group: only what's needed
protected $middlewareGroups = [
    'api' => [
        'throttle:api',
        SubstituteBindings::class,
        // NO: cookies, CSRF, sessions for API
    ],
    'web' => [
        EncryptCookies::class,
        AddQueuedCookiesToResponse::class,
        StartSession::class,
        VerifyCsrfToken::class,
        SubstituteBindings::class,
    ],
];
```

### Phòng ngừa
- [ ] Separate `web` and `api` middleware groups
- [ ] Only needed middleware per route group
- [ ] Profile middleware execution time
- Tool: Laravel Debugbar timeline

---

## Pattern 11: Config/Route Cache Thiếu

### Tên
Config/Route Cache Thiếu (Missing Optimization Commands)

### Phân loại
Performance / Laravel / Deployment

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```
Without cache:
├── Config: Parse 20+ PHP files per request
├── Routes: Parse all route files per request
├── Views: Compile Blade templates per request
└── Events: Discover listeners per request
→ Added ~50-100ms per request
```

### Phát hiện

```bash
rg "config:cache|route:cache|view:cache|event:cache" -n --glob "*.sh"
rg "optimize" -n --glob "*.sh" --glob "Dockerfile*"
```

### Giải pháp

❌ **BAD**
```bash
# Deploy without optimization:
composer install
php artisan migrate
# Missing: cache commands
```

✅ **GOOD**
```bash
# Deploy script:
composer install --no-dev --optimize-autoloader
php artisan config:cache   # Cache config into single file
php artisan route:cache    # Cache routes into single file
php artisan view:cache     # Pre-compile all Blade templates
php artisan event:cache    # Cache event/listener mappings
# Or all at once:
php artisan optimize
```

### Phòng ngừa
- [ ] `php artisan optimize` in deployment pipeline
- [ ] `composer install --optimize-autoloader --no-dev`
- [ ] Clear caches when deploying new version
- Tool: CI/CD pipeline automation

---

## Pattern 12: Pagination Thiếu

### Tên
Pagination Thiếu (Returning All Records To Frontend)

### Phân loại
Performance / API / Data Transfer

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```php
// API returns ALL records:
public function index()
{
    return User::all(); // 50,000 users = huge JSON response
}
// → Slow response, high bandwidth, frontend crashes
```

### Phát hiện

```bash
rg --type php "return.*::all\(\)" -n --glob "*Controller*"
rg --type php "->paginate\(|->simplePaginate\(|->cursorPaginate\(" -n
```

### Giải pháp

❌ **BAD**
```php
public function index()
{
    return User::all(); // No limit!
}
```

✅ **GOOD**
```php
public function index(Request $request)
{
    return User::query()
        ->select('id', 'name', 'email')
        ->when($request->search, fn($q, $s) => $q->where('name', 'like', "%{$s}%"))
        ->orderBy('created_at', 'desc')
        ->paginate(25); // Returns paginated JSON with meta

    // Or cursor pagination for infinite scroll:
    // ->cursorPaginate(25);
}
```

### Phòng ngừa
- [ ] ALWAYS paginate list endpoints
- [ ] `paginate()` for offset-based
- [ ] `cursorPaginate()` for large datasets (no COUNT query)
- Tool: Laravel resource collections with pagination
