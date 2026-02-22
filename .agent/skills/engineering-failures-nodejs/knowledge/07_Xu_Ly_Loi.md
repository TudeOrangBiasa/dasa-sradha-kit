# Domain 07: Xử Lý Lỗi (Error Handling)

> Node.js/TypeScript patterns liên quan đến error handling: exceptions, async errors, process crashes, error classes.

---

## Pattern 01: Unhandled Exception Crash

### Tên
Unhandled Exception Crash (Uncaught Exception Gây Process Exit)

### Phân loại
Error Handling / Process / Crash

### Mức nghiêm trọng
CRITICAL 🔴

### Vấn đề

```
Uncaught exception hoặc unhandled rejection → process exit
→ Tất cả requests đang xử lý bị mất
→ Không có graceful shutdown
→ Data corruption nếu đang write

Request 1 ──processing──╳ LOST
Request 2 ──processing──╳ LOST
                         │
          uncaughtException → process.exit(1)
```

### Phát hiện

```bash
rg --type ts --type js "process\.on\(.(uncaughtException|unhandledRejection)" -n
rg --type ts --type js "process\.exit" -n
```

### Giải pháp

❌ **BAD**
```typescript
// No handler at all — process crashes on any unhandled error
// Or:
process.on('uncaughtException', (err) => {
  console.log(err); // Log and continue ← DANGEROUS: state may be corrupted
});
```

✅ **GOOD**
```typescript
process.on('uncaughtException', (err, origin) => {
  logger.fatal({ err, origin }, 'Uncaught exception — shutting down');
  // Graceful shutdown
  server.close(() => {
    process.exit(1); // MUST exit — state may be corrupted
  });
  // Force exit after timeout
  setTimeout(() => process.exit(1), 5000).unref();
});

process.on('unhandledRejection', (reason, promise) => {
  logger.error({ reason }, 'Unhandled rejection');
  // In Node 15+, unhandledRejection crashes by default
  // Handle gracefully
  throw reason; // Convert to uncaughtException for unified handling
});
```

### Phòng ngừa
- [ ] ALWAYS register `uncaughtException` + `unhandledRejection` handlers
- [ ] NEVER continue after `uncaughtException` — state is corrupted
- [ ] Graceful shutdown: close server, flush logs, then `process.exit(1)`
- Tool: ESLint `no-process-exit` (use only in handlers)

---

## Pattern 02: Error Swallowing

### Tên
Error Swallowing (Nuốt Lỗi — Empty Catch Block)

### Phân loại
Error Handling / Exception / Swallowing

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```typescript
try {
  await saveToDatabase(data);
} catch (e) {
  // Empty catch — error completely swallowed
}
// Data not saved but code continues as if success
```

### Phát hiện

```bash
rg --type ts --type js "catch\s*\(.*\)\s*\{\s*\}" -n
rg --type ts --type js "\.catch\(\s*\(\)\s*=>\s*\{\s*\}\s*\)" -n
rg --type ts --type js "\.catch\(\s*\(\)\s*=>\s*null\)" -n
```

### Giải pháp

❌ **BAD**
```typescript
try { await sendEmail(user); } catch (e) { }

promise.catch(() => {}); // Silenced
```

✅ **GOOD**
```typescript
try {
  await sendEmail(user);
} catch (error) {
  logger.error({ error, userId: user.id }, 'Failed to send email');
  // Decide: retry, fallback, or rethrow
  throw new EmailDeliveryError('Email send failed', { cause: error });
}

// Or if error is truly ignorable, document why:
try {
  await cacheResult(key, value);
} catch (error) {
  // Cache failure is non-critical — request still served from DB
  logger.warn({ error }, 'Cache write failed');
}
```

### Phòng ngừa
- [ ] NEVER empty catch blocks
- [ ] Always log or handle errors
- [ ] Document why if intentionally ignoring
- Tool: ESLint `no-empty` rule

---

## Pattern 03: Error Type Unknown

### Tên
Error Type Unknown (Kiểu Error Unknown Trong Catch)

### Phân loại
Error Handling / TypeScript / Type Safety

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```typescript
// TypeScript strict: catch(e) → e is `unknown`
try {
  await fetch(url);
} catch (e) {
  console.log(e.message); // TS error: 'e' is of type 'unknown'
  // Many devs cast to `any` to silence this
}
```

### Phát hiện

```bash
rg --type ts "catch\s*\(\s*\w+\s*:\s*any\s*\)" -n
rg --type ts "catch\s*\(\s*\w+\s*\)\s*\{" -A 1 -n
rg --type ts "as\s+Error" -n
```

