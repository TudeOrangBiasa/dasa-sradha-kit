# Domain 06: Thiết Kế Và Kiến Trúc (Design & Architecture)

> .NET/ASP.NET Core patterns liên quan đến thiết kế hệ thống, DI, middleware pipeline, và tổ chức code.

---

## Pattern 01: God Controller

### Tên
God Controller (Controller Chứa Business Logic)

### Phân loại
Architecture / Controller / SRP Violation

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```
[ApiController]
[Route("api/[controller]")]
public class OrderController : ControllerBase  ← 500+ lines
{
    public async Task<IActionResult> Create(CreateOrderRequest req)
    {
        // Validation (should be FluentValidation)
        if (req.Items.Count == 0) return BadRequest();

        // Business logic (should be Service/Handler)
        var discount = CalculateDiscount(req);
        var tax = CalculateTax(req);
        var total = req.Subtotal - discount + tax;

        // Database (should be Repository)
        var order = new Order { Total = total, ... };
        _context.Orders.Add(order);
        await _context.SaveChangesAsync();

        // Side effects (should be MediatR notification / event)
        await _emailService.SendConfirmation(order);
        await _notificationService.NotifyAdmin(order);

        return CreatedAtAction(...);
    }
}
```

### Phát hiện

```bash
# Tìm controllers lớn
rg --type cs "class\s+\w+Controller" -l | xargs wc -l | sort -rn

# Tìm DB operations trong controller
rg --type cs "(SaveChangesAsync|\.Add\(|\.Remove\(|\.Update\()" -n --glob "*Controller.cs"

# Tìm email/notification trong controller
rg --type cs "(SendEmail|SendNotification|_emailService|_notificationService)" -n --glob "*Controller.cs"

# Tìm business logic helpers trong controller
rg --type cs "private.*Calculate|private.*Validate|private.*Process" -n --glob "*Controller.cs"
```

### Giải pháp

❌ **BAD**: Fat controller
```csharp
[HttpPost]
public async Task<IActionResult> Create(CreateOrderRequest req)
{
    // 100+ lines of mixed concerns
}
```

✅ **GOOD**: Thin controller with MediatR
```csharp
[HttpPost]
public async Task<IActionResult> Create(
    CreateOrderCommand command,
    CancellationToken ct)
{
    var result = await _mediator.Send(command, ct);
    return result.Match(
        success: order => CreatedAtAction(nameof(Get), new { id = order.Id }, order),
        failure: error => BadRequest(error)
    );
}
```

✅ **GOOD**: Thin controller with service
```csharp
[HttpPost]
public async Task<ActionResult<OrderResponse>> Create(
    [FromBody] CreateOrderRequest request,
    CancellationToken ct)
{
    var order = await _orderService.CreateAsync(request, ct);
    return CreatedAtAction(nameof(Get), new { id = order.Id },
        _mapper.Map<OrderResponse>(order));
}
```

### Phòng ngừa

- [ ] Controller methods < 15 lines
- [ ] Validation → FluentValidation / DataAnnotations
- [ ] Business logic → Service or MediatR Handler
- [ ] Side effects → MediatR Notifications / Domain Events
- Tool: Roslyn analyzer cho method length

---

## Pattern 02: DI Container Service Locator

### Tên
DI Container Service Locator (Dùng IServiceProvider Thay Vì Constructor DI)

### Phân loại
Architecture / DI / Anti-Pattern

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```
public class OrderService
{
    private readonly IServiceProvider _provider;

    public OrderService(IServiceProvider provider)
    {
        _provider = provider;  ← Service Locator!
    }

    public async Task Process()
    {
        var repo = _provider.GetRequiredService<IOrderRepository>();
        var mailer = _provider.GetService<IEmailService>();
             │
             ├── Hidden dependencies (không thấy trong constructor)
             ├── Runtime errors: GetRequiredService throws nếu không registered
             ├── Untestable: phải setup full DI container trong tests
             └── Violation of Explicit Dependencies Principle
    }
}
```

### Phát hiện

