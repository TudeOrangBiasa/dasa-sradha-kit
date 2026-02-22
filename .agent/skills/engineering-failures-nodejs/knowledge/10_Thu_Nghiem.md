# Domain 10: Thử Nghiệm (Testing)

> Node.js/TypeScript patterns liên quan đến testing: Jest mocking, async tests, snapshots, E2E, database cleanup, coverage.

---

## Pattern 01: Jest Mock Isolation Thiếu

### Tên
Jest Mock Isolation Thiếu (Module Cache Leaks Between Tests)

### Phân loại
Testing / Isolation / Jest

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```typescript
// test1.test.ts
jest.mock('./db', () => ({ query: jest.fn().mockResolvedValue([]) }));
// test2.test.ts — same module cached! Mock leaks.
```

### Phát hiện

```bash
rg --type ts --type js "jest\.mock\(" -n --glob "*test*"
rg --type ts --type js "jest\.resetModules|jest\.restoreAllMocks" -n
rg --type ts --type js "beforeEach|afterEach" -n --glob "*test*"
```

### Giải pháp

❌ **BAD**
```typescript
jest.mock('./service'); // Mocked globally, leaks to other tests
const service = require('./service');
test('works', () => { service.fn.mockReturnValue(42); });
```

✅ **GOOD**
```typescript
describe('OrderService', () => {
    beforeEach(() => {
        jest.restoreAllMocks(); // Clean up mock state
    });

    afterEach(() => {
        jest.resetModules(); // Reset module cache
    });

    test('creates order', () => {
        const dbMock = jest.spyOn(db, 'query').mockResolvedValue({ id: 1 });
        const result = await createOrder({ item: 'book' });
        expect(result.id).toBe(1);
        expect(dbMock).toHaveBeenCalledWith(expect.stringContaining('INSERT'));
    });
});
```

### Phòng ngừa
- [ ] `jest.restoreAllMocks()` in `beforeEach`
- [ ] `jest.spyOn` over `jest.mock` when possible
- [ ] `jest.resetModules()` when mocking modules
- Tool: Jest, `--detectOpenHandles`

---

## Pattern 02: Async Test Timeout

### Tên
Async Test Timeout (Unhandled Async in Tests)

### Phân loại
Testing / Async / Timeout

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```typescript
test('fetches data', () => {
    fetchData().then(data => { // No return/await!
        expect(data.length).toBe(5);
    });
    // Test passes immediately — assertion never runs!
});
```

### Phát hiện

```bash
rg --type ts --type js "test\(.*\(\)" -A 3 --glob "*test*" | rg "\.then\("
rg --type ts --type js "done\)" -n --glob "*test*"
rg --type ts --type js "async.*=>" -n --glob "*test*"
```

### Giải pháp

❌ **BAD**
```typescript
test('fetches', () => {
    fetchData().then(d => expect(d).toBeDefined()); // Never awaited
});
test('callback', (done) => {
    fetchData(result => {
        expect(result).toBeDefined();
        // Forgot done() — test hangs until timeout
    });
});
```

✅ **GOOD**
```typescript
// async/await:
test('fetches data', async () => {
    const data = await fetchData();
    expect(data.length).toBe(5);
});

// Promises:
test('fetches data', () => {
    return fetchData().then(data => {
        expect(data.length).toBe(5);
    });
});

// Error testing:
test('rejects on invalid', async () => {
    await expect(fetchData(-1)).rejects.toThrow('Invalid ID');
});
```

### Phòng ngừa
- [ ] Always `async/await` or `return` promises
- [ ] Never use `done` callback — use async
- [ ] `expect.assertions(n)` to verify assertions ran
- Tool: ESLint `jest/no-done-callback`, `jest/valid-expect-in-promise`

---

## Pattern 03: Snapshot Testing Overuse

### Tên
Snapshot Testing Overuse (Snapshot Là Test Mặc Định)

### Phân loại
Testing / Snapshot / Maintenance

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```typescript
test('renders correctly', () => {
    const tree = renderer.create(<UserProfile user={mockUser} />).toJSON();
    expect(tree).toMatchSnapshot();
    // 500-line snapshot file — nobody reviews changes
    // Developers blindly update: jest --updateSnapshot
});
```

### Phát hiện

