# Domain 09: Thiết Kế API (API Design)

> PHP/Laravel patterns liên quan đến API design: REST, validation, response format, versioning, pagination.

---

## Pattern 01: REST Conventions Vi Phạm

### Tên
REST Conventions Vi Phạm (Verb In URL, Wrong HTTP Method)

### Phân loại
API Design / REST / Convention

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```php
Route::post('/api/getUsers', [UserController::class, 'getUsers']);
Route::get('/api/deleteUser/{id}', [UserController::class, 'delete']);
Route::post('/api/users/update/{id}', [UserController::class, 'update']);
```

### Phát hiện

```bash
rg --type php "Route::(get|post|put|delete)" -n | rg "(get|create|update|delete|fetch|list)\w*'"
rg --type php "apiResource|Route::resource" -n
```

### Giải pháp

❌ **BAD**
```php
Route::post('/api/getUsers', ...);
Route::get('/api/deleteUser/{id}', ...);
```

✅ **GOOD**
```php
Route::apiResource('users', UserController::class);
// GET    /api/users          → index
// POST   /api/users          → store
// GET    /api/users/{id}     → show
// PUT    /api/users/{id}     → update
// DELETE /api/users/{id}     → destroy
```

### Phòng ngừa
- [ ] `Route::apiResource()` for CRUD
- [ ] Nouns in URLs, verbs via HTTP methods
- [ ] Plural resource names
- Tool: `php artisan route:list`

---

## Pattern 02: Request Validation Thiếu

### Tên
Request Validation Thiếu (No Form Request Validation)

### Phân loại
API Design / Validation / Security

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```php
public function store(Request $request) {
    User::create($request->all()); // No validation! Mass assignment!
}
```

### Phát hiện

```bash
rg --type php "Request \$request\)" -A 3 | rg -v "validate|FormRequest"
rg --type php "extends FormRequest" -n
rg --type php "\$request->all\(\)" -n
```

### Giải pháp

❌ **BAD**
```php
public function store(Request $request) {
    $user = User::create($request->all());
}
```

✅ **GOOD**
```php
// Form Request class:
class StoreUserRequest extends FormRequest
{
    public function rules(): array
    {
        return [
            'name' => ['required', 'string', 'max:255'],
            'email' => ['required', 'email', 'unique:users'],
            'password' => ['required', 'min:8', 'confirmed'],
        ];
    }
}

public function store(StoreUserRequest $request): JsonResponse
{
    $user = User::create($request->validated()); // Only validated fields
    return response()->json($user, 201);
}
```

### Phòng ngừa
- [ ] FormRequest classes for ALL endpoints
- [ ] `$request->validated()` not `$request->all()`
- [ ] NEVER trust raw input
- Tool: `php artisan make:request`

---

## Pattern 03: Response Format Inconsistent

### Tên
Response Format Inconsistent (No API Resource)

### Phân loại
API Design / Response / Consistency

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```php
return response()->json($user);           // Raw model (leaks fields)
return response()->json(['error' => $e->getMessage()]); // Ad-hoc error
return response(['data' => $users]);       // Different wrapper
```

### Phát hiện

```bash
rg --type php "response\(\)->json\(" -n
rg --type php "JsonResource|ResourceCollection" -n
rg --type php "return new \w+Resource" -n
```

### Giải pháp

❌ **BAD**
```php
return response()->json($user); // Exposes all model fields including timestamps, etc.
```

✅ **GOOD**
```php
// API Resource:
class UserResource extends JsonResource
{
    public function toArray(Request $request): array
    {
        return [
            'id' => $this->id,
            'name' => $this->name,
            'email' => $this->email,
            'created_at' => $this->created_at->toIso8601String(),
        ];
    }
}

// Controller:
public function show(User $user): UserResource
{
    return new UserResource($user);
}

public function index(): AnonymousResourceCollection
{
    return UserResource::collection(User::paginate(25));
}
```

### Phòng ngừa
- [ ] API Resources for ALL responses
- [ ] Never return raw Eloquent models
- [ ] Consistent error format
- Tool: `php artisan make:resource`

---

## Pattern 04: API Versioning Thiếu

### Tên
API Versioning Thiếu (No Version Strategy)