```bash
# Tìm IServiceProvider injection
rg --type cs "IServiceProvider" -n --glob "!*Startup*" --glob "!*Program*" --glob "!*ServiceCollection*"

# Tìm GetService/GetRequiredService calls
rg --type cs "GetService<|GetRequiredService<" -n

# Tìm service locator pattern
rg --type cs "_provider\.|_serviceProvider\.|_services\." -n

# Tìm ActivatorUtilities (another form of service locator)
rg --type cs "ActivatorUtilities" -n
```

### Giải pháp

❌ **BAD**: Service locator
```csharp
public class OrderService
{
    private readonly IServiceProvider _sp;
    public OrderService(IServiceProvider sp) => _sp = sp;

    public void Process()
    {
        var repo = _sp.GetRequiredService<IOrderRepository>();
        var email = _sp.GetRequiredService<IEmailService>();
        // Hidden dependencies!
    }
}
```

✅ **GOOD**: Constructor injection
```csharp
public class OrderService
{
    private readonly IOrderRepository _repository;
    private readonly IEmailService _emailService;

    public OrderService(
        IOrderRepository repository,
        IEmailService emailService)
    {
        _repository = repository;
        _emailService = emailService;
    }

    public void Process()
    {
        // Dependencies explicit and mockable
    }
}
```

✅ **GOOD**: Factory for runtime-resolved dependencies
```csharp
// Khi cần create scoped services from singleton
public class OrderProcessorFactory
{
    private readonly IServiceScopeFactory _scopeFactory;

    public OrderProcessorFactory(IServiceScopeFactory scopeFactory)
        => _scopeFactory = scopeFactory;

    public async Task ProcessInScope()
    {
        using var scope = _scopeFactory.CreateScope();
        var repo = scope.ServiceProvider.GetRequiredService<IOrderRepository>();
        // OK: factory pattern for scoped resolution
    }
}
```

### Phòng ngừa

- [ ] ALWAYS constructor injection
- [ ] IServiceProvider chỉ trong: Startup, Middleware, Factories
- [ ] `IServiceScopeFactory` cho scoped resolution từ singleton
- [ ] Explicit dependencies → easy to test, easy to understand
- Tool: Scrutor — convention-based registration

---

## Pattern 03: Anemic Domain Model

### Tên
Anemic Domain Model (Entity Chỉ Có Properties)

### Phân loại
Architecture / Domain / DDD

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```
public class Order       ← Data bag, no behavior
{
    public int Id { get; set; }
    public OrderStatus Status { get; set; }
    public decimal Total { get; set; }
    public DateTime CreatedAt { get; set; }
    // ALL public setters → anyone can set anything
}

public class OrderService  ← ALL logic here
{
    public void Cancel(Order order)
    {
        if (order.Status != OrderStatus.Pending)
            throw new InvalidOperationException();
        order.Status = OrderStatus.Cancelled;  ← Mutate from outside
        order.CancelledAt = DateTime.UtcNow;
    }
}
```

Entity chỉ chứa properties (data) mà không có behavior. Business rules nằm trong services → vi phạm OOP encapsulation.

### Phát hiện

```bash
# Tìm entities chỉ có auto-properties
rg --type cs "{ get; set; }" -c --glob "**/Entities/*.cs" | sort -t: -k2 -rn

# Tìm entities không có methods
rg --type cs "public\s+(void|bool|Task)" -c --glob "**/Entities/*.cs"

# Tìm services thao tác trực tiếp lên entity properties
rg --type cs "\.\w+\s*=\s*" -n --glob "*Service.cs"
```

### Giải pháp

❌ **BAD**: Anemic entity
```csharp
public class Order
{
    public int Id { get; set; }
    public OrderStatus Status { get; set; }
    public decimal Total { get; set; }
}
```

✅ **GOOD**: Rich domain model
```csharp
public class Order
{
    public int Id { get; private set; }
    public OrderStatus Status { get; private set; }
    public decimal Total { get; private set; }
    public DateTime? CancelledAt { get; private set; }

    private Order() { } // EF Core

    public static Order Create(IReadOnlyList<OrderItem> items)
    {
        if (items.Count == 0)
            throw new DomainException("Order must have at least one item");

        return new Order
        {
            Status = OrderStatus.Pending,
            Total = items.Sum(i => i.Subtotal),
        };
    }

    public void Cancel()
    {
        if (Status != OrderStatus.Pending)
            throw new DomainException($"Cannot cancel order in {Status} state");

        Status = OrderStatus.Cancelled;
        CancelledAt = DateTime.UtcNow;
        AddDomainEvent(new OrderCancelledEvent(Id));
    }
}
```

