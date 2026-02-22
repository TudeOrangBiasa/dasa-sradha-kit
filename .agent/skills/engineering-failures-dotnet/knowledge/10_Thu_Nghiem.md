# Domain 10: Thử Nghiệm (Testing)

> .NET/C# patterns liên quan đến testing: xUnit isolation, WebApplicationFactory, EF Core testing, mocking, Testcontainers, coverage.

---

## Pattern 01: xUnit Test Isolation Thiếu

### Tên
xUnit Test Isolation Thiếu (Shared State Between Tests)

### Phân loại
Testing / Isolation / xUnit

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```csharp
public class UserTests
{
    private static readonly List<User> _users = new(); // Shared static state!

    [Fact]
    public void TestAdd() { _users.Add(new User("Alice")); Assert.Single(_users); }

    [Fact]
    public void TestCount() { Assert.Empty(_users); } // Fails if TestAdd runs first!
}
```

### Phát hiện

```bash
rg --type cs "static.*List|static.*Dictionary|static.*=.*new" -n --glob "*Test*"
rg --type cs "IClassFixture|ICollectionFixture" -n --glob "*Test*"
```

### Giải pháp

❌ **BAD**
```csharp
public class Tests {
    private static int _counter = 0; // Shared across tests
}
```

✅ **GOOD**
```csharp
public class UserTests
{
    [Fact]
    public void TestAdd()
    {
        var users = new List<User>(); // Fresh per test
        users.Add(new User("Alice"));
        Assert.Single(users);
    }
}

// Shared expensive setup via IClassFixture:
public class DatabaseFixture : IAsyncLifetime
{
    public DbContext Db { get; private set; } = null!;
    public async Task InitializeAsync() { Db = await CreateTestDb(); }
    public async Task DisposeAsync() { await Db.DisposeAsync(); }
}

public class UserTests : IClassFixture<DatabaseFixture>
{
    private readonly DatabaseFixture _fixture;
    public UserTests(DatabaseFixture fixture) => _fixture = fixture;
}
```

### Phòng ngừa
- [ ] No static mutable state in test classes
- [ ] `IClassFixture<T>` for shared setup within a class
- [ ] `ICollectionFixture<T>` for shared setup across classes
- Tool: xUnit, `IAsyncLifetime`

---

## Pattern 02: WebApplicationFactory Misuse

### Tên
WebApplicationFactory Misuse (Integration Test Without Proper Setup)

### Phân loại
Testing / Integration / ASP.NET

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```csharp
// Creating real HttpClient to real running server:
var client = new HttpClient { BaseAddress = new Uri("http://localhost:5000") };
var response = await client.GetAsync("/api/users");
// Requires server running, port conflicts, environment issues
```

### Phát hiện

```bash
rg --type cs "WebApplicationFactory|CreateClient" -n --glob "*Test*"
rg --type cs "new HttpClient" -n --glob "*Test*"
rg --type cs "WithWebHostBuilder" -n
```

### Giải pháp

❌ **BAD**
```csharp
var client = new HttpClient(); // Real HTTP to running server
```

✅ **GOOD**
```csharp
public class UserApiTests : IClassFixture<WebApplicationFactory<Program>>
{
    private readonly HttpClient _client;

    public UserApiTests(WebApplicationFactory<Program> factory)
    {
        _client = factory.WithWebHostBuilder(builder =>
        {
            builder.ConfigureServices(services =>
            {
                // Replace real DB with in-memory:
                services.RemoveAll<DbContextOptions<AppDbContext>>();
                services.AddDbContext<AppDbContext>(o => o.UseInMemoryDatabase("test"));
            });
        }).CreateClient();
    }

    [Fact]
    public async Task GetUsers_ReturnsOk()
    {
        var response = await _client.GetAsync("/api/users");
        response.EnsureSuccessStatusCode();
        var users = await response.Content.ReadFromJsonAsync<List<UserDto>>();
        Assert.NotNull(users);
    }
}
```

### Phòng ngừa
- [ ] `WebApplicationFactory<Program>` for integration tests
- [ ] Override services for test dependencies
- [ ] `CreateClient()` for in-memory HTTP
- Tool: `Microsoft.AspNetCore.Mvc.Testing`

---

## Pattern 03: EF Core InMemory vs SQLite

### Tên
EF Core InMemory Limitations (InMemory Provider Thiếu Features)

### Phân loại
Testing / Database / EF Core

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```csharp
services.AddDbContext<AppDb>(o => o.UseInMemoryDatabase("test"));
// InMemory doesn't enforce: constraints, transactions, SQL queries
// Test passes but production fails on FK violation
```

