# Domain 03: Bảo Mật Và Xác Thực (Authentication Security)

**Ngôn ngữ:** PHP (Laravel / Symfony)
**Tổng số pattern:** 12
**Cập nhật:** 2026-02-18

---

## Pattern 01: MD5/SHA1 Cho Password (Weak Hashing)

### Tên
MD5/SHA1 Password Hashing

### Phân loại
Authentication / Cryptography

### Mức nghiêm trọng
CRITICAL 🔴

### Vấn đề

```
Attacker có DB dump
        │
        ▼
┌───────────────────┐
│  md5('secret123') │  ← hash cố định, không có salt
│  = 5ebe2294ecd0e0 │
└───────────────────┘
        │
        ▼
  Rainbow table / hashcat
  crack trong vài giây
        │
        ▼
  Toàn bộ user bị lộ password
```

MD5 và SHA1 là các thuật toán hash **tốc độ cao**, không được thiết kế cho password. GPU hiện đại có thể thử hàng tỷ hash/giây. Không có salt → rainbow table tấn công trực tiếp.

### Phát hiện

```bash
# Tìm sử dụng md5/sha1 cho password
rg --type php "md5\s*\(" -n
rg --type php "sha1\s*\(" -n
rg --type php "hash\s*\(\s*['\"]md5['\"]" -n
rg --type php "hash\s*\(\s*['\"]sha1['\"]" -n
rg --type php "hash\s*\(\s*['\"]sha256['\"]" -n

# Tìm trong migration/seeder
rg --type php "password.*md5|md5.*password" -in
rg --type php "password.*sha|sha.*password" -in
```

### Giải pháp

**BAD:**
```php
<?php
// ❌ MD5 - crack được trong giây
class UserController
{
    public function register(Request $request): JsonResponse
    {
        $user = User::create([
            'email'    => $request->email,
            'password' => md5($request->password),  // CRITICAL: rainbow table!
        ]);

        return response()->json(['user' => $user]);
    }

    public function login(Request $request): JsonResponse
    {
        $user = User::where('email', $request->email)->first();

        // ❌ So sánh md5 trực tiếp
        if ($user && $user->password === md5($request->password)) {
            return response()->json(['token' => $user->createToken('auth')->plainTextToken]);
        }

        return response()->json(['error' => 'Invalid credentials'], 401);
    }
}

// ❌ SHA1 - cũng không an toàn
$hash = sha1($password);

// ❌ SHA256 không salt - vẫn bị dictionary attack
$hash = hash('sha256', $password);
```

**GOOD:**
```php
<?php
// ✅ Sử dụng password_hash() với PASSWORD_BCRYPT hoặc PASSWORD_ARGON2ID
class UserController
{
    public function register(Request $request): JsonResponse
    {
        $validated = $request->validate([
            'email'    => 'required|email|unique:users',
            'password' => 'required|min:12|confirmed',
        ]);

        $user = User::create([
            'email'    => $validated['email'],
            // ✅ Argon2id: memory-hard, GPU/ASIC resistant
            'password' => password_hash(
                $validated['password'],
                PASSWORD_ARGON2ID,
                [
                    'memory_cost' => 65536,  // 64MB
                    'time_cost'   => 4,       // 4 iterations
                    'threads'     => 2,
                ]
            ),
        ]);

        return response()->json(['user' => $user->only(['id', 'email'])], 201);
    }

    public function login(Request $request): JsonResponse
    {
        $user = User::where('email', $request->email)->first();

        // ✅ password_verify() - constant-time + tự xử lý salt
        if (! $user || ! password_verify($request->password, $user->password)) {
            // ✅ Không tiết lộ user có tồn tại hay không
            return response()->json(['error' => 'Invalid credentials'], 401);
        }

        // ✅ Tự động rehash nếu algorithm thay đổi
        if (password_needs_rehash($user->password, PASSWORD_ARGON2ID)) {
            $user->update([
                'password' => password_hash($request->password, PASSWORD_ARGON2ID),
            ]);
        }

        return response()->json(['token' => $user->createToken('auth')->plainTextToken]);
    }
}

// ✅ Laravel: dùng Hash facade (Bcrypt mặc định, cấu hình Argon2id)
// config/hashing.php: 'driver' => 'argon2id'
use Illuminate\Support\Facades\Hash;

$hashed = Hash::make($password);
Hash::check($password, $hashed); // constant-time
```

### Phòng ngừa

```xml
<!-- phpstan.neon - cấm dùng md5/sha1 cho password -->
parameters:
    forbidden_functions:
        - md5
        - sha1
        - crc32
```

```php
<?php
// Psalm: custom rule cảnh báo md5/sha1
// psalm-plugin: ForbiddenFunctions
// Thêm vào psalm.xml:
// <forbiddenFunctions>
//   <function name="md5"/>
//   <function name="sha1"/>
// </forbiddenFunctions>
```

```bash
# PHP CS Fixer rule
# .php-cs-fixer.php
$config->setRules([
    'no_alias_functions' => true,
    // Custom sniff: SlevomatCodingStandard
]);

# Kiểm tra nhanh toàn project
rg --type php "(md5|sha1)\s*\(" --stats
```

---

## Pattern 02: Timing Attack Trong Compare

### Tên
String Comparison Timing Attack

### Phân loại
Authentication / Side-Channel Attack

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```
Attacker gửi token thử dần
        │
        ▼
┌──────────────────────────────┐
│  strcmp("AAAA", "XBCD")     │  ← return ngay khi 'A' ≠ 'X'
│  strcmp("XAAA", "XBCD")     │  ← mất thêm 1 char để compare
│  strcmp("XBAA", "XBCD")     │  ← mất thêm 2 chars
└──────────────────────────────┘
        │
        ▼
  Đo thời gian response
  → Đoán được từng ký tự token
  → Brute-force có chủ đích
```

PHP's `==`, `===`, `strcmp()` dừng so sánh ngay khi tìm thấy ký tự khác nhau. Attacker đo latency để suy ra token từng byte.

### Phát hiện

```bash
# Tìm so sánh token/secret bằng == hoặc strcmp
rg --type php "token.*==|==.*token" -n
rg --type php "secret.*==|==.*secret" -n
rg --type php "strcmp\s*\(" -n
rg --type php "strncmp\s*\(" -n

# Tìm trong middleware/auth
rg --type php "api.?key.*===|===.*api.?key" -in
rg --type php "hmac.*==|signature.*==" -in
```

### Giải pháp

**BAD:**
```php
<?php
// ❌ === bị timing attack
class WebhookController
{
    public function handleStripe(Request $request): Response
    {
        $signature = $request->header('X-Stripe-Signature');
        $expected   = hash_hmac('sha256', $request->getContent(), config('stripe.secret'));

        // ❌ So sánh thông thường - timing attack!
        if ($signature !== $expected) {
            abort(403, 'Invalid signature');
        }

        return $this->processWebhook($request->json()->all());
    }
}

// ❌ strcmp cũng bị timing attack
function validateApiKey(string $provided, string $stored): bool
{
    return strcmp($provided, $stored) === 0;  // WRONG!
}

// ❌ Custom compare loop
function compareTokens(string $a, string $b): bool
{
    if (strlen($a) !== strlen($b)) {
        return false;  // Vẫn leak độ dài!
    }
    for ($i = 0; $i < strlen($a); $i++) {
        if ($a[$i] !== $b[$i]) {
            return false;  // Dừng sớm!
        }
    }
    return true;
}
```

**GOOD:**
```php
<?php
// ✅ hash_equals() - constant-time comparison (PHP built-in)
class WebhookController
{
    public function handleStripe(Request $request): Response
    {
        $payload   = $request->getContent();
        $signature = $request->header('X-Stripe-Signature', '');
        $expected  = hash_hmac('sha256', $payload, config('stripe.secret'));

        // ✅ Constant-time: luôn so sánh đủ toàn bộ chuỗi
        if (! hash_equals($expected, $signature)) {
            abort(403, 'Invalid signature');
        }

        return $this->processWebhook($request->json()->all());
    }
}

// ✅ Utility function chuẩn
function secureCompare(string $knownString, string $userString): bool
{
    // hash_equals yêu cầu cùng độ dài - hash trước để chuẩn hóa
    $knownHash = hash('sha256', $knownString);
    $userHash  = hash('sha256', $userString);

    return hash_equals($knownHash, $userHash);
}

// ✅ Laravel: dùng Str::is() không phù hợp cho secret
// Dùng hash_equals trực tiếp cho mọi so sánh secret

// ✅ Symfony: dùng hash_equals() hoặc StringUtils::equals()
use Symfony\Component\Security\Core\Util\StringUtils;

// StringUtils::equals() bên trong dùng hash_equals
$isValid = StringUtils::equals($storedSecret, $providedSecret);

// ✅ API Key validation
class ApiKeyMiddleware
{
    public function handle(Request $request, Closure $next): Response
    {
        $provided = $request->header('X-API-Key', '');
        $stored   = config('app.api_key');

        // ✅ Hash cả hai để đảm bảo cùng độ dài trước khi so sánh
        if (! hash_equals(hash('sha256', $stored), hash('sha256', $provided))) {
            return response()->json(['error' => 'Unauthorized'], 401);
        }

        return $next($request);
    }
}
```

