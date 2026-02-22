# Domain 06: Thiết Kế Và Kiến Trúc (Design & Architecture)

> PHP/Laravel patterns liên quan đến thiết kế hệ thống, kiến trúc, và tổ chức code.

---

## Pattern 01: God Controller

### Tên
God Controller (Controller Chứa Business Logic)

### Phân loại
Architecture / Controller / SRP Violation

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```
class OrderController extends Controller
{
    public function store(Request $request)  ← 200+ lines
    {
        // Validation (should be FormRequest)
        $validated = $request->validate([...]);

        // Business logic (should be Service)
        $discount = $this->calculateDiscount($validated);
        $tax = $this->calculateTax($validated);
        $total = $subtotal - $discount + $tax;

        // Database operations (should be Repository)
        $order = Order::create([...]);
        $order->items()->createMany([...]);

        // Side effects (should be Event/Listener)
        Mail::to($user)->send(new OrderConfirmation($order));
        Notification::send($admin, new NewOrderNotification($order));

        // External API (should be Service)
        $payment = Stripe::charge($total);

        return response()->json($order);
    }
}
```

Controller chứa validation, business logic, DB operations, email, notifications, payment trong 1 method. Vi phạm Single Responsibility Principle, untestable.

### Phát hiện

```bash
# Tìm controllers có nhiều dòng
rg --type php "class\s+\w+Controller" -l | xargs wc -l | sort -rn

# Tìm DB operations trong controller
rg --type php "(::create|::update|::delete|->save\(\)|->delete\(\))" -n --glob "*Controller.php"

# Tìm Mail/Notification trong controller
rg --type php "(Mail::|Notification::)" -n --glob "*Controller.php"

# Tìm external API calls trong controller
rg --type php "(Http::|\bcurl\b|Guzzle|Stripe::)" -n --glob "*Controller.php"
```

### Giải pháp

❌ **BAD**: Everything in controller
```php
class OrderController extends Controller
{
    public function store(Request $request)
    {
        // 200+ lines of mixed concerns...
    }
}
```

✅ **GOOD**: Thin controller, delegate to services
```php
class OrderController extends Controller
{
    public function __construct(
        private readonly OrderService $orderService
    ) {}

    public function store(StoreOrderRequest $request): JsonResponse
    {
        $order = $this->orderService->createOrder(
            $request->validated()
        );
        return response()->json(OrderResource::make($order), 201);
    }
}

class OrderService
{
    public function createOrder(array $data): Order
    {
        $order = DB::transaction(function () use ($data) {
            $order = $this->repository->create($data);
            $this->applyDiscount($order);
            return $order;
        });

        event(new OrderCreated($order));
        return $order;
    }
}
```

### Phòng ngừa

- [ ] Controller methods < 20 lines
- [ ] Validation → FormRequest classes
- [ ] Business logic → Service classes
- [ ] Side effects → Events/Listeners
- [ ] DB operations → Repository or Service
- Tool: `phpstan` — enforce architecture rules

---

## Pattern 02: Service Locator Anti-Pattern

### Tên
Service Locator Anti-Pattern (Dùng app() Thay Vì DI)

### Phân loại
Architecture / DI / Anti-Pattern

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```
class OrderService
{
    public function process()
    {
        $repo = app()->make(OrderRepository::class);  ← Service Locator
        $mailer = app('mailer');                       ← Service Locator
        $cache = resolve(CacheManager::class);         ← Service Locator
             │
             ├── Hidden dependencies (không thấy trong constructor)
             ├── Untestable (khó mock app() container)
             ├── Tight coupling to Laravel container
             └── Impossible to know dependencies từ class signature
    }
}
```

### Phát hiện

```bash
# Tìm app() calls
rg --type php "app\(\)" -n

# Tìm app()->make() pattern
rg --type php "app\(\)->make\(" -n

# Tìm resolve() helper
rg --type php "\bresolve\(" -n

# Tìm app() trong non-service-provider files
rg --type php "app\(|resolve\(" -n --glob "!*ServiceProvider*" --glob "!*bootstrap*"
```

### Giải pháp

