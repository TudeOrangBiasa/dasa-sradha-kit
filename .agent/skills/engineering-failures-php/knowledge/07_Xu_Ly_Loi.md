# Domain 07: Xử Lý Lỗi (Error Handling)

> PHP/Laravel patterns liên quan đến error handling: exceptions, @ suppression, error reporting, shutdown functions.

---

## Pattern 01: @ Error Suppression

### Tên
@ Error Suppression (Dùng @ Để Ẩn Lỗi)

### Phân loại
Error Handling / Suppression / Silent

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```php
$data = @file_get_contents($url);  ← @ suppresses ALL errors
// Network timeout? Silenced
// File not found? Silenced
// Permission denied? Silenced
// $data = false but you don't know WHY
```

### Phát hiện

```bash
rg --type php "@\w+\(" -n
rg --type php "@file_|@unlink|@mkdir|@fopen|@json_decode" -n
```

### Giải pháp

❌ **BAD**
```php
$json = @file_get_contents('config.json');
$data = @json_decode($json, true);
```

✅ **GOOD**
```php
$json = file_get_contents('config.json');
if ($json === false) {
    throw new ConfigException("Cannot read config.json: " . error_get_last()['message']);
}
$data = json_decode($json, true, 512, JSON_THROW_ON_ERROR);
```

### Phòng ngừa
- [ ] NEVER use @ operator
- [ ] Check return values explicitly
- [ ] `JSON_THROW_ON_ERROR` cho json_decode/encode
- Tool: PHPStan rule `disallowedConstructs`

---

## Pattern 02: Pokemon Exception Handling

### Tên
Pokemon Exception Handling (Catch All, Handle None)

### Phân loại
Error Handling / Exception / Swallowing

### Mức nghiêm trọng
CRITICAL 🔴

### Vấn đề

```php
try {
    $result = $this->processPayment($order);
} catch (\Exception $e) {
    // Gotta catch 'em all!
    // Empty catch block — error swallowed completely
}
// Or:
} catch (\Throwable $t) {
    return null;  ← Silently returns null
}
```

### Phát hiện

```bash
rg --type php "catch\s*\(.*Exception.*\)\s*\{" -A 2 | rg "^\s*\}"
rg --type php "catch\s*\(.*Throwable" -n
rg --type php "catch\s*\(\\\\Exception" -n
```

### Giải pháp

❌ **BAD**
```php
try { $user = $api->getUser($id); }
catch (\Exception $e) { }  // Swallowed!

try { $this->save($data); }
catch (\Exception $e) { return false; }  // Which exception? Why?
```

✅ **GOOD**
```php
try {
    $user = $api->getUser($id);
} catch (ApiConnectionException $e) {
    Log::error('API connection failed', ['error' => $e->getMessage()]);
    throw new ServiceUnavailableException('User service down', 0, $e);
} catch (UserNotFoundException $e) {
    return null; // Expected: user not found is valid response
} catch (\Exception $e) {
    report($e); // Log unexpected errors
    throw $e;   // Re-throw
}
```

### Phòng ngừa
- [ ] Catch specific exceptions, not \Exception
- [ ] NEVER empty catch blocks
- [ ] Log or report unexpected exceptions
- [ ] Re-throw if can't handle properly

---

## Pattern 03: error_reporting Off Production

### Tên
error_reporting Off (Error Reporting Disabled)

### Phân loại
Error Handling / Configuration / Visibility

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```php
// php.ini hoặc runtime:
error_reporting(0);           ← ALL errors hidden
ini_set('display_errors', 0); ← Errors not shown (OK for prod)
ini_set('log_errors', 0);     ← Errors NOT LOGGED (BAD!)
```

### Phát hiện

```bash
rg --type php "error_reporting\(0\)" -n
rg --type php "ini_set.*log_errors.*0" -n
rg --type php "ini_set.*display_errors" -n
```

### Giải pháp

❌ **BAD**
```php
error_reporting(0);
ini_set('log_errors', '0');
```

✅ **GOOD** (.env)
```ini
# Production:
APP_DEBUG=false          # display_errors off
LOG_LEVEL=error          # Log errors and above

# php.ini:
display_errors = Off     # Don't show to users
log_errors = On          # ALWAYS log
error_reporting = E_ALL  # Report everything
error_log = /var/log/php/error.log
```

### Phòng ngừa
- [ ] `display_errors = Off` in production (security)
- [ ] `log_errors = On` ALWAYS (visibility)
- [ ] `error_reporting = E_ALL` (catch everything)
- [ ] Laravel: `APP_DEBUG=false` in production

---

## Pattern 04: Exception Handler Thiếu

### Tên
Exception Handler Thiếu (Missing Global Exception Handler)

### Phân loại
Error Handling / Global / Framework

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```
Unhandled exception → PHP default: white page + stack trace
→ Security: leaks internal paths, DB credentials
→ UX: user sees ugly error page
→ Monitoring: no alert, no tracking
```

### Phát hiện

```bash
rg --type php "set_exception_handler|set_error_handler" -n
rg --type php "class\s+Handler\s+extends\s+ExceptionHandler" -n
rg --type php "reportable|renderable" -n --glob "*Handler*"
```