### Phân loại
API Design / Versioning / Breaking Change

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```php
Route::prefix('api')->group(function () {
    Route::apiResource('users', UserController::class);
});
// Breaking change → all clients break
```

### Phát hiện

```bash
rg --type php "api/v\d" -n
rg --type php "prefix.*api" -n --glob "*api*"
```

### Giải pháp

❌ **BAD**
```php
Route::prefix('api')->group(function () { /* no versioning */ });
```

✅ **GOOD**
```php
// routes/api.php:
Route::prefix('v1')->group(function () {
    Route::apiResource('users', V1\UserController::class);
});

Route::prefix('v2')->group(function () {
    Route::apiResource('users', V2\UserController::class);
});

// Controllers in versioned namespaces:
// app/Http/Controllers/Api/V1/UserController.php
// app/Http/Controllers/Api/V2/UserController.php
```

### Phòng ngừa
- [ ] Version from day one (`/api/v1/`)
- [ ] Separate controller namespaces per version
- [ ] Deprecation headers for old versions

---

## Pattern 05: Pagination Thiếu

### Tên
Pagination Thiếu (Returning All Records)

### Phân loại
API Design / Pagination / Performance

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```php
public function index() {
    return User::all(); // 50,000 users in one response!
}
```

### Phát hiện

```bash
rg --type php "::all\(\)" -n --glob "*Controller*"
rg --type php "->paginate\(|->cursorPaginate\(" -n
```

### Giải pháp

❌ **BAD**
```php
return User::all();
```

✅ **GOOD**
```php
public function index(Request $request): AnonymousResourceCollection
{
    $users = User::query()
        ->when($request->search, fn($q, $s) => $q->where('name', 'like', "%{$s}%"))
        ->orderBy('created_at', 'desc')
        ->paginate($request->input('per_page', 25));

    return UserResource::collection($users);
}
```

### Phòng ngừa
- [ ] ALWAYS paginate list endpoints
- [ ] `cursorPaginate()` for large datasets
- [ ] Max per_page limit
- Tool: Laravel pagination

---

## Pattern 06: Rate Limiting Thiếu

### Tên
Rate Limiting Thiếu (No Throttling)

### Phân loại
API Design / Security / DDoS

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```php
// No rate limiting → API abuse, brute force, DDoS
Route::post('login', LoginController::class);
```

### Phát hiện

```bash
rg --type php "RateLimiter|throttle|ThrottleRequests" -n
rg --type php "configureRateLimiting" -n
```

### Giải pháp

❌ **BAD**
```php
Route::post('login', LoginController::class); // No throttle
```

✅ **GOOD**
```php
// AppServiceProvider:
RateLimiter::for('api', function (Request $request) {
    return Limit::perMinute(60)->by($request->user()?->id ?: $request->ip());
});

RateLimiter::for('login', function (Request $request) {
    return Limit::perMinute(5)->by($request->ip());
});

// Routes:
Route::middleware('throttle:login')->post('login', LoginController::class);
Route::middleware('throttle:api')->group(function () { /* API routes */ });
```

### Phòng ngừa
- [ ] `throttle` middleware on all API routes
- [ ] Stricter limits on auth endpoints
- [ ] Per-user or per-IP limits
- Tool: Laravel RateLimiter

---

## Pattern 07: Mass Assignment Vulnerability

### Tên
Mass Assignment Vulnerability (Fillable/Guarded Thiếu)

### Phân loại
API Design / Security / Mass Assignment

### Mức nghiêm trọng
CRITICAL 🔴

### Vấn đề

```php
User::create($request->all());
// If request has: { "name": "John", "is_admin": true }
// → User created as admin!
```

### Phát hiện

```bash
rg --type php "\$request->all\(\)" -n
rg --type php "->fill\(|::create\(|::update\(" -n
rg --type php "\$fillable|\$guarded" -n
```

### Giải pháp

❌ **BAD**
```php
User::create($request->all()); // ALL fields including is_admin!
$user->fill($request->input()); // Same problem
```

✅ **GOOD**
```php
// Model:
class User extends Model {
    protected $fillable = ['name', 'email', 'password'];
    // is_admin NOT in fillable
}

// Controller — use validated() only:
User::create($request->validated());

// Or explicit assignment:
$user = new User();
$user->name = $request->validated('name');
$user->email = $request->validated('email');
$user->save();
```

