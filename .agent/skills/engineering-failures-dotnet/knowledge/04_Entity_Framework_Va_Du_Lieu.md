# Domain 04: Entity Framework Và Dữ Liệu (EF Core & Data)
# Domain 04: Entity Framework & Data Access Patterns

**Lĩnh vực:** .NET Engineering - Data Access / ORM
**Ngôn ngữ:** C#
**Tổng số patterns:** 14
**Cập nhật:** 2026-02-18

---

## Tổng Quan Domain

Entity Framework Core là ORM phổ biến nhất trong hệ sinh thái .NET, nhưng cũng là nguồn gốc của vô số lỗi hiệu năng và data integrity trong production. Hầu hết các lỗi EF Core không xuất hiện trong môi trường phát triển với dữ liệu nhỏ, nhưng bùng phát khi cơ sở dữ liệu có hàng triệu bản ghi hoặc nhiều người dùng đồng thời.

```
PHÂN LOẠI MỨC ĐỘ NGHIÊM TRỌNG
================================
CRITICAL  - Có thể gây crash ứng dụng, SQL injection, mất dữ liệu toàn bộ
HIGH      - Gây suy giảm hiệu năng nghiêm trọng, race condition, data loss
MEDIUM    - Gây memory leak, query chậm, kết quả không nhất quán
LOW       - Code smell, vi phạm best practice
```

---

## Pattern 01: N+1 Query (Lazy Loading)

### 1. Tên
**N+1 Query Problem** (Lazy Loading Implicit)

### 2. Phân Loại
- **Domain:** Entity Framework Core / Query Performance
- **Subcategory:** Lazy Loading / Select N+1

### 3. Mức Nghiêm Trọng
**HIGH** ⚠️ - Gây suy giảm hiệu năng nghiêm trọng, N queries thay vì 1

### 4. Vấn Đề

N+1 là lỗi phổ biến nhất với EF Core. Thay vì tải dữ liệu liên quan trong một query duy nhất, ứng dụng thực hiện 1 query lấy danh sách + N query riêng lẻ cho mỗi phần tử.

```
N+1 QUERY FLOW (100 Orders)
============================

SELECT * FROM Orders                    ← 1 query

foreach (order in orders)
{
    SELECT * FROM Customers             ← query #1
    WHERE CustomerId = order.CustomerId

    SELECT * FROM Customers             ← query #2
    WHERE CustomerId = order.CustomerId

    ...                                 ← query #3 ... #100
}

TỔNG: 1 + 100 = 101 queries
Thay vì: 1 query với JOIN

KẾT QUẢ:
- 100 orders  → 101 queries
- 1000 orders → 1001 queries
- 10000 orders → 10001 queries (TIMEOUT / OOM)
```

**Tại sao Lazy Loading gây ra vấn đề này:**

```
Lazy Loading BẬT (virtual navigation property)
    ↓
Truy cập order.Customer khi chưa load
    ↓
EF Core tự động gửi query đến DB
    ↓
Lặp lại N lần trong vòng lặp
    ↓
N+1 queries không kiểm soát được
```

### 5. Phát Hiện Trong Mã Nguồn

**Dấu hiệu nhận biết:**
- Nhiều query giống nhau xuất hiện trong SQL Profiler / EF logs
- Vòng lặp `foreach` truy cập navigation properties
- Navigation properties được khai báo `virtual`
- Response time tăng tuyến tính theo số bản ghi

**Regex patterns cho ripgrep:**

```bash
# Tìm virtual navigation properties (dấu hiệu lazy loading)
rg "public\s+virtual\s+\w+" --type cs

# Tìm vòng lặp foreach truy cập navigation property
rg "foreach.*\)\s*\{" -A 5 --type cs | rg "\.\w+\.\w+"

# Tìm truy cập property sau khi load collection
rg "\.(Include|ToList|ToArray)\(\).*\n.*foreach" --multiline --type cs

# Tìm configuration bật lazy loading
rg "UseLazyLoadingProxies|LazyLoadingEnabled" --type cs
```

### 6. Giải Pháp

**Ví dụ SAI:**

```csharp
// BAD: Lazy loading - N+1 queries
public class OrderService
{
    public async Task<List<OrderDto>> GetOrdersAsync()
    {
        // Query 1: Load tất cả orders
        var orders = await _context.Orders.ToListAsync();

        var result = new List<OrderDto>();
        foreach (var order in orders)
        {
            // Query 2...N+1: Mỗi lần truy cập Customer -> 1 query riêng
            result.Add(new OrderDto
            {
                Id = order.Id,
                CustomerName = order.Customer.Name,      // ← LAZY LOAD: 1 query
                CustomerEmail = order.Customer.Email,    // ← cached, không query thêm
                TotalItems = order.Items.Count,          // ← LAZY LOAD: 1 query nữa
            });
        }
        return result;
    }
}

// BAD: Entity với virtual properties bật lazy loading
public class Order
{
    public int Id { get; set; }
    public int CustomerId { get; set; }
    public virtual Customer Customer { get; set; }  // ← LAZY LOADING
    public virtual ICollection<OrderItem> Items { get; set; }  // ← LAZY LOADING
}
```

**Ví dụ ĐÚNG:**

```csharp
// GOOD: Eager loading với Include - 1 query duy nhất
public class OrderService
{
    public async Task<List<OrderDto>> GetOrdersAsync()
    {
        var orders = await _context.Orders
            .Include(o => o.Customer)      // ← JOIN Customer trong 1 query
            .Include(o => o.Items)         // ← JOIN Items trong 1 query
            .Select(o => new OrderDto      // ← Project ngay tại DB (tốt nhất)
            {
                Id = o.Id,
                CustomerName = o.Customer.Name,
                CustomerEmail = o.Customer.Email,
                TotalItems = o.Items.Count,
            })
            .ToListAsync();

        return orders;
    }
}

// GOOD: Dùng AsSplitQuery cho nhiều collections
public async Task<List<OrderDto>> GetOrdersWithDetailAsync()
{
    return await _context.Orders
        .Include(o => o.Customer)
        .Include(o => o.Items)
            .ThenInclude(i => i.Product)
        .AsSplitQuery()  // ← Tránh Cartesian Explosion khi nhiều collections
        .Select(o => new OrderDto { ... })
        .ToListAsync();
}

// GOOD: Tắt lazy loading hoàn toàn trong DbContext
protected override void OnConfiguring(DbContextOptionsBuilder options)
{
    options.UseSqlServer(connectionString)
           .UseLazyLoadingProxies(false); // ← Tắt lazy loading
}
```

### 7. Phòng Ngừa

```csharp
// Roslyn Analyzer: Bật EF Core query logging để phát hiện N+1
builder.Services.AddDbContext<AppDbContext>(options =>
{
    options.UseSqlServer(connectionString)
           .EnableSensitiveDataLogging() // ← Chỉ dùng Development
           .LogTo(Console.WriteLine, LogLevel.Information); // ← Xem queries
});

// EF Core 7+: Dùng DbContext logging để đếm queries
// Nếu thấy > 2 queries giống nhau trong 1 request -> N+1

// Analyzer: Microsoft.EntityFrameworkCore.Analyzers (built-in)
// EF Power Tools: Reverse Engineer + Query Analyzer
```

---

## Pattern 02: Tracking Query Không Cần (AsNoTracking Missing)

### 1. Tên
**Unnecessary Change Tracking** (AsNoTracking Missing)

### 2. Phân Loại
- **Domain:** Entity Framework Core / Performance
- **Subcategory:** Change Tracking / Memory Overhead

### 3. Mức Nghiêm Trọng
**MEDIUM** ⚡ - Gây memory overhead, query chậm hơn 30-50% cho read-only operations

### 4. Vấn Đề

Mặc định EF Core theo dõi (track) tất cả entities được load từ database để phát hiện thay đổi khi `SaveChanges()`. Với các read-only queries, việc tracking này lãng phí bộ nhớ và thời gian CPU.

```
TRACKING QUERY (mặc định)
==========================
Query DB → Load entities → Store snapshot → Add to ChangeTracker
                                ↓
                    Memory: 2x (entity + snapshot)
                    CPU: Phải so sánh tất cả properties khi SaveChanges
                    GC Pressure tăng

NO-TRACKING QUERY (AsNoTracking)
=================================
Query DB → Load entities → Return (không store)
                ↓
            Memory: 1x
            CPU: Không overhead khi SaveChanges
            Faster: ~20-30%
```

### 5. Phát Hiện Trong Mã Nguồn

**Dấu hiệu nhận biết:**
- Query dùng để đọc dữ liệu nhưng không có `AsNoTracking()`
- Method tên là `Get`, `List`, `Find`, `Search` nhưng không AsNoTracking
- Report/export queries load lượng lớn dữ liệu

**Regex patterns cho ripgrep:**

```bash
# Tìm queries không có AsNoTracking (có thể là read-only)
rg "\.Where\(|\.ToList\(|\.ToListAsync\(" --type cs | rg -v "AsNoTracking"

# Tìm Get/Find methods không dùng AsNoTracking
rg "public.*async.*Task.*Get\w+\(" -A 10 --type cs | rg -v "AsNoTracking"

# Tìm tất cả nơi dùng AsNoTracking (để biết codebase awareness)
rg "AsNoTracking\(\)" --type cs

# Tìm SELECT queries lớn (report/export) thiếu AsNoTracking
rg "\.(OrderBy|Skip|Take)\(" -B 5 --type cs | rg -v "AsNoTracking"
```

### 6. Giải Pháp

**Ví dụ SAI:**

```csharp
// BAD: Read-only query với tracking mặc định
public class ProductService
{
    public async Task<List<ProductDto>> GetProductsForCatalogAsync()
    {
        // EF sẽ track tất cả 10,000 products -> memory overhead
        var products = await _context.Products
            .Where(p => p.IsActive)
            .Include(p => p.Category)
            .ToListAsync();  // ← Tracking ON - lãng phí bộ nhớ

        return products.Select(p => new ProductDto
        {
            Id = p.Id,
            Name = p.Name,
            CategoryName = p.Category.Name
        }).ToList();
    }
}
```