### Phòng ngừa

```bash
# Tìm tất cả so sánh string trong security-critical code
rg --type php "=== \$.*token|=== \$.*key|=== \$.*secret|=== \$.*hash" -n

# Đảm bảo dùng hash_equals
rg --type php "hash_equals" --stats
```

```xml
<!-- PHPStan: custom rule cảnh báo strcmp trong auth context -->
<!-- Dùng phpstan-strict-rules -->
includes:
    - vendor/phpstan/phpstan-strict-rules/rules.neon
```

---

## Pattern 03: JWT Secret Weak

### Tên
Weak JWT Secret / Algorithm Confusion

### Phân loại
Authentication / JWT

### Mức nghiêm trọng
CRITICAL 🔴

### Vấn đề

```
JWT header.payload.signature
        │
        ▼
┌──────────────────────────────────┐
│ SECRET = "secret" hoặc "123456"  │  ← dictionary attack
│ SECRET = app name, domain        │  ← predictable
│ ALG = "none"                     │  ← bypass hoàn toàn!
└──────────────────────────────────┘
        │
        ▼
  Attacker forge token bất kỳ:
  {"sub":"admin","role":"admin"}
        │
        ▼
  Chiếm toàn bộ hệ thống
```

JWT với secret yếu bị brute-force offline (không cần gửi request). Algorithm "none" bypass signature hoàn toàn.

### Phát hiện

```bash
# Tìm JWT secret yếu hoặc hardcoded
rg --type php "JWT_SECRET|jwt.secret|jwt_secret" -in
rg --type php "'secret'|\"secret\"|'password'|\"password\"" -n
rg --type php "HS256.*secret|secret.*HS256" -in

# Tìm algorithm "none" vulnerability
rg --type php "alg.*none|none.*alg" -in
rg --type php "allowedAlgorithms|supported_algs" -n

# Tìm trong .env files
rg "JWT_SECRET=.{1,20}$" .env* --no-ignore
```

### Giải pháp

**BAD:**
```php
<?php
use Firebase\JWT\JWT;
use Firebase\JWT\Key;

// ❌ Secret yếu, hardcoded
class JwtService
{
    private string $secret = 'secret';  // CRITICAL: quá yếu!

    public function generateToken(User $user): string
    {
        return JWT::encode(
            ['sub' => $user->id, 'role' => $user->role],
            $this->secret,
            'HS256'
        );
    }

    public function validateToken(string $token): object
    {
        // ❌ Chấp nhận nhiều algorithm - algorithm confusion attack!
        return JWT::decode($token, new Key($this->secret, 'HS256'));
        // Hoặc tệ hơn:
        // JWT::decode($token, $this->secret, ['HS256', 'HS384', 'HS512', 'none'])
    }
}

// ❌ Secret từ config không đủ entropy
// APP_KEY=base64:abcdefgh... (Laravel APP_KEY không phải JWT secret!)
$secret = config('app.key');  // WRONG: dùng nhầm APP_KEY!

// ❌ JWT payload không validate claims
$decoded = JWT::decode($token, new Key($secret, 'HS256'));
$userId  = $decoded->sub;  // Không check exp, iss, aud!
```

**GOOD:**
```php
<?php
use Firebase\JWT\JWT;
use Firebase\JWT\Key;
use Ramsey\Uuid\Uuid;

// ✅ JWT Service chuẩn
class JwtService
{
    private string $secret;
    private string $algorithm = 'HS256';
    private int $ttl = 3600; // 1 giờ

    public function __construct()
    {
        $secret = config('jwt.secret');

        // ✅ Validate secret đủ mạnh khi khởi động
        if (empty($secret) || strlen($secret) < 32) {
            throw new \RuntimeException(
                'JWT_SECRET must be at least 32 characters. Run: php artisan jwt:secret'
            );
        }

        $this->secret = $secret;
    }

    public function generateToken(User $user): string
    {
        $now = time();

        return JWT::encode(
            [
                'iss' => config('app.url'),            // Issuer
                'aud' => config('app.url'),            // Audience
                'iat' => $now,                          // Issued at
                'exp' => $now + $this->ttl,             // Expiry
                'nbf' => $now,                          // Not before
                'jti' => Uuid::uuid4()->toString(),     // ✅ JWT ID (prevent replay)
                'sub' => $user->id,
                // ❌ KHÔNG đặt password, secret vào payload!
            ],
            $this->secret,
            $this->algorithm
        );
    }

    public function validateToken(string $token): object
    {
        try {
            // ✅ Chỉ chấp nhận HS256 - không cho phép "none" hay algorithm confusion
            $decoded = JWT::decode($token, new Key($this->secret, $this->algorithm));

            // ✅ Validate claims thêm
            $this->validateClaims($decoded);

            return $decoded;
        } catch (\Firebase\JWT\ExpiredException $e) {
            throw new AuthenticationException('Token expired');
        } catch (\Firebase\JWT\SignatureInvalidException $e) {
            throw new AuthenticationException('Invalid token signature');
        } catch (\Exception $e) {
            throw new AuthenticationException('Invalid token');
        }
    }

    private function validateClaims(object $decoded): void
    {
        $appUrl = config('app.url');

        if (($decoded->iss ?? '') !== $appUrl) {
            throw new AuthenticationException('Invalid token issuer');
        }

        if (($decoded->aud ?? '') !== $appUrl) {
            throw new AuthenticationException('Invalid token audience');
        }
    }
}
```

```bash
# ✅ Tạo JWT secret đủ mạnh (256-bit entropy)
php -r "echo base64_encode(random_bytes(32));"
# Hoặc:
openssl rand -base64 32
```

```ini
# .env - JWT secret đủ mạnh
JWT_SECRET=7xK9mP2nQ5rL8vF1yB4wE6uH3jG0dC... # 32+ chars random
JWT_TTL=3600
JWT_REFRESH_TTL=86400
```

### Phòng ngừa

```php
<?php
// AppServiceProvider::boot() - validate JWT config khi boot
public function boot(): void
{
    if (app()->isProduction()) {
        $secret = config('jwt.secret');
        assert(strlen($secret) >= 32, 'JWT_SECRET too weak for production!');
    }
}
```

```bash
# PHPStan: tìm hardcoded secret
rg --type php "=\s*['\"]secret['\"]|=\s*['\"]password['\"]|=\s*['\"]123" -n
```

---

## Pattern 04: Remember-Me Token Predictable

### Tên
Predictable Remember-Me Token

### Phân loại
Authentication / Session Management

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```
Token = md5(user_id + timestamp)
           │
           ▼
┌─────────────────────────────┐
│  user_id: public (1, 2, 3)  │
│  timestamp: đoán được       │
└─────────────────────────────┘
           │
           ▼
  Attacker brute-force token
  Chiếm session "Nhớ tôi" mà
  không cần password
```

Remember-me token phải là random bytes không thể đoán. Token dựa trên dữ liệu biết trước → có thể forge.

### Phát hiện

```bash
# Tìm token generation yếu
rg --type php "remember.*md5|md5.*remember" -in
rg --type php "remember.*time\(\)|time\(\).*remember" -in
rg --type php "uniqid\s*\(" -n  # uniqid() KHÔNG đủ random!
rg --type php "rand\s*\(|mt_rand\s*\(" -n  # Không dùng cho security!

# Tìm remember_token generation
rg --type php "remember_token" -n
rg --type php "createRememberToken\|generateRememberToken" -n
```

### Giải pháp