### Giải pháp

❌ **BAD**
```typescript
catch (e: any) {
  console.log(e.message); // Unsafe — e might not have .message
}
// Or:
catch (e) {
  console.log((e as Error).message); // Unsafe assertion
}
```

✅ **GOOD**
```typescript
catch (error) {
  if (error instanceof AppError) {
    logger.error({ code: error.code }, error.message);
  } else if (error instanceof Error) {
    logger.error({ error }, error.message);
  } else {
    logger.error({ error: String(error) }, 'Unknown error type');
  }
}

// Helper function:
function getErrorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  return String(error);
}
```

### Phòng ngừa
- [ ] Enable `useUnknownInCatchVariables` in tsconfig
- [ ] Use `instanceof` checks, not type assertions
- [ ] Helper function for safe error message extraction
- Tool: TypeScript strict mode

---

## Pattern 04: Async Error Context Lost

### Tên
Async Error Context Lost (Mất Context Trong Async Chain)

### Phân loại
Error Handling / Async / Stack Trace

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```
Async stack trace mất context qua event loop boundaries:

Error: Connection refused
    at Socket.connect (net.js:123)
    at processTicksAndRejections (internal/process/task_queues.js:95)
    ← WHERE was this called from? No business context!
```

### Phát hiện

```bash
rg --type ts --type js "new Error\(" -n | rg -v "cause"
rg --type ts --type js "throw new Error" -n
rg --type ts --type js "\.catch\(.*throw" -n
```

### Giải pháp

❌ **BAD**
```typescript
async function getUser(id: string) {
  const response = await fetch(`/api/users/${id}`);
  if (!response.ok) {
    throw new Error('Request failed'); // No context: which request? what status?
  }
}
```

✅ **GOOD**
```typescript
async function getUser(id: string) {
  try {
    const response = await fetch(`/api/users/${id}`);
    if (!response.ok) {
      throw new HttpError(`Failed to fetch user ${id}`, {
        statusCode: response.status,
        url: `/api/users/${id}`,
      });
    }
    return await response.json();
  } catch (error) {
    throw new UserServiceError(`getUser(${id}) failed`, { cause: error });
    // ES2022 Error.cause preserves original error + adds context
  }
}
```

### Phòng ngừa
- [ ] Use `Error.cause` (ES2022) to chain errors
- [ ] Add business context when re-throwing
- [ ] Enable `--enable-source-maps` in production for async traces
- Tool: `@nodejs/diagnostics` for async stack traces

---

## Pattern 05: Error Class Thiếu

### Tên
Error Class Thiếu (Throw String/Object Thay Vì Error Instance)

### Phân loại
Error Handling / Exception / Type

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```typescript
throw 'Something went wrong';     // ← string, no stack trace!
throw { code: 404 };              // ← plain object, no stack trace!
throw 42;                         // ← number, no stack trace!
// None of these have .stack property
// Cannot use instanceof for type checking
```

### Phát hiện

```bash
rg --type ts --type js "throw\s+['\"]" -n
rg --type ts --type js "throw\s+\{" -n
rg --type ts --type js "throw\s+\d" -n
rg --type ts --type js "reject\([^n]" -n
```

### Giải pháp

❌ **BAD**
```typescript
throw 'User not found';
Promise.reject('timeout');
throw { status: 404, message: 'Not found' };
```

✅ **GOOD**
```typescript
class AppError extends Error {
  constructor(
    message: string,
    public readonly code: string,
    public readonly statusCode: number = 500,
    options?: ErrorOptions,
  ) {
    super(message, options);
    this.name = this.constructor.name;
  }
}

class NotFoundError extends AppError {
  constructor(resource: string, id: string, options?: ErrorOptions) {
    super(`${resource} ${id} not found`, 'NOT_FOUND', 404, options);
  }
}

// Usage:
throw new NotFoundError('User', userId);
Promise.reject(new TimeoutError('API call timed out'));
```

### Phòng ngừa
- [ ] ONLY throw Error instances (or subclasses)
- [ ] Custom error hierarchy per domain
- [ ] `Promise.reject(new Error(...))` not `reject('string')`
- Tool: ESLint `no-throw-literal`

---

## Pattern 06: Express Error Handler Thiếu

### Tên
Express Error Handler Thiếu (Async Route Handler Unhandled)

### Phân loại
Error Handling / Express / Middleware

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```typescript
// Express DOES NOT catch async errors automatically (before v5):
app.get('/users/:id', async (req, res) => {
  const user = await db.getUser(req.params.id);
  // If getUser throws → unhandled rejection → no response → request hangs
  res.json(user);
});
```

