# Domain 04: Toàn Vẹn Dữ Liệu (Data Integrity)

**Lĩnh vực:** Toàn Vẹn Dữ Liệu / Database / Cache / Session
**Số lượng patterns:** 12
**Ngôn ngữ:** PHP 8.x / Laravel 10+
**Cập nhật:** 2026-02-18

---

## Mục Lục

1. [Eloquent N+1 Query](#1-eloquent-n1-query---high)
2. [Transaction Thiếu (Multi-table update)](#2-transaction-thiếu-multi-table-update---critical)
3. [Race Condition DB (Read-modify-write)](#3-race-condition-db-read-modify-write---high)
4. [PDO Emulated Prepare](#4-pdo-emulated-prepare---high)
5. [Date Timezone Mismatch (PHP vs MySQL)](#5-date-timezone-mismatch-php-vs-mysql---high)
6. [JSON Encoding Loss (float precision, unicode)](#6-json-encoding-loss-float-precision-unicode---medium)
7. [Character Encoding Mismatch (UTF-8 vs Latin1)](#7-character-encoding-mismatch-utf-8-vs-latin1---high)
8. [Soft Delete Inconsistency (unique constraint)](#8-soft-delete-inconsistency-unique-constraint---medium)
9. [Migration Rollback Thiếu (empty down)](#9-migration-rollback-thiếu-empty-down---medium)
10. [Cache Invalidation Sai (stale after write)](#10-cache-invalidation-sai-stale-after-write---high)
11. [Session Data Loss (concurrent write race)](#11-session-data-loss-concurrent-write-race---high)
12. [Seeder Idempotency (duplicate data on re-run)](#12-seeder-idempotency-duplicate-data-on-re-run---medium)

---

## 1. Eloquent N+1 Query - HIGH

### 1. Tên
**Eloquent N+1 Query** (Truy Vấn N+1 với Eloquent ORM)

### 2. Phân loại
Hiệu năng / Toàn Vẹn Dữ Liệu / Eloquent ORM

### 3. Mức nghiêm trọng
🟠 **HIGH** - N+1 query làm hệ thống phát sinh hàng trăm truy vấn không cần thiết, gây chậm nghiêm trọng, có thể dẫn đến timeout, làm dữ liệu tải không đồng nhất hoặc không đầy đủ dưới tải lớn.

### 4. Vấn đề
Khi duyệt qua một collection Eloquent và truy cập relationship bên trong vòng lặp mà không eager load, Laravel tự động thực hiện thêm 1 query cho mỗi phần tử. Với 100 bản ghi, hệ thống phát sinh 101 queries thay vì 2.

```
LUỒNG N+1 QUERY
================

  Controller              Eloquent ORM              Database
      |                       |                        |
      | $orders = Order::all()|                        |
      |---------------------->|                        |
      |                       |-- SELECT * FROM orders -->|
      |                       |<-- 100 rows -----------|
      |                       |                        |
      | foreach ($orders)     |                        |
      |  $order->user->name   |                        |
      |                       |-- SELECT * FROM users WHERE id=1 -->|
      |                       |<-- 1 row --------------|
      |                       |-- SELECT * FROM users WHERE id=2 -->|
      |                       |<-- 1 row --------------|
      |                       |  ... (98 queries more) |
      |                       |                        |
      | TOTAL: 101 queries!   |                        |
      | (1 + N queries)       |                        |
```

### 5. Phát hiện
```bash
# Tìm lazy loading trong vòng lặp (foreach/for/while chứa ->relationship)
rg --type php -n "foreach\s*\(\s*\$\w+\s+as" -A 10 | grep -E "\->(user|order|product|category|tags|items|comments)\b"

# Tìm all() không có with()
rg --type php -n "::(all|get)\(\)" | grep -v "with("

# Tìm truy cập relationship không qua eager load
rg --type php -n "\->(belongsTo|hasMany|hasOne|belongsToMany)\b" app/

# Tìm usage của LazyCollection mà không eager load
rg --type php -n "->lazy()\|->cursor()" app/Http/Controllers/
```

### 6. Giải pháp

**BAD - Lazy loading gây N+1:**
```php
// app/Http/Controllers/OrderController.php

// BAD: N+1 query - mỗi order tạo 1 query lấy user
public function index(): JsonResponse
{
    $orders = Order::all(); // Query 1: SELECT * FROM orders

    $result = [];
    foreach ($orders as $order) {
        $result[] = [
            'id'         => $order->id,
            'user_name'  => $order->user->name,       // Query 2, 3, 4... (N queries!)
            'item_count' => $order->items->count(),   // Query N+1, N+2... (2N queries!)
        ];
    }

    return response()->json($result);
}

// BAD: Lấy từng relationship riêng trong service
class OrderService
{
    public function getOrderSummaries(): array
    {
        $orders = Order::where('status', 'pending')->get();
        // Với 500 orders -> 1001 queries!
        return $orders->map(fn($o) => [
            'total' => $o->total,
            'email' => $o->user->email, // N+1
        ])->toArray();
    }
}
```

**GOOD - Eager loading với with():**
```php
// app/Http/Controllers/OrderController.php

// GOOD: Eager load với with() - chỉ 3 queries dù 1000 orders
public function index(): JsonResponse
{
    $orders = Order::with(['user', 'items'])->get();
    // Query 1: SELECT * FROM orders
    // Query 2: SELECT * FROM users WHERE id IN (1,2,3,...)
    // Query 3: SELECT * FROM order_items WHERE order_id IN (1,2,3,...)

    $result = $orders->map(fn($order) => [
        'id'         => $order->id,
        'user_name'  => $order->user->name,     // Không tốn thêm query
        'item_count' => $order->items->count(), // Không tốn thêm query
    ]);

    return response()->json($result);
}

// GOOD: Eager load có điều kiện (constrained eager loading)
public function show(int $id): JsonResponse
{
    $order = Order::with([
        'user:id,name,email',                          // Chỉ lấy 3 cột
        'items' => fn($q) => $q->where('active', true), // Lọc items
        'items.product:id,name,sku',                   // Nested eager load
    ])->findOrFail($id);

    return response()->json($order);
}

// GOOD: Trong service - luôn khai báo relationships cần thiết
class OrderService
{
    public function getOrderSummaries(): array
    {
        return Order::with('user:id,email')
            ->where('status', 'pending')
            ->get()
            ->map(fn($o) => [
                'total' => $o->total,
                'email' => $o->user->email, // An toàn - đã eager load
            ])
            ->toArray();
    }
}

// GOOD: Dùng withCount() thay vì count() trên collection
public function listWithCounts(): Collection
{
    return Order::withCount(['items', 'comments'])
        ->get();
    // Truy cập: $order->items_count, $order->comments_count
    // Không cần load toàn bộ items/comments
}
```

### 7. Phòng ngừa
```php
// config/app.php hoặc AppServiceProvider - bật strict mode để detect lazy loading
// app/Providers/AppServiceProvider.php
use Illuminate\Database\Eloquent\Model;

public function boot(): void
{
    // Throw exception khi lazy load xảy ra (chỉ dùng trong development)
    if (app()->isLocal()) {
        Model::preventLazyLoading();
    }

    // Production: log warning thay vì throw exception
    if (app()->isProduction()) {
        Model::handleLazyLoadingViolationUsing(function ($model, $relation) {
            logger()->warning("N+1 detected: {$model}::{$relation}");
        });
    }
}

// PHPStan rule (phpstan.neon):
// Dùng package: beyondcode/laravel-query-detector trong development
// Dùng Telescope hoặc Debugbar để monitor query count
```

---

## 2. Transaction Thiếu (Multi-table update) - CRITICAL

### 1. Tên
**Transaction Thiếu** (Missing Database Transaction for Multi-table Update)

### 2. Phân loại
Toàn Vẹn Dữ Liệu / Database Transaction / Atomic Operation

### 3. Mức nghiêm trọng
🔴 **CRITICAL** - Khi update nhiều bảng mà không dùng transaction, nếu một bước thất bại, dữ liệu sẽ ở trạng thái không nhất quán (partial commit), gây lỗi nghiêm trọng về toàn vẹn dữ liệu mà rất khó phát hiện và sửa.

### 4. Vấn đề
Trong một thao tác nghiệp vụ cần cập nhật nhiều bảng (ví dụ: tạo đơn hàng, trừ tồn kho, ghi transaction tài chính), nếu bước 2 hoặc 3 thất bại sau khi bước 1 đã thành công, dữ liệu sẽ bị "nửa vời" mà không có cơ chế rollback.

```
LUỒNG PARTIAL COMMIT (THẢM HỌA)
==================================

  User              Service              Database
   |                   |                    |
   | Place Order       |                    |
   |------------------>|                    |
   |                   |-- INSERT orders -->|  (OK - order tạo thành công)
   |                   |                    |
   |                   |-- UPDATE inventory -->| (OK - trừ 5 units)
   |                   |                    |
   |                   |-- INSERT payments -->| (EXCEPTION! payment_method lỗi)
   |                   |                    |
   |    500 Error      |                    |
   |<------------------|                    |
   |                   |                    |
   TRẠNG THÁI SAU LỖI:
   - orders: 1 record mới (trạng thái "pending")
   - inventory: đã bị trừ 5 units
   - payments: KHÔNG có record

   -> Hệ thống KHÔNG NHẤT QUÁN!
   -> Inventory bị sai, order không có payment
   -> Cần can thiệp manual để fix!
```

### 5. Phát hiện
```bash
# Tìm service/controller update nhiều model mà không dùng transaction
rg --type php -n "->save()\|->update()\|->create()\|->delete()" app/Services/ | \
  grep -v "DB::transaction\|beginTransaction"

# Tìm method có nhiều Eloquent write mà không có transaction wrapper
rg --type php -n "DB::transaction" app/Services/

# Tìm các chỗ gọi nhiều save() liên tiếp
rg --type php -n "->save();" -A 3 | grep -B 1 "->save();"

# Tìm service method dài với nhiều write operations
rg --type php -n "function (create|store|place|process|transfer)\b" app/Services/
```

### 6. Giải pháp

**BAD - Không có transaction:**
```php
// app/Services/OrderService.php

// BAD: Không có transaction - dữ liệu có thể bị partial commit
class OrderService
{
    public function placeOrder(array $data): Order
    {
        // Bước 1: Tạo order - thành công
        $order = Order::create([
            'user_id' => $data['user_id'],
            'total'   => $data['total'],
            'status'  => 'pending',
        ]);

        // Bước 2: Trừ tồn kho - thành công
        foreach ($data['items'] as $item) {
            Product::find($item['id'])
                ->decrement('stock', $item['quantity']); // Nếu lỗi ở đây?
        }

        // Bước 3: Tạo payment record - CÓ THỂ EXCEPTION!
        Payment::create([
            'order_id'       => $order->id,
            'amount'         => $data['total'],
            'payment_method' => $data['method'], // Nếu method không hợp lệ?
        ]);

        // Nếu bước 3 lỗi: order tồn tại, stock đã bị trừ, payment KHÔNG có!
        return $order;
    }
}
```

**GOOD - Bọc trong transaction:**
```php
// app/Services/OrderService.php

// GOOD: Dùng DB::transaction() để đảm bảo atomic
class OrderService
{
    public function placeOrder(array $data): Order
    {
        return DB::transaction(function () use ($data): Order {
            // Bước 1: Tạo order
            $order = Order::create([
                'user_id' => $data['user_id'],
                'total'   => $data['total'],
                'status'  => 'pending',
            ]);

            // Bước 2: Trừ tồn kho - pessimistic lock để tránh race condition
            foreach ($data['items'] as $item) {
                $product = Product::lockForUpdate()->find($item['id']);

                if ($product->stock < $item['quantity']) {
                    throw new InsufficientStockException(
                        "Sản phẩm #{$product->id} không đủ tồn kho"
                    );
                }

                $product->decrement('stock', $item['quantity']);

                OrderItem::create([
                    'order_id'   => $order->id,
                    'product_id' => $product->id,
                    'quantity'   => $item['quantity'],
                    'price'      => $product->price,
                ]);
            }

            // Bước 3: Tạo payment record
            Payment::create([
                'order_id'       => $order->id,
                'amount'         => $data['total'],
                'payment_method' => $data['method'],
            ]);

            // Nếu BẤT KỲ bước nào exception -> tất cả rollback tự động!
            return $order;
        });
        // Nếu muốn retry khi deadlock:
        // return DB::transaction(fn() => ..., attempts: 3);
    }

    // GOOD: Nested transaction với savepoint
    public function transferFunds(int $fromId, int $toId, float $amount): void
    {
        DB::transaction(function () use ($fromId, $toId, $amount): void {
            $from = Account::lockForUpdate()->findOrFail($fromId);
            $to   = Account::lockForUpdate()->findOrFail($toId);

            if ($from->balance < $amount) {
                throw new \DomainException('Số dư không đủ');
            }

            $from->decrement('balance', $amount);
            $to->increment('balance', $amount);

            AccountTransaction::create([
                'from_account_id' => $fromId,
                'to_account_id'   => $toId,
                'amount'          => $amount,
                'type'            => 'transfer',
            ]);
        });
    }
}
```

### 7. Phòng ngừa
```php
// Tạo trait để enforce transaction trong service
trait RequiresTransaction
{
    protected function runInTransaction(callable $callback, int $attempts = 1): mixed
    {
        return DB::transaction($callback, $attempts);
    }
}

// PHPStan custom rule: cảnh báo khi service method gọi nhiều write mà không có transaction
// Dùng phpstan-dba hoặc custom rule để phát hiện pattern này

// Trong test: kiểm tra rollback hoạt động đúng
/** @test */
public function it_rolls_back_on_payment_failure(): void
{
    $this->expectException(PaymentException::class);

    $orderCountBefore = Order::count();
    $stockBefore      = Product::find(1)->stock;

    try {
        $this->service->placeOrder($this->invalidPaymentData());
    } catch (PaymentException $e) {
        // Verify rollback
        $this->assertEquals($orderCountBefore, Order::count());
        $this->assertEquals($stockBefore, Product::find(1)->stock);
        throw $e;
    }
}
```

---

## 3. Race Condition DB (Read-modify-write) - HIGH

### 1. Tên
**Race Condition DB** (Read-Modify-Write Race Condition trong Database)

### 2. Phân loại
Toàn Vẹn Dữ Liệu / Concurrency / Locking

### 3. Mức nghiêm trọng
🟠 **HIGH** - Race condition trong read-modify-write cycle khiến nhiều request đồng thời đọc cùng một giá trị, tính toán độc lập rồi ghi đè lên nhau, dẫn đến dữ liệu sai (lost update, overselling, double booking).

### 4. Vấn đề
Khi nhiều request đồng thời đọc một giá trị (ví dụ stock = 5), mỗi request tính toán và ghi lại (stock = 4), cuối cùng chỉ có 1 đơn vị được trừ dù 2 người mua.

```
RACE CONDITION: OVERSELLING
=============================

  Request A              Database            Request B
      |                     |                    |
      | READ stock=5         |                    |
      |-------------------->|                    |
      |<-- stock=5 ----------|                    |
      |                     |  READ stock=5      |
      |                     |<-------------------|
      |                     |-- stock=5 -------->|
      |                     |                    |
      | stock = 5 - 1 = 4   |                    |
      | WRITE stock=4        |                    |
      |-------------------->|    stock=5-1=4     |
      |                     |    WRITE stock=4   |
      |                     |<-------------------|
      |                     |                    |
      KẾT QUẢ: stock = 4
      (2 người mua nhưng chỉ trừ 1!)
      -> OVERSELLING: bán được nhiều hơn tồn kho!

TÌNH HUỐNG TƯƠNG TỰ:
- Coupon: giới hạn 100 lượt nhưng dùng được 200 lượt
- Seat booking: 1 ghế được đặt bởi 2 người
- Wallet: số dư âm do rút đồng thời
```

### 5. Phát hiện
```bash
# Tìm pattern read rồi write không có lock
rg --type php -n "->find\(\|->first\(" -A 5 | grep -E "increment\|decrement\|->save\(\|->update\("

# Tìm increment/decrement không trong transaction
rg --type php -n "->increment\|->decrement" app/ | grep -v "transaction\|lockForUpdate"

# Tìm check rồi update (check-then-act pattern)
rg --type php -n "if.*->stock\|if.*->balance\|if.*->quota" -A 3 app/Services/

# Tìm update không dùng where điều kiện atomic
rg --type php -n "::where.*->update(" app/
```

### 6. Giải pháp

**BAD - Race condition:**
```php
// app/Services/InventoryService.php

// BAD: Read-modify-write không có lock -> overselling
class InventoryService
{
    public function reserve(int $productId, int $qty): bool
    {
        $product = Product::find($productId);

        // RACE CONDITION: nhiều request cùng đọc stock = 5
        if ($product->stock < $qty) {
            return false;
        }

        // Khoảng thời gian giữa read và write -> race condition!
        $product->update(['stock' => $product->stock - $qty]);
        // Request A: 5 - 1 = 4 (write 4)
        // Request B: 5 - 1 = 4 (write 4) <- OVERWRITES A!
        // Thực tế stock phải là 3!

        return true;
    }
}
```

**GOOD - Pessimistic và Optimistic locking:**
```php
// app/Services/InventoryService.php

class InventoryService
{
    // GOOD: Pessimistic locking - lockForUpdate() giữ row lock
    public function reserveWithPessimisticLock(int $productId, int $qty): bool
    {
        return DB::transaction(function () use ($productId, $qty): bool {
            // lockForUpdate() phát ra SELECT ... FOR UPDATE
            // Các request khác phải chờ cho đến khi transaction kết thúc
            $product = Product::lockForUpdate()->find($productId);

            if ($product === null || $product->stock < $qty) {
                return false;
            }

            $product->decrement('stock', $qty);
            // Chỉ 1 request tại 1 thời điểm có thể thực hiện bước này
            return true;
        });
    }

    // GOOD: Optimistic locking - dùng version column
    public function reserveWithOptimisticLock(int $productId, int $qty): bool
    {
        return DB::transaction(function () use ($productId, $qty): bool {
            $product = Product::find($productId);

            if ($product->stock < $qty) {
                return false;
            }

            // Update chỉ thành công nếu version chưa thay đổi
            $affected = Product::where('id', $productId)
                ->where('version', $product->version) // Optimistic lock condition
                ->where('stock', '>=', $qty)
                ->update([
                    'stock'   => DB::raw("stock - {$qty}"),
                    'version' => DB::raw('version + 1'),
                ]);

            if ($affected === 0) {
                throw new ConcurrentUpdateException('Dữ liệu đã được cập nhật bởi request khác');
            }

            return true;
        });
    }

    // GOOD: Atomic increment/decrement với điều kiện
    public function decrementStock(int $productId, int $qty): bool
    {
        // Atomic: UPDATE products SET stock = stock - ? WHERE id = ? AND stock >= ?
        $affected = Product::where('id', $productId)
            ->where('stock', '>=', $qty)
            ->decrement('stock', $qty);

        return $affected > 0; // 0 = không đủ stock hoặc không tồn tại
    }
}
```

### 7. Phòng ngừa
```php
// Model với optimistic locking trait
trait OptimisticLocking
{
    public static function bootOptimisticLocking(): void
    {
        static::updating(function ($model): void {
            $dirty = $model->getDirty();
            if (!empty($dirty)) {
                $affected = static::where($model->getKeyName(), $model->getKey())
                    ->where('version', $model->getOriginal('version'))
                    ->update(array_merge($dirty, ['version' => $model->version + 1]));

                if ($affected === 0) {
                    throw new \RuntimeException('Optimistic lock conflict');
                }
            }
        });
    }
}

// Migration: thêm version column
Schema::table('products', function (Blueprint $table): void {
    $table->unsignedInteger('version')->default(0);
});

// PHPStan: custom rule để phát hiện pattern read rồi save không lock
```

---

## 4. PDO Emulated Prepare - HIGH

### 1. Tên
**PDO Emulated Prepare** (PHP Emulates Prepared Statements thay vì Server-side)

### 2. Phân loại
Toàn Vẹn Dữ Liệu / SQL Injection / PDO Configuration

### 3. Mức nghiêm trọng
🟠 **HIGH** - Khi `PDO::ATTR_EMULATE_PREPARES = true` (mặc định), PHP tự nội suy tham số thay vì để MySQL xử lý, vô hiệu hóa prepared statement thực sự và có thể mở ra SQL injection trong một số edge case, đặc biệt với encoding bất thường.

### 4. Vấn đề
PDO mặc định dùng emulated prepares: PHP tự thay thế `?` bằng giá trị (có escape). Điều này không phải true prepared statements — MySQL không nhận được placeholder mà nhận SQL đã nội suy. Điều này có thể gây ra:
- SQL injection với multi-byte characters trong một số MySQL version cũ
- Type coercion bất ngờ (số vs chuỗi)
- Query plan caching không hoạt động đúng

```
EMULATED vs TRUE PREPARED STATEMENTS
=======================================

EMULATED PREPARE (mặc định, KHÔNG AN TOÀN hoàn toàn):
  PHP Application                 MySQL Server
       |                               |
       | $stmt->prepare("SELECT * FROM users WHERE id = ?")
       | $stmt->execute([userInput])   |
       |                               |
       | PHP escapes: "SELECT * FROM users WHERE id = '1; DROP TABLE--'"
       |------------------------------>|
       | MySQL nhận: SQL đã nội suy    |
       | (escape có thể bị bypass với GBK encoding!)

TRUE PREPARED STATEMENTS (an toàn):
  PHP Application                 MySQL Server
       |                               |
       | prepare("SELECT * FROM users WHERE id = ?")
       |------------------------------>|
       |                               | MySQL parse query template
       | execute([userInput])          |
       |------------------------------>|
       |                               | MySQL bind param SEPARATELY
       |                               | Không thể thay đổi SQL structure!
       |<-- safe results --------------|
```

### 5. Phát hiện
```bash
# Tìm cấu hình PDO hoặc database config
rg --type php -n "ATTR_EMULATE_PREPARES" config/ database/ app/

# Tìm cấu hình database.php Laravel
rg --type php -n "options\s*=>" config/database.php

# Tìm raw PDO usage
rg --type php -n "new PDO\b" app/

# Tìm DB::statement hoặc raw query
rg --type php -n "DB::statement\|DB::select\b\|DB::raw\b" app/ --type php

# Kiểm tra charset config
rg --type php -n "'charset'" config/database.php
```

### 6. Giải pháp

**BAD - Emulated prepare mặc định:**
```php
// config/database.php

// BAD: Không tắt emulated prepares
return [
    'connections' => [
        'mysql' => [
            'driver'    => 'mysql',
            'host'      => env('DB_HOST', '127.0.0.1'),
            'database'  => env('DB_DATABASE'),
            'username'  => env('DB_USERNAME'),
            'password'  => env('DB_PASSWORD'),
            'charset'   => 'utf8mb4',
            // THIẾU: options để tắt emulated prepares
            // PDO::ATTR_EMULATE_PREPARES mặc định là true!
        ],
    ],
];

// BAD: Raw PDO không tắt emulated prepares
$pdo = new PDO($dsn, $user, $pass);
// Mặc định: ATTR_EMULATE_PREPARES = true (PHP emulates, không phải MySQL)
$stmt = $pdo->prepare('SELECT * FROM users WHERE id = ?');
$stmt->execute([$userId]); // PHP tự nội suy, không phải true prepared
```

**GOOD - Tắt emulated prepares:**
```php
// config/database.php

// GOOD: Tắt emulated prepares, bật strict mode
return [
    'connections' => [
        'mysql' => [
            'driver'    => 'mysql',
            'host'      => env('DB_HOST', '127.0.0.1'),
            'port'      => env('DB_PORT', '3306'),
            'database'  => env('DB_DATABASE'),
            'username'  => env('DB_USERNAME'),
            'password'  => env('DB_PASSWORD'),
            'charset'   => 'utf8mb4',
            'collation' => 'utf8mb4_unicode_ci',
            'prefix'    => '',
            'strict'    => true,       // Bật MySQL strict mode
            'engine'    => 'InnoDB',   // InnoDB hỗ trợ transaction
            'options'   => [
                // QUAN TRỌNG: Tắt emulated prepares -> dùng true prepared statements
                PDO::ATTR_EMULATE_PREPARES   => false,
                // Bật exception thay vì silent error
                PDO::ATTR_ERRMODE            => PDO::ERRMODE_EXCEPTION,
                // MySQL server-side type casting
                PDO::ATTR_STRINGIFY_FETCHES  => false,
            ],
        ],
    ],
];

// GOOD: Raw PDO đúng cách
$pdo = new PDO($dsn, $user, $pass, [
    PDO::ATTR_EMULATE_PREPARES  => false,  // True prepared statements
    PDO::ATTR_ERRMODE           => PDO::ERRMODE_EXCEPTION,
    PDO::ATTR_STRINGIFY_FETCHES => false,
]);

$stmt = $pdo->prepare('SELECT * FROM users WHERE id = ?');
$stmt->execute([$userId]); // MySQL nhận query template + param riêng biệt
```

### 7. Phòng ngừa
```php
// Kiểm tra cấu hình trong AppServiceProvider
public function boot(): void
{
    $options = config('database.connections.mysql.options', []);
    if (($options[PDO::ATTR_EMULATE_PREPARES] ?? true) === true) {
        logger()->warning('PDO emulated prepares đang BẬT - hãy tắt để tăng bảo mật');
    }
}

// phpunit.xml: Chạy test với cấu hình production-like
// <env name="DB_CONNECTION" value="mysql"/>

// PHPStan: Thêm vào phpstan.neon
// Dùng taint analysis để phát hiện SQL injection
// parameters:
//   taintAnalysis: true
```

---

## 5. Date Timezone Mismatch (PHP vs MySQL) - HIGH

### 1. Tên
**Date Timezone Mismatch** (Lệch Múi Giờ Giữa PHP và MySQL)

### 2. Phân loại
Toàn Vẹn Dữ Liệu / Timezone / Datetime

### 3. Mức nghiêm trọng
🟠 **HIGH** - Khi PHP và MySQL dùng timezone khác nhau, dữ liệu datetime lưu vào DB bị lệch giờ, các truy vấn so sánh thời gian trả về kết quả sai, và báo cáo/thống kê theo ngày có thể bị sai hoàn toàn.

### 4. Vấn đề
PHP có timezone riêng, MySQL có timezone riêng. Nếu không đồng bộ, `Carbon::now()` trả về giờ Asia/Tokyo trong khi MySQL `NOW()` trả về UTC, dẫn đến dữ liệu bị lệch 9 giờ.

```
TIMEZONE MISMATCH FLOW
=======================

  PHP App (Asia/Tokyo)         MySQL (UTC)         Storage
       |                           |                  |
       | Carbon::now()             |                  |
       | = 2026-02-18 15:00:00 JST |                  |
       |                           |                  |
       | INSERT created_at = '2026-02-18 15:00:00'    |
       |-------------------------->|                  |
       |                           | Lưu: 15:00:00    |
       |                           |-- store -------->|
       |                           |                  |
       | SELECT WHERE date = today |                  |
       | (PHP today = 2026-02-18)  |                  |
       | MySQL NOW() = 06:00 UTC   |                  |
       |                           |                  |
       KẾT QUẢ:
       - Record 15:00 JST = 06:00 UTC ngày hôm qua!
       - Query "hôm nay" có thể bị mất dữ liệu
       - Báo cáo doanh thu ngày bị sai 9 tiếng!
```

### 5. Phát hiện
```bash
# Tìm timezone config trong Laravel
rg --type php -n "'timezone'" config/app.php

# Tìm MySQL timezone setting
rg --type php -n "time_zone\|@@global.time_zone" config/ app/

# Tìm Carbon usage không chỉ định timezone
rg --type php -n "Carbon::now()\|Carbon::today()\|now()" app/ | grep -v "timezone\|setTimezone"

# Tìm raw datetime string không có timezone info
rg --type php -n "date\('Y-m-d\|date\('Y-m-d H:i" app/

# Kiểm tra .env
rg "APP_TIMEZONE\|DB_TIMEZONE" .env
```

### 6. Giải pháp

**BAD - Timezone không nhất quán:**
```php
// config/app.php - BAD: timezone mặc định UTC nhưng MySQL cấu hình khác
return [
    'timezone' => 'UTC', // PHP dùng UTC
    // Nhưng MySQL server được set Asia/Tokyo!
];

// BAD: Lưu datetime không nhất quán
class AppointmentService
{
    public function create(array $data): Appointment
    {
        return Appointment::create([
            'scheduled_at' => $data['date'], // String từ user, timezone?
            'created_at'   => date('Y-m-d H:i:s'), // PHP timezone
            // MySQL tự ghi NOW() với timezone của MySQL server
        ]);
    }

    // BAD: So sánh ngày không nhất quán
    public function getTodayAppointments(): Collection
    {
        // Carbon::today() dùng PHP timezone
        // Nhưng MySQL CURDATE() dùng MySQL timezone
        return Appointment::whereDate('scheduled_at', today())->get();
        // Có thể trả về kết quả sai nếu timezone khác nhau!
    }
}
```

**GOOD - Timezone đồng nhất:**
```php
// config/app.php - GOOD: Đặt PHP timezone rõ ràng
return [
    'timezone' => env('APP_TIMEZONE', 'Asia/Tokyo'), // Luôn nhất quán
];

// config/database.php - GOOD: Sync timezone MySQL với PHP
return [
    'connections' => [
        'mysql' => [
            // ...
            'timezone' => '+09:00', // Hoặc 'Asia/Tokyo' nếu MySQL đã load tz data
        ],
    ],
];

// GOOD: Service dùng timezone nhất quán
class AppointmentService
{
    public function create(array $data): Appointment
    {
        // Luôn dùng Carbon với timezone rõ ràng
        $scheduledAt = Carbon::parse($data['date'], 'Asia/Tokyo')
            ->setTimezone(config('app.timezone'));

        return Appointment::create([
            'scheduled_at' => $scheduledAt,
            // Laravel tự xử lý created_at/updated_at với app timezone
        ]);
    }

    // GOOD: So sánh ngày với timezone rõ ràng
    public function getTodayAppointments(): Collection
    {
        $start = Carbon::today(config('app.timezone'))->startOfDay();
        $end   = Carbon::today(config('app.timezone'))->endOfDay();

        return Appointment::whereBetween('scheduled_at', [$start, $end])->get();
    }
}

// GOOD: Migration lưu timestamp luôn UTC
Schema::create('appointments', function (Blueprint $table): void {
    $table->id();
    $table->timestamp('scheduled_at')->nullable(); // Lưu UTC, hiển thị convert
    $table->timestamps();
});

// GOOD: Model cast datetime và set timezone display
class Appointment extends Model
{
    protected $casts = [
        'scheduled_at' => 'datetime', // Cast về Carbon
    ];

    // Hiển thị luôn convert sang app timezone
    public function getScheduledAtLocalAttribute(): string
    {
        return $this->scheduled_at
            ->setTimezone(config('app.timezone'))
            ->format('Y-m-d H:i:s');
    }
}
```

### 7. Phòng ngừa
```php
// Test timezone consistency
/** @test */
public function database_and_app_timezone_are_consistent(): void
{
    $appTz  = config('app.timezone');
    $dbTime = DB::select('SELECT NOW() as now')[0]->now;
    $phpNow = Carbon::now($appTz)->format('Y-m-d H:i');
    $dbNow  = Carbon::parse($dbTime, 'UTC')
        ->setTimezone($appTz)
        ->format('Y-m-d H:i');

    $this->assertEquals($phpNow, $dbNow, 'PHP và DB timezone phải đồng nhất');
}

// .env best practice
// APP_TIMEZONE=Asia/Tokyo
// Và cấu hình MySQL server: SET GLOBAL time_zone = '+09:00';

// PHPStan: Thêm Carbon timezone extension để kiểm tra static usage
```

---

## 6. JSON Encoding Loss (float precision, unicode) - MEDIUM

### 1. Tên
**JSON Encoding Loss** (Mất Dữ Liệu Khi Encode JSON - Float Precision và Unicode)

### 2. Phân loại
Toàn Vẹn Dữ Liệu / JSON / Encoding

### 3. Mức nghiêm trọng
🟡 **MEDIUM** - `json_encode()` mặc định có thể làm mất độ chính xác của số thực (float), escape ký tự Unicode không cần thiết, hoặc trả về `false` khi gặp dữ liệu không encode được mà không báo lỗi rõ ràng.

### 4. Vấn đề
PHP `json_encode()` dùng double precision float nhưng có thể thay đổi giá trị tiền tệ hoặc tọa độ. Unicode mặc định bị escape thành `\uXXXX`. Khi encoding thất bại, hàm trả về `false` thay vì throw exception.

```
JSON ENCODING ISSUES
======================

1. FLOAT PRECISION LOSS:
   PHP: $price = 1234567.89
   json_encode($price) -> "1234567.89" (OK nhỏ)
   $price = 12345678901234.56
   json_encode($price) -> "12345678901234.56" -> "12345678901234.5" (mất!)

2. UNICODE ESCAPE (không cần thiết):
   $name = "田中 太郎"
   json_encode($name)
   -> "\"\\u7530\\u4e2d \\u592a\\u90ce\""  (escaped!)

   json_encode($name, JSON_UNESCAPED_UNICODE)
   -> "\"田中 太郎\""  (readable, nhỏ hơn)

3. SILENT FAILURE:
   $data = ["key" => "\xff\xfe"]; // invalid UTF-8
   $json = json_encode($data);    // Returns FALSE!
   // Không có exception, $json là false
   // Nếu dùng $json ngay: "false" hoặc empty!
```

### 5. Phát hiện
```bash
# Tìm json_encode không kiểm tra kết quả
rg --type php -n "json_encode\(" app/ | grep -v "=== false\|!== false\|json_last_error"

# Tìm json_decode không xử lý lỗi
rg --type php -n "json_decode\(" app/ | grep -v "json_last_error\|!== null"

# Tìm float trong context JSON (giá tiền, tọa độ)
rg --type php -n "->price\|->amount\|->latitude\|->longitude" app/ | grep "json_encode\|toJson"

# Tìm JSON response không có JSON_UNESCAPED_UNICODE
rg --type php -n "json_encode\(" app/ | grep -v "JSON_UNESCAPED_UNICODE"
```

### 6. Giải pháp

**BAD - json_encode không an toàn:**
```php
// app/Services/ApiResponseService.php

// BAD: Không kiểm tra lỗi, không xử lý float precision, không unescaped unicode
class ApiResponseService
{
    public function toJson(array $data): string
    {
        return json_encode($data); // Có thể trả về false!
        // Float precision mất, unicode bị escape, lỗi không bị catch
    }

    // BAD: Float tiền tệ bị mất precision
    public function formatPrice(float $price): string
    {
        return json_encode(['price' => $price]);
        // Với giá lớn: 12345678.90 -> 12345678.9 (mất số 0 cuối!)
    }
}

// BAD: json_decode không xử lý lỗi
$data = json_decode($jsonString, true);
$userId = $data['user_id']; // PHP Warning nếu decode thất bại (null)
```

**GOOD - json_encode an toàn:**
```php
// app/Services/ApiResponseService.php

// GOOD: Helper function an toàn
class JsonHelper
{
    /**
     * @throws \JsonException
     */
    public static function encode(mixed $data): string
    {
        return json_encode(
            $data,
            JSON_THROW_ON_ERROR        // Throw \JsonException thay vì return false
            | JSON_UNESCAPED_UNICODE   // Không escape unicode: "田中" thay vì "\u7530\u4e2d"
            | JSON_UNESCAPED_SLASHES   // Không escape slash: "/" thay vì "\/"
        );
    }

    /**
     * @throws \JsonException
     */
    public static function decode(string $json, bool $assoc = true): mixed
    {
        return json_decode($json, $assoc, 512, JSON_THROW_ON_ERROR);
    }
}

// GOOD: Float tiền tệ - dùng string hoặc integer (cents)
class PriceService
{
    // Option 1: Lưu integer (cents), hiển thị string
    public function formatForJson(int $amountInCents): array
    {
        return [
            'amount_cents'  => $amountInCents,           // Integer, không mất precision
            'amount_string' => number_format($amountInCents / 100, 2), // "1234.56"
        ];
    }

    // Option 2: Dùng BC Math cho số lớn
    public function calculateTax(string $price, string $rate): string
    {
        // bcmul trả về string, không bị float precision issue
        return bcmul($price, $rate, 2); // "1234.56"
    }
}

// GOOD: Model cast để đảm bảo JSON an toàn
class Product extends Model
{
    protected $casts = [
        'metadata' => 'array',    // Tự động json_decode/encode
        'price'    => 'decimal:2', // Lưu exact decimal, không float
        'tags'     => 'array',
    ];
}

// GOOD: Xử lý lỗi decode rõ ràng
function parseWebhookPayload(string $payload): array
{
    try {
        $data = JsonHelper::decode($payload);
    } catch (\JsonException $e) {
        logger()->error('Invalid JSON payload', [
            'error'   => $e->getMessage(),
            'payload' => substr($payload, 0, 100), // Log một phần để debug
        ]);
        throw new InvalidPayloadException('Payload JSON không hợp lệ', previous: $e);
    }

    return $data;
}
```

### 7. Phòng ngừa
```php
// PHPStan custom rule: cảnh báo json_encode không có JSON_THROW_ON_ERROR
// Thêm vào phpstan.neon:
// rules:
//   - App\PHPStan\JsonEncodeRule

// Tạo custom PHPStan rule
class JsonEncodeRule implements \PHPStan\Rules\Rule
{
    public function getNodeType(): string { return \PhpParser\Node\Expr\FuncCall::class; }

    public function processNode(\PhpParser\Node $node, \PHPStan\Analyser\Scope $scope): array
    {
        if ($node->name->toString() === 'json_encode') {
            $args = $node->args;
            if (count($args) < 2) {
                return [RuleErrorBuilder::message(
                    'json_encode() thiếu flag JSON_THROW_ON_ERROR'
                )->build()];
            }
        }
        return [];
    }
}
```

---

## 7. Character Encoding Mismatch (UTF-8 vs Latin1) - HIGH

### 1. Tên
**Character Encoding Mismatch** (Lệch Encoding Ký Tự UTF-8 vs Latin1)

### 2. Phân loại
Toàn Vẹn Dữ Liệu / Encoding / Database

### 3. Mức nghiêm trọng
🟠 **HIGH** - Khi PHP gửi dữ liệu UTF-8 nhưng MySQL connection được cấu hình Latin1, ký tự multibyte bị lưu sai (mojibake), dữ liệu không thể khôi phục hoàn toàn, và search/sort tiếng Nhật/Việt/Trung sẽ sai.

### 4. Vấn đề
MySQL có 3 tầng encoding: server, database, table/column. Nếu connection charset không khớp với storage charset, dữ liệu bị convert sai. Đặc biệt nguy hiểm khi có emoji (cần `utf8mb4`, không phải `utf8`).

```
ENCODING MISMATCH FLOW
========================

  PHP (UTF-8)              MySQL Connection           MySQL Storage
      |                    (Latin1, sai!)                (utf8mb4)
      |                          |                          |
      | "田中太郎" (UTF-8)        |                          |
      | 3 bytes/char             |                          |
      |------------------------->|                          |
      |                    Convert sai!                     |
      |                    UTF-8 -> Latin1 -> ???           |
      |                          |-- lưu sai chars -------->|
      |                          |                          |
      | SELECT name              |                          |
      |------------------------->|                          |
      |                          |<-- "???" hoặc "ç°äº"---|
      |<-- "?????" --------------|                          |

      KẾT QUẢ: Dữ liệu bị hỏng (mojibake)!
      - Không thể search đúng
      - Không thể sort đúng
      - Dữ liệu KHÔNG THỂ khôi phục hoàn toàn!

EMOJI TRAP (utf8 vs utf8mb4):
  MySQL "utf8" chỉ hỗ trợ 3-byte UTF-8
  Emoji = 4-byte: "😊" = U+1F60A
  Nếu column là utf8 (không phải utf8mb4):
  INSERT "Hello 😊" -> lưu "Hello " (emoji bị cắt!)
  Có thể lỗi hoặc silent truncation!
```

### 5. Phát hiện
```bash
# Kiểm tra charset trong database config Laravel
rg --type php -n "'charset'\|'collation'" config/database.php

# Tìm migration không chỉ định charset
rg --type php -n "Schema::create\|Blueprint" database/migrations/ | grep -v "utf8mb4"

# Kiểm tra MySQL charset thực tế
# mysql -u root -e "SHOW VARIABLES LIKE 'character%';"

# Tìm column text không có collation rõ ràng
rg --type php -n "->string\|->text\|->mediumText\|->longText" database/migrations/

# Tìm emoji trong test data hoặc seeder
rg --type php -n "[\x{1F600}-\x{1F64F}]" database/seeders/
```

### 6. Giải pháp

**BAD - Encoding mặc định không đúng:**
```php
// config/database.php - BAD
return [
    'connections' => [
        'mysql' => [
            'charset'   => 'utf8',          // THIẾU mb4! Emoji bị cắt!
            'collation' => 'utf8_unicode_ci', // Sai collation!
        ],
    ],
];

// database/migrations - BAD: Không chỉ định charset rõ ràng
Schema::create('users', function (Blueprint $table): void {
    $table->id();
    $table->string('name'); // Dùng default charset của table/DB
    // Nếu MySQL default là latin1 -> lỗi ngay!
});

// BAD: Không set charset khi kết nối raw PDO
$pdo = new PDO("mysql:host={$host};dbname={$db}", $user, $pass);
// Charset mặc định có thể là latin1!
```

**GOOD - Encoding nhất quán:**
```php
// config/database.php - GOOD
return [
    'connections' => [
        'mysql' => [
            'charset'   => 'utf8mb4',              // Hỗ trợ emoji (4-byte UTF-8)
            'collation' => 'utf8mb4_unicode_ci',   // Unicode-aware collation
            // Laravel tự gửi: SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci
        ],
    ],
];

// database/migrations - GOOD: Chỉ định charset cho table
Schema::create('users', function (Blueprint $table): void {
    $table->id();
    $table->string('name');
    $table->string('bio')->charset('utf8mb4')->collation('utf8mb4_unicode_ci');
    $table->timestamps();
}); // Laravel sẽ set table charset từ config database

// GOOD: Đảm bảo table charset khi create
DB::statement('ALTER TABLE users CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci');

// GOOD: Raw PDO với charset rõ ràng
$pdo = new PDO(
    "mysql:host={$host};dbname={$db};charset=utf8mb4",
    $user,
    $pass
);

// GOOD: Kiểm tra encoding trước khi lưu
class UserService
{
    public function validateEncoding(string $text): void
    {
        if (!mb_check_encoding($text, 'UTF-8')) {
            throw new \InvalidArgumentException('Text không phải UTF-8 hợp lệ');
        }
    }

    public function create(array $data): User
    {
        $this->validateEncoding($data['name']);

        // Normalize unicode (NFC) để tránh duplicate key issue
        $data['name'] = \Normalizer::normalize($data['name'], \Normalizer::FORM_C);

        return User::create($data);
    }
}
```

### 7. Phòng ngừa
```php
// Test encoding consistency
/** @test */
public function it_stores_and_retrieves_multibyte_characters(): void
{
    $name    = '田中太郎テスト😊'; // Kanji + emoji
    $user    = User::factory()->create(['name' => $name]);
    $fetched = User::find($user->id);

    $this->assertSame($name, $fetched->name, 'Multibyte và emoji phải lưu/đọc đúng');
}

// MySQL script: Kiểm tra và fix encoding
// SHOW CREATE TABLE users; -> Kiểm tra CHARACTER SET
// ALTER TABLE users CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

// php.ini:
// default_charset = "UTF-8"
// mbstring.internal_encoding = UTF-8
```

---

## 8. Soft Delete Inconsistency (unique constraint) - MEDIUM

### 1. Tên
**Soft Delete Inconsistency** (Mâu Thuẫn Unique Constraint với Soft Delete)

### 2. Phân loại
Toàn Vẹn Dữ Liệu / Soft Delete / Database Constraint

### 3. Mức nghiêm trọng
🟡 **MEDIUM** - Khi dùng soft delete với unique constraint, một record đã bị soft-delete vẫn chiếm unique slot, khiến không thể tạo record mới với cùng email/username, gây lỗi UX khó hiểu.

### 4. Vấn đề
Soft delete đặt `deleted_at` thành timestamp nhưng record vẫn ở DB. Unique index trên `email` không phân biệt `deleted_at IS NULL` hay không, nên email đã "xóa" vẫn bị coi là đang dùng.

```
SOFT DELETE + UNIQUE CONSTRAINT PROBLEM
=========================================

  users table:
  +----+------------------+---------------------+
  | id | email            | deleted_at          |
  +----+------------------+---------------------+
  |  1 | user@example.com | 2026-01-01 10:00:00 | <- Soft deleted
  |  2 | other@test.com   | NULL                |
  +----+------------------+---------------------+

  UNIQUE INDEX: (email) <- không phân biệt deleted!

  User đăng ký lại: user@example.com
  -> INSERT INTO users (email=...)
  -> SQLSTATE[23000]: Duplicate entry 'user@example.com'
  -> Lỗi "Email đã tồn tại" dù user đã xóa account!

  NGƯỢC LẠI: Truy vấn Eloquent mặc định thêm WHERE deleted_at IS NULL
  -> User::where('email', $email)->first() trả về NULL
  -> Nhưng validate unique vẫn check toàn bộ table!
```

### 5. Phát hiện
```bash
# Tìm model dùng SoftDeletes
rg --type php -n "use SoftDeletes\|use Illuminate\\\\Database\\\\Eloquent\\\\SoftDeletes" app/Models/

# Tìm migration có unique constraint trên model dùng soft delete
rg --type php -n "->unique()" database/migrations/

# Tìm validate unique không exclude soft deleted
rg --type php -n "'unique:" app/Http/Requests/ | grep -v "deleted_at"

# Tìm unique rule không có whereNull condition
rg --type php -n "Rule::unique" app/ | grep -v "whereNull\|withoutTrashed"
```

### 6. Giải pháp

**BAD - Unique constraint xung đột với soft delete:**
```php
// database/migrations - BAD: Unique không account for soft delete
Schema::create('users', function (Blueprint $table): void {
    $table->id();
    $table->string('email')->unique(); // Unique không phân biệt deleted_at!
    $table->softDeletes();
});

// app/Http/Requests/RegisterRequest.php - BAD
public function rules(): array
{
    return [
        'email' => 'required|email|unique:users', // Vẫn check soft-deleted records!
    ];
}

// Hệ quả: User đã xóa account không thể đăng ký lại cùng email!
```

**GOOD - Composite unique hoặc partial index:**
```php
// database/migrations - GOOD: Option 1 - Partial unique index (MySQL 8+)
Schema::create('users', function (Blueprint $table): void {
    $table->id();
    $table->string('email');
    $table->softDeletes();
    // Unique chỉ áp dụng khi deleted_at IS NULL
    // Cần raw SQL cho partial index
});

// Thêm partial index riêng
DB::statement(
    'CREATE UNIQUE INDEX users_email_unique ON users (email) WHERE deleted_at IS NULL'
);

// GOOD: Option 2 - Composite unique bao gồm deleted_at
Schema::create('users', function (Blueprint $table): void {
    $table->id();
    $table->string('email');
    $table->softDeletes();
    // Unique trên (email, deleted_at) - cho phép cùng email nếu deleted_at khác nhau
    // Nhưng cần cẩn thận: 2 deleted records cùng email cũng bị conflict
});

// GOOD: Option 3 - Dùng uniqueDeletedAt column trick
Schema::create('users', function (Blueprint $table): void {
    $table->id();
    $table->string('email');
    $table->timestamp('deleted_at')->nullable();
    // Không unique trên email, kiểm tra trong application layer
});

// app/Http/Requests/RegisterRequest.php - GOOD
use Illuminate\Validation\Rule;

public function rules(): array
{
    return [
        'email' => [
            'required',
            'email',
            // Chỉ kiểm tra unique trong records CHƯA bị soft delete
            Rule::unique('users', 'email')->whereNull('deleted_at'),
        ],
    ];
}

// app/Services/UserService.php - GOOD: Cho phép restore khi đăng ký lại
public function registerOrRestore(array $data): User
{
    // Kiểm tra xem có soft-deleted user với email này không
    $deletedUser = User::withTrashed()
        ->where('email', $data['email'])
        ->whereNotNull('deleted_at')
        ->first();

    if ($deletedUser) {
        // Restore thay vì tạo mới
        $deletedUser->restore();
        $deletedUser->update(['password' => bcrypt($data['password'])]);
        return $deletedUser;
    }

    return User::create($data);
}
```

### 7. Phòng ngừa
```php
// Test soft delete + unique behavior
/** @test */
public function deleted_user_email_can_be_reused(): void
{
    $user = User::factory()->create(['email' => 'test@example.com']);
    $user->delete(); // Soft delete

    // Phải có thể đăng ký lại với cùng email
    $response = $this->post('/register', [
        'email'    => 'test@example.com',
        'password' => 'password123',
    ]);

    $response->assertStatus(201);
    $this->assertDatabaseHas('users', [
        'email'      => 'test@example.com',
        'deleted_at' => null,
    ]);
}

// PHPStan: Custom rule kiểm tra unique validation trên SoftDelete model
// Rule::unique() mà không có whereNull('deleted_at') -> warning
```

---

## 9. Migration Rollback Thiếu (empty down) - MEDIUM

### 1. Tên
**Migration Rollback Thiếu** (Empty `down()` Method trong Migration)

### 2. Phân loại
Toàn Vẹn Dữ Liệu / Migration / Database Schema

### 3. Mức nghiêm trọng
🟡 **MEDIUM** - Migration có `down()` rỗng hoặc không đúng khiến rollback (`php artisan migrate:rollback`) không thể hoàn tác, gây ra trạng thái DB không nhất quán trong quá trình deployment/hotfix.

### 4. Vấn đề
Khi deploy gặp sự cố và cần rollback, migration với `down()` rỗng khiến `migrate:rollback` không làm gì, nhưng migration_history đã bị mark là rolled back. Schema thực tế không khớp với state mà artisan nghĩ.

```
MIGRATION ROLLBACK FAILURE
===========================

  Deploy Process              Artisan              Database
       |                        |                      |
       | migrate:migrate        |                      |
       |----------------------->|                      |
       |                        |-- ALTER TABLE... --->|  (schema thay đổi)
       |                        |                      |
       |   DEPLOYMENT FAILS!    |                      |
       |                        |                      |
       | migrate:rollback       |                      |
       |----------------------->|                      |
       |                        | down() = {} (rỗng!)  |
       |                        |  (không làm gì)      |
       |                        |                      |
       |                        | Mark migration as    |
       |                        | "not run" in migrations table
       |                        |                      |
       TRẠNG THÁI SAU:
       - migrations table: migration CHƯA chạy
       - Database schema: column/table vẫn còn!
       - KHÔNG NHẤT QUÁN!

       Lần migrate tiếp theo:
       -> "Column already exists" ERROR!
```

### 5. Phát hiện
```bash
# Tìm migration có down() rỗng hoặc chỉ có comment
rg --type php -n "function down\(\)" -A 5 database/migrations/ | grep -B 1 "^\s*}$\|^\s*//\|^\s*return"

# Tìm migration không có down() method
rg --type php -n "function up\b" database/migrations/ | \
  while read file; do grep -L "function down" "$file"; done

# Tìm migration có down() nhưng không reverse up()
rg --type php -n "Schema::table" database/migrations/ -l | \
  xargs rg -l "function down" | xargs rg -L "dropColumn\|dropForeign\|drop("

# Tìm migration có down() chỉ comment
rg --type php -n "function down\b" -A 3 database/migrations/ | grep "TODO\|FIXME\|not reversible\|//.*\."
```

### 6. Giải pháp

**BAD - down() rỗng hoặc sai:**
```php
// database/migrations/2026_02_18_add_status_to_orders_table.php

// BAD: down() rỗng - rollback không làm gì
class AddStatusToOrdersTable extends Migration
{
    public function up(): void
    {
        Schema::table('orders', function (Blueprint $table): void {
            $table->string('status')->default('pending')->after('total');
            $table->index('status'); // Thêm index
        });
    }

    public function down(): void
    {
        // TODO: Implement rollback
        // (Bỏ trống hoặc quên implement!)
    }
}

// BAD: down() không đúng thứ tự (phải drop index trước khi drop column)
class AddIndexToUsersTable extends Migration
{
    public function up(): void
    {
        Schema::table('users', function (Blueprint $table): void {
            $table->index('email', 'users_email_idx');
        });
    }

    public function down(): void
    {
        Schema::table('users', function (Blueprint $table): void {
            $table->dropColumn('email'); // SAI! Phải dropIndex trước!
        });
    }
}
```

**GOOD - down() đúng và đầy đủ:**
```php
// database/migrations/2026_02_18_add_status_to_orders_table.php

// GOOD: down() là exact reverse của up()
class AddStatusToOrdersTable extends Migration
{
    public function up(): void
    {
        Schema::table('orders', function (Blueprint $table): void {
            $table->string('status', 50)->default('pending')->after('total');
            $table->index('status', 'orders_status_idx');
        });
    }

    public function down(): void
    {
        Schema::table('orders', function (Blueprint $table): void {
            // Thứ tự QUAN TRỌNG: drop index trước, drop column sau
            $table->dropIndex('orders_status_idx');
            $table->dropColumn('status');
        });
    }
}

// GOOD: Migration tạo table
class CreateInvoicesTable extends Migration
{
    public function up(): void
    {
        Schema::create('invoices', function (Blueprint $table): void {
            $table->id();
            $table->foreignId('order_id')->constrained()->cascadeOnDelete();
            $table->string('invoice_number')->unique();
            $table->decimal('amount', 10, 2);
            $table->timestamps();
        });
    }

    public function down(): void
    {
        // Reverse của Schema::create là Schema::dropIfExists
        Schema::dropIfExists('invoices');
    }
}

// GOOD: Migration với foreign key
class AddUserIdToCommentsTable extends Migration
{
    public function up(): void
    {
        Schema::table('comments', function (Blueprint $table): void {
            $table->foreignId('user_id')->after('id')->constrained()->cascadeOnDelete();
        });
    }

    public function down(): void
    {
        Schema::table('comments', function (Blueprint $table): void {
            // Drop foreign key constraint trước, rồi drop column
            $table->dropForeign(['user_id']); // Hoặc: $table->dropForeignIdFor(User::class)
            $table->dropColumn('user_id');
        });
    }
}
```

### 7. Phòng ngừa
```php
// Luôn test rollback trong CI/CD
// Thêm vào pipeline:
// php artisan migrate
// php artisan migrate:rollback
// php artisan migrate (lần nữa để verify idempotent)

// phpunit test cho migration
/** @test */
public function migration_can_be_rolled_back(): void
{
    // Chạy migrate
    $this->artisan('migrate')->assertSuccessful();

    // Rollback 1 step
    $this->artisan('migrate:rollback', ['--step' => 1])->assertSuccessful();

    // Chạy lại để verify không có conflict
    $this->artisan('migrate')->assertSuccessful();

    $this->assertTrue(Schema::hasColumn('orders', 'status'));
}

// PHPStan: Có thể tạo custom rule kiểm tra down() không rỗng
// Hoặc dùng pre-commit hook: php artisan migrate:status
```

---

## 10. Cache Invalidation Sai (stale after write) - HIGH

### 1. Tên
**Cache Invalidation Sai** (Stale Cache Data After Write Operation)

### 2. Phân loại
Toàn Vẹn Dữ Liệu / Cache / Consistency

### 3. Mức nghiêm trọng
🟠 **HIGH** - Khi cache không được invalidate sau khi write, người dùng đọc dữ liệu cũ (stale) trong khoảng thời gian cache còn tồn tại, gây ra hiển thị sai, quyết định nghiệp vụ dựa trên data lỗi thời, hoặc security bypass (quyền đã thu hồi nhưng cache vẫn cho phép).

### 4. Vấn đề
Sau khi update DB, nếu quên xóa cache, các request tiếp theo vẫn đọc giá trị cũ từ cache cho đến khi TTL hết hạn. Với security-sensitive data như permissions, đây là lỗ hổng nghiêm trọng.

```
STALE CACHE FLOW
==================

  Admin               Cache              Database
    |                   |                    |
    | UPDATE user role  |                    |
    |                               |                    |
    |-- UPDATE users SET role='user' WHERE id=5 -------->|
    |                               |                    |
    |  (QUÊN: Cache::forget!)       |                    |
    |                               |                    |
    Sau update:                     |                    |
                                    |                    |
  User #5            Cache              Database
    |                   |                    |
    | GET permissions   |                    |
    |------------------>|                    |
    |  Cache hit!       |                    |
    |<-- role='admin' --|  (Cache cũ!)       |
    |                   |  (DB: role='user') |
    |  Vẫn có admin     |                    |
    |  quyền!!!         |                    |

    TTL còn 45 phút -> 45 phút bảo mật bị breach!
```

### 5. Phát hiện
```bash
# Tìm Cache::put/remember mà không có Cache::forget tương ứng
rg --type php -n "Cache::put\|Cache::remember" app/ -l

# Tìm service/repository write không có cache invalidation
rg --type php -n "->save()\|->update()\|->delete()\|->create(" app/Repositories/ | \
  grep -v "Cache::forget\|Cache::flush\|cache()->forget"

# Tìm cache key hardcoded (khó invalidate đúng record)
rg --type php -n "Cache::remember\|cache()->remember" app/ | grep -v "\\.id\|\\$id\|{id}"

# Tìm observer hoặc event listener cho cache invalidation
rg --type php -n "class.*Observer\|class.*Listener" app/ | grep -i "cache\|flush\|forget"
```

### 6. Giải pháp

**BAD - Cache invalidation thiếu:**
```php
// app/Repositories/UserRepository.php - BAD

class UserRepository
{
    private const CACHE_TTL = 3600; // 1 giờ

    public function findById(int $id): ?User
    {
        // Cache read - OK
        return Cache::remember("user.{$id}", self::CACHE_TTL, function () use ($id): ?User {
            return User::with('roles')->find($id);
        });
    }

    public function updateRole(int $id, string $role): void
    {
        User::where('id', $id)->update(['role' => $role]);
        // QUÊN: Cache::forget("user.{$id}");
        // Người dùng vẫn thấy role cũ trong 1 giờ!
    }

    public function delete(int $id): void
    {
        User::destroy($id);
        // QUÊN: Cache::forget("user.{$id}");
        // User đã xóa nhưng cache vẫn trả về object!
    }
}
```

**GOOD - Cache invalidation đúng:**
```php
// app/Repositories/UserRepository.php - GOOD

class UserRepository
{
    private const CACHE_TTL = 3600;

    private function cacheKey(int $id): string
    {
        return "user.{$id}"; // Centralize key generation
    }

    private function listCacheKey(): string
    {
        return 'users.list'; // Cache cho danh sách
    }

    public function findById(int $id): ?User
    {
        return Cache::remember($this->cacheKey($id), self::CACHE_TTL, function () use ($id): ?User {
            return User::with('roles')->find($id);
        });
    }

    public function update(int $id, array $data): User
    {
        $user = User::findOrFail($id);
        $user->update($data);

        // QUAN TRỌNG: Invalidate cache ngay sau write
        $this->invalidateUserCache($id);

        return $user->fresh(); // Trả về data mới nhất từ DB
    }

    public function delete(int $id): void
    {
        User::destroy($id);
        $this->invalidateUserCache($id);
    }

    private function invalidateUserCache(int $id): void
    {
        Cache::forget($this->cacheKey($id));
        Cache::forget($this->listCacheKey()); // Invalidate list cache cũng
    }
}

// GOOD: Dùng Model Observer để tự động invalidate
// app/Observers/UserObserver.php
class UserObserver
{
    public function saved(User $user): void
    {
        Cache::forget("user.{$user->id}");
        Cache::forget('users.list');
    }

    public function deleted(User $user): void
    {
        Cache::forget("user.{$user->id}");
        Cache::forget('users.list');
    }

    public function restored(User $user): void
    {
        Cache::forget("user.{$user->id}");
    }
}

// app/Providers/AppServiceProvider.php - Đăng ký observer
public function boot(): void
{
    User::observe(UserObserver::class);
}

// GOOD: Cache tags (Redis) để group invalidation
class ProductRepository
{
    public function findById(int $id): ?Product
    {
        // Tags cho phép invalidate toàn bộ product cache cùng lúc
        return Cache::tags(['products'])->remember(
            "product.{$id}",
            3600,
            fn() => Product::with('category')->find($id)
        );
    }

    public function updatePrice(int $id, float $price): void
    {
        Product::where('id', $id)->update(['price' => $price]);

        // Invalidate tất cả cache liên quan đến products
        Cache::tags(['products'])->flush();
        // Hoặc chỉ invalidate record cụ thể:
        // Cache::tags(['products'])->forget("product.{$id}");
    }
}
```

### 7. Phòng ngừa
```php
// Test cache invalidation
/** @test */
public function cache_is_invalidated_after_update(): void
{
    $user = User::factory()->create(['role' => 'admin']);

    // Warm up cache
    $this->repository->findById($user->id);
    $this->assertTrue(Cache::has("user.{$user->id}"));

    // Update
    $this->repository->update($user->id, ['role' => 'user']);

    // Cache phải bị xóa
    $this->assertFalse(Cache::has("user.{$user->id}"));

    // Đọc lại phải trả về data mới
    $fresh = $this->repository->findById($user->id);
    $this->assertEquals('user', $fresh->role);
}

// PHPStan: Custom rule phát hiện repository write không có cache invalidation
// Có thể dùng event-driven invalidation với Horizon/Queue
```

---

## 11. Session Data Loss (concurrent write race) - HIGH

### 1. Tên
**Session Data Loss** (Mất Dữ Liệu Session Do Race Condition Ghi Đồng Thời)

### 2. Phân loại
Toàn Vẹn Dữ Liệu / Session / Concurrency

### 3. Mức nghiêm trọng
🟠 **HIGH** - Khi nhiều request đồng thời đọc và ghi session, PHP lock session file theo default nhưng một số driver (database, redis không config đúng) có thể bị race condition, dẫn đến dữ liệu session bị ghi đè hoặc mất một phần.

### 4. Vấn đề
File-based session lock session file trong suốt request, nhưng database/redis session driver mặc định không lock. Nếu 2 AJAX request cùng lúc đọc session, modify khác nhau rồi ghi lại, request sau sẽ ghi đè data của request trước.

```
SESSION CONCURRENT WRITE RACE
================================

  Request A (AJAX)         Session Store        Request B (AJAX)
       |                        |                      |
       | READ session           |                      |
       |----------------------->|                      |
       |<-- {cart: [A], step:1}-|                      |
       |                        |  READ session        |
       |                        |<---------------------|
       |                        |-- {cart:[A],step:1}->|
       |                        |                      |
       | Modify: add item B     |                      |
       | Write: {cart:[A,B],    |   Modify: step=2     |
       |         step:1}        |   Write: {cart:[A],  |
       |----------------------->|          step:2}     |
       |                        |<---------------------|
       |                        | (Request B overwrites A!)
       KẾT QUẢ:
       - Item B KHÔNG có trong cart!
       - Request A thành công nhưng thay đổi bị mất!

       Người dùng thêm item vào giỏ hàng
       -> Sau vài giây item biến mất!
       -> Trải nghiệm tệ, dữ liệu không nhất quán
```

### 5. Phát hiện
```bash
# Kiểm tra session driver
rg --type php -n "'driver'" config/session.php

# Tìm concurrent session writes (nhiều routes cùng write session)
rg --type php -n "session\(\)->put\|session\(\)->push\|\$request->session\(\)->put" app/Http/

# Tìm AJAX endpoints write session
rg --type php -n "session\(\)->put" app/Http/Controllers/ | grep -i "ajax\|api\|json"

# Tìm session lock config
rg --type php -n "block\|block_expire\|lock_expire" config/session.php

# Kiểm tra redis session config
rg --type php -n "'connection'" config/session.php
```

### 6. Giải pháp

**BAD - Session không có locking:**
```php
// config/session.php - BAD: Database driver không lock
return [
    'driver' => 'database',
    // Không có lock configuration!
    // Nhiều request đồng thời có thể ghi đè nhau
];

// app/Http/Controllers/CartController.php - BAD
class CartController extends Controller
{
    // BAD: Không xử lý concurrent writes
    public function addItem(Request $request): JsonResponse
    {
        $cart = session('cart', []);
        $cart[] = $request->input('product_id');
        session(['cart' => $cart]);
        // Nếu 2 request đồng thời: chỉ item của request cuối được lưu!

        return response()->json(['success' => true]);
    }
}
```

**GOOD - Session với locking và database-backed cart:**
```php
// config/session.php - GOOD: Block (lock) session
return [
    'driver' => env('SESSION_DRIVER', 'redis'),

    // Với Redis: block session để prevent concurrent writes
    'block'         => true,       // Bật session blocking
    'block_store'   => 'redis',    // Store để lock
    'block_expire'  => 10,         // Lock expire sau 10 giây
    'block_wait'    => 10,         // Chờ tối đa 10 giây để lấy lock

    'connection' => env('SESSION_CONNECTION', 'default'),
];

// GOOD: Dùng database thay vì session cho shopping cart
// Session phù hợp cho state nhỏ, DB phù hợp cho data quan trọng

// app/Models/Cart.php
class Cart extends Model
{
    protected $fillable = ['user_id', 'session_id', 'items'];
    protected $casts = ['items' => 'array'];
}

// app/Services/CartService.php - GOOD: Dùng DB + pessimistic lock
class CartService
{
    public function addItem(string $sessionId, int $productId, int $qty): Cart
    {
        return DB::transaction(function () use ($sessionId, $productId, $qty): Cart {
            // lockForUpdate prevent concurrent modification
            $cart = Cart::where('session_id', $sessionId)
                ->lockForUpdate()
                ->first();

            if ($cart === null) {
                $cart = Cart::create(['session_id' => $sessionId, 'items' => []]);
            }

            $items = $cart->items;
            $existing = collect($items)->firstWhere('product_id', $productId);

            if ($existing) {
                $items = collect($items)->map(function ($item) use ($productId, $qty) {
                    return $item['product_id'] === $productId
                        ? array_merge($item, ['qty' => $item['qty'] + $qty])
                        : $item;
                })->toArray();
            } else {
                $items[] = ['product_id' => $productId, 'qty' => $qty];
            }

            $cart->update(['items' => $items]);
            return $cart;
        });
    }
}

// GOOD: Nếu phải dùng session, serialize writes qua queue
class SessionWriteJob implements ShouldQueue
{
    public function __construct(
        private readonly string $sessionId,
        private readonly string $key,
        private readonly mixed $value
    ) {}

    public function handle(): void
    {
        // Queue đảm bảo sequential processing
        // Không thể concurrent!
    }
}
```

### 7. Phòng ngừa
```php
// Test concurrent session access
/** @test */
public function concurrent_cart_updates_do_not_lose_items(): void
{
    $sessionId = 'test-session-123';

    // Simulate concurrent requests
    $promises = [];
    for ($i = 1; $i <= 5; $i++) {
        $promises[] = fn() => $this->service->addItem($sessionId, $i, 1);
    }

    // Run all concurrently (in test, chạy sequentially nhưng verify result)
    foreach ($promises as $promise) {
        $promise();
    }

    $cart = Cart::where('session_id', $sessionId)->first();
    $this->assertCount(5, $cart->items, 'Tất cả 5 items phải được lưu');
}

// config/session.php best practices:
// - Dùng Redis với block=true cho concurrent-safe sessions
// - Đặt TTL hợp lý (không quá dài)
// - Lưu data quan trọng trong DB thay vì session
```

---

## 12. Seeder Idempotency (duplicate data on re-run) - MEDIUM

### 1. Tên
**Seeder Idempotency** (Seeder Không Idempotent Gây Duplicate Khi Re-run)

### 2. Phân loại
Toàn Vẹn Dữ Liệu / Database Seeder / CI/CD

### 3. Mức nghiêm trọng
🟡 **MEDIUM** - Seeder không idempotent gây ra duplicate data khi chạy lại (trong CI/CD, staging reset, hoặc fresh deploy), dẫn đến duplicate key error, logic nghiệp vụ sai (2 admin users), hoặc test data nhiễu production.

### 4. Vấn đề
Seeder thường dùng `DB::table()->insert()` hoặc `Model::create()` không kiểm tra existence. Khi chạy lại `php artisan db:seed`, dữ liệu bị duplicate hoặc gây constraint violation.

```
NON-IDEMPOTENT SEEDER
=======================

  First Run:
  users: [admin@system.com (id=1)]  <- OK

  Second Run (re-seed sau deploy):
  -> INSERT admin@system.com -> DUPLICATE KEY ERROR!
  Hoặc nếu không có unique constraint:
  users: [admin@system.com (id=1), admin@system.com (id=2)]
  -> 2 admin accounts!
  -> Logic "findOrFail(admin)" trả về 2 results!

  Trong CI/CD:
  migrate:fresh --seed (OK lần 1)
  Bug fix -> pipeline re-run
  migrate:fresh --seed (OK vì fresh)
  NHƯNG: Staging với data thật:
  db:seed (lần 2) -> DUPLICATE DATA!
```

### 5. Phát hiện
```bash
# Tìm seeder dùng insert() không có firstOrCreate/updateOrInsert
rg --type php -n "DB::table.*->insert\b\|Model::create\b" database/seeders/

# Tìm seeder không có truncate/deleteOrCreate/updateOrInsert
rg --type php -n "class.*Seeder" database/seeders/ -l | \
  xargs rg -L "firstOrCreate\|updateOrCreate\|updateOrInsert\|truncate\|upsert"

# Tìm factory calls trong seeder không idempotent
rg --type php -n "::factory\(\)->create\b" database/seeders/

# Tìm seeder được gọi trong DatabaseSeeder
rg --type php -n "\$this->call" database/seeders/DatabaseSeeder.php
```

### 6. Giải pháp

**BAD - Seeder không idempotent:**
```php
// database/seeders/RoleSeeder.php - BAD

class RoleSeeder extends Seeder
{
    public function run(): void
    {
        // BAD: Mỗi lần chạy lại sẽ insert duplicate!
        DB::table('roles')->insert([
            ['name' => 'admin', 'created_at' => now(), 'updated_at' => now()],
            ['name' => 'user',  'created_at' => now(), 'updated_at' => now()],
            ['name' => 'staff', 'created_at' => now(), 'updated_at' => now()],
        ]);
    }
}

// database/seeders/AdminUserSeeder.php - BAD
class AdminUserSeeder extends Seeder
{
    public function run(): void
    {
        // BAD: Duplicate admin user khi re-run!
        User::create([
            'name'     => 'System Admin',
            'email'    => 'admin@system.com',
            'password' => bcrypt('secret'),
            'role'     => 'admin',
        ]);
    }
}

// database/seeders/ProductSeeder.php - BAD: Factory không idempotent
class ProductSeeder extends Seeder
{
    public function run(): void
    {
        // BAD: Mỗi lần chạy tạo thêm 50 products!
        Product::factory(50)->create();
    }
}
```

**GOOD - Seeder idempotent:**
```php
// database/seeders/RoleSeeder.php - GOOD

class RoleSeeder extends Seeder
{
    public function run(): void
    {
        $roles = [
            ['name' => 'admin', 'description' => 'System Administrator'],
            ['name' => 'user',  'description' => 'Regular User'],
            ['name' => 'staff', 'description' => 'Staff Member'],
        ];

        // GOOD: updateOrInsert - idempotent, update nếu tồn tại
        foreach ($roles as $role) {
            DB::table('roles')->updateOrInsert(
                ['name' => $role['name']],         // Lookup condition
                array_merge($role, [               // Data to insert/update
                    'updated_at' => now(),
                    'created_at' => now(),
                ])
            );
        }
    }
}

// database/seeders/AdminUserSeeder.php - GOOD
class AdminUserSeeder extends Seeder
{
    public function run(): void
    {
        // GOOD: firstOrCreate - tạo chỉ khi chưa tồn tại
        User::firstOrCreate(
            ['email' => 'admin@system.com'],  // Lookup by email
            [                                  // Data chỉ dùng khi CREATE
                'name'              => 'System Admin',
                'password'          => bcrypt('secret'),
                'email_verified_at' => now(),
                'role'              => 'admin',
            ]
        );

        // GOOD: updateOrCreate - tạo hoặc update
        User::updateOrCreate(
            ['email' => 'support@system.com'],
            [
                'name'     => 'Support Staff',
                'password' => bcrypt('support123'),
                'role'     => 'staff',
            ]
        );
    }
}

// database/seeders/ProductSeeder.php - GOOD: Idempotent factory seeder
class ProductSeeder extends Seeder
{
    private const TARGET_COUNT = 50;

    public function run(): void
    {
        $currentCount = Product::count();

        if ($currentCount >= self::TARGET_COUNT) {
            $this->command->info("ProductSeeder: Đã có {$currentCount} products, bỏ qua.");
            return;
        }

        $toCreate = self::TARGET_COUNT - $currentCount;
        Product::factory($toCreate)->create();

        $this->command->info("ProductSeeder: Tạo thêm {$toCreate} products.");
    }
}

// GOOD: DatabaseSeeder với clear logging
class DatabaseSeeder extends Seeder
{
    public function run(): void
    {
        $this->call([
            RoleSeeder::class,      // Roles trước (foreign key)
            AdminUserSeeder::class, // User sau khi có roles
            CategorySeeder::class,
            ProductSeeder::class,
        ]);
    }
}

// GOOD: Seeder phân biệt production vs development
class DevelopmentDataSeeder extends Seeder
{
    public function run(): void
    {
        if (app()->isProduction()) {
            $this->command->error('DevelopmentDataSeeder KHÔNG được chạy trên production!');
            return;
        }

        // Data chỉ dùng cho development/testing
        User::factory(100)->create();
        Product::factory(200)->create();
    }
}
```

### 7. Phòng ngừa
```php
// Test seeder idempotency
/** @test */
public function seeders_are_idempotent(): void
{
    // Chạy lần 1
    $this->artisan('db:seed', ['--class' => 'RoleSeeder'])->assertSuccessful();
    $countAfterFirst = DB::table('roles')->count();

    // Chạy lần 2
    $this->artisan('db:seed', ['--class' => 'RoleSeeder'])->assertSuccessful();
    $countAfterSecond = DB::table('roles')->count();

    $this->assertEquals(
        $countAfterFirst,
        $countAfterSecond,
        'Seeder phải idempotent - chạy nhiều lần không tạo duplicate'
    );
}

// CI/CD best practice: Luôn chạy seeder sau migrate:fresh để test idempotency
// php artisan migrate:fresh --seed
// php artisan db:seed  <- Chạy lần 2 để verify idempotent

// PHPStan: Không có built-in rule, nhưng code review checklist:
// - [ ] Seeder dùng firstOrCreate/updateOrCreate/updateOrInsert thay vì create/insert
// - [ ] Seeder có guard cho production
// - [ ] Factory seeder có check count trước khi tạo thêm
```

---

## Tổng Kết

| # | Pattern | Mức độ | Giải pháp chính |
|---|---------|--------|-----------------|
| 1 | Eloquent N+1 Query | HIGH | `with()` eager loading, `withCount()` |
| 2 | Transaction Thiếu | CRITICAL | `DB::transaction()` cho multi-table write |
| 3 | Race Condition DB | HIGH | `lockForUpdate()`, atomic update với `where` |
| 4 | PDO Emulated Prepare | HIGH | `ATTR_EMULATE_PREPARES => false` |
| 5 | Date Timezone Mismatch | HIGH | Đồng nhất `app.timezone` và MySQL timezone |
| 6 | JSON Encoding Loss | MEDIUM | `JSON_THROW_ON_ERROR`, `JSON_UNESCAPED_UNICODE` |
| 7 | Character Encoding Mismatch | HIGH | `utf8mb4` charset, đồng nhất PHP và MySQL |
| 8 | Soft Delete Inconsistency | MEDIUM | `whereNull('deleted_at')` trong unique rule |
| 9 | Migration Rollback Thiếu | MEDIUM | Implement `down()` là exact reverse của `up()` |
| 10 | Cache Invalidation Sai | HIGH | `Cache::forget()` sau write, Model Observer |
| 11 | Session Data Loss | HIGH | Redis block session, dùng DB cho data quan trọng |
| 12 | Seeder Idempotency | MEDIUM | `firstOrCreate()`, `updateOrInsert()` |