**BAD:**
```php
<?php
// ❌ Token predictable
class AuthController
{
    public function login(Request $request): RedirectResponse
    {
        if (Auth::attempt($request->only('email', 'password'))) {
            if ($request->boolean('remember')) {
                $user  = Auth::user();
                // ❌ Predictable: user_id + timestamp
                $token = md5($user->id . time());
                // ❌ uniqid() dựa trên microsecond timestamp
                $token = uniqid('remember_', true);
                // ❌ rand() không cryptographically secure
                $token = md5(rand(100000, 999999));

                Cookie::queue('remember_me', $token, 43200); // 30 days
                $user->update(['remember_token' => $token]);
            }

            return redirect('/dashboard');
        }

        return back()->withErrors(['email' => 'Invalid credentials']);
    }

    public function autoLogin(Request $request): RedirectResponse
    {
        $token = $request->cookie('remember_me');
        $user  = User::where('remember_token', $token)->first();

        // ❌ Không rotate token sau khi dùng!
        if ($user) {
            Auth::login($user);
            return redirect('/dashboard');
        }

        return redirect('/login');
    }
}
```

**GOOD:**
```php
<?php
// ✅ Cryptographically secure remember-me token
class AuthController
{
    private const REMEMBER_COOKIE_DAYS = 30;
    private const TOKEN_BYTES          = 32; // 256-bit entropy

    public function login(Request $request): RedirectResponse
    {
        $credentials = $request->validate([
            'email'    => 'required|email',
            'password' => 'required',
            'remember' => 'boolean',
        ]);

        if (! Auth::attempt(
            $request->only('email', 'password'),
            $request->boolean('remember')  // ✅ Laravel tự xử lý remember-me
        )) {
            return back()->withErrors(['email' => 'Invalid credentials'])
                         ->onlyInput('email');
        }

        $request->session()->regenerate(); // ✅ Prevent session fixation

        return redirect()->intended('/dashboard');
    }
}

// ✅ Nếu cần custom remember-me token
class RememberMeService
{
    public function generateToken(): string
    {
        // ✅ random_bytes() - CSPRNG (Cryptographically Secure PRN)
        return bin2hex(random_bytes(self::TOKEN_BYTES));
        // Kết quả: 64 hex chars, 256-bit entropy
    }

    public function storeToken(User $user, string $plainToken): void
    {
        // ✅ Lưu hash của token (không lưu plain text)
        $user->update([
            'remember_token'    => hash('sha256', $plainToken),
            'remember_token_at' => now(),
        ]);
    }

    public function validateToken(string $plainToken): ?User
    {
        $hashedToken = hash('sha256', $plainToken);

        $user = User::where('remember_token', $hashedToken)
                    ->where('remember_token_at', '>=', now()->subDays(30))
                    ->first();

        if (! $user) {
            return null;
        }

        // ✅ Rotate token sau mỗi lần dùng (prevent token reuse)
        $newToken = $this->generateToken();
        $this->storeToken($user, $newToken);
        Cookie::queue('remember_me', $newToken, 60 * 24 * 30);

        return $user;
    }

    public function invalidateToken(User $user): void
    {
        // ✅ Xóa token khi logout
        $user->update([
            'remember_token'    => null,
            'remember_token_at' => null,
        ]);
        Cookie::queue(Cookie::forget('remember_me'));
    }
}
```

### Phòng ngừa

```bash
# Kiểm tra usage của hàm random không an toàn
rg --type php "(uniqid|rand|mt_rand|microtime)\s*\(" -n

# Đảm bảo dùng random_bytes / random_int
rg --type php "random_bytes\|random_int" --stats
```

---

## Pattern 05: Rate Limiting Thiếu (Brute Force)

### Tên
Missing Rate Limiting - Brute Force Attack

### Phân loại
Authentication / Access Control

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```
Attacker script tự động
        │
        ▼
POST /login × 10,000 lần
├── admin@site.com : password1
├── admin@site.com : password2
├── admin@site.com : password3
└── ...
        │
        ▼
  Không bị block
  Dictionary attack thành công
  Chiếm tài khoản admin
```

Không có rate limiting → brute force không giới hạn. Tool như Hydra/Burp Intruder tự động hóa hoàn toàn.

### Phát hiện

```bash
# Tìm login endpoint không có throttle
rg --type php "function login\|Route.*login" -n
rg --type php "throttle\|RateLimiter\|rate.limit" -in

# Kiểm tra middleware trong routes
rg --type php "middleware.*throttle" -n
rg "throttle" routes/ -rn

# Tìm password reset không có rate limit
rg --type php "sendResetLink\|forgotPassword\|reset.password" -in
```

### Giải pháp

**BAD:**
```php
<?php
// ❌ Login không có rate limiting
Route::post('/login', [AuthController::class, 'login']); // Không throttle!
Route::post('/forgot-password', [AuthController::class, 'forgotPassword']); // Không throttle!

// ❌ Controller không tự rate limit
class AuthController extends Controller
{
    public function login(Request $request): JsonResponse
    {
        // Không có bất kỳ rate limit check nào!
        $user = User::where('email', $request->email)->first();

        if ($user && Hash::check($request->password, $user->password)) {
            return response()->json(['token' => $user->createToken('auth')->plainTextToken]);
        }

        return response()->json(['error' => 'Invalid credentials'], 401);
    }
}
```

**GOOD:**
```php
<?php
// ✅ Route với throttle middleware
// routes/api.php
Route::middleware(['throttle:login'])->group(function () {
    Route::post('/login', [AuthController::class, 'login']);
});

Route::middleware(['throttle:5,1'])->group(function () {
    Route::post('/forgot-password', [AuthController::class, 'forgotPassword']);
    Route::post('/verify-2fa', [AuthController::class, 'verify2fa']);
});

// ✅ Cấu hình rate limiter trong RouteServiceProvider
// app/Providers/RouteServiceProvider.php
use Illuminate\Cache\RateLimiting\Limit;
use Illuminate\Support\Facades\RateLimiter;

protected function configureRateLimiting(): void
{
    // ✅ Login: 5 lần/phút theo IP + email (prevent credential stuffing)
    RateLimiter::for('login', function (Request $request) {
        return [
            Limit::perMinute(5)->by($request->ip()),
            Limit::perMinute(3)->by($request->input('email') . '|' . $request->ip()),
        ];
    });

    // ✅ API chung: 60 lần/phút
    RateLimiter::for('api', function (Request $request) {
        return Limit::perMinute(60)->by(
            optional($request->user())->id ?? $request->ip()
        );
    });
}

// ✅ Controller với progressive delay (thêm lớp bảo vệ)
class AuthController extends Controller
{
    public function login(Request $request): JsonResponse
    {
        $request->validate([
            'email'    => 'required|email',
            'password' => 'required',
        ]);

        $key = 'login_attempts:' . $request->ip() . ':' . $request->email;

        // ✅ Thêm progressive lockout
        $attempts = Cache::get($key, 0);
        if ($attempts >= 5) {
            $lockoutUntil = Cache::get($key . ':lockout');
            if ($lockoutUntil && now()->lt($lockoutUntil)) {
                return response()->json([
                    'error'       => 'Too many attempts',
                    'retry_after' => now()->diffInSeconds($lockoutUntil),
                ], 429);
            }
        }

        if (! Auth::attempt($request->only('email', 'password'))) {
            // ✅ Tăng counter với exponential backoff
            $newAttempts = $attempts + 1;
            Cache::put($key, $newAttempts, now()->addHour());

            if ($newAttempts >= 5) {
                // Lockout: 2^(attempts-5) phút
                $lockoutMinutes = pow(2, $newAttempts - 5);
                Cache::put($key . ':lockout', now()->addMinutes($lockoutMinutes), now()->addHour());
            }

            return response()->json(['error' => 'Invalid credentials'], 401);
        }

        // ✅ Reset counter sau login thành công
        Cache::forget($key);
        Cache::forget($key . ':lockout');

        $request->session()->regenerate();

        return response()->json([
            'token' => Auth::user()->createToken('auth')->plainTextToken,
        ]);
    }
}

// ✅ Symfony: dùng RateLimiter component
// config/packages/rate_limiter.yaml
/*
framework:
    rate_limiter:
        login:
            policy: token_bucket
            limit: 5
            rate: { interval: '1 minute' }
        api:
            policy: sliding_window
            limit: 100
            interval: '1 minute'
*/
```

### Phòng ngừa

```bash
# Kiểm tra tất cả POST routes có throttle chưa
rg "Route::post" routes/ -rn | grep -v throttle

# Đảm bảo login route có rate limiting
rg "login.*throttle\|throttle.*login" routes/ -rn
```

---

## Pattern 06: 2FA Bypass

