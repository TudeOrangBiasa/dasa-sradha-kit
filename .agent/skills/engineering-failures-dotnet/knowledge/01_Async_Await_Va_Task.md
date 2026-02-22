# Domain 01: Bất Đồng Bộ / Async & Await và Task
# Domain 01: Asynchronous Programming - Async/Await & Task

**Lĩnh vực:** .NET Engineering - Backend / Full-stack
**Ngôn ngữ:** C#
**Tổng số patterns:** 16
**Cập nhật:** 2026-02-18

---

## Tổng Quan Domain

Lập trình bất đồng bộ trong .NET là một trong những nguồn gốc phổ biến nhất của các lỗi hiệu năng, deadlock, và mất dữ liệu trong môi trường sản xuất. Các lỗi này thường không xuất hiện trong môi trường phát triển vì tải thấp, nhưng bùng phát khi ứng dụng chịu tải thực tế.

```
PHÂN LOẠI MỨC ĐỘ NGHIÊM TRỌNG
================================
CRITICAL  - Có thể gây crash ứng dụng, deadlock hoàn toàn, mất dữ liệu
HIGH      - Gây suy giảm hiệu năng nghiêm trọng, lỗi không nhất quán
MEDIUM    - Gây memory leak, hiệu năng kém, khó debug
LOW       - Code smell, vi phạm best practice
```

---

## Pattern 01: Async Void

### 1. Tên
**Async Void** (Async Void Method)

### 2. Phân Loại
- **Domain:** Async/Await & Task
- **Subcategory:** Exception Handling / Fire-and-Forget

### 3. Mức Nghiêm Trọng
**CRITICAL** - Gây crash ứng dụng không thể bắt exception

### 4. Vấn Đề

`async void` là một trong những lỗi nguy hiểm nhất trong .NET async programming. Khi một method `async void` ném exception, exception đó được đẩy vào `SynchronizationContext` hiện tại. Nếu không có handler phù hợp, ứng dụng sẽ crash ngay lập tức mà không có cách nào bắt exception từ caller.

**Cơ chế gây lỗi:**

```
CALLER CODE                    ASYNC VOID METHOD
     │                               │
     │──── gọi method ─────────────► │
     │                               │ await task...
     │ (caller tiếp tục, không await)│
     │                               │ ❌ Exception xảy ra
     │                               │
     │                        Exception được đẩy vào
     │                        SynchronizationContext
     │                               │
     │                        Nếu không có UnhandledException handler
     │                               │
     │                        ☠️  APPLICATION CRASH
     │
     ├── try { AsyncVoidMethod(); }
     └── catch { } ← KHÔNG BAO GIỜ BAT ĐƯỢC EXCEPTION NÀY
```

**Tại sao `async Task` không gặp vấn đề này:**

```
async Task Method() → Exception được capture trong Task object
                     → Caller có thể await và catch exception
                     → Exception không bị "mất"

async void Method() → Exception KHÔNG được capture trong Task
                     → Caller không thể catch
                     → Exception lan truyền lên SynchronizationContext
                     → Crash nếu không có global handler
```

**Trường hợp hợp lệ DUY NHẤT của async void:**
- Event handlers (vì delegate signature yêu cầu `void`)
- Ngay cả với event handlers, cần bọc try-catch bên trong

### 5. Phát Hiện Trong Mã Nguồn

**Dấu hiệu nhận biết:**
- Method có chữ ký `async void` (không phải event handler)
- Ứng dụng crash bí ẩn không có stack trace rõ ràng
- Exception không được log mặc dù có try-catch ở caller
- Crash chỉ xuất hiện dưới tải cao

**Regex patterns cho ripgrep:**

```bash
# Tìm tất cả async void methods (không phải event handler)
rg "async\s+void\s+\w+" --type cs

# Tìm async void với parameter không phải (object sender, EventArgs e)
rg "async\s+void\s+\w+\s*\([^)]*\)" --type cs

# Tìm async void trong class (không phải interface)
rg "^\s+(private|public|protected|internal)\s+async\s+void" --type cs

# Tìm nơi gọi async void mà không có await
rg "(?<!await\s)\b\w+Async\s*\(" --type cs
```

**Ví dụ output log khi lỗi:**
```
Unhandled exception. System.InvalidOperationException: ...
   at Program.<Main>d__0.MoveNext()
--- End of stack trace ---
```

### 6. Giải Pháp

| Tình huống | Sai | Đúng |
|------------|-----|------|
| Method thường | `async void DoWork()` | `async Task DoWork()` |
| Event handler | `async void OnClick(...)` | `async void OnClick(...)` + try-catch bên trong |
| Fire-and-forget | `async void FireForget()` | Dùng `_ = Task.Run(...)` hoặc pattern riêng |

**Ví dụ SAI:**

```csharp
// BAD: async void - exception sẽ crash application
public async void ProcessDataAsync(int id)
{
    var data = await _repository.GetAsync(id);
    await _service.ProcessAsync(data);
    // Nếu exception xảy ra ở đây -> APPLICATION CRASH
}

// BAD: async void trong service class
public class DataService
{
    public async void RefreshCacheAsync()
    {
        await Task.Delay(1000);
        throw new InvalidOperationException("Cache refresh failed");
        // Caller không thể bắt exception này
    }
}

// BAD: Gọi async void và nghĩ rằng exception được bắt
public void DoSomething()
{
    try
    {
        RefreshCacheAsync(); // Không await, không thể bắt exception
    }
    catch (Exception ex)
    {
        // KHÔNG BAO GIỜ vào đây dù RefreshCacheAsync ném exception
        _logger.LogError(ex, "Error");
    }
}
```

**Ví dụ ĐÚNG:**

```csharp
// GOOD: Dùng async Task thay vì async void
public async Task ProcessDataAsync(int id)
{
    var data = await _repository.GetAsync(id);
    await _service.ProcessAsync(data);
    // Exception được capture trong Task, caller có thể catch
}

// GOOD: Event handler - trường hợp hợp lệ duy nhất
// Nhưng PHẢI có try-catch bên trong
private async void Button_Click(object sender, EventArgs e)
{
    try
    {
        await ProcessDataAsync(42);
    }
    catch (Exception ex)
    {
        // Bắt exception ở đây, KHÔNG để lan ra ngoài
        MessageBox.Show($"Error: {ex.Message}");
        _logger.LogError(ex, "Button click failed");
    }
}

// GOOD: Fire-and-forget pattern an toàn
public void StartBackgroundWork()
{
    // Option 1: Task.Run với error handling
    _ = Task.Run(async () =>
    {
        try
        {
            await DoBackgroundWorkAsync();
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Background work failed");
        }
    });
}

// GOOD: Extension method cho safe fire-and-forget
public static class TaskExtensions
{
    public static void FireAndForget(
        this Task task,
        Action<Exception>? errorHandler = null)
    {
        task.ContinueWith(t =>
        {
            if (t.IsFaulted)
            {
                var ex = t.Exception?.InnerException ?? t.Exception;
                errorHandler?.Invoke(ex!);
            }
        }, TaskContinuationOptions.OnlyOnFaulted);
    }
}

// Usage:
DoWorkAsync().FireAndForget(ex => _logger.LogError(ex, "Failed"));
```

### 7. Phòng Ngừa

**Checklist:**
- [ ] Không bao giờ dùng `async void` ngoài event handlers
- [ ] Với event handlers, luôn có try-catch bên trong
- [ ] Enable Roslyn analyzer để tự động phát hiện
- [ ] Code review checklist bao gồm kiểm tra async void
- [ ] Đăng ký `UnhandledException` handler ở startup để log trước khi crash

**Roslyn Analyzer Rules:**
```xml
<!-- Trong .editorconfig -->
dotnet_diagnostic.CA2007.severity = warning  <!-- ConfigureAwait -->
dotnet_diagnostic.VSTHRD100.severity = error <!-- Avoid async void -->
dotnet_diagnostic.VSTHRD101.severity = error <!-- Async void event handler exception -->
```

**Global Exception Handler (NET 6+):**
```csharp
// Program.cs - Bắt exception từ async void làm last resort
AppDomain.CurrentDomain.UnhandledException += (sender, args) =>
{
    var ex = args.ExceptionObject as Exception;
    Log.Fatal(ex, "Unhandled exception - async void likely culprit");
};

TaskScheduler.UnobservedTaskException += (sender, args) =>
{
    Log.Error(args.Exception, "Unobserved task exception");
    args.SetObserved(); // Ngăn crash (không khuyến khích production)
};
```

---

## Pattern 02: Deadlock SynchronizationContext

### 1. Tên
**Deadlock do SynchronizationContext** (SynchronizationContext Deadlock)

### 2. Phân Loại
- **Domain:** Async/Await & Task
- **Subcategory:** Deadlock / Thread Synchronization

### 3. Mức Nghiêm Trọng
**CRITICAL** - Gây deadlock hoàn toàn, request treo vô thời hạn

### 4. Vấn Đề

Deadlock xảy ra khi code synchronous gọi `.Result` hoặc `.Wait()` trên một Task bất đồng bộ trong môi trường có `SynchronizationContext` (ASP.NET Classic, WinForms, WPF). Luồng bị block chờ Task hoàn thành, nhưng Task cần quay lại luồng đó để tiếp tục sau `await` - dẫn đến deadlock hoàn toàn.

**Cơ chế deadlock:**

```
UI Thread / ASP.NET Request Thread
           │
           │ 1. Gọi GetResultSync()
           │
           ▼
    GetResultSync()
    {
        return GetDataAsync().Result;  ← 2. BLOCK thread này
    }               │
                    │ 3. Task bắt đầu chạy...
                    │    await HttpClient.GetAsync(...)
                    │    Response nhận được!
                    │
                    │ 4. await cố gắng resume trên SynchronizationContext
                    │    (tức là UI Thread / Request Thread)
                    │
                    │ 5. Nhưng thread đó đang bị BLOCK ở bước 2!
                    │
                    ▼
             ☠️  DEADLOCK - Không ai nhường, không ai tiến được
```

**Môi trường bị ảnh hưởng:**
- ASP.NET (không phải ASP.NET Core) - có SynchronizationContext
- WinForms / WPF - có UI SynchronizationContext
- Unit Test runners cũ - có SynchronizationContext riêng

**ASP.NET Core KHÔNG bị ảnh hưởng** vì không có SynchronizationContext mặc định.

### 5. Phát Hiện Trong Mã Nguồn

**Dấu hiệu nhận biết:**
- Request treo vô thời hạn (timeout sau thời gian dài)
- `.Result`, `.Wait()`, `.GetAwaiter().GetResult()` trong code async
- Deadlock chỉ xảy ra trong ASP.NET/WinForms, không xảy ra trong Console app
- CPU 0%, request không tiến triển

**Regex patterns cho ripgrep:**

```bash
# Tìm .Result trên Task
rg "\.Result\b" --type cs

# Tìm .Wait() call
rg "\.Wait\(\)" --type cs

# Tìm GetAwaiter().GetResult() pattern
rg "\.GetAwaiter\(\)\.GetResult\(\)" --type cs

# Tìm tất cả blocking calls
rg "\.(Result|Wait\(\)|GetAwaiter\(\)\.GetResult\(\))" --type cs

# Tìm Task.WaitAll và Task.WaitAny
rg "Task\.(WaitAll|WaitAny)\(" --type cs
```

### 6. Giải Pháp

| Tình huống | Sai | Đúng |
|------------|-----|------|
| Lấy kết quả từ async | `task.Result` | `await task` |
| Chờ task xong | `task.Wait()` | `await task` |
| Chờ nhiều tasks | `Task.WaitAll(...)` | `await Task.WhenAll(...)` |
| Code sync buộc phải gọi async | `GetAsync().Result` | Dùng `ConfigureAwait(false)` trong async method |