### Phòng ngừa

- [ ] `private set` cho entity properties
- [ ] Business rules INSIDE entity methods
- [ ] Static factory methods cho creation
- [ ] Domain events cho side effects
- Ref: Domain-Driven Design — Rich Domain Model

---

## Pattern 04: Repository Over DbContext

### Tên
Repository Over DbContext (Generic Repository Wrap DbContext)

### Phân loại
Architecture / Repository / Abstraction

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```
public interface IRepository<T> where T : class
{
    Task<T?> GetByIdAsync(int id);
    Task<IEnumerable<T>> GetAllAsync();
    Task AddAsync(T entity);
    Task UpdateAsync(T entity);
    Task DeleteAsync(T entity);
}

public class Repository<T> : IRepository<T> where T : class
{
    private readonly DbContext _context;

    public async Task<T?> GetByIdAsync(int id)
        => await _context.Set<T>().FindAsync(id);

    public async Task<IEnumerable<T>> GetAllAsync()
        => await _context.Set<T>().ToListAsync();
    // ...
}
// Đây chỉ là thin wrapper quanh DbContext
// Không thêm value nào — DbContext ĐÃ LÀ Unit of Work + Repository
```

### Phát hiện

```bash
# Tìm generic repository interfaces
rg --type cs "interface IRepository<T>" -n

# Tìm generic repository implementations
rg --type cs "class\s+\w+Repository.*<T>" -n

# Tìm DbContext.Set<T>() trong repository (thin wrapper)
rg --type cs "_context\.Set<T>\(\)" -n

# Tìm pattern: repository chỉ delegate to DbContext
rg --type cs "FindAsync|ToListAsync|AddAsync" -n --glob "*Repository.cs"
```

### Giải pháp

❌ **BAD**: Generic repository wrapping DbContext 1:1
```csharp
public class Repository<T> : IRepository<T> where T : class
{
    private readonly AppDbContext _context;

    public Task<T?> GetByIdAsync(int id) => _context.Set<T>().FindAsync(id).AsTask();
    public Task<List<T>> GetAllAsync() => _context.Set<T>().ToListAsync();
    // Just proxying DbContext — adds complexity, no value
}
```

✅ **GOOD**: Domain-specific repository with real value
```csharp
public interface IOrderRepository
{
    Task<Order?> GetWithItemsAsync(int id, CancellationToken ct);
    Task<IReadOnlyList<Order>> GetPendingOrdersAsync(CancellationToken ct);
    Task<Order> AddAsync(Order order, CancellationToken ct);
}

public class OrderRepository : IOrderRepository
{
    private readonly AppDbContext _context;

    public async Task<Order?> GetWithItemsAsync(int id, CancellationToken ct)
    {
        return await _context.Orders
            .Include(o => o.Items)
            .Include(o => o.User)
            .AsSplitQuery()
            .FirstOrDefaultAsync(o => o.Id == id, ct);
    }

    public async Task<IReadOnlyList<Order>> GetPendingOrdersAsync(CancellationToken ct)
    {
        return await _context.Orders
            .Where(o => o.Status == OrderStatus.Pending)
            .OrderBy(o => o.CreatedAt)
            .AsNoTracking()
            .ToListAsync(ct);
    }
}
```

### Phòng ngừa

- [ ] Avoid generic `IRepository<T>` — use domain-specific repos
- [ ] DbContext IS already Unit of Work + Repository
- [ ] Repository adds value via: specific queries, includes, projections
- [ ] Consider: direct DbContext injection for simple CRUD
- Ref: Jimmy Bogard — "Repositories: You're Doing It Wrong"

---

## Pattern 05: MediatR Overuse

### Tên
MediatR Overuse (MediatR Cho Mọi Thứ)