### Tên
Two-Factor Authentication Bypass

### Phân loại
Authentication / Multi-Factor

### Mức nghiêm trọng
CRITICAL 🔴

### Vấn đề

```
Login flow chuẩn:
  ① Password OK  →  ② OTP check  →  ③ Access

Flow bị bypass:
  ① Password OK  →  ② Skip OTP  →  ③ Access (??)

Cách bypass phổ biến:
  - Truy cập trực tiếp dashboard URL sau step ①
  - Manipulate session flag 2fa_passed=true
  - Race condition giữa 2 request
  - OTP không expire / reusable
  - OTP length quá ngắn (4 digits)
```

### Phát hiện

```bash
# Tìm 2FA implementation
rg --type php "2fa|two.factor|totp|otp" -in
rg --type php "google2fa\|authy\|twilio" -in

# Tìm middleware 2FA
rg --type php "TwoFactor\|2fa.verified\|mfa" -in

# Tìm session flag cho 2FA
rg --type php "session.*2fa\|2fa.*session" -in
```

### Giải pháp

**BAD:**
```php
<?php
// ❌ 2FA flow không an toàn
class AuthController
{
    // Step 1: Login
    public function login(Request $request): RedirectResponse
    {
        if (Auth::attempt($request->only('email', 'password'))) {
            // ❌ Auth user NGAY - chưa xác minh 2FA!
            session(['2fa_pending' => true]);
            return redirect('/2fa/verify');
        }
        return back()->withErrors(['email' => 'Invalid credentials']);
    }

    // Step 2: Verify 2FA
    public function verify2fa(Request $request): RedirectResponse
    {
        $user = Auth::user(); // ❌ User đã logged in từ step 1!
        $otp  = $request->input('otp');

        // ❌ OTP không expire
        // ❌ OTP có thể reuse
        // ❌ Không có rate limit
        if ($otp === $user->current_otp) {
            session(['2fa_verified' => true]);
            return redirect('/dashboard');
        }

        return back()->withErrors(['otp' => 'Invalid OTP']);
    }
}

// ❌ Middleware lỏng lẻo
class Require2fa
{
    public function handle(Request $request, Closure $next): Response
    {
        // ❌ Chỉ check session flag - có thể forge!
        if (! session('2fa_verified')) {
            return redirect('/2fa/verify');
        }
        return $next($request);
    }
}

// ❌ Dashboard không được protect đúng
Route::get('/dashboard', [DashboardController::class, 'index']);
// Quên add middleware Require2fa!
```

**GOOD:**
```php
<?php
// ✅ 2FA flow an toàn với state machine
class AuthController
{
    // Step 1: Verify password, KHÔNG login vào session chính
    public function login(Request $request): RedirectResponse
    {
        $request->validate([
            'email'    => 'required|email',
            'password' => 'required',
        ]);

        $user = User::where('email', $request->email)->first();

        if (! $user || ! Hash::check($request->password, $user->password)) {
            return back()->withErrors(['email' => 'Invalid credentials'])->onlyInput('email');
        }

        // ✅ Lưu user ID tạm thời (KHÔNG login), dùng signed data
        $request->session()->put([
            '2fa_user_id'  => $user->id,
            '2fa_started'  => now()->timestamp,
        ]);

        // Gửi OTP
        $this->send2faCode($user);

        return redirect('/2fa/verify');
    }

    // Step 2: Verify OTP, sau đó mới thực sự login
    public function verify2fa(Request $request): RedirectResponse
    {
        $userId    = $request->session()->get('2fa_user_id');
        $startedAt = $request->session()->get('2fa_started');

        // ✅ Validate session còn hiệu lực (max 10 phút)
        if (! $userId || ! $startedAt || (now()->timestamp - $startedAt) > 600) {
            return redirect('/login')->withErrors(['error' => 'Session expired, please login again']);
        }

        $user = User::findOrFail($userId);

        // ✅ Rate limit OTP verification (3 lần/5 phút)
        $attemptKey = '2fa_attempts:' . $userId;
        if (Cache::get($attemptKey, 0) >= 3) {
            return redirect('/login')->withErrors(['error' => 'Too many OTP attempts']);
        }

        $request->validate(['otp' => 'required|digits:6']);

        // ✅ Verify TOTP (time-based, tự expire)
        $google2fa = new Google2FA();
        $isValid   = $google2fa->verifyKey(
            $user->google2fa_secret,
            $request->otp,
            2 // ✅ Window: ±2 * 30s = 1 phút tolerance
        );

        if (! $isValid) {
            Cache::increment($attemptKey);
            Cache::put($attemptKey, Cache::get($attemptKey), now()->addMinutes(5));
            return back()->withErrors(['otp' => 'Invalid OTP']);
        }

        // ✅ Check OTP chưa được dùng (prevent replay)
        $usedKey = '2fa_used:' . $userId . ':' . $request->otp;
        if (Cache::has($usedKey)) {
            return back()->withErrors(['otp' => 'OTP already used']);
        }
        Cache::put($usedKey, true, now()->addMinutes(2)); // OTP valid 30s, giữ 2 phút để an toàn

        // ✅ Xóa 2FA session
        $request->session()->forget(['2fa_user_id', '2fa_started']);
        Cache::forget($attemptKey);

        // ✅ Bây giờ mới thực sự login
        Auth::login($user, $request->boolean('remember'));
        $request->session()->regenerate();

        return redirect()->intended('/dashboard');
    }
}

// ✅ Middleware 2FA (dùng Auth guard, không phụ thuộc session flag)
class Require2faMiddleware
{
    public function handle(Request $request, Closure $next): Response
    {
        // Chỉ access sau khi Auth::login() thực sự được gọi
        if (! Auth::check()) {
            return redirect('/login');
        }

        // ✅ 2FA verified = user đã qua cả 2 bước
        // Không cần thêm flag vì Auth::login() chỉ được gọi sau verify2fa
        return $next($request);
    }
}

// ✅ Routes với middleware đúng
Route::middleware(['auth', 'verified'])->group(function () {
    Route::get('/dashboard', [DashboardController::class, 'index']);
    // Mọi route cần auth đều ở đây
});
```

### Phòng ngừa

```bash
# Kiểm tra routes có middleware auth
rg "Route::get\|Route::post" routes/ -rn | grep -v middleware
# Kiểm tra tất cả controller action có check auth không
rg --type php "Auth::check\|auth()->check\|middleware.*auth" -n
```

---

## Pattern 07: Password Reset Token Reuse

### Tên
Password Reset Token Reuse / Non-Expiry

### Phân loại
Authentication / Token Management

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```
Email reset password bị lộ / forward
          │
          ▼
┌─────────────────────────────────┐
│  Token không expire             │  ← Link vẫn dùng được sau 1 tuần
│  Token không bị invalidate      │  ← Sau reset, link cũ vẫn work!
│  Token không bind với email     │  ← Thay email → vẫn dùng được
└─────────────────────────────────┘
          │
          ▼
  Attacker dùng token cũ
  Reset password bất cứ lúc nào
```

### Phát hiện

```bash
# Tìm password reset implementation
rg --type php "sendResetLink\|ResetPassword\|password.reset" -in
rg --type php "password_resets\|PasswordReset" -n

# Kiểm tra token expiry
rg --type php "expires_at\|expire\|ttl" -n
rg "passwords.*expire\|expire.*passwords" config/ -rn
```

### Giải pháp

**BAD:**
```php
<?php
// ❌ Token không expire, không invalidate
class PasswordController
{
    public function sendResetLink(Request $request): JsonResponse
    {
        $user  = User::where('email', $request->email)->firstOrFail();
        $token = Str::random(60); // ❌ Không expire

        DB::table('password_resets')->insert([
            'email'      => $user->email,
            'token'      => $token, // ❌ Lưu plain text!
            'created_at' => now(),
            // Không có expires_at!
        ]);

        Mail::to($user)->send(new ResetPasswordMail($token));
        return response()->json(['message' => 'Reset link sent']);
    }

    public function resetPassword(Request $request): JsonResponse
    {
        $reset = DB::table('password_resets')
                   ->where('email', $request->email)
                   ->where('token', $request->token) // ❌ Plain text compare
                   ->first();

        if (! $reset) {
            return response()->json(['error' => 'Invalid token'], 400);
        }

        // ❌ Token không bị xóa sau khi dùng!
        User::where('email', $request->email)->update([
            'password' => Hash::make($request->password),
        ]);

        return response()->json(['message' => 'Password reset']);
    }
}
```

