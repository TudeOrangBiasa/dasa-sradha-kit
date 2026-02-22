# Domain 09: Thiết Kế API (API Design)

> .NET/C# patterns liên quan đến API design: Minimal API, validation, content negotiation, versioning, rate limiting.

---

## Pattern 01: Minimal API vs Controller Inconsistent

### Tên
Minimal API vs Controller Routing Inconsistent

### Phân loại
API Design / Routing / Convention

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```csharp
// Mix of Minimal API and controllers in same project:
app.MapGet("/api/users", () => ...);                    // Minimal
app.MapControllers(); // Also maps [ApiController] routes
// Confusing — which pattern to follow?
```

### Phát hiện

```bash
rg --type cs "app\.Map(Get|Post|Put|Delete)" -n
rg --type cs "\[ApiController\]" -n
rg --type cs "MapControllers" -n
```

### Giải pháp

❌ **BAD**
```csharp
// Mixed routing styles:
app.MapGet("/api/users", GetUsers);
[ApiController] [Route("api/[controller]")]
public class ProductsController : ControllerBase { }
```

✅ **GOOD**: Pick one and be consistent
```csharp
// Option 1: Controllers (complex APIs)
[ApiController]
[Route("api/[controller]")]
public class UsersController : ControllerBase
{
    [HttpGet] public async Task<IActionResult> GetAll() => Ok(await _service.GetAllAsync());
    [HttpGet("{id}")] public async Task<IActionResult> Get(int id) => Ok(await _service.GetAsync(id));
    [HttpPost] public async Task<IActionResult> Create(CreateUserDto dto) => CreatedAtAction(...);
}

// Option 2: Minimal API (simple APIs)
var users = app.MapGroup("/api/users");
users.MapGet("/", GetUsers);
users.MapGet("/{id}", GetUser);
users.MapPost("/", CreateUser);
```

### Phòng ngừa
- [ ] Pick one pattern per project
- [ ] Controllers for complex APIs with filters/auth
- [ ] Minimal API for simple/microservices
- Tool: `dotnet new webapi` templates

---

## Pattern 02: Model Validation Thiếu

### Tên
Model Validation Thiếu ([ApiController] Validation Missing)

### Phân loại
API Design / Validation / Security

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```csharp
public record CreateUserDto(string Name, string Email);
// No validation attributes!
// Name can be empty, Email can be "not-an-email"
```

### Phát hiện

```bash
rg --type cs "\[Required\]|\[StringLength\]|\[Range\]|\[EmailAddress\]" -n
rg --type cs "record\s+\w+Dto|class\s+\w+Dto" -n
rg --type cs "FluentValidation|AbstractValidator" -n
```

### Giải pháp

❌ **BAD**
```csharp
public record CreateUserDto(string Name, string Email);
// [ApiController] returns 400 for null, but not for empty string or invalid email
```

✅ **GOOD**
```csharp
// Data annotations:
public record CreateUserDto(
    [Required, StringLength(100, MinimumLength = 2)] string Name,
    [Required, EmailAddress] string Email,
    [Range(0, 150)] int? Age
);

// Or FluentValidation (more powerful):
public class CreateUserValidator : AbstractValidator<CreateUserDto>
{
    public CreateUserValidator()
    {
        RuleFor(x => x.Name).NotEmpty().MaximumLength(100);
        RuleFor(x => x.Email).NotEmpty().EmailAddress();
        RuleFor(x => x.Age).InclusiveBetween(0, 150).When(x => x.Age.HasValue);
    }
}

// Program.cs:
builder.Services.AddValidatorsFromAssemblyContaining<CreateUserValidator>();
```

### Phòng ngừa
- [ ] Data annotations or FluentValidation on ALL DTOs
- [ ] `[ApiController]` auto-validates model state
- [ ] Custom validation for business rules
- Tool: `FluentValidation`, Data Annotations

---

## Pattern 03: Content Negotiation Sai

