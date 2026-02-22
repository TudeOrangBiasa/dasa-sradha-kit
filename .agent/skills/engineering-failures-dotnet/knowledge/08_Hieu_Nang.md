# Domain 08: Hiệu Năng Và Mở Rộng (Performance & Scalability)

> .NET/C# patterns liên quan đến performance: LINQ, GC pressure, LOH, async, EF Core, connection pooling.

---

## Pattern 01: LINQ Deferred Execution

### Tên
LINQ Deferred Execution (Multiple Enumeration Của IEnumerable)

### Phân loại
Performance / LINQ / Enumeration

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```csharp
IEnumerable<Order> orders = GetOrders(); // Query not executed yet
var count = orders.Count();  // Executes query (enumeration 1)
var total = orders.Sum(o => o.Total); // Executes AGAIN (enumeration 2)
var list = orders.ToList();  // Executes AGAIN (enumeration 3)
// 3 database queries or 3 full enumerations!
```

### Phát hiện

```bash
rg --type cs "IEnumerable<" -n
rg --type cs "\.Count\(\).*\.Sum\(|\.Any\(\).*\.Count\(\)" -n
```

### Giải pháp

❌ **BAD**
```csharp
IEnumerable<Product> products = _db.Products.Where(p => p.Active);
if (products.Any())          // Query 1
{
    var count = products.Count(); // Query 2
    foreach (var p in products)   // Query 3
    { /* ... */ }
}
```

✅ **GOOD**
```csharp
var products = _db.Products.Where(p => p.Active).ToList(); // Single query
if (products.Count > 0)
{
    foreach (var p in products) { /* ... */ }
}
```

### Phòng ngừa
- [ ] Materialize with `.ToList()` before multiple uses
- [ ] `IReadOnlyList<T>` instead of `IEnumerable<T>` for materialized data
- Tool: Roslyn CA1851 (Possible multiple enumerations)

---

## Pattern 02: String Concatenation Trong Loop

### Tên
String Concatenation Trong Loop (String += In Loop)

### Phân loại
Performance / String / Allocation

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```csharp
string result = "";
foreach (var item in items) // 10,000 items
{
    result += item.ToString() + ",";
    // Each += creates a NEW string — O(n²)
}
```

### Phát hiện

```bash
rg --type cs "\+= .*\"|\+ \"" -n | rg "for|foreach|while"
rg --type cs "StringBuilder" -n
```

### Giải pháp

❌ **BAD**
```csharp
string csv = "";
foreach (var row in rows)
    csv += string.Join(",", row.Values) + "\n";
```

✅ **GOOD**
```csharp
var sb = new StringBuilder(rows.Count * 100);
foreach (var row in rows)
{
    sb.AppendJoin(",", row.Values);
    sb.AppendLine();
}
var csv = sb.ToString();

// Or string.Join:
var csv = string.Join("\n", rows.Select(r => string.Join(",", r.Values)));
```

### Phòng ngừa
- [ ] `StringBuilder` for loop concatenation
- [ ] `string.Join` for joining collections
- Tool: Roslyn CA1845 (Use span-based string.Concat)

---

## Pattern 03: Boxing/Unboxing

### Tên
Boxing/Unboxing (Value Type → Object → Value Type)

### Phân loại
Performance / Memory / Boxing

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```csharp
int value = 42;
object boxed = value;    // Boxing: stack → heap allocation
int unboxed = (int)boxed; // Unboxing: heap → stack copy

// Hidden boxing:
string s = string.Format("Value: {0}", 42); // 42 is boxed!
```

### Phát hiện

```bash
rg --type cs "ArrayList|Hashtable" -n
rg --type cs "\(object\)" -n
```

### Giải pháp

❌ **BAD**
```csharp
ArrayList items = new ArrayList();
items.Add(42); // Boxing
```

✅ **GOOD**
```csharp
List<int> items = new List<int>();
items.Add(42); // No boxing

// String interpolation (no boxing in .NET 6+):
Console.WriteLine($"Count: {count}");
```

### Phòng ngừa
- [ ] Use generic collections (`List<T>`, `Dictionary<K,V>`)
- [ ] String interpolation instead of `string.Format`
- Tool: BenchmarkDotNet for measuring allocations

---

## Pattern 04: GC Pressure (Gen 2)

### Tên
GC Pressure Gen 2 (Excessive Gen 2 Collections)

### Phân loại
Performance / GC / Memory

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```
Gen 0: Short-lived (fast ~1ms)
Gen 1: Medium-lived
Gen 2: Long-lived (expensive ~10-100ms STW pause!)

Objects survive to Gen 2 unnecessarily:
→ Static collections growing forever
→ Event handlers not unsubscribed
→ Gen 2 collections cause latency spikes
```

