# Domain 10: Thử Nghiệm (Testing)

> PHP/Laravel patterns liên quan đến testing: PHPUnit isolation, database seeding, mocking, feature tests, Dusk E2E, coverage.

---

## Pattern 01: Test Không Isolated

### Tên
Test Không Isolated (Shared State Between Tests)

### Phân loại
Testing / Isolation / PHPUnit

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```php
class UserTest extends TestCase {
    private static $user; // Static state shared between tests!

    public function testCreate() {
        self::$user = User::create(['name' => 'Alice']);
        $this->assertNotNull(self::$user);
    }

    public function testUpdate() {
        self::$user->update(['name' => 'Bob']); // Depends on testCreate running first!
        $this->assertEquals('Bob', self::$user->name);
    }
}
```

### Phát hiện

```bash
rg --type php "static \$" -n --glob "*Test*"
rg --type php "RefreshDatabase|DatabaseTransactions" -n --glob "*Test*"
rg --type php "@depends" -n --glob "*Test*"
```

### Giải pháp

❌ **BAD**
```php
class OrderTest extends TestCase {
    // No database refresh — tests pollute each other
    public function testList() { Order::factory(5)->create(); }
    public function testCount() { $this->assertEquals(0, Order::count()); } // Fails!
}
```

✅ **GOOD**
```php
class OrderTest extends TestCase {
    use RefreshDatabase; // Wraps each test in transaction + rollback

    public function testCreateOrder(): void {
        $user = User::factory()->create();
        $order = Order::factory()->for($user)->create();
        $this->assertDatabaseHas('orders', ['user_id' => $user->id]);
    }

    public function testListOrders(): void {
        Order::factory(5)->create();
        $this->assertEquals(5, Order::count()); // Clean slate — always passes
    }
}
```

### Phòng ngừa
- [ ] `RefreshDatabase` trait in ALL database tests
- [ ] No static/shared state between tests
- [ ] No `@depends` annotation (creates coupling)
- Tool: PHPUnit, Laravel `RefreshDatabase`

---

## Pattern 02: Database Seeding Chậm

### Tên
Database Seeding Chậm (Seeding In Every Test)

### Phân loại
Testing / Performance / Database

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```php
class ReportTest extends TestCase {
    use RefreshDatabase;

    protected function setUp(): void {
        parent::setUp();
        $this->seed(); // Seeds ALL seeders — 50 tables, 10,000 rows
        // Each test: migrate + seed = 5 seconds
    }
}
// 100 tests × 5 seconds = 8+ minutes
```

### Phát hiện

```bash
rg --type php "\$this->seed\(\)" -n --glob "*Test*"
rg --type php "DatabaseSeeder|--seed" -n --glob "*Test*"
rg --type php "factory\(\)" -n --glob "*Test*"
```

### Giải pháp

❌ **BAD**
```php
$this->seed(); // Seeds everything — slow
```

✅ **GOOD**
```php
class ReportTest extends TestCase {
    use RefreshDatabase;

    public function testMonthlyReport(): void {
        // Create ONLY what this test needs:
        $user = User::factory()->create();
        $orders = Order::factory(10)
            ->for($user)
            ->state(['created_at' => now()->subMonth()])
            ->create();

        $report = (new ReportService)->monthly($user);
        $this->assertEquals(10, $report->orderCount);
    }
}

// If shared data needed, use specific seeder:
protected function setUp(): void {
    parent::setUp();
    $this->seed(RolesAndPermissionsSeeder::class); // Only what's needed
}
```

### Phòng ngừa
- [ ] Factories over seeders in tests
- [ ] Specific seeders only when shared setup needed
- [ ] `LazilyRefreshDatabase` for read-only tests
- Tool: Laravel Factories, `--parallel` flag

---

## Pattern 03: Mock Eloquent Sai

### Tên
Mock Eloquent Sai (Mocking Eloquent Models Incorrectly)

### Phân loại
Testing / Mocking / Eloquent

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```php
$mock = Mockery::mock(User::class);
$mock->shouldReceive('save')->andReturn(true);
// But Eloquent models have magic methods, query scopes, relationships
// Mock doesn't behave like real model — test passes, production breaks
```