```bash
rg --type ts --type js "toMatchSnapshot|toMatchInlineSnapshot" -n --glob "*test*"
rg "\.snap$" --glob "__snapshots__/*"
```

### Giải pháp

❌ **BAD**
```typescript
expect(component).toMatchSnapshot(); // Huge, unreadable snapshots
```

✅ **GOOD**
```typescript
// Inline snapshots for small outputs:
test('formats name', () => {
    expect(formatName('alice', 'smith')).toMatchInlineSnapshot(`"Alice Smith"`);
});

// Specific assertions over snapshots:
test('renders user profile', () => {
    render(<UserProfile user={mockUser} />);
    expect(screen.getByText('Alice')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Edit' })).toBeEnabled();
});

// Snapshots only for serializable data:
test('API response shape', () => {
    const response = transformUser(rawData);
    expect(response).toEqual({
        id: expect.any(Number),
        name: 'Alice',
        email: expect.stringContaining('@'),
    });
});
```

### Phòng ngừa
- [ ] Inline snapshots for small outputs
- [ ] Specific assertions over full-tree snapshots
- [ ] Review snapshot changes in PRs
- Tool: ESLint `jest/no-large-snapshots`

---

## Pattern 04: E2E Test Flaky

### Tên
E2E Test Flaky (Unreliable Playwright/Cypress Tests)

### Phân loại
Testing / E2E / Reliability

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```typescript
await page.click('.submit-btn');
expect(await page.textContent('.result')).toBe('Success');
// Race condition — result not rendered yet
```

### Phát hiện

```bash
rg --type ts "page\.(click|fill|type)" -A 1 --glob "*e2e*" | rg -v "waitFor|locator"
rg --type ts "sleep|setTimeout" -n --glob "*e2e*"
rg --type ts "playwright|cypress" -n --glob "package.json"
```

### Giải pháp

❌ **BAD**
```typescript
await page.click('.btn');
await page.waitForTimeout(3000); // Fixed delay — slow + unreliable
const text = await page.$eval('.result', el => el.textContent);
```

✅ **GOOD**
```typescript
// Playwright — auto-waiting locators:
const submitBtn = page.getByRole('button', { name: 'Submit' });
await submitBtn.click();
await expect(page.getByText('Success')).toBeVisible({ timeout: 10000 });

// Wait for network idle:
await page.waitForLoadState('networkidle');

// Wait for specific response:
const [response] = await Promise.all([
    page.waitForResponse(resp => resp.url().includes('/api/orders')),
    submitBtn.click(),
]);
expect(response.status()).toBe(200);
```

### Phòng ngừa
- [ ] Auto-waiting locators (`getByRole`, `getByText`)
- [ ] Never `waitForTimeout` — use explicit waits
- [ ] Retry on flaky assertions
- Tool: Playwright `expect` with auto-retry

---

## Pattern 05: Test Database Cleanup

### Tên
Test Database Cleanup Thiếu (Leftover Test Data)

### Phân loại
Testing / Database / Cleanup

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```typescript
describe('UserService', () => {
    test('creates user', async () => {
        await db.user.create({ data: { name: 'Alice' } });
        // No cleanup — data persists
    });
    test('counts users', async () => {
        const count = await db.user.count();
        expect(count).toBe(0); // FAILS — Alice still exists
    });
});
```

### Phát hiện

```bash
rg --type ts "beforeEach|afterEach|beforeAll|afterAll" -A 3 --glob "*test*"
rg --type ts "truncate|deleteMany|DROP" -n --glob "*test*"
rg --type ts "prisma|knex|typeorm" -n --glob "*test*"
```

### Giải pháp

❌ **BAD**: No cleanup, or manual cleanup that misses tables

✅ **GOOD**
```typescript
// Transaction rollback (Prisma example):
import { PrismaClient } from '@prisma/client';

let prisma: PrismaClient;

beforeEach(async () => {
    prisma = new PrismaClient();
    await prisma.$executeRaw`BEGIN`;
});

afterEach(async () => {
    await prisma.$executeRaw`ROLLBACK`;
    await prisma.$disconnect();
});

// Or truncate all tables:
async function cleanDatabase(prisma: PrismaClient) {
    const tables = await prisma.$queryRaw<{ tablename: string }[]>`
        SELECT tablename FROM pg_tables WHERE schemaname = 'public'`;
    for (const { tablename } of tables) {
        await prisma.$executeRawUnsafe(`TRUNCATE TABLE "${tablename}" CASCADE`);
    }
}

afterEach(() => cleanDatabase(prisma));
```

