# Domain 07: Xử Lý Lỗi (Error Handling)

> .NET/C# patterns liên quan đến error handling: exceptions, Result pattern, Problem Details, global handlers.

---

## Pattern 01: Exception Swallowing

### Tên
Exception Swallowing (Nuốt Exception — Empty Catch Block)

### Phân loại
Error Handling / Exception / Swallowing

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```csharp
try
{
    await _repository.SaveAsync(entity);
}
catch (Exception)
{
    // Empty — exception swallowed completely
}
// Entity not saved but code continues as if success
```

### Phát hiện

```bash
rg --type cs "catch\s*\(.*Exception.*\)\s*\{?\s*\}" -n
rg --type cs "catch\s*\{\s*\}" -n
rg --type cs "catch\s*\(.*\)\s*\{\s*(return|//)" -n
```

### Giải pháp

❌ **BAD**
```csharp
try { await _service.Process(data); }
catch (Exception) { } // Swallowed

try { await _service.Process(data); }
catch (Exception) { return null; } // Silent null
```

✅ **GOOD**
```csharp
try
{
    await _service.Process(data);
}
catch (DbUpdateConcurrencyException ex)
{
    _logger.LogWarning(ex, "Concurrency conflict for entity {Id}", entity.Id);
    throw new ConflictException($"Entity {entity.Id} was modified", ex);
}
catch (DbUpdateException ex)
{
    _logger.LogError(ex, "Database error saving entity {Id}", entity.Id);
    throw; // Re-throw — let global handler deal with it
}
```

### Phòng ngừa
- [ ] NEVER empty catch blocks
- [ ] Catch specific exception types
- [ ] Log with context before re-throwing
- Tool: Roslyn analyzer CA1031 (Do not catch general exception types)

---

## Pattern 02: Catch Exception Quá Rộng

### Tên
Catch Exception Quá Rộng (Catching Base Exception Type)

### Phân loại
Error Handling / Exception / Specificity

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```csharp
try
{
    var result = await _paymentService.Charge(order);
}
catch (Exception ex) // Catches EVERYTHING:
{
    // OutOfMemoryException? Caught
    // StackOverflowException? Caught (sometimes)
    // NullReferenceException? Caught (hides bugs!)
    // PaymentDeclinedException? Caught (same as bugs!)
    _logger.LogError(ex, "Payment failed");
    return Error("Payment failed");
}
```

### Phát hiện

```bash
rg --type cs "catch\s*\(\s*Exception\s" -n
rg --type cs "catch\s*\(\s*System\.Exception" -n
rg --type cs "catch\s*\{" -n
```

### Giải pháp

❌ **BAD**
```csharp
catch (Exception ex)
{
    return BadRequest(ex.Message);
}
```

✅ **GOOD**
```csharp
try
{
    var result = await _paymentService.Charge(order);
}
catch (PaymentDeclinedException ex)
{
    _logger.LogWarning(ex, "Payment declined for order {OrderId}", order.Id);
    return BadRequest(new { error = "Payment declined", code = ex.DeclineCode });
}
catch (PaymentGatewayException ex)
{
    _logger.LogError(ex, "Gateway error for order {OrderId}", order.Id);
    return StatusCode(503, new { error = "Payment gateway unavailable" });
}
// NullReferenceException, etc. → NOT caught → bubbles to global handler
```

### Phòng ngừa
- [ ] Catch specific exception types
- [ ] Let system exceptions propagate
- [ ] `catch (Exception)` only in global handler
- Tool: Roslyn CA1031

---

## Pattern 03: Throw Ex Mất Stack Trace

### Tên
Throw Ex Mất Stack Trace (`throw ex` vs `throw`)

### Phân loại
Error Handling / Exception / Stack Trace

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```csharp
try { DoSomething(); }
catch (Exception ex)
{
    _logger.LogError(ex, "Error");
    throw ex;  // ← RESETS stack trace!
    // Stack trace now starts HERE, not at original throw point
    // Debugging becomes impossible
}
```

### Phát hiện

```bash
rg --type cs "throw\s+ex\s*;" -n
rg --type cs "throw\s+\w+\s*;" -n | rg -v "throw new"
```

### Giải pháp

❌ **BAD**
```csharp
catch (Exception ex)
{
    LogError(ex);
    throw ex; // Stack trace reset — original throw location lost!
}
```