### Phân loại
Architecture / Mediator / Indirection

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```
Controller:
  _mediator.Send(new GetUserByIdQuery(id))
       │
       ▼
  MediatR Pipeline:
       │
       ├── ValidationBehavior
       ├── LoggingBehavior
       ├── CachingBehavior
       ├── PerformanceBehavior
       ▼
  GetUserByIdQueryHandler
       │
       └── return _context.Users.FindAsync(id);
           ^^^ 1 line of actual logic, 5 layers of indirection

  File count explosion:
  ├── GetUserByIdQuery.cs
  ├── GetUserByIdQueryHandler.cs
  ├── GetUserByIdQueryValidator.cs
  ├── GetUserByIdQueryResponse.cs
  └── 4 files cho 1 line of logic!
```

### Phát hiện

```bash
# Count MediatR request/handler files
rg --type cs "IRequest<|IRequestHandler<" -l | wc -l

# Tìm handlers với 1-3 lines of logic
rg --type cs "class\s+\w+Handler.*IRequestHandler" -l | xargs -I{} sh -c \
  'echo "=== {} ===" && wc -l {}'

# Tìm _mediator.Send calls
rg --type cs "_mediator\.Send\(" -n

# Count behaviors in pipeline
rg --type cs "IPipelineBehavior" -l | wc -l
```

### Giải pháp

❌ **BAD**: MediatR for everything
```csharp
// 4 files cho simple GetById
public record GetUserByIdQuery(int Id) : IRequest<User?>;
public class GetUserByIdQueryHandler : IRequestHandler<GetUserByIdQuery, User?>
{
    public async Task<User?> Handle(GetUserByIdQuery request, CancellationToken ct)
        => await _context.Users.FindAsync(request.Id, ct);
}
```

✅ **GOOD**: MediatR cho complex operations, direct service cho simple
```csharp
// Simple CRUD → service directly
public class UserService
{
    public Task<User?> GetByIdAsync(int id, CancellationToken ct)
        => _context.Users.FindAsync(id, ct).AsTask();
}

// Complex business logic → MediatR
public record PlaceOrderCommand(OrderDto Order) : IRequest<Result<Order>>;
public class PlaceOrderCommandHandler : IRequestHandler<PlaceOrderCommand, Result<Order>>
{
    // Multiple services, validation, events, transactions
    // MediatR pipeline adds value here
}
```

### Phòng ngừa

- [ ] MediatR cho: commands có side effects, complex workflows
- [ ] Direct service cho: simple queries, CRUD
- [ ] Nếu handler < 5 lines → probably don't need MediatR
- [ ] File count: 4 files per operation = overhead signal
- Ref: Consider Vertical Slice Architecture balance

---

## Pattern 06: Static Abuse

### Tên
Static Abuse (Lạm Dụng Static Class/Method)

### Phân loại
Architecture / Testability / OOP

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```
public static class DateHelper
{
    public static DateTime GetStartOfWeek()
        => DateTime.Now.AddDays(-(int)DateTime.Now.DayOfWeek);
                   ^^^^
                   Static dependency on DateTime.Now
                   Cannot test with fixed date!
}

public static class CacheManager
{
    private static readonly Dictionary<string, object> _cache = new();
    public static void Set(string key, object value) => _cache[key] = value;
    public static object? Get(string key) => _cache.GetValueOrDefault(key);
    // Shared mutable state — race conditions, test pollution
}
```

### Phát hiện

```bash
# Tìm static classes
rg --type cs "static class" -n

# Tìm static methods (non-extension)
rg --type cs "public static\s+\w+\s+\w+\(" -n --glob "!*Extensions*"

# Tìm DateTime.Now/UtcNow (untestable static)
rg --type cs "DateTime\.(Now|UtcNow)" -n

# Tìm static mutable fields
rg --type cs "private static\s+(?!readonly)" -n
```

### Giải pháp

❌ **BAD**: Static with dependencies
```csharp
public static class PriceCalculator
{
    public static decimal Calculate(Order order)
    {
        var taxRate = TaxService.GetRate(order.Country); // Static call
        var discount = PromotionEngine.GetDiscount(order); // Static call
        return order.Subtotal * (1 + taxRate) - discount;
    }
}
```