**GOOD:**
```php
<?php
// ✅ Laravel built-in Password Broker (chuẩn bảo mật)
// Sử dụng Password::sendResetLink() và Password::reset() là ĐÚNG cách
use Illuminate\Support\Facades\Password;

class PasswordController
{
    private const TOKEN_EXPIRY_MINUTES = 60;

    public function sendResetLink(Request $request): JsonResponse
    {
        $request->validate(['email' => 'required|email']);

        // ✅ Laravel tự động: hash token, set expiry, một token per user
        $status = Password::sendResetLink($request->only('email'));

        // ✅ Trả về cùng message dù email có tồn tại hay không (prevent enumeration)
        return response()->json([
            'message' => 'If that email exists, a reset link has been sent.',
        ]);
    }

    public function resetPassword(Request $request): JsonResponse
    {
        $request->validate([
            'token'                 => 'required',
            'email'                 => 'required|email',
            'password'              => 'required|min:12|confirmed',
            'password_confirmation' => 'required',
        ]);

        // ✅ Laravel: verify token, check expiry, invalidate sau dùng
        $status = Password::reset(
            $request->only('email', 'password', 'password_confirmation', 'token'),
            function (User $user, string $password) {
                $user->forceFill([
                    'password' => Hash::make($password),
                ])->setRememberToken(Str::random(60)); // ✅ Invalidate remember-me tokens

                $user->save();

                // ✅ Logout tất cả sessions khác
                Auth::logoutOtherDevices($password);

                event(new PasswordReset($user));
            }
        );

        if ($status !== Password::PASSWORD_RESET) {
            return response()->json(['error' => __($status)], 400);
        }

        return response()->json(['message' => 'Password has been reset']);
    }
}

// ✅ Config expiry trong config/auth.php
/*
'passwords' => [
    'users' => [
        'provider' => 'users',
        'table'    => 'password_reset_tokens',
        'expire'   => 60,      // ✅ 60 phút
        'throttle' => 60,      // ✅ Rate limit: 1 email/60 giây
    ],
],
*/

// ✅ Nếu custom implementation
class CustomPasswordResetService
{
    public function createToken(User $user): string
    {
        // ✅ Xóa token cũ trước
        DB::table('password_reset_tokens')->where('email', $user->email)->delete();

        $plainToken = bin2hex(random_bytes(32)); // 256-bit

        DB::table('password_reset_tokens')->insert([
            'email'      => $user->email,
            'token'      => hash('sha256', $plainToken), // ✅ Lưu hash
            'created_at' => now(),
        ]);

        return $plainToken; // Gửi plain token qua email
    }

    public function validateToken(string $email, string $plainToken): bool
    {
        $record = DB::table('password_reset_tokens')
                    ->where('email', $email)
                    ->where('created_at', '>=', now()->subMinutes(60)) // ✅ Check expiry
                    ->first();

        if (! $record) {
            return false;
        }

        // ✅ Constant-time compare hashed token
        return hash_equals($record->token, hash('sha256', $plainToken));
    }

    public function invalidateToken(string $email): void
    {
        // ✅ Xóa ngay sau khi dùng
        DB::table('password_reset_tokens')->where('email', $email)->delete();
    }
}
```

### Phòng ngừa

```bash
# Kiểm tra config expiry
rg "expire.*password\|password.*expire" config/ -rn

# Tìm custom reset implementation thiếu invalidation
rg --type php "password_resets\|password_reset_tokens" -n
```

---

## Pattern 08: OAuth State Parameter Thiếu

### Tên
Missing OAuth State Parameter (CSRF on OAuth)

### Phân loại
Authentication / OAuth / CSRF

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```
OAuth flow hợp lệ:
  ① App tạo state=RANDOM → lưu session
  ② Redirect sang Provider với ?state=RANDOM
  ③ Provider redirect về /callback?code=...&state=RANDOM
  ④ App verify state = session state → OK

Không có state parameter:
  ① Attacker tạo OAuth URL với client_id của victim app
  ② Trick victim click link → /callback?code=ATTACKER_CODE
  ③ App không verify → bind attacker account với victim account
  ④ Attacker login = victim identity!
```

### Phát hiện

```bash
# Tìm OAuth implementation
rg --type php "oauth\|socialite\|social.login" -in
rg --type php "getAuthorizationUrl\|redirect.*oauth" -in

# Kiểm tra state parameter
rg --type php "state.*session\|session.*state" -in
rg --type php "oauth.*state\|state.*oauth" -in

# Laravel Socialite
rg --type php "Socialite::" -n
```

### Giải pháp

**BAD:**
```php
<?php
// ❌ OAuth không có state parameter
class SocialAuthController
{
    public function redirectToGoogle(): RedirectResponse
    {
        $authUrl = 'https://accounts.google.com/o/oauth2/auth?' . http_build_query([
            'client_id'     => config('services.google.client_id'),
            'redirect_uri'  => route('oauth.google.callback'),
            'response_type' => 'code',
            'scope'         => 'email profile',
            // ❌ Không có state parameter!
        ]);

        return redirect($authUrl);
    }

    public function handleGoogleCallback(Request $request): RedirectResponse
    {
        // ❌ Không verify state!
        $code = $request->query('code');
        // Trực tiếp exchange code lấy token...
        $user = $this->exchangeCodeForUser($code);
        Auth::login($user);
        return redirect('/dashboard');
    }
}

// ❌ Laravel Socialite - stateless() bỏ qua state check
Route::get('/oauth/google/callback', function () {
    // ❌ stateless() disables state verification!
    $user = Socialite::driver('google')->stateless()->user();
    // ...
});
```

**GOOD:**
```php
<?php
// ✅ OAuth với state parameter đúng cách

// ✅ Laravel Socialite - tự động handle state
class SocialAuthController
{
    public function redirectToGoogle(): RedirectResponse
    {
        // ✅ Socialite tự tạo state, lưu session, verify khi callback
        return Socialite::driver('google')
                        ->scopes(['email', 'profile'])
                        ->redirect();
        // KHÔNG dùng ->stateless()!
    }

    public function handleGoogleCallback(Request $request): RedirectResponse
    {
        try {
            // ✅ Socialite tự verify state parameter
            $socialUser = Socialite::driver('google')->user();
        } catch (\Laravel\Socialite\Two\InvalidStateException $e) {
            // ✅ State mismatch = CSRF attack hoặc session expired
            return redirect('/login')->withErrors(['error' => 'OAuth state mismatch. Please try again.']);
        } catch (\Exception $e) {
            return redirect('/login')->withErrors(['error' => 'OAuth authentication failed.']);
        }

        // ✅ Find or create user an toàn
        $user = User::updateOrCreate(
            ['google_id' => $socialUser->getId()],
            [
                'name'          => $socialUser->getName(),
                'email'         => $socialUser->getEmail(),
                'google_token'  => encrypt($socialUser->token), // ✅ Encrypt token
                'avatar'        => $socialUser->getAvatar(),
            ]
        );

        // ✅ Verify email từ OAuth provider (Google đã verify)
        if (! $user->hasVerifiedEmail()) {
            $user->markEmailAsVerified();
        }

        Auth::login($user, false); // Không remember-me tự động
        $request->session()->regenerate();

        return redirect()->intended('/dashboard');
    }
}

// ✅ Custom OAuth (nếu không dùng Socialite)
class CustomOAuthService
{
    public function getAuthorizationUrl(): string
    {
        $state = bin2hex(random_bytes(16)); // 128-bit random state
        session(['oauth_state' => $state, 'oauth_state_at' => now()->timestamp]);

        return 'https://provider.com/oauth?' . http_build_query([
            'client_id'     => config('oauth.client_id'),
            'redirect_uri'  => route('oauth.callback'),
            'response_type' => 'code',
            'state'         => $state, // ✅ Include state
            'scope'         => 'email profile',
        ]);
    }

    public function handleCallback(Request $request): void
    {
        // ✅ Verify state
        $sessionState = session('oauth_state');
        $sessionAt    = session('oauth_state_at');

        // ✅ State phải tồn tại và không quá 10 phút
        if (! $sessionState || (now()->timestamp - $sessionAt) > 600) {
            throw new \Exception('OAuth session expired');
        }

        // ✅ Constant-time compare
        if (! hash_equals($sessionState, $request->query('state', ''))) {
            throw new \Exception('OAuth state mismatch - possible CSRF attack');
        }

        // ✅ Xóa state sau khi dùng
        session()->forget(['oauth_state', 'oauth_state_at']);

        // Exchange code for token...
    }
}
```

