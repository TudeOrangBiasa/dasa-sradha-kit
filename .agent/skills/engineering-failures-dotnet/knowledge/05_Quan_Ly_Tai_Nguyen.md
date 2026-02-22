# Domain 05: Quản Lý Tài Nguyên (Resource Management)

> .NET/C# patterns liên quan đến quản lý tài nguyên: IDisposable, memory, connections, GC.

| Thuộc tính | Giá trị |
|-----------|---------|
| **Lĩnh vực** | Quản Lý Tài Nguyên |
| **Số mẫu** | 12 |
| **Ngôn ngữ** | C# / .NET 8+ |
| **Ngày cập nhật** | 2026-02-18 |

---

## Pattern 01: IDisposable Không Dispose

### Tên
IDisposable Không Dispose (Missing using/Dispose)

### Phân loại
Resource Management / IDisposable / Unmanaged Resources

### Mức nghiêm trọng
CRITICAL 🔴

> Object implement `IDisposable` nhưng không được `Dispose()`. Unmanaged resources leak cho đến GC Finalizer — timing không xác định.

### Vấn đề

```
IDisposable Lifecycle:

  ĐÚNG:                              SAI:
  using var conn = new SqlConnection()   var conn = new SqlConnection()
       │                                      │
  conn.Open() + query                   conn.Open() + query
       │                                      │
  Dispose() ← tự động                  return result
       │                                      │
  [Connection returned to pool]         [Connection LEAKED!]
                                        [Pool dần exhausted]
```

### Phát hiện

```bash
rg --type cs "new\s+(SqlConnection|FileStream|HttpClient|StreamReader)\s*\(" | grep -v "using"
```

### Giải pháp

**BAD:**
```csharp
var conn = new SqlConnection(connStr);
conn.Open();
var cmd = new SqlCommand("SELECT * FROM Users WHERE Id = @id", conn);
// conn, cmd — NOT disposed!
```

**GOOD:**
```csharp
await using var conn = new SqlConnection(connStr);
await conn.OpenAsync();
await using var cmd = new SqlCommand("SELECT * FROM Users WHERE Id = @id", conn);
cmd.Parameters.AddWithValue("@id", id);
await using var reader = await cmd.ExecuteReaderAsync();
```

### Phòng ngừa

- [ ] Mọi `IDisposable` phải dùng `using` statement
- [ ] Enable CA2000: `dotnet_diagnostic.CA2000.severity = error`
- [ ] Enable CA1001 cho classes owning disposable fields

---

## Pattern 02: HttpClient Socket Exhaustion

### Tên
HttpClient Socket Exhaustion (Cạn Kiệt Socket)

### Phân loại
Resource Management / Network / HTTP

### Mức nghiêm trọng
CRITICAL 🔴

> `new HttpClient()` mỗi request → socket TIME_WAIT 240s → ephemeral port exhaustion. Singleton → DNS stale.

### Vấn đề

```
new HttpClient() per request:
  Request 1: socket A → Dispose → TIME_WAIT (240s!)
  Request 2: socket B → Dispose → TIME_WAIT (240s!)
  ...65535 requests → NO PORTS LEFT! ❌
```

### Phát hiện

```bash
rg --type cs "new\s+HttpClient\s*\(" -n
rg --type cs "HttpClient" | grep -v "IHttpClientFactory\|AddHttpClient"
```

### Giải pháp

**BAD:**
```csharp
using var client = new HttpClient(); // Socket leaked 240s
return await client.GetStringAsync(url);
```

**GOOD — IHttpClientFactory:**
```csharp
// Program.cs
builder.Services.AddHttpClient("Api", client =>
{
    client.BaseAddress = new Uri("https://api.example.com");
    client.Timeout = TimeSpan.FromSeconds(10);
}).ConfigurePrimaryHttpMessageHandler(() => new SocketsHttpHandler
{
    PooledConnectionLifetime = TimeSpan.FromMinutes(2),
    MaxConnectionsPerServer = 50,
});

// Service
public class ApiService(IHttpClientFactory factory)
{
    public async Task<string> Call(string endpoint)
    {
        using var client = factory.CreateClient("Api");
        return await client.GetStringAsync(endpoint);
    }
}
```