✅ **GOOD**
```csharp
// Option 1: Bare throw (preserves stack trace)
catch (Exception ex)
{
    _logger.LogError(ex, "Error in ProcessOrder");
    throw; // ← Preserves original stack trace
}

// Option 2: Wrap with inner exception (adds context)
catch (Exception ex)
{
    throw new OrderProcessingException(
        $"Failed to process order {orderId}",
        ex  // ← Original exception as InnerException
    );
}

// Option 3: ExceptionDispatchInfo (preserves exact stack)
catch (Exception ex)
{
    _logger.LogError(ex, "Error");
    ExceptionDispatchInfo.Capture(ex).Throw();
}
```

### Phòng ngừa
- [ ] NEVER `throw ex;` — always `throw;`
- [ ] Wrap exceptions to add context (InnerException)
- [ ] Use `ExceptionDispatchInfo` for deferred re-throw
- Tool: Roslyn CA2200 (Rethrow to preserve stack details)

---

## Pattern 04: Exception Trong Constructor

### Tên
Exception Trong Constructor (Constructor Throws Exception)

### Phân loại
Error Handling / Exception / Object Lifecycle

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```csharp
public class DatabaseConnection : IDisposable
{
    private readonly SqlConnection _conn;
    private readonly FileStream _log;

    public DatabaseConnection(string connStr, string logPath)
    {
        _conn = new SqlConnection(connStr);
        _conn.Open();         // ← If this throws...
        _log = new FileStream(logPath, FileMode.Create);
        // _log is never created, but _conn was opened
        // Object not fully constructed → Dispose() never called
        // _conn is LEAKED
    }
}
```

### Phát hiện

```bash
rg --type cs "public\s+\w+\(.*\)\s*\{" -A 10 | rg "(throw|Open|Connect|new\s+\w+Stream)"
rg --type cs "class\s+\w+.*IDisposable" -n
rg --type cs "constructor.*throw" -i -n
```

### Giải pháp

❌ **BAD**
```csharp
public ResourceManager(string path)
{
    _fileStream = File.Open(path, FileMode.Open); // If next line throws → leaked
    _connection = CreateConnection(); // throws!
}
```

✅ **GOOD**
```csharp
public class ResourceManager : IDisposable
{
    private readonly FileStream _fileStream;
    private readonly DbConnection _connection;

    private ResourceManager(FileStream fileStream, DbConnection connection)
    {
        _fileStream = fileStream;
        _connection = connection;
    }

    public static ResourceManager Create(string path, string connStr)
    {
        FileStream? fileStream = null;
        DbConnection? connection = null;
        try
        {
            fileStream = File.Open(path, FileMode.Open);
            connection = new SqlConnection(connStr);
            connection.Open();
            return new ResourceManager(fileStream, connection);
        }
        catch
        {
            fileStream?.Dispose();
            connection?.Dispose();
            throw;
        }
    }

    public void Dispose()
    {
        _fileStream.Dispose();
        _connection.Dispose();
    }
}
```

### Phòng ngừa
- [ ] Use factory methods for complex initialization
- [ ] Clean up partial resources if constructor fails
- [ ] Prefer simple constructors, defer complex work
- Tool: Roslyn CA1065 (Do not raise exceptions in unexpected locations)

---

## Pattern 05: Result Pattern Thiếu

### Tên
Result Pattern Thiếu (Exception Cho Flow Control)

### Phân loại
Error Handling / Design / Pattern

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```csharp
// Using exceptions for expected business failures:
public User GetUser(int id)
{
    var user = _db.Users.Find(id);
    if (user == null)
        throw new UserNotFoundException(id);  // ← Exception for expected case!
    return user;
}
// Exceptions are expensive (stack trace capture)
// Expected failures are not "exceptional"
```

### Phát hiện

```bash
rg --type cs "throw new \w+NotFoundException" -n
rg --type cs "throw new \w+ValidationException" -n
rg --type cs "class Result" -n
rg --type cs "OneOf|ErrorOr" -n
```

### Giải pháp

❌ **BAD**
```csharp
try
{
    var user = _userService.GetUser(id);
}
catch (UserNotFoundException)
{
    return NotFound();
}
catch (ValidationException ex)
{
    return BadRequest(ex.Message);
}
```

✅ **GOOD**
```csharp
// Result<T> pattern:
public sealed record Result<T>
{
    public T? Value { get; }
    public Error? Error { get; }
    public bool IsSuccess => Error is null;

    private Result(T value) => Value = value;
    private Result(Error error) => Error = error;

    public static Result<T> Success(T value) => new(value);
    public static Result<T> Failure(Error error) => new(error);
}

public sealed record Error(string Code, string Message);

// Usage:
public async Task<Result<User>> GetUser(int id)
{
    var user = await _db.Users.FindAsync(id);
    return user is null
        ? Result<User>.Failure(new Error("USER_NOT_FOUND", $"User {id} not found"))
        : Result<User>.Success(user);
}

// Controller:
var result = await _userService.GetUser(id);
return result.IsSuccess
    ? Ok(result.Value)
    : NotFound(new ProblemDetails { Detail = result.Error!.Message });
```