### Phát hiện

```bash
rg --type ts --type js "app\.(get|post|put|delete|patch)\(.*async" -n
rg --type ts --type js "router\.(get|post|put|delete|patch)\(.*async" -n
rg --type ts --type js "asyncHandler|expressAsyncErrors" -n
rg --type ts --type js "err.*req.*res.*next" -n
```

### Giải pháp

❌ **BAD**
```typescript
app.get('/users/:id', async (req, res) => {
  const user = await userService.findById(req.params.id); // Unhandled if throws
  res.json(user);
});
```

✅ **GOOD**
```typescript
// Option 1: Wrapper function
const asyncHandler = (fn: RequestHandler) => (req: Request, res: Response, next: NextFunction) =>
  Promise.resolve(fn(req, res, next)).catch(next);

app.get('/users/:id', asyncHandler(async (req, res) => {
  const user = await userService.findById(req.params.id);
  res.json(user);
}));

// Option 2: express-async-errors (monkey-patches Express)
import 'express-async-errors';

// Option 3: Express 5 (built-in async support)

// ALWAYS: Global error handler middleware (4 params!)
app.use((err: Error, req: Request, res: Response, next: NextFunction) => {
  logger.error({ err, path: req.path }, 'Request error');
  const statusCode = err instanceof AppError ? err.statusCode : 500;
  res.status(statusCode).json({
    error: {
      message: err instanceof AppError ? err.message : 'Internal Server Error',
      code: err instanceof AppError ? err.code : 'INTERNAL_ERROR',
    },
  });
});
```

### Phòng ngừa
- [ ] Wrap all async route handlers
- [ ] Global error middleware (4 params: err, req, res, next)
- [ ] Express 5+ handles async natively
- Tool: `express-async-errors` package

---

## Pattern 07: Process Exit Handler Thiếu

### Tên
Process Exit Handler Thiếu (Missing Graceful Shutdown)

### Phân loại
Error Handling / Process / Lifecycle

### Mức nghiêm trọng
CRITICAL 🔴

### Vấn đề

```
SIGTERM (Docker stop, K8s pod termination):
→ Process killed immediately
→ In-flight requests dropped
→ DB connections not closed
→ Data loss possible

Process ──receiving requests──╳ KILLED
  │── Request A: half-written to DB
  │── Request B: response never sent
  └── DB pool: connections leaked
```

### Phát hiện

```bash
rg --type ts --type js "process\.on\(.(SIGTERM|SIGINT)" -n
rg --type ts --type js "server\.close" -n
rg --type ts --type js "graceful" -i -n
```

### Giải pháp

❌ **BAD**
```typescript
const server = app.listen(3000);
// No shutdown handler — process killed abruptly on SIGTERM
```

✅ **GOOD**
```typescript
const server = app.listen(3000);

async function gracefulShutdown(signal: string) {
  logger.info({ signal }, 'Received shutdown signal');

  // 1. Stop accepting new connections
  server.close(() => {
    logger.info('HTTP server closed');
  });

  // 2. Close database connections
  await db.end();

  // 3. Close Redis connections
  await redis.quit();

  // 4. Flush logs
  await logger.flush();

  logger.info('Graceful shutdown complete');
  process.exit(0);
}

process.on('SIGTERM', () => gracefulShutdown('SIGTERM'));
process.on('SIGINT', () => gracefulShutdown('SIGINT'));

// Force exit if graceful shutdown takes too long
process.on('SIGTERM', () => {
  setTimeout(() => {
    logger.error('Forced shutdown after timeout');
    process.exit(1);
  }, 10000).unref();
});
```

### Phòng ngừa
- [ ] Handle SIGTERM + SIGINT
- [ ] Close server, DB, cache connections
- [ ] Timeout for forced exit
- Tool: `@godaddy/terminus` for graceful shutdown

---

## Pattern 08: Error Message Leak

### Tên
Error Message Leak (Lộ Stack Trace Cho Client)

### Phân loại
Error Handling / Security / Information Leak

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```typescript
app.use((err, req, res, next) => {
  res.status(500).json({
    error: err.message,     // ← May contain internal details
    stack: err.stack,       // ← NEVER send to client!
  });
});
// Client sees: "Connection to postgres://admin:secret@db:5432 refused"
```

### Phát hiện

```bash
rg --type ts --type js "err\.stack|error\.stack" -n --glob "!*test*"
rg --type ts --type js "res\.(json|send).*stack" -n
rg --type ts --type js "getMessage\(\)|\.message" -n --glob "*controller*"
```