✅ **GOOD**: Instance with DI
```csharp
public class PriceCalculator
{
    private readonly ITaxService _taxService;
    private readonly IPromotionEngine _promotionEngine;

    public PriceCalculator(ITaxService taxService, IPromotionEngine promotionEngine)
    {
        _taxService = taxService;
        _promotionEngine = promotionEngine;
    }

    public decimal Calculate(Order order)
    {
        var taxRate = _taxService.GetRate(order.Country);
        var discount = _promotionEngine.GetDiscount(order);
        return order.Subtotal * (1 + taxRate) - discount;
    }
}

// For DateTime — use TimeProvider (.NET 8+)
public class OrderService(TimeProvider timeProvider)
{
    public void Process(Order order)
    {
        order.ProcessedAt = timeProvider.GetUtcNow();
    }
}
```

### Phòng ngừa

- [ ] Static chỉ cho: extension methods, pure functions, constants
- [ ] Instance + DI cho everything else
- [ ] `TimeProvider` (.NET 8+) thay `DateTime.Now`
- [ ] No static mutable state
- Tool: Roslyn analyzer CA1052 (static class members)

---

## Pattern 07: Middleware Order Sai

### Tên
Middleware Order Sai (Incorrect Middleware Pipeline Order)

### Phân loại
Architecture / HTTP / Middleware Pipeline

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```
ASP.NET Core Middleware Pipeline:

  Request → M1 → M2 → M3 → Endpoint → M3 → M2 → M1 → Response
            │                                          │
            └──────── Order matters! ─────────────────┘

  WRONG ORDER:
  app.UseAuthorization();     ← BEFORE Authentication!
  app.UseAuthentication();    ← TOO LATE — already checked authz
  app.UseRateLimiter();       ← After auth — unauthenticated bypass rate limit

  Result: Authorization check runs before identity is established
          → Authorize attribute always fails or bypassed
```

### Phát hiện

```bash
# Tìm middleware ordering trong Program.cs
rg --type cs "app\.Use\w+" -n --glob "Program.cs"

# Check authentication/authorization order
rg --type cs "UseAuthentication|UseAuthorization" -n

# Tìm CORS placement
rg --type cs "UseCors" -n

# Tìm rate limiter placement
rg --type cs "UseRateLimiter" -n
```

### Giải pháp

❌ **BAD**: Wrong order
```csharp
app.UseAuthorization();    // Runs before identity is known!
app.UseAuthentication();   // Too late
app.UseRateLimiter();      // After auth — DDoS vector
app.UseCors();             // After routing — doesn't work for preflight
```

✅ **GOOD**: Correct middleware order
```csharp
// ASP.NET Core recommended order:
app.UseExceptionHandler();      // 1. Catch all exceptions
app.UseHsts();                  // 2. HSTS
app.UseHttpsRedirection();      // 3. Redirect HTTP → HTTPS
app.UseStaticFiles();           // 4. Serve static files (skip pipeline)
app.UseRouting();               // 5. Route matching
app.UseCors();                  // 6. CORS (after routing, before auth)
app.UseRateLimiter();           // 7. Rate limiting (before auth)
app.UseAuthentication();        // 8. Who are you?
app.UseAuthorization();         // 9. Can you access this? (AFTER auth!)
app.UseResponseCaching();       // 10. Cache responses
app.MapControllers();           // 11. Endpoints
```

### Phòng ngừa

- [ ] Follow ASP.NET Core recommended order
- [ ] Authentication ALWAYS before Authorization
- [ ] Rate limiting BEFORE Authentication
- [ ] CORS after UseRouting, before UseAuthentication
- [ ] Test: unauthenticated requests hit rate limiter
- Ref: Microsoft docs — Middleware order

---

## Pattern 08: Configuration Binding Sai

### Tên
Configuration Binding Sai (Options Pattern Không Validate)

### Phân loại
Architecture / Configuration / Options

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```
appsettings.json:
{
    "Database": {
        "ConnectionString": "",        ← Empty!
        "MaxRetries": -1,              ← Invalid!
        "TimeoutSeconds": "not-a-number" ← Wrong type!
    }
}

services.Configure<DatabaseOptions>(config.GetSection("Database"));
// No validation! App starts with invalid config
// Crash at runtime when first DB operation
```