### Phòng ngừa
- [ ] Use Result<T> for expected failures
- [ ] Reserve exceptions for unexpected errors
- [ ] Libraries: `ErrorOr`, `OneOf`, `FluentResults`
- Tool: NuGet `ErrorOr` package

---

## Pattern 06: Problem Details Thiếu

### Tên
Problem Details Thiếu (API Error Response Không Chuẩn)

### Phân loại
Error Handling / API / Response Format

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```
Mỗi endpoint trả error format khác nhau:

GET /users/999    → { "error": "Not found" }
POST /orders      → { "message": "Invalid", "errors": [...] }
PUT /products/1   → "Something went wrong"

→ Client phải handle nhiều format
→ Không theo RFC 7807 (Problem Details)
```

### Phát hiện

```bash
rg --type cs "ProblemDetails" -n
rg --type cs "BadRequest\(new\s*\{" -n
rg --type cs "StatusCode\(\d+.*new\s*\{" -n
rg --type cs "AddProblemDetails" -n
```

### Giải pháp

❌ **BAD**
```csharp
return BadRequest(new { error = "Invalid email" });
return StatusCode(500, "Internal error");
return NotFound("User not found");
```

✅ **GOOD**
```csharp
// Program.cs — ASP.NET Core 7+
builder.Services.AddProblemDetails(options =>
{
    options.CustomizeProblemDetails = context =>
    {
        context.ProblemDetails.Extensions["traceId"] = context.HttpContext.TraceIdentifier;
    };
});

// Controller:
return Problem(
    title: "User not found",
    detail: $"User with ID {id} does not exist",
    statusCode: StatusCodes.Status404NotFound,
    type: "https://api.example.com/errors/user-not-found"
);

// Global exception handler produces ProblemDetails:
app.UseExceptionHandler(app =>
{
    app.Run(async context =>
    {
        var problemDetails = new ProblemDetails
        {
            Status = StatusCodes.Status500InternalServerError,
            Title = "An unexpected error occurred",
            Type = "https://api.example.com/errors/internal"
        };
        context.Response.StatusCode = 500;
        await context.Response.WriteAsJsonAsync(problemDetails);
    });
});
```

### Phòng ngừa
- [ ] Use `ProblemDetails` for ALL error responses
- [ ] Follow RFC 7807 format
- [ ] `builder.Services.AddProblemDetails()` in Program.cs
- Tool: ASP.NET Core built-in Problem Details support

---

## Pattern 07: Global Exception Handler

### Tên
Global Exception Handler (UseExceptionHandler Thiếu)

### Phân loại
Error Handling / ASP.NET / Global

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```
Unhandled exception in ASP.NET Core:
→ Default: Developer Exception Page (development) or generic 500
→ Production without handler:
  - Stack trace may leak to client
  - No logging of error details
  - No custom error response format
  - No monitoring/alerting
```

### Phát hiện

```bash
rg --type cs "UseExceptionHandler|UseStatusCodePages" -n
rg --type cs "app\.UseDeveloperExceptionPage" -n
rg --type cs "IExceptionHandler" -n
rg --type cs "ExceptionHandlerMiddleware" -n
```

### Giải pháp

❌ **BAD**
```csharp
var app = builder.Build();
// No exception handler configured
// Development: stack trace shown
// Production: generic 500
app.MapControllers();
app.Run();
```

✅ **GOOD**
```csharp
// .NET 8+ IExceptionHandler:
public class GlobalExceptionHandler : IExceptionHandler
{
    private readonly ILogger<GlobalExceptionHandler> _logger;

    public GlobalExceptionHandler(ILogger<GlobalExceptionHandler> logger)
    {
        _logger = logger;
    }

    public async ValueTask<bool> TryHandleAsync(
        HttpContext httpContext,
        Exception exception,
        CancellationToken cancellationToken)
    {
        _logger.LogError(exception, "Unhandled exception: {Message}", exception.Message);

        var problemDetails = exception switch
        {
            ValidationException ex => new ProblemDetails
            {
                Status = 400,
                Title = "Validation Error",
                Detail = ex.Message,
            },
            NotFoundException ex => new ProblemDetails
            {
                Status = 404,
                Title = "Not Found",
                Detail = ex.Message,
            },
            _ => new ProblemDetails
            {
                Status = 500,
                Title = "Internal Server Error",
                Detail = "An unexpected error occurred",
            },
        };

        httpContext.Response.StatusCode = problemDetails.Status!.Value;
        await httpContext.Response.WriteAsJsonAsync(problemDetails, cancellationToken);
        return true;
    }
}

// Program.cs:
builder.Services.AddExceptionHandler<GlobalExceptionHandler>();
builder.Services.AddProblemDetails();

app.UseExceptionHandler();
```