### Phát hiện

```bash
rg --type cs "static.*List<|static.*Dictionary<" -n
rg --type cs "GC\.Collect" -n
rg --type cs "\+= new\s+EventHandler" -n
```

### Giải pháp

❌ **BAD**
```csharp
private static readonly List<byte[]> _cache = new(); // Grows forever
public void Process(byte[] data) { _cache.Add(data); }
```

✅ **GOOD**
```csharp
private readonly IMemoryCache _cache;
public void Process(string key, byte[] data)
{
    _cache.Set(key, data, new MemoryCacheEntryOptions
    {
        SlidingExpiration = TimeSpan.FromMinutes(5),
        Size = data.Length,
    });
}
```

### Phòng ngừa
- [ ] `IMemoryCache` with eviction instead of static collections
- [ ] Unsubscribe events to prevent leaked references
- Tool: `dotnet-counters`, `dotnet-gcdump`

---

## Pattern 05: Large Object Heap

### Tên
Large Object Heap (LOH Fragmentation)

### Phân loại
Performance / GC / LOH

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```
Objects > 85,000 bytes → Large Object Heap (LOH)
LOH is NOT compacted by default → fragmentation
→ OutOfMemoryException even with free memory

Common: byte[] > 85KB, string > ~42K chars, large arrays
```

### Phát hiện

```bash
rg --type cs "new byte\[|new char\[" -n
rg --type cs "ArrayPool<|MemoryPool<" -n
```

### Giải pháp

❌ **BAD**
```csharp
public byte[] ReadFile(string path)
{
    var buffer = new byte[1_000_000]; // 1MB → LOH every call
    using var stream = File.OpenRead(path);
    stream.Read(buffer);
    return buffer;
}
```

✅ **GOOD**
```csharp
public void ProcessFile(string path)
{
    var buffer = ArrayPool<byte>.Shared.Rent(1_000_000);
    try
    {
        using var stream = File.OpenRead(path);
        var bytesRead = stream.Read(buffer);
        Process(buffer.AsSpan(0, bytesRead));
    }
    finally
    {
        ArrayPool<byte>.Shared.Return(buffer);
    }
}
```

### Phòng ngừa
- [ ] `ArrayPool<T>.Shared` for large buffers
- [ ] `RecyclableMemoryStream` for stream operations
- Tool: `dotnet-gcdump`, PerfView LOH analysis

---

## Pattern 06: Reflection Overhead

### Tên
Reflection Overhead (Reflection In Hot Path)

### Phân loại
Performance / Reflection / Runtime

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```csharp
foreach (var item in items)
{
    var value = item.GetType().GetProperty("Name").GetValue(item); // Slow!
}
```

### Phát hiện

```bash
rg --type cs "GetType\(\)\.|Activator\.CreateInstance" -n
rg --type cs "GetProperty\(|GetMethod\(" -n
```

### Giải pháp

❌ **BAD**
```csharp
var value = item.GetType().GetProperty("Name").GetValue(item);
```

✅ **GOOD**
```csharp
// Source generators (.NET 6+):
[JsonSerializable(typeof(MyClass))]
internal partial class MyJsonContext : JsonSerializerContext { }
var json = JsonSerializer.Serialize(obj, MyJsonContext.Default.MyClass);

// Cache reflection:
private static readonly PropertyInfo _nameProp = typeof(Item).GetProperty("Name")!;
```

### Phòng ngừa
- [ ] Source generators instead of runtime reflection
- [ ] Cache `PropertyInfo`/`MethodInfo` lookups
- Tool: BenchmarkDotNet, `System.Text.Json` source generators

---

## Pattern 07: Regex Compile Thiếu

### Tên
Regex Compile Thiếu (Recompiling Regex Per Call)

### Phân loại
Performance / Regex / Compilation

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```csharp
public bool IsValidEmail(string email)
{
    return Regex.IsMatch(email, @"^[\w.-]+@[\w.-]+\.\w+$"); // Compiled per call!
}
```

### Phát hiện

```bash
rg --type cs "Regex\.(IsMatch|Match|Replace)\(" -n
rg --type cs "GeneratedRegex" -n
```

### Giải pháp

❌ **BAD**
```csharp
bool valid = Regex.IsMatch(input, pattern); // Per-call compilation
```