### Phát hiện

```bash
rg --type cs "UseInMemoryDatabase" -n --glob "*Test*"
rg --type cs "UseSqlite.*:memory:|DataSource=:memory:" -n
rg --type cs "Testcontainers|PostgreSql|SqlServer" -n --glob "*Test*"
```

### Giải pháp

❌ **BAD**
```csharp
options.UseInMemoryDatabase("test"); // No constraints, no FK, no SQL
```

✅ **GOOD**
```csharp
// SQLite in-memory (enforces constraints):
public static DbContextOptions<AppDbContext> CreateSqliteOptions()
{
    var connection = new SqliteConnection("DataSource=:memory:");
    connection.Open(); // Must stay open for lifetime

    var options = new DbContextOptionsBuilder<AppDbContext>()
        .UseSqlite(connection)
        .Options;

    using var ctx = new AppDbContext(options);
    ctx.Database.EnsureCreated();
    return options;
}

// Or Testcontainers for real DB:
public class DbFixture : IAsyncLifetime
{
    private readonly PostgreSqlContainer _container = new PostgreSqlBuilder()
        .WithImage("postgres:16").Build();

    public string ConnectionString => _container.GetConnectionString();
    public Task InitializeAsync() => _container.StartAsync();
    public Task DisposeAsync() => _container.DisposeAsync().AsTask();
}
```

### Phòng ngừa
- [ ] SQLite in-memory for constraint testing
- [ ] Testcontainers for production-like DB
- [ ] InMemory only for simple unit tests
- Tool: `Testcontainers.PostgreSql`, SQLite

---

## Pattern 04: Mock DbContext Anti-Pattern

### Tên
Mock DbContext Anti-Pattern (Mocking EF Core DbContext)

### Phân loại
Testing / Mocking / EF Core

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```csharp
var mockDb = new Mock<AppDbContext>();
mockDb.Setup(x => x.Users).Returns(MockDbSet(users));
// Mocking DbSet is complex, fragile, and doesn't test real EF behavior
// SaveChanges, Include, navigation properties all differ
```

### Phát hiện

```bash
rg --type cs "Mock<.*DbContext>|Mock<.*DbSet>" -n --glob "*Test*"
rg --type cs "MockDbSet|CreateMockSet" -n
```

### Giải pháp

❌ **BAD**
```csharp
var mockSet = new Mock<DbSet<User>>();
mockSet.As<IQueryable<User>>().Setup(m => m.Provider).Returns(...);
// 20 lines of fragile mock setup
```

✅ **GOOD**
```csharp
// Use real DbContext with SQLite or InMemory:
public class UserServiceTests
{
    private AppDbContext CreateContext()
    {
        var options = new DbContextOptionsBuilder<AppDbContext>()
            .UseSqlite("DataSource=:memory:").Options;
        var ctx = new AppDbContext(options);
        ctx.Database.OpenConnection();
        ctx.Database.EnsureCreated();
        return ctx;
    }

    [Fact]
    public async Task GetUser_ReturnsUser()
    {
        await using var ctx = CreateContext();
        ctx.Users.Add(new User { Name = "Alice" });
        await ctx.SaveChangesAsync();

        var service = new UserService(ctx);
        var user = await service.GetByNameAsync("Alice");
        Assert.NotNull(user);
    }
}
```

### Phòng ngừa
- [ ] Real DbContext with SQLite for service tests
- [ ] Mock repository interface, not DbContext
- [ ] Integration tests with real DB for complex queries
- Tool: SQLite in-memory, Repository pattern

---

## Pattern 05: Moq Setup Incomplete

### Tên
Moq Setup Incomplete (Missing Mock Configurations)

### Phân loại
Testing / Mocking / Moq

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```csharp
var mock = new Mock<IUserService>();
mock.Setup(x => x.GetAsync(1)).ReturnsAsync(new User { Name = "Alice" });
// But test calls GetAsync(2) → returns null → NullReferenceException
// Not a test failure — it's a mock configuration gap
```

### Phát hiện

```bash
rg --type cs "new Mock<" -n --glob "*Test*"
rg --type cs "\.Setup\(" -n --glob "*Test*"
rg --type cs "MockBehavior\.Strict" -n
```

### Giải pháp

❌ **BAD**
```csharp
var mock = new Mock<IService>(); // Loose behavior — returns defaults silently
mock.Setup(x => x.Get(1)).Returns(result);
// Get(2) returns null without warning
```