### Phòng ngừa
- [ ] `$fillable` whitelist on all models
- [ ] `$request->validated()` not `$request->all()`
- [ ] NEVER trust raw request data
- Tool: PHPStan, Laravel mass assignment protection

---

## Pattern 08: OpenAPI Spec Out Of Sync

### Tên
OpenAPI Spec Out Of Sync (API Docs Don't Match Code)

### Phân loại
API Design / Documentation / Consistency

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```
Swagger docs say: POST /api/users accepts { name, email }
Code accepts: { name, email, role, department }
→ Frontend follows outdated docs
```

### Phát hiện

```bash
rg "openapi|swagger" -n --glob "*.yaml" --glob "*.json"
rg --type php "l5-swagger|scramble|scribe" -n
```

### Giải pháp

❌ **BAD**: Manual OpenAPI spec that gets outdated

✅ **GOOD**
```php
// Auto-generate from code using Scramble (Laravel):
// composer require dedoc/scramble
// Automatically generates OpenAPI from routes, FormRequests, Resources

// Or Scribe:
// php artisan scribe:generate
// Generates from docblocks and route analysis

// CI: validate spec matches code
```

### Phòng ngừa
- [ ] Auto-generate OpenAPI from code
- [ ] CI validation that spec matches implementation
- [ ] Serve Swagger UI from app
- Tool: `dedoc/scramble`, `knuckleswtf/scribe`

---

## Pattern 09: Webhook Idempotency Thiếu

### Tên
Webhook Idempotency Thiếu (Duplicate Webhook Processing)

### Phân loại
API Design / Webhook / Reliability

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```
Payment gateway sends webhook:
1. "payment.completed" → Process payment ✓
2. Network timeout → Gateway retries
3. "payment.completed" (same event) → Process AGAIN!
→ Double charge, double credit, duplicate records
```

### Phát hiện

```bash
rg --type php "webhook|Webhook" -n
rg --type php "idempotency|idempotent" -i -n
rg --type php "event_id|webhook_id" -n
```

### Giải pháp

❌ **BAD**
```php
public function handleWebhook(Request $request) {
    $this->processPayment($request->input('payment_id'));
    return response('OK');
}
```

✅ **GOOD**
```php
public function handleWebhook(Request $request): Response
{
    $eventId = $request->input('event_id');

    // Idempotency check:
    if (ProcessedWebhook::where('event_id', $eventId)->exists()) {
        return response('Already processed', 200);
    }

    DB::transaction(function () use ($request, $eventId) {
        ProcessedWebhook::create(['event_id' => $eventId]);
        $this->processPayment($request->input('payment_id'));
    });

    return response('OK', 200);
}
```

### Phòng ngừa
- [ ] Store processed event IDs
- [ ] Check before processing
- [ ] Use database transactions for atomicity
- Tool: Unique constraint on event_id column

---

## Pattern 10: Batch Endpoint Thiếu

### Tên
Batch Endpoint Thiếu (No Bulk Operations)

### Phân loại
API Design / Performance / Batch

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```
Frontend needs to update 100 items:
100 × PUT /api/items/{id} → 100 HTTP requests
→ High latency, connection overhead
→ Server processes 100 separate transactions
```

### Phát hiện

```bash
rg --type php "Route::.*(update|store|destroy)" -n
rg --type php "batch|bulk|mass" -i -n
```

### Giải pháp

❌ **BAD**: Only single-item endpoints

✅ **GOOD**
```php
// Batch update endpoint:
Route::put('api/items/batch', [ItemController::class, 'batchUpdate']);

public function batchUpdate(BatchUpdateRequest $request): JsonResponse
{
    $items = $request->validated('items'); // [{id: 1, status: 'active'}, ...]

    DB::transaction(function () use ($items) {
        foreach ($items as $item) {
            Item::where('id', $item['id'])->update(Arr::except($item, 'id'));
        }
    });

    return response()->json(['updated' => count($items)]);
}

// Or upsert for batch create/update:
Item::upsert($items, ['id'], ['status', 'name']);
```

### Phòng ngừa
- [ ] Batch endpoints for bulk operations
- [ ] `upsert()` for create-or-update
- [ ] Transaction wrapping for atomicity
- Tool: Laravel `upsert()`, `insert()`