**Ví dụ ĐÚNG:**

```csharp
// GOOD: AsNoTracking cho read-only queries
public class ProductService
{
    public async Task<List<ProductDto>> GetProductsForCatalogAsync()
    {
        // Không track vì không cần SaveChanges
        var products = await _context.Products
            .AsNoTracking()  // ← Tắt tracking
            .Where(p => p.IsActive)
            .Include(p => p.Category)
            .Select(p => new ProductDto  // ← Project tại DB, không cần Include
            {
                Id = p.Id,
                Name = p.Name,
                CategoryName = p.Category.Name
            })
            .ToListAsync();

        return products;
    }
}

// GOOD: Cấu hình mặc định NoTracking cho toàn bộ context (read-only service)
public class ReadOnlyDbContext : DbContext
{
    public ReadOnlyDbContext(DbContextOptions options) : base(options)
    {
        ChangeTracker.QueryTrackingBehavior = QueryTrackingBehavior.NoTracking;
    }
}

// GOOD: AsNoTrackingWithIdentityResolution (EF 5+) khi cần dedup
var orders = await _context.Orders
    .AsNoTrackingWithIdentityResolution()  // ← NoTracking nhưng dedup objects
    .Include(o => o.Customer)
    .ToListAsync();
```

### 7. Phòng Ngừa

```csharp
// Repository pattern: bắt buộc AsNoTracking cho query methods
public interface IReadRepository<T> where T : class
{
    IQueryable<T> GetQueryable();  // Luôn AsNoTracking bên trong
}

public class ReadRepository<T> : IReadRepository<T> where T : class
{
    private readonly DbContext _context;

    public IQueryable<T> GetQueryable()
        => _context.Set<T>().AsNoTracking();  // ← Enforce tại base
}

// Roslyn Rule: Tự viết analyzer hoặc dùng code review checklist
// EF Core Analyzers: chưa có built-in rule cho điều này
// -> Dùng Architecture Tests (ArchUnitNET) để enforce
```

---

## Pattern 03: DbContext Lifetime Sai (Singleton Instead of Scoped)

### 1. Tên
**DbContext Singleton Lifetime** (Wrong DI Lifetime)

### 2. Phân Loại
- **Domain:** Entity Framework Core / Dependency Injection
- **Subcategory:** DbContext Lifetime / Concurrency

### 3. Mức Nghiêm Trọng
**CRITICAL** 💀 - Gây race condition, data corruption, exception không kiểm soát được

### 4. Vấn Đề

`DbContext` KHÔNG phải thread-safe. Nếu đăng ký DbContext là Singleton, tất cả requests sẽ dùng chung một instance, dẫn đến race condition nghiêm trọng.

```
SINGLETON DBCONTEXT (SAI)
==========================

Request A ──────────────┐
                        ├──► DbContext (shared) ◄──── RACE CONDITION!
Request B ──────────────┘
     │                              │
     │ A và B cùng lúc:             │
     │ - A đang SaveChanges()       │
     │ - B đang thay đổi entities   │
     │                              ▼
     │                    ❌ InvalidOperationException
     │                    ❌ Data corruption
     │                    ❌ "A second operation was started on this context"

SCOPED DBCONTEXT (ĐÚNG)
=========================
Request A ──► DbContext Instance A (riêng biệt, dispose khi request kết thúc)
Request B ──► DbContext Instance B (riêng biệt, thread-safe)
```

### 5. Phát Hiện Trong Mã Nguồn

**Dấu hiệu nhận biết:**
- `AddSingleton<DbContext>` hoặc `AddSingleton<AppDbContext>`
- Exception: "A second operation was started on this context instance before a previous operation completed"
- Lỗi chỉ xuất hiện dưới tải concurrent cao
- Dữ liệu bị sai sau khi nhiều users cùng thao tác

**Regex patterns cho ripgrep:**

```bash
# Tìm DbContext đăng ký sai lifetime
rg "AddSingleton.*Context|AddTransient.*Context" --type cs

# Tìm DbContext đúng cách (để xác nhận pattern đúng)
rg "AddDbContext|AddScoped.*Context" --type cs

# Tìm DbContext được inject vào Singleton services (captive dependency)
rg "private\s+readonly\s+\w+Context" --type cs -B 5

# Tìm DbContext trong hosted services (cần IServiceScope)
rg "class\s+\w+\s*:\s*(BackgroundService|IHostedService)" -A 20 --type cs
```

### 6. Giải Pháp

**Ví dụ SAI:**

```csharp
// BAD: DbContext đăng ký là Singleton
public static class ServiceCollectionExtensions
{
    public static void AddDataServices(this IServiceCollection services, string connectionString)
    {
        // ❌ CRITICAL: DbContext KHÔNG phải thread-safe!
        services.AddSingleton<AppDbContext>(sp =>
        {
            var options = new DbContextOptionsBuilder<AppDbContext>()
                .UseSqlServer(connectionString)
                .Options;
            return new AppDbContext(options);
        });
    }
}

// BAD: Inject DbContext vào Singleton service (captive dependency)
public class CacheService  // Singleton
{
    private readonly AppDbContext _context;  // ← DbContext bị "capture" vào Singleton!

    public CacheService(AppDbContext context)
    {
        _context = context;  // ← Scoped được inject vào Singleton = Singleton effective
    }
}
```

**Ví dụ ĐÚNG:**

```csharp
// GOOD: AddDbContext tự động đăng ký Scoped
public static class ServiceCollectionExtensions
{
    public static void AddDataServices(this IServiceCollection services, string connectionString)
    {
        // ✅ Scoped theo mặc định - mỗi request một instance mới
        services.AddDbContext<AppDbContext>(options =>
            options.UseSqlServer(connectionString));
    }
}

// GOOD: DbContext trong Singleton service - dùng IServiceScopeFactory
public class CacheService  // Singleton
{
    private readonly IServiceScopeFactory _scopeFactory;

    public CacheService(IServiceScopeFactory scopeFactory)
    {
        _scopeFactory = scopeFactory;
    }

    public async Task RefreshCacheAsync()
    {
        // Tạo scope mới cho mỗi lần cần DbContext
        await using var scope = _scopeFactory.CreateAsyncScope();
        var context = scope.ServiceProvider.GetRequiredService<AppDbContext>();

        var data = await context.Products.AsNoTracking().ToListAsync();
        // ... cập nhật cache
    }  // ← DbContext disposed khi scope kết thúc
}

// GOOD: BackgroundService cũng cần IServiceScopeFactory
public class DataSyncService : BackgroundService
{
    private readonly IServiceScopeFactory _scopeFactory;

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        while (!stoppingToken.IsCancellationRequested)
        {
            await using var scope = _scopeFactory.CreateAsyncScope();
            var context = scope.ServiceProvider.GetRequiredService<AppDbContext>();
            // ... sử dụng context

            await Task.Delay(TimeSpan.FromMinutes(5), stoppingToken);
        }
    }
}
```

### 7. Phòng Ngừa

```csharp
// EF Core tự động phát hiện captive dependency khi Development
// Bật ValidateScopes để phát hiện sớm:
builder.Host.UseDefaultServiceProvider(options =>
{
    options.ValidateScopes = true;           // ← Phát hiện captive dependency
    options.ValidateOnBuild = true;          // ← Validate khi build
});

// Test kiểm tra lifetime đăng ký
[Fact]
public void DbContext_ShouldBeRegisteredAsScoped()
{
    var descriptor = _services.FirstOrDefault(d => d.ServiceType == typeof(AppDbContext));
    Assert.Equal(ServiceLifetime.Scoped, descriptor?.Lifetime);
}
```

---

## Pattern 04: Migration Rollback Thiếu (Empty Down)

### 1. Tên
**Empty Migration Down Method** (Missing Rollback)

### 2. Phân Loại
- **Domain:** Entity Framework Core / Migrations
- **Subcategory:** Schema Management / Rollback

### 3. Mức Nghiêm Trọng
**MEDIUM** ⚡ - Không rollback được migration khi cần, gây downtime kéo dài

### 4. Vấn Đề

EF Core migration tự động generate `Up()` nhưng đôi khi `Down()` bị để trống hoặc thiếu logic. Khi cần rollback sau deploy lỗi, không thể reverse schema change.

```
MIGRATION LIFECYCLE
====================

Deploy mới:
Code → Add-Migration → Up() chạy → Schema thay đổi → App hoạt động

Rollback sau deploy lỗi:
App lỗi → Cần rollback → Down() chạy → ???

Nếu Down() trống:
    Down() { } ← Không làm gì
         ↓
    Schema KHÔNG được restore
         ↓
    App cũ không tương thích với schema mới
         ↓
    DOWNTIME kéo dài, manual fix DB
```

### 5. Phát Hiện Trong Mã Nguồn

**Dấu hiệu nhận biết:**
- Method `Down()` có thân rỗng hoặc chỉ có comment
- Migration có `Up()` phức tạp nhưng `Down()` đơn giản bất thường
- Không có test cho migration rollback

**Regex patterns cho ripgrep:**

```bash
# Tìm migration Down() rỗng
rg "protected\s+override\s+void\s+Down.*\{\s*\}" --type cs --multiline

# Tìm Down() chỉ có comment
rg "void Down\(MigrationBuilder migrationBuilder\)" -A 5 --type cs

# Tìm tất cả migration files để review
rg "CreateTable|AddColumn|DropTable" --type cs -l

# Tìm migration không có throw hoặc action trong Down
rg "Down\(MigrationBuilder" -A 3 --type cs | rg -v "(DropTable|DropColumn|AlterColumn|CreateTable)"
```

### 6. Giải Pháp

**Ví dụ SAI:**

```csharp
// BAD: Down() bị để trống - không rollback được
public partial class AddDoctorSpecialty : Migration
{
    protected override void Up(MigrationBuilder migrationBuilder)
    {
        migrationBuilder.AddColumn<string>(
            name: "Specialty",
            table: "Doctors",
            type: "nvarchar(100)",
            nullable: true);

        migrationBuilder.CreateIndex(
            name: "IX_Doctors_Specialty",
            table: "Doctors",
            column: "Specialty");
    }

    protected override void Down(MigrationBuilder migrationBuilder)
    {
        // TODO: Add rollback logic
        // ← KHÔNG làm gì cả! Rollback sẽ không có tác dụng
    }
}
```