✅ **GOOD**
```csharp
// Strict mode — fails on unconfigured calls:
var mock = new Mock<IUserService>(MockBehavior.Strict);
mock.Setup(x => x.GetAsync(It.IsAny<int>()))
    .ReturnsAsync((int id) => new User { Id = id, Name = $"User{id}" });

// Verify interactions:
mock.Verify(x => x.GetAsync(1), Times.Once);
mock.VerifyNoOtherCalls();

// Or use NSubstitute for cleaner syntax:
var service = Substitute.For<IUserService>();
service.GetAsync(Arg.Any<int>()).Returns(x => new User { Id = (int)x[0] });
```

### Phòng ngừa
- [ ] `MockBehavior.Strict` for critical mocks
- [ ] `It.IsAny<T>()` for flexible matching
- [ ] `Verify` + `VerifyNoOtherCalls` for completeness
- Tool: Moq, NSubstitute, FakeItEasy

---

## Pattern 06: Integration Test DB Cleanup

### Tên
Integration Test DB Cleanup Thiếu (Test Data Leaks)

### Phân loại
Testing / Integration / Cleanup

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```csharp
[Fact]
public async Task CreateUser_Succeeds()
{
    await _client.PostAsJsonAsync("/api/users", new { Name = "Alice" });
    // Data persists — next test sees it
}
```

### Phát hiện

```bash
rg --type cs "Respawn|respawner|Checkpoint" -n --glob "*Test*"
rg --type cs "EnsureDeleted|Database\.Migrate" -n --glob "*Test*"
```

### Giải pháp

❌ **BAD**: No cleanup between integration tests

✅ **GOOD**
```csharp
// Using Respawn for fast DB cleanup:
public class IntegrationTestBase : IAsyncLifetime
{
    private Respawner _respawner = null!;
    protected HttpClient Client { get; private set; } = null!;

    public async Task InitializeAsync()
    {
        _respawner = await Respawner.CreateAsync(_connectionString, new RespawnerOptions
        {
            TablesToIgnore = ["__EFMigrationsHistory"],
            WithReseed = true,
        });
    }

    public async Task DisposeAsync()
    {
        await _respawner.ResetAsync(_connectionString); // Clean after each test
    }
}
```

### Phòng ngừa
- [ ] `Respawn` for fast DB reset between tests
- [ ] Transaction rollback for unit tests
- [ ] Testcontainers for complete isolation
- Tool: `Respawn`, `Testcontainers`

---

## Pattern 07: Testcontainers Không Dùng

### Tên
Testcontainers Không Dùng (No Container-Based Testing)

### Phân loại
Testing / Infrastructure / Containers

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```
Integration tests require:
- SQL Server running locally
- Redis running locally
- Specific versions matching production
→ "Works on my machine" — CI fails, new devs can't run tests
```

### Phát hiện

```bash
rg --type cs "Testcontainers|IContainer|DockerContainer" -n
rg --type cs "localhost.*5432|localhost.*1433|localhost.*6379" -n --glob "*Test*"
```

### Giải pháp

❌ **BAD**: Tests depend on locally installed services

✅ **GOOD**
```csharp
public class DatabaseFixture : IAsyncLifetime
{
    private readonly MsSqlContainer _container = new MsSqlBuilder()
        .WithImage("mcr.microsoft.com/mssql/server:2022-latest")
        .Build();

    public string ConnectionString => _container.GetConnectionString();

    public async Task InitializeAsync()
    {
        await _container.StartAsync();
        // Run migrations:
        var options = new DbContextOptionsBuilder<AppDbContext>()
            .UseSqlServer(ConnectionString).Options;
        await using var ctx = new AppDbContext(options);
        await ctx.Database.MigrateAsync();
    }

    public Task DisposeAsync() => _container.DisposeAsync().AsTask();
}

[CollectionDefinition("Database")]
public class DatabaseCollection : ICollectionFixture<DatabaseFixture> { }

[Collection("Database")]
public class UserRepositoryTests(DatabaseFixture db)
{
    [Fact]
    public async Task FindUser_Works()
    {
        await using var ctx = new AppDbContext(db.ConnectionString);
        // Test with real SQL Server
    }
}
```

### Phòng ngừa
- [ ] Testcontainers for all external dependencies
- [ ] `ICollectionFixture` to share containers across tests
- [ ] Same DB engine as production
- Tool: `Testcontainers.MsSql`, `.PostgreSql`, `.Redis`

---

## Pattern 08: FluentAssertions Thiếu

### Tên
FluentAssertions Custom Assertion Thiếu

### Phân loại
Testing / Assertions / Readability

### Mức nghiêm trọng
LOW 🟢

### Vấn đề