### Giải pháp

❌ **BAD**
```typescript
res.status(500).json({
  message: err.message,
  stack: err.stack,
  sql: err.sql, // SQL query leaked!
});
```

✅ **GOOD**
```typescript
app.use((err: Error, req: Request, res: Response, next: NextFunction) => {
  // Log full error internally
  logger.error({ err, reqId: req.id }, 'Request error');

  // Send safe response to client
  if (err instanceof AppError) {
    res.status(err.statusCode).json({
      error: { message: err.message, code: err.code },
    });
  } else {
    res.status(500).json({
      error: { message: 'Internal Server Error', code: 'INTERNAL_ERROR' },
    });
  }

  // ONLY in development:
  if (process.env.NODE_ENV === 'development') {
    res.locals.debugError = { stack: err.stack };
  }
});
```

### Phòng ngừa
- [ ] NEVER send `err.stack` to client in production
- [ ] Generic message for unexpected errors
- [ ] Detailed errors only for known operational errors
- [ ] Log full details server-side

---

## Pattern 09: Operational vs Programmer Error

### Tên
Operational vs Programmer Error (Không Phân Biệt Lỗi Recoverable vs Bug)

### Phân loại
Error Handling / Design / Classification

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```
Operational errors (recoverable):     Programmer errors (bugs):
├── Network timeout                   ├── TypeError: undefined.foo
├── DB connection refused             ├── RangeError: invalid index
├── File not found                    ├── Reference to undefined var
├── Invalid user input                ├── Wrong argument count
└── → Handle and recover              └── → Fix the code, crash is OK

Treating both the same → either:
  1. Crash on recoverable errors (bad UX)
  2. Continue after bugs (corrupted state)
```

### Phát hiện

```bash
rg --type ts --type js "catch.*Error\)" -A 3 -n | rg "(continue|retry|return null)"
rg --type ts --type js "isOperational" -n
rg --type ts --type js "instanceof TypeError|instanceof RangeError" -n
```

### Giải pháp

❌ **BAD**
```typescript
process.on('uncaughtException', (err) => {
  logger.error(err);
  // Continue running ← WRONG for programmer errors!
});
```

✅ **GOOD**
```typescript
class AppError extends Error {
  constructor(
    message: string,
    public readonly isOperational: boolean = true,
    public readonly statusCode: number = 500,
    options?: ErrorOptions,
  ) {
    super(message, options);
  }
}

// Error handler decides based on type:
function handleError(error: Error): void {
  if (error instanceof AppError && error.isOperational) {
    // Operational: log and recover
    logger.warn({ error }, 'Operational error');
  } else {
    // Programmer error: log and crash
    logger.fatal({ error }, 'Programmer error — restarting');
    process.exit(1); // PM2/Docker will restart
  }
}
```

### Phòng ngừa
- [ ] Classify errors: operational vs programmer
- [ ] Operational → handle and recover
- [ ] Programmer → crash and restart (PM2/K8s will restart)
- Tool: Process manager (PM2, Docker, K8s) for auto-restart

---

## Pattern 10: Domain/Zone Deprecated

### Tên
Domain/Zone Deprecated (Dùng Module Deprecated Cho Error Handling)

### Phân loại
Error Handling / Node.js / Deprecated

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```typescript
import { Domain } from 'domain'; // ← DEPRECATED since Node 4!
const d = Domain.create();
d.on('error', (err) => { /* handle */ });
d.run(() => {
  // async operations
});

// Zone.js — Angular specific, not standard Node
// AsyncLocalStorage — the modern replacement
```

### Phát hiện

```bash
rg --type ts --type js "require\(.domain.\)|from .domain." -n
rg --type ts --type js "Domain\.create" -n
rg --type ts --type js "zone\.js|Zone\.(current|root)" -n
```

### Giải pháp

❌ **BAD**
```typescript
import { Domain } from 'domain';
const d = Domain.create();
d.run(() => server.listen(3000));
```

✅ **GOOD**
```typescript
import { AsyncLocalStorage } from 'async_hooks';

const requestContext = new AsyncLocalStorage<{ requestId: string }>();

app.use((req, res, next) => {
  const store = { requestId: crypto.randomUUID() };
  requestContext.run(store, () => next());
});

// In any async code:
function getRequestId(): string | undefined {
  return requestContext.getStore()?.requestId;
}

// Logger automatically includes request context:
logger.info({ requestId: getRequestId() }, 'Processing request');
```