### Phòng ngừa

- [ ] KHÔNG `new HttpClient()` — dùng `IHttpClientFactory`
- [ ] Set `PooledConnectionLifetime` cho DNS refresh

---

## Pattern 03: DI Lifetime Mismatch

### Tên
DI Lifetime Mismatch (Singleton Inject Scoped Service)

### Phân loại
Resource Management / DI / Service Lifetime

### Mức nghiêm trọng
CRITICAL 🔴

> Singleton inject Scoped → Scoped becomes Singleton → DbContext shared across requests → concurrency bugs.

### Vấn đề

```
Singleton (lives forever)
  └── inject Scoped (DbContext)
       └── DbContext now shared across ALL requests!
            Thread A: context.Users.Where(...)
            Thread B: context.Orders.Where(...)
            → InvalidOperationException / data corruption!
```

### Phát hiện

```bash
rg --type cs "AddSingleton<" -n
rg --type cs "DbContext\s+\w+" | grep -v "AddDbContext\|AddScoped"
```

### Giải pháp

**BAD:**
```csharp
builder.Services.AddSingleton<ICacheService, CacheService>();
public class CacheService(AppDbContext db) : ICacheService // Scoped injected!
{
    public async Task<User?> Get(int id) => await db.Users.FindAsync(id); // CRASH!
}
```

**GOOD — IServiceScopeFactory:**
```csharp
builder.Services.AddSingleton<ICacheService, CacheService>();
public class CacheService(IServiceScopeFactory scopeFactory) : ICacheService
{
    public async Task<User?> Get(int id)
    {
        using var scope = scopeFactory.CreateScope();
        var db = scope.ServiceProvider.GetRequiredService<AppDbContext>();
        return await db.Users.FindAsync(id);
    }
}
```

### Phòng ngừa

- [ ] `ValidateScopes = true` trong Development
- [ ] `ValidateOnBuild = true` cho startup validation
- [ ] Singleton KHÔNG inject Scoped — dùng `IServiceScopeFactory`

---

## Pattern 04: Large Object Heap Fragmentation

### Tên
LOH Fragmentation (Large Object Heap Phân Mảnh)

### Phân loại
Resource Management / GC / Memory

### Mức nghiêm trọng
HIGH 🟠

> Objects > 85KB → LOH. LOH không compact mặc định → fragmentation → OOM dù còn RAM.

### Vấn đề

```
LOH: [85KB] [FREE 20KB] [85KB] [FREE 30KB] [85KB]
     Request 50KB allocation → no contiguous block → OOM! ❌
```

### Phát hiện

```bash
rg --type cs "new\s+byte\[" -n
rg --type cs "ArrayPool" -n
```

### Giải pháp

**BAD:**
```csharp
var buffer = new byte[128 * 1024]; // > 85KB → LOH → fragmentation
```

**GOOD — ArrayPool:**
```csharp
var buffer = ArrayPool<byte>.Shared.Rent(128 * 1024);
try {
    await stream.ReadAsync(buffer);
} finally {
    ArrayPool<byte>.Shared.Return(buffer);
}
```

### Phòng ngừa

- [ ] `ArrayPool<T>.Shared` cho buffers > 85KB
- [ ] `RecyclableMemoryStream` thay `MemoryStream`
- [ ] Monitor: `dotnet-counters monitor --counters System.Runtime`

---

## Pattern 05: Finalizer Abuse

### Tên
Finalizer Abuse (Dùng Finalizer Thay IDisposable)

### Phân loại
Resource Management / GC / Finalization

### Mức nghiêm trọng
MEDIUM 🟡

> Finalizer chạy timing không xác định, single-threaded → bottleneck. Object survives extra GC generation.

### Phát hiện

```bash
rg --type cs "~\w+\(\)" -n
```

### Giải pháp