**Ví dụ ĐÚNG:**

```csharp
// GOOD: Down() là mirror của Up() theo thứ tự ngược lại
public partial class AddDoctorSpecialty : Migration
{
    protected override void Up(MigrationBuilder migrationBuilder)
    {
        migrationBuilder.AddColumn<string>(
            name: "Specialty",
            table: "Doctors",
            type: "nvarchar(100)",
            nullable: true);

        migrationBuilder.CreateIndex(
            name: "IX_Doctors_Specialty",
            table: "Doctors",
            column: "Specialty");
    }

    protected override void Down(MigrationBuilder migrationBuilder)
    {
        // ✅ Thứ tự ngược lại của Up()
        // 1. Xóa index trước (dependency)
        migrationBuilder.DropIndex(
            name: "IX_Doctors_Specialty",
            table: "Doctors");

        // 2. Xóa column sau
        migrationBuilder.DropColumn(
            name: "Specialty",
            table: "Doctors");
    }
}

// GOOD: Với data migration, cần cẩn thận hơn
public partial class MigrateUserRoles : Migration
{
    protected override void Up(MigrationBuilder migrationBuilder)
    {
        migrationBuilder.Sql("UPDATE Users SET RoleId = 1 WHERE Role = 'Admin'");
    }

    protected override void Down(MigrationBuilder migrationBuilder)
    {
        // Phải restore data hoặc ít nhất ghi chú rõ không thể rollback data
        // Nếu không thể rollback data: ném exception để ngăn Down() chạy ngầm
        migrationBuilder.Sql("UPDATE Users SET Role = 'Admin' WHERE RoleId = 1");
    }
}
```

### 7. Phòng Ngừa

```bash
# CI/CD: Test rollback migration trong pipeline
# Apply migration
dotnet ef database update --connection "..."

# Test rollback
dotnet ef database update PreviousMigrationName --connection "..."

# Apply lại
dotnet ef database update --connection "..."
```

```csharp
// Test tự động kiểm tra migration rollback
[Fact]
public async Task AllMigrations_ShouldHaveDownMethod()
{
    var migrations = typeof(AppDbContext).Assembly
        .GetTypes()
        .Where(t => t.IsSubclassOf(typeof(Migration)));

    foreach (var migType in migrations)
    {
        var migration = (Migration)Activator.CreateInstance(migType)!;
        var builder = new MigrationBuilder("Microsoft.EntityFrameworkCore.SqlServer");

        // Không ném exception -> Down() có nội dung
        var exception = Record.Exception(() => migration.Down(builder));
        Assert.Null(exception);

        // Kiểm tra có ít nhất 1 operation
        Assert.NotEmpty(builder.Operations);  // ← Down() không được rỗng
    }
}
```

---

## Pattern 05: Raw SQL Injection (FromSqlRaw with String Interpolation)

### 1. Tên
**SQL Injection via FromSqlRaw** (String Interpolation in Raw SQL)

### 2. Phân Loại
- **Domain:** Entity Framework Core / Security
- **Subcategory:** SQL Injection / Raw SQL

### 3. Mức Nghiêm Trọng
**CRITICAL** 💀 - SQL Injection: Mất toàn bộ database, data breach, RCE

### 4. Vấn Đề

`FromSqlRaw()` và `ExecuteSqlRaw()` nhận raw SQL string. Nếu dùng string interpolation (`$"..."`), giá trị user input được nhúng trực tiếp vào SQL mà không escape, tạo ra lỗ hổng SQL injection nghiêm trọng.

```
SQL INJECTION ATTACK FLOW
==========================

User nhập: name = "'; DROP TABLE Users; --"

Code: FromSqlRaw($"SELECT * FROM Users WHERE Name = '{name}'")
                                                       ↑
                                               Input không được escape

SQL thực thi:
SELECT * FROM Users WHERE Name = ''; DROP TABLE Users; --'
                                      ↑
                              ĐÂY LÀ STATEMENT MỚI!

Kết quả:
1. SELECT trả về empty
2. DROP TABLE Users → XÓA TOÀN BỘ BẢNG USERS
3. -- comment phần còn lại

SEVERITY: CRITICAL - Mất toàn bộ dữ liệu
```

### 5. Phát Hiện Trong Mã Nguồn

**Dấu hiệu nhận biết:**
- `FromSqlRaw($"...")`  với string interpolation
- `ExecuteSqlRaw($"...")` với biến từ user input
- `Database.ExecuteSqlRaw` với string concatenation

**Regex patterns cho ripgrep:**

```bash
# Tìm FromSqlRaw với string interpolation (CRITICAL)
rg 'FromSqlRaw\s*\(\s*\$"' --type cs

# Tìm ExecuteSqlRaw với string interpolation
rg 'ExecuteSqlRaw\s*\(\s*\$"' --type cs

# Tìm string concatenation trong SQL
rg 'FromSqlRaw\s*\(\s*".*\+' --type cs

# Tìm tất cả raw SQL để review
rg "(FromSqlRaw|ExecuteSqlRaw|FromSql\b)" --type cs -n

# Tìm đúng cách dùng (FromSqlInterpolated)
rg "FromSqlInterpolated|ExecuteSqlInterpolated" --type cs
```

### 6. Giải Pháp

**Ví dụ SAI:**

```csharp
// BAD: CRITICAL SQL INJECTION VULNERABILITY
public class UserRepository
{
    public async Task<List<User>> SearchUsersAsync(string searchTerm)
    {
        // ❌ KHÔNG BAO GIỜ làm thế này!
        return await _context.Users
            .FromSqlRaw($"SELECT * FROM Users WHERE Name LIKE '%{searchTerm}%'")
            .ToListAsync();
    }

    public async Task<int> DeleteUserAsync(string userName)
    {
        // ❌ Cực kỳ nguy hiểm với ExecuteSqlRaw
        return await _context.Database
            .ExecuteSqlRaw($"DELETE FROM Users WHERE UserName = '{userName}'");
    }

    public async Task<List<User>> GetByRoleAsync(string role)
    {
        // ❌ String concatenation cũng nguy hiểm
        var sql = "SELECT * FROM Users WHERE Role = '" + role + "'";
        return await _context.Users.FromSqlRaw(sql).ToListAsync();
    }
}
```

**Ví dụ ĐÚNG:**

```csharp
// GOOD: Dùng FormattableString (tự động parameterize)
public class UserRepository
{
    public async Task<List<User>> SearchUsersAsync(string searchTerm)
    {
        // ✅ FromSqlInterpolated: EF tự động tạo parameter
        return await _context.Users
            .FromSqlInterpolated($"SELECT * FROM Users WHERE Name LIKE '%{searchTerm}%'")
            .ToListAsync();
        // SQL thực thi: SELECT * FROM Users WHERE Name LIKE '%@p0%'
        // searchTerm được truyền qua SqlParameter - SAFE
    }

    public async Task<int> DeleteUserAsync(string userName)
    {
        // ✅ ExecuteSqlInterpolated
        return await _context.Database
            .ExecuteSqlInterpolated($"DELETE FROM Users WHERE UserName = {userName}");
    }

    public async Task<List<User>> GetByRoleAsync(string role)
    {
        // ✅ Cách 1: SqlParameter tường minh
        return await _context.Users
            .FromSqlRaw("SELECT * FROM Users WHERE Role = {0}", role)
            .ToListAsync();

        // ✅ Cách 2: Dùng LINQ thay vì raw SQL (tốt nhất)
        return await _context.Users
            .Where(u => u.Role == role)
            .ToListAsync();
    }

    // ✅ Cách 3: SqlParameter tường minh (cho stored procedures)
    public async Task<List<User>> SearchWithStoredProcAsync(string searchTerm)
    {
        var param = new SqlParameter("@SearchTerm", searchTerm);
        return await _context.Users
            .FromSqlRaw("EXEC SearchUsers @SearchTerm", param)
            .ToListAsync();
    }
}
```

### 7. Phòng Ngừa

```csharp
// Roslyn Analyzer: Cài SecurityCodeScan.VS2019 (NuGet)
// -> Phát hiện SQL injection tại compile time

// Architecture Test: Không cho phép FromSqlRaw với string interpolation
[Fact]
public void NoRawSqlWithStringInterpolation()
{
    var csFiles = Directory.GetFiles("src", "*.cs", SearchOption.AllDirectories);
    var violations = csFiles
        .SelectMany(f => File.ReadAllLines(f).Select((line, i) => (File: f, Line: i + 1, Content: line)))
        .Where(x => x.Content.Contains("FromSqlRaw($") || x.Content.Contains("ExecuteSqlRaw($"));

    Assert.Empty(violations);  // ← Fail build nếu tìm thấy
}

// dotnet-format + Roslyn: Thêm banned API list
// BannedSymbols.txt:
// M:Microsoft.EntityFrameworkCore.RelationalQueryableExtensions.FromSqlRaw``1(...)
```

---

## Pattern 06: Cartesian Explosion (Multiple Include)

### 1. Tên
**Cartesian Explosion** (Multiple Collection Includes)

### 2. Phân Loại
- **Domain:** Entity Framework Core / Query Performance
- **Subcategory:** JOIN / Data Volume Explosion

### 3. Mức Nghiêm Trọng
**CRITICAL** 💀 - Gây OOM, timeout, query trả về hàng triệu rows không cần thiết

### 4. Vấn Đề

Khi Include nhiều collection navigation properties, EF Core tạo ra CROSS JOIN dẫn đến số rows tăng theo cấp số nhân (N × M × K rows).

```
CARTESIAN EXPLOSION
====================

Order có 10 Items và 5 Tags

Include(o => o.Items)                → 10 rows
Include(o => o.Tags)                 → kết hợp thành 10 × 5 = 50 rows!
                                       (mỗi item được lặp lại cho mỗi tag)

Thực tế:
- 100 orders × 50 items × 20 tags = 100,000 rows thay vì 170 rows
- 1000 orders × 100 items × 30 tags = 3,000,000 rows → TIMEOUT / OOM

SQL tạo ra:
SELECT o.*, i.*, t.*
FROM Orders o
JOIN Items i ON i.OrderId = o.Id
JOIN Tags t ON t.OrderId = o.Id  ← CROSS JOIN với Items!
```