❌ **BAD**: Service locator
```php
class OrderService
{
    public function createOrder(array $data): Order
    {
        $repo = app()->make(OrderRepository::class);
        $payment = resolve(PaymentGateway::class);
        $notifier = app('notification');

        $order = $repo->create($data);
        $payment->charge($order->total);
        $notifier->send($order->user, new OrderCreated($order));
        return $order;
    }
}
```

✅ **GOOD**: Constructor injection
```php
class OrderService
{
    public function __construct(
        private readonly OrderRepository $repository,
        private readonly PaymentGateway $payment,
        private readonly NotificationService $notifier,
    ) {}

    public function createOrder(array $data): Order
    {
        $order = $this->repository->create($data);
        $this->payment->charge($order->total);
        $this->notifier->send($order->user, new OrderCreated($order));
        return $order;
    }
}
```

### Phòng ngừa

- [ ] ALWAYS constructor injection
- [ ] app()/resolve() chỉ trong ServiceProvider
- [ ] Dependencies visible trong constructor
- [ ] Easy to mock trong tests
- Tool: `phpstan` rule: `disallowedFunctionCalls`

---

## Pattern 03: Anemic Domain Model

### Tên
Anemic Domain Model (Entity Chỉ Có Getter/Setter)

### Phân loại
Architecture / Domain / DDD

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```
class Order (Eloquent Model)
│
├── id, status, total, user_id  ← Data only
├── getStatus(), setStatus()     ← Getters/Setters only
├── user(), items()              ← Relationships
└── NO business logic!           ← Anemic!

class OrderService
│
├── calculateTotal(Order $order)     ← Logic ngoài entity
├── applyDiscount(Order $order)      ← Logic ngoài entity
├── canBeCancelled(Order $order)     ← Logic ngoài entity
└── markAsShipped(Order $order)      ← Logic ngoài entity
    │
    └── Entity = data bag, Service = logic bag
        OOP bị phá vỡ: data và behavior tách rời
```

### Phát hiện

```bash
# Tìm models chỉ có relationships (không có methods)
rg --type php "class\s+\w+\s+extends\s+Model" -l | xargs -I{} sh -c \
  'echo "=== {} ===" && rg "public function" {} | wc -l'

# Tìm services thao tác trực tiếp trên model properties
rg --type php "->(status|state|total)\s*=" -n --glob "*Service.php"

# Tìm getter/setter only models
rg --type php "function (get|set|is)\w+\(" -n --glob "**/Models/*.php"
```

### Giải pháp

❌ **BAD**: Anemic model + fat service
```php
// Model: no behavior
class Order extends Model
{
    protected $fillable = ['status', 'total', 'user_id'];
}

// Service: all logic
class OrderService
{
    public function cancel(Order $order): void
    {
        if ($order->status !== 'pending') {
            throw new \Exception('Cannot cancel');
        }
        $order->status = 'cancelled';
        $order->save();
    }
}
```

✅ **GOOD**: Rich domain model
```php
class Order extends Model
{
    protected $fillable = ['status', 'total', 'user_id'];

    public function cancel(): void
    {
        if (!$this->canBeCancelled()) {
            throw new OrderCannotBeCancelledException($this);
        }
        $this->status = OrderStatus::Cancelled;
        $this->cancelled_at = now();
        $this->save();

        event(new OrderCancelled($this));
    }

    public function canBeCancelled(): bool
    {
        return $this->status === OrderStatus::Pending
            && $this->created_at->diffInHours(now()) < 24;
    }

    public function calculateTotal(): Money
    {
        return $this->items->sum(fn ($item) => $item->subtotal());
    }
}
```

### Phòng ngừa

- [ ] Business rules thuộc về entity/model
- [ ] Service orchestrate, model calculate
- [ ] "Tell, don't ask" — model tự thay đổi state
- [ ] Value objects cho domain concepts
- Ref: Domain-Driven Design — Rich Domain Model

---

## Pattern 04: Fat Model

### Tên
Fat Model (Model Chứa Tất Cả Logic)