### Phòng ngừa

```bash
# Đảm bảo không dùng stateless() trong OAuth
rg --type php "->stateless()" -n

# Kiểm tra state verification
rg --type php "oauth_state\|InvalidStateException" -n
```

---

## Pattern 09: Bcrypt Truncation (72 bytes limit)

### Tên
Bcrypt 72-Byte Password Truncation

### Phân loại
Authentication / Cryptography

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```
Password: "correct_horse_battery_staple_very_long_password_that_exceeds_72_bytes_IMPORTANT_PART"
                                                                    │
                                              Bcrypt cắt ở đây ──→ ╪
                                                                    │
Bcrypt chỉ hash 72 bytes đầu tiên!

Password 1: "correct_horse_battery_staple_very_long_password_that_exceeds_72_bytes_AAAAAAA"
Password 2: "correct_horse_battery_staple_very_long_password_that_exceeds_72_bytes_BBBBBBB"

hash(pass1) === hash(pass2)  ← SAME HASH!
```

Bcrypt giới hạn 72 bytes. Password dài hơn → bytes thừa bị ignore. Hai password khác nhau sau byte 72 tạo ra hash giống nhau.

### Phát hiện

```bash
# Tìm nơi kiểm tra độ dài password
rg --type php "max.*password\|password.*max\|maxlength" -in
rg --type php "password.*validate\|validate.*password" -in

# Kiểm tra validation rules
rg --type php "'password'.*=>.*'required" -n
rg --type php "min:.*max:" -n
```

### Giải pháp

**BAD:**
```php
<?php
// ❌ Không giới hạn max length - bcrypt sẽ truncate silently
class UserController
{
    public function register(Request $request): JsonResponse
    {
        $request->validate([
            'password' => 'required|min:8|confirmed',
            // ❌ Không có max! Password 1000 chars cũng pass
        ]);

        User::create([
            'password' => Hash::make($request->password), // Bcrypt truncate tại 72 bytes!
        ]);
    }
}

// ❌ Hậu quả: user đặt password dài, sau 72 bytes là phần "nhớ được"
// Attacker biết 72 bytes đầu → crack được dù password "dài"
```

**GOOD:**
```php
<?php
// ✅ Giải pháp 1: Giới hạn max 72 bytes (bytes, không characters!)
class UserController
{
    public function register(Request $request): JsonResponse
    {
        $request->validate([
            'password' => [
                'required',
                'confirmed',
                'min:12',
                // ✅ 72 bytes max (UTF-8: một số ký tự chiếm nhiều bytes)
                // Safe limit: 72 characters (vì 1 ASCII char = 1 byte)
                // Hoặc dùng custom rule để check bytes
                new MaxBytesRule(72),
            ],
        ]);

        User::create([
            'password' => Hash::make($request->password),
        ]);
    }
}

// ✅ Custom Validation Rule kiểm tra bytes
class MaxBytesRule implements \Illuminate\Contracts\Validation\Rule
{
    public function __construct(private readonly int $maxBytes) {}

    public function passes(mixed $attribute, mixed $value): bool
    {
        return strlen($value) <= $this->maxBytes; // strlen đếm bytes, không characters
    }

    public function message(): string
    {
        return "The :attribute must not exceed {$this->maxBytes} bytes.";
    }
}

// ✅ Giải pháp 2: Pre-hash password trước khi bcrypt (cho phép password dài)
// Dùng khi muốn support passphrase rất dài
class SecurePasswordService
{
    public function hash(string $password): string
    {
        // ✅ SHA-256 trước: output luôn là 64 hex chars (< 72 bytes)
        // Base64: 44 chars, cũng < 72 bytes
        $prehashed = base64_encode(hash('sha256', $password, true));

        return password_hash($prehashed, PASSWORD_ARGON2ID);
    }

    public function verify(string $password, string $hash): bool
    {
        $prehashed = base64_encode(hash('sha256', $password, true));
        return password_verify($prehashed, $hash);
    }
}

// ✅ Giải pháp 3: Dùng Argon2id (không có truncation issue)
// Argon2id không giới hạn input length!
$hash = password_hash($password, PASSWORD_ARGON2ID, [
    'memory_cost' => 65536,
    'time_cost'   => 4,
    'threads'     => 2,
]);
```

```php
<?php
// ✅ Validation rule tái sử dụng
// app/Rules/PasswordStrength.php
class PasswordStrength implements \Illuminate\Contracts\Validation\Rule
{
    public function passes(mixed $attribute, mixed $value): bool
    {
        if (! is_string($value)) {
            return false;
        }

        // ✅ Check bytes (không characters) cho bcrypt compatibility
        if (strlen($value) > 72) {
            return false;
        }

        // Minimum requirements
        if (mb_strlen($value) < 12) {
            return false;
        }

        return true;
    }

    public function message(): string
    {
        return 'Password must be 12-72 characters (bytes) long.';
    }
}
```

### Phòng ngừa

```bash
# Tìm password validation thiếu max constraint
rg --type php "'password'.*'required\|min:[0-9]'" -n | grep -v "max:"

# Kiểm tra hash algorithm
rg --type php "PASSWORD_BCRYPT\|PASSWORD_ARGON2ID\|password_hash" -n
```

---

## Pattern 10: Constant-Time Comparison Thiếu

### Tên
Missing Constant-Time String Comparison (General)

### Phân loại
Authentication / Side-Channel

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```
So sánh thông thường dừng sớm khi tìm thấy byte khác:

"correct"  vs  "cXrect"
  c == c  → tiếp
  o != X  → return false (sau 2 bước)

"correct"  vs  "aXrect"
  c != a  → return false (sau 1 bước)

Đo thời gian: case 2 nhanh hơn case 1
→ Suy ra ký tự đầu tiên là 'c' không phải 'a'
→ Từng ký tự một, brute-force có hướng dẫn
```

Khác với Pattern 02 tập trung JWT/token, pattern này cover tất cả các loại secret comparison.

### Phát hiện

```bash
# Tìm tất cả so sánh có thể bị timing attack
rg --type php "=== \$request.*key\|=== \$request.*secret\|=== \$request.*token" -n
rg --type php "strcmp.*secret\|strcmp.*key\|strcmp.*hash" -in
rg --type php "\$_POST.*===\|\$_GET.*===" -n

# Trong middleware/auth
rg --type php "apiKey\s*===\|api_key\s*===" -in
rg --type php "secret\s*===\|hmac\s*===" -in
```

### Giải pháp

**BAD:**
```php
<?php
// ❌ Tất cả các dạng so sánh không an toàn

// Case 1: Direct comparison
if ($request->header('X-API-Key') === config('app.api_key')) { }  // WRONG

// Case 2: strcmp
if (strcmp($userToken, $storedToken) === 0) { }  // WRONG

// Case 3: strncmp
if (strncmp($signature, $expected, strlen($expected)) === 0) { }  // WRONG

// Case 4: In array check
if (in_array($token, $validTokens)) { }  // WRONG

// Case 5: Custom loop
function compare(string $a, string $b): bool {
    for ($i = 0; $i < strlen($a); $i++) {
        if ($a[$i] !== $b[$i]) return false;  // Early return!
    }
    return true;  // WRONG
}

// Case 6: Type juggling + compare
if ($token == $expected) { }  // WRONG: type coercion + timing
```