### 5. Phát Hiện Trong Mã Nguồn

**Dấu hiệu nhận biết:**
- Query có 2+ `Include()` trên collection properties
- Memory spike đột ngột khi query data lớn
- Query timeout mặc dù dữ liệu không nhiều
- SQL Profiler cho thấy rows trả về nhiều bất thường

**Regex patterns cho ripgrep:**

```bash
# Tìm queries có nhiều Include (tiềm ẩn Cartesian Explosion)
rg "\.Include\(" --type cs -n | rg -v "ThenInclude"

# Tìm queries có 2+ Include liên tiếp
rg "\.Include\(.*\).*\.Include\(" --type cs

# Tìm AsSplitQuery (giải pháp đúng)
rg "AsSplitQuery" --type cs

# Tìm Include với collection properties (ICollection, IList, List)
rg "Include\(.*=>" --type cs -A 1
```

### 6. Giải Pháp

**Ví dụ SAI:**

```csharp
// BAD: Cartesian Explosion với 3 collections
public async Task<List<Order>> GetOrdersWithDetailsAsync()
{
    return await _context.Orders
        .Include(o => o.Items)       // ← Collection 1
        .Include(o => o.Tags)        // ← Collection 2: 10×5 = 50 rows/order
        .Include(o => o.Attachments) // ← Collection 3: 50×3 = 150 rows/order!
        .ToListAsync();              // ← Cartesian Explosion!
}
```

**Ví dụ ĐÚNG:**

```csharp
// GOOD: AsSplitQuery - EF Core 5+ tự động tách thành nhiều queries
public async Task<List<Order>> GetOrdersWithDetailsAsync()
{
    return await _context.Orders
        .Include(o => o.Items)
        .Include(o => o.Tags)
        .Include(o => o.Attachments)
        .AsSplitQuery()  // ← Tách thành 4 queries riêng biệt, không có Cartesian
        .ToListAsync();
}
// EF tạo ra:
// Query 1: SELECT * FROM Orders
// Query 2: SELECT * FROM Items WHERE OrderId IN (...)
// Query 3: SELECT * FROM Tags WHERE OrderId IN (...)
// Query 4: SELECT * FROM Attachments WHERE OrderId IN (...)

// GOOD: Cấu hình mặc định SplitQuery cho toàn bộ context
protected override void OnConfiguring(DbContextOptionsBuilder optionsBuilder)
{
    optionsBuilder.UseSqlServer(connectionString, options =>
        options.UseQuerySplittingBehavior(QuerySplittingBehavior.SplitQuery));
}

// GOOD: Projection để tránh hoàn toàn Cartesian Explosion
public async Task<List<OrderSummaryDto>> GetOrderSummariesAsync()
{
    return await _context.Orders
        .Select(o => new OrderSummaryDto
        {
            Id = o.Id,
            ItemCount = o.Items.Count,           // ← Subquery, không JOIN
            TagNames = o.Tags.Select(t => t.Name).ToList(),  // ← Subquery
            AttachmentCount = o.Attachments.Count // ← Subquery
        })
        .ToListAsync();
}
```

### 7. Phòng Ngừa

```csharp
// Bật SplitQuery theo mặc định trong Program.cs
builder.Services.AddDbContext<AppDbContext>(options =>
    options.UseSqlServer(connectionString, sqlOptions =>
        sqlOptions.UseQuerySplittingBehavior(QuerySplittingBehavior.SplitQuery)));

// Monitoring: Log warning khi query trả về quá nhiều rows
// Dùng EF Core interceptor
public class QuerySizeInterceptor : DbCommandInterceptor
{
    public override DbDataReader ReaderExecuted(
        DbCommand command,
        CommandExecutedEventData eventData,
        DbDataReader result)
    {
        // Log khi query chậm
        if (eventData.Duration > TimeSpan.FromSeconds(1))
        {
            _logger.LogWarning("Slow query detected: {Duration}ms\n{Sql}",
                eventData.Duration.TotalMilliseconds, command.CommandText);
        }
        return result;
    }
}
```

---

## Pattern 07: SaveChanges Không Transaction

### 1. Tên
**SaveChanges Without Explicit Transaction** (Partial Save Risk)

### 2. Phân Loại
- **Domain:** Entity Framework Core / Data Integrity
- **Subcategory:** Transaction / Atomicity

### 3. Mức Nghiêm Trọng
**HIGH** ⚠️ - Gây partial save, data inconsistency khi có lỗi giữa chừng

### 4. Vấn Đề

Khi một business operation cần nhiều `SaveChanges()` calls hoặc kết hợp EF với raw SQL/ADO.NET, nếu không dùng transaction tường minh, một phần dữ liệu có thể được save trong khi phần còn lại không.

```
PARTIAL SAVE SCENARIO
======================

Business Rule: Tạo Order phải đồng thời:
  1. Tạo Order record
  2. Giảm Inventory count
  3. Tạo Payment record
  4. Gửi Notification

Code:
  await _context.SaveChangesAsync()  → ✅ Order saved
  inventory.Count -= order.Quantity
  await _context.SaveChangesAsync()  → ✅ Inventory updated
  // ❌ Exception xảy ra ở đây!
  await _context.SaveChangesAsync()  → ❌ Payment KHÔNG được save

Kết quả:
  - Order tồn tại ✅
  - Inventory giảm ✅
  - Payment KHÔNG tồn tại ❌
  - DATA INCONSISTENT!
```

### 5. Phát Hiện Trong Mã Nguồn

**Dấu hiệu nhận biết:**
- Nhiều `SaveChanges()` trong một method business
- Mix EF và ADO.NET/Dapper không có shared transaction
- `SaveChanges()` trong loop

**Regex patterns cho ripgrep:**

```bash
# Tìm nhiều SaveChanges trong cùng một method
rg "SaveChanges" --type cs -n

# Tìm SaveChanges trong vòng lặp
rg "for.*\{" -A 20 --type cs | rg "SaveChanges"

# Tìm transaction usage (đúng cách)
rg "BeginTransaction|IDbContextTransaction|TransactionScope" --type cs

# Tìm kết hợp SaveChanges và raw SQL không có transaction
rg "ExecuteSqlRaw|ExecuteSqlInterpolated" -B 10 --type cs | rg "SaveChanges"
```

### 6. Giải Pháp

**Ví dụ SAI:**

```csharp
// BAD: Nhiều SaveChanges không có transaction - partial save risk
public class OrderService
{
    public async Task CreateOrderAsync(CreateOrderDto dto)
    {
        var order = new Order { ... };
        _context.Orders.Add(order);
        await _context.SaveChangesAsync();  // Save 1: Order

        var inventory = await _context.Inventories.FindAsync(dto.ProductId);
        inventory.Count -= dto.Quantity;
        await _context.SaveChangesAsync();  // Save 2: Inventory

        // Nếu exception xảy ra ở đây:
        var payment = new Payment { OrderId = order.Id, ... };
        _context.Payments.Add(payment);
        await _context.SaveChangesAsync();  // Save 3: Payment - có thể không chạy!
    }
}
```

**Ví dụ ĐÚNG:**

```csharp
// GOOD: Explicit transaction bọc toàn bộ operation
public class OrderService
{
    public async Task CreateOrderAsync(CreateOrderDto dto)
    {
        await using var transaction = await _context.Database.BeginTransactionAsync();
        try
        {
            var order = new Order { ... };
            _context.Orders.Add(order);

            var inventory = await _context.Inventories.FindAsync(dto.ProductId);
            inventory.Count -= dto.Quantity;

            var payment = new Payment { OrderId = order.Id, ... };
            _context.Payments.Add(payment);

            // 1 SaveChanges duy nhất - atomic
            await _context.SaveChangesAsync();

            await transaction.CommitAsync();
        }
        catch
        {
            await transaction.RollbackAsync();
            throw;
        }
    }
}

// GOOD: Unit of Work pattern - 1 SaveChanges cho cả business operation
public class OrderService
{
    public async Task CreateOrderAsync(CreateOrderDto dto)
    {
        // Thêm tất cả thay đổi vào context trước
        var order = new Order { ... };
        _context.Orders.Add(order);

        var inventory = await _context.Inventories.FindAsync(dto.ProductId);
        inventory.Count -= dto.Quantity;

        _context.Payments.Add(new Payment { ... });

        // 1 SaveChanges duy nhất - EF tự wrap trong transaction
        await _context.SaveChangesAsync();  // ← Atomic: tất cả hoặc không có gì
    }
}
```

### 7. Phòng Ngừa

```csharp
// Unit of Work pattern: bắt buộc 1 SaveChanges per request
public interface IUnitOfWork : IDisposable
{
    Task<int> SaveChangesAsync(CancellationToken ct = default);
    Task<IDbContextTransaction> BeginTransactionAsync();
}

// Middleware: Tự động commit/rollback cho mỗi request
public class TransactionMiddleware
{
    public async Task InvokeAsync(HttpContext context, IUnitOfWork uow)
    {
        try
        {
            await _next(context);
            await uow.SaveChangesAsync(); // ← Commit cuối request
        }
        catch
        {
            // Auto rollback nếu exception
            throw;
        }
    }
}
```

---

## Pattern 08: Concurrency Token Thiếu (Optimistic Concurrency)

### 1. Tên
**Missing Concurrency Token** (Lost Update Problem)

### 2. Phân Loại
- **Domain:** Entity Framework Core / Concurrency
- **Subcategory:** Optimistic Concurrency / Race Condition

### 3. Mức Nghiêm Trọng
**HIGH** ⚠️ - Gây lost update: thay đổi của user A bị ghi đè bởi user B

### 4. Vấn Đề

Khi hai users cùng đọc và chỉnh sửa một record, thay đổi của người save sau sẽ ghi đè thay đổi của người save trước mà không có cảnh báo.