**Ví dụ SAI:**

```csharp
// BAD: Blocking call gây deadlock trong ASP.NET Classic / WinForms
public class UserController : Controller
{
    private readonly IUserService _service;

    public ActionResult GetUser(int id)
    {
        // DEADLOCK trong ASP.NET Classic!
        var user = _service.GetUserAsync(id).Result;
        return Json(user);
    }
}

// BAD: Wait() cũng gây deadlock
public void LoadData()
{
    _dataService.LoadAsync().Wait(); // DEADLOCK!
    UpdateUI();
}

// BAD: GetAwaiter().GetResult() - không an toàn hơn .Result
public string GetValue()
{
    return _service.GetValueAsync().GetAwaiter().GetResult(); // DEADLOCK!
}
```

**Ví dụ ĐÚNG:**

```csharp
// GOOD: Async all the way
public class UserController : Controller
{
    public async Task<ActionResult> GetUser(int id)
    {
        var user = await _service.GetUserAsync(id);
        return Json(user);
    }
}

// GOOD: Async trong WinForms
private async void Button_Click(object sender, EventArgs e)
{
    try
    {
        var data = await _dataService.LoadAsync();
        UpdateUI(data);
    }
    catch (Exception ex)
    {
        MessageBox.Show(ex.Message);
    }
}

// GOOD: Nếu BUỘC phải gọi async từ sync (tránh khi có thể)
// Chỉ dùng khi không thể thay đổi signature của caller
public string GetValueForcedSync()
{
    // ConfigureAwait(false) trong GetValueAsync tránh capture SynchronizationContext
    // Nhưng cách này vẫn không tốt, chỉ là "ít tệ hơn"
    return Task.Run(() => _service.GetValueAsync()).GetAwaiter().GetResult();
}

// GOOD: Pattern đúng cho library code phải hỗ trợ cả sync và async
public class DataService
{
    // Async implementation với ConfigureAwait(false)
    public async Task<string> GetDataAsync(CancellationToken ct = default)
    {
        var response = await _httpClient.GetAsync("/data", ct)
            .ConfigureAwait(false); // Quan trọng!
        return await response.Content.ReadAsStringAsync(ct)
            .ConfigureAwait(false); // Quan trọng!
    }
}
```

### 7. Phòng Ngừa

**Checklist:**
- [ ] Không dùng `.Result`, `.Wait()` trong code async pipeline
- [ ] Nếu code phải đồng bộ, xem xét lại thiết kế
- [ ] Thêm `ConfigureAwait(false)` trong mọi library method
- [ ] Dùng ASP.NET Core thay vì ASP.NET Classic khi có thể
- [ ] Đặt timeout cho mọi async operation để tránh treo vô hạn

**Roslyn Analyzer Rules:**
```xml
dotnet_diagnostic.VSTHRD002.severity = error  <!-- Avoid problematic synchronous waits -->
dotnet_diagnostic.VSTHRD104.severity = error  <!-- Offer async option -->
dotnet_diagnostic.CA1849.severity = warning   <!-- Call async methods when in async context -->
```

---

## Pattern 03: ConfigureAwait Thiếu

### 1. Tên
**Thiếu ConfigureAwait(false)** (Missing ConfigureAwait in Library Code)

### 2. Phân Loại
- **Domain:** Async/Await & Task
- **Subcategory:** SynchronizationContext / Performance

### 3. Mức Nghiêm Trọng
**HIGH** - Gây deadlock tiềm ẩn và hiệu năng kém trong library code

### 4. Vấn Đề

Sau mỗi `await`, .NET mặc định cố gắng resume execution trên `SynchronizationContext` ban đầu (UI thread, ASP.NET request context). Đây là hành vi tốt cho application code nhưng nguy hiểm và không hiệu quả cho library code vì:

1. **Deadlock tiềm ẩn:** Consumer gọi library với `.Result` → deadlock (xem Pattern 02)
2. **Hiệu năng kém:** Không cần thiết phải marshal về UI thread trong library
3. **Coupling không mong muốn:** Library phụ thuộc vào context của caller

```
APPLICATION CODE                    LIBRARY CODE
        │                                │
  await libMethod()                      │
        │                          await httpClient.GetAsync()
        │                                │
        │                          [cần resume về UI thread]
        │                                │
        │◄──── Resume trên UI ───────────┘
        │      thread (marshal)
        │
        ▼
  Tiếp tục code    ← Đúng cho app code, nhưng
                     KHÔNG CẦN cho library code
                     → Waste thời gian marshal
```

**So sánh với ConfigureAwait(false):**

```
LIBRARY CODE với ConfigureAwait(false)
        │
  await httpClient.GetAsync().ConfigureAwait(false)
        │
  [Resume trên thread pool, không marshal về UI]
        │
  Nhanh hơn, không có nguy cơ deadlock
```

### 5. Phát Hiện Trong Mã Nguồn

**Dấu hiệu nhận biết:**
- Library / NuGet package code có `await` không có `ConfigureAwait(false)`
- Hiệu năng kém không rõ lý do trong code library
- Deadlock xảy ra khi consumer gọi library synchronously

**Regex patterns cho ripgrep:**

```bash
# Tìm await không có ConfigureAwait
rg "await\s+(?!.*ConfigureAwait)" --type cs

# Tìm await trong files có namespace chứa "Library" hoặc "Shared"
rg "await\s+\w+" --type cs --glob "*Library*"

# Kiểm tra tỷ lệ ConfigureAwait coverage
rg "await " --type cs | wc -l
rg "ConfigureAwait\(false\)" --type cs | wc -l

# Tìm await trong using blocks (thường quên ConfigureAwait)
rg "await\s+using" --type cs
```

### 6. Giải Pháp

| Loại code | Cần ConfigureAwait(false)? | Lý do |
|-----------|---------------------------|-------|
| Library / NuGet package | Có | Tránh deadlock, tăng hiệu năng |
| Application (ASP.NET Core) | Không bắt buộc | ASP.NET Core không có SynchronizationContext |
| UI Application (WPF/WinForms) | Không (sau await cần UI context) | Cần UI thread để update UI |
| Unit Tests | Tùy | Không có SynchronizationContext thường |

**Ví dụ SAI:**

```csharp
// BAD: Library code không có ConfigureAwait(false)
public class EmailService
{
    private readonly HttpClient _httpClient;

    public async Task<bool> SendEmailAsync(string to, string subject, string body)
    {
        // Không có ConfigureAwait(false) - nguy hiểm trong library!
        var response = await _httpClient.PostAsJsonAsync("/send", new { to, subject, body });

        // Không có ConfigureAwait(false) - tiếp tục không an toàn
        var result = await response.Content.ReadFromJsonAsync<SendResult>();

        return result?.Success ?? false;
    }
}
```

**Ví dụ ĐÚNG:**

```csharp
// GOOD: Library code với ConfigureAwait(false) đầy đủ
public class EmailService
{
    private readonly HttpClient _httpClient;

    public async Task<bool> SendEmailAsync(
        string to,
        string subject,
        string body,
        CancellationToken cancellationToken = default)
    {
        var response = await _httpClient
            .PostAsJsonAsync("/send", new { to, subject, body }, cancellationToken)
            .ConfigureAwait(false); // Quan trọng!

        var result = await response.Content
            .ReadFromJsonAsync<SendResult>(cancellationToken: cancellationToken)
            .ConfigureAwait(false); // Quan trọng!

        return result?.Success ?? false;
    }
}

// GOOD: Application code (ASP.NET Core) - không cần thiết nhưng không hại
[ApiController]
public class OrderController : ControllerBase
{
    private readonly IOrderService _orderService;

    [HttpPost]
    public async Task<IActionResult> CreateOrder(CreateOrderRequest request)
    {
        // Trong ASP.NET Core, ConfigureAwait(false) không cần thiết
        // nhưng vẫn là good practice vì không có SynchronizationContext
        var order = await _orderService.CreateAsync(request);
        return Ok(order);
    }
}

// GOOD: WPF - phải cẩn thận khi nào dùng ConfigureAwait(false)
private async void SaveButton_Click(object sender, RoutedEventArgs e)
{
    // Step 1: Fetch data (không cần UI thread) - dùng ConfigureAwait(false)
    var data = await _service.FetchDataAsync()
        .ConfigureAwait(false);

    // Step 2: Phải update UI - CẦN quay lại UI thread
    // Dùng Dispatcher vì sau ConfigureAwait(false) không còn ở UI thread
    await Dispatcher.InvokeAsync(() =>
    {
        StatusLabel.Text = "Saved!";
        DataGrid.ItemsSource = data;
    });
}
```

### 7. Phòng Ngừa

**Checklist:**
- [ ] Mọi `await` trong library code đều có `.ConfigureAwait(false)`
- [ ] Sử dụng Roslyn analyzer để enforce
- [ ] Document rõ: library code dùng `ConfigureAwait(false)`, app code tùy ý
- [ ] Sau `ConfigureAwait(false)`, không trực tiếp update UI - dùng Dispatcher

**Roslyn Analyzer Rules:**
```xml
dotnet_diagnostic.CA2007.severity = warning  <!-- ConfigureAwait -->
dotnet_diagnostic.VSTHRD111.severity = error <!-- Use .ConfigureAwait(bool) -->

<!-- Trong .editorconfig cho library projects -->
[*.cs]
dotnet_diagnostic.CA2007.severity = error
```

**Cấu hình cho toàn project (Directory.Build.props):**
```xml
<Project>
  <PropertyGroup>
    <!-- Tắt warning nếu project là app, không phải library -->
    <NoWarn Condition="'$(IsLibrary)' != 'true'">CA2007</NoWarn>
  </PropertyGroup>
</Project>
```

---

## Pattern 04: Task.Run Trong ASP.NET

### 1. Tên
**Lạm Dụng Task.Run Trong ASP.NET** (Misuse of Task.Run in ASP.NET)

### 2. Phân Loại
- **Domain:** Async/Await & Task
- **Subcategory:** Thread Pool / ASP.NET Performance

### 3. Mức Nghiêm Trọng
**HIGH** - Gây thread pool starvation, giảm throughput ASP.NET

### 4. Vấn Đề

`Task.Run` đưa công việc vào thread pool. Trong ASP.NET, mỗi request đã chạy trên thread pool thread. Dùng `Task.Run` để wrap code I/O-bound chỉ lãng phí thread pool thread mà không mang lại lợi ích gì.

```
ASP.NET Request Pipeline

Request 1 → Thread Pool Thread #1
              │
              └─► Task.Run(() => await IoOperation())
                      │
                      └─► Thread Pool Thread #2 (LÃ NG PHÍ!)
                              │
                              └─► Await I/O (thread về pool)
                              │
                              └─► Thread Pool Thread #3 (resume)

THAY VÀO ĐÓ:

Request 1 → Thread Pool Thread #1
              │
              └─► await IoOperationAsync()  (trực tiếp)
                      │
                      └─► I/O operation (thread #1 về pool)
                      │
                      └─► Thread Pool Thread #1 hoặc #X (resume)

→ Ít thread hơn, throughput cao hơn!
```

**Khi nào Task.Run HỢP LÝ trong ASP.NET:**
- CPU-bound work thực sự (tính toán nặng, không phải I/O)
- Cần parallelism thực sự trên nhiều core
- Offload sang background sau response

### 5. Phát Hiện Trong Mã Nguồn

**Dấu hiệu nhận biết:**
- `Task.Run` bọc quanh `async` method hoặc I/O operation
- Thread count cao bất thường trong production
- Throughput thấp dù CPU không cao

