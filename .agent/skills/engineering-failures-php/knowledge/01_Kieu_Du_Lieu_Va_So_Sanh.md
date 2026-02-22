# Domain 01: Kiểu Dữ Liệu Và So Sánh (Type Coercion & Comparison)

**Lĩnh vực:** Kiểu Dữ Liệu / So Sánh / Type System
**Số lượng patterns:** 14
**Ngôn ngữ:** PHP 8.x
**Cập nhật:** 2026-02-18

---

## Mục Lục

1. [Loose Comparison Trap (==)](#1-loose-comparison-trap----critical)
2. [Type Juggling Authentication Bypass](#2-type-juggling-authentication-bypass---critical)
3. [Integer Overflow Silent](#3-integer-overflow-silent---high)
4. [Array Key Coercion](#4-array-key-coercion---high)
5. [Null Coalescing Confusion (?? vs ?: vs isset vs empty)](#5-null-coalescing-confusion----vs----vs-isset-vs-empty---medium)
6. [String Number Comparison](#6-string-number-comparison---high)
7. [Float Precision](#7-float-precision---medium)
8. [Strict Types Thiếu (Missing declare strict_types)](#8-strict-types-thiếu-missing-declare-strict_types---high)
9. [Enum String Cast](#9-enum-string-cast---medium)
10. [Union Type Narrowing](#10-union-type-narrowing---medium)
11. [Mixed Type Abuse](#11-mixed-type-abuse---high)
12. [Array Spread Gotcha](#12-array-spread-gotcha---medium)
13. [Readonly Property Clone](#13-readonly-property-clone---medium)
14. [Fiber State Confusion](#14-fiber-state-confusion---high)

---

## 1. Loose Comparison Trap (==) - CRITICAL

### 1. Tên
**Loose Comparison Trap** (Bẫy So Sánh Lỏng với `==`)

### 2. Phân loại
Kiểu Dữ Liệu / So Sánh / Type Coercion

### 3. Mức nghiêm trọng
🔴 **CRITICAL** - Có thể dẫn đến bypass xác thực, logic sai hoàn toàn, và lỗ hổng bảo mật nghiêm trọng khi toán tử `==` tự động ép kiểu hai vế trước khi so sánh.

### 4. Vấn đề
PHP dùng `==` sẽ thực hiện **type coercion** (ép kiểu ngầm định) trước khi so sánh. Điều này tạo ra các kết quả hoàn toàn bất ngờ: số `0` bằng chuỗi bất kỳ không bắt đầu bằng số, `null` bằng `false` bằng `""` bằng `0`, `true` bằng mọi chuỗi không rỗng.

```
BẢNG SO SÁNH NGUY HIỂM VỚI == (PHP 7/8)
==========================================

Biểu thức                 Kết quả    Lý do
------------------------  ---------  ----------------------------
0    == "foo"             TRUE (7)   "foo" cast sang int = 0
0    == ""               TRUE (7)   "" cast sang int = 0
0    == "0"              TRUE       Cả hai đều là 0
0    == false            TRUE       false = 0
0    == null             TRUE       null = 0
""   == null             TRUE       cả hai "falsy"
""   == false            TRUE       cả hai "falsy"
"1"  == "01"             TRUE       cast sang int = 1
"10" == "1e1"            TRUE       1e1 = 10.0
100  == "1e2"            TRUE       1e2 = 100
"0"  == false            TRUE       "0" = 0 = false

LƯU Ý PHP 8: 0 == "foo" đã sửa thành FALSE
  Nhưng: "1" == "01" vẫn TRUE
  Và:    null == false vẫn TRUE
  Nguy cơ vẫn còn trong nhiều trường hợp!

LUỒNG BYPASS XÁC THỰC:
=======================

  Kẻ tấn công         PHP Application          Database
       |                     |                     |
       | POST token=0        |                     |
       |-------------------->|                     |
       |                     | $token = $_POST['token']  // "0"
       |                     | $hash = getHashFromDB()   // "abc123"
       |                     |                     |
       |                     | if ($token == $hash)      // "0" == "abc123"
       |                     | // PHP 7: TRUE! (cả hai cast sang 0)
       |                     |                     |
       |  Access Granted!    |                     |
       |<--------------------|                     |
```

### 5. Phát hiện trong mã nguồn

**Dấu hiệu nguy hiểm:**
- Dùng `==` để so sánh giá trị từ `$_GET`, `$_POST`, database, hash functions
- So sánh kết quả `md5()`, `sha1()`, `hash()` bằng `==`
- So sánh token, OTP, password reset key bằng `==`

**Regex patterns (dùng với ripgrep):**
```bash
# Tìm so sánh == với hash functions
rg --type php "(md5|sha1|sha256|hash)\(.*\)\s*==\s" -n

# Tìm so sánh == với biến từ request
rg --type php "\\\$_(GET|POST|REQUEST|COOKIE)\[.*\]\s*==[^=]" -n

# Tìm if với == (không phải ===) trên các biến nhạy cảm
rg --type php "if\s*\(.*\$(token|hash|key|password|otp|code)\s*==[^=]" -n

# Tìm switch với loose comparison (switch dùng == nội bộ)
rg --type php "switch\s*\(\s*\\\$(type|status|role|mode)\s*\)" -n
```

### 6. Giải pháp

| Toán tử | Kiểu so sánh | Dùng khi nào |
|---------|-------------|--------------|
| `==`  | Loose (ép kiểu) | Không bao giờ dùng cho bảo mật |
| `===` | Strict (cùng type + value) | Luôn dùng mặc định |
| `hash_equals()` | Timing-safe strict | So sánh hash, token, secret |
| `strcmp()` | So sánh chuỗi nhị phân | Không an toàn về timing |

```php
<?php
declare(strict_types=1);

// ============================================================
// BAD - Loose comparison dẫn đến bug và security issue
// ============================================================

// PHP 7: "0abc" == 0 => TRUE => bypass được!
$userToken = $_POST['token'];           // "0"
$validToken = getTokenFromDB();         // "abc123"
if ($userToken == $validToken) {        // BUG! TRUE trong PHP 7
    grantAccess();
}

// Switch dùng == nội bộ - bất ngờ!
switch ($_GET['status']) {
    case 0:      // Match với "foo", "", "bar" (PHP 7)
        break;
    case false:  // Match với null, 0, ""
        break;
}

// So sánh kết quả in_array với loose mode
$allowed = [0, 1, 2];
in_array("foo", $allowed);   // TRUE trong PHP 7! (0 == "foo")
in_array(null, $allowed);    // TRUE! (0 == null)

// ============================================================
// GOOD - Strict comparison mọi nơi
// ============================================================

// Luôn dùng === cho so sánh thông thường
$userToken = $_POST['token'] ?? '';
$validToken = getTokenFromDB();
if ($userToken === $validToken) {       // Strict: phải cùng type và value
    grantAccess();
}

// So sánh token bảo mật - dùng hash_equals (chống timing attack)
if (hash_equals($validToken, $userToken)) {
    grantAccess();
}

// in_array với strict mode
$allowed = [0, 1, 2];
in_array("foo", $allowed, true);   // FALSE - strict mode
in_array(0, $allowed, true);       // TRUE - đúng

// Switch thay bằng match (PHP 8 - luôn strict)
$result = match($_GET['status']) {
    '0', 'inactive' => handleInactive(),
    '1', 'active'   => handleActive(),
    default         => handleUnknown(),
};
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Thay toàn bộ `==` bằng `===` trong codebase (trừ khi cố ý ép kiểu)
- [ ] Dùng `hash_equals()` cho mọi so sánh token/hash bảo mật
- [ ] Dùng `in_array($val, $arr, true)` với strict mode
- [ ] Ưu tiên dùng `match` thay `switch` trong PHP 8
- [ ] Bật `declare(strict_types=1)` ở đầu mọi file

**PHPStan / Psalm rules:**
```yaml
# phpstan.neon
parameters:
  level: 8
  # Cài phpstan-strict-rules
  # composer require --dev phpstan/phpstan-strict-rules
```

```bash
# Psalm - phát hiện loose comparison
composer require --dev vimeo/psalm
# Thêm vào psalm.xml:
# <plugin filename="vendor/psalm/plugin-laravel/src/Plugin.php"/>
vendor/bin/psalm --show-info=true --find-dead-code
```

---

## 2. Type Juggling Authentication Bypass - CRITICAL

### 1. Tên
**Type Juggling Authentication Bypass** (Bypass Xác Thực Qua Ép Kiểu)

### 2. Phân loại
Kiểu Dữ Liệu / Bảo Mật / Authentication

### 3. Mức nghiêm trọng
🔴 **CRITICAL** - Kẻ tấn công có thể bypass hoàn toàn xác thực bằng cách khai thác type juggling trong so sánh JSON/loose comparison, dẫn đến chiếm quyền admin.

### 4. Vấn đề
Khi ứng dụng nhận JSON và dùng `json_decode()` mà không ép kiểu rõ ràng, kẻ tấn công có thể truyền kiểu dữ liệu sai (số thay vì chuỗi, `true`/`false`/`null`) để bypass so sánh `==`. Đây là lỗ hổng cực kỳ phổ biến trong REST API PHP.

```
LUỒNG TẤN CÔNG TYPE JUGGLING
==============================

Bình thường:
  POST {"password": "mysecret"}
  $data->password = "mysecret" (string)
  $hash = "$2y$..." (bcrypt hash)
  password_verify("mysecret", $hash) => TRUE => OK

Tấn công:
  POST {"password": true}
  $data->password = true (boolean)
  if ($data->password == $storedPassword)
  // true == "anystring" => TRUE! (loose comparison)
  => Bypass xác thực!

  Hoặc:
  POST {"role": "admin"}    // nếu không validate
  $data->role = "admin"
  if ($data->role == $expectedRole) => bypass role check

ATTACK VECTORS:
===============
  JSON: {"token": 0}          => 0 == "anystring" (PHP 7)
  JSON: {"token": true}       => true == "non-empty-string"
  JSON: {"token": null}       => null == "" == false == 0
  JSON: {"count": "999999"}   => string cast sang int tùy ngữ cảnh
```

### 5. Phát hiện trong mã nguồn

**Dấu hiệu nguy hiểm:**
- `json_decode()` không có type casting sau đó
- So sánh `$data->field ==` với giá trị nhạy cảm
- Không validate kiểu dữ liệu của JSON input

**Regex patterns (dùng với ripgrep):**
```bash
# Tìm json_decode rồi dùng == ngay sau
rg --type php "json_decode" -A 10 | grep -E "==[^=]"

# Tìm so sánh trực tiếp field từ object decode
rg --type php "\\\$data->(password|token|key|hash|otp)\s*==[^=]" -n

# Tìm password_verify bị bypass - dùng == thay vì hàm
rg --type php "if\s*\(.*password\s*==[^=]" -n

# Tìm json_decode mà không validate
rg --type php "json_decode\s*\(" -n
```

### 6. Giải pháp

| Phương pháp | Mức an toàn | Ghi chú |
|------------|------------|---------|
| `==` với JSON field | ❌ Nguy hiểm | Dễ bypass bằng type juggling |
| `===` với JSON field | ⚠️ Tốt hơn | Vẫn cần validate type trước |
| Validate type + `===` | ✅ An toàn | Kiểm tra `is_string()` trước |
| DTO với type hints | ✅ Tốt nhất | PHP 8 typed properties |
| `password_verify()` | ✅ An toàn | Luôn dùng cho password |

```php
<?php
declare(strict_types=1);

// ============================================================
// BAD - Type juggling bypass
// ============================================================

// API endpoint nhận JSON
$body = file_get_contents('php://input');
$data = json_decode($body);  // stdClass, các field không có type

// Attacker gửi {"password": true}
if ($data->password == $storedPasswordHash) {  // true == "hash" => TRUE!
    return loginSuccess();
}

// Attacker gửi {"token": 0} (PHP 7)
if ($data->token == $validToken) {  // 0 == "abc123" => TRUE! (PHP 7)
    return resetPassword();
}

// ============================================================
// GOOD - Validate type và dùng strict comparison
// ============================================================

$body = file_get_contents('php://input');
$data = json_decode($body, true);  // Array thay vì stdClass

// Validate type trước
if (!isset($data['password']) || !is_string($data['password'])) {
    throw new \InvalidArgumentException('password phải là string');
}

// Luôn dùng password_verify cho password
if (!password_verify($data['password'], $storedHash)) {
    throw new UnauthorizedException('Sai mật khẩu');
}

// Validate token với hash_equals (timing-safe)
if (!isset($data['token']) || !is_string($data['token'])) {
    throw new \InvalidArgumentException('token không hợp lệ');
}
if (!hash_equals($validToken, $data['token'])) {
    throw new UnauthorizedException('Token không hợp lệ');
}

// BEST PRACTICE: Dùng DTO với typed properties (PHP 8)
final class LoginRequest
{
    public function __construct(
        public readonly string $email,    // PHP ép kiểu khi gán
        public readonly string $password,
    ) {}

    public static function fromArray(array $data): self
    {
        if (!isset($data['email'], $data['password'])) {
            throw new \InvalidArgumentException('Thiếu trường bắt buộc');
        }
        return new self(
            email: (string) $data['email'],
            password: (string) $data['password'],
        );
    }
}

$request = LoginRequest::fromArray($data);
if (!password_verify($request->password, $storedHash)) {
    throw new UnauthorizedException();
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Luôn validate kiểu dữ liệu (`is_string()`, `is_int()`) trước khi so sánh
- [ ] Dùng `password_verify()` cho password, không bao giờ dùng `==`
- [ ] Dùng `hash_equals()` cho token/key bảo mật
- [ ] Dùng DTO với typed properties để tự động ép kiểu an toàn
- [ ] Dùng thư viện validation (Symfony Validator, Laravel Validation)
- [ ] Không bao giờ so sánh trực tiếp field từ JSON với `==`

**PHPStan / Psalm rules:**
```yaml
# phpstan.neon
parameters:
  level: 8
includes:
  - vendor/phpstan/phpstan-strict-rules/rules.neon
```

```bash
# Tìm toàn bộ file dùng json_decode mà không validate
rg --type php "json_decode" -l | xargs rg "==[^=]"
```

---

## 3. Integer Overflow Silent - HIGH

### 1. Tên
**Integer Overflow Silent** (Tràn Số Nguyên Không Có Cảnh Báo)

### 2. Phân loại
Kiểu Dữ Liệu / Arithmetic / Platform Dependency

### 3. Mức nghiêm trọng
🟠 **HIGH** - PHP tự động chuyển integer sang float khi tràn số mà không có exception hay cảnh báo, dẫn đến tính toán sai lặng lẽ trong tài chính, ID sinh ra, hoặc vòng lặp vô hạn.

### 4. Vấn đề
PHP không có integer overflow exception. Khi giá trị vượt `PHP_INT_MAX` (9223372036854775807 trên 64-bit), PHP tự động convert sang `float`. Float không thể biểu diễn chính xác số nguyên lớn, dẫn đến mất độ chính xác. Trên hệ thống 32-bit, `PHP_INT_MAX` chỉ là 2147483647.

```
INTEGER OVERFLOW TRONG PHP
============================

64-bit system:
  PHP_INT_MAX = 9,223,372,036,854,775,807

  $max = PHP_INT_MAX;           // 9223372036854775807 (int)
  $overflow = $max + 1;         // 9.2233720368548E+18 (float!)
  gettype($overflow);           // "double" - không phải "integer"

  // Mất độ chính xác:
  $a = PHP_INT_MAX + 1;         // float: 9.2233720368548E+18
  $b = PHP_INT_MAX + 2;         // float: 9.2233720368548E+18
  $a === $b;                    // TRUE! Mất 2 đơn vị cuối

32-bit system (PHP_INT_MAX = 2,147,483,647):
  $price = 2147483647;          // int
  $price += 1;                  // -2147483648 (wrap-around!)
  // Hoặc convert sang float tùy platform

TÌNH HUỐNG THỰC TẾ NGUY HIỂM:
================================
  // Tính tổng doanh thu (triệu đồng)
  $total = 0;
  foreach ($orders as $order) {
      $total += $order->amount;  // Khi $total > PHP_INT_MAX: silent float!
  }
  // $total có thể sai hàng nghìn đồng mà không ai biết
```

### 5. Phát hiện trong mã nguồn

**Dấu hiệu nguy hiểm:**
- Tính toán cộng dồn số lớn (tài chính, analytics)
- Dùng `intval()` trên số rất lớn từ API
- ID sinh ra từ timestamp * random mà không kiểm tra giới hạn

**Regex patterns (dùng với ripgrep):**
```bash
# Tìm cộng dồn trong vòng lặp (potential overflow)
rg --type php "\\\$total\s*\+=|\\\$sum\s*\+=|\\\$count\s*\+=" -n

# Tìm intval() dùng với field có thể lớn
rg --type php "intval\s*\(\s*\\\$" -n

# Tìm dùng PHP_INT_MAX hoặc kiểm tra overflow
rg --type php "PHP_INT_MAX|PHP_INT_MIN" -n

# Tìm tính toán tài chính không dùng BCMath
rg --type php "(price|amount|total|sum|balance)\s*[\+\-\*]\s*" -n
```

### 6. Giải pháp

| Phương pháp | Dùng khi nào | Ghi chú |
|------------|-------------|---------|
| PHP native int | Số nhỏ < PHP_INT_MAX/2 | Nhanh, đơn giản |
| BCMath (`bcadd`, `bcmul`) | Tài chính, số lớn | Chính xác tuyệt đối |
| GMP extension | Số nguyên cực lớn | Hiệu suất tốt hơn BCMath |
| `brick/money` library | Tiền tệ | Best practice cho money |

```php
<?php
declare(strict_types=1);

// ============================================================
// BAD - Silent integer overflow
// ============================================================

// Tính tổng doanh thu - có thể overflow
$totalRevenue = 0;
foreach ($orders as $order) {
    $totalRevenue += $order->amountCents;  // Có thể thành float!
}

// Nhân giá với số lượng lớn
$price = 999999999;
$quantity = 100000;
$total = $price * $quantity;  // 99999999900000 - OK trên 64-bit
                               // Nhưng trên 32-bit: OVERFLOW!

// Dùng intval trên số rất lớn
$bigId = intval("99999999999999999999");  // Cắt bớt, không báo lỗi!

// ============================================================
// GOOD - Dùng BCMath cho tài chính
// ============================================================

// BCMath: chính xác tuyệt đối với string representation
$totalRevenue = '0';
foreach ($orders as $order) {
    $totalRevenue = bcadd($totalRevenue, (string) $order->amountCents, 0);
}

// Nhân với BCMath
$price = '999999999';
$quantity = '100000';
$total = bcmul($price, $quantity, 0);  // "99999999900000" - chính xác

// Kiểm tra overflow trước khi dùng int
function safeToInt(string $value): int
{
    if (bccomp($value, (string) PHP_INT_MAX) > 0) {
        throw new \OverflowException("Giá trị vượt PHP_INT_MAX: $value");
    }
    if (bccomp($value, (string) PHP_INT_MIN) < 0) {
        throw new \UnderflowException("Giá trị dưới PHP_INT_MIN: $value");
    }
    return (int) $value;
}

// Dùng brick/money cho tiền tệ (khuyến nghị)
// composer require brick/money
use Brick\Money\Money;
use Brick\Money\Currency;

$price = Money::of('999.99', 'JPY');
$quantity = 1000;
$total = $price->multipliedBy($quantity);  // Chính xác, type-safe
echo $total->getAmount();  // "999990.00"
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Luôn dùng BCMath hoặc `brick/money` cho tính toán tài chính
- [ ] Không dùng `float` để lưu tiền - luôn dùng `int` (cents) hoặc BCMath string
- [ ] Kiểm tra `PHP_INT_SIZE` khi deploy lên server 32-bit
- [ ] Validate range của input số lớn trước khi tính toán
- [ ] Dùng `gettype()` hoặc `is_int()` để kiểm tra sau tính toán quan trọng

**PHPStan / Psalm rules:**
```yaml
# phpstan.neon - detect potential float from int operations
parameters:
  level: 8
  # Psalm có thể detect overflow trong một số trường hợp
```

```bash
# Tìm tính toán tài chính không dùng BCMath
rg --type php "(price|amount|total|balance)\s*[\+\-\*\/]=?\s*\\\$" -n \
  | grep -v "bc(add|sub|mul|div)"
```

---

## 4. Array Key Coercion - HIGH

### 1. Tên
**Array Key Coercion** (Ép Kiểu Key Mảng)

### 2. Phân loại
Kiểu Dữ Liệu / Array / Implicit Conversion

### 3. Mức nghiêm trọng
🟠 **HIGH** - PHP tự động ép kiểu array key theo các quy tắc không rõ ràng, có thể ghi đè dữ liệu, mất data, hoặc tạo lỗ hổng logic khi dùng user input làm array key.

### 4. Vấn đề
PHP array chỉ chấp nhận `int` hoặc `string` làm key. Khi dùng kiểu khác: `float` bị truncate thành `int`, `bool` thành `0`/`1`, `null` thành `""`, object gây lỗi. Điều này dẫn đến việc ghi đè key không mong muốn và mất dữ liệu.

```
QUY TẮC ÉP KIỂU ARRAY KEY TRONG PHP
======================================

Giá trị gốc    Key thực tế    Ghi chú
------------   -----------   ----------------------------
"1"            1             String số -> int
"01"           "01"          String không thuần số -> giữ nguyên
"1.5"          "1.5"         String float -> giữ nguyên string
1.7            1             Float -> truncate (bỏ phần thập phân!)
true           1             Bool true -> 1
false          0             Bool false -> 0
null           ""            null -> empty string
"key"          "key"         String thường -> giữ nguyên

VÍ DỤ GHI ĐÈ KEY NGUY HIỂM:
==============================

$arr = [];
$arr[1]     = "từ int 1";
$arr["1"]   = "từ string '1'";    // GHI ĐÈ key 1!
$arr[1.9]   = "từ float 1.9";     // GHI ĐÈ key 1!
$arr[true]  = "từ true";          // GHI ĐÈ key 1!

// Kết quả: $arr chỉ có 1 phần tử: [1 => "từ true"]
// Mất hoàn toàn 3 giá trị trước!

TÌNH HUỐNG NGUY HIỂM VỚI USER INPUT:
======================================
  $permissions = [];
  foreach ($userInput as $key => $value) {
      $permissions[$key] = $value;
      // Nếu user gửi key "0" và key false -> cùng một ô!
  }
```

### 5. Phát hiện trong mã nguồn

**Dấu hiệu nguy hiểm:**
- Dùng biến từ request/db làm array key trực tiếp
- Dùng float, bool, null làm array key
- `array_flip()` trên mảng có giá trị số mixed với string số

**Regex patterns (dùng với ripgrep):**
```bash
# Tìm dùng biến request làm array key
rg --type php "\\\$arr\[\\\$_(GET|POST|REQUEST)\[" -n

# Tìm array với float key
rg --type php "\\\$\w+\[\s*[0-9]+\.[0-9]+" -n

# Tìm array_flip có thể bị coercion
rg --type php "array_flip\s*\(" -n

# Tìm foreach dùng $key trực tiếp làm key mảng khác
rg --type php "foreach.*\\\$key.*\\\$\w+\[\\\$key\]" -n
```

### 6. Giải pháp

| Tình huống | Phương pháp an toàn | Ghi chú |
|-----------|-------------------|---------|
| Key từ user input | Validate và cast `(string)` hoặc `(int)` | Tường minh |
| Key số | Luôn dùng `int` nhất quán | Tránh mix string/int |
| Nhóm theo giá trị | `array_group_by()` custom | Tránh dùng giá trị float làm key |
| Kiểm tra key | `array_key_exists()` với `===` | Không dùng `isset` cho key 0/false |

```php
<?php
declare(strict_types=1);

// ============================================================
// BAD - Array key coercion dẫn đến mất data
// ============================================================

// Float key bị truncate
$scores = [];
$scores[1.1] = "A";   // key = 1
$scores[1.9] = "B";   // key = 1, GHI ĐÈ "A"!
// Kết quả: [1 => "B"] - mất "A"

// Bool key coercion
$flags = [];
$flags[true]  = "admin";    // key = 1
$flags[1]     = "regular";  // key = 1, GHI ĐÈ!
$flags[false] = "guest";    // key = 0

// User input làm key - nguy hiểm
$userGroups = [];
foreach ($_POST['assignments'] as $userId => $groupId) {
    $userGroups[$groupId][] = $userId;
    // Nếu $groupId là "1" và 1 -> cùng một group!
}

// ============================================================
// GOOD - Tường minh về kiểu key
// ============================================================

// Cast key rõ ràng
$scores = [];
$scores[(string) "1.1"] = "A";   // key = "1.1"
$scores[(string) "1.9"] = "B";   // key = "1.9", không ghi đè
// Kết quả: ["1.1" => "A", "1.9" => "B"] - đúng

// Validate user input trước khi dùng làm key
$userGroups = [];
foreach ($_POST['assignments'] ?? [] as $userId => $groupId) {
    $userId  = filter_var($userId,  FILTER_VALIDATE_INT);
    $groupId = filter_var($groupId, FILTER_VALIDATE_INT);

    if ($userId === false || $groupId === false) {
        continue; // Skip invalid input
    }

    $userGroups[(int) $groupId][] = (int) $userId;
}

// Dùng SplObjectStorage thay array khi cần object key
$map = new \SplObjectStorage();
$map[$objectA] = "value A";
$map[$objectB] = "value B";

// Kiểm tra key tồn tại đúng cách
$arr = [0 => "zero", "" => "empty"];
array_key_exists(0, $arr);   // TRUE - đúng
array_key_exists("", $arr);  // TRUE - đúng
isset($arr[0]);               // TRUE
isset($arr[false]);           // TRUE (false -> 0) - NGUY HIỂM!
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Không bao giờ dùng `float`, `bool`, `null` làm array key
- [ ] Cast key tường minh `(int)` hoặc `(string)` trước khi dùng
- [ ] Validate input từ user/db trước khi dùng làm key
- [ ] Dùng `array_key_exists()` thay `isset()` khi key có thể là 0 hoặc false
- [ ] Review tất cả nơi dùng biến từ request làm array key

**PHPStan / Psalm rules:**
```yaml
# Psalm - detect array key type issues
# psalm.xml
<plugins>
  <plugin filename="vendor/psalm/plugin-laravel/src/Plugin.php"/>
</plugins>
```

---

## 5. Null Coalescing Confusion (?? vs ?: vs isset vs empty) - MEDIUM

### 1. Tên
**Null Coalescing Confusion** (Nhầm Lẫn Giữa `??`, `?:`, `isset()`, `empty()`)

### 2. Phân loại
Kiểu Dữ Liệu / Null Handling / Control Flow

### 3. Mức nghiêm trọng
🟡 **MEDIUM** - Nhầm lẫn giữa các toán tử/hàm xử lý null/falsy có thể dẫn đến giá trị mặc định sai, logic điều kiện sai, hoặc lỗ hổng khi giá trị `0`, `""`, `false` bị xử lý như `null`.

### 4. Vấn đề
PHP có 4 cách khác nhau để xử lý null/falsy, mỗi cách có ngữ nghĩa khác nhau. Nhầm lẫn giữa chúng rất phổ biến và tạo ra bug khó phát hiện, đặc biệt khi giá trị hợp lệ là `0`, `"0"`, `""`, hay `false`.

```
SO SÁNH CÁC OPERATOR/HÀM FALSY
=================================

Giá trị      isset()   empty()   ?? "def"   ?: "def"
-----------  --------  --------  ---------  ---------
null         FALSE     TRUE      "def"      "def"
0            TRUE      TRUE      0          "def"  <- KHÁC NHAU!
""           TRUE      TRUE      ""         "def"  <- KHÁC NHAU!
"0"          TRUE      TRUE      "0"        "def"  <- KHÁC NHAU!
false        TRUE      TRUE      false      "def"  <- KHÁC NHAU!
[]           TRUE      TRUE      []         "def"  <- KHÁC NHAU!
"text"       TRUE      FALSE     "text"     "text"
1            TRUE      FALSE     1          1

?? = Chỉ check NULL (hoặc undefined)
?:  = Check FALSY (giống if($x) ... else ...)

LUỒNG BUG THỰC TẾ:
====================
  $quantity = $_POST['quantity'] ?: 1;
  // User gửi quantity=0 (hợp lệ: đặt 0 sản phẩm)
  // ?:  thấy 0 là falsy -> trả về 1 (SAI!)
  // ??  thấy "0" không phải null -> trả về "0" (ĐÚNG hơn)
```

### 5. Phát hiện trong mã nguồn

**Dấu hiệu nguy hiểm:**
- Dùng `?:` với số lượng, tuổi, giá tiền (có thể là 0)
- Dùng `empty()` để validate input (sẽ reject "0", 0, false)
- Dùng `isset()` để check giá trị (không phân biệt null vs undefined)

**Regex patterns (dùng với ripgrep):**
```bash
# Tìm ?: với biến có thể là 0
rg --type php "\\\$(quantity|count|age|amount|price|score)\s*\?:" -n

# Tìm empty() dùng để validate
rg --type php "if\s*\(!?\s*empty\s*\(\s*\\\$_(GET|POST|REQUEST)" -n

# Tìm ?? vs ?: mixed usage
rg --type php "\?\?" -n
rg --type php "[^?]\?:[^:]" -n
```

### 6. Giải pháp

| Operator/Hàm | Trả về default khi | Giữ giá trị khi | Dùng cho |
|-------------|-------------------|----------------|---------|
| `?? $default` | `null` hoặc chưa đặt | `0`, `""`, `false` | Optional fields có thể là falsy |
| `?: $default` | Falsy (`0`, `""`, `false`, `null`) | Truthy | Chỉ khi falsy thực sự cần default |
| `isset($x)` | - | TRUE khi không phải null | Check biến tồn tại và không null |
| `empty($x)` | - | FALSE khi falsy | Validate "phải có giá trị truthy" |

```php
<?php
declare(strict_types=1);

// ============================================================
// BAD - Nhầm lẫn operator
// ============================================================

// Bug: quantity=0 hợp lệ nhưng bị replace bằng 1
$quantity = $_POST['quantity'] ?: 1;    // 0 -> 1, SAI!

// Bug: price=0 (miễn phí) bị reject
$price = $_POST['price'] ?: null;       // 0 -> null, SAI!

// Bug: empty() reject "0" là chuỗi hợp lệ
if (empty($_POST['code'])) {            // "0" là falsy -> reject!
    throw new \Exception('Mã không được trống');
}

// Bug: ternary với isset không xử lý null
$name = isset($_GET['name']) ? $_GET['name'] : 'Guest';
// Cách viết dài dòng, và nếu $_GET['name'] = "" -> trả về ""
// Có thể muốn trả về 'Guest' khi chuỗi rỗng

// ============================================================
// GOOD - Chọn đúng operator cho từng tình huống
// ============================================================

// Dùng ?? khi giá trị 0/""/false là hợp lệ
$quantity = $_POST['quantity'] ?? 1;    // Chỉ default khi không gửi
$price    = $_POST['price']    ?? null; // Giữ nguyên 0 nếu user gửi

// Validate rõ ràng thay vì dùng empty()
$code = $_POST['code'] ?? '';
if (!isset($_POST['code'])) {
    throw new \Exception('Thiếu trường code');
}
// Hoặc validate bằng filter_var
$code = filter_input(INPUT_POST, 'code', FILTER_DEFAULT);
if ($code === null || $code === false) {
    throw new \Exception('Trường code không hợp lệ');
}

// Khi thực sự muốn falsy -> default: dùng ?: có chủ ý
$displayName = $user->nickname ?: $user->fullName;  // Nếu nickname rỗng, dùng fullName

// Null coalescing assignment (PHP 7.4+)
$config['timeout'] ??= 30;  // Chỉ set nếu chưa có (không phải falsy check)

// Typed với default rõ ràng
function getQuantity(array $data): int
{
    $raw = $data['quantity'] ?? null;
    if ($raw === null) {
        return 1; // Default
    }
    $quantity = filter_var($raw, FILTER_VALIDATE_INT);
    if ($quantity === false || $quantity < 0) {
        throw new \InvalidArgumentException('quantity phải là số nguyên >= 0');
    }
    return $quantity; // 0 là hợp lệ!
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Xác định rõ: "giá trị 0/false/'' có hợp lệ không?" trước khi chọn operator
- [ ] Ưu tiên `??` thay `?:` cho optional parameters
- [ ] Tránh `empty()` để validate - dùng explicit check thay thế
- [ ] Thêm type hints để PHP tự validate kiểu

**PHPStan / Psalm rules:**
```bash
# PHPStan level 8 sẽ cảnh báo nhiều trường hợp mixed type
vendor/bin/phpstan analyse --level=8 src/

# Psalm strict mode
vendor/bin/psalm --strict-types
```

---

## 6. String Number Comparison - HIGH

### 1. Tên
**String Number Comparison** (So Sánh Chuỗi Số Với Số)

### 2. Phân loại
Kiểu Dữ Liệu / So Sánh / Implicit Casting

### 3. Mức nghiêm trọng
🟠 **HIGH** - PHP 8 thay đổi hành vi so sánh string-int so với PHP 7, tạo ra breaking change ẩn khi migrate và logic sai trong các hệ thống sort/search khi trộn lẫn string và number.

### 4. Vấn đề
Trong PHP 7: `0 == "foo"` là TRUE (string ép sang int = 0). Trong PHP 8: đã sửa thành FALSE. Tuy nhiên, PHP 8 vẫn có nhiều trường hợp so sánh chuỗi số gây bất ngờ, đặc biệt khi dùng `<`, `>`, `usort()`, `array_search()`.

```
PHP 7 vs PHP 8 - THAY ĐỔI BREAKING CHANGE
===========================================

Biểu thức           PHP 7    PHP 8    Ghi chú
------------------  -------  -------  ---------------------
0 == "foo"          TRUE     FALSE    PHP 8 FIX quan trọng!
0 == ""             TRUE     FALSE    PHP 8 FIX!
0 == "0"            TRUE     TRUE     Vẫn TRUE (cả hai số)
"1" == "01"         TRUE     TRUE     Vẫn TRUE (numeric string)
"10" == "1e1"       TRUE     TRUE     Vẫn TRUE (scientific)
"0" == false        TRUE     TRUE     Vẫn TRUE
100 == "1e2"        TRUE     TRUE     Vẫn TRUE

VẪN NGUY HIỂM TRONG PHP 8:
============================
  // usort với so sánh ngầm định
  $items = ["10", "9", "100", "1a"];
  sort($items);              // ["1a", "10", "100", "9"]
  // "1a" không phải numeric -> so sánh string lexicographic!

  // array_search trả về 0 (falsy!) khi tìm thấy ở vị trí đầu
  $pos = array_search("foo", $arr);  // Trả về 0 nếu ở index 0
  if (!$pos) { /* nghĩ không tìm thấy nhưng thực ra tìm thấy! */ }
```

### 5. Phát hiện trong mã nguồn

**Dấu hiệu nguy hiểm:**
- `sort()` hoặc `usort()` trên mảng mixed string/number
- `array_search()` kết quả không check `=== false`
- So sánh ID từ database (thường là string) với int literal

**Regex patterns (dùng với ripgrep):**
```bash
# Tìm array_search không check === false
rg --type php "array_search\s*\(" -A 2 | grep -v "=== false\|!== false"

# Tìm so sánh string với số literal
rg --type php "\"[0-9]+\"\s*[<>=!]+\s*[0-9]|[0-9]\s*[<>=!]+\s*\"[0-9]+" -n

# Tìm sort trên mảng có thể mixed
rg --type php "\bsort\s*\(\s*\\\$" -n

# Tìm strnatcmp/strnatcasecmp usage (natural sort)
rg --type php "strnat(case)?cmp\s*\(" -n
```

### 6. Giải pháp

| Tình huống | PHP 7 hành vi | PHP 8 hành vi | Giải pháp |
|-----------|-------------|-------------|---------|
| `0 == "foo"` | TRUE | FALSE | Dùng `===` |
| `"10" > "9"` | FALSE (string) | FALSE (string) | Dùng `(int)` cast |
| `sort(["10","9"])` | `["10","9"]` (string sort) | `["10","9"]` | Dùng `natsort()` |
| `array_search()` | Trả về 0/false | Trả về 0/false | Check `=== false` |

```php
<?php
declare(strict_types=1);

// ============================================================
// BAD - String number comparison bugs
// ============================================================

// Sắp xếp version numbers sai
$versions = ["1.10", "1.9", "1.2", "1.20"];
sort($versions);
// Kết quả: ["1.10", "1.2", "1.20", "1.9"] - SAI! (lexicographic)

// array_search trả về 0 -> falsy
$fruits = ["apple", "banana", "cherry"];
$pos = array_search("apple", $fruits);  // 0
if (!$pos) {
    echo "Không tìm thấy";  // SAI! Tìm thấy nhưng index = 0
}

// So sánh ID từ JSON (string) với int
$userId = json_decode($response)->user_id;  // "123" (string)
if ($userId == 123) {  // "123" == 123 -> TRUE (OK trong PHP 8)
    // Nhưng với loose comparison, vẫn dễ gây nhầm
}

// usort với so sánh không nhất quán
usort($items, function($a, $b) {
    return $a['priority'] - $b['priority'];  // Nếu là string -> sai
});

// ============================================================
// GOOD - Tường minh về kiểu khi so sánh
// ============================================================

// Natural sort cho version/số
$versions = ["1.10", "1.9", "1.2", "1.20"];
natsort($versions);
// Kết quả: ["1.2", "1.9", "1.10", "1.20"] - ĐÚNG!

// Sort số trong mảng string
$numbers = ["10", "9", "100", "2"];
usort($numbers, fn($a, $b) => (int)$a <=> (int)$b);
// Kết quả: ["2", "9", "10", "100"] - ĐÚNG!

// array_search - luôn check === false
$fruits = ["apple", "banana", "cherry"];
$pos = array_search("apple", $fruits);
if ($pos === false) {
    echo "Không tìm thấy";
} else {
    echo "Tìm thấy tại vị trí: $pos";  // 0
}

// Cast rõ ràng trước khi so sánh
$userId = (int) json_decode($response)->user_id;  // 123 (int)
if ($userId === 123) {  // Strict, rõ ràng
    // ...
}

// usort với spaceship operator và cast
usort($items, fn($a, $b) => (int)$a['priority'] <=> (int)$b['priority']);
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Luôn check `array_search()` kết quả với `=== false` (không phải `!`)
- [ ] Cast sang `int` hoặc `float` trước khi so sánh số từ JSON/DB
- [ ] Dùng `natsort()` hoặc `usort` với cast cho sắp xếp số
- [ ] Kiểm tra migration từ PHP 7 lên 8: tìm `==` với string/number
- [ ] Dùng `declare(strict_types=1)` để bắt nhiều lỗi type hơn

**PHPStan / Psalm rules:**
```bash
# Phát hiện comparison issues
vendor/bin/phpstan analyse --level=9 src/

# Tìm tất cả array_search không safe
rg --type php "array_search" -n -A 3 | grep -v "false"
```

---

## 7. Float Precision - MEDIUM

### 1. Tên
**Float Precision** (Độ Chính Xác Số Thực)

### 2. Phân loại
Kiểu Dữ Liệu / Arithmetic / Floating Point

### 3. Mức nghiêm trọng
🟡 **MEDIUM** - Số thực (float/double) không thể biểu diễn chính xác nhiều giá trị thập phân trong hệ nhị phân, dẫn đến sai số tích lũy trong tính toán tài chính và so sánh float bằng `==` cho kết quả sai.

### 4. Vấn đề
PHP float theo chuẩn IEEE 754 double precision. Nhiều số thập phân đơn giản như `0.1`, `0.2` không có biểu diễn chính xác trong hệ nhị phân. Kết quả: `0.1 + 0.2 !== 0.3` và tích lũy sai số trong vòng lặp.

```
VẤN ĐỀ IEEE 754 DOUBLE PRECISION
===================================

Trong bộ nhớ:
  0.1  ≈ 0.100000000000000005551115123...
  0.2  ≈ 0.200000000000000011102230246...
  0.3  ≈ 0.299999999999999988897769754...

  0.1 + 0.2 = 0.30000000000000004 (không phải 0.3!)

Hệ quả:
  if (0.1 + 0.2 == 0.3)  // FALSE! Bug kinh điển
  if (0.1 + 0.2 === 0.3) // FALSE!

  // Tích lũy sai số:
  $total = 0.0;
  for ($i = 0; $i < 10; $i++) {
      $total += 0.1;
  }
  var_dump($total == 1.0);  // FALSE!
  var_dump($total);         // float(0.9999999999999999)

TÌNH HUỐNG NGUY HIỂM:
=======================
  // Tính thuế VAT 10%
  $price    = 19.99;
  $vat      = $price * 0.1;   // 1.999 -> 1.9990000000000001
  $total    = $price + $vat;  // 21.989000000000001
  // Hiển thị: 21.99 (round) nhưng nội bộ: sai!
```

### 5. Phát hiện trong mã nguồn

**Dấu hiệu nguy hiểm:**
- So sánh float với `==` hoặc `===`
- Tính toán tài chính bằng float
- Dùng `round()` để "fix" kết quả float

**Regex patterns (dùng với ripgrep):**
```bash
# Tìm so sánh float với ==
rg --type php "[0-9]+\.[0-9]+\s*==\s*|==\s*[0-9]+\.[0-9]+" -n

# Tìm tính toán tài chính bằng float
rg --type php "\\\$(price|amount|total|tax|vat|fee)\s*[\+\-\*\/]=?\s*[0-9]" -n

# Tìm round() dùng để fix float
rg --type php "round\s*\(\s*\\\$(price|amount|total)" -n

# Tìm sprintf với số thập phân (có thể che giấu sai số)
rg --type php "sprintf\s*\(\s*['\"]%\.[0-9]+f" -n
```

### 6. Giải pháp

| Phương pháp | Khi nào | Độ chính xác |
|------------|---------|-------------|
| PHP float | Hiển thị gần đúng, không tài chính | ~15 chữ số thập phân |
| BCMath | Tài chính, cần chính xác tuyệt đối | Tùy ý |
| `brick/money` | Tiền tệ, đa tiền tệ | Chính xác tuyệt đối |
| Lưu int (cents) | Tiền tệ đơn giản | Chính xác tuyệt đối |

```php
<?php
declare(strict_types=1);

// ============================================================
// BAD - Float precision bugs
// ============================================================

// So sánh float - luôn sai
if (0.1 + 0.2 == 0.3) {          // FALSE!
    echo "Bằng nhau";
}

// Tính toán tài chính bằng float
$price    = 19.99;
$quantity = 3;
$total    = $price * $quantity;   // 59.97 - CÓ THỂ KHÔNG CHÍNH XÁC
$tax      = $total * 0.1;         // 5.997000...001
$final    = $total + $tax;        // 65.967000...001

// Round không giải quyết được vấn đề tích lũy
$sum = 0.0;
for ($i = 0; $i < 1000; $i++) {
    $sum += round(0.001 * 1.1, 10);  // Sai số vẫn tích lũy
}

// ============================================================
// GOOD - Dùng BCMath hoặc lưu int (cents)
// ============================================================

// OPTION 1: BCMath cho tính toán chính xác
$price    = '19.99';
$quantity = '3';
$total    = bcmul($price, $quantity, 2);   // "59.97"
$taxRate  = '0.10';
$tax      = bcmul($total, $taxRate, 2);    // "5.99" (không phải 6.00)
$final    = bcadd($total, $tax, 2);        // "65.96"

// OPTION 2: Lưu int (cents/yen/xu) trong DB
$priceYen = 1999;           // int: 19.99 JPY * 100
$quantity  = 3;
$total     = $priceYen * $quantity;        // 5997 int - chính xác tuyệt đối
$tax       = (int) round($total * 0.1);   // 599 (round một lần duy nhất)
$final     = $total + $tax;               // 6596 - chính xác

// OPTION 3: brick/money (khuyến nghị nhất)
use Brick\Money\Money;
$price  = Money::ofMinor(1999, 'JPY');    // 19.99 JPY
$total  = $price->multipliedBy(3);        // 59.97 JPY, exact
$tax    = $total->multipliedBy('0.1', \Brick\Math\RoundingMode::HALF_UP);
$final  = $total->plus($tax);

// So sánh float đúng cách (khi cần)
$epsilon = 1e-9;
if (abs((0.1 + 0.2) - 0.3) < $epsilon) {
    echo "Gần bằng nhau";   // TRUE - dùng epsilon comparison
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Không bao giờ so sánh float với `==` hoặc `===`
- [ ] Tất cả giá trị tiền tệ lưu dưới dạng int (cents) hoặc BCMath string
- [ ] Dùng `brick/money` cho logic tài chính phức tạp
- [ ] Chỉ round/format float khi hiển thị, không dùng trong tính toán nội bộ
- [ ] Kiểm tra tích lũy sai số trong vòng lặp tài chính

**PHPStan / Psalm rules:**
```yaml
# Psalm strict-mode giúp detect float comparison
# phpstan.neon - custom rule cho float comparison
parameters:
  level: 8
```

```bash
# Tìm mọi so sánh float
rg --type php "[0-9]+\.[0-9]+\s*(==|===|!=|!==)" -n
rg --type php "(==|===|!=|!==)\s*[0-9]+\.[0-9]+" -n
```

---

## 8. Strict Types Thiếu (Missing declare strict_types) - HIGH

### 1. Tên
**Strict Types Thiếu** (Missing `declare(strict_types=1)`)

### 2. Phân loại
Kiểu Dữ Liệu / Type System / Configuration

### 3. Mức nghiêm trọng
🟠 **HIGH** - Thiếu `declare(strict_types=1)` khiến PHP tự động coerce kiểu khi gọi hàm có type hints, dẫn đến hành vi không mong đợi: string "123abc" được chấp nhận như int 123, float 1.9 bị truncate thành int 1.

### 4. Vấn đề
Khi không có `declare(strict_types=1)`, PHP dùng "coercive mode" cho scalar type hints: tự động ép kiểu thay vì báo lỗi. `"123abc"` passed như `int` sẽ là `123` (phần số đầu). `1.9` passed như `int` sẽ là `1`. File có `declare` chỉ ảnh hưởng đến các lời gọi hàm TRONG file đó - không ảnh hưởng file khác.

```
STRICT_TYPES SCOPE
===================

File A (KHÔNG có declare):          File B (có declare):
  function add(int $a, int $b) {}     declare(strict_types=1);

  // Gọi từ File A (không có declare):
  add("1", "2");   // OK! PHP coerce -> 1, 2
  add(1.9, 2.1);   // OK! PHP coerce -> 1, 2 (truncate!)
  add("1abc", 2);  // OK! PHP coerce -> 1, 2 (cắt "abc")

  // Gọi từ File B (có declare):
  add("1", "2");   // TypeError!
  add(1.9, 2.1);   // TypeError!
  add("1abc", 2);  // TypeError!

  // QUAN TRỌNG: strict_types ảnh hưởng nơi GỌI, không nơi ĐỊNH NGHĨA!

VÍ DỤ BUG THỰC TẾ:
====================
  function setAge(int $age): void {
      $this->age = $age;
  }

  // File không có strict_types:
  $form->setAge($_POST['age']);     // "25abc" -> 25 (mất "abc", silent!)
  $form->setAge("0");              // "0" -> 0 (OK)
  $form->setAge(25.9);            // 25.9 -> 25 (mất .9, silent!)
  $form->setAge("not a number");  // "not a number" -> TypeError (vì không phải numeric string)
```

### 5. Phát hiện trong mã nguồn

**Dấu hiệu nguy hiểm:**
- File PHP thiếu `declare(strict_types=1)` ở dòng đầu
- Type hints có trong function nhưng input từ user không được validate

**Regex patterns (dùng với ripgrep):**
```bash
# Tìm file PHP KHÔNG có declare strict_types
# Liệt kê tất cả file PHP
rg --type php --files | while read f; do
  grep -qL "declare(strict_types=1)" "$f" && echo "MISSING: $f"
done

# Hoặc dùng ripgrep để tìm file CÓ declare
rg --type php -l "declare\s*\(\s*strict_types\s*=\s*1\s*\)"

# Tìm function có type hints nhưng gọi với request input
rg --type php "function\s+\w+\s*\(\s*(int|float|bool)\s+\\\$" -n
```

### 6. Giải pháp

| Tình huống | Không có strict_types | Có strict_types | Kết quả |
|-----------|----------------------|----------------|---------|
| `func(int $x)` với `"123"` | Chấp nhận (123) | TypeError | strict: đúng |
| `func(int $x)` với `"123abc"` | Chấp nhận (123) | TypeError | strict: đúng |
| `func(int $x)` với `1.9` | Chấp nhận (1) | TypeError | strict: đúng |
| `func(string $x)` với `123` | Chấp nhận ("123") | TypeError | Tùy ngữ cảnh |

```php
<?php
declare(strict_types=1);  // PHẢI là dòng đầu tiên (sau <?php)

// ============================================================
// BAD - Thiếu declare, type hint bị bypass
// ============================================================
// (file không có declare(strict_types=1))

function calculateDiscount(int $price, float $rate): float
{
    return $price * $rate;
}

// PHP silently coerce:
calculateDiscount("100abc", "0.1xyz");  // 100 * 0.1 = 10.0 (sai im lặng!)
calculateDiscount(99.9, 0.15);          // 99 * 0.15 = 14.85 (mất .9!)

// ============================================================
// GOOD - Có declare, PHP báo lỗi ngay
// ============================================================

// File BẮT BUỘC bắt đầu bằng:
// <?php
// declare(strict_types=1);

function calculateDiscount(int $price, float $rate): float
{
    return $price * $rate;
}

// Bây giờ PHP ném TypeError:
calculateDiscount("100abc", 0.1);  // TypeError!
calculateDiscount(99.9, 0.15);     // TypeError!

// Phải truyền đúng kiểu:
calculateDiscount(100, 0.1);       // 10.0 - OK
calculateDiscount((int) $price, (float) $rate);  // Cast tường minh

// Với input từ user - validate và cast trước:
function processOrder(array $data): void
{
    $price = filter_var($data['price'], FILTER_VALIDATE_INT);
    if ($price === false) {
        throw new \InvalidArgumentException('price phải là số nguyên');
    }
    $discount = filter_var($data['discount_rate'], FILTER_VALIDATE_FLOAT);
    if ($discount === false) {
        throw new \InvalidArgumentException('discount_rate phải là số thực');
    }
    $result = calculateDiscount($price, $discount);  // An toàn
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Mọi file PHP mới đều có `declare(strict_types=1)` ở dòng đầu
- [ ] Chạy script để tìm file thiếu declare trong CI/CD
- [ ] Không bao giờ truyền raw `$_POST`/`$_GET` trực tiếp vào function có type hints
- [ ] Dùng PHPStan level 8+ để phát hiện type mismatch

**PHPStan / Psalm rules:**
```yaml
# phpstan.neon - enforce strict types
parameters:
  level: 8
  strictRules:
    strictCalls: true
```

```bash
# Script kiểm tra file thiếu strict_types
find src/ -name "*.php" -exec grep -L "declare(strict_types=1)" {} \;

# Hoặc với ripgrep (nhanh hơn)
comm -23 \
  <(rg --type php --files src/ | sort) \
  <(rg --type php -l "declare\s*\(\s*strict_types\s*=\s*1\s*\)" src/ | sort)
```

---

## 9. Enum String Cast - MEDIUM

### 1. Tên
**Enum String Cast** (Ép Kiểu Enum Sang Chuỗi)

### 2. Phân loại
Kiểu Dữ Liệu / Enum / PHP 8.1

### 3. Mức nghiêm trọng
🟡 **MEDIUM** - Enum thuần (Pure Enum) trong PHP 8.1 không thể cast sang string hay int, dẫn đến `Error` runtime khi cố dùng trong context cần string (interpolation, concatenation, echo). Backed Enum có `->value` nhưng thường bị quên.

### 4. Vấn đề
PHP 8.1 có hai loại enum: Pure Enum (không có type) và Backed Enum (có `string` hoặc `int`). Pure Enum không có `->value` và không thể dùng trong string context. Backed Enum có `->value` nhưng vẫn không tự cast sang string trong interpolation.

```
ENUM TYPES TRONG PHP 8.1
==========================

Pure Enum:              Backed Enum:
  enum Status {           enum Status: string {
      case Active;            case Active = 'active';
      case Inactive;          case Inactive = 'inactive';
  }                       }

  $s = Status::Active;    $s = Status::Active;
  echo $s;        // Error!    echo $s;        // Error! (vẫn cần ->value)
  echo $s->name;  // "Active"  echo $s->name;  // "Active"
  // $s->value   // Error!     echo $s->value; // "active" - OK!
  (string) $s;   // Error!     (string) $s;    // Error! (không tự cast)

BUG THỰC TẾ PHỔ BIẾN:
========================
  $status = UserStatus::Active;

  // Lưu vào DB - KHÔNG ĐÚNG với Pure Enum
  DB::table('users')->update(['status' => $status]); // Error hoặc object!

  // String interpolation
  $msg = "Trạng thái: $status";    // Error!
  $msg = "Trạng thái: {$status}";  // Error!

  // JSON encode
  json_encode(['status' => $status]); // {"status": {}} - không phải string!
```

### 5. Phát hiện trong mã nguồn

**Dấu hiệu nguy hiểm:**
- Dùng Pure Enum trong DB query, JSON, string interpolation
- Không dùng `->value` khi lấy giá trị từ Backed Enum
- Dùng `(string)` cast trên Enum

**Regex patterns (dùng với ripgrep):**
```bash
# Tìm enum cases dùng trực tiếp trong DB query
rg --type php "DB::|->update\(|->insert\(" -A 5 | grep "::Active\|::Inactive\|::Pending"

# Tìm enum trong json_encode
rg --type php "json_encode\s*\(\[" -A 3 | grep "::[A-Z]"

# Tìm Pure Enum definitions
rg --type php "^enum\s+\w+\s*\{" -n

# Tìm Backed Enum definitions
rg --type php "^enum\s+\w+\s*:\s*(string|int)\s*\{" -n
```

### 6. Giải pháp

| Tình huống | Pure Enum | Backed Enum |
|-----------|----------|------------|
| Lấy tên | `->name` ("Active") | `->name` ("Active") |
| Lấy giá trị | Không có | `->value` ("active") |
| Lưu DB | `->name` hoặc dùng Backed | `->value` |
| JSON | Cần custom, hoặc `->name` | `->value` |
| So sánh | `=== Status::Active` | `=== Status::Active` |
| Tạo từ string | `Status::from('Active')` (name) | `Status::from('active')` (value) |

```php
<?php
declare(strict_types=1);

// ============================================================
// BAD - Enum cast errors
// ============================================================

enum OrderStatus {
    case Pending;
    case Processing;
    case Completed;
}

$status = OrderStatus::Pending;

// Lỗi: Pure Enum không có value
echo $status;                              // Fatal Error!
echo "Status: $status";                    // Fatal Error!
(string) $status;                          // Fatal Error!
DB::table('orders')->where('status', $status)->get();  // Lỗi/sai!

// Backed Enum nhưng quên ->value
enum PaymentStatus: string {
    case Pending  = 'pending';
    case Paid     = 'paid';
}

$ps = PaymentStatus::Pending;
json_encode(['payment' => $ps]);           // {"payment": {}} - SAI!
DB::table('t')->insert(['status' => $ps]); // Error hoặc object!

// ============================================================
// GOOD - Đúng cách dùng Enum
// ============================================================

// Luôn dùng Backed Enum khi cần lưu DB hoặc serialize
enum OrderStatus: string
{
    case Pending    = 'pending';
    case Processing = 'processing';
    case Completed  = 'completed';

    // Helper: label hiển thị tiếng Việt
    public function label(): string
    {
        return match($this) {
            self::Pending    => 'Chờ xử lý',
            self::Processing => 'Đang xử lý',
            self::Completed  => 'Hoàn thành',
        };
    }
}

$status = OrderStatus::Pending;

// Lấy value để lưu DB, JSON
echo $status->value;                        // "pending" - OK
echo "Status: {$status->value}";            // "Status: pending" - OK

// Lưu DB với ->value
DB::table('orders')->insert([
    'status' => $status->value,             // "pending" - OK
]);

// JSON serialize - implement JsonSerializable
final class Order implements \JsonSerializable
{
    public function __construct(
        public readonly OrderStatus $status,
    ) {}

    public function jsonSerialize(): mixed
    {
        return [
            'status' => $this->status->value,  // Tường minh
        ];
    }
}

// Tạo Enum từ string (safe)
$fromDb = 'pending';
$status = OrderStatus::from($fromDb);          // OrderStatus::Pending - OK
$safe   = OrderStatus::tryFrom('unknown');     // null (không throw)
if ($safe === null) {
    throw new \UnexpectedValueException("Status không hợp lệ: $fromDb");
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Luôn dùng Backed Enum (`enum X: string`) khi cần lưu DB hoặc serialize
- [ ] Luôn dùng `->value` khi lấy giá trị từ Backed Enum
- [ ] Implement `JsonSerializable` cho class chứa Enum
- [ ] Dùng `tryFrom()` thay `from()` khi input từ user/DB (để handle invalid value)
- [ ] Thêm PHPStan để phát hiện Enum dùng sai context

**PHPStan / Psalm rules:**
```bash
# PHPStan với level 8 phát hiện enum type errors
vendor/bin/phpstan analyse --level=8 src/

# Psalm - strict enum checking
vendor/bin/psalm --strict-types src/
```

---

## 10. Union Type Narrowing - MEDIUM

### 1. Tên
**Union Type Narrowing** (Thu Hẹp Kiểu Union Không Đúng)

### 2. Phân loại
Kiểu Dữ Liệu / Union Types / PHP 8.0

### 3. Mức nghiêm trọng
🟡 **MEDIUM** - Không thu hẹp (narrow) union type trước khi sử dụng dẫn đến gọi method không tồn tại, lỗi runtime `TypeError`, hoặc PHPStan/IDE không thể infer đúng kiểu.

### 4. Vấn đề
PHP 8.0 hỗ trợ Union Types (`int|string`, `User|null`). Khi nhận union type, code phải kiểm tra kiểu thực tế trước khi dùng method/property chỉ có ở một kiểu cụ thể. Không làm điều này dẫn đến lỗi runtime hoặc static analysis sai.

```
UNION TYPE NARROWING
=====================

function process(int|string $value): string
{
    // $value có thể là int HOẶC string
    // Nếu gọi $value->toUpperCase() -> Error (int không có method)

    // Phải narrow trước:
    if (is_string($value)) {
        // Ở đây PHPStan biết $value là string
        return strtoupper($value);
    }
    return (string) $value;
}

CÁC PHÉP NARROW TYPE TRONG PHP:
==================================
  is_string($x)   -> PHP + PHPStan biết $x là string
  is_int($x)      -> biết $x là int
  is_array($x)    -> biết $x là array
  is_null($x)     -> biết $x là null
  $x instanceof Foo -> biết $x là Foo
  match(true) { ... } -> narrowing trong từng branch
  assert(is_string($x)) -> narrow sau assert
```

### 5. Phát hiện trong mã nguồn

**Dấu hiệu nguy hiểm:**
- Hàm nhận `int|string` nhưng gọi method string trực tiếp
- `?User` (nullable) dùng `->id` mà không check null
- Union type nhưng không có `instanceof`/`is_*` check

**Regex patterns (dùng với ripgrep):**
```bash
# Tìm nullable không được check
rg --type php "\\\?\w+\s+\\\$\w+" -n | head -20

# Tìm hàm nhận union type
rg --type php "function\s+\w+\s*\([^)]*\|[^)]*\)" -n

# Tìm dùng ->method() trên nullable (pattern đơn giản)
rg --type php "\\\$\w+\?->" -n

# Tìm truy cập property không check null
rg --type php "\\\$(user|order|item)\->id" -n
```

### 6. Giải pháp

| Kỹ thuật narrow | Dùng khi | PHPStan hỗ trợ |
|----------------|---------|---------------|
| `is_string($x)` | Primitive types | Có |
| `is_int($x)` | Primitive types | Có |
| `$x instanceof Foo` | Objects | Có |
| `is_null($x)` / `=== null` | Nullable | Có |
| `match(true)` | Multiple types | Có |
| `assert(is_string($x))` | Debug/test | Có |
| PHPDoc `@var string $x` | Bypass static analysis | Có (cẩn thận) |

```php
<?php
declare(strict_types=1);

// ============================================================
// BAD - Dùng union type không narrow
// ============================================================

function formatId(int|string $id): string
{
    return strtoupper($id);  // Error nếu $id là int! strtoupper() cần string
}

function getUser(?User $user): string
{
    return $user->name;  // Error nếu $user là null!
}

function processValue(array|string $data): int
{
    return strlen($data);  // Error nếu $data là array!
}

// ============================================================
// GOOD - Narrow type trước khi dùng
// ============================================================

function formatId(int|string $id): string
{
    if (is_int($id)) {
        return sprintf('ID-%05d', $id);  // "ID-00123"
    }
    return strtoupper($id);  // PHPStan biết $id là string ở đây
}

// Nullable: kiểm tra null trước
function getUserName(?User $user): string
{
    if ($user === null) {
        return 'Guest';
    }
    return $user->name;  // PHPStan biết $user là User ở đây
}

// Null safe operator PHP 8.0
function getUserEmail(?User $user): ?string
{
    return $user?->email;  // null nếu $user là null, không Error
}

// match với type narrowing
function describe(int|string|array $value): string
{
    return match(true) {
        is_int($value)    => "Số nguyên: $value",
        is_string($value) => "Chuỗi: $value",
        is_array($value)  => "Mảng có " . count($value) . " phần tử",
    };
}

// instanceof narrowing
function render(Button|Input|Select $component): string
{
    if ($component instanceof Button) {
        return "<button>{$component->label}</button>";
    }
    if ($component instanceof Input) {
        return "<input type='{$component->type}' />";
    }
    return "<select>{$component->renderOptions()}</select>";
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Luôn narrow union type trước khi gọi method/property
- [ ] Dùng null safe operator `?->` cho nullable objects
- [ ] Cài PHPStan level 8 để phát hiện narrowing issues
- [ ] Ưu tiên specific type hơn union khi có thể

**PHPStan / Psalm rules:**
```bash
vendor/bin/phpstan analyse --level=8 src/
# PHPStan phát hiện: "Cannot call method X on int|string"
# và "Cannot access property on null"
```

---

## 11. Mixed Type Abuse - HIGH

### 1. Tên
**Mixed Type Abuse** (Lạm Dụng Kiểu Mixed)

### 2. Phân loại
Kiểu Dữ Liệu / Type System / Code Quality

### 3. Mức nghiêm trọng
🟠 **HIGH** - Lạm dụng `mixed` type vô hiệu hóa hoàn toàn static type checking, che giấu bug tiềm ẩn, làm giảm khả năng refactor an toàn và IDE support. Đặc biệt nguy hiểm khi `mixed` xuất hiện trong return type của hàm business logic.

### 4. Vấn đề
`mixed` là kiểu thoát (escape hatch) trong PHP 8.0, tương đương "bất kỳ kiểu nào". Khi dùng `mixed` cho param/return type, toàn bộ type safety bị vô hiệu. PHPStan/Psalm không thể phân tích tiếp, IDE không thể autocomplete. `mixed` chỉ nên dùng trong các trường hợp thực sự cần thiết (serialization, generic utilities).

```
PHÂN TÍCH MIXED TYPE PROPAGATION
===================================

function getValue(): mixed {   // "mixed" = bỏ type safety
    return $this->data;
}

$val = getValue();             // PHPStan: $val is mixed
$val->process();               // PHPStan: OK! (bỏ qua check)
                               // Runtime: Error nếu $val là int!

CHUỖI PROPAGATION:
==================
  mixed -> mixed -> mixed -> ...
  Một hàm trả về mixed "lây nhiễm" sang các hàm dùng nó

  function getConfig(): mixed { ... }           // mixed
  function applyConfig(mixed $c): void { ... }  // mixed vào
  $cfg = getConfig();                           // mixed
  applyConfig($cfg);                            // mixed truyền đi

  // Toàn bộ chain mất type safety!
```

### 5. Phát hiện trong mã nguồn

**Dấu hiệu nguy hiểm:**
- Hàm business logic có return type `mixed`
- Param type `mixed` trong hàm non-generic
- PHPDoc `@return mixed` trên nhiều hàm

**Regex patterns (dùng với ripgrep):**
```bash
# Tìm function trả về mixed
rg --type php "function\s+\w+[^:]*:\s*mixed" -n

# Tìm param mixed
rg --type php "function\s+\w+\s*\([^)]*mixed\s+\\\$" -n

# Tìm @return mixed trong docblock
rg --type php "@return\s+mixed" -n

# Tìm @var mixed
rg --type php "@var\s+mixed" -n
```

### 6. Giải pháp

| Thay thế `mixed` | Khi nào dùng |
|-----------------|-------------|
| Specific type `int\|string` | Biết rõ các kiểu có thể |
| Generic với template | Collections, containers |
| Interface/abstract | Nhóm các implementation |
| `never` | Hàm luôn throw/exit |
| `mixed` hợp lệ | `json_decode`, `var_export`, serialization |

```php
<?php
declare(strict_types=1);

// ============================================================
// BAD - Mixed type abuse
// ============================================================

class ConfigManager
{
    private mixed $data = [];  // mixed - mất type safety

    public function get(string $key): mixed  // mixed return - nguy hiểm
    {
        return $this->data[$key] ?? null;
    }

    public function set(string $key, mixed $value): void  // mixed param
    {
        $this->data[$key] = $value;
    }
}

// Caller không biết phải xử lý kiểu gì
$timeout = $config->get('timeout');  // mixed
$timeout + 1;  // Có thể Error nếu null hoặc string!

// ============================================================
// GOOD - Specific types
// ============================================================

class ConfigManager
{
    /** @var array<string, int|string|bool|array<mixed>> */
    private array $data = [];

    public function getString(string $key, string $default = ''): string
    {
        $value = $this->data[$key] ?? $default;
        if (!is_string($value)) {
            throw new \RuntimeException("Config '$key' phải là string");
        }
        return $value;
    }

    public function getInt(string $key, int $default = 0): int
    {
        $value = $this->data[$key] ?? $default;
        if (!is_int($value)) {
            throw new \RuntimeException("Config '$key' phải là int");
        }
        return $value;
    }

    public function getBool(string $key, bool $default = false): bool
    {
        $value = $this->data[$key] ?? $default;
        if (!is_bool($value)) {
            throw new \RuntimeException("Config '$key' phải là bool");
        }
        return $value;
    }
}

// Caller biết chính xác kiểu nhận được
$timeout = $config->getInt('timeout', 30);  // int
$timeout + 1;  // Chắc chắn OK!

// Khi thực sự cần mixed (JSON decode, serialize):
/**
 * @return array<string, mixed>
 */
function parseJson(string $json): array
{
    $data = json_decode($json, true);
    if (!is_array($data)) {
        throw new \JsonException('Invalid JSON object');
    }
    return $data;  // Đây là trường hợp hợp lệ cho mixed bên trong
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Không dùng `mixed` trong business logic code
- [ ] Replace `mixed` bằng union type cụ thể hoặc interface
- [ ] Chỉ dùng `mixed` ở boundary (JSON decode, ORM result, serialization)
- [ ] Bật PHPStan level 9 để phát hiện mixed propagation
- [ ] Dùng generics/templates khi có thể (`@template T`)

**PHPStan / Psalm rules:**
```yaml
# phpstan.neon - cấm mixed
parameters:
  level: 9
  # Level 9 - checkMissingIterableValueType, checkGenericClassInNonGenericObjectType
  reportUnmatchedIgnoredErrors: true
```

---

## 12. Array Spread Gotcha - MEDIUM

### 1. Tên
**Array Spread Gotcha** (Bẫy Toán Tử Spread Mảng)

### 2. Phân loại
Kiểu Dữ Liệu / Array / PHP 8.1

### 3. Mức nghiêm trọng
🟡 **MEDIUM** - Toán tử spread (`...`) có hành vi khác nhau giữa PHP 7.4 (chỉ int key), PHP 8.0, và PHP 8.1 (hỗ trợ string key). Dùng sai có thể mất data hoặc gây lỗi "Cannot unpack array with string keys".

### 4. Vấn đề
PHP 7.4 cho phép spread (`...`) với mảng có int key. PHP 8.1 thêm hỗ trợ string key. Khi spread mảng associative trong PHP < 8.1 sẽ gây lỗi. Ngoài ra, spread không merge deep, chỉ merge shallow (tầng 1).

```
ARRAY SPREAD BEHAVIOR
======================

PHP 7.4:
  [...[1, 2], ...[3, 4]]          // OK: [1, 2, 3, 4]
  [...['a' => 1], ...['b' => 2]]  // Error! String keys không hỗ trợ

PHP 8.1+:
  [...['a' => 1], ...['b' => 2]]  // OK: ['a' => 1, 'b' => 2]
  [...['a' => 1], ...['a' => 2]]  // OK: ['a' => 2] (ghi đè)

SHALLOW MERGE - NGUY HIỂM:
============================
  $default = ['db' => ['host' => 'localhost', 'port' => 3306]];
  $override = ['db' => ['host' => 'production.db']];

  $config = [...$default, ...$override];
  // Kết quả: ['db' => ['host' => 'production.db']]
  // MẤT 'port' => 3306! Không phải deep merge!

  // Đúng: array_replace_recursive
  $config = array_replace_recursive($default, $override);
  // Kết quả: ['db' => ['host' => 'production.db', 'port' => 3306]]
```

### 5. Phát hiện trong mã nguồn

**Dấu hiệu nguy hiểm:**
- Spread mảng associative trên PHP < 8.1
- Dùng spread để merge config/settings nhiều tầng
- Dùng spread khi cần deep merge

**Regex patterns (dùng với ripgrep):**
```bash
# Tìm array spread
rg --type php "\.\.\.\\\$\w+" -n
rg --type php "\.\.\.\[" -n

# Tìm spread dùng để merge (shallow)
rg --type php "\[.*\.\.\.\\\$\w+.*,.*\.\.\.\\\$\w+" -n
```

### 6. Giải pháp

| Tình huống | PHP 7.4 | PHP 8.1+ | Giải pháp |
|-----------|---------|---------|---------|
| Merge int-keyed | Spread OK | Spread OK | `[...$a, ...$b]` |
| Merge string-keyed | Error! | Spread OK | `array_merge()` hoặc PHP 8.1 spread |
| Deep merge | Spread sai | Spread sai | `array_replace_recursive()` |
| Append element | `[...$arr, $new]` | OK | OK |

```php
<?php
declare(strict_types=1);

// ============================================================
// BAD - Array spread gotchas
// ============================================================

// PHP 7.4: Error với string key
$defaults = ['timeout' => 30, 'retry' => 3];
$overrides = ['timeout' => 60];
$config = [...$defaults, ...$overrides];  // Error trong PHP 7.4!

// Shallow merge - mất nested data
$defaultConfig = [
    'database' => ['host' => 'localhost', 'port' => 5432, 'name' => 'app'],
];
$envConfig = [
    'database' => ['host' => 'prod.server.com'],
];
$merged = [...$defaultConfig, ...$envConfig];
// Kết quả: ['database' => ['host' => 'prod.server.com']]
// MẤT: port => 5432 và name => 'app'!

// ============================================================
// GOOD - Dùng đúng hàm cho từng tình huống
// ============================================================

// Shallow merge string-keyed (PHP 8.1+ hoặc dùng array_merge)
$defaults = ['timeout' => 30, 'retry' => 3];
$overrides = ['timeout' => 60];

// PHP 8.1+
$config = [...$defaults, ...$overrides];  // ['timeout' => 60, 'retry' => 3]

// Tương thích PHP 7.4+
$config = array_merge($defaults, $overrides);  // Tương tự

// Deep merge - luôn dùng array_replace_recursive
$defaultConfig = [
    'database' => ['host' => 'localhost', 'port' => 5432, 'name' => 'app'],
    'cache'    => ['driver' => 'redis', 'ttl' => 3600],
];
$envConfig = [
    'database' => ['host' => 'prod.server.com'],
];
$merged = array_replace_recursive($defaultConfig, $envConfig);
// Kết quả: ['database' => ['host' => 'prod.server.com', 'port' => 5432, 'name' => 'app'], ...]
// ĐÚNG: giữ lại port và name!

// Spread hợp lệ - thêm phần tử vào mảng
$items = [1, 2, 3];
$newItems = [...$items, 4, 5];  // [1, 2, 3, 4, 5] - OK

// Spread function arguments
function sum(int ...$nums): int
{
    return array_sum($nums);
}
$numbers = [1, 2, 3, 4];
sum(...$numbers);  // 10 - OK
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Kiểm tra PHP version khi dùng spread với string-keyed arrays
- [ ] Dùng `array_replace_recursive()` cho deep merge, không phải spread
- [ ] Test rõ ràng hành vi merge trước khi dùng trong config/settings
- [ ] Thêm PHPStan check cho PHP version compatibility

**PHPStan / Psalm rules:**
```bash
# PHPStan với PHP version target
vendor/bin/phpstan analyse --level=8 --php-version=7.4 src/
# Sẽ báo lỗi string key spread trong PHP 7.4 mode
```

---

## 13. Readonly Property Clone - MEDIUM

### 1. Tên
**Readonly Property Clone** (Clone Object Có Readonly Properties)

### 2. Phân loại
Kiểu Dữ Liệu / PHP 8.1 / Object Cloning

### 3. Mức nghiêm trọng
🟡 **MEDIUM** - Không thể gán lại `readonly` property sau khi khởi tạo, kể cả trong `__clone()`. PHP 8.3 thêm `clone with` syntax nhưng PHP 8.1/8.2 không có giải pháp native thanh lịch, dẫn đến code workaround phức tạp.

### 4. Vấn đề
`readonly` properties PHP 8.1 chỉ có thể gán một lần (trong constructor). `clone` tạo shallow copy của object nhưng không thể tái gán `readonly` properties trong `__clone()`. Điều này gây khó khăn khi cần "clone with changes" pattern (immutable objects).

```
READONLY + CLONE VẤN ĐỀ
=========================

class User {
    public function __construct(
        public readonly int    $id,
        public readonly string $name,
        public readonly string $email,
    ) {}
}

$user = new User(1, "Nguyen Van A", "a@example.com");

// KHÔNG thể clone với thay đổi:
$updated = clone $user;
$updated->name = "Nguyen Van B";  // Fatal Error! Cannot modify readonly

// __clone() cũng không giúp được:
public function __clone() {
    $this->name = "new name";  // Fatal Error trong PHP 8.1/8.2!
}

PHP 8.3 GIẢI PHÁP:
===================
  // PHP 8.3: clone with expression
  $updated = clone $user with { name: "Nguyen Van B" };
  // $updated->id    = 1          (giữ nguyên)
  // $updated->name  = "Nguyen Van B"  (thay đổi)
  // $updated->email = "a@example.com" (giữ nguyên)
```

### 5. Phát hiện trong mã nguồn

**Dấu hiệu nguy hiểm:**
- Class có `readonly` properties cần tạo modified copy
- `clone` object có `readonly` rồi gán property
- `__clone()` cố gán readonly

**Regex patterns (dùng với ripgrep):**
```bash
# Tìm class có readonly properties
rg --type php "public readonly\s+\w+" -n

# Tìm clone object
rg --type php "\bclone\b\s+\\\$\w+" -n

# Tìm assign sau clone (potential error)
rg --type php "clone\s+\\\$\w+.*;\s*\n.*->\w+\s*=" -n
```

### 6. Giải pháp

| PHP Version | Giải pháp | Ghi chú |
|------------|---------|---------|
| PHP 8.3+ | `clone $obj with { prop: val }` | Native, tốt nhất |
| PHP 8.1/8.2 | `new static(...)` với reflection | Workaround |
| PHP 8.1/8.2 | `with()` method pattern | Phổ biến nhất |
| PHP 8.1/8.2 | Bỏ `readonly`, dùng private setter | Compromise |

```php
<?php
declare(strict_types=1);

// ============================================================
// BAD - Clone với readonly (PHP 8.1/8.2)
// ============================================================

class UserProfile
{
    public function __construct(
        public readonly int    $id,
        public readonly string $name,
        public readonly string $email,
    ) {}
}

$profile = new UserProfile(1, "Nam", "nam@example.com");
$updated = clone $profile;
$updated->name = "Lan";  // Fatal Error! Cannot modify readonly property

// ============================================================
// GOOD OPTION 1: with() method pattern (PHP 8.1/8.2)
// ============================================================

final class UserProfile
{
    public function __construct(
        public readonly int    $id,
        public readonly string $name,
        public readonly string $email,
    ) {}

    public function withName(string $name): self
    {
        return new self(
            id:    $this->id,
            name:  $name,        // Thay đổi
            email: $this->email, // Giữ nguyên
        );
    }

    public function withEmail(string $email): self
    {
        return new self(
            id:    $this->id,
            name:  $this->name,
            email: $email,
        );
    }
}

$profile = new UserProfile(1, "Nam", "nam@example.com");
$updated = $profile->withName("Lan");  // Tạo instance mới

// ============================================================
// GOOD OPTION 2: PHP 8.3 clone with
// ============================================================

// PHP 8.3+
$updated = clone $profile with { name: "Lan" };
// $updated->id    = 1 (copied)
// $updated->name  = "Lan" (new)
// $updated->email = "nam@example.com" (copied)

// ============================================================
// GOOD OPTION 3: Reflection (phức tạp, ít dùng)
// ============================================================

function cloneWith(object $obj, array $changes): object
{
    $clone = clone $obj;
    $reflection = new \ReflectionClass($clone);
    foreach ($changes as $property => $value) {
        $prop = $reflection->getProperty($property);
        $prop->setValue($clone, $value);  // Bypass readonly qua reflection
    }
    return $clone;
}

$updated = cloneWith($profile, ['name' => 'Lan']);
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Cân nhắc `with()` method pattern cho immutable value objects
- [ ] Upgrade lên PHP 8.3 để dùng `clone with` syntax
- [ ] Không dùng `__clone()` để modify readonly properties
- [ ] Document rõ ràng các class là immutable

**PHPStan / Psalm rules:**
```bash
# PHPStan phát hiện readonly modification
vendor/bin/phpstan analyse --level=8 src/
# "Cannot assign to readonly property X::$name"
```

---

## 14. Fiber State Confusion - HIGH

### 1. Tên
**Fiber State Confusion** (Nhầm Lẫn Trạng Thái Fiber)

### 2. Phân loại
Kiểu Dữ Liệu / PHP 8.1 / Concurrency

### 3. Mức nghiêm trọng
🟠 **HIGH** - Không kiểm tra trạng thái Fiber trước khi gọi `resume()`/`getReturn()` dẫn đến `FiberError` runtime trong các ứng dụng async/event-driven, đặc biệt khó debug vì lỗi xảy ra không đồng bộ.

### 4. Vấn đề
PHP 8.1 Fibers là coroutines nhẹ hỗ trợ suspend/resume. Fiber có 4 trạng thái: `created`, `running`, `suspended`, `terminated`. Gọi `resume()` khi Fiber không ở trạng thái `suspended`, hoặc `getReturn()` khi chưa `terminated` đều throw `FiberError`. Trong event loop, trạng thái có thể thay đổi không đồng bộ.

```
FIBER STATE MACHINE
====================

  [Created] ──start()──> [Running]
                              │
                         suspend()
                              │
                              v
  [Terminated] <──────── [Suspended]
      ^                       │
      │                  resume()
      │                       │
      └──── (tự kết thúc) ────┘

TRẠNG THÁI VÀ METHODS HỢP LỆ:
================================
  Trạng thái    start()   resume()  getReturn()  isTerminated()
  -----------   -------   --------  -----------  --------------
  created       OK        Error!    Error!        false
  running       Error!    Error!    Error!        false
  suspended     Error!    OK        Error!        false
  terminated    Error!    Error!    OK            true

BUG THỰC TẾ:
=============
  $fiber = new Fiber(function() { Fiber::suspend(); });
  $fiber->start();        // Fiber suspend, chờ resume

  // Sau đó trong event handler - KHÔNG BIẾT Fiber đã terminate chưa:
  $fiber->resume($data);  // Có thể FiberError nếu đã terminate!
  $value = $fiber->getReturn();  // FiberError nếu chưa terminate!
```

### 5. Phát hiện trong mã nguồn

**Dấu hiệu nguy hiểm:**
- `resume()` không kiểm tra `isSuspended()` trước
- `getReturn()` không kiểm tra `isTerminated()` trước
- Fiber dùng trong event loop mà không track state

**Regex patterns (dùng với ripgrep):**
```bash
# Tìm Fiber usage
rg --type php "new\s+Fiber\s*\(" -n
rg --type php "\\\$fiber->(resume|getReturn|start)\s*\(" -n

# Tìm resume không có state check trước
rg --type php "\\\$fiber->resume\s*\(" -B 3 | grep -v "isSuspended"

# Tìm getReturn không có isTerminated check
rg --type php "\\\$fiber->getReturn\s*\(" -B 3 | grep -v "isTerminated"
```

### 6. Giải pháp

| Method | Khi nào hợp lệ | Check trước khi gọi |
|--------|---------------|-------------------|
| `start()` | Chỉ khi `isStarted() === false` | `!$fiber->isStarted()` |
| `resume($val)` | Chỉ khi `isSuspended() === true` | `$fiber->isSuspended()` |
| `getReturn()` | Chỉ khi `isTerminated() === true` | `$fiber->isTerminated()` |
| `Fiber::suspend()` | Chỉ từ bên trong Fiber đang chạy | - |

```php
<?php
declare(strict_types=1);

// ============================================================
// BAD - Không kiểm tra Fiber state
// ============================================================

$fiber = new Fiber(function(): string {
    $value = Fiber::suspend('ready');  // Suspend và trả về 'ready'
    return "Result: $value";
});

$fiber->start();           // Chạy đến suspend
// ... thời gian trôi qua, có thể Fiber đã terminate ...
$fiber->resume('input');   // FiberError nếu Fiber không suspended!
$result = $fiber->getReturn();  // FiberError nếu chưa terminated!

// ============================================================
// GOOD - Luôn kiểm tra state trước khi gọi
// ============================================================

class SafeFiberRunner
{
    private \Fiber $fiber;

    public function __construct(callable $callback)
    {
        $this->fiber = new \Fiber($callback);
    }

    public function start(mixed ...$args): mixed
    {
        if ($this->fiber->isStarted()) {
            throw new \LogicException('Fiber đã được start');
        }
        return $this->fiber->start(...$args);
    }

    public function resume(mixed $value = null): mixed
    {
        if (!$this->fiber->isSuspended()) {
            throw new \LogicException(
                'Fiber không ở trạng thái suspended. ' .
                'isTerminated: ' . ($this->fiber->isTerminated() ? 'true' : 'false')
            );
        }
        return $this->fiber->resume($value);
    }

    public function getReturn(): mixed
    {
        if (!$this->fiber->isTerminated()) {
            throw new \LogicException('Fiber chưa terminated, không thể lấy return value');
        }
        return $this->fiber->getReturn();
    }

    public function isRunnable(): bool
    {
        return $this->fiber->isSuspended();
    }

    public function isDone(): bool
    {
        return $this->fiber->isTerminated();
    }
}

// Sử dụng safe wrapper
$runner = new SafeFiberRunner(function(): string {
    echo "Bắt đầu\n";
    $input = \Fiber::suspend('waiting for input');
    echo "Nhận được: $input\n";
    return "Hoàn thành với: $input";
});

// Start Fiber
$suspended = $runner->start();  // "Bắt đầu", suspended = 'waiting for input'

// Kiểm tra state trước khi resume
if ($runner->isRunnable()) {
    $runner->resume('user_data');
}

// Lấy kết quả sau khi terminate
if ($runner->isDone()) {
    $result = $runner->getReturn();  // "Hoàn thành với: user_data"
    echo $result . "\n";
}

// Event loop pattern với Fiber
class EventLoop
{
    /** @var array<\Fiber> */
    private array $fibers = [];

    public function add(\Fiber $fiber): void
    {
        if (!$fiber->isStarted()) {
            $fiber->start();
        }
        if ($fiber->isSuspended()) {
            $this->fibers[] = $fiber;
        }
    }

    public function run(): void
    {
        while (!empty($this->fibers)) {
            foreach ($this->fibers as $key => $fiber) {
                if ($fiber->isSuspended()) {
                    $fiber->resume();
                }
                if ($fiber->isTerminated()) {
                    unset($this->fibers[$key]);  // Loại bỏ fiber đã xong
                }
            }
            $this->fibers = array_values($this->fibers);
        }
    }
}
```

### 7. Phòng ngừa

**Checklist:**
- [ ] Luôn kiểm tra `isSuspended()` trước `resume()`
- [ ] Luôn kiểm tra `isTerminated()` trước `getReturn()`
- [ ] Wrapper class để encapsulate state management
- [ ] Log state transitions khi debug Fiber issues
- [ ] Dùng try-catch `FiberError` làm safety net
- [ ] Test tất cả state transitions trong unit test

**PHPStan / Psalm rules:**
```bash
# PHPStan có thể phát hiện một số Fiber misuse
vendor/bin/phpstan analyse --level=8 src/

# Tìm tất cả Fiber usage để review thủ công
rg --type php "new Fiber|Fiber::suspend|\->resume\(\|\->getReturn\(" -n
```

---

*Hết Domain 01: Kiểu Dữ Liệu Và So Sánh - 14 patterns*