### Phát hiện

```bash
rg --type php "Mockery::mock.*Model" -n --glob "*Test*"
rg --type php "->shouldReceive\(" -n --glob "*Test*"
rg --type php "factory\(\)->make\(\)|factory\(\)->create\(\)" -n
```

### Giải pháp

❌ **BAD**
```php
$user = Mockery::mock(User::class);
$user->shouldReceive('getAttribute')->with('name')->andReturn('Alice');
// Fragile — breaks when model changes
```

✅ **GOOD**
```php
// Use factories for model instances:
public function testUserFullName(): void {
    $user = User::factory()->make(['first_name' => 'Alice', 'last_name' => 'Smith']);
    $this->assertEquals('Alice Smith', $user->full_name);
}

// Mock repositories/services, not models:
public function testOrderService(): void {
    $repo = Mockery::mock(OrderRepository::class);
    $repo->shouldReceive('findByUser')
        ->with(1)
        ->andReturn(Order::factory(3)->make());

    $service = new OrderService($repo);
    $this->assertCount(3, $service->getUserOrders(1));
}
```

### Phòng ngừa
- [ ] Factories for model instances, mocks for services
- [ ] Mock interfaces/repositories, not Eloquent models
- [ ] Feature tests for full integration
- Tool: Mockery, Laravel Factories

---

## Pattern 04: HTTP/Feature Test Thiếu

### Tên
HTTP/Feature Test Thiếu (No Feature Tests)

### Phân loại
Testing / Feature / Integration

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```php
// Only unit tests — no HTTP test for API endpoint:
class UserServiceTest extends TestCase {
    public function testCreate() {
        $service = new UserService(new FakeRepo());
        $user = $service->create(['name' => 'Alice']);
        // Tests service but not: routes, middleware, validation, auth, response format
    }
}
```

### Phát hiện

```bash
rg --type php "->getJson\(|->postJson\(|->putJson\(|->deleteJson\(" -n
rg --type php "class.*extends.*TestCase" -n --glob "*Test*"
rg --type php "assertStatus|assertJson" -n
```

### Giải pháp

❌ **BAD**: Only unit tests, no HTTP integration tests

✅ **GOOD**
```php
class UserApiTest extends TestCase {
    use RefreshDatabase;

    public function testCreateUserValidation(): void {
        $response = $this->postJson('/api/users', []);
        $response->assertStatus(422)
            ->assertJsonValidationErrors(['name', 'email']);
    }

    public function testCreateUserSuccess(): void {
        $response = $this->postJson('/api/users', [
            'name' => 'Alice',
            'email' => 'alice@example.com',
            'password' => 'secure123',
            'password_confirmation' => 'secure123',
        ]);
        $response->assertStatus(201)
            ->assertJsonStructure(['data' => ['id', 'name', 'email']]);
        $this->assertDatabaseHas('users', ['email' => 'alice@example.com']);
    }

    public function testCreateUserRequiresAuth(): void {
        $response = $this->postJson('/api/admin/users', ['name' => 'Alice']);
        $response->assertStatus(401);
    }
}
```

### Phòng ngừa
- [ ] Feature tests for ALL API endpoints
- [ ] Test validation, auth, success, and error paths
- [ ] `assertJsonStructure` for response format
- Tool: `php artisan make:test --unit` vs `make:test`

---

## Pattern 05: Dusk E2E Flaky

### Tên
Dusk E2E Flaky (Flaky Browser Tests)

### Phân loại
Testing / E2E / Reliability

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```php
$browser->visit('/dashboard')
    ->click('.btn-submit') // Button not yet rendered
    ->assertSee('Success'); // Race condition — flaky
```

### Phát hiện

```bash
rg --type php "extends DuskTestCase" -n
rg --type php "->click\(|->type\(|->press\(" -n --glob "*Dusk*"
rg --type php "waitFor|waitUntil|pause" -n --glob "*Dusk*"
```