### Phòng ngừa
- [ ] Transaction rollback per test
- [ ] `afterEach` cleanup hook
- [ ] Test database separate from development
- Tool: Prisma, Knex migrations, testcontainers

---

## Pattern 06: Environment Variable In Test

### Tên
Environment Variable Trong Test (Shared process.env)

### Phân loại
Testing / Environment / Isolation

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```typescript
test('uses API key', () => {
    process.env.API_KEY = 'test-key'; // Mutates shared process.env
    const result = callApi();
    // Next test sees 'test-key' — leaked!
});
```

### Phát hiện

```bash
rg --type ts --type js "process\.env\.\w+\s*=" -n --glob "*test*"
rg --type ts --type js "process\.env" -n --glob "*test*"
```

### Giải pháp

❌ **BAD**
```typescript
process.env.NODE_ENV = 'test'; // Never restored
```

✅ **GOOD**
```typescript
describe('config', () => {
    const originalEnv = process.env;

    beforeEach(() => {
        process.env = { ...originalEnv }; // Clone
    });

    afterEach(() => {
        process.env = originalEnv; // Restore
    });

    test('reads API key', () => {
        process.env.API_KEY = 'test-key';
        expect(getConfig().apiKey).toBe('test-key');
    });
});

// Or inject config:
function createService(config: Config) {
    return new ApiService(config);
}
test('uses config', () => {
    const svc = createService({ apiKey: 'test-key' });
});
```

### Phòng ngừa
- [ ] Save/restore `process.env` in beforeEach/afterEach
- [ ] Inject config objects instead of reading `process.env`
- [ ] `.env.test` file for test-specific values
- Tool: `dotenv`, `jest-environment-node`

---

## Pattern 07: Mock vs Stub Confusion

### Tên
Mock vs Stub Confusion (Wrong Test Double)

### Phân loại
Testing / Mocking / Design

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```typescript
const mockDb = {
    query: jest.fn().mockReturnValue([]),
    connect: jest.fn(),
    disconnect: jest.fn(),
    transaction: jest.fn(),
    // Mocking 20 methods when test only needs query()
};
```

### Phát hiện

```bash
rg --type ts "jest\.fn\(\)" -n --glob "*test*" | head -20
rg --type ts "mockReturnValue|mockResolvedValue" -n --glob "*test*"
```

### Giải pháp

❌ **BAD**
```typescript
// Over-mocking — brittle, hard to maintain
const mockService = {
    getUser: jest.fn(), createUser: jest.fn(), updateUser: jest.fn(),
    deleteUser: jest.fn(), listUsers: jest.fn(), // All methods mocked
};
```

✅ **GOOD**
```typescript
// Stub: provides canned answers (state verification)
const userRepo: UserRepo = {
    findById: async (id) => ({ id, name: 'Alice', email: 'a@b.com' }),
    // Only implement what's needed
};

// Mock: verifies interactions (behavior verification)
test('sends welcome email on signup', async () => {
    const sendEmail = jest.fn();
    const service = new UserService(userRepo, { sendEmail });
    await service.signup({ name: 'Alice', email: 'a@b.com' });
    expect(sendEmail).toHaveBeenCalledWith('a@b.com', expect.stringContaining('Welcome'));
});

// Spy: wraps real implementation
test('logs on error', async () => {
    const logSpy = jest.spyOn(logger, 'error');
    await service.process(invalidData);
    expect(logSpy).toHaveBeenCalled();
});
```

### Phòng ngừa
- [ ] Stubs for data, mocks for behavior verification
- [ ] `jest.spyOn` to wrap real implementations
- [ ] Minimal mocking — only mock boundaries
- Tool: Jest, `ts-mockito`, `sinon`

---

## Pattern 08: Integration Test Port Conflict

### Tên
Port Conflict Trong Integration Test

### Phân loại
Testing / Integration / Network

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```typescript
beforeAll(async () => {
    app = express();
    server = app.listen(3000); // Port 3000 already in use → EADDRINUSE
});
// Parallel test suites all try port 3000
```