### Phòng ngừa
- [ ] Always configure `UseExceptionHandler`
- [ ] Use `IExceptionHandler` (.NET 8+)
- [ ] Map exception types to HTTP status codes
- [ ] Log all unhandled exceptions
- Tool: Roslyn analyzers for ASP.NET Core

---

## Pattern 08: Middleware Exception Propagation

### Tên
Middleware Exception Propagation (Exception Trong Middleware)

### Phân loại
Error Handling / ASP.NET / Middleware

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```csharp
public class TenantMiddleware
{
    public async Task InvokeAsync(HttpContext context, RequestDelegate next)
    {
        var tenantId = context.Request.Headers["X-Tenant-Id"].ToString();
        // If header missing → empty string → FindTenant throws
        var tenant = await _tenantService.FindTenant(tenantId);
        context.Items["Tenant"] = tenant;
        await next(context);
        // Exception in next() → middleware cleanup code skipped
    }
}
```

### Phát hiện

```bash
rg --type cs "class\s+\w+Middleware" -n
rg --type cs "InvokeAsync.*next\(" -n
rg --type cs "await\s+next\(" -A 5 -n
```

### Giải pháp

❌ **BAD**
```csharp
public async Task InvokeAsync(HttpContext context, RequestDelegate next)
{
    SetupSomething();
    await next(context); // If this throws → cleanup never runs
    CleanupSomething(); // Never reached!
}
```

✅ **GOOD**
```csharp
public async Task InvokeAsync(HttpContext context, RequestDelegate next)
{
    if (!context.Request.Headers.TryGetValue("X-Tenant-Id", out var tenantHeader)
        || string.IsNullOrEmpty(tenantHeader))
    {
        context.Response.StatusCode = 400;
        await context.Response.WriteAsJsonAsync(new ProblemDetails
        {
            Title = "Missing Tenant",
            Detail = "X-Tenant-Id header is required",
            Status = 400,
        });
        return; // Short-circuit — don't call next
    }

    try
    {
        SetupContext(context);
        await next(context);
    }
    finally
    {
        CleanupContext(context); // ALWAYS runs
    }
}
```

### Phòng ngừa
- [ ] Use try/finally for cleanup in middleware
- [ ] Validate input before calling `next()`
- [ ] Short-circuit with proper error response
- [ ] Test middleware error scenarios

---

## Pattern 09: Custom Exception Serialization

### Tên
Custom Exception Serialization (Custom Exception Không Serializable)

### Phân loại
Error Handling / Exception / Serialization

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```csharp
public class OrderException : Exception
{
    public string OrderId { get; }
    public decimal Amount { get; }

    public OrderException(string message, string orderId, decimal amount)
        : base(message)
    {
        OrderId = orderId;
        Amount = amount;
    }
}
// When serialized (remote services, logging):
// OrderId and Amount are LOST
// No serialization constructor
```

### Phát hiện

```bash
rg --type cs "class\s+\w+Exception\s*:" -n
rg --type cs "\[Serializable\]" -n
rg --type cs "GetObjectData\(" -n
rg --type cs "SerializationInfo" -n
```

### Giải pháp

❌ **BAD**
```csharp
public class AppException : Exception
{
    public string Code { get; }
    public AppException(string message, string code) : base(message)
    {
        Code = code;
    }
    // Missing: serialization support, ToString override
}
```

✅ **GOOD**
```csharp
public class AppException : Exception
{
    public string Code { get; }
    public IDictionary<string, object>? Context { get; }

    public AppException(string message, string code,
        IDictionary<string, object>? context = null,
        Exception? innerException = null)
        : base(message, innerException)
    {
        Code = code;
        Context = context;
    }

    public override string ToString()
    {
        var contextStr = Context is not null
            ? $" Context: {string.Join(", ", Context.Select(kv => $"{kv.Key}={kv.Value}"))}"
            : "";
        return $"[{Code}] {Message}{contextStr}\n{StackTrace}";
    }
}

// Usage:
throw new AppException(
    "Order processing failed",
    "ORDER_FAILED",
    new Dictionary<string, object>
    {
        ["orderId"] = order.Id,
        ["amount"] = order.Amount,
    },
    innerException: ex
);
```