### Phân loại
Architecture / Model / SRP Violation

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```
class User extends Model  ← 1000+ lines!
│
├── Relationships (20+ methods)
├── Accessors/Mutators (15+ methods)
├── Scopes (10+ methods)
├── Business logic (30+ methods)
│   ├── calculateAge()
│   ├── canAccessFeature()
│   ├── sendNotification()      ← Should be service
│   ├── generateReport()        ← Should be service
│   ├── processPayment()        ← Should be service
│   └── syncWithExternalAPI()   ← Should be service
├── Query builders (5+ methods)
└── Validation rules (static)
```

Ngược lại Anemic Model: model chứa QUÁ NHIỀU logic. Model trở thành god class, khó test từng phần.

### Phát hiện

```bash
# Tìm model files lớn
rg --type php "class\s+\w+\s+extends\s+Model" -l | xargs wc -l | sort -rn

# Tìm models có quá nhiều methods
rg --type php "public function" --glob "**/Models/*.php" -c | sort -t: -k2 -rn

# Tìm non-Eloquent concerns trong models
rg --type php "(Mail::|Http::|Cache::|Queue::)" -n --glob "**/Models/*.php"
```

### Giải pháp

❌ **BAD**: Everything in model
```php
class User extends Model
{
    // 1000+ lines...
    public function sendWelcomeEmail() { Mail::send(...); }
    public function generateInvoice() { /* PDF generation */ }
    public function syncWithCRM() { Http::post('crm.api/sync', ...); }
}
```

✅ **GOOD**: Extract concerns to traits, services, actions
```php
// Model: core domain logic + relationships
class User extends Model
{
    use HasRoles, HasSubscription, Searchable;

    public function orders(): HasMany { return $this->hasMany(Order::class); }
    public function canAccessFeature(string $feature): bool { /* domain logic */ }
}

// Service: orchestration
class UserNotificationService
{
    public function sendWelcome(User $user): void { /* ... */ }
}

// Action: single purpose
class GenerateUserInvoice
{
    public function execute(User $user, Period $period): Invoice { /* ... */ }
}
```

### Phòng ngừa

- [ ] Model < 500 lines
- [ ] Extract: traits cho reusable behaviors
- [ ] Extract: services cho orchestration
- [ ] Extract: actions cho single-purpose operations
- [ ] Model keeps: relationships, scopes, accessors, core domain logic

---

## Pattern 05: Static Method Abuse

### Tên
Static Method Abuse (Lạm Dụng Static Methods)

### Phân loại
Architecture / Testability / OOP

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```
class PriceCalculator
{
    public static function calculate(Order $order): float
    {
        $discount = DiscountHelper::getDiscount($order);  ← Static call
        $tax = TaxService::calculateTax($order);          ← Static call
        $shipping = ShippingCost::estimate($order);       ← Static call
             │
             ├── Cannot mock: PriceCalculator::calculate() in tests
             ├── Hidden dependencies: không biết DiscountHelper, TaxService, ShippingCost
             ├── Tight coupling: thay đổi TaxService ảnh hưởng tất cả callers
             └── Cannot inject alternatives (different tax rules per country)
    }
}
```

### Phát hiện

```bash
# Tìm static method calls
rg --type php "\w+::\w+\(" -n --glob "!*Facade*" --glob "!*Test*"

# Tìm static method declarations (không phải trong tests)
rg --type php "public static function" -n --glob "!*Test*"

# Tìm helper classes toàn static
rg --type php "class\s+\w+Helper" -l

# Count static calls per file
rg --type php "::" -c --glob "!*Facade*" | sort -t: -k2 -rn
```

### Giải pháp

❌ **BAD**: Static everywhere
```php
class ReportGenerator
{
    public static function generate(string $type): Report
    {
        $data = DataFetcher::fetch($type);
        $formatted = Formatter::format($data);
        return PDFGenerator::create($formatted);
    }
}
// Cannot mock DataFetcher, Formatter, PDFGenerator in tests
```

✅ **GOOD**: Instance methods with DI
```php
class ReportGenerator
{
    public function __construct(
        private readonly DataFetcher $fetcher,
        private readonly Formatter $formatter,
        private readonly PDFGenerator $pdf,
    ) {}

    public function generate(string $type): Report
    {
        $data = $this->fetcher->fetch($type);
        $formatted = $this->formatter->format($data);
        return $this->pdf->create($formatted);
    }
}
```