### Phòng ngừa
- [ ] NEVER use `domain` module — deprecated
- [ ] Use `AsyncLocalStorage` for request context
- [ ] Structured logging with context propagation
- Tool: `cls-hooked` (older) or `AsyncLocalStorage` (native)

---

## Pattern 11: Try/Catch Performance

### Tên
Try/Catch Performance (Try/Catch Bọc Toàn Function)

### Phân loại
Error Handling / Performance / Scope

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```typescript
async function processOrder(order: Order) {
  try {
    // 50 lines of code inside try block
    const user = await getUser(order.userId);
    const inventory = await checkInventory(order.items);
    const payment = await chargePayment(order);
    const shipment = await createShipment(order);
    await sendConfirmation(user, order);
    // ← Which operation failed? All caught the same way
  } catch (error) {
    logger.error('Order processing failed'); // ← No idea which step
  }
}
```

### Phát hiện

```bash
rg --type ts --type js "try\s*\{" -A 30 -n | rg "catch"
rg --type ts --type js "catch.*\{" -B 20 -n | rg "await.*await.*await"
```

### Giải pháp

❌ **BAD**
```typescript
try {
  // Everything in one big try block
  await step1(); await step2(); await step3();
} catch (e) {
  // Which step failed?
}
```

✅ **GOOD**
```typescript
async function processOrder(order: Order): Promise<OrderResult> {
  const user = await getUser(order.userId)
    .catch((e) => { throw new OrderError('Failed to fetch user', { cause: e }); });

  const inventory = await checkInventory(order.items)
    .catch((e) => { throw new OrderError('Inventory check failed', { cause: e }); });

  const payment = await chargePayment(order)
    .catch((e) => { throw new PaymentError('Payment failed', { cause: e }); });

  // Or use specific try/catch per critical section:
  try {
    await createShipment(order);
  } catch (error) {
    // Payment succeeded but shipment failed → needs special handling
    await refundPayment(payment);
    throw new ShipmentError('Shipment failed, payment refunded', { cause: error });
  }

  return { orderId: order.id, status: 'completed' };
}
```

### Phòng ngừa
- [ ] Small, focused try/catch blocks
- [ ] Each catch knows exactly what failed
- [ ] Add context when re-throwing
- [ ] Compensating actions for partial failures

---

## Pattern 12: Custom Error Serialization

### Tên
Custom Error Serialization (JSON.stringify Mất Properties)

### Phân loại
Error Handling / Serialization / JSON

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```typescript
const error = new Error('Something failed');
console.log(JSON.stringify(error));
// Output: {} ← Empty! message, stack are non-enumerable

class AppError extends Error {
  code = 'APP_ERR';
}
JSON.stringify(new AppError('test'));
// Output: {"code":"APP_ERR"} ← message and stack still missing!
```

### Phát hiện

```bash
rg --type ts --type js "JSON\.stringify.*error|JSON\.stringify.*err\b" -n
rg --type ts --type js "class\s+\w+Error\s+extends\s+Error" -n
rg --type ts --type js "toJSON\(\)" -n --glob "*error*"
```

### Giải pháp

❌ **BAD**
```typescript
class ApiError extends Error {
  constructor(message: string, public code: string) {
    super(message);
  }
}
// JSON.stringify(new ApiError('fail', 'ERR_01')) → {"code":"ERR_01"}
// message is lost!
```

✅ **GOOD**
```typescript
class ApiError extends Error {
  constructor(
    message: string,
    public readonly code: string,
    public readonly statusCode: number = 500,
    options?: ErrorOptions,
  ) {
    super(message, options);
    this.name = this.constructor.name;
  }

  toJSON() {
    return {
      name: this.name,
      message: this.message,
      code: this.code,
      statusCode: this.statusCode,
      stack: process.env.NODE_ENV === 'development' ? this.stack : undefined,
      cause: this.cause instanceof Error
        ? { message: this.cause.message, name: this.cause.name }
        : this.cause,
    };
  }
}

// Or use a serializer:
function serializeError(error: Error): Record<string, unknown> {
  return {
    name: error.name,
    message: error.message,
    stack: error.stack,
    ...Object.getOwnPropertyNames(error).reduce((acc, key) => {
      acc[key] = (error as any)[key];
      return acc;
    }, {} as Record<string, unknown>),
  };
}
```

### Phòng ngừa
- [ ] Implement `toJSON()` on custom Error classes
- [ ] Use `serialize-error` package for generic serialization
- [ ] Test error serialization in unit tests
- Tool: `serialize-error` npm package