### Giải pháp

✅ **GOOD**: Laravel Exception Handler
```php
// app/Exceptions/Handler.php
class Handler extends ExceptionHandler
{
    protected $dontReport = [
        AuthenticationException::class,
        ValidationException::class,
    ];

    public function register(): void
    {
        $this->reportable(function (PaymentException $e) {
            // Alert payment team
            Notification::route('slack', config('slack.payments'))
                ->notify(new PaymentFailedNotification($e));
        });

        $this->renderable(function (ApiException $e, Request $request) {
            if ($request->expectsJson()) {
                return response()->json([
                    'error' => $e->getUserMessage(),
                    'code' => $e->getErrorCode(),
                ], $e->getStatusCode());
            }
        });
    }
}
```

### Phòng ngừa
- [ ] Custom exception handler cho ALL applications
- [ ] Don't leak internal info to users
- [ ] Report to monitoring (Sentry, Bugsnag)
- [ ] Custom error pages (404, 500)

---

## Pattern 05: Custom Exception Hierarchy Thiếu

### Tên
Custom Exception Hierarchy Thiếu (Missing Exception Hierarchy)

### Phân loại
Error Handling / Exception / Organization

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```php
throw new \Exception('User not found');     ← Generic
throw new \RuntimeException('DB error');    ← Generic
throw new \InvalidArgumentException('Bad'); ← Wrong use

// All are PHP built-in exceptions
// Cannot catch by domain: payment, user, order
// Cannot differentiate: retryable vs non-retryable
```

### Phát hiện

```bash
rg --type php "throw new \\\\(Exception|RuntimeException|InvalidArgumentException)" -n
rg --type php "throw new \\\\" -n
rg --type php "class\s+\w+Exception\s+extends" -n  # Custom exceptions
```

### Giải pháp

❌ **BAD**
```php
throw new \Exception('Payment failed: card declined');
throw new \Exception('User not found');
```

✅ **GOOD**
```php
// Base exception per domain
abstract class DomainException extends \RuntimeException {}

// Specific exceptions
class PaymentDeclinedException extends DomainException
{
    public function __construct(
        public readonly string $cardLast4,
        public readonly string $declineCode,
        ?\Throwable $previous = null,
    ) {
        parent::__construct(
            "Payment declined for card ending {$cardLast4}: {$declineCode}",
            0,
            $previous,
        );
    }
}

class UserNotFoundException extends DomainException
{
    public function __construct(public readonly int|string $userId)
    {
        parent::__construct("User {$userId} not found");
    }
}

// Usage:
try { $this->charge($card); }
catch (PaymentDeclinedException $e) {
    Log::warning('Payment declined', [
        'card' => $e->cardLast4,
        'code' => $e->declineCode,
    ]);
    return back()->with('error', 'Card declined. Please try another.');
}
```

### Phòng ngừa
- [ ] Custom exception per domain/feature
- [ ] Carry context data as public properties
- [ ] Hierarchy: base → domain → specific
- [ ] `$previous` parameter cho error chain

---

## Pattern 06: Display_errors On Production

### Tên
Display_errors On Production (Error Details Shown To Users)

### Phân loại
Error Handling / Security / Information Leak

### Mức nghiêm trọng
CRITICAL 🔴

### Vấn đề

```
APP_DEBUG=true in production!
→ Stack traces shown to users
→ Database credentials in error messages
→ File paths exposed
→ PHP version, framework version visible
```

### Phát hiện

```bash
rg "APP_DEBUG=true" -n --glob ".env*"
rg --type php "dd\(|dump\(|var_dump\(" -n --glob "!*test*"
rg --type php "display_errors.*On|display_errors.*1" -n
```

### Giải pháp

❌ **BAD**
```ini
APP_DEBUG=true    # In production .env
```

✅ **GOOD**
```ini
# .env.production
APP_DEBUG=false
LOG_CHANNEL=stack
LOG_LEVEL=error
```

```php
// Remove ALL debug statements before deploy
// dd(), dump(), var_dump() → NEVER in production code
```

### Phòng ngừa
- [ ] `APP_DEBUG=false` in production
- [ ] CI: fail if dd()/dump() found in code
- [ ] Custom error pages for 4xx, 5xx
- Tool: PHPStan — ban dd(), dump()

---

## Pattern 07: Shutdown Function Thiếu

### Tên
Shutdown Function Thiếu (Missing Shutdown Handler)

### Phân loại
Error Handling / Fatal / Recovery

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```
Fatal errors (E_ERROR, segfault) CANNOT be caught by try/catch
→ Script dies without cleanup
→ No logging of what happened
→ User sees blank page

register_shutdown_function() runs even after fatal errors
```

### Phát hiện

```bash
rg --type php "register_shutdown_function" -n
rg --type php "error_get_last" -n
```

### Giải pháp