```
LOST UPDATE SCENARIO
=====================

T=0: User A đọc Record (Version=1, Name="Old")
T=0: User B đọc Record (Version=1, Name="Old")
T=1: User A cập nhật Name="New A" → SaveChanges → Version=2
T=2: User B cập nhật Phone="123" → SaveChanges (dựa trên Version=1)
     ↓
     DB: UPDATE SET Phone="123", Name="Old"  ← Name="New A" bị MẤT!
     ↓
     Version=3 (User B không biết về Version=2)

KẾT QUẢ: Thay đổi của User A bị mất hoàn toàn!
```

### 5. Phát Hiện Trong Mã Nguồn

**Dấu hiệu nhận biết:**
- Entity quan trọng không có `[Timestamp]` hoặc `[ConcurrencyCheck]`
- Không có xử lý `DbUpdateConcurrencyException`
- Tính năng chỉnh sửa cho phép nhiều users cùng thao tác

**Regex patterns cho ripgrep:**

```bash
# Tìm entity không có RowVersion/Timestamp
rg "public\s+class\s+\w+\s*:" --type cs | rg -v "(Timestamp|RowVersion|ConcurrencyToken)"

# Tìm [Timestamp] và [ConcurrencyCheck] đang dùng
rg "\[Timestamp\]|\[ConcurrencyCheck\]|IsConcurrencyToken" --type cs

# Tìm xử lý DbUpdateConcurrencyException
rg "DbUpdateConcurrencyException" --type cs

# Tìm SaveChanges mà không có concurrency handling
rg "SaveChangesAsync" --type cs -B 5 | rg -v "DbUpdateConcurrencyException"
```

### 6. Giải Pháp

**Ví dụ SAI:**

```csharp
// BAD: Entity quan trọng không có concurrency token
public class MedicalRecord
{
    public int Id { get; set; }
    public string Diagnosis { get; set; }
    public string Treatment { get; set; }
    public DateTime UpdatedAt { get; set; }
    // ← Không có RowVersion! Lost Update có thể xảy ra
}

// BAD: Update không xử lý concurrency
public async Task UpdateMedicalRecordAsync(UpdateRecordDto dto)
{
    var record = await _context.MedicalRecords.FindAsync(dto.Id);
    record.Diagnosis = dto.Diagnosis;
    record.Treatment = dto.Treatment;

    await _context.SaveChangesAsync(); // ← Không detect nếu record đã thay đổi
}
```

**Ví dụ ĐÚNG:**

```csharp
// GOOD: Entity với RowVersion cho optimistic concurrency
public class MedicalRecord
{
    public int Id { get; set; }
    public string Diagnosis { get; set; }
    public string Treatment { get; set; }

    [Timestamp]  // ← SQL Server: rowversion / PostgreSQL: xmin
    public byte[] RowVersion { get; set; }  // Concurrency token
}

// Hoặc dùng Fluent API:
protected override void OnModelCreating(ModelBuilder modelBuilder)
{
    modelBuilder.Entity<MedicalRecord>()
        .Property(p => p.RowVersion)
        .IsRowVersion();  // ← Auto-increment khi update
}

// GOOD: Service xử lý DbUpdateConcurrencyException
public async Task UpdateMedicalRecordAsync(UpdateRecordDto dto)
{
    var record = await _context.MedicalRecords.FindAsync(dto.Id);

    // Set original RowVersion từ client (để EF so sánh)
    _context.Entry(record).Property(r => r.RowVersion).OriginalValue = dto.RowVersion;

    record.Diagnosis = dto.Diagnosis;
    record.Treatment = dto.Treatment;

    try
    {
        await _context.SaveChangesAsync();
    }
    catch (DbUpdateConcurrencyException ex)
    {
        // Reload giá trị mới từ DB
        var entry = ex.Entries.Single();
        var dbValues = await entry.GetDatabaseValuesAsync();

        if (dbValues == null)
            throw new InvalidOperationException("Record đã bị xóa bởi người dùng khác.");

        // Thông báo conflict cho user
        throw new ConcurrencyConflictException(
            "Record đã được chỉnh sửa bởi người dùng khác. Vui lòng tải lại và thử lại.",
            currentValues: entry.CurrentValues,
            databaseValues: dbValues);
    }
}
```

### 7. Phòng Ngừa

```csharp
// Base entity có RowVersion cho tất cả entities quan trọng
public abstract class AuditableEntity
{
    public int Id { get; set; }
    public DateTime CreatedAt { get; set; }
    public DateTime UpdatedAt { get; set; }

    [Timestamp]
    public byte[] RowVersion { get; set; }  // ← Bắt buộc cho mọi entity
}

// Architecture Test: entity quan trọng phải có RowVersion
[Fact]
public void ImportantEntities_ShouldHaveConcurrencyToken()
{
    var importantEntities = new[] { typeof(MedicalRecord), typeof(Order), typeof(User) };
    foreach (var entityType in importantEntities)
    {
        var hasRowVersion = entityType.GetProperties()
            .Any(p => p.GetCustomAttribute<TimestampAttribute>() != null);
        Assert.True(hasRowVersion, $"{entityType.Name} phải có [Timestamp] property");
    }
}
```

---

## Pattern 09: Owned Type Confusion

### 1. Tên
**Owned Type Mapping Confusion** (Value Object vs Entity)

### 2. Phân Loại
- **Domain:** Entity Framework Core / Domain Modeling
- **Subcategory:** Owned Types / Value Objects

### 3. Mức Nghiêm Trọng
**MEDIUM** ⚡ - Gây data model sai, query phức tạp không cần thiết, performance issues

### 4. Vấn Đề

Owned Types trong EF Core cho phép map Value Objects (không có identity riêng) vào cùng bảng với owner. Nhầm lẫn giữa Owned Type và Entity riêng biệt gây ra schema không phù hợp với domain model.

```
OWNED TYPE vs ENTITY
=====================

Value Object (nên dùng Owned Type):
- Không có identity riêng (Id)
- Được định nghĩa bởi giá trị của nó
- Ví dụ: Address, Money, DateRange, ContactInfo

Entity (nên dùng riêng):
- Có identity riêng (Id)
- Tồn tại độc lập
- Ví dụ: Customer, Product, Order

NHẦM LẪN:
Address có ID riêng → Tạo bảng Addresses riêng với FK
→ Không phản ánh đúng domain (Address không tồn tại độc lập)
→ Phải JOIN mỗi khi cần address
→ Schema phức tạp không cần thiết

ĐÚNG:
Address là Owned Type → Columns trong bảng Customer
→ Không cần JOIN
→ Phản ánh đúng domain
```

### 5. Phát Hiện Trong Mã Nguồn

**Dấu hiệu nhận biết:**
- Value Objects có `Id` property
- Bảng riêng cho các khái niệm như `Address`, `Money`, `DateRange`
- JOIN không cần thiết cho dữ liệu luôn gắn với owner

**Regex patterns cho ripgrep:**

```bash
# Tìm Owned Type configuration
rg "OwnsOne|OwnsMany" --type cs

# Tìm Value Objects có Id (tiềm năng nhầm lẫn)
rg "class\s+(Address|Money|DateRange|ContactInfo|Location)" -A 10 --type cs | rg "public.*Id\s*{"

# Tìm tables riêng cho address/money (schema review)
rg "HasColumnName.*Address|ToTable.*Address" --type cs

# Tìm [Owned] attribute
rg "\[Owned\]" --type cs
```

### 6. Giải Pháp

**Ví dụ SAI:**

```csharp
// BAD: Address được model như Entity riêng biệt
public class Address
{
    public int Id { get; set; }  // ← Value Object không nên có Id
    public string Street { get; set; }
    public string City { get; set; }
    public string PostalCode { get; set; }
}

public class Customer
{
    public int Id { get; set; }
    public string Name { get; set; }
    public int AddressId { get; set; }  // ← FK không cần thiết
    public Address Address { get; set; }
}

// Schema: 2 bảng, 1 JOIN
// SELECT c.*, a.* FROM Customers c JOIN Addresses a ON a.Id = c.AddressId
```

**Ví dụ ĐÚNG:**

```csharp
// GOOD: Address là Value Object / Owned Type
[Owned]  // ← Đánh dấu là Value Object
public class Address
{
    // Không có Id
    public string Street { get; set; }
    public string City { get; set; }
    public string PostalCode { get; set; }

    // Value Object nên immutable
    public Address(string street, string city, string postalCode)
    {
        Street = street;
        City = city;
        PostalCode = postalCode;
    }

    // Equality based on values, not identity
    public override bool Equals(object obj) =>
        obj is Address other &&
        Street == other.Street &&
        City == other.City &&
        PostalCode == other.PostalCode;
}

public class Customer
{
    public int Id { get; set; }
    public string Name { get; set; }
    public Address Address { get; set; }  // ← Owned Type, không có FK
}

// Fluent API configuration
protected override void OnModelCreating(ModelBuilder modelBuilder)
{
    modelBuilder.Entity<Customer>()
        .OwnsOne(c => c.Address, address =>
        {
            address.Property(a => a.Street).HasColumnName("AddressStreet");
            address.Property(a => a.City).HasColumnName("AddressCity");
            address.Property(a => a.PostalCode).HasColumnName("AddressPostalCode");
        });
}

// Schema: 1 bảng, không JOIN
// SELECT Id, Name, AddressStreet, AddressCity, AddressPostalCode FROM Customers
```

### 7. Phòng Ngừa

```csharp
// DDD Rule: Value Objects phải implement IEquatable, không có Id
public abstract class ValueObject
{
    protected abstract IEnumerable<object> GetEqualityComponents();

    public override bool Equals(object obj) { ... }
    public override int GetHashCode() { ... }
}

// Architecture Test: Owned Types không có Id property
[Fact]
public void OwnedTypes_ShouldNotHaveIdProperty()
{
    var ownedTypes = typeof(AppDbContext).Assembly.GetTypes()
        .Where(t => t.GetCustomAttribute<OwnedAttribute>() != null);

    foreach (var type in ownedTypes)
    {
        var hasId = type.GetProperty("Id") != null;
        Assert.False(hasId, $"Owned type {type.Name} không được có Id property");
    }
}
```

---