### Phòng ngừa

- [ ] Static chỉ cho: pure functions, factory methods, constants
- [ ] Instance methods + DI cho everything else
- [ ] Laravel Facades: OK trong application code, avoid trong library
- [ ] Test: nếu không thể mock → refactor to instance
- Tool: `phpstan` — rule against static calls

---

## Pattern 06: Global State

### Tên
Global State (Biến Toàn Cục Chia Sẻ State)

### Phân loại
Architecture / State / Side Effects

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```
class Config
{
    public static array $settings = [];  ← Global mutable state

    public static function set(string $key, mixed $value): void
    {
        self::$settings[$key] = $value;
    }
}

// Request A: Config::set('currency', 'USD');
// Request B: Config::set('currency', 'EUR');
// Race condition trong PHP-FPM long-running processes!

$_GLOBALS['current_user'] = $user;  ← Super global
global $db;                          ← Global keyword
```

### Phát hiện

```bash
# Tìm $GLOBALS
rg --type php "\\\$_?GLOBALS" -n

# Tìm global keyword
rg --type php "\bglobal\s+\\\$" -n

# Tìm static mutable properties
rg --type php "public static\s+(array|\w+)\s+\\\$" -n

# Tìm static property assignments
rg --type php "self::\\\$\w+\s*=" -n
```

### Giải pháp

❌ **BAD**: Global/static mutable state
```php
class AppState
{
    public static ?User $currentUser = null;
    public static string $locale = 'en';
    public static array $cache = [];
}

// Anywhere in code:
AppState::$currentUser = $user;  // Side effect!
```

✅ **GOOD**: Scoped state via DI
```php
class RequestContext
{
    public function __construct(
        private readonly User $user,
        private readonly string $locale,
    ) {}

    public function user(): User { return $this->user; }
    public function locale(): string { return $this->locale; }
}

// Bind per-request in ServiceProvider
$this->app->scoped(RequestContext::class, function ($app) {
    return new RequestContext(
        user: auth()->user(),
        locale: app()->getLocale(),
    );
});
```

### Phòng ngừa

- [ ] NEVER dùng `global`, `$GLOBALS`, static mutable properties
- [ ] Scoped bindings trong Laravel container
- [ ] Immutable value objects cho shared state
- [ ] Request-scoped context via middleware
- Tool: `phpstan` — ban global usage rules

---

## Pattern 07: Circular Dependency

### Tên
Circular Dependency (Phụ Thuộc Vòng Tròn)

### Phân loại
Architecture / Dependency / Coupling

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```
class UserService                class OrderService
│                                │
│ depends on OrderService ──────►│
│◄────── depends on UserService  │
│                                │
└── Cannot instantiate!          └── Cannot instantiate!
    Laravel DI: circular dependency detected
    "Target [UserService] is not instantiable while building [OrderService]"
```

### Phát hiện

```bash
# Tìm constructor dependencies
rg --type php "__construct\(" -A 10 --glob "*Service.php" -n

# Tìm mutual imports
rg --type php "use App\\Services\\" --glob "*Service.php" -n

# Check Laravel sẽ throw error tại runtime
# "Circular dependency detected"
```

### Giải pháp

❌ **BAD**: Circular dependency
```php
class UserService
{
    public function __construct(private OrderService $orders) {}
    public function getUserOrders(int $userId): Collection { }
}

class OrderService
{
    public function __construct(private UserService $users) {}
    public function getOrderUser(int $orderId): User { }
}
```

✅ **GOOD**: Extract shared interface or mediator
```php
// Option 1: Interface at boundary
interface OrderQueryInterface
{
    public function getOrdersByUserId(int $userId): Collection;
}

class UserService
{
    public function __construct(private OrderQueryInterface $orders) {}
}

class OrderService implements OrderQueryInterface
{
    // No dependency on UserService
    public function getOrdersByUserId(int $userId): Collection { }
}

// Option 2: Event-driven
class UserService
{
    public function deleteUser(int $userId): void
    {
        event(new UserDeleted($userId)); // OrderService listens
    }
}
```