**Regex patterns cho ripgrep:**

```bash
# Tìm Task.Run bọc async lambda
rg "Task\.Run\(async" --type cs

# Tìm Task.Run trong controllers/services
rg "Task\.Run\(" --type cs --glob "*Controller*"
rg "Task\.Run\(" --type cs --glob "*Service*"

# Tìm Task.Run() trong code (tất cả)
rg "await\s+Task\.Run\(" --type cs
```

### 6. Giải Pháp

| Pattern | Dùng khi | Không dùng khi |
|---------|----------|----------------|
| `await ioMethodAsync()` | Luôn luôn với I/O | - |
| `Task.Run(cpuWork)` | CPU-bound work nặng | I/O-bound operations |
| `Parallel.ForEach` | CPU-bound parallel | Async I/O parallel |
| `Task.WhenAll` | Nhiều async I/O parallel | - |

**Ví dụ SAI:**

```csharp
// BAD: Task.Run bọc I/O-bound operation
[ApiController]
public class ProductController : ControllerBase
{
    [HttpGet("{id}")]
    public async Task<IActionResult> GetProduct(int id)
    {
        // WRONG: Task.Run với I/O operation - lãng phí thread!
        var product = await Task.Run(async () =>
        {
            return await _repository.GetByIdAsync(id);
        });

        return Ok(product);
    }

    [HttpPost("import")]
    public async Task<IActionResult> ImportProducts(List<Product> products)
    {
        // WRONG: Task.Run với async I/O - double thread waste
        var results = await Task.Run(async () =>
        {
            var tasks = products.Select(p => _repository.SaveAsync(p));
            return await Task.WhenAll(tasks);
        });

        return Ok(results);
    }
}
```

**Ví dụ ĐÚNG:**

```csharp
// GOOD: Gọi trực tiếp async method I/O-bound
[ApiController]
public class ProductController : ControllerBase
{
    [HttpGet("{id}")]
    public async Task<IActionResult> GetProduct(int id)
    {
        // CORRECT: Gọi trực tiếp, không cần Task.Run
        var product = await _repository.GetByIdAsync(id);
        return Ok(product);
    }

    [HttpPost("import")]
    public async Task<IActionResult> ImportProducts(List<Product> products)
    {
        // CORRECT: Parallel I/O không cần Task.Run
        var tasks = products.Select(p => _repository.SaveAsync(p));
        var results = await Task.WhenAll(tasks);
        return Ok(results);
    }

    // CORRECT: Task.Run HỢP LÝ cho CPU-bound work
    [HttpPost("analyze")]
    public async Task<IActionResult> AnalyzeImage(IFormFile image)
    {
        var imageBytes = await image.OpenReadStream()
            .ReadBytesAsync(); // I/O - không cần Task.Run

        // CPU-bound heavy computation - HỢP LÝ dùng Task.Run
        var analysisResult = await Task.Run(() =>
        {
            return _imageAnalyzer.PerformComplexAnalysis(imageBytes);
        });

        return Ok(analysisResult);
    }
}
```

### 7. Phòng Ngừa

**Checklist:**
- [ ] Phân biệt rõ I/O-bound vs CPU-bound trước khi dùng Task.Run
- [ ] I/O-bound: luôn dùng async method trực tiếp
- [ ] CPU-bound: xem xét Task.Run, cân nhắc SemaphoreSlim để giới hạn concurrency
- [ ] Review code: mọi `Task.Run(async () =>` đều là code smell trong ASP.NET

**Roslyn Analyzer Rules:**
```xml
dotnet_diagnostic.VSTHRD105.severity = warning  <!-- Avoid method overloads that assume TaskScheduler.Current -->
```

---

## Pattern 05: Fire-and-Forget Task

### 1. Tên
**Fire-and-Forget Task Không An Toàn** (Unsafe Fire-and-Forget)

### 2. Phân Loại
- **Domain:** Async/Await & Task
- **Subcategory:** Exception Handling / Background Work

### 3. Mức Nghiêm Trọng
**HIGH** - Mất exception, memory leak, hành vi không nhất quán

### 4. Vấn Đề

Fire-and-forget là pattern bắt đầu một Task mà không await, nhưng nếu làm sai sẽ dẫn đến exception bị nuốt, memory leak, và behavior không nhất quán khi shutdown.

```
FIRE-AND-FORGET KHÔNG AN TOÀN

Task.Run(() => DoWork())   ← Task bắt đầu
     │
     │ (caller tiếp tục ngay, không chờ)
     │
     ▼
DoWork() chạy trong background...
     │
     │ ❌ Exception xảy ra!
     │
     ▼
Exception bị nuốt vào TaskScheduler.UnobservedTaskException
     │
     │ Trong .NET 4.5+: ứng dụng KHÔNG crash (nhưng exception BỊ MẤT)
     │ Trong .NET 4.0: ứng dụng có thể CRASH
     │
     ▼
❗ BẠN KHÔNG BIẾT CÓ LỖI XẢY RA
```

**Vấn đề khi ASP.NET app shutdown:**
```
Request đến → Task.Run(backgroundWork) → Response trả về
                    │
              ASP.NET bắt đầu shutdown
                    │
              Background task bị dừng ĐỘT NGỘT
              (IIS recycle, deployment, etc.)
                    │
              ❌ Công việc bị cắt ngang, data corrupt
```

### 5. Phát Hiện Trong Mã Nguồn

**Regex patterns cho ripgrep:**

```bash
# Tìm Task.Run không được await và không assign
rg "^\s+Task\.Run\(" --type cs

# Tìm _ = Task.Run (discard pattern - cần review)
rg "_\s*=\s*Task\.Run\(" --type cs

# Tìm Task bị bỏ (không await, không assign)
rg "(?<!await\s)(?<!var\s\w+\s*=\s*)Task\.(Run|Factory\.StartNew)\(" --type cs
```

### 6. Giải Pháp

| Pattern | An toàn? | Dùng khi |
|---------|----------|----------|
| `_ = Task.Run(...)` không có try-catch | Không | Không bao giờ |
| `Task.Run(async () => { try-catch })` | Có | Background work đơn giản |
| `IHostedService` / `BackgroundService` | Tốt nhất | Background work trong ASP.NET |
| `Channel<T>` producer-consumer | Tốt nhất | Queue-based background work |

**Ví dụ SAI:**

```csharp
// BAD: Fire-and-forget không có error handling
[HttpPost("order")]
public async Task<IActionResult> CreateOrder(CreateOrderRequest request)
{
    var order = await _orderService.CreateAsync(request);

    // WRONG: Exception sẽ bị mất hoàn toàn
    Task.Run(() => _emailService.SendConfirmationAsync(order));

    // WRONG: _ discard nhưng không có error handling
    _ = Task.Run(() => _analyticsService.TrackOrderAsync(order));

    return Ok(order);
}
```

**Ví dụ ĐÚNG:**

```csharp
// GOOD Option 1: Task.Run với proper error handling
[HttpPost("order")]
public async Task<IActionResult> CreateOrder(CreateOrderRequest request)
{
    var order = await _orderService.CreateAsync(request);

    // Background work với error handling đầy đủ
    _ = Task.Run(async () =>
    {
        try
        {
            await _emailService.SendConfirmationAsync(order);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to send confirmation for order {OrderId}", order.Id);
            // Optionally: retry, dead letter queue, etc.
        }
    });

    return Ok(order);
}

// GOOD Option 2: BackgroundService (Best Practice cho ASP.NET)
// Đăng ký trong Program.cs: builder.Services.AddHostedService<OrderNotificationService>()
public class OrderNotificationService : BackgroundService
{
    private readonly Channel<Order> _channel;
    private readonly ILogger<OrderNotificationService> _logger;

    public OrderNotificationService(
        Channel<Order> channel,
        ILogger<OrderNotificationService> logger)
    {
        _channel = channel;
        _logger = logger;
    }

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        await foreach (var order in _channel.Reader.ReadAllAsync(stoppingToken))
        {
            try
            {
                await ProcessOrderAsync(order, stoppingToken);
            }
            catch (Exception ex) when (ex is not OperationCanceledException)
            {
                _logger.LogError(ex, "Failed to process order {OrderId}", order.Id);
            }
        }
    }

    private async Task ProcessOrderAsync(Order order, CancellationToken ct)
    {
        // Xử lý trong background một cách an toàn
        await _emailService.SendConfirmationAsync(order, ct);
    }
}

// Controller gửi vào channel thay vì fire-and-forget
[ApiController]
public class OrderController : ControllerBase
{
    private readonly ChannelWriter<Order> _channelWriter;

    [HttpPost]
    public async Task<IActionResult> CreateOrder(CreateOrderRequest request)
    {
        var order = await _orderService.CreateAsync(request);

        // An toàn: ghi vào channel, BackgroundService sẽ xử lý
        await _channelWriter.WriteAsync(order);

        return Ok(order);
    }
}
```

### 7. Phòng Ngừa

**Checklist:**
- [ ] Mọi fire-and-forget đều có try-catch với logging
- [ ] Background work trong ASP.NET: dùng `BackgroundService` hoặc `IHostedService`
- [ ] Đăng ký `TaskScheduler.UnobservedTaskException` handler
- [ ] Đảm bảo background task nhận và tôn trọng `CancellationToken`

**Roslyn Analyzer Rules:**
```xml
dotnet_diagnostic.VSTHRD110.severity = warning  <!-- Observe result of async calls -->
```

---

## Pattern 06: Async Lazy Init

### 1. Tên
**Async Lazy Initialization Sai** (Incorrect Async Lazy Initialization)

### 2. Phân Loại
- **Domain:** Async/Await & Task
- **Subcategory:** Initialization / Thread Safety

### 3. Mức Nghiêm Trọng
**MEDIUM** - Race condition, khởi tạo nhiều lần, exception không được cache

### 4. Vấn Đề

`Lazy<T>` là synchronous và không hỗ trợ async factory function đúng cách. Dùng `Lazy<Task<T>>` có vẻ đúng nhưng có nhiều vấn đề tiềm ẩn về exception handling và thread safety.

```
LAZY<TASK<T>> VẤN ĐỀ

Thread A → Lazy.Value → factory() → Task<T> được tạo
                                         │
Thread B → Lazy.Value → Task<T> (cùng instance)
                                         │
Thread A await Task → Exception xảy ra!
                                         │
Task<T> bây giờ trong trạng thái Faulted
                                         │
Thread B await cùng Task → NHẬ N Exception của Thread A!
                                         │
                              ❌ Exception bị cache mãi mãi
                              Phải restart app để recovery
```

### 5. Phát Hiện Trong Mã Nguồn

**Regex patterns cho ripgrep:**

```bash
# Tìm Lazy<Task
rg "Lazy<Task" --type cs

# Tìm Lazy được khởi tạo với async lambda
rg "new\s+Lazy<.*>\(async" --type cs

# Tìm AsyncLazy implementation tự làm
rg "class\s+AsyncLazy" --type cs
```

### 6. Giải Pháp

**Ví dụ SAI:**

```csharp
// BAD: Lazy<Task<T>> - exception bị cache mãi mãi
public class DatabaseService
{
    private static readonly Lazy<Task<SqlConnection>> _connection =
        new Lazy<Task<SqlConnection>>(async () =>
        {
            var conn = new SqlConnection(_connectionString);
            await conn.OpenAsync(); // Nếu fail, Task faulted được cache mãi mãi!
            return conn;
        });

    public async Task<SqlConnection> GetConnectionAsync()
    {
        return await _connection.Value; // Lần sau vẫn nhận exception cũ
    }
}
```

**Ví dụ ĐÚNG:**