### Phát hiện

```bash
# Tìm Configure<T> without validation
rg --type cs "Configure<\w+>" -n

# Tìm Options classes
rg --type cs "class\s+\w+Options" -n

# Check for validation
rg --type cs "ValidateDataAnnotations|ValidateOnStart|IValidateOptions" -n

# Tìm direct config binding
rg --type cs "GetSection\(|Bind\(" -n
```

### Giải pháp

❌ **BAD**: No validation
```csharp
services.Configure<SmtpOptions>(config.GetSection("Smtp"));
// Starts with empty host, port 0 → runtime crash
```

✅ **GOOD**: Options with validation
```csharp
public class SmtpOptions
{
    public const string Section = "Smtp";

    [Required]
    public string Host { get; init; } = string.Empty;

    [Range(1, 65535)]
    public int Port { get; init; } = 587;

    [Required, EmailAddress]
    public string FromAddress { get; init; } = string.Empty;
}

// Registration with validation
services.AddOptions<SmtpOptions>()
    .BindConfiguration(SmtpOptions.Section)
    .ValidateDataAnnotations()
    .ValidateOnStart(); // Fail at startup, not runtime!

// Inject via IOptions<T>
public class EmailService(IOptions<SmtpOptions> options)
{
    private readonly SmtpOptions _smtp = options.Value;
}
```

### Phòng ngừa

- [ ] `.ValidateDataAnnotations()` cho attribute-based validation
- [ ] `.ValidateOnStart()` — fail fast at startup
- [ ] `IValidateOptions<T>` cho complex validation
- [ ] `required` properties in options classes
- Tool: `ValidateOnStart` catches config errors early

---

## Pattern 09: Circular Dependency

### Tên
Circular Dependency (Phụ Thuộc Vòng Tròn)

### Phân loại
Architecture / DI / Dependency

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```
public class ServiceA
{
    public ServiceA(ServiceB b) { }  ← Depends on B
}

public class ServiceB
{
    public ServiceB(ServiceA a) { }  ← Depends on A
}

// DI container:
// "A circular dependency was detected for the service of type ServiceA"
// Stack overflow hoặc DI exception at startup
```

### Phát hiện

```bash
# Tìm constructor dependencies
rg --type cs "public\s+\w+\(I?\w+Service" -n --glob "*Service.cs"

# Tìm mutual dependencies
rg --type cs "using.*Services" -n --glob "*Service.cs"

# Check DI registration
rg --type cs "AddScoped|AddTransient|AddSingleton" -n --glob "Program.cs"
```

### Giải pháp

❌ **BAD**: Direct circular dependency
```csharp
public class UserService(IOrderService orders) { }
public class OrderService(IUserService users) { }
```

✅ **GOOD**: Break cycle with interface/event
```csharp
// Option 1: Extract shared interface
public interface IUserInfo
{
    Task<UserDto> GetUserInfoAsync(int id, CancellationToken ct);
}

public class UserService : IUserInfo { /* no dependency on OrderService */ }
public class OrderService(IUserInfo userInfo) { /* depends on interface, not UserService */ }

// Option 2: Domain events
public class OrderService
{
    public async Task CancelOrder(int orderId)
    {
        // Publish event instead of calling UserService
        await _mediator.Publish(new OrderCancelledEvent(orderId));
    }
}

public class UserNotificationHandler : INotificationHandler<OrderCancelledEvent>
{
    public async Task Handle(OrderCancelledEvent e, CancellationToken ct)
    {
        // Handle in separate handler
    }
}

// Option 3: Lazy<T> (last resort)
public class ServiceA(Lazy<IServiceB> b) { }
```

### Phòng ngừa

- [ ] Dependency graph: directed acyclic (no cycles)
- [ ] Extract interface to break cycle
- [ ] MediatR notifications cho cross-domain communication
- [ ] `Lazy<T>` chỉ khi không thể restructure
- Tool: NDepend — dependency graph visualization

---

## Pattern 10: Feature Flag Stale

### Tên
Feature Flag Stale (Feature Flags Không Cleanup)