### Phòng ngừa

- [ ] Dependency graph: directed acyclic (no cycles)
- [ ] Extract shared interface to break cycle
- [ ] Events/Listeners cho cross-domain communication
- [ ] Mediator pattern cho complex interactions
- Tool: `deptrac` — architecture dependency checker

---

## Pattern 08: Config In Code

### Tên
Config In Code (Hardcode Config Thay Vì Env)

### Phân loại
Architecture / Configuration / 12-Factor

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```
class PaymentService
{
    private string $apiKey = 'sk_live_abc123';      ← Hardcoded secret!
    private string $apiUrl = 'https://api.stripe.com'; ← Hardcoded URL
    private int $timeout = 30;                       ← Hardcoded value
    private string $currency = 'USD';                ← Hardcoded default
}
```

### Phát hiện

```bash
# Tìm hardcoded URLs
rg --type php "https?://[a-zA-Z0-9]" -n --glob "!*config*" --glob "!*test*"

# Tìm hardcoded API keys
rg --type php "(api_key|apiKey|secret|token)\s*=\s*['\"]" -n --glob "!*.env*"

# Tìm hardcoded numbers (magic numbers)
rg --type php "=\s*[0-9]{2,}" -n --glob "*Service.php"

# Tìm thiếu env() hoặc config() calls
rg --type php "class\s+\w+Service" -l | xargs rg -L "(env\(|config\()"
```

### Giải pháp

❌ **BAD**: Hardcoded config
```php
class EmailService
{
    public function send(string $to, string $body): void
    {
        $transport = new SmtpTransport('smtp.gmail.com', 587);
        $transport->setUsername('app@gmail.com');
        $transport->setPassword('my-password-123');
    }
}
```

✅ **GOOD**: Config via .env and config files
```php
// .env
MAIL_HOST=smtp.gmail.com
MAIL_PORT=587
MAIL_USERNAME=app@gmail.com
MAIL_PASSWORD=encrypted-password

// config/mail.php
return [
    'host' => env('MAIL_HOST', 'localhost'),
    'port' => env('MAIL_PORT', 587),
    'username' => env('MAIL_USERNAME'),
    'password' => env('MAIL_PASSWORD'),
];

// Service
class EmailService
{
    public function __construct(
        private readonly array $config = []
    ) {
        $this->config = config('mail');
    }
}
```

### Phòng ngừa

- [ ] ALL config via `.env` + config files
- [ ] NEVER hardcode secrets, URLs, credentials
- [ ] `config:cache` trong production
- [ ] env() chỉ trong config files, KHÔNG trong app code
- Tool: `phpstan` — custom rule cho hardcoded values

---

## Pattern 09: Magic Method Overuse

### Tên
Magic Method Overuse (Lạm Dụng __get, __call)

### Phân loại
Architecture / PHP / Readability

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```
class DynamicConfig
{
    private array $data = [];

    public function __get(string $name): mixed
    {
        return $this->data[$name] ?? null;  ← Property không tồn tại → null
    }

    public function __call(string $name, array $args): mixed
    {
        return $this->data[$name]($args);   ← Method không tồn tại → error?
    }
}

$config->databse_url;  ← Typo! Returns null, no error
$config->nonExistentMethod();  ← Runtime error
// IDE: no autocomplete, no type hints, no refactoring
```

### Phát hiện

```bash
# Tìm magic methods
rg --type php "function __get\(|function __set\(|function __call\(|function __callStatic\(" -n

# Tìm __toString
rg --type php "function __toString\(" -n

# Tìm overuse (nhiều magic methods trong 1 class)
rg --type php "function __(get|set|call|isset|unset)\(" -l | xargs -I{} sh -c \
  'echo "=== {} ===" && rg "function __" {} | wc -l'
```

### Giải pháp

❌ **BAD**: Magic methods che giấu behavior
```php
class Settings
{
    private array $data;
    public function __get($key) { return $this->data[$key] ?? null; }
    public function __set($key, $val) { $this->data[$key] = $val; }
    public function __isset($key) { return isset($this->data[$key]); }
}
```