```csharp
// GOOD Option 1: AsyncLazy<T> custom implementation an toàn
public class AsyncLazy<T>
{
    private readonly Func<Task<T>> _factory;
    private readonly SemaphoreSlim _semaphore = new SemaphoreSlim(1, 1);
    private Task<T>? _cachedTask;

    public AsyncLazy(Func<Task<T>> factory)
    {
        _factory = factory;
    }

    public async Task<T> GetValueAsync(CancellationToken ct = default)
    {
        if (_cachedTask is { IsCompletedSuccessfully: true })
            return await _cachedTask;

        await _semaphore.WaitAsync(ct).ConfigureAwait(false);
        try
        {
            // Double-check sau khi acquire semaphore
            if (_cachedTask is { IsCompletedSuccessfully: true })
                return await _cachedTask;

            // Nếu task trước đó fail, tạo task mới (không cache lỗi)
            _cachedTask = _factory();
            return await _cachedTask.ConfigureAwait(false);
        }
        catch
        {
            // Reset để lần sau thử lại
            _cachedTask = null;
            throw;
        }
        finally
        {
            _semaphore.Release();
        }
    }
}

// Usage:
public class DatabaseService
{
    private readonly AsyncLazy<SqlConnection> _connection;

    public DatabaseService(string connectionString)
    {
        _connection = new AsyncLazy<SqlConnection>(async () =>
        {
            var conn = new SqlConnection(connectionString);
            await conn.OpenAsync().ConfigureAwait(false);
            return conn;
        });
    }

    public Task<SqlConnection> GetConnectionAsync(CancellationToken ct = default)
        => _connection.GetValueAsync(ct);
}

// GOOD Option 2: Dùng IServiceProvider với Singleton scope (ASP.NET Core)
// Đơn giản nhất - framework lo thread safety
builder.Services.AddSingleton<DatabaseService>();
// DatabaseService constructor sẽ được gọi một lần duy nhất
```

### 7. Phòng Ngừa

**Checklist:**
- [ ] Không dùng `Lazy<Task<T>>` nếu có thể fail và cần retry
- [ ] Implement custom `AsyncLazy<T>` hoặc dùng thư viện có sẵn
- [ ] Cân nhắc DI container singleton thay vì tự implement lazy init
- [ ] Test với concurrent access để đảm bảo thread safety

---

## Pattern 07: CancellationToken Bỏ Qua

### 1. Tên
**Bỏ Qua CancellationToken** (Ignoring CancellationToken)

### 2. Phân Loại
- **Domain:** Async/Await & Task
- **Subcategory:** Cancellation / Resource Management

### 3. Mức Nghiêm Trọng
**HIGH** - Lãng phí tài nguyên, request treo sau client disconnect

### 4. Vấn Đề

Khi client disconnect hoặc request timeout, ASP.NET Core hủy `CancellationToken`. Nếu code không kiểm tra và truyền token này, ứng dụng tiếp tục xử lý công việc vô ích - tốn CPU, DB connections, memory trong khi kết quả sẽ không được dùng.

```
CLIENT DISCONNECT SCENARIO

Client ──── Request ─────► ASP.NET Controller
                                  │
                    [Client ngắt kết nối]
                                  │
                    CancellationToken bị cancel
                                  │
                    Nếu KHÔNG pass token:
                                  │
                    ├─ DB Query vẫn chạy...
                    ├─ HTTP call vẫn chạy...
                    ├─ CPU vẫn tính toán...
                    └─ Memory vẫn được allocate...
                                  │
                    → Kết quả không ai nhận
                    → TÀI NGUYÊN BỊ LÃNG PHÍ
```

### 5. Phát Hiện Trong Mã Nguồn

**Regex patterns cho ripgrep:**

```bash
# Tìm method nhận CancellationToken nhưng không dùng
rg "CancellationToken\s+\w+" --type cs

# Tìm async method trong controller không có CancellationToken param
rg "public\s+async\s+Task.*\((?!.*CancellationToken)" --type cs --glob "*Controller*"

# Tìm GetAsync/PostAsync/FindAsync không có CancellationToken
rg "\.(GetAsync|PostAsync|FindAsync|FirstOrDefaultAsync|ToListAsync)\(\)" --type cs
```

### 6. Giải Pháp

**Ví dụ SAI:**

```csharp
// BAD: Không nhận và không truyền CancellationToken
[ApiController]
public class ReportController : ControllerBase
{
    [HttpGet("annual")]
    public async Task<IActionResult> GetAnnualReport(int year)
    {
        // Không có CancellationToken parameter!
        var data = await _repository.GetSalesDataAsync(year);
        var report = await _reportService.GenerateAsync(data);
        return Ok(report);
    }
}

// BAD: Nhận token nhưng không truyền cho dependencies
[HttpGet("details/{id}")]
public async Task<IActionResult> GetDetails(int id, CancellationToken ct)
{
    // ct bị bỏ qua hoàn toàn!
    var item = await _repository.GetByIdAsync(id);  // Không có ct
    var details = await _service.EnrichAsync(item);  // Không có ct
    return Ok(details);
}
```

**Ví dụ ĐÚNG:**

```csharp
// GOOD: Nhận và truyền CancellationToken đầy đủ
[ApiController]
public class ReportController : ControllerBase
{
    [HttpGet("annual")]
    public async Task<IActionResult> GetAnnualReport(
        int year,
        CancellationToken cancellationToken) // ASP.NET Core tự inject từ request
    {
        var data = await _repository.GetSalesDataAsync(year, cancellationToken);
        var report = await _reportService.GenerateAsync(data, cancellationToken);
        return Ok(report);
    }
}

// GOOD: Repository với CancellationToken
public class SalesRepository
{
    private readonly AppDbContext _context;

    public async Task<List<SalesData>> GetSalesDataAsync(
        int year,
        CancellationToken ct = default)
    {
        return await _context.Sales
            .Where(s => s.Year == year)
            .ToListAsync(ct); // Truyền ct cho EF Core
    }
}

// GOOD: Xử lý cancellation gracefully
public class ReportService
{
    public async Task<Report> GenerateAsync(
        List<SalesData> data,
        CancellationToken ct = default)
    {
        var report = new Report();

        foreach (var item in data)
        {
            ct.ThrowIfCancellationRequested(); // Kiểm tra thường xuyên

            var processed = await ProcessItemAsync(item, ct);
            report.AddItem(processed);
        }

        return report;
    }
}

// GOOD: Linked CancellationToken - timeout + external cancel
public async Task<Result> ExecuteWithTimeoutAsync(
    Request request,
    CancellationToken externalCt = default)
{
    using var timeoutCts = new CancellationTokenSource(TimeSpan.FromSeconds(30));
    using var linkedCts = CancellationTokenSource.CreateLinkedTokenSource(
        externalCts, timeoutCts.Token);

    try
    {
        return await _service.ProcessAsync(request, linkedCts.Token);
    }
    catch (OperationCanceledException) when (timeoutCts.IsCancellationRequested)
    {
        throw new TimeoutException("Operation timed out after 30 seconds");
    }
}
```

### 7. Phòng Ngừa

**Checklist:**
- [ ] Mọi async method đều có `CancellationToken ct = default` parameter
- [ ] Truyền token đến mọi internal async calls
- [ ] Gọi `ct.ThrowIfCancellationRequested()` trong vòng lặp dài
- [ ] Tạo linked token khi cần kết hợp timeout và external cancellation

**Roslyn Analyzer Rules:**
```xml
dotnet_diagnostic.CA2016.severity = warning  <!-- Forward CancellationToken to async methods -->
```

---

## Pattern 08: Parallel.ForEach Async

### 1. Tên
**Parallel.ForEach Với Async Lambda** (Parallel.ForEach with Async Lambda)

### 2. Phân Loại
- **Domain:** Async/Await & Task
- **Subcategory:** Parallelism / Async Misuse

### 3. Mức Nghiêm Trọng
**HIGH** - Fire-and-forget ngầm, không chờ async work hoàn thành

### 4. Vấn Đề

`Parallel.ForEach` với async lambda KHÔNG await các async operations. Nó nhận `Func<T, void>` nhưng async lambda trả về `Task`. `Parallel.ForEach` bỏ qua Task này và tiếp tục, tạo ra fire-and-forget cho mỗi item.

```
Parallel.ForEach(items, async item =>
{
    await ProcessAsync(item);  ← Task được tạo nhưng KHÔNG được await
})

Parallel.ForEach nhìn thấy:
  Func<Item, void>  ← Task bị bỏ qua!
  Không phải Func<Item, Task>

Kết quả:
  items[0] → Task bắt đầu (fire-and-forget)
  items[1] → Task bắt đầu (fire-and-forget)
  items[2] → Task bắt đầu (fire-and-forget)
  ...
  Parallel.ForEach return ngay lập tức!
  Tất cả tasks vẫn đang chạy background...
  → Không ai biết khi nào xong
  → Exception bị nuốt
```

### 5. Phát Hiện Trong Mã Nguồn

**Regex patterns cho ripgrep:**

```bash
# Tìm Parallel.ForEach với async lambda
rg "Parallel\.ForEach\(.*async" --type cs

# Tìm Parallel.For với async lambda
rg "Parallel\.For\(.*async" --type cs

# Tìm cả hai
rg "Parallel\.(ForEach|For)\(.*,\s*async" --type cs
```

### 6. Giải Pháp

| Tình huống | Solution |
|------------|----------|
| I/O-bound parallel | `Task.WhenAll(items.Select(async i => await ProcessAsync(i)))` |
| I/O-bound với throttle | `SemaphoreSlim` + `Task.WhenAll` |
| CPU-bound parallel | `Parallel.ForEach` với SYNC lambda |
| .NET 6+: I/O parallel | `Parallel.ForEachAsync` |

**Ví dụ SAI:**

```csharp
// BAD: Parallel.ForEach với async lambda - silent fire-and-forget
public async Task ImportUsersAsync(List<UserDto> users)
{
    Parallel.ForEach(users, async user =>
    {
        // Task này bị bỏ qua! Không ai await nó.
        await _repository.SaveAsync(user);
        await _emailService.SendWelcomeAsync(user.Email);
    });

    // Method return nhưng nhiều saves chưa xong!
    _logger.LogInformation("Import complete"); // LỜI NÓI DỐI!
}
```

**Ví dụ ĐÚNG:**

```csharp
// GOOD Option 1: Task.WhenAll (tất cả parallel)
public async Task ImportUsersAsync(List<UserDto> users)
{
    var tasks = users.Select(async user =>
    {
        await _repository.SaveAsync(user);
        await _emailService.SendWelcomeAsync(user.Email);
    });

    await Task.WhenAll(tasks);
    _logger.LogInformation("Import complete - thật sự xong");
}

// GOOD Option 2: Throttled parallelism với SemaphoreSlim
public async Task ImportUsersWithThrottleAsync(
    List<UserDto> users,
    CancellationToken ct = default)
{
    using var semaphore = new SemaphoreSlim(10, 10); // Tối đa 10 concurrent

    var tasks = users.Select(async user =>
    {
        await semaphore.WaitAsync(ct).ConfigureAwait(false);
        try
        {
            await _repository.SaveAsync(user, ct).ConfigureAwait(false);
            await _emailService.SendWelcomeAsync(user.Email, ct).ConfigureAwait(false);
        }
        finally
        {
            semaphore.Release();
        }
    });

    await Task.WhenAll(tasks).ConfigureAwait(false);
}

// GOOD Option 3: Parallel.ForEachAsync (.NET 6+)
public async Task ImportUsersModernAsync(
    List<UserDto> users,
    CancellationToken ct = default)
{
    await Parallel.ForEachAsync(
        users,
        new ParallelOptions
        {
            MaxDegreeOfParallelism = 10,
            CancellationToken = ct
        },
        async (user, token) =>
        {
            await _repository.SaveAsync(user, token).ConfigureAwait(false);
            await _emailService.SendWelcomeAsync(user.Email, token).ConfigureAwait(false);
        });
}

// GOOD Option 4: CPU-bound - Parallel.ForEach ĐÚNG
public void ProcessDataCpuBound(List<DataItem> items)
{
    Parallel.ForEach(items, item =>
    {
        // SYNC operation - Parallel.ForEach hợp lý ở đây
        ProcessItemCpuIntensive(item);
    });
}
```