### Giải pháp

❌ **BAD**
```php
$browser->click('.btn')->assertSee('Done'); // No wait — flaky
$browser->pause(3000)->assertSee('Done');   // Fixed delay — slow + still flaky
```

✅ **GOOD**
```php
$browser->visit('/dashboard')
    ->waitFor('.btn-submit', 10)     // Wait for element
    ->click('.btn-submit')
    ->waitForText('Success', 10)     // Wait for result
    ->assertSee('Success');

// Or with explicit wait conditions:
$browser->waitUsing(10, 100, function () use ($browser) {
    return $browser->element('.result-count') !== null;
});
```

### Phòng ngừa
- [ ] `waitFor()` before interactions
- [ ] `waitForText()` before assertions
- [ ] Never use `pause()` — use explicit waits
- Tool: Laravel Dusk, `DatabaseMigrations` trait

---

## Pattern 06: Test Coverage Sai

### Tên
Test Coverage Report Sai (Misleading Coverage)

### Phân loại
Testing / Coverage / Accuracy

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```php
// 90% line coverage but:
// - No edge case testing
// - Interfaces/abstract classes counted
// - Generated code inflates numbers
```

### Phát hiện

```bash
rg --type php "coverageClover|coverageHtml" -n --glob "phpunit*"
rg --type php "@codeCoverageIgnore" -n
rg --type php "@covers" -n --glob "*Test*"
```

### Giải pháp

❌ **BAD**
```xml
<!-- phpunit.xml: No coverage filter -->
<coverage>
    <include><directory>./app</directory></include>
    <!-- Includes migrations, interfaces, generated code -->
</coverage>
```

✅ **GOOD**
```xml
<coverage>
    <include>
        <directory suffix=".php">./app</directory>
    </include>
    <exclude>
        <directory>./app/Console</directory>
        <directory>./app/Providers</directory>
        <file>./app/Http/Kernel.php</file>
    </exclude>
</coverage>
```

```php
// Use @covers to enforce intentional coverage:
/** @covers \App\Services\OrderService */
class OrderServiceTest extends TestCase {
    public function testCalculateTotal(): void {
        // Must actually cover OrderService methods
    }
}
```

### Phòng ngừa
- [ ] Exclude generated/boilerplate from coverage
- [ ] `@covers` annotation for targeted coverage
- [ ] Branch coverage, not just line coverage
- Tool: PHPUnit coverage, `infection` (mutation testing)

---

## Pattern 07: Factory Definition Không Realistic

### Tên
Factory Definition Không Realistic (Fake Data Mismatches Reality)

### Phân loại
Testing / Factories / Data

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```php
User::factory()->definition(): [
    'name' => 'test',
    'email' => 'test@test.com', // Same for every factory call!
    'phone' => '1234567890',    // Not realistic format
];
// Unique constraint violations, unrealistic edge cases missed
```

### Phát hiện

```bash
rg --type php "->definition\(\)" -A 10 -n --glob "*Factory*"
rg --type php "fake\(\)" -n --glob "*Factory*"
```

### Giải pháp

❌ **BAD**
```php
'email' => 'test@test.com', // Duplicate on second call
'age' => 25,                // Always same age
```

✅ **GOOD**
```php
class UserFactory extends Factory {
    public function definition(): array {
        return [
            'name' => fake()->name(),
            'email' => fake()->unique()->safeEmail(),
            'phone' => fake()->e164PhoneNumber(),
            'age' => fake()->numberBetween(18, 80),
            'created_at' => fake()->dateTimeBetween('-1 year'),
        ];
    }

    public function admin(): static {
        return $this->state(['role' => 'admin']);
    }

    public function withOrders(int $count = 3): static {
        return $this->has(Order::factory($count));
    }
}
```

### Phòng ngừa
- [ ] `fake()->unique()` for unique fields
- [ ] Realistic data ranges and formats
- [ ] State methods for common variations
- Tool: Faker library, Laravel Factories

---

## Pattern 08: Event Fake Scope Sai