✅ **GOOD**: Explicit typed properties
```php
class Settings
{
    public function __construct(
        public readonly string $appName,
        public readonly string $appUrl,
        public readonly int $maxRetries,
        public readonly bool $debugMode,
    ) {}

    public static function fromArray(array $data): self
    {
        return new self(
            appName: $data['app_name'] ?? 'MyApp',
            appUrl: $data['app_url'] ?? 'http://localhost',
            maxRetries: $data['max_retries'] ?? 3,
            debugMode: $data['debug_mode'] ?? false,
        );
    }
}
```

### Phòng ngừa

- [ ] Explicit typed properties thay __get/__set
- [ ] DTOs/Value Objects cho data containers
- [ ] Magic methods chỉ khi thực sự cần (ORMs, proxies)
- [ ] PHPDoc `@property` nếu phải dùng magic
- Tool: `phpstan` — level 6+ catches magic method issues

---

## Pattern 10: Repository Pattern Sai

### Tên
Repository Pattern Sai (Repository Leaking Query Builder)

### Phân loại
Architecture / Repository / Abstraction

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```
class UserRepository
{
    public function query(): Builder
    {
        return User::query();  ← Returns Eloquent Builder!
    }

    public function findActive(): Builder
    {
        return User::where('active', true);  ← Returns Builder, not Collection!
    }
}

// Controller:
$users = $repo->findActive()->where('role', 'admin')->paginate(10);
                              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                              Caller builds query → Repository không abstract gì cả
                              Might as well use Eloquent directly
```

### Phát hiện

```bash
# Tìm repositories return Builder
rg --type php "return.*::query\(\)|return.*::where\(" -n --glob "*Repository*"

# Tìm repository methods return type Builder
rg --type php ":\s*Builder" -n --glob "*Repository*"

# Tìm chaining sau repository calls
rg --type php "\->repository.*\->where\(|\->repo.*\->where\(" -n
```

### Giải pháp

❌ **BAD**: Repository returns query builder
```php
class UserRepository
{
    public function findActive(): Builder
    {
        return User::where('active', true);
    }
}

// Caller builds query — leaky abstraction
$users = $repo->findActive()->where('age', '>', 18)->get();
```

✅ **GOOD**: Repository returns concrete results
```php
class UserRepository
{
    public function findActive(array $filters = []): Collection
    {
        $query = User::where('active', true);

        if (isset($filters['min_age'])) {
            $query->where('age', '>=', $filters['min_age']);
        }
        if (isset($filters['role'])) {
            $query->where('role', $filters['role']);
        }

        return $query->get();
    }

    public function findActiveAdmin(): Collection
    {
        return User::where('active', true)
            ->where('role', 'admin')
            ->get();
    }
}
```

### Phòng ngừa

- [ ] Repository returns Collection, Model, hoặc paginated results
- [ ] NEVER return Builder từ repository
- [ ] Specific query methods cho specific use cases
- [ ] Consider: nếu wrapping Eloquent 1:1 → có cần Repository không?
- Ref: Repository Pattern vs Active Record trade-offs

---

## Pattern 11: Event Listener Tight Coupling

### Tên
Event Listener Tight Coupling (Listener Phụ Thuộc Concrete)

### Phân loại
Architecture / Events / Coupling

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```
class SendOrderConfirmation
{
    public function handle(OrderCreated $event)
    {
        $order = Order::find($event->orderId);        ← Direct DB query
        $user = User::find($order->user_id);           ← Direct DB query
        $items = OrderItem::where('order_id', $order->id)->get();

        Mail::to($user->email)->send(
            new OrderConfirmationMail($order, $items)
        );
             │
             └── Listener coupled to: Order, User, OrderItem models
                 + Mail facade + Mailable class
                 Testing requires DB + Mail fake
    }
}
```

### Phát hiện