### 7. Phòng Ngừa

**Checklist:**
- [ ] Không bao giờ dùng `Parallel.ForEach` với `async` lambda
- [ ] I/O-bound: dùng `Task.WhenAll` hoặc `Parallel.ForEachAsync` (.NET 6+)
- [ ] CPU-bound: dùng `Parallel.ForEach` với SYNC lambda
- [ ] Luôn giới hạn concurrency cho I/O operations

**Roslyn Analyzer Rules:**
```xml
dotnet_diagnostic.VSTHRD101.severity = error  <!-- Async void event handler -->
<!-- Không có analyzer tự động cho Parallel.ForEach async - cần code review -->
```

---

## Pattern 09: SemaphoreSlim Trong Async

### 1. Tên
**SemaphoreSlim Sử Dụng Không Đúng Trong Async** (Incorrect SemaphoreSlim Usage in Async)

### 2. Phân Loại
- **Domain:** Async/Await & Task
- **Subcategory:** Synchronization / Resource Management

### 3. Mức Nghiêm Trọng
**MEDIUM** - Deadlock, resource leak khi exception xảy ra

### 4. Vấn Đề

`SemaphoreSlim` là cách đúng để giới hạn concurrency trong async code, nhưng dễ bị lỗi nếu không dùng `try-finally` hoặc quên `Release()` khi có exception.

```
SemaphoreSlim LEAK scenario:

WaitAsync() → Enter critical section
     │
     │ ❌ Exception xảy ra trước Release()
     │
     ▼
Release() KHÔNG được gọi!
     │
     ▼
SemaphoreSlim count giảm dần mỗi exception
     │
     ▼
Cuối cùng: SemaphoreSlim count = 0
     │
     ▼
☠️  TẤT CẢ THREAD BỊ BLOCK MÃI MÃI
```

### 5. Phát Hiện Trong Mã Nguồn

**Regex patterns cho ripgrep:**

```bash
# Tìm WaitAsync không trong try block
rg "\.WaitAsync\(" --type cs

# Tìm SemaphoreSlim.Wait (sync version - sai trong async)
rg "semaphore\w*\.Wait\(\)" --type cs -i

# Tìm SemaphoreSlim không có finally Release
rg "SemaphoreSlim" --type cs
```

### 6. Giải Pháp

**Ví dụ SAI:**

```csharp
// BAD: Không có try-finally, semaphore leak khi exception
public class RateLimiter
{
    private readonly SemaphoreSlim _semaphore = new SemaphoreSlim(5, 5);

    public async Task<T> ExecuteAsync<T>(Func<Task<T>> operation)
    {
        await _semaphore.WaitAsync(); // Acquire

        var result = await operation(); // Nếu throw → Release không được gọi!

        _semaphore.Release(); // KHÔNG AN TOÀN - có thể không chạy
        return result;
    }
}

// BAD: Dùng sync Wait() trong async method
public async Task ProcessAsync()
{
    _semaphore.Wait(); // Block thread! Không phải async!
    try
    {
        await DoWorkAsync();
    }
    finally
    {
        _semaphore.Release();
    }
}
```

**Ví dụ ĐÚNG:**

```csharp
// GOOD: Luôn dùng try-finally với SemaphoreSlim
public class RateLimiter
{
    private readonly SemaphoreSlim _semaphore;

    public RateLimiter(int maxConcurrency)
    {
        _semaphore = new SemaphoreSlim(maxConcurrency, maxConcurrency);
    }

    public async Task<T> ExecuteAsync<T>(
        Func<Task<T>> operation,
        CancellationToken ct = default)
    {
        await _semaphore.WaitAsync(ct).ConfigureAwait(false);
        try
        {
            return await operation().ConfigureAwait(false);
        }
        finally
        {
            _semaphore.Release(); // LUÔN được gọi, kể cả khi exception
        }
    }
}

// GOOD: Wrapper tiện lợi dùng IDisposable pattern
public static class SemaphoreSlimExtensions
{
    public static async Task<IDisposable> AcquireAsync(
        this SemaphoreSlim semaphore,
        CancellationToken ct = default)
    {
        await semaphore.WaitAsync(ct).ConfigureAwait(false);
        return new SemaphoreReleaser(semaphore);
    }

    private sealed class SemaphoreReleaser : IDisposable
    {
        private readonly SemaphoreSlim _semaphore;
        private bool _disposed;

        public SemaphoreReleaser(SemaphoreSlim semaphore)
            => _semaphore = semaphore;

        public void Dispose()
        {
            if (!_disposed)
            {
                _semaphore.Release();
                _disposed = true;
            }
        }
    }
}

// Usage với extension method:
public async Task ProcessAsync(CancellationToken ct = default)
{
    using (await _semaphore.AcquireAsync(ct))
    {
        await DoWorkAsync(ct);
    } // Tự động Release khi dispose
}
```

### 7. Phòng Ngừa

**Checklist:**
- [ ] Luôn dùng `try-finally` sau `WaitAsync()`
- [ ] Không dùng `Wait()` (sync) trong async context - dùng `WaitAsync()`
- [ ] Cân nhắc tạo wrapper `IDisposable` để tự động release
- [ ] Test với exception scenarios để verify release luôn được gọi

---

## Pattern 10: ValueTask Misuse

### 1. Tên
**Lạm Dụng ValueTask** (ValueTask Misuse)

### 2. Phân Loại
- **Domain:** Async/Await & Task
- **Subcategory:** Performance / Memory Management

### 3. Mức Nghiêm Trọng
**HIGH** - Memory corruption, undefined behavior khi await nhiều lần

### 4. Vấn Đề

`ValueTask<T>` được tối ưu cho hot path khi kết quả thường available synchronously (tránh heap allocation của `Task<T>`). Nhưng `ValueTask<T>` có quy tắc sử dụng khắt khe hơn `Task<T>` - vi phạm dẫn đến undefined behavior.

**Các quy tắc của ValueTask:**
1. Chỉ được `await` MỘT LẦN
2. Không thể `await` sau khi nó đã hoàn thành
3. Không thể `await` trên nhiều threads cùng lúc
4. Nếu cần dùng nhiều lần, phải `.AsTask()` trước

```
ValueTask ĐƯỢC PHÉP            ValueTask KHÔNG ĐƯỢC PHÉP
========================       =============================
var vt = GetValueAsync();      var vt = GetValueAsync();
var result = await vt;         var result1 = await vt;  ← OK
                               var result2 = await vt;  ← UNDEFINED!

var vt = GetValueAsync();      var vt = GetValueAsync();
var task = vt.AsTask();        task1.Start(() => vt.Result);
var r1 = await task;           task2.Start(() => vt.Result);
var r2 = await task; ← OK!     ← RACE CONDITION, UNDEFINED!
```

### 5. Phát Hiện Trong Mã Nguồn

**Regex patterns cho ripgrep:**

```bash
# Tìm ValueTask<T> declarations
rg "ValueTask<" --type cs

# Tìm ValueTask (non-generic)
rg "\bValueTask\b" --type cs

# Tìm nơi ValueTask có thể bị await nhiều lần
rg "var\s+\w+\s*=\s*.*Async\(\)" --type cs
```

### 6. Giải Pháp

| Dùng | Khi |
|------|-----|
| `Task<T>` | Mặc định, dùng khi không chắc |
| `ValueTask<T>` | Hot path, kết quả thường synchronous, performance-critical |
| `ValueTask<T>.AsTask()` | Khi cần await nhiều lần hoặc store |

**Ví dụ SAI:**

```csharp
// BAD: Await ValueTask nhiều lần
public async Task ProcessAsync()
{
    var valueTask = _cache.GetValueAsync("key");

    var value1 = await valueTask; // OK - lần đầu
    var value2 = await valueTask; // UNDEFINED BEHAVIOR - lần thứ hai!

    // Cả hai có thể khác nhau hoặc crash
}

// BAD: Lưu ValueTask vào biến field và dùng sau
public class Service
{
    private ValueTask<string> _cachedTask; // WRONG - ValueTask không nên là field!

    public void StartWork()
    {
        _cachedTask = DoWorkAsync();
    }

    public async Task<string> GetResultAsync()
    {
        return await _cachedTask; // Có thể đã completed, có thể không - UNDEFINED!
    }
}
```

**Ví dụ ĐÚNG:**

```csharp
// GOOD: ValueTask dùng đúng cách - await ngay
public async Task ProcessAsync()
{
    // Await ngay lập tức, không lưu vào biến trung gian
    var value = await _cache.GetValueAsync("key");
    Process(value);
}

// GOOD: Nếu cần dùng nhiều lần, dùng AsTask()
public async Task MultipleAwaitAsync()
{
    var task = _cache.GetValueAsync("key").AsTask(); // Chuyển sang Task

    var value1 = await task; // OK
    var value2 = await task; // OK - Task có thể await nhiều lần
}

// GOOD: Implement ValueTask đúng cách trong hot path
public class Cache
{
    private readonly ConcurrentDictionary<string, string> _cache = new();

    public ValueTask<string> GetValueAsync(string key)
    {
        // Hot path: synchronous return nếu cache hit (không allocate Task)
        if (_cache.TryGetValue(key, out var cached))
            return new ValueTask<string>(cached); // Synchronous, no allocation!

        // Cold path: cần async work
        return new ValueTask<string>(LoadFromDatabaseAsync(key));
    }

    private async Task<string> LoadFromDatabaseAsync(string key)
    {
        var value = await _db.GetAsync(key).ConfigureAwait(false);
        _cache[key] = value;
        return value;
    }
}
```

### 7. Phòng Ngừa

**Checklist:**
- [ ] Không lưu `ValueTask` vào field hoặc property
- [ ] Chỉ `await` `ValueTask` một lần
- [ ] Dùng `.AsTask()` trước khi cần await nhiều lần
- [ ] Mặc định dùng `Task<T>`, chỉ chuyển sang `ValueTask<T>` khi có đo lường hiệu năng

---

## Pattern 11: Thread Pool Starvation

### 1. Tên
**Thread Pool Starvation** (Thread Pool Exhaustion)

### 2. Phân Loại
- **Domain:** Async/Await & Task
- **Subcategory:** Thread Pool / Scalability

### 3. Mức Nghiêm Trọng
**CRITICAL** - Ứng dụng đóng băng hoàn toàn, không phản hồi request

### 4. Vấn Đề

Thread pool starvation xảy ra khi tất cả thread pool threads bị block (sync waiting), không có thread nào sẵn sàng xử lý công việc mới. Ứng dụng trở nên không phản hồi mặc dù CPU thấp.

```
THREAD POOL STARVATION

Ban đầu: Thread Pool = 8 threads
                        │
Request 1 → Thread #1 → .Result → BLOCKED
Request 2 → Thread #2 → .Result → BLOCKED
Request 3 → Thread #3 → .Result → BLOCKED
...
Request 8 → Thread #8 → .Result → BLOCKED
                        │
Request 9 → ??? → Không có thread available!
                   Queue đầy...
                        │
Thread pool tạo thread mới (chậm, 1 thread/giây)
                        │
Nhưng request đến nhanh hơn thread được tạo
                        │
☠️  APP ĐÔNG CỨNG - Mọi request timeout
```