✅ **GOOD**
```php
register_shutdown_function(function () {
    $error = error_get_last();
    if ($error !== null && in_array($error['type'], [E_ERROR, E_CORE_ERROR, E_COMPILE_ERROR])) {
        Log::critical('Fatal error', [
            'message' => $error['message'],
            'file' => $error['file'],
            'line' => $error['line'],
        ]);

        if (!headers_sent()) {
            http_response_code(500);
            echo view('errors.500')->render();
        }
    }
});
```

Note: Laravel handles this automatically via its exception handler.

### Phòng ngừa
- [ ] register_shutdown_function cho non-framework apps
- [ ] Laravel: ExceptionHandler covers this
- [ ] Log fatal errors for post-mortem

---

## Pattern 08: Exception Message Leak Sensitive Info

### Tên
Exception Message Leak (Sensitive Data In Error Messages)

### Phân loại
Error Handling / Security / Data Leak

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```php
throw new \Exception("Login failed for user {$email} with password {$password}");
                                             ^^^^^^^               ^^^^^^^^^^
throw new \Exception("DB error: " . $e->getMessage());
// DB message may contain: table names, query, connection string
```

### Phát hiện

```bash
rg --type php "throw.*password|throw.*secret|throw.*token|throw.*api_key" -n
rg --type php "throw.*\\\$.*getMessage\(\)" -n
rg --type php "Exception\(.*\\\$" -n
```

### Giải pháp

❌ **BAD**
```php
throw new AuthException("Failed to login {$email}: {$e->getMessage()}");
```

✅ **GOOD**
```php
Log::error('Login failed', [
    'email' => $email,
    'error' => $e->getMessage(),
    // password NEVER logged
]);

throw new AuthException(
    'Invalid credentials',  // Safe user message
    previous: $e,           // Full error in chain (for logs, not users)
);
```

### Phòng ngừa
- [ ] User-facing messages: generic, no internal details
- [ ] Log detailed errors with context
- [ ] NEVER include: passwords, tokens, API keys in exceptions
- [ ] `$previous` parameter preserves chain for logging

---

## Pattern 09: Throwable vs Exception Confusion

### Tên
Throwable vs Exception Confusion

### Phân loại
Error Handling / PHP / Type Hierarchy

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```
PHP Error Hierarchy:
  Throwable
  ├── Error (PHP internal errors — shouldn't catch usually)
  │   ├── TypeError
  │   ├── ValueError
  │   ├── ArithmeticError
  │   └── ...
  └── Exception (Application errors — catch these)
      ├── RuntimeException
      ├── LogicException
      └── ...

catch (Exception $e) — misses Error subclasses
catch (Throwable $t) — catches EVERYTHING including PHP bugs
```

### Phát hiện

```bash
rg --type php "catch\s*\(\\\\?Throwable" -n
rg --type php "catch\s*\(\\\\?Error\b" -n
rg --type php "catch\s*\(\\\\?Exception" -n
```

### Giải pháp

❌ **BAD**: Catch Throwable everywhere
```php
try { process(); }
catch (\Throwable $t) { return null; }
// Catches TypeError from bugs → hides programmer errors
```

✅ **GOOD**: Catch specific, let bugs crash
```php
try {
    $result = $this->processPayment($order);
} catch (PaymentDeclinedException $e) {
    return $this->handleDecline($e);
} catch (GatewayTimeoutException $e) {
    return $this->retry($order);
}
// TypeError, ValueError → NOT caught → bug surfaces in logs
```

### Phòng ngừa
- [ ] Catch \Exception subclasses, not \Throwable
- [ ] \Throwable chỉ ở global handler level
- [ ] Let \Error propagate (they indicate bugs)

---

## Pattern 10: Error Log Flood

### Tên
Error Log Flood (Quá Nhiều Log Gây Noise)

### Phân loại
Error Handling / Logging / Volume

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```php
// Trong loop:
foreach ($users as $user) {
    try { $this->sync($user); }
    catch (\Exception $e) {
        Log::error('Sync failed', ['user' => $user->id, 'error' => $e->getMessage()]);
        // 10,000 users × same error = 10,000 log entries
        // Log storage full, real errors buried
    }
}
```

### Phát hiện

```bash
rg --type php "Log::(error|warning)" -n | rg "(foreach|for|while)" -B 3
rg --type php "Log::error\(" -c | sort -t: -k2 -rn
```

### Giải pháp

❌ **BAD**
```php
foreach ($items as $item) {
    try { process($item); }
    catch (\Exception $e) {
        Log::error("Failed: {$e->getMessage()}"); // N log entries
    }
}
```

✅ **GOOD**
```php
$errors = [];
foreach ($items as $item) {
    try { process($item); }
    catch (\Exception $e) {
        $errors[] = ['item' => $item->id, 'error' => $e->getMessage()];
    }
}

if (!empty($errors)) {
    Log::error('Batch processing failures', [
        'total' => count($items),
        'failed' => count($errors),
        'sample_errors' => array_slice($errors, 0, 5), // First 5 only
    ]);
}
```

### Phòng ngừa
- [ ] Aggregate errors in batch operations
- [ ] Log summary, not individual errors
- [ ] Rate limiting for repeated errors
- Tool: Sentry — auto-groups similar errors