```bash
# Tìm listeners với direct model queries
rg --type php "(::find|::where|::query)" -n --glob "*Listener*"

# Tìm listeners với nhiều dependencies
rg --type php "use App\\Models\\" -n --glob "*Listener*"

# Tìm event classes thiếu data
rg --type php "class\s+\w+Event|class\s+\w+Created|class\s+\w+Updated" -A 10 -n
```

### Giải pháp

❌ **BAD**: Listener queries everything
```php
class SendOrderConfirmation
{
    public function handle(OrderCreated $event)
    {
        $order = Order::with('items', 'user')->find($event->orderId);
        Mail::to($order->user->email)->send(new OrderMail($order));
    }
}
```

✅ **GOOD**: Event carries needed data, Listener is thin
```php
// Rich event with needed data
class OrderCreated
{
    public function __construct(
        public readonly int $orderId,
        public readonly string $userEmail,
        public readonly string $userName,
        public readonly float $total,
    ) {}
}

// Thin listener
class SendOrderConfirmation
{
    public function __construct(
        private readonly MailerInterface $mailer
    ) {}

    public function handle(OrderCreated $event): void
    {
        $this->mailer->send(
            to: $event->userEmail,
            mailable: new OrderConfirmationMail(
                userName: $event->userName,
                total: $event->total,
            ),
        );
    }
}
```

### Phòng ngừa

- [ ] Events carry sufficient data (no DB queries in listener)
- [ ] Listener has single responsibility
- [ ] DI trong listener constructor
- [ ] Queue listeners cho heavy operations
- Tool: `phpstan` — enforce listener structure

---

## Pattern 12: Middleware Order Sai

### Tên
Middleware Order Sai (Incorrect Middleware Ordering)

### Phân loại
Architecture / HTTP / Middleware Pipeline

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```
HTTP Request Pipeline:

  Request
    │
    ▼
  RateLimiting ← Should be FIRST (reject early)
    │
    ▼
  Authentication ← Should be BEFORE authorization
    │
    ▼
  Authorization ← AFTER authentication
    │
    ▼
  Controller

WRONG ORDER:
  Request → Auth → RateLimit → Controller
                   ^^^^^^^^^^
                   Rate limit SAU auth = unauthenticated requests
                   bypass rate limit → DDoS vector
```

### Phát hiện

```bash
# Tìm middleware registration order
rg --type php "middleware" -n --glob "*Kernel.php"

# Tìm route middleware groups
rg --type php "middlewareGroups|routeMiddleware" -A 20 -n --glob "*Kernel.php"

# Tìm inline middleware trong routes
rg --type php "->middleware\(" -n --glob "*routes*"

# Tìm middleware priority
rg --type php "middlewarePriority" -A 15 -n
```

### Giải pháp

❌ **BAD**: Wrong middleware order
```php
// Kernel.php
protected $middlewareGroups = [
    'api' => [
        'auth:sanctum',      // Auth first — bad!
        'throttle:60,1',     // Rate limit after auth
        // Unauthenticated requests not rate limited!
    ],
];
```

✅ **GOOD**: Correct middleware order
```php
protected $middlewareGroups = [
    'api' => [
        \Illuminate\Http\Middleware\HandleCors::class,      // 1. CORS
        'throttle:api',                                      // 2. Rate limiting (early reject)
        \Illuminate\Routing\Middleware\SubstituteBindings::class,
    ],
];

// Route groups with correct auth order
Route::middleware(['auth:sanctum'])->group(function () {
    // 3. Authentication
    Route::middleware(['can:admin'])->group(function () {
        // 4. Authorization (after auth)
    });
});

// Middleware priority (Laravel auto-sorts based on this)
protected $middlewarePriority = [
    \Illuminate\Session\Middleware\StartSession::class,
    \Illuminate\Auth\Middleware\Authenticate::class,
    \Illuminate\Auth\Middleware\Authorize::class,
];
```

### Phòng ngừa

- [ ] Order: CORS → Rate Limit → Auth → Authorization → Validation
- [ ] Rate limiting BEFORE authentication
- [ ] Authentication BEFORE authorization
- [ ] Use `$middlewarePriority` để enforce order
- [ ] Test: unauthenticated requests ARE rate limited
- Ref: OWASP API Security — Rate Limiting