✅ **GOOD**
```csharp
// .NET 7+: Source-generated regex (best):
[GeneratedRegex(@"^[\w.-]+@[\w.-]+\.\w+$")]
private static partial Regex EmailRegex();

public bool IsValidEmail(string email) => EmailRegex().IsMatch(email);

// Or pre-compiled static:
private static readonly Regex _emailRegex =
    new(@"^[\w.-]+@[\w.-]+\.\w+$", RegexOptions.Compiled);
```

### Phòng ngừa
- [ ] `[GeneratedRegex]` for .NET 7+
- [ ] `RegexOptions.Compiled` for static instances
- Tool: Roslyn SYSLIB1045

---

## Pattern 08: Async State Machine Allocation

### Tên
Async State Machine Allocation (Unnecessary Async Overhead)

### Phân loại
Performance / Async / Allocation

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```csharp
// Wrapper that just awaits another async:
async Task<User> GetUserAsync(int id)
{
    return await _repository.GetByIdAsync(id);
    // Unnecessary state machine — just forwarding
}
```

### Phát hiện

```bash
rg --type cs "async Task" -n | rg "return.*await"
rg --type cs "ValueTask" -n
```

### Giải pháp

❌ **BAD**
```csharp
async Task<User> GetUserAsync(int id) => await _repo.GetByIdAsync(id);
```

✅ **GOOD**
```csharp
// Return Task directly (no state machine):
Task<User> GetUserAsync(int id) => _repo.GetByIdAsync(id);

// ValueTask for hot paths with sync completion:
ValueTask<int> GetCachedValueAsync(string key)
{
    if (_cache.TryGetValue(key, out var value))
        return new ValueTask<int>(value); // No allocation!
    return new ValueTask<int>(LoadFromDbAsync(key));
}
```

### Phòng ngừa
- [ ] Elide async/await when just forwarding tasks
- [ ] `ValueTask<T>` for hot paths with sync completion
- Tool: Roslyn CA1849

---

## Pattern 09: Span Không Dùng

### Tên
Span Không Dùng (Heap Allocation Instead Of Stack-Based Span)

### Phân loại
Performance / Memory / Span

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```csharp
string input = "2024-01-15";
string[] parts = input.Split('-'); // Allocates array + 3 strings!
int year = int.Parse(parts[0]);
```

### Phát hiện

```bash
rg --type cs "\.Split\(|\.Substring\(" -n
rg --type cs "Span<|ReadOnlySpan<|AsSpan\(" -n
```

### Giải pháp

❌ **BAD**
```csharp
var parts = date.Split('-'); // 4 allocations
```

✅ **GOOD**
```csharp
ReadOnlySpan<char> date = "2024-01-15".AsSpan();
int year = int.Parse(date[..4]);   // No allocation
int month = int.Parse(date[5..7]); // No allocation
int day = int.Parse(date[8..10]);  // No allocation
```

### Phòng ngừa
- [ ] `Span<T>` / `ReadOnlySpan<T>` for parsing and slicing
- [ ] `AsSpan()` instead of `Substring()`
- Tool: BenchmarkDotNet with `[MemoryDiagnoser]`

---

## Pattern 10: JSON Serialization Overhead

### Tên
JSON Serialization Overhead (Missing Source Generator)

### Phân loại
Performance / JSON / Serialization

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```csharp
var json = JsonSerializer.Serialize(obj); // Reflection-based
// AOT: doesn't work at all!
```

### Phát hiện

```bash
rg --type cs "JsonSerializer\.(Serialize|Deserialize)" -n
rg --type cs "JsonSerializable|JsonSerializerContext" -n
```

### Giải pháp

❌ **BAD**
```csharp
var json = JsonSerializer.Serialize(user); // Reflection-based
```

✅ **GOOD**
```csharp
[JsonSerializable(typeof(User))]
[JsonSerializable(typeof(List<User>))]
internal partial class AppJsonContext : JsonSerializerContext { }

var json = JsonSerializer.Serialize(user, AppJsonContext.Default.User);
```

### Phòng ngừa
- [ ] Source generators for high-throughput JSON
- [ ] Required for AOT compilation
- Tool: `System.Text.Json` source generator

---

## Pattern 11: EF Core Query Tracking

### Tên
EF Core Query Tracking (Tracking Overhead For Read-Only)

### Phân loại
Performance / EF Core / Tracking

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```csharp
var users = _db.Users.ToList(); // Default: tracked
// Each entity stored in change tracker
// For read-only: 100% overhead, 0% benefit
```

### Phát hiện

```bash
rg --type cs "\.AsNoTracking\(\)" -n
rg --type cs "QueryTrackingBehavior" -n
```

### Giải pháp