## Pattern 10: Global Query Filter Quên (Soft Delete Join)

### 1. Tên
**Missing Global Query Filter** (Soft Delete Leak)

### 2. Phân Loại
- **Domain:** Entity Framework Core / Soft Delete
- **Subcategory:** Global Query Filter / Data Leak

### 3. Mức Nghiêm Trọng
**MEDIUM** ⚡ - Gây lộ dữ liệu đã xóa, kết quả query không nhất quán

### 4. Vấn Đề

Soft delete dùng flag `IsDeleted` thay vì xóa thật. Nếu quên Global Query Filter hoặc Include navigation property mà navigation không có filter, dữ liệu "đã xóa" vẫn xuất hiện trong kết quả.

```
SOFT DELETE LEAK SCENARIO
==========================

Global Filter: IsDeleted == false trên Order

Query:
var customers = await _context.Customers
    .Include(c => c.Orders)  ← Include navigation
    .ToListAsync();

Kết quả: Customer.Orders chứa cả Orders đã bị soft delete!
Vì Include trên navigation property bỏ qua Global Query Filter
(EF Core behavior trước v6)

Expected: Customer.Orders chỉ có orders IsDeleted=false
Actual: Customer.Orders có TẤT CẢ orders (kể cả đã xóa)
```

### 5. Phát Hiện Trong Mã Nguồn

**Dấu hiệu nhận biết:**
- Có `IsDeleted` property nhưng không có Global Query Filter
- Include navigation properties mà không filter `IsDeleted`
- Query trả về dữ liệu "đã xóa"

**Regex patterns cho ripgrep:**

```bash
# Tìm IsDeleted property (soft delete entities)
rg "bool\s+IsDeleted\s*{" --type cs

# Tìm Global Query Filter configuration
rg "HasQueryFilter" --type cs

# Tìm entities có IsDeleted nhưng thiếu HasQueryFilter
rg "IsDeleted" --type cs -l

# Tìm IgnoreQueryFilters (bypass filter)
rg "IgnoreQueryFilters" --type cs
```

### 6. Giải Pháp

**Ví dụ SAI:**

```csharp
// BAD: Soft delete không có Global Query Filter
public class Order
{
    public int Id { get; set; }
    public bool IsDeleted { get; set; }  // ← Soft delete flag
    public DateTime? DeletedAt { get; set; }
}

// BAD: Phải nhớ filter IsDeleted ở khắp nơi
public class OrderRepository
{
    public async Task<List<Order>> GetActiveOrdersAsync()
    {
        // Phải nhớ thêm Where(o => !o.IsDeleted) ở MỌI query!
        return await _context.Orders
            .Where(o => !o.IsDeleted)  // ← Dễ quên
            .ToListAsync();
    }

    public async Task<Order> GetByIdAsync(int id)
    {
        // Quên filter IsDeleted -> trả về order đã xóa!
        return await _context.Orders.FindAsync(id);
    }
}
```

**Ví dụ ĐÚNG:**

```csharp
// GOOD: Interface cho soft delete
public interface ISoftDelete
{
    bool IsDeleted { get; set; }
    DateTime? DeletedAt { get; set; }
}

public class Order : ISoftDelete
{
    public int Id { get; set; }
    public bool IsDeleted { get; set; }
    public DateTime? DeletedAt { get; set; }
    public ICollection<OrderItem> Items { get; set; }
}

// GOOD: Global Query Filter tự động áp dụng cho mọi query
protected override void OnModelCreating(ModelBuilder modelBuilder)
{
    // Áp dụng filter cho TẤT CẢ entities implement ISoftDelete
    foreach (var entityType in modelBuilder.Model.GetEntityTypes())
    {
        if (typeof(ISoftDelete).IsAssignableFrom(entityType.ClrType))
        {
            var parameter = Expression.Parameter(entityType.ClrType, "e");
            var filter = Expression.Lambda(
                Expression.Not(Expression.Property(parameter, nameof(ISoftDelete.IsDeleted))),
                parameter);

            entityType.SetQueryFilter(filter);
        }
    }
}

// GOOD: Bypass filter khi cần (admin panel, restore)
public async Task<List<Order>> GetDeletedOrdersAsync()
{
    return await _context.Orders
        .IgnoreQueryFilters()  // ← Tường minh bypass filter
        .Where(o => o.IsDeleted)
        .ToListAsync();
}

// GOOD: Soft delete service
public async Task DeleteOrderAsync(int id)
{
    var order = await _context.Orders.FindAsync(id);
    order.IsDeleted = true;           // ← Soft delete
    order.DeletedAt = DateTime.UtcNow;
    await _context.SaveChangesAsync();
    // Global Filter tự động loại trừ record này khỏi mọi query sau đó
}
```

### 7. Phòng Ngừa

```csharp
// Architecture Test: Mọi ISoftDelete entity phải có Global Query Filter
[Fact]
public void SoftDeleteEntities_ShouldHaveGlobalQueryFilter()
{
    using var context = CreateTestContext();
    var softDeleteEntityTypes = context.Model.GetEntityTypes()
        .Where(e => typeof(ISoftDelete).IsAssignableFrom(e.ClrType));

    foreach (var entityType in softDeleteEntityTypes)
    {
        Assert.NotNull(entityType.GetQueryFilter());
    }
}
```

---

## Pattern 11: Connection Resilience (EnableRetryOnFailure)

### 1. Tên
**Missing Connection Resilience** (No Retry Policy)

### 2. Phân Loại
- **Domain:** Entity Framework Core / Infrastructure
- **Subcategory:** Connection Resilience / Transient Errors

### 3. Mức Nghiêm Trọng
**HIGH** ⚠️ - Gây lỗi tạm thời không được retry, user thấy error trong môi trường cloud

### 4. Vấn Đề

Môi trường cloud (Azure SQL, RDS, v.v.) thường có transient errors (kết nối tạm thời mất, throttling). Nếu không cấu hình retry, mọi transient error đều trở thành lỗi cho user.

```
TRANSIENT ERRORS TRONG CLOUD
=============================

Không retry:
  Request → Query DB → Transient Error → ❌ Exception ngay lập tức

Với retry:
  Request → Query DB → Transient Error → Retry 1 → Retry 2 → ✅ Thành công

Azure SQL throttling:
  - Error 40197: Service busy
  - Error 40501: Service busy (backoff required)
  - Error 49918: Cannot process request
  → Đây là TRANSIENT errors, nên retry tự động
```

### 5. Phát Hiện Trong Mã Nguồn

**Dấu hiệu nhận biết:**
- DbContext không có `EnableRetryOnFailure()`
- Không có Polly retry policy
- Errors "connection refused" hoặc "timeout" không được retry trong log

**Regex patterns cho ripgrep:**

```bash
# Tìm cấu hình UseSqlServer/UseNpgsql không có retry
rg "UseSqlServer|UseNpgsql|UseMySql" --type cs | rg -v "EnableRetryOnFailure|RetryOn"

# Tìm EnableRetryOnFailure (đúng cách)
rg "EnableRetryOnFailure" --type cs

# Tìm Polly retry policy
rg "AddPolicyHandler|WaitAndRetryAsync" --type cs

# Tìm AddDbContext configuration
rg "AddDbContext" -A 10 --type cs
```

### 6. Giải Pháp

**Ví dụ SAI:**

```csharp
// BAD: Không có retry policy cho Azure SQL
builder.Services.AddDbContext<AppDbContext>(options =>
    options.UseSqlServer(connectionString));
    // ← Không có EnableRetryOnFailure -> transient errors sẽ crash request
```

**Ví dụ ĐÚNG:**

```csharp
// GOOD: EnableRetryOnFailure cho SQL Server / Azure SQL
builder.Services.AddDbContext<AppDbContext>(options =>
    options.UseSqlServer(connectionString, sqlOptions =>
    {
        sqlOptions.EnableRetryOnFailure(
            maxRetryCount: 5,
            maxRetryDelay: TimeSpan.FromSeconds(30),
            errorNumbersToAdd: null);  // null = dùng danh sách mặc định
    }));

// GOOD: Custom retry với logging
builder.Services.AddDbContext<AppDbContext>((serviceProvider, options) =>
{
    var logger = serviceProvider.GetRequiredService<ILogger<AppDbContext>>();

    options.UseSqlServer(connectionString, sqlOptions =>
        sqlOptions.EnableRetryOnFailure(
            maxRetryCount: 3,
            maxRetryDelay: TimeSpan.FromSeconds(10),
            errorNumbersToAdd: new[] { 49920, 49919 }))  // Custom error codes
    .AddInterceptors(new RetryLoggingInterceptor(logger));
});

// GOOD: PostgreSQL với retry
builder.Services.AddDbContext<AppDbContext>(options =>
    options.UseNpgsql(connectionString, npgsqlOptions =>
        npgsqlOptions.EnableRetryOnFailure(
            maxRetryCount: 3,
            maxRetryDelay: TimeSpan.FromSeconds(15),
            errorCodesToAdd: null)));

// GOOD: Không thể dùng retry với explicit transaction
// EF sẽ throw khi retry policy bật mà dùng explicit transaction
// -> Dùng execution strategy tường minh
public async Task CreateOrderWithTransactionAsync(CreateOrderDto dto)
{
    var strategy = _context.Database.CreateExecutionStrategy();
    await strategy.ExecuteAsync(async () =>
    {
        await using var transaction = await _context.Database.BeginTransactionAsync();
        try
        {
            // ... operations
            await _context.SaveChangesAsync();
            await transaction.CommitAsync();
        }
        catch
        {
            await transaction.RollbackAsync();
            throw;
        }
    });
}
```

### 7. Phòng Ngừa

```csharp
// Health check để monitor DB connectivity
builder.Services.AddHealthChecks()
    .AddDbContextCheck<AppDbContext>(
        name: "database",
        failureStatus: HealthStatus.Unhealthy,
        tags: new[] { "db", "sql" });

// Startup validation: đảm bảo retry được cấu hình
[Fact]
public void DbContext_ShouldHaveRetryPolicy()
{
    var options = _services.GetRequiredService<DbContextOptions<AppDbContext>>();
    var extension = options.FindExtension<SqlServerOptionsExtension>();
    Assert.NotNull(extension?.ExecutionStrategyFactory);
}
```