```csharp
Assert.True(result.IsSuccess); // "Expected: True, Actual: False" — no context
Assert.Equal("Alice", user.Name);
Assert.True(user.Age > 0 && user.Age < 150); // Complex assertion, poor message
```

### Phát hiện

```bash
rg --type cs "Assert\.True|Assert\.Equal|Assert\.NotNull" -n --glob "*Test*"
rg --type cs "FluentAssertions|\.Should\(\)" -n --glob "*Test*"
```

### Giải pháp

❌ **BAD**
```csharp
Assert.True(users.Count > 0); // "Expected True"
```

✅ **GOOD**
```csharp
using FluentAssertions;

users.Should().NotBeEmpty("because we seeded 5 users");
user.Name.Should().Be("Alice");
user.Age.Should().BeInRange(0, 150);
result.Should().BeOfType<OkObjectResult>()
    .Which.Value.Should().BeAssignableTo<UserDto>();

// Collection assertions:
orders.Should().HaveCount(5)
    .And.OnlyContain(o => o.Total > 0)
    .And.BeInAscendingOrder(o => o.CreatedAt);
```

### Phòng ngừa
- [ ] FluentAssertions for readable test failures
- [ ] Descriptive `because` messages
- [ ] Chained assertions for complex checks
- Tool: `FluentAssertions` NuGet

---

## Pattern 09: Test Parallelism Conflict

### Tên
Test Parallelism Conflict (xUnit Parallel Execution Issues)

### Phân loại
Testing / Parallel / xUnit

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```csharp
// xUnit runs test classes in parallel by default
// Two test classes writing to same DB table → race condition
// Or accessing same file/port → conflict
```

### Phát hiện

```bash
rg --type cs "\[Collection\(" -n --glob "*Test*"
rg --type cs "DisableTestParallelization" -n
rg --type cs "xunit\.runner\.json|parallelizeTestCollections" -n
```

### Giải pháp

❌ **BAD**
```json
// xunit.runner.json: disable ALL parallelism (slow)
{ "parallelizeTestCollections": false }
```

✅ **GOOD**
```csharp
// Group tests that share state into collections:
[CollectionDefinition("Database", DisableParallelization = true)]
public class DatabaseCollection : ICollectionFixture<DatabaseFixture> { }

[Collection("Database")]
public class UserTests { /* Runs sequentially with other "Database" tests */ }

[Collection("Database")]
public class OrderTests { /* Same collection — no parallel with UserTests */ }

// Tests NOT in a collection still run in parallel — fast!
public class UtilityTests { /* Runs parallel with everything */ }
```

### Phòng ngừa
- [ ] Collections for shared-state tests only
- [ ] Keep pure unit tests collection-free (parallel)
- [ ] Per-test database isolation over disabling parallelism
- Tool: xUnit collections, `xunit.runner.json`

---

## Pattern 10: Coverage Misleading

### Tên
Code Coverage Misleading (Branch vs Line Coverage)

### Phân loại
Testing / Coverage / Quality

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```csharp
// 90% line coverage but:
public decimal CalculateDiscount(User user)
{
    if (user.IsPremium && user.YearsActive > 5) return 0.3m; // Never tested
    if (user.IsPremium) return 0.2m;
    return 0m;
}
// Only tested: IsPremium=true, IsPremium=false
// Never tested: IsPremium=true AND YearsActive > 5
```

### Phát hiện

```bash
rg --type cs "coverlet|coverageThreshold" -n --glob "*.csproj"
rg --type cs "CollectCoverage|ThresholdType" -n --glob "*.props"
```

### Giải pháp

❌ **BAD**
```xml
<!-- Only line coverage threshold -->
<ThresholdType>line</ThresholdType>
```

✅ **GOOD**
```xml
<!-- Directory.Build.props: -->
<PropertyGroup>
    <CollectCoverage>true</CollectCoverage>
    <CoverletOutputFormat>cobertura</CoverletOutputFormat>
    <ThresholdType>line,branch,method</ThresholdType>
    <Threshold>80</Threshold>
    <ExcludeByFile>**/Migrations/**,**/*.Designer.cs</ExcludeByFile>
</PropertyGroup>
```

```bash
# CI:
dotnet test --collect:"XPlat Code Coverage" -- DataCollectionRunSettings.DataCollectors.DataCollector.Configuration.Format=cobertura
# Generate report:
reportgenerator -reports:coverage.cobertura.xml -targetdir:coverage-report
```

### Phòng ngừa
- [ ] Branch coverage threshold (not just lines)
- [ ] Exclude migrations, generated code
- [ ] Mutation testing with `Stryker.NET`
- Tool: Coverlet, ReportGenerator, Stryker.NET