### Phân loại
Architecture / Feature Management / Technical Debt

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```
// Added 2 years ago, feature đã GA
if (await _featureManager.IsEnabledAsync("NewCheckoutFlow"))
{
    // "New" flow — actually been the only flow for 18 months
    return await NewCheckout(order);
}
else
{
    // "Old" flow — dead code, never executed
    return await LegacyCheckout(order);  ← Dead code!
}

// 50+ stale feature flags → code full of if/else branches
// No one knows which flags are active
// LegacyCheckout has security vulnerability but no one reviews it
```

### Phát hiện

```bash
# Tìm feature flag checks
rg --type cs "IsEnabledAsync|FeatureGate|_featureManager" -n

# Count unique feature flags
rg --type cs "\"[A-Z]\w+Feature\"|\"[A-Z]\w+Flag\"" -n -o | sort -u

# Tìm feature flag definitions
rg --type cs "class\s+\w+Features|static.*Feature" -n

# Tìm else branches (potential dead code)
rg --type cs "IsEnabledAsync" -A 10 | rg "else"
```

### Giải pháp

❌ **BAD**: Stale flags accumulate
```csharp
if (await _features.IsEnabledAsync("DarkMode")) // Shipped Q1 2024
if (await _features.IsEnabledAsync("NewPayment")) // Shipped Q3 2023
if (await _features.IsEnabledAsync("V2API")) // Shipped Q2 2023
// 3 flags, all always-on, dead else branches
```

✅ **GOOD**: Flag lifecycle management
```csharp
// 1. Track flag metadata
public static class FeatureFlags
{
    // Active: still toggling
    public const string BetaSearch = "BetaSearch"; // Added: 2024-01, Owner: @team-search

    // Cleanup candidates: GA for >30 days
    [Obsolete("GA since 2024-06. Remove flag and else branch.")]
    public const string NewCheckout = "NewCheckout";
}

// 2. Remove flag when GA
// Before:
if (await _features.IsEnabledAsync(FeatureFlags.NewCheckout))
    return NewCheckout(order);
else
    return LegacyCheckout(order); // Dead code

// After cleanup:
return NewCheckout(order); // Remove flag, remove dead code
```

### Phòng ngừa

- [ ] Feature flag registry with owner + date
- [ ] `[Obsolete]` cho flags that should be removed
- [ ] Sprint task: review and cleanup GA flags
- [ ] Max flag lifetime: 90 days after GA
- Tool: Custom Roslyn analyzer cho stale flags

---

## Pattern 11: Assembly Coupling

### Tên
Assembly Coupling (Domain Reference Infrastructure)

### Phân loại
Architecture / Clean Architecture / Dependency

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```
Clean Architecture Dependency Rule:

  Outer ──────────────────► Inner
  (Infrastructure)          (Domain)

  Infrastructure → Application → Domain
       │                             ▲
       └─────────────────────────────┘ OK: inward dependency

  VIOLATION:
  Domain → Infrastructure
       │         ▲
       └─────────┘ WRONG: domain depends on implementation detail!

  Domain.csproj:
    <ProjectReference Include="..\Infrastructure\Infrastructure.csproj" />
    ^^^ Domain knows about EF Core, SQL Server, etc.
```

### Phát hiện

```bash
# Check project references
rg "ProjectReference" -n --glob "*.csproj"

# Tìm Infrastructure references trong Domain
rg "Infrastructure" -n --glob "*Domain*.csproj"

# Tìm EF Core trong Domain project
rg --type cs "using Microsoft.EntityFrameworkCore" -n --glob "**/Domain/**"

# Tìm implementation details trong Domain
rg --type cs "using System.Data.SqlClient|using Npgsql|using MongoDB" -n --glob "**/Domain/**"
```

### Giải pháp

❌ **BAD**: Domain references Infrastructure
```xml
<!-- Domain.csproj -->
<ProjectReference Include="..\Infrastructure\Infrastructure.csproj" />
<!-- Domain.cs -->
using Microsoft.EntityFrameworkCore; // Framework dependency in Domain!
```