### Phòng ngừa
- [ ] Override `ToString()` for logging
- [ ] Include context data as properties
- [ ] Always support `innerException` parameter
- [ ] Note: `[Serializable]` obsolete in .NET 8+ (BinaryFormatter removed)

---

## Pattern 10: Aggregate Exception

### Tên
Aggregate Exception (AggregateException Flatten Thiếu)

### Phân loại
Error Handling / Async / Exception

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```csharp
// Task.WhenAll wraps exceptions in AggregateException:
try
{
    await Task.WhenAll(task1, task2, task3);
}
catch (Exception ex)
{
    // ex is the FIRST exception only!
    // Other exceptions are hidden in AggregateException
    _logger.LogError(ex, "Failed"); // Only logs first error
}
```

### Phát hiện

```bash
rg --type cs "Task\.WhenAll" -n
rg --type cs "AggregateException" -n
rg --type cs "\.Flatten\(\)" -n
rg --type cs "InnerExceptions" -n
```

### Giải pháp

❌ **BAD**
```csharp
try
{
    await Task.WhenAll(tasks);
}
catch (Exception ex)
{
    _logger.LogError(ex, "Task failed"); // Only first exception!
}
```

✅ **GOOD**
```csharp
var allTasks = Task.WhenAll(tasks);
try
{
    await allTasks;
}
catch
{
    // Access ALL exceptions:
    var aggregateException = allTasks.Exception!;
    foreach (var ex in aggregateException.Flatten().InnerExceptions)
    {
        _logger.LogError(ex, "Task failed: {Message}", ex.Message);
    }

    // Or handle by type:
    var exceptions = aggregateException.Flatten().InnerExceptions;
    var critical = exceptions.OfType<CriticalException>().ToList();
    var transient = exceptions.OfType<TransientException>().ToList();

    if (critical.Any())
        throw new AggregateException("Critical failures", critical);
    if (transient.Any())
        _logger.LogWarning("Transient failures: {Count}", transient.Count);
}
```

### Phòng ngừa
- [ ] Use `allTasks.Exception` to access all exceptions
- [ ] Call `.Flatten()` to unwrap nested AggregateExceptions
- [ ] Log ALL inner exceptions, not just the first
- [ ] Classify exceptions by type for different handling

---

## Pattern 11: ExceptionDispatchInfo Thiếu

### Tên
ExceptionDispatchInfo Thiếu (Rethrow Mất Original Context)

### Phân loại
Error Handling / Exception / Rethrow

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```csharp
Exception? capturedException = null;

try { DoWork(); }
catch (Exception ex)
{
    capturedException = ex;
}

// Later:
if (capturedException != null)
    throw capturedException; // ← Stack trace shows THIS line, not original!
```

### Phát hiện

```bash
rg --type cs "ExceptionDispatchInfo" -n
rg --type cs "throw\s+\w+;" -n | rg -v "throw new"
rg --type cs "Exception\?\s+\w+\s*=\s*null" -n
```

### Giải pháp

❌ **BAD**
```csharp
Exception? saved = null;
try { Process(); }
catch (Exception ex) { saved = ex; }

// ... some cleanup ...

if (saved != null)
    throw saved; // Stack trace reset to this line!
```

✅ **GOOD**
```csharp
using System.Runtime.ExceptionServices;

ExceptionDispatchInfo? savedExceptionInfo = null;
try
{
    Process();
}
catch (Exception ex)
{
    savedExceptionInfo = ExceptionDispatchInfo.Capture(ex);
}

// ... cleanup code ...

// Re-throw with original stack trace preserved:
savedExceptionInfo?.Throw();

// Common use case: async exception handling
public async Task ExecuteWithRetry(Func<Task> action, int maxRetries)
{
    ExceptionDispatchInfo? lastException = null;
    for (int i = 0; i < maxRetries; i++)
    {
        try
        {
            await action();
            return;
        }
        catch (Exception ex)
        {
            lastException = ExceptionDispatchInfo.Capture(ex);
            await Task.Delay(TimeSpan.FromSeconds(Math.Pow(2, i)));
        }
    }
    lastException!.Throw(); // Preserves original stack trace
}
```

### Phòng ngừa
- [ ] Use `ExceptionDispatchInfo.Capture()` for deferred rethrow
- [ ] Preserves original stack trace + Watson bucket
- [ ] Common in retry patterns, async pipelines
- Tool: Roslyn CA2200 for `throw ex` detection