### Phát hiện

```bash
rg --type ts "\.listen\(\d+" -n --glob "*test*"
rg --type ts "EADDRINUSE|address already in use" -n
```

### Giải pháp

❌ **BAD**
```typescript
server = app.listen(3000); // Hardcoded port
```

✅ **GOOD**
```typescript
import { AddressInfo } from 'net';

let server: Server;
let baseUrl: string;

beforeAll(async () => {
    server = app.listen(0); // OS assigns random available port
    const { port } = server.address() as AddressInfo;
    baseUrl = `http://localhost:${port}`;
});

afterAll(async () => {
    await new Promise(resolve => server.close(resolve));
});

test('GET /users', async () => {
    const res = await fetch(`${baseUrl}/users`);
    expect(res.status).toBe(200);
});
```

### Phòng ngừa
- [ ] `listen(0)` for random port assignment
- [ ] Clean server shutdown in `afterAll`
- [ ] `supertest` for in-process testing (no port needed)
- Tool: `supertest`, `got`

---

## Pattern 09: Coverage Report Misleading

### Tên
Coverage Report Misleading (Istanbul Branch Coverage)

### Phân loại
Testing / Coverage / Accuracy

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```typescript
// 95% line coverage but only 40% branch coverage:
function getDiscount(user: User): number {
    if (user.isPremium && user.yearsActive > 5) return 0.3; // Branch never tested
    if (user.isPremium) return 0.2;
    return 0;
}
// Tests only cover isPremium=true and isPremium=false
// Never test isPremium=true && yearsActive > 5
```

### Phát hiện

```bash
rg --type ts "coverageThreshold|branches" -n --glob "jest*"
rg --type ts "istanbul ignore" -n
```

### Giải pháp

❌ **BAD**
```json
{ "coverageThreshold": { "global": { "lines": 80 } } }
```

✅ **GOOD**
```json
// jest.config.ts:
{
    "coverageThreshold": {
        "global": {
            "branches": 80,
            "functions": 80,
            "lines": 80,
            "statements": 80
        }
    },
    "collectCoverageFrom": [
        "src/**/*.ts",
        "!src/**/*.d.ts",
        "!src/**/index.ts",
        "!src/**/*.mock.ts"
    ]
}
```

### Phòng ngừa
- [ ] Branch coverage threshold (not just lines)
- [ ] Exclude generated/config files
- [ ] Mutation testing for real coverage quality
- Tool: `stryker-mutator`, c8 coverage

---

## Pattern 10: Fixture Management

### Tên
Fixture Management Thiếu (Unorganized Test Data)

### Phân loại
Testing / Fixtures / Organization

### Mức nghiêm trọng
LOW 🟢

### Vấn đề

```typescript
test('processes order', () => {
    const user = { id: 1, name: 'Alice', email: 'a@b.com', role: 'admin', ... };
    const order = { id: 1, userId: 1, items: [...], total: 99.99, ... };
    // Same 20-line setup duplicated in 50 tests
});
```

### Phát hiện

```bash
rg --type ts "fixtures|factories|builders" -n --glob "*test*"
rg --type ts "const mock\w+ = \{" -n --glob "*test*"
```

### Giải pháp

❌ **BAD**: Inline test data duplicated across files

✅ **GOOD**
```typescript
// tests/fixtures/users.ts:
export function buildUser(overrides: Partial<User> = {}): User {
    return {
        id: 1,
        name: 'Alice',
        email: 'alice@example.com',
        role: 'user',
        createdAt: new Date('2024-01-01'),
        ...overrides,
    };
}

// tests/fixtures/orders.ts:
export function buildOrder(overrides: Partial<Order> = {}): Order {
    return { id: 1, userId: 1, total: 99.99, status: 'pending', ...overrides };
}

// In tests:
test('admin can cancel order', () => {
    const admin = buildUser({ role: 'admin' });
    const order = buildOrder({ status: 'pending' });
    expect(canCancel(admin, order)).toBe(true);
});
```

### Phòng ngừa
- [ ] Builder/factory functions for test data
- [ ] `tests/fixtures/` directory for shared data
- [ ] Override pattern for test-specific values
- Tool: `fishery`, `factory.ts`