✅ **GOOD**: Proper dependency direction
```
Solution structure:
├── Domain/              (no project references, no framework deps)
│   ├── Entities/
│   ├── ValueObjects/
│   ├── Interfaces/      (IOrderRepository, IEmailService)
│   └── DomainEvents/
├── Application/         (references: Domain only)
│   ├── Services/
│   ├── Commands/
│   └── Queries/
├── Infrastructure/      (references: Domain, Application)
│   ├── Persistence/     (EF Core implementations)
│   ├── Email/
│   └── ExternalAPIs/
└── API/                 (references: Application, Infrastructure)
    ├── Controllers/
    └── Program.cs       (DI composition root)
```

### Phòng ngừa

- [ ] Domain project: ZERO external references
- [ ] Interfaces trong Domain, implementations trong Infrastructure
- [ ] Application chỉ reference Domain
- [ ] Composition Root (Program.cs) wires everything
- Tool: `NetArchTest` — architecture unit tests
- Tool: `ArchUnitNET` — enforce dependency rules

---

## Pattern 12: Background Service Lifetime

### Tên
Background Service Lifetime (IHostedService Crash Silently)

### Phân loại
Architecture / Background / Lifetime

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```
public class OrderProcessorService : BackgroundService
{
    protected override async Task ExecuteAsync(CancellationToken ct)
    {
        while (!ct.IsCancellationRequested)
        {
            var orders = await _repository.GetPendingAsync(ct);
            foreach (var order in orders)
            {
                await ProcessOrder(order, ct);  ← Exception thrown!
            }
            await Task.Delay(TimeSpan.FromSeconds(30), ct);
        }
    }
}

Unhandled exception in ExecuteAsync:
  .NET 6+: Host STOPS (IHostApplicationLifetime.StopApplication)
  .NET 5:  Exception SWALLOWED silently — service dead, no one knows
           No logs, no alerts, no restart
           Orders pile up unprocessed
```

### Phát hiện

```bash
# Tìm BackgroundService/IHostedService implementations
rg --type cs "BackgroundService|IHostedService" -n

# Tìm ExecuteAsync without try/catch
rg --type cs "ExecuteAsync" -A 20 -n | rg -v "try|catch"

# Tìm fire-and-forget tasks trong background service
rg --type cs "Task\.Run\(|_ = " -n --glob "*Service.cs" --glob "*Worker.cs"

# Check exception handling
rg --type cs "catch.*Exception" -n --glob "*Worker*.cs" --glob "*Background*.cs"
```

### Giải pháp

❌ **BAD**: No error handling in background service
```csharp
public class WorkerService : BackgroundService
{
    protected override async Task ExecuteAsync(CancellationToken ct)
    {
        while (!ct.IsCancellationRequested)
        {
            await DoWork(ct); // Exception → service dies
            await Task.Delay(30_000, ct);
        }
    }
}
```

✅ **GOOD**: Robust background service
```csharp
public class WorkerService : BackgroundService
{
    private readonly ILogger<WorkerService> _logger;
    private readonly IServiceScopeFactory _scopeFactory;

    protected override async Task ExecuteAsync(CancellationToken ct)
    {
        _logger.LogInformation("WorkerService started");

        while (!ct.IsCancellationRequested)
        {
            try
            {
                using var scope = _scopeFactory.CreateScope();
                var processor = scope.ServiceProvider
                    .GetRequiredService<IOrderProcessor>();

                await processor.ProcessPendingOrdersAsync(ct);
            }
            catch (OperationCanceledException) when (ct.IsCancellationRequested)
            {
                _logger.LogInformation("WorkerService stopping");
                break;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "WorkerService error, retrying in 60s");
                // Continue running — don't let one error kill the service
            }

            await Task.Delay(TimeSpan.FromSeconds(30), ct);
        }

        _logger.LogInformation("WorkerService stopped");
    }
}
```

### Phòng ngừa

- [ ] ALWAYS try/catch trong ExecuteAsync loop
- [ ] Scoped services via IServiceScopeFactory (background = singleton)
- [ ] Log errors with structured logging
- [ ] Health check endpoint reflects background service status
- [ ] Consider Polly retry policies
- Tool: Health checks — `IHealthCheck` for background service status