**GOOD:**
```php
<?php
// ✅ hash_equals() cho tất cả so sánh security-critical

// ✅ Case 1: API Key
class ApiKeyMiddleware
{
    public function handle(Request $request, Closure $next): Response
    {
        $provided = $request->header('X-API-Key', '');
        $expected = config('services.api.key');

        if (! hash_equals($expected, $provided)) {
            return response()->json(['error' => 'Unauthorized'], 401);
        }

        return $next($request);
    }
}

// ✅ Case 2: HMAC signature (webhook)
function verifyHmacSignature(string $payload, string $signature, string $secret): bool
{
    $computed = hash_hmac('sha256', $payload, $secret);
    // hash_equals: constant-time, cùng độ dài (hex string)
    return hash_equals($computed, $signature);
}

// ✅ Case 3: Khi so sánh string khác độ dài
function secureEquals(string $known, string $provided): bool
{
    // Hash cả hai để chuẩn hóa độ dài, rồi mới so sánh
    return hash_equals(
        hash('sha256', $known),
        hash('sha256', $provided)
    );
}

// ✅ Case 4: Webhook secret (Stripe, GitHub, etc.)
class WebhookVerifier
{
    public function verifyGitHub(Request $request): bool
    {
        $secret    = config('services.github.webhook_secret');
        $signature = $request->header('X-Hub-Signature-256', '');
        $computed  = 'sha256=' . hash_hmac('sha256', $request->getContent(), $secret);

        return hash_equals($computed, $signature);
    }

    public function verifyStripe(Request $request): bool
    {
        $secret    = config('services.stripe.webhook_secret');
        $payload   = $request->getContent();
        $sigHeader = $request->header('Stripe-Signature', '');

        // Parse timestamp và signature từ header
        preg_match('/t=(\d+)/', $sigHeader, $tMatch);
        preg_match('/v1=([a-f0-9]+)/', $sigHeader, $vMatch);

        if (empty($tMatch[1]) || empty($vMatch[1])) {
            return false;
        }

        $timestamp = $tMatch[1];
        $expected  = hash_hmac('sha256', "{$timestamp}.{$payload}", $secret);

        return hash_equals($expected, $vMatch[1]);
    }
}

// ✅ Utility trait cho mọi class cần secure comparison
trait SecureComparison
{
    protected function secureEquals(string $known, string $provided): bool
    {
        return hash_equals(hash('sha256', $known), hash('sha256', $provided));
    }

    protected function verifyHmac(string $data, string $signature, string $secret): bool
    {
        $expected = hash_hmac('sha256', $data, $secret);
        return hash_equals($expected, $signature);
    }
}
```

### Phòng ngừa

```bash
# Audit script: tìm tất cả string comparison trong auth files
rg --type php "(===|strcmp|strncmp)" app/Http/Middleware/ -n
rg --type php "(===|strcmp|strncmp)" app/Services/Auth/ -n

# Đảm bảo dùng hash_equals
rg --type php "hash_equals" --stats
```

---

## Pattern 11: Privilege Escalation Qua Role Check

### Tên
Privilege Escalation via Broken Role Check

### Phân loại
Authorization / Access Control

### Mức nghiêm trọng
CRITICAL 🔴

### Vấn đề

```
User thường gửi request:
POST /api/users/profile
{"name": "John", "role": "admin"}  ← Mass assignment!
          │
          ▼
┌─────────────────────────────┐
│  $user->fill($request->all()) │  ← role bị update!
│  $user->save()               │
└─────────────────────────────┘
          │
          ▼
  User bình thường → Admin
  Toàn quyền hệ thống

Hoặc:
  Role check dễ bypass:
  if ($user->role == 'admin') { }  ← type juggling
  if ($user->isAdmin) { }          ← truthy check
  if ($user->role) { }             ← bất kỳ role nào đều pass!
```

### Phát hiện

```bash
# Tìm mass assignment với role
rg --type php "fill\s*\(\$request\|update\s*\(\$request->all" -n
rg --type php "role.*request\|request.*role" -in

# Tìm role check yếu
rg --type php "->role\s*==\|->role\s*===" -n
rg --type php "isAdmin\s*=\s*true\|is_admin\s*=\s*1" -in

# Tìm $fillable thiếu protection
rg --type php "fillable\s*=" -n
rg --type php "guarded\s*=\s*\[\s*\]" -n  # Không guard gì cả!
```

### Giải pháp

**BAD:**
```php
<?php
// ❌ Mass assignment không bảo vệ
class User extends Model
{
    // ❌ Không có $fillable → mọi field đều fillable
    // protected $fillable = [];

    // ❌ Hoặc guard không có gì
    protected $guarded = []; // CRITICAL: tất cả fields đều fillable!
}

class UserController
{
    // ❌ fill() với toàn bộ request data
    public function update(Request $request, int $id): JsonResponse
    {
        $user = User::findOrFail($id);
        $user->fill($request->all()); // CRITICAL: role, is_admin, etc. đều bị update!
        $user->save();
        return response()->json($user);
    }
}

// ❌ Role check yếu
class AdminMiddleware
{
    public function handle(Request $request, Closure $next): Response
    {
        $user = Auth::user();

        // ❌ Type juggling: '0' == false, 'admin' == true (gần như mọi truthy string)
        if ($user->role == 'admin') { return $next($request); }

        // ❌ Chỉ check field tồn tại, không check value
        if ($user->is_admin) { return $next($request); }

        // ❌ Check role string không case-sensitive
        if (strtolower($user->role) === 'admin') { return $next($request); }

        return response()->json(['error' => 'Forbidden'], 403);
    }
}

// ❌ Authorize bằng request parameter
public function delete(Request $request): JsonResponse
{
    // ❌ Attacker gửi ?admin=1 hoặc ?role=admin
    if ($request->query('admin') || Auth::user()->role === 'admin') {
        User::destroy($request->id);
    }
}
```

**GOOD:**
```php
<?php
// ✅ Model với $fillable explicit
class User extends Model
{
    // ✅ Chỉ cho phép fill các field an toàn
    protected $fillable = [
        'name',
        'email',
        'phone',
        'avatar',
        // ❌ KHÔNG có 'role', 'is_admin', 'permissions'
    ];

    // ✅ Các field nhạy cảm phải được set trực tiếp bởi service
    // $user->role = 'admin'; // Phải explicit, không qua mass assignment
}

// ✅ Controller với explicit field selection
class UserController
{
    public function update(Request $request, int $id): JsonResponse
    {
        $this->authorize('update', User::findOrFail($id)); // ✅ Gate check

        $validated = $request->validate([
            'name'   => 'sometimes|string|max:255',
            'email'  => 'sometimes|email|unique:users,email,' . $id,
            'phone'  => 'sometimes|string|max:20',
            // ❌ KHÔNG validate/accept 'role', 'is_admin'
        ]);

        // ✅ Chỉ update fields đã validate (không phải all())
        $user = User::findOrFail($id);
        $user->update($validated);

        return response()->json($user->only(['id', 'name', 'email', 'phone']));
    }

    // ✅ Admin-only action với gate
    public function promoteToAdmin(Request $request, int $userId): JsonResponse
    {
        // ✅ Gate kiểm tra quyền thực hiện action này
        $this->authorize('manage-roles', User::class);

        $user = User::findOrFail($userId);
        $user->role = 'admin'; // ✅ Explicit assignment, không qua fillable
        $user->save();

        return response()->json(['message' => 'User promoted to admin']);
    }
}

// ✅ Role check mạnh với Enum
enum UserRole: string
{
    case User  = 'user';
    case Admin = 'admin';
    case Staff = 'staff';
}

class AdminMiddleware
{
    public function handle(Request $request, Closure $next): Response
    {
        $user = Auth::user();

        if (! $user) {
            return response()->json(['error' => 'Unauthenticated'], 401);
        }

        // ✅ Strict comparison với Enum
        $role = UserRole::tryFrom($user->role);
        if ($role !== UserRole::Admin) {
            return response()->json(['error' => 'Forbidden'], 403);
        }

        return $next($request);
    }
}

// ✅ Laravel Policy - authorize theo object, không theo role string
class PostPolicy
{
    public function delete(User $user, Post $post): bool
    {
        // ✅ Owner hoặc Admin mới được xóa
        return $user->id === $post->user_id
            || UserRole::tryFrom($user->role) === UserRole::Admin;
    }
}

// ✅ Laravel Gate
Gate::define('manage-roles', function (User $user) {
    return UserRole::tryFrom($user->role) === UserRole::Admin;
});

// ✅ Spatie Permission (recommended package)
// $user->assignRole('admin');
// $user->can('edit articles');
// Route::middleware(['role:admin'])
```

### Phòng ngừa

```bash
# Tìm mass assignment vulnerability
rg --type php "guarded\s*=\s*\[\s*\]" -n  # Empty guard = tất cả fillable!
rg --type php "->fill\s*\(\$request\b" -n
rg --type php "->update\s*\(\$request->all\b" -n

# Audit fillable/guarded
rg --type php "fillable\|guarded" app/Models/ -rn
```

```xml
<!-- PHPStan: Larastan detect mass assignment issues -->
includes:
    - vendor/nunomaduro/larastan/extension.neon
parameters:
    checkModelProperties: true
```

---

## Pattern 12: API Key Trong URL

### Tên
API Key Exposed in URL / Query String