**BAD:**
```csharp
public class FileProcessor {
    private IntPtr handle;
    ~FileProcessor() { CloseHandle(handle); } // When? Unknown!
}
```

**GOOD — Dispose pattern:**
```csharp
public class FileProcessor : IDisposable {
    private IntPtr handle;
    private bool disposed;
    public void Dispose() { Dispose(true); GC.SuppressFinalize(this); }
    protected virtual void Dispose(bool disposing) {
        if (disposed) return;
        if (handle != IntPtr.Zero) { CloseHandle(handle); handle = IntPtr.Zero; }
        disposed = true;
    }
    ~FileProcessor() => Dispose(false);
}
```

### Phòng ngừa

- [ ] Prefer `IDisposable` + `using` over Finalizer
- [ ] Call `GC.SuppressFinalize(this)` trong `Dispose()`
- [ ] CA1063: Implement IDisposable correctly

---

## Pattern 06: Event Handler Leak

### Tên
Event Handler Leak (Rò Rỉ Qua Event Handler)

### Phân loại
Resource Management / GC / Events

### Mức nghiêm trọng
HIGH 🟠

> Subscribe (`+=`) không unsubscribe (`-=`). Publisher giữ strong reference → subscriber never GC'd.

### Vấn đề

```
Long-lived Publisher:
  delegates: [sub1.OnEvent, sub2.OnEvent, sub3.OnEvent, ...]
  → sub1 đã dispose nhưng vẫn bị giữ reference!
  → Memory leak grows with subscriber count
```

### Phát hiện

```bash
echo "Subscribe:" && rg --type cs "\+=" -c 2>/dev/null
echo "Unsubscribe:" && rg --type cs "-=" -c 2>/dev/null
```

### Giải pháp

**BAD:**
```csharp
public class OrderVM : IDisposable {
    public OrderVM(IEventBus bus) { bus.OrderUpdated += OnUpdate; }
    public void Dispose() { } // Forgot -= !
}
```

**GOOD:**
```csharp
public class OrderVM : IDisposable {
    private readonly IEventBus bus;
    public OrderVM(IEventBus bus) { this.bus = bus; bus.OrderUpdated += OnUpdate; }
    public void Dispose() { bus.OrderUpdated -= OnUpdate; }
}
```

### Phòng ngừa

- [ ] Mọi `+=` phải có `-=` trong `Dispose()`
- [ ] Prefer `IObservable<T>` (subscription returns IDisposable)

---

## Pattern 07: Static Collection Growth

### Tên
Static Collection Growth (Static Cache Tăng Vô Hạn)

### Phân loại
Resource Management / Memory / Cache

### Mức nghiêm trọng
HIGH 🟠

> Static `ConcurrentDictionary` làm cache không eviction → grow vô hạn → OOM.

### Phát hiện

```bash
rg --type cs "static.*(?:Dictionary|ConcurrentDictionary)<" -n
```

### Giải pháp

**BAD:**
```csharp
private static readonly ConcurrentDictionary<string, byte[]> cache = new();
public byte[] Get(string key) => cache.GetOrAdd(key, LoadFromDb); // Only add!
```

**GOOD — IMemoryCache:**
```csharp
builder.Services.AddMemoryCache(o => o.SizeLimit = 1000);

public class DataService(IMemoryCache cache) {
    public byte[] Get(string key) => cache.GetOrCreate(key, entry => {
        entry.SetSlidingExpiration(TimeSpan.FromMinutes(5));
        entry.SetSize(1);
        return LoadFromDb(key);
    })!;
}
```

### Phòng ngừa

- [ ] KHÔNG static `Dictionary` làm cache — dùng `IMemoryCache`
- [ ] Set `SizeLimit` và expiration

---

## Pattern 08: Stream Không Close

### Tên
Stream Không Close (FileStream/NetworkStream Missing Dispose)

### Phân loại
Resource Management / I/O / Streams

### Mức nghiêm trọng
HIGH 🟠

> FileStream, NetworkStream không dispose → file locks held, connections leaked.

### Phát hiện