---

## Pattern 12: Bulk Operation Thiếu (SaveChanges 1000+ Entities)

### 1. Tên
**Inefficient Bulk Operations** (SaveChanges Loop for Large Datasets)

### 2. Phân Loại
- **Domain:** Entity Framework Core / Performance
- **Subcategory:** Bulk Insert/Update/Delete / Throughput

### 3. Mức Nghiêm Trọng
**MEDIUM** ⚡ - Gây timeout, memory overflow khi xử lý lượng lớn dữ liệu

### 4. Vấn Đề

EF Core không có built-in bulk operation. Gọi `SaveChanges()` cho 10,000 entities sẽ tạo 10,000 SQL statements riêng lẻ thay vì 1 bulk INSERT.

```
INEFFICIENT BULK INSERT
========================

// 10,000 records:
foreach (var item in items)  // ← Lặp 10,000 lần
{
    _context.Add(item);
    await _context.SaveChangesAsync();  // ← 10,000 round trips đến DB!
}

Thời gian: ~30-60 giây (network latency × 10,000)

// Hoặc:
_context.AddRange(items);
await _context.SaveChangesAsync();  // ← 1 call nhưng vẫn N SQL INSERT statements
                                    // Change tracker track 10,000 entities → OOM

BULK INSERT ĐÚNG:
1 SQL statement: INSERT INTO Table (col1, col2) VALUES (v1,v2),(v3,v4),...
Thời gian: ~0.1-1 giây
```

### 5. Phát Hiện Trong Mã Nguồn

**Dấu hiệu nhận biết:**
- `SaveChanges()` trong vòng lặp với nhiều items
- Import/export data lớn qua EF
- Batch job xử lý hàng nghìn records

**Regex patterns cho ripgrep:**

```bash
# Tìm SaveChanges trong vòng lặp
rg "foreach\s*\(" -A 10 --type cs | rg "SaveChanges"

# Tìm AddRange với large dataset
rg "AddRange\|BulkInsert" --type cs

# Tìm import/batch operations
rg "class\s+\w*(Import|Batch|Sync|Seed)\w*" --type cs

# Tìm EF Bulk Extensions usage
rg "BulkInsertAsync|BulkUpdateAsync|BulkDeleteAsync" --type cs
```

### 6. Giải Pháp

**Ví dụ SAI:**

```csharp
// BAD: SaveChanges trong loop - cực kỳ chậm với 10,000+ records
public async Task ImportProductsAsync(IEnumerable<ProductDto> products)
{
    foreach (var dto in products)
    {
        var product = new Product { Name = dto.Name, Price = dto.Price };
        _context.Products.Add(product);
        await _context.SaveChangesAsync();  // ← 1 round trip per record!
    }
}

// BAD: AddRange + 1 SaveChanges - vẫn slow, memory issue với 100k+ records
public async Task ImportProductsAsync(IEnumerable<ProductDto> products)
{
    var entities = products.Select(dto => new Product { ... }).ToList();
    _context.Products.AddRange(entities);  // ← Track 100k entities → OOM
    await _context.SaveChangesAsync();
}
```

**Ví dụ ĐÚNG:**

```csharp
// GOOD: Batch processing với chunk size
public async Task ImportProductsAsync(IEnumerable<ProductDto> products)
{
    const int batchSize = 1000;
    var batch = new List<Product>(batchSize);

    foreach (var dto in products)
    {
        batch.Add(new Product { Name = dto.Name, Price = dto.Price });

        if (batch.Count >= batchSize)
        {
            _context.Products.AddRange(batch);
            await _context.SaveChangesAsync();
            _context.ChangeTracker.Clear();  // ← Xóa tracking để giải phóng memory
            batch.Clear();
        }
    }

    if (batch.Any())
    {
        _context.Products.AddRange(batch);
        await _context.SaveChangesAsync();
    }
}

// GOOD: EF Core 7+ ExecuteUpdate/ExecuteDelete (không load entity)
public async Task DeactivateOldProductsAsync(DateTime cutoffDate)
{
    // Không load entities vào memory - trực tiếp UPDATE trong DB
    await _context.Products
        .Where(p => p.CreatedAt < cutoffDate && p.IsActive)
        .ExecuteUpdateAsync(setter => setter
            .SetProperty(p => p.IsActive, false)
            .SetProperty(p => p.DeactivatedAt, DateTime.UtcNow));
}

public async Task DeleteOldLogsAsync(DateTime cutoffDate)
{
    // DELETE không cần load entities
    await _context.AuditLogs
        .Where(l => l.CreatedAt < cutoffDate)
        .ExecuteDeleteAsync();
}

// GOOD: EFCore.BulkExtensions (NuGet) cho bulk operations phức tạp
public async Task BulkImportAsync(List<Product> products)
{
    await _context.BulkInsertAsync(products, options =>
    {
        options.BatchSize = 2000;
        options.SetOutputIdentity = true;
    });
}
```

### 7. Phòng Ngừa

```csharp
// Extension method tái sử dụng batch processing
public static class DbContextExtensions
{
    public static async Task BulkSaveAsync<T>(
        this DbContext context,
        IEnumerable<T> entities,
        int batchSize = 1000) where T : class
    {
        var batch = new List<T>(batchSize);
        foreach (var entity in entities)
        {
            batch.Add(entity);
            if (batch.Count >= batchSize)
            {
                context.Set<T>().AddRange(batch);
                await context.SaveChangesAsync();
                context.ChangeTracker.Clear();
                batch.Clear();
            }
        }

        if (batch.Any())
        {
            context.Set<T>().AddRange(batch);
            await context.SaveChangesAsync();
        }
    }
}
```

---

## Pattern 13: DateTime UTC Thiếu (DateTime.Now vs UtcNow)

### 1. Tên
**DateTime Timezone Inconsistency** (Local vs UTC)

### 2. Phân Loại
- **Domain:** Entity Framework Core / Data Quality
- **Subcategory:** DateTime / Timezone

### 3. Mức Nghiêm Trọng
**HIGH** ⚠️ - Gây sai lệch dữ liệu thời gian, bug khó phát hiện khi deploy đa vùng

### 4. Vấn Đề

Dùng `DateTime.Now` (local time) thay vì `DateTime.UtcNow` gây ra sai lệch khi server đặt ở múi giờ khác với database hoặc khi deploy sang cloud.

```
DATETIME TIMEZONE BUG
======================

Server: Tokyo (UTC+9)
Database: UTC

DateTime.Now:  2024-01-15 09:00:00 (JST - local)
DateTime.UtcNow: 2024-01-15 00:00:00 (UTC)

Save DateTime.Now vào DB (DateTime column):
  DB lưu: 2024-01-15 09:00:00 (không có timezone info!)

Khi đọc từ DB (server ở UTC):
  Đọc ra: 2024-01-15 09:00:00 → Hiểu là UTC → SAI 9 tiếng!

Khi migrate server từ Tokyo → Singapore (UTC+8):
  Dữ liệu cũ: 2024-01-15 09:00:00 (thực ra là JST)
  Dữ liệu mới: 2024-01-15 08:00:00 (SGT)
  → Sai lệch 1 tiếng, không phát hiện được ngay!
```

### 5. Phát Hiện Trong Mã Nguồn

**Dấu hiệu nhận biết:**
- `DateTime.Now` trong code server-side
- Column type `datetime` thay vì `datetimeoffset`
- Không có UTC convention trong entity

**Regex patterns cho ripgrep:**

```bash
# Tìm DateTime.Now (tiềm năng lỗi timezone)
rg "DateTime\.Now\b" --type cs

# Tìm DateTime.Today
rg "DateTime\.Today\b" --type cs

# Tìm DateTime.UtcNow (đúng cách)
rg "DateTime\.UtcNow" --type cs

# Tìm column type datetime (không có offset)
rg '"datetime"' --type cs | rg -v "datetimeoffset"

# Tìm DateTimeOffset usage (tốt nhất)
rg "DateTimeOffset\." --type cs
```

### 6. Giải Pháp

**Ví dụ SAI:**

```csharp
// BAD: DateTime.Now - local timezone
public class Order
{
    public int Id { get; set; }
    public DateTime CreatedAt { get; set; }  // ← Không có timezone
    public DateTime UpdatedAt { get; set; }
}

public class OrderService
{
    public async Task<Order> CreateOrderAsync(CreateOrderDto dto)
    {
        var order = new Order
        {
            CreatedAt = DateTime.Now,   // ← Local time! Sai khi deploy cloud
            UpdatedAt = DateTime.Now,   // ← Sai!
        };
        // ...
    }
}
```

**Ví dụ ĐÚNG:**

```csharp
// GOOD: DateTimeOffset bảo toàn timezone information
public class Order
{
    public int Id { get; set; }
    public DateTimeOffset CreatedAt { get; set; }  // ← Có timezone info
    public DateTimeOffset UpdatedAt { get; set; }
}

// GOOD: Service dùng UtcNow
public class OrderService
{
    public async Task<Order> CreateOrderAsync(CreateOrderDto dto)
    {
        var order = new Order
        {
            CreatedAt = DateTime.UtcNow,    // ← UTC: nhất quán mọi nơi
            UpdatedAt = DateTime.UtcNow,
        };
        // ...
    }
}

// GOOD: EF Core convention - tự động set UTC
protected override void OnModelCreating(ModelBuilder modelBuilder)
{
    // Convention: Tất cả DateTime columns là datetimeoffset
    foreach (var entityType in modelBuilder.Model.GetEntityTypes())
    {
        foreach (var property in entityType.GetProperties())
        {
            if (property.ClrType == typeof(DateTime) ||
                property.ClrType == typeof(DateTime?))
            {
                property.SetColumnType("datetimeoffset");
            }
        }
    }
}

// GOOD: Interceptor tự động set UtcNow
public class AuditInterceptor : SaveChangesInterceptor
{
    public override InterceptionResult<int> SavingChanges(
        DbContextEventData eventData, InterceptionResult<int> result)
    {
        var now = DateTime.UtcNow;
        foreach (var entry in eventData.Context!.ChangeTracker.Entries())
        {
            if (entry.Entity is IAuditable auditable)
            {
                if (entry.State == EntityState.Added)
                    auditable.CreatedAt = now;
                if (entry.State is EntityState.Added or EntityState.Modified)
                    auditable.UpdatedAt = now;
            }
        }
        return result;
    }
}
```