### Tên
Content Negotiation Sai (Wrong Content-Type Handling)

### Phân loại
API Design / HTTP / Content Type

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```csharp
// Client sends: Accept: application/xml
// Server always returns JSON → 406 or unexpected format
// Or: Client sends JSON but server expects form data
```

### Phát hiện

```bash
rg --type cs "Produces|Consumes|AddXmlSerializer" -n
rg --type cs "Content-Type|Accept" -n
rg --type cs "application/json|application/xml" -n
```

### Giải pháp

❌ **BAD**
```csharp
[HttpPost]
public IActionResult Create([FromBody] CreateDto dto) { }
// What if client sends XML? Form data? No clear contract.
```

✅ **GOOD**
```csharp
[HttpPost]
[Consumes("application/json")]
[Produces("application/json")]
[ProducesResponseType<UserDto>(StatusCodes.Status201Created)]
[ProducesResponseType<ProblemDetails>(StatusCodes.Status400BadRequest)]
public async Task<IActionResult> Create([FromBody] CreateUserDto dto)
{
    var user = await _service.CreateAsync(dto);
    return CreatedAtAction(nameof(Get), new { id = user.Id }, new UserDto(user));
}
```

### Phòng ngừa
- [ ] `[Consumes]` and `[Produces]` on all endpoints
- [ ] `[ProducesResponseType]` for OpenAPI generation
- [ ] Consistent JSON-only for APIs
- Tool: Swagger/OpenAPI generation

---

## Pattern 04: API Versioning Thiếu

### Tên
API Versioning Thiếu (No Version Strategy)

### Phân loại
API Design / Versioning / Breaking Change

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```
Breaking change to /api/users response:
→ All clients break immediately
→ No migration path
```

### Phát hiện

```bash
rg --type cs "ApiVersion|MapToApiVersion|AddApiVersioning" -n
rg --type cs "/api/v\d" -n
```

### Giải pháp

❌ **BAD**
```csharp
[Route("api/users")] // No versioning
```

✅ **GOOD**
```csharp
// NuGet: Asp.Versioning.Http
builder.Services.AddApiVersioning(options =>
{
    options.DefaultApiVersion = new ApiVersion(1, 0);
    options.AssumeDefaultVersionWhenUnspecified = true;
    options.ReportApiVersions = true;
}).AddApiExplorer();

[ApiVersion(1.0)]
[Route("api/v{version:apiVersion}/users")]
public class UsersV1Controller : ControllerBase { }

[ApiVersion(2.0)]
[Route("api/v{version:apiVersion}/users")]
public class UsersV2Controller : ControllerBase { }
```

### Phòng ngừa
- [ ] Version API from day one
- [ ] `Asp.Versioning` NuGet package
- [ ] URL or header-based versioning
- Tool: `Asp.Versioning.Mvc`

---

## Pattern 05: Rate Limiting Thiếu

### Tên
Rate Limiting Thiếu (No Request Throttling)

### Phân loại
API Design / Security / DDoS

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```
No rate limiting → API abuse, brute force, DDoS
Single user can exhaust all server resources
```

### Phát hiện

```bash
rg --type cs "AddRateLimiter|UseRateLimiter|RateLimiting" -n
rg --type cs "EnableRateLimiting|DisableRateLimiting" -n
rg --type cs "429" -n
```

### Giải pháp

❌ **BAD**
```csharp
app.MapPost("/api/login", Login); // Unlimited attempts
```

✅ **GOOD**
```csharp
// ASP.NET Core 7+ built-in:
builder.Services.AddRateLimiter(options =>
{
    options.AddFixedWindowLimiter("api", opt =>
    {
        opt.PermitLimit = 100;
        opt.Window = TimeSpan.FromMinutes(1);
        opt.QueueLimit = 0;
    });

    options.AddFixedWindowLimiter("login", opt =>
    {
        opt.PermitLimit = 5;
        opt.Window = TimeSpan.FromMinutes(15);
    });

    options.RejectionStatusCode = StatusCodes.Status429TooManyRequests;
});

app.UseRateLimiter();

[EnableRateLimiting("login")]
app.MapPost("/api/login", Login);
```