**Tại sao CPU thấp nhưng app không phản hồi:**
- Threads đang BỊ BLOCK, không phải đang CHẠY
- CPU idle nhưng threads đang chờ lock/I/O sync
- Thread pool cạn kiệt → không xử lý được request mới

### 5. Phát Hiện Trong Mã Nguồn

**Dấu hiệu nhận biết:**
- App không phản hồi, request timeout hàng loạt
- CPU 0-5% nhưng app "chết"
- Thread count tăng dần, chậm chạp
- Event Log: ThreadPool warnings

**Regex patterns cho ripgrep:**

```bash
# Tìm tất cả blocking patterns
rg "\.(Wait\(\)|Result)\b" --type cs

# Tìm Thread.Sleep trong async context
rg "Thread\.Sleep\(" --type cs

# Tìm Monitor.Enter/lock trong async
rg "(Monitor\.Enter|lock\s*\()" --type cs

# Tìm blocking calls trong controllers/services
rg "\.(Wait|Result)\b" --type cs --glob "*Controller*"
rg "\.(Wait|Result)\b" --type cs --glob "*Service*"
```

**Monitoring code để phát hiện starvation:**

```csharp
// Thêm vào health check hoặc metrics
ThreadPool.GetAvailableThreads(out int workerThreads, out int completionPortThreads);
ThreadPool.GetMaxThreads(out int maxWorker, out int maxCompletion);

var utilizationPercent = (maxWorker - workerThreads) * 100.0 / maxWorker;
// Nếu > 90%: nguy hiểm, có thể starvation
```

### 6. Giải Pháp

**Ví dụ SAI:**

```csharp
// BAD: Blocking calls gây thread pool starvation
public class OrderService
{
    public Order ProcessOrder(int orderId)
    {
        // .Result block thread - N concurrent requests = N threads bị block!
        var order = _repository.GetOrderAsync(orderId).Result;
        var inventory = _inventoryService.CheckAsync(order).Result;
        var payment = _paymentService.ChargeAsync(order).Result;

        return FinalizeOrder(order, inventory, payment);
    }
}

// BAD: Thread.Sleep trong async (phải dùng Task.Delay)
public async Task RetryAsync()
{
    for (int i = 0; i < 3; i++)
    {
        try { await DoWorkAsync(); return; }
        catch { Thread.Sleep(1000); } // Block thread! Dùng Task.Delay thay thế
    }
}
```

**Ví dụ ĐÚNG:**

```csharp
// GOOD: Async all the way - không block threads
public class OrderService
{
    public async Task<Order> ProcessOrderAsync(
        int orderId,
        CancellationToken ct = default)
    {
        // Tất cả async - threads không bị block
        var order = await _repository.GetOrderAsync(orderId, ct);

        // Parallel nếu independent
        var (inventory, customer) = await (
            _inventoryService.CheckAsync(order, ct),
            _customerService.GetAsync(order.CustomerId, ct)
        ).WhenBoth();

        var payment = await _paymentService.ChargeAsync(order, inventory, ct);
        return await FinalizeOrderAsync(order, payment, ct);
    }
}

// GOOD: Task.Delay thay vì Thread.Sleep
public async Task RetryAsync(CancellationToken ct = default)
{
    for (int i = 0; i < 3; i++)
    {
        try
        {
            await DoWorkAsync(ct);
            return;
        }
        catch (Exception ex) when (i < 2)
        {
            _logger.LogWarning(ex, "Attempt {Attempt} failed, retrying...", i + 1);
            await Task.Delay(TimeSpan.FromSeconds(Math.Pow(2, i)), ct); // Không block thread!
        }
    }
}

// GOOD: Cấu hình thread pool minimum (startup)
// Tránh "cold start" chậm
ThreadPool.SetMinThreads(workerThreads: 100, completionPortThreads: 100);
```

### 7. Phòng Ngừa

**Checklist:**
- [ ] Không có `.Result`, `.Wait()` trong production code
- [ ] Dùng `Task.Delay` thay vì `Thread.Sleep`
- [ ] Không dùng `lock` trong async context - dùng `SemaphoreSlim`
- [ ] Configure `ThreadPool.SetMinThreads` cho high-load applications
- [ ] Monitor thread pool usage qua metrics

**Roslyn Analyzer Rules:**
```xml
dotnet_diagnostic.VSTHRD002.severity = error  <!-- Avoid problematic synchronous waits -->
dotnet_diagnostic.VSTHRD011.severity = error  <!-- Use AsyncLazy<T> -->
```

---

## Pattern 12: Async Disposal Thiếu

### 1. Tên
**Thiếu Async Disposal** (Missing IAsyncDisposable Implementation)

### 2. Phân Loại
- **Domain:** Async/Await & Task
- **Subcategory:** Resource Management / IDisposable

### 3. Mức Nghiêm Trọng
**HIGH** - Resource leak, blocking trong disposal, connection pool exhaustion

### 4. Vấn Đề

Khi dispose resource có async operations (đóng kết nối DB, flush buffer bất đồng bộ), nếu dùng `IDisposable` thay vì `IAsyncDisposable`, phải block để chờ async operation hoàn thành - gây deadlock hoặc resource leak.

```
SYNC DISPOSE VẤN ĐỀ

using (var resource = new AsyncResource())
{
    await resource.UseAsync();
}  ← Gọi Dispose() sync

Dispose() {
    FlushAsync().Wait(); ← DEADLOCK tiềm ẩn!
    // Hoặc
    // Không flush gì cả → DATA LOSS
}
```

### 5. Phát Hiện Trong Mã Nguồn

**Regex patterns cho ripgrep:**

```bash
# Tìm class implement IDisposable nhưng có async operations
rg "class\s+\w+.*IDisposable" --type cs

# Tìm Dispose method với .Wait() hoặc .Result
rg "void\s+Dispose\(\)" --type cs -A 10

# Tìm using statement với async resources
rg "using\s+var\s+\w+\s*=" --type cs
```

### 6. Giải Pháp

**Ví dụ SAI:**

```csharp
// BAD: IDisposable với async flush - blocking hoặc data loss
public class BufferedWriter : IDisposable
{
    private readonly List<string> _buffer = new();
    private readonly FileStream _stream;
    private bool _disposed;

    public void Write(string data) => _buffer.Add(data);

    public void Dispose()
    {
        if (_disposed) return;

        // WRONG Option A: Block để flush - deadlock tiềm ẩn
        FlushAsync().Wait();

        // WRONG Option B: Không flush - DATA LOSS!
        // _stream.Dispose();

        _disposed = true;
    }

    private async Task FlushAsync()
    {
        foreach (var item in _buffer)
            await _stream.WriteAsync(Encoding.UTF8.GetBytes(item));
    }
}
```

**Ví dụ ĐÚNG:**

```csharp
// GOOD: IAsyncDisposable cho resources có async operations
public class BufferedWriter : IAsyncDisposable, IDisposable
{
    private readonly List<string> _buffer = new();
    private readonly FileStream _stream;
    private bool _disposed;

    public void Write(string data)
    {
        ObjectDisposedException.ThrowIf(_disposed, this);
        _buffer.Add(data);
    }

    // Async disposal - flush data properly
    public async ValueTask DisposeAsync()
    {
        if (_disposed) return;
        _disposed = true;

        try
        {
            await FlushAsync().ConfigureAwait(false);
        }
        finally
        {
            await _stream.DisposeAsync().ConfigureAwait(false);
        }
    }

    // Sync disposal fallback - chỉ cho compatibility
    public void Dispose()
    {
        if (_disposed) return;
        _disposed = true;

        // Flush synchronously trong emergency - có thể incomplete
        try
        {
            foreach (var item in _buffer)
                _stream.Write(Encoding.UTF8.GetBytes(item));
        }
        finally
        {
            _stream.Dispose();
        }
    }

    private async Task FlushAsync()
    {
        foreach (var item in _buffer)
            await _stream.WriteAsync(Encoding.UTF8.GetBytes(item)).ConfigureAwait(false);
        await _stream.FlushAsync().ConfigureAwait(false);
    }
}

// GOOD: Dùng await using cho IAsyncDisposable
public async Task ProcessAsync()
{
    await using var writer = new BufferedWriter("output.txt");

    writer.Write("line 1");
    writer.Write("line 2");

    // DisposeAsync() được gọi tự động khi ra khỏi scope
}

// GOOD: DbContext trong EF Core - đã implement IAsyncDisposable
public async Task WithDbContextAsync()
{
    await using var context = new AppDbContext();
    var users = await context.Users.ToListAsync();
    // DisposeAsync() tự động
}
```

### 7. Phòng Ngừa

**Checklist:**
- [ ] Resources có async operations: implement `IAsyncDisposable`
- [ ] Dùng `await using` thay vì `using` khi possible
- [ ] Implement cả `IDisposable` làm fallback (ít nhất là synchronous fallback)
- [ ] Test disposal với exception scenarios

**Roslyn Analyzer Rules:**
```xml
dotnet_diagnostic.CA1816.severity = warning  <!-- Call GC.SuppressFinalize correctly -->
dotnet_diagnostic.CA2213.severity = warning  <!-- Disposable fields should be disposed -->
```

---

## Pattern 13: Task.WhenAll Exception Loss

### 1. Tên
**Mất Exception Trong Task.WhenAll** (Exception Loss in Task.WhenAll)

### 2. Phân Loại
- **Domain:** Async/Await & Task
- **Subcategory:** Exception Handling / Task Coordination

### 3. Mức Nghiêm Trọng
**MEDIUM** - Mất thông tin lỗi, khó debug production issues

### 4. Vấn Đề

Khi nhiều tasks trong `Task.WhenAll` fail, chỉ exception đầu tiên được propagate khi await. Các exception từ task khác bị mất trong `AggregateException`.

```
Task.WhenAll([Task1, Task2, Task3])

Task1 → FAIL: IOException "File not found"
Task2 → FAIL: HttpException "Service unavailable"
Task3 → SUCCESS

await Task.WhenAll(...) throws:
  IOException "File not found"  ← CHỈ EXCEPTION ĐẦU TIÊN!

HttpException BỊMẤT! → Khó debug, root cause ẩn
```

### 5. Phát Hiện Trong Mã Nguồn

**Regex patterns cho ripgrep:**

```bash
# Tìm Task.WhenAll
rg "Task\.WhenAll\(" --type cs

# Tìm await Task.WhenAll không check AggregateException
rg "await\s+Task\.WhenAll" --type cs
```

### 6. Giải Pháp

**Ví dụ SAI:**

```csharp
// BAD: Chỉ bắt exception đầu tiên
public async Task ProcessAllAsync(List<int> ids)
{
    var tasks = ids.Select(id => ProcessAsync(id));

    try
    {
        await Task.WhenAll(tasks); // Chỉ throw exception đầu tiên!
    }
    catch (Exception ex)
    {
        // Chỉ log 1 exception, bỏ sót các exception khác
        _logger.LogError(ex, "Processing failed");
    }
}
```

**Ví dụ ĐÚNG:**