### 7. Phòng Ngừa

```csharp
// Roslyn Analyzer: Cảnh báo khi dùng DateTime.Now
// File: DateTimeNowAnalyzer.cs
[DiagnosticAnalyzer(LanguageNames.CSharp)]
public class DateTimeNowAnalyzer : DiagnosticAnalyzer
{
    public static readonly DiagnosticDescriptor Rule = new(
        id: "DT001",
        title: "Sử dụng DateTime.UtcNow thay vì DateTime.Now",
        messageFormat: "Dùng DateTime.UtcNow để đảm bảo nhất quán timezone",
        category: "Reliability",
        defaultSeverity: DiagnosticSeverity.Warning,
        isEnabledByDefault: true);
}

// Architecture Test
[Fact]
public void NoDateTimeNow_InServerCode()
{
    var sourceFiles = Directory.GetFiles("src", "*.cs", SearchOption.AllDirectories);
    var violations = sourceFiles
        .SelectMany(f => File.ReadAllLines(f).Select((line, i) => (f, i + 1, line)))
        .Where(x => x.line.Contains("DateTime.Now") && !x.line.TrimStart().StartsWith("//"));

    Assert.Empty(violations);
}
```

---

## Pattern 14: String Column Length (nvarchar max)

### 1. Tên
**Unspecified String Column Length** (nvarchar(max) Default)

### 2. Phân Loại
- **Domain:** Entity Framework Core / Schema Design
- **Subcategory:** Column Configuration / Performance

### 3. Mức Nghiêm Trọng
**MEDIUM** ⚡ - Gây hiệu năng index kém, storage lãng phí, query plan suboptimal

### 4. Vấn Đề

EF Core mặc định map `string` property thành `nvarchar(max)`. Column `nvarchar(max)` không thể được index một cách hiệu quả, gây query plan kém và storage overhead.

```
NVARCHAR(MAX) PROBLEMS
=======================

1. Index Limitation:
   nvarchar(max) KHÔNG thể tạo index thông thường
   → Full table scan thay vì index seek
   → Query chậm O(n) thay vì O(log n)

2. Storage Overhead:
   nvarchar(max) < 8000 bytes: lưu in-row
   nvarchar(max) > 8000 bytes: lưu off-row (LOB)
   → Thêm 24 bytes overhead per row
   → I/O tăng

3. Sort/Group Performance:
   ORDER BY, GROUP BY trên nvarchar(max) chậm hơn
   → Vì không thể dùng sort index

4. Migration Issues:
   Không thể thay đổi nvarchar(max) thành nvarchar(n)
   mà không mất index và data migration
```

### 5. Phát Hiện Trong Mã Nguồn

**Dấu hiệu nhận binh:**
- `string` properties không có `[MaxLength]` attribute
- Migration tạo `nvarchar(max)` cho tất cả string columns
- Không có column configuration trong `OnModelCreating`

**Regex patterns cho ripgrep:**

```bash
# Tìm string properties không có MaxLength (tiềm năng nvarchar max)
rg "public\s+string\s+\w+\s*\{" --type cs | rg -v "MaxLength\|StringLength\|HasMaxLength"

# Tìm [MaxLength] và [StringLength] đang dùng
rg "\[MaxLength|\[StringLength" --type cs

# Tìm nvarchar(max) trong migrations
rg 'nvarchar\(max\)' --type cs

# Tìm HasMaxLength trong Fluent API
rg "HasMaxLength|HasColumnType.*nvarchar" --type cs
```

### 6. Giải Pháp

**Ví dụ SAI:**

```csharp
// BAD: String properties không có độ dài -> nvarchar(max)
public class Doctor
{
    public int Id { get; set; }
    public string Name { get; set; }           // ← nvarchar(max)!
    public string Email { get; set; }          // ← nvarchar(max)!
    public string PhoneNumber { get; set; }    // ← nvarchar(max)!
    public string LicenseNumber { get; set; }  // ← nvarchar(max)!
    public string Specialization { get; set; } // ← nvarchar(max)!
    public string Notes { get; set; }          // ← OK: notes có thể max
}
```

**Ví dụ ĐÚNG:**

```csharp
// GOOD: Data Annotations để định nghĩa độ dài
public class Doctor
{
    public int Id { get; set; }

    [MaxLength(100)]      // ← Tên tối đa 100 ký tự
    public string Name { get; set; }

    [MaxLength(256)]      // ← Email tối đa 256 theo RFC 5321
    public string Email { get; set; }

    [MaxLength(20)]       // ← Phone number tối đa 20 ký tự
    public string PhoneNumber { get; set; }

    [MaxLength(50)]       // ← License number format cố định
    public string LicenseNumber { get; set; }

    [MaxLength(100)]      // ← Specialization category
    public string Specialization { get; set; }

    // Notes: OK để nvarchar(max) vì nội dung không giới hạn
    // và không cần index trên column này
    public string Notes { get; set; }
}

// GOOD: Fluent API configuration (tách biệt domain và infrastructure)
public class DoctorConfiguration : IEntityTypeConfiguration<Doctor>
{
    public void Configure(EntityTypeBuilder<Doctor> builder)
    {
        builder.Property(d => d.Name)
               .HasMaxLength(100)
               .IsRequired();

        builder.Property(d => d.Email)
               .HasMaxLength(256)
               .IsRequired();

        builder.Property(d => d.PhoneNumber)
               .HasMaxLength(20);

        builder.Property(d => d.LicenseNumber)
               .HasMaxLength(50)
               .IsRequired();

        // Index chỉ hoạt động hiệu quả khi có MaxLength
        builder.HasIndex(d => d.Email).IsUnique();
        builder.HasIndex(d => d.LicenseNumber).IsUnique();
    }
}

// GOOD: Convention-based approach - áp dụng MaxLength mặc định
protected override void OnModelCreating(ModelBuilder modelBuilder)
{
    // Áp dụng MaxLength mặc định cho tất cả string properties chưa có config
    foreach (var property in modelBuilder.Model.GetEntityTypes()
        .SelectMany(e => e.GetProperties())
        .Where(p => p.ClrType == typeof(string) && p.GetMaxLength() == null))
    {
        property.SetMaxLength(512);  // ← Default max length nếu chưa specify
    }
}
```

### 7. Phòng Ngừa

```csharp
// Architecture Test: Phát hiện nvarchar(max) không có chủ đích
[Fact]
public void StringProperties_ShouldHaveExplicitMaxLength()
{
    using var context = CreateTestContext();
    var problematicProperties = context.Model.GetEntityTypes()
        .SelectMany(e => e.GetProperties())
        .Where(p => p.ClrType == typeof(string) && p.GetMaxLength() == null)
        // Whitelist các columns được phép nvarchar(max) có chủ đích
        .Where(p => !_allowedNvarcharMaxColumns.Contains($"{p.DeclaringType.ShortName()}.{p.Name}"));

    var violations = problematicProperties
        .Select(p => $"{p.DeclaringType.ShortName()}.{p.Name}")
        .ToList();

    Assert.Empty(violations);
}

private static readonly HashSet<string> _allowedNvarcharMaxColumns = new()
{
    "Doctor.Notes",
    "AuditLog.Details",
    "EmailTemplate.Body",
};

// Roslyn: SonarAnalyzer.CSharp hoặc custom rule để cảnh báo
// string property không có [MaxLength] trong EF entity class
```

---

## Tóm Tắt Domain 04

| # | Pattern | Mức độ | Tác động chính |
|---|---------|--------|----------------|
| 01 | N+1 Query (Lazy Loading) | HIGH ⚠️ | N queries thay vì 1, timeout |
| 02 | Tracking Query Không Cần | MEDIUM ⚡ | Memory overhead, query chậm |
| 03 | DbContext Singleton Lifetime | CRITICAL 💀 | Race condition, data corruption |
| 04 | Migration Rollback Thiếu | MEDIUM ⚡ | Không rollback được, downtime |
| 05 | Raw SQL Injection | CRITICAL 💀 | SQL injection, mất toàn bộ DB |
| 06 | Cartesian Explosion | CRITICAL 💀 | OOM, timeout, rows tăng theo cấp số nhân |
| 07 | SaveChanges Không Transaction | HIGH ⚠️ | Partial save, data inconsistency |
| 08 | Concurrency Token Thiếu | HIGH ⚠️ | Lost update, race condition |
| 09 | Owned Type Confusion | MEDIUM ⚡ | Schema sai, JOIN không cần thiết |
| 10 | Global Query Filter Quên | MEDIUM ⚡ | Lộ dữ liệu đã xóa |
| 11 | Connection Resilience Thiếu | HIGH ⚠️ | Transient errors không retry |
| 12 | Bulk Operation Thiếu | MEDIUM ⚡ | Timeout, OOM với dữ liệu lớn |
| 13 | DateTime UTC Thiếu | HIGH ⚠️ | Sai lệch thời gian, bug timezone |
| 14 | String Column Length | MEDIUM ⚡ | Index kém, storage lãng phí |

### Quick Detection Commands

```bash
# Scan toàn bộ EF issues trong project
echo "=== N+1: Virtual Navigation ===" && rg "public virtual" --type cs -c
echo "=== Tracking: Missing AsNoTracking ===" && rg "\.ToListAsync\(\)" --type cs -c
echo "=== Lifetime: Singleton DbContext ===" && rg "AddSingleton.*Context" --type cs
echo "=== SQL Injection: Raw SQL ===" && rg 'FromSqlRaw\(\s*\$"' --type cs
echo "=== Cartesian: Multiple Include ===" && rg "\.Include\(" --type cs -c
echo "=== DateTime: Local Time ===" && rg "DateTime\.Now\b" --type cs
echo "=== String Length: No MaxLength ===" && rg "public string" --type cs -c
```