### Phòng ngừa
- [ ] `AddRateLimiter` for ASP.NET Core 7+
- [ ] Per-endpoint rate policies
- [ ] Stricter limits on auth endpoints
- Tool: ASP.NET Core built-in rate limiting

---

## Pattern 06: Response Compression Thiếu

### Tên
Response Compression Thiếu (Uncompressed Responses)

### Phân loại
API Design / HTTP / Bandwidth

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```
500KB JSON response → without compression
With gzip: ~50KB (90% reduction)
```

### Phát hiện

```bash
rg --type cs "AddResponseCompression|UseResponseCompression" -n
rg --type cs "Brotli|GzipCompressionProvider" -n
```

### Giải pháp

❌ **BAD**
```csharp
// No compression configured
```

✅ **GOOD**
```csharp
builder.Services.AddResponseCompression(options =>
{
    options.EnableForHttps = true;
    options.Providers.Add<BrotliCompressionProvider>();
    options.Providers.Add<GzipCompressionProvider>();
    options.MimeTypes = ResponseCompressionDefaults.MimeTypes
        .Concat(["application/json"]);
});

app.UseResponseCompression(); // Before UseStaticFiles
```

### Phòng ngừa
- [ ] Enable response compression
- [ ] Brotli + Gzip providers
- [ ] Or let reverse proxy (nginx) handle it
- Tool: ASP.NET Core `ResponseCompression`

---

## Pattern 07: Swagger/OpenAPI Out Of Sync