```bash
rg --type cs "new\s+(File|Network|Buffered|Crypto)Stream\s*\(" | grep -v "using"
```

### Giải pháp

**BAD:**
```csharp
var stream = new FileStream("data.bin", FileMode.Open);
var reader = new BinaryReader(stream);
var data = reader.ReadBytes(1024);
// NOT disposed → file locked!
```

**GOOD:**
```csharp
await using var stream = new FileStream("data.bin", FileMode.Open, FileAccess.Read);
using var reader = new BinaryReader(stream);
var data = reader.ReadBytes(1024);
```

### Phòng ngừa

- [ ] Mọi Stream phải `using` / `await using`
- [ ] CA2000 analyzer

---

## Pattern 09: Timer Leak

### Tên
Timer Leak (Timer Không Dispose)

### Phân loại
Resource Management / Threading / Timers

### Mức nghiêm trọng
MEDIUM 🟡

> Timer callback giữ `this` alive → object never GC'd. Timer chạy forever.

### Phát hiện

```bash
rg --type cs "new\s+(System\.Timers\.Timer|Timer|PeriodicTimer)\s*\(" -n
```

### Giải pháp

**BAD:**
```csharp
var timer = new Timer(5000);
timer.Elapsed += (s, e) => CheckHealth(); // `this` captured forever!
timer.Start(); // No Dispose
```

**GOOD — PeriodicTimer (.NET 6+):**
```csharp
public class HealthChecker : IDisposable {
    private readonly PeriodicTimer timer = new(TimeSpan.FromSeconds(5));
    private readonly CancellationTokenSource cts = new();
    public async Task StartAsync() {
        while (await timer.WaitForNextTickAsync(cts.Token)) await CheckAsync();
    }
    public void Dispose() { cts.Cancel(); timer.Dispose(); cts.Dispose(); }
}
```

### Phòng ngừa

- [ ] Prefer `PeriodicTimer` over `System.Timers.Timer`
- [ ] Timer-owning class MUST implement `IDisposable`

---

## Pattern 10: WeakReference Misuse

### Tên
WeakReference Misuse (WeakRef Cho Object Cần Sống)

### Phân loại
Resource Management / GC / References

### Mức nghiêm trọng
MEDIUM 🟡

> `WeakReference<T>` cho objects cần tồn tại → GC thu hồi bất ngờ → data loss.

### Phát hiện

```bash
rg --type cs "WeakReference" -n
```

### Giải pháp

**BAD:**
```csharp
// Cache dùng WeakRef → GC evict bất kỳ lúc nào
Dictionary<string, WeakReference<Data>> cache = new();
```

**GOOD — IMemoryCache:**
```csharp
return memoryCache.GetOrCreate(key, entry => {
    entry.SetSlidingExpiration(TimeSpan.FromMinutes(10));
    return LoadExpensive(key);
})!;
```

### Phòng ngừa

- [ ] WeakReference CHỈ cho optional data (acceptable nếu mất)
- [ ] Prefer `IMemoryCache` cho caching

---

## Pattern 11: MemoryPool Return Thiếu

### Tên
MemoryPool Return Thiếu (Rent Without Return)

### Phân loại
Resource Management / Memory / Pooling

### Mức nghiêm trọng
HIGH 🟠

> `ArrayPool<T>.Rent()` không `Return()` → pool exhausted → fallback to allocation.

### Phát hiện

```bash
rg --type cs "\.Rent\(" -n
rg --type cs "\.Return\(" -n
```

### Giải pháp

**BAD:**
```csharp
var buffer = ArrayPool<byte>.Shared.Rent(4096);
await stream.ReadAsync(buffer);
// NOT returned!
```

**GOOD:**
```csharp
var buffer = ArrayPool<byte>.Shared.Rent(4096);
try {
    var bytesRead = await stream.ReadAsync(buffer);
    ProcessData(buffer.AsSpan(0, bytesRead));
} finally {
    ArrayPool<byte>.Shared.Return(buffer, clearArray: true);
}
```

### Phòng ngừa