```csharp
// GOOD: Bắt tất cả exceptions
public async Task ProcessAllAsync(List<int> ids, CancellationToken ct = default)
{
    var tasks = ids.Select(id => ProcessAsync(id, ct)).ToArray();

    var whenAllTask = Task.WhenAll(tasks);

    try
    {
        await whenAllTask;
    }
    catch
    {
        // whenAllTask.Exception chứa TẤT CẢ exceptions
        if (whenAllTask.Exception != null)
        {
            var allExceptions = whenAllTask.Exception.InnerExceptions;

            foreach (var ex in allExceptions)
            {
                _logger.LogError(ex, "Task failed");
            }

            // Re-throw tất cả nếu cần
            throw new AggregateException(
                $"{allExceptions.Count} tasks failed",
                allExceptions);
        }
    }
}

// GOOD: Collect results và errors riêng biệt
public async Task<(List<T> Results, List<Exception> Errors)> WhenAllSettledAsync<T>(
    IEnumerable<Task<T>> tasks)
{
    var taskArray = tasks.ToArray();

    // Chờ tất cả complete, kể cả failed ones
    await Task.WhenAll(taskArray.Select(t => t.ContinueWith(_ => { })));

    var results = taskArray
        .Where(t => t.IsCompletedSuccessfully)
        .Select(t => t.Result)
        .ToList();

    var errors = taskArray
        .Where(t => t.IsFaulted)
        .Select(t => t.Exception?.InnerException ?? t.Exception!)
        .ToList();

    return (results, errors);
}

// GOOD: .NET 6+ Task.WhenEach hoặc custom gather
public async Task GatherResultsAsync(List<int> ids, CancellationToken ct = default)
{
    var results = new ConcurrentBag<(int Id, string Result, Exception? Error)>();

    var tasks = ids.Select(async id =>
    {
        try
        {
            var result = await ProcessAsync(id, ct).ConfigureAwait(false);
            results.Add((id, result, null));
        }
        catch (Exception ex)
        {
            results.Add((id, string.Empty, ex));
            _logger.LogError(ex, "Failed to process id {Id}", id);
        }
    });

    await Task.WhenAll(tasks);

    var failed = results.Where(r => r.Error != null).ToList();
    if (failed.Any())
    {
        _logger.LogWarning("{FailedCount}/{Total} items failed", failed.Count, ids.Count);
    }
}
```

### 7. Phòng Ngừa

**Checklist:**
- [ ] Sau `await Task.WhenAll`, kiểm tra `.Exception.InnerExceptions` để lấy tất cả lỗi
- [ ] Cân nhắc pattern "gather all" thay vì throw at first failure
- [ ] Log tất cả exceptions, không chỉ exception đầu tiên
- [ ] Test với multiple concurrent failures

---

## Pattern 14: Channel Bounded Full

### 1. Tên
**Channel Đầy Gây Blocking** (Bounded Channel Full Blocking)

### 2. Phân Loại
- **Domain:** Async/Await & Task
- **Subcategory:** Channel / Producer-Consumer

### 3. Mức Nghiêm Trọng
**MEDIUM** - Blocking producer, timeout, backpressure không kiểm soát

### 4. Vấn Đề

`Channel<T>` với `BoundedChannelOptions` có thể block producer khi channel đầy. Nếu producer không handle case này (async wait hoặc drop), dẫn đến blocking hoặc silent drop.

```
BOUNDED CHANNEL FULL SCENARIO

Producer → WriteAsync() ─────► Channel [■■■■■] FULL!
                                        │
                        BoundedChannelFullMode.Wait:
                                WriteAsync() chờ... chờ... timeout?
                        BoundedChannelFullMode.DropWrite:
                                Item bị drop SILENT!
                        BoundedChannelFullMode.DropOldest:
                                Item cũ nhất bị drop SILENT!
```

### 5. Phát Hiện Trong Mã Nguồn

**Regex patterns cho ripgrep:**

```bash
# Tìm Channel creation
rg "Channel\.(CreateBounded|CreateUnbounded)" --type cs

# Tìm TryWrite (có thể bị drop silently)
rg "\.TryWrite\(" --type cs

# Tìm WriteAsync không có timeout/cancellation
rg "\.WriteAsync\(" --type cs
```

### 6. Giải Pháp

**Ví dụ SAI:**

```csharp
// BAD: TryWrite không check return value - silent drop
public class EventPublisher
{
    private readonly Channel<Event> _channel;

    public void Publish(Event evt)
    {
        _channel.Writer.TryWrite(evt); // Nếu false - event BỊ MẤT SILENT!
    }
}

// BAD: WriteAsync không có timeout - có thể block mãi mãi
public async Task PublishAsync(Event evt, CancellationToken ct)
{
    await _channel.Writer.WriteAsync(evt); // Không truyền ct - không thể cancel!
}
```

**Ví dụ ĐÚNG:**

```csharp
// GOOD: Bounded channel với proper backpressure handling
public class EventPublisher
{
    private readonly Channel<Event> _channel;
    private readonly ILogger<EventPublisher> _logger;

    public EventPublisher(ILogger<EventPublisher> logger)
    {
        _logger = logger;
        _channel = Channel.CreateBounded<Event>(new BoundedChannelOptions(capacity: 1000)
        {
            FullMode = BoundedChannelFullMode.Wait, // Async backpressure
            SingleReader = false,
            SingleWriter = false
        });
    }

    // GOOD: Async publish với timeout
    public async Task<bool> PublishAsync(
        Event evt,
        TimeSpan? timeout = null,
        CancellationToken ct = default)
    {
        using var timeoutCts = timeout.HasValue
            ? new CancellationTokenSource(timeout.Value)
            : null;

        using var linkedCts = timeoutCts != null
            ? CancellationTokenSource.CreateLinkedTokenSource(ct, timeoutCts.Token)
            : null;

        var effectiveCt = linkedCts?.Token ?? ct;

        try
        {
            await _channel.Writer.WriteAsync(evt, effectiveCt).ConfigureAwait(false);
            return true;
        }
        catch (OperationCanceledException) when (timeoutCts?.IsCancellationRequested == true)
        {
            _logger.LogWarning("Channel full, event dropped after timeout: {EventType}", evt.Type);
            return false;
        }
    }

    // GOOD: TryWrite với explicit drop handling
    public bool TryPublish(Event evt)
    {
        if (_channel.Writer.TryWrite(evt))
            return true;

        // Explicit logging khi drop
        _logger.LogWarning("Channel full, dropping event: {EventType}", evt.Type);
        // Optionally: metrics, dead letter, etc.
        return false;
    }
}

// GOOD: Monitor channel health
public class ChannelMonitor<T>
{
    private readonly Channel<T> _channel;
    private readonly int _capacity;

    public ChannelMonitor(int capacity)
    {
        _capacity = capacity;
        _channel = Channel.CreateBounded<T>(capacity);
    }

    public double GetUtilization()
    {
        // Channel không expose Count trực tiếp trong bounded mode
        // Dùng Reader.CanRead và Writer.TryWrite để estimate
        return _channel.Reader.Count / (double)_capacity;
    }
}
```

### 7. Phòng Ngừa

**Checklist:**
- [ ] Luôn check return value của `TryWrite()`
- [ ] Truyền `CancellationToken` cho `WriteAsync()`
- [ ] Quyết định explicit về `BoundedChannelFullMode`
- [ ] Monitor channel queue length trong production
- [ ] Có alerting khi channel utilization > 80%

---

## Pattern 15: Timer Trong Async

### 1. Tên
**Timer Trong Async Context Sai** (Incorrect Timer Usage in Async)

### 2. Phân Loại
- **Domain:** Async/Await & Task
- **Subcategory:** Timer / Background Tasks

### 3. Mức Nghiêm Trọng
**MEDIUM** - Concurrent execution, exception bị mất, memory leak

### 4. Vấn Đề

`System.Threading.Timer` và `System.Timers.Timer` callback là synchronous. Dùng `async void` trong callback hoặc không handle concurrent execution dẫn đến nhiều vấn đề.

```
TIMER CONCURRENT EXECUTION

Timer fires every 1 second:
t=0  Callback bắt đầu, async work kéo dài 3 giây
t=1  Timer fires lại! Callback thứ 2 bắt đầu
t=2  Timer fires lại! Callback thứ 3 bắt đầu
t=3  Callback 1 xong, callback 2 và 3 vẫn chạy!

→ Concurrent execution không mong muốn
→ DB connections, shared state bị race condition
→ Exception trong callback bị mất (async void issue)
```

### 5. Phát Hiện Trong Mã Nguồn

**Regex patterns cho ripgrep:**

```bash
# Tìm Timer với async callback
rg "new\s+(System\.Threading\.)?Timer\(" --type cs

# Tìm Elapsed event handler async
rg "Elapsed\s*\+=.*async" --type cs

# Tìm PeriodicTimer (NET 6+ - đúng cách)
rg "PeriodicTimer" --type cs
```

### 6. Giải Pháp

**Ví dụ SAI:**

```csharp
// BAD: async void timer callback - exception bị mất + concurrent
public class DataSyncService
{
    private readonly Timer _timer;

    public DataSyncService()
    {
        // Callback là async void - DANGEROUS!
        _timer = new Timer(async _ =>
        {
            // Nếu sync còn chạy và timer fires lại → CONCURRENT
            await SyncDataAsync(); // Exception bị mất!
        }, null, TimeSpan.Zero, TimeSpan.FromSeconds(30));
    }
}

// BAD: System.Timers.Timer với async void Elapsed
public class ReportTimer
{
    private readonly System.Timers.Timer _timer = new(30_000);

    public void Start()
    {
        _timer.Elapsed += async (s, e) =>
        {
            await GenerateReportAsync(); // async void equivalent - dangerous!
        };
        _timer.Start();
    }
}
```

**Ví dụ ĐÚNG:**

```csharp
// GOOD: PeriodicTimer (.NET 6+) - Best Practice
public class DataSyncService : BackgroundService
{
    private readonly ILogger<DataSyncService> _logger;

    public DataSyncService(ILogger<DataSyncService> logger)
    {
        _logger = logger;
    }

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        // PeriodicTimer: không có concurrent execution, không có async void
        using var timer = new PeriodicTimer(TimeSpan.FromSeconds(30));

        while (await timer.WaitForNextTickAsync(stoppingToken))
        {
            try
            {
                await SyncDataAsync(stoppingToken).ConfigureAwait(false);
            }
            catch (Exception ex) when (ex is not OperationCanceledException)
            {
                _logger.LogError(ex, "Sync failed, will retry next tick");
                // PeriodicTimer tự động chờ đến tick tiếp theo
            }
        }
    }

    private async Task SyncDataAsync(CancellationToken ct)
    {
        // Implementation
    }
}

// GOOD: Threading.Timer với non-concurrent pattern
public class LegacyTimerService : IDisposable
{
    private readonly Timer _timer;
    private readonly SemaphoreSlim _executionLock = new SemaphoreSlim(1, 1);
    private readonly ILogger<LegacyTimerService> _logger;

    public LegacyTimerService(ILogger<LegacyTimerService> logger)
    {
        _logger = logger;
        _timer = new Timer(OnTimerElapsed, null, Timeout.Infinite, Timeout.Infinite);
    }

    public void Start()
    {
        _timer.Change(TimeSpan.Zero, TimeSpan.FromSeconds(30));
    }

    private void OnTimerElapsed(object? state)
    {
        // Sync wrapper để avoid async void
        // Non-reentrant: skip nếu previous execution còn chạy
        if (!_executionLock.Wait(0)) // Try acquire non-blocking
        {
            _logger.LogWarning("Timer skipped - previous execution still running");
            return;
        }

        Task.Run(async () =>
        {
            try
            {
                await SyncDataAsync(CancellationToken.None).ConfigureAwait(false);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Timer callback failed");
            }
            finally
            {
                _executionLock.Release();
            }
        });
    }

    public void Dispose()
    {
        _timer.Dispose();
        _executionLock.Dispose();
    }
}
```

### 7. Phòng Ngừa