❌ **BAD**
```csharp
var users = _db.Users.Where(u => u.Active).ToList(); // Tracked!
return users.Select(u => new UserDto(u.Id, u.Name));
```

✅ **GOOD**
```csharp
var users = _db.Users
    .AsNoTracking()
    .Where(u => u.Active)
    .Select(u => new UserDto(u.Id, u.Name))
    .ToList();
```

### Phòng ngừa
- [ ] `.AsNoTracking()` for all read-only queries
- [ ] Project to DTOs in query
- Tool: EF Core query tags, MiniProfiler

---

## Pattern 12: Connection Pool Tuning

### Tên
Connection Pool Tuning (Default Pool Size Insufficient)

### Phân loại
Performance / Database / Connection

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```
Default SQL Server pool: max 100
Under load: all in use → new requests queue → timeout
Or: pool too large → DB overwhelmed
```

### Phát hiện

```bash
rg --type cs "Max Pool Size|Min Pool Size" -n
rg "Pooling|pool_size" -n --glob "*appsettings*"
```

### Giải pháp

❌ **BAD**
```json
{ "ConnectionStrings": { "Default": "Server=db;Database=app;..." } }
```

✅ **GOOD**
```json
{
  "ConnectionStrings": {
    "Default": "Server=db;Database=app;Max Pool Size=30;Min Pool Size=5;Connection Timeout=15;"
  }
}
```

### Phòng ngừa
- [ ] Tune `Max Pool Size` based on load testing
- [ ] Monitor pool metrics with `dotnet-counters`
- Tool: `dotnet-counters`, Azure SQL metrics

---

## Pattern 13: Response Caching Thiếu

### Tên
Response Caching Thiếu (No Caching For Semi-Static Content)

### Phân loại
Performance / HTTP / Caching

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```
GET /api/products (rarely changes, requested 1000x/min)
→ DB query every request → same response 99% of the time
```

### Phát hiện

```bash
rg --type cs "OutputCache|ResponseCache|IMemoryCache" -n
rg --type cs "AddOutputCache" -n
```

### Giải pháp

❌ **BAD**
```csharp
[HttpGet("products")]
public async Task<IActionResult> GetProducts()
    => Ok(await _db.Products.ToListAsync()); // DB hit every request
```

✅ **GOOD**
```csharp
// Output caching (.NET 7+):
[HttpGet("products")]
[OutputCache(Duration = 60)]
public async Task<IActionResult> GetProducts()
    => Ok(await _db.Products.ToListAsync());

// Or application-level cache:
var products = await _cache.GetOrCreateAsync("products", async entry =>
{
    entry.AbsoluteExpirationRelativeToNow = TimeSpan.FromMinutes(5);
    return await _db.Products.AsNoTracking().ToListAsync();
});
```

### Phòng ngừa
- [ ] `[OutputCache]` for semi-static endpoints
- [ ] `IMemoryCache` / `IDistributedCache` for data caching
- Tool: `AddOutputCache()`, Redis

---

## Pattern 14: Output Caching Thiếu

### Tên
Output Caching Thiếu (Server-Side Cache Not Enabled)

### Phân loại
Performance / ASP.NET / Caching

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```
Response Caching (HTTP headers) vs Output Caching (server-side):
├── Response Caching: relies on client/proxy
├── Output Caching: server stores cached response
└── Output Caching: more control, tag-based invalidation
```

### Phát hiện

```bash
rg --type cs "AddOutputCache|UseOutputCache" -n
rg --type cs "EvictByTag" -n
```

### Giải pháp

❌ **BAD**
```csharp
[ResponseCache(Duration = 60)] // Only HTTP headers
public IActionResult GetData() => Ok(_service.GetData());
```

✅ **GOOD**
```csharp
// Program.cs:
builder.Services.AddOutputCache(options =>
{
    options.AddPolicy("Products", b =>
        b.Expire(TimeSpan.FromMinutes(5)).Tag("products"));
});
app.UseOutputCache();

// Controller:
[HttpGet("products")]
[OutputCache(PolicyName = "Products")]
public async Task<IActionResult> GetProducts()
    => Ok(await _productService.GetAllAsync());

// Invalidation on write:
[HttpPost("products")]
public async Task<IActionResult> Create(CreateDto dto, IOutputCacheStore cache)
{
    var product = await _productService.CreateAsync(dto);
    await cache.EvictByTagAsync("products", default);
    return CreatedAtAction(nameof(GetProducts), product);
}
```

### Phòng ngừa
- [ ] Output Caching for semi-static endpoints
- [ ] Tag-based invalidation for related data
- Tool: ASP.NET Core 7+ `OutputCache` middleware