- [ ] Mọi `Rent()` phải có `Return()` trong `finally`
- [ ] `clearArray: true` cho sensitive data
- [ ] `using var owner = MemoryPool<byte>.Shared.Rent(size)` pattern

---

## Pattern 12: Span/Memory Lifetime

### Tên
Span/Memory Lifetime Violation

### Phân loại
Resource Management / Memory / Stack Safety

### Mức nghiêm trọng
HIGH 🟠

> `Span<T>` stack-only, không thể escape scope. `Memory<T>` phải quản lý source lifetime. Vi phạm → data corruption.

### Phát hiện

```bash
rg --type cs "stackalloc" -n
rg --type cs "Span<\w+>\s+\w+\s*;" | grep -v "var\|local"
```

### Giải pháp

**BAD:**
```csharp
// Memory outlives source — caller có thể corrupt
public Memory<byte> GetSlice(byte[] source) => source.AsMemory(0, 100);
```

**GOOD — IMemoryOwner:**
```csharp
public int Parse(ReadOnlySpan<byte> data) { // Span as param = OK
    var header = data[..4];
    return BinaryPrimitives.ReadInt32BigEndian(header);
}
public IMemoryOwner<byte> CreateBuffer(int size) {
    return MemoryPool<byte>.Shared.Rent(size); // Caller owns lifecycle
}
// Usage: using var owner = parser.CreateBuffer(4096);
```

### Phòng ngừa

- [ ] `Span<T>` chỉ local variables và parameters
- [ ] `Memory<T>` + `IMemoryOwner<T>` cho async/stored scenarios
- [ ] Compiler enforces Span rules — `Memory<T>` needs manual care

---

## Bảng Tóm Tắt

| # | Pattern | Mức độ | Tác động |
|---|---------|--------|----------|
| 01 | IDisposable Không Dispose | 🔴 CRITICAL | Resource leak, pool exhaustion |
| 02 | HttpClient Socket Exhaustion | 🔴 CRITICAL | Port exhaustion |
| 03 | DI Lifetime Mismatch | 🔴 CRITICAL | Data corruption |
| 04 | LOH Fragmentation | 🟠 HIGH | OOM despite free memory |
| 05 | Finalizer Abuse | 🟡 MEDIUM | Delayed cleanup |
| 06 | Event Handler Leak | 🟠 HIGH | Growing heap |
| 07 | Static Collection Growth | 🟠 HIGH | Unbounded memory |
| 08 | Stream Không Close | 🟠 HIGH | File locks, connection leak |
| 09 | Timer Leak | 🟡 MEDIUM | Background task leak |
| 10 | WeakReference Misuse | 🟡 MEDIUM | Random eviction |
| 11 | MemoryPool Return Thiếu | 🟠 HIGH | Pool exhaustion |
| 12 | Span/Memory Lifetime | 🟠 HIGH | Data corruption |

## Quick Scan Script

```bash
#!/bin/bash
echo "=== .NET Resource Management Audit ==="
echo -e "\n--- RM-01: Missing Dispose ---"
rg --type cs "new\s+(SqlConnection|FileStream|HttpClient)\s*\(" 2>/dev/null | grep -v "using"
echo -e "\n--- RM-02: HttpClient ---"
rg --type cs "new\s+HttpClient\s*\(" 2>/dev/null
echo -e "\n--- RM-03: DI Lifetime ---"
rg --type cs "AddSingleton" 2>/dev/null | head -10
echo -e "\n--- RM-06: Events ---"
echo "Subscribe:" && rg --type cs "\+=" -c 2>/dev/null
echo "Unsubscribe:" && rg --type cs "-=" -c 2>/dev/null
echo -e "\n--- RM-07: Static Cache ---"
rg --type cs "static.*Dictionary\|static.*ConcurrentDictionary" 2>/dev/null
echo -e "\n--- RM-11: ArrayPool ---"
echo "Rent:" && rg --type cs "\.Rent\(" -c 2>/dev/null
echo "Return:" && rg --type cs "\.Return\(" -c 2>/dev/null
echo -e "\n=== Scan Complete ==="
```