### Tên
Swagger/OpenAPI Out Of Sync (Docs Don't Match Code)

### Phân loại
API Design / Documentation / Consistency

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```
Swagger shows wrong request/response schemas
→ Frontend follows wrong docs
→ Integration failures
```

### Phát hiện

```bash
rg --type cs "AddSwaggerGen|UseSwagger|AddEndpointsApiExplorer" -n
rg --type cs "SwaggerDoc|SwaggerEndpoint" -n
rg --type cs "ProducesResponseType|Produces" -n
```

### Giải pháp

❌ **BAD**
```csharp
builder.Services.AddSwaggerGen(); // Minimal config, missing schemas
```

✅ **GOOD**
```csharp
builder.Services.AddSwaggerGen(options =>
{
    options.SwaggerDoc("v1", new OpenApiInfo { Title = "My API", Version = "v1" });
    options.IncludeXmlComments(xmlFilePath); // From XML doc comments
});

// Controllers with full annotations:
/// <summary>Creates a new user</summary>
/// <param name="dto">User creation data</param>
/// <response code="201">User created successfully</response>
/// <response code="400">Invalid input</response>
[HttpPost]
[ProducesResponseType<UserDto>(201)]
[ProducesResponseType<ProblemDetails>(400)]
public async Task<IActionResult> Create(CreateUserDto dto) { }
```

### Phòng ngừa
- [ ] XML comments + `IncludeXmlComments`
- [ ] `[ProducesResponseType]` on all actions
- [ ] CI: validate OpenAPI spec
- Tool: Swashbuckle, NSwag

---

## Pattern 08: Health Check Thiếu

### Tên
Health Check Thiếu (No Health Endpoint)

### Phân loại
API Design / Operations / Monitoring

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```
K8s/load balancer needs health checks.
Without → traffic to unhealthy instances.
```

### Phát hiện

```bash
rg --type cs "AddHealthChecks|MapHealthChecks" -n
rg --type cs "IHealthCheck" -n
```

### Giải pháp

❌ **BAD**: No health endpoints

✅ **GOOD**
```csharp
builder.Services.AddHealthChecks()
    .AddSqlServer(connectionString, name: "sqlserver")
    .AddRedis(redisConnection, name: "redis")
    .AddCheck<CustomHealthCheck>("custom");

app.MapHealthChecks("/healthz", new HealthCheckOptions
{
    Predicate = _ => false, // Liveness — no dependency checks
});

app.MapHealthChecks("/readyz", new HealthCheckOptions
{
    ResponseWriter = UIResponseWriter.WriteHealthCheckUIResponse,
});
```

### Phòng ngừa
- [ ] `/healthz` for liveness (lightweight)
- [ ] `/readyz` for readiness (check dependencies)
- [ ] `AspNetCore.HealthChecks.*` NuGet packages
- Tool: HealthChecks UI, K8s probes

---

## Pattern 09: Pagination Cursor vs Offset

### Tên
Pagination Offset Performance (Deep Offset Slow)

### Phân loại
API Design / Pagination / Performance

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```csharp
var users = await _db.Users
    .Skip((page - 1) * pageSize)
    .Take(pageSize)
    .ToListAsync();
// page=1000 → Skip(20000) → DB scans 20,000 rows
```

### Phát hiện

```bash
rg --type cs "\.Skip\(|\.Take\(" -n
rg --type cs "cursor|Cursor|after|After" -i -n
```

### Giải pháp

❌ **BAD**
```csharp
.Skip((page - 1) * size).Take(size) // Slow for large offsets
```

✅ **GOOD**
```csharp
// Cursor-based (keyset pagination):
public async Task<PagedResult<UserDto>> GetUsers(int? afterId, int pageSize = 20)
{
    var query = _db.Users.AsNoTracking().OrderBy(u => u.Id);
    if (afterId.HasValue)
        query = query.Where(u => u.Id > afterId.Value);

    var users = await query.Take(pageSize + 1).ToListAsync();
    var hasMore = users.Count > pageSize;
    var data = users.Take(pageSize).Select(u => new UserDto(u)).ToList();

    return new PagedResult<UserDto>
    {
        Data = data,
        NextCursor = hasMore ? data.Last().Id : null,
        HasMore = hasMore,
    };
}
```

### Phòng ngừa
- [ ] Cursor-based for large datasets
- [ ] Offset OK for admin dashboards (<10K)
- [ ] Always include `hasMore`

---

## Pattern 10: Health Check Customization Thiếu

### Tên
Health Check Customization (Superficial Health Checks)

### Phân loại
API Design / Operations / Depth

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```csharp
app.MapHealthChecks("/health"); // Only checks if app is running
// DB down? Redis down? Disk full? → Still reports "Healthy"!
```

### Phát hiện

```bash
rg --type cs "AddHealthChecks\(\)" -A 3 -n
rg --type cs "IHealthCheck" -n
```

### Giải pháp

❌ **BAD**
```csharp
builder.Services.AddHealthChecks(); // No actual checks
```

✅ **GOOD**
```csharp
builder.Services.AddHealthChecks()
    .AddSqlServer(connStr, name: "db", tags: ["ready"])
    .AddRedis(redisConnStr, name: "cache", tags: ["ready"])
    .AddCheck("disk", () =>
    {
        var freeSpace = new DriveInfo("/").AvailableFreeSpace;
        return freeSpace > 1_000_000_000
            ? HealthCheckResult.Healthy()
            : HealthCheckResult.Degraded($"Low disk: {freeSpace / 1_000_000}MB");
    }, tags: ["ready"]);

// Separate endpoints:
app.MapHealthChecks("/healthz/live", new() { Predicate = _ => false });
app.MapHealthChecks("/healthz/ready", new() { Predicate = c => c.Tags.Contains("ready") });
```

### Phòng ngừa
- [ ] Check ALL critical dependencies
- [ ] Tag-based filtering (liveness vs readiness)
- [ ] Custom checks for business-critical resources
- Tool: `AspNetCore.HealthChecks.SqlServer`, `.Redis`, `.UI`