### Tên
Event Fake Scope Sai (Event::fake Affects All Events)

### Phân loại
Testing / Events / Mocking

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```php
Event::fake(); // Fakes ALL events — including framework events
User::create([...]); // UserCreated event faked — observer doesn't run!
// But observer was supposed to create related records
// Test fails because related records don't exist
```

### Phát hiện

```bash
rg --type php "Event::fake\(\)" -n --glob "*Test*"
rg --type php "Event::fake\(\[" -n --glob "*Test*"
rg --type php "assertDispatched|assertNotDispatched" -n
```

### Giải pháp

❌ **BAD**
```php
Event::fake(); // Blocks ALL events including model observers
```

✅ **GOOD**
```php
// Fake only specific events:
Event::fake([OrderShipped::class, PaymentProcessed::class]);

// Or fake after setup:
$user = User::create([...]); // Observer runs normally
Event::fake(); // Only fake events from this point
$user->shipOrder();
Event::assertDispatched(OrderShipped::class);

// Or use fakeExcept:
Event::fake();
Event::fakeExcept([UserCreated::class]); // Let UserCreated through
```

### Phòng ngừa
- [ ] `Event::fake([specific events])` not `Event::fake()`
- [ ] Setup data before faking events
- [ ] Test observers separately
- Tool: Laravel Event Faking

---

## Pattern 09: Assertion Message Thiếu

### Tên
Assertion Message Thiếu (No Context in Failures)

### Phân loại
Testing / Assertions / Debugging

### Mức nghiêm trọng
LOW 🟢

### Vấn đề

```php
$this->assertTrue($result); // Failure: "Failed asserting that false is true"
// WHICH result? WHY false? No context.
```

### Phát hiện

```bash
rg --type php "assertTrue\(|assertFalse\(|assertEquals\(" -n --glob "*Test*" | rg -v "',\s*\$"
```

### Giải pháp

❌ **BAD**
```php
$this->assertTrue($user->isActive());    // "Failed asserting that false is true"
$this->assertEquals(5, count($orders));  // "Failed asserting that 3 matches 5"
```

✅ **GOOD**
```php
$this->assertTrue(
    $user->isActive(),
    "User {$user->id} should be active after verification"
);

$this->assertCount(5, $orders, 'Expected 5 orders for verified user');

// Or use specific assertions:
$this->assertDatabaseHas('users', ['id' => $user->id, 'active' => true]);
```

### Phòng ngừa
- [ ] Context messages on all assertions
- [ ] Specific assertions over generic ones
- [ ] `assertDatabaseHas` over manual DB queries
- Tool: PHPUnit assertion methods

---

## Pattern 10: Fixture Hardcoded

### Tên
Fixture Hardcoded (Hardcoded Test Data Paths)

### Phân loại
Testing / Fixtures / Maintenance

### Mức nghiêm trọng
LOW 🟢

### Vấn đề

```php
public function testImport() {
    $csv = file_get_contents('/home/dev/project/tests/data/users.csv');
    // Absolute path — fails on CI, other machines
}
```

### Phát hiện

```bash
rg --type php "file_get_contents|fopen" -n --glob "*Test*"
rg --type php "__DIR__|base_path|storage_path" -n --glob "*Test*"
```

### Giải pháp

❌ **BAD**
```php
file_get_contents('/absolute/path/test.csv');
```

✅ **GOOD**
```php
public function testImportCsv(): void {
    $csv = file_get_contents(__DIR__ . '/fixtures/users.csv');
    // Or use Laravel helpers:
    $csv = file_get_contents(base_path('tests/fixtures/users.csv'));

    // Or UploadedFile for file uploads:
    $file = UploadedFile::fake()->create('users.csv', 100, 'text/csv');
    $response = $this->postJson('/api/import', ['file' => $file]);
    $response->assertStatus(200);
}
```

### Phòng ngừa
- [ ] `__DIR__` for relative paths in tests
- [ ] `UploadedFile::fake()` for upload tests
- [ ] `tests/fixtures/` directory convention
- Tool: PHPUnit, Laravel UploadedFile