### Phân loại
Authentication / Information Disclosure

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```
GET /api/data?api_key=sk-prod-12345secretkey HTTP/1.1
                  │
         Bị lưu vào nhiều nơi:
                  │
         ├── Server access logs
         ├── Browser history
         ├── Proxy logs (CDN, WAF)
         ├── Referrer header khi redirect
         ├── Web server logs của 3rd party
         └── Shared URL (user copy-paste link)

  Tất cả nơi này không được mã hóa
  → API key bị lộ toàn bộ!
```

### Phát hiện

```bash
# Tìm API key/token trong query string
rg --type php "api.?key.*query\|query.*api.?key" -in
rg --type php "request()->query.*token\|request()->get.*key" -in
rg --type php "\$_GET\[.*key.*\]|\$_GET\[.*token.*\]" -in

# Tìm routes nhận key qua GET
rg "Route::get.*api_key\|Route::get.*token" routes/ -rn

# Tìm trong HTTP client calls
rg --type php "->withQueryParameters.*key\|->withQueryParameters.*token" -in
rg --type php "http_build_query.*api_key\|http_build_query.*secret" -in
```

### Giải pháp

**BAD:**
```php
<?php
// ❌ API key trong URL/query string
// routes/api.php
Route::get('/data', function (Request $request) {
    $apiKey = $request->query('api_key'); // ❌ Từ URL!
    $token  = $request->get('token');     // ❌ Từ URL!
    // ...
});

// ❌ HTTP Client gửi secret qua URL
class ExternalApiService
{
    public function fetchData(): array
    {
        $response = Http::get('https://api.example.com/data', [
            'api_key' => config('services.example.key'), // ❌ Sẽ là URL query param!
            'secret'  => config('services.example.secret'),
        ]);

        return $response->json();
    }
}

// ❌ Trong codebase có hardcoded API key
$client = new Client(['base_uri' => 'https://api.example.com']);
$response = $client->get('/data?api_key=sk-prod-XXXXXXXX'); // ❌ Hardcoded!

// ❌ Generate URL với token
$url = route('protected.resource') . '?token=' . $user->api_token;
// Gửi URL này qua email → token bị lộ trong email logs!
```

**GOOD:**
```php
<?php
// ✅ API key trong Authorization header
class ExternalApiService
{
    public function fetchData(): array
    {
        // ✅ API key trong header, không trong URL
        $response = Http::withHeaders([
            'Authorization' => 'Bearer ' . config('services.example.api_key'),
            'X-API-Key'     => config('services.example.secret'), // Hoặc custom header
        ])->get('https://api.example.com/data'); // URL sạch, không có secret

        if ($response->failed()) {
            throw new \RuntimeException('External API request failed: ' . $response->status());
        }

        return $response->json();
    }
}

// ✅ Middleware nhận API key từ header
class ApiKeyMiddleware
{
    public function handle(Request $request, Closure $next): Response
    {
        // ✅ Đọc từ header (Bearer token hoặc custom header)
        $apiKey = $request->bearerToken()
               ?? $request->header('X-API-Key');

        if (! $apiKey) {
            return response()->json(['error' => 'API key required'], 401);
        }

        $storedKey = config('app.api_key');
        if (! hash_equals($storedKey, $apiKey)) { // ✅ Constant-time compare
            return response()->json(['error' => 'Invalid API key'], 401);
        }

        return $next($request);
    }
}

// ✅ Routes nhận auth từ header
Route::middleware(['api.key'])->group(function () {
    Route::get('/data', [DataController::class, 'index']);
});

// ✅ Nếu PHẢI dùng URL token (download links, email links)
// Dùng Signed URL với expiry - KHÔNG phải API key!
class DownloadController
{
    public function generateDownloadLink(int $fileId): JsonResponse
    {
        // ✅ Signed URL: có chữ ký, có expiry, không lộ secret
        $url = URL::temporarySignedRoute(
            'files.download',
            now()->addMinutes(15), // ✅ Expire sau 15 phút
            ['file' => $fileId]
        );

        return response()->json(['download_url' => $url]);
    }

    public function download(Request $request, int $fileId): Response
    {
        // ✅ Verify signature (Laravel tự xử lý)
        if (! $request->hasValidSignature()) {
            abort(403, 'Invalid or expired download link');
        }

        return Storage::download("files/{$fileId}");
    }
}

// ✅ Webhook callback URL - dùng secret trong header, không trong URL
class WebhookController
{
    public function handle(Request $request): Response
    {
        // ✅ Secret trong header X-Webhook-Secret, không trong URL
        $secret = $request->header('X-Webhook-Secret', '');
        if (! hash_equals(config('webhook.secret'), $secret)) {
            abort(403);
        }

        return $this->processWebhook($request->all());
    }
}
```

```bash
# ✅ Audit logs để phát hiện API key đã bị lộ
grep -r "api_key=" storage/logs/
grep -r "token=" storage/logs/
# Nếu tìm thấy → rotate key ngay lập tức!
```

### Phòng ngừa

```bash
# Audit: tìm API key trong URL patterns
rg --type php "request()->query\|request()->get\|\$_GET" -n | grep -i "key\|token\|secret"

# Kiểm tra không có secret trong query string
rg --type php "http_build_query\|withQueryParameters" -n | grep -i "key\|token\|secret"

# Tìm hardcoded credential trong code
rg --type php "api_key\s*=\s*['\"][a-zA-Z0-9_\-]{10,}" -n
rg --type php "secret\s*=\s*['\"][a-zA-Z0-9_\-]{10,}" -n
```

```ini
# .gitignore - đảm bảo không commit .env
.env
.env.*
!.env.example
```

```bash
# git-secrets hoặc gitleaks để prevent commit credential
# Cài đặt pre-commit hook:
# .git/hooks/pre-commit
# gitleaks detect --source . --verbose
```

---

## Tổng Kết Domain 03

| # | Pattern | Mức độ | Phát hiện nhanh |
|---|---------|--------|-----------------|
| 01 | MD5/SHA1 Password | CRITICAL | `rg "md5\|sha1" --type php` |
| 02 | Timing Attack Compare | HIGH | `rg "===.*token\|strcmp" --type php` |
| 03 | JWT Secret Weak | CRITICAL | `rg "JWT_SECRET\|'secret'" --type php` |
| 04 | Remember-Me Predictable | HIGH | `rg "uniqid\|mt_rand.*remember" --type php` |
| 05 | Rate Limiting Thiếu | HIGH | `rg "Route::post.*login" routes/` |
| 06 | 2FA Bypass | CRITICAL | `rg "2fa\|two.factor" --type php` |
| 07 | Password Reset Token Reuse | HIGH | `rg "password_resets\|reset.*token" --type php` |
| 08 | OAuth State Thiếu | HIGH | `rg "stateless\(\)" --type php` |
| 09 | Bcrypt 72-byte Truncation | HIGH | `rg "PASSWORD_BCRYPT\|max.*password" --type php` |
| 10 | Constant-Time Compare Thiếu | HIGH | `rg "===.*secret\|strcmp.*key" --type php` |
| 11 | Privilege Escalation Role | CRITICAL | `rg "guarded.*\[\]" --type php` |
| 12 | API Key Trong URL | HIGH | `rg "query.*api_key\|_GET.*key" --type php` |

### Audit Script Nhanh

```bash
#!/usr/bin/env bash
# audit-auth-security.sh
echo "=== Domain 03: Authentication Security Audit ==="

echo "[CRITICAL] MD5/SHA1 password hashing:"
rg --type php "(md5|sha1)\s*\(" -n --color=always

echo "[CRITICAL] JWT weak config:"
rg --type php "jwt.*secret\s*=\s*['\"][^'\"]{1,20}['\"]" -in --color=always

echo "[CRITICAL] Mass assignment (empty guard):"
rg --type php "guarded\s*=\s*\[\s*\]" -n --color=always

echo "[CRITICAL] 2FA session flag (possible bypass):"
rg --type php "session.*2fa.*=.*true\|2fa.*verified.*session" -in --color=always

echo "[HIGH] Non-constant-time compare:"
rg --type php "===\s*\\\$.*token\|===\s*\\\$.*secret\|strcmp.*key" -n --color=always

echo "[HIGH] Missing rate limit on login:"
rg "Route::post.*login" routes/ -rn --color=always

echo "[HIGH] OAuth stateless (bypasses state check):"
rg --type php "->stateless()" -n --color=always

echo "[HIGH] API key in URL:"
rg --type php "request\(\)->query|request\(\)->get|\\\$_GET" -n | grep -i "key\|token\|secret"

echo "=== Audit Complete ==="
```