**Checklist:**
- [ ] Dùng `PeriodicTimer` (.NET 6+) thay vì `System.Threading.Timer` cho periodic work
- [ ] Tránh `async void` trong timer callbacks
- [ ] Handle concurrent execution - dùng semaphore hoặc lock
- [ ] Đăng ký timer service như `BackgroundService` trong ASP.NET Core
- [ ] Luôn có `CancellationToken` để dừng timer gracefully

---

## Pattern 16: IAsyncEnumerable Thiếu

### 1. Tên
**Thiếu IAsyncEnumerable Cho Streaming Data** (Missing IAsyncEnumerable for Streaming)

### 2. Phân Loại
- **Domain:** Async/Await & Task
- **Subcategory:** Streaming / Memory Efficiency

### 3. Mức Nghiêm Trọng
**MEDIUM** - Memory exhaustion khi load lớn, poor performance, poor UX

### 4. Vấn Đề

Trả về `List<T>` hoặc `IEnumerable<T>` từ async method buộc load tất cả data vào memory trước khi bắt đầu xử lý. Với dataset lớn, điều này gây `OutOfMemoryException` và latency cao (chờ load hết trước khi response đầu tiên).

```
LIST<T> APPROACH (SAI cho large data)

DB ────► Load ALL 1M records ────► Memory (RAM đầy?)
                                         │
                                   Serialize ALL
                                         │
                                   Send to client
                                         │
Client nhận TOÀN BỘ sau 30 giây
(hoặc OutOfMemoryException)

IASYNCENUMERABLE<T> APPROACH (ĐÚNG)

DB ────► Load batch 1 ────► Client nhận batch 1 (ngay!)
     ────► Load batch 2 ────► Client nhận batch 2
     ────► Load batch 3 ────► Client nhận batch 3
     ...
Memory nhỏ, latency thấp, streaming!
```

### 5. Phát Hiện Trong Mã Nguồn

**Regex patterns cho ripgrep:**

```bash
# Tìm method trả về List<T> từ DB query lớn
rg "Task<List<" --type cs

# Tìm ToListAsync() - có thể là điểm để convert sang streaming
rg "\.ToListAsync\(\)" --type cs

# Tìm IAsyncEnumerable usage (đúng)
rg "IAsyncEnumerable" --type cs

# Tìm AsAsyncEnumerable
rg "\.AsAsyncEnumerable\(\)" --type cs
```

### 6. Giải Pháp

| Tình huống | Dùng | Không dùng |
|------------|------|-----------|
| Query nhỏ (<1000 rows) | `ToListAsync()` | `IAsyncEnumerable` (overhead) |
| Query lớn, streaming | `IAsyncEnumerable<T>` | `ToListAsync()` |
| Paging | `Skip/Take` + `ToListAsync()` | Load all rồi skip |
| Export CSV/Excel | `IAsyncEnumerable<T>` | `List<T>` |
| Real-time events | `IAsyncEnumerable<T>` | Polling |

**Ví dụ SAI:**

```csharp
// BAD: Load tất cả data vào memory
[ApiController]
public class ExportController : ControllerBase
{
    [HttpGet("export/users")]
    public async Task<IActionResult> ExportUsers()
    {
        // Load tất cả 1M users vào RAM!
        var users = await _context.Users.ToListAsync();

        var csv = ConvertToCsv(users); // 1M records trong memory
        return File(Encoding.UTF8.GetBytes(csv), "text/csv", "users.csv");
    }
}

// BAD: Repository trả về List cho large dataset
public class UserRepository
{
    public async Task<List<User>> GetAllActiveUsersAsync()
    {
        // Có thể hàng triệu records!
        return await _context.Users
            .Where(u => u.IsActive)
            .ToListAsync();
    }
}
```

**Ví dụ ĐÚNG:**

```csharp
// GOOD: IAsyncEnumerable cho streaming
[ApiController]
public class ExportController : ControllerBase
{
    [HttpGet("export/users")]
    public async Task ExportUsers(CancellationToken ct)
    {
        Response.ContentType = "text/csv";
        Response.Headers.Append("Content-Disposition", "attachment; filename=users.csv");

        await using var writer = new StreamWriter(Response.Body);
        await writer.WriteLineAsync("Id,Name,Email,CreatedAt");

        // Stream data trực tiếp, không load tất cả vào RAM
        await foreach (var user in _repository.StreamActiveUsersAsync(ct))
        {
            ct.ThrowIfCancellationRequested();
            await writer.WriteLineAsync($"{user.Id},{user.Name},{user.Email},{user.CreatedAt:O}");
        }
    }
}

// GOOD: Repository với IAsyncEnumerable
public class UserRepository
{
    private readonly AppDbContext _context;

    public IAsyncEnumerable<User> StreamActiveUsersAsync(
        CancellationToken ct = default)
    {
        return _context.Users
            .Where(u => u.IsActive)
            .OrderBy(u => u.Id)
            .AsAsyncEnumerable() // EF Core streaming
            .WithCancellation(ct);
    }

    // GOOD: Yield return pattern cho custom async enumerable
    public async IAsyncEnumerable<ProcessedUser> StreamProcessedUsersAsync(
        [EnumeratorCancellation] CancellationToken ct = default)
    {
        await foreach (var user in StreamActiveUsersAsync(ct))
        {
            var processed = await ProcessUserAsync(user, ct).ConfigureAwait(false);
            yield return processed;
        }
    }
}

// GOOD: Consume với await foreach
public async Task ProcessAllUsersAsync(CancellationToken ct = default)
{
    var count = 0;

    await foreach (var user in _repository.StreamActiveUsersAsync(ct)
        .ConfigureAwait(false))
    {
        await ProcessUserAsync(user, ct).ConfigureAwait(false);
        count++;

        if (count % 1000 == 0)
            _logger.LogInformation("Processed {Count} users", count);
    }

    _logger.LogInformation("Total processed: {Count}", count);
}

// GOOD: Batching với IAsyncEnumerable
public static async IAsyncEnumerable<List<T>> BatchAsync<T>(
    this IAsyncEnumerable<T> source,
    int batchSize,
    [EnumeratorCancellation] CancellationToken ct = default)
{
    var batch = new List<T>(batchSize);

    await foreach (var item in source.WithCancellation(ct))
    {
        batch.Add(item);

        if (batch.Count >= batchSize)
        {
            yield return batch;
            batch = new List<T>(batchSize);
        }
    }

    if (batch.Count > 0)
        yield return batch;
}

// Usage:
await foreach (var batch in _repository.StreamActiveUsersAsync(ct).BatchAsync(100, ct))
{
    await _bulkService.ProcessBatchAsync(batch, ct);
}
```

### 7. Phòng Ngừa

**Checklist:**
- [ ] Phân tích query: expected row count có thể lớn không?
- [ ] Nếu > 10K rows: cân nhắc `IAsyncEnumerable<T>`
- [ ] Dùng `AsAsyncEnumerable()` với EF Core cho streaming queries
- [ ] Implement `[EnumeratorCancellation]` cho cancellation support
- [ ] Test với large dataset để đo memory usage

**EF Core Configuration cho streaming:**
```csharp
// Đảm bảo EF Core không buffer
services.AddDbContext<AppDbContext>(options =>
{
    options.UseNpgsql(connectionString)
           .EnableDetailedErrors(isDevelopment);
    // Không dùng UseQueryTrackingBehavior(QueryTrackingBehavior.NoTracking)
    // khi streaming - có thể tắt change tracking để tiết kiệm memory
});

// Trong query streaming:
_context.Users
    .AsNoTracking() // Tắt change tracking - tiết kiệm memory
    .Where(u => u.IsActive)
    .AsAsyncEnumerable()
```

---

## Tổng Kết

| # | Pattern | Mức Độ | Tác Động |
|---|---------|--------|----------|
| 01 | Async Void | CRITICAL | App crash, exception không thể bắt |
| 02 | Deadlock SynchronizationContext | CRITICAL | Deadlock hoàn toàn, request treo mãi |
| 03 | ConfigureAwait Thiếu | HIGH | Deadlock tiềm ẩn, hiệu năng kém |
| 04 | Task.Run Trong ASP.NET | HIGH | Thread waste, throughput giảm |
| 05 | Fire-and-Forget Không An Toàn | HIGH | Mất exception, data loss |
| 06 | Async Lazy Init Sai | MEDIUM | Race condition, exception cache |
| 07 | CancellationToken Bỏ Qua | HIGH | Lãng phí tài nguyên |
| 08 | Parallel.ForEach Async | HIGH | Silent fire-and-forget, exception mất |
| 09 | SemaphoreSlim Sai | MEDIUM | Deadlock, resource leak |
| 10 | ValueTask Misuse | HIGH | Undefined behavior, memory corruption |
| 11 | Thread Pool Starvation | CRITICAL | App đóng băng hoàn toàn |
| 12 | Async Disposal Thiếu | HIGH | Resource leak, data loss khi dispose |
| 13 | Task.WhenAll Exception Loss | MEDIUM | Mất thông tin lỗi |
| 14 | Channel Bounded Full | MEDIUM | Blocking hoặc silent drop |
| 15 | Timer Trong Async | MEDIUM | Concurrent execution, exception mất |
| 16 | IAsyncEnumerable Thiếu | MEDIUM | OutOfMemory, latency cao |

---

## Công Cụ Phân Tích Tự Động

### Roslyn Analyzers Quan Trọng

```xml
<!-- Thêm vào .csproj -->
<PackageReference Include="Microsoft.VisualStudio.Threading.Analyzers" Version="17.*">
  <PrivateAssets>all</PrivateAssets>
  <IncludeAssets>runtime; build; native; contentfiles; analyzers</IncludeAssets>
</PackageReference>

<PackageReference Include="Roslynator.Analyzers" Version="4.*">
  <PrivateAssets>all</PrivateAssets>
  <IncludeAssets>runtime; build; native; contentfiles; analyzers</IncludeAssets>
</PackageReference>
```

### .editorconfig Rules

```ini
[*.cs]
# Async void
dotnet_diagnostic.VSTHRD100.severity = error

# Avoid blocking calls
dotnet_diagnostic.VSTHRD002.severity = error
dotnet_diagnostic.VSTHRD104.severity = warning

# ConfigureAwait
dotnet_diagnostic.CA2007.severity = warning

# CancellationToken
dotnet_diagnostic.CA2016.severity = warning

# Async naming
dotnet_diagnostic.VSTHRD200.severity = suggestion
```

### Quick Scan Script (ripgrep)

```bash
#!/bin/bash
# quick-async-scan.sh - Scan codebase for common async anti-patterns
# Chạy từ thư mục gốc project

echo "=== ASYNC ANTI-PATTERN SCAN ==="

echo ""
echo "--- [CRITICAL] Async Void Methods ---"
rg "^\s+(private|public|protected|internal)\s+async\s+void\s+(?!.*EventHandler)" --type cs -l

echo ""
echo "--- [CRITICAL] Blocking Calls (.Result/.Wait()) ---"
rg "\.(Result|Wait\(\))\b" --type cs -l

echo ""
echo "--- [HIGH] Task.Run với async lambda ---"
rg "Task\.Run\(async" --type cs -l

echo ""
echo "--- [HIGH] Parallel.ForEach với async ---"
rg "Parallel\.ForEach\(.*async" --type cs -l

echo ""
echo "--- [HIGH] Thread.Sleep trong code ---"
rg "Thread\.Sleep\(" --type cs -l

echo ""
echo "--- [MEDIUM] Timer với async callback ---"
rg "new\s+Timer\(.*async" --type cs -l

echo ""
echo "--- [MEDIUM] Lazy<Task ---"
rg "Lazy<Task" --type cs -l

echo "=== SCAN COMPLETE ==="
```
