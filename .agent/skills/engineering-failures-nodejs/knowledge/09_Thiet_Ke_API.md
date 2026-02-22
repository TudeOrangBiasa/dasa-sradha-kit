# Domain 09: Thiết Kế API (API Design)

> Node.js/TypeScript patterns liên quan đến API design: REST, validation, GraphQL N+1, response format, versioning.

---

## Pattern 01: REST Conventions Vi Phạm

### Tên
REST Conventions Vi Phạm (Verb In URL, Wrong Method)

### Phân loại
API Design / REST / Convention

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```typescript
app.post('/api/getUsers', getUsers);
app.get('/api/deleteUser/:id', deleteUser);
app.post('/api/users/update/:id', updateUser);
```

### Phát hiện

```bash
rg --type ts --type js "app\.(get|post|put|delete|patch)\(" -n
rg --type ts --type js "router\.(get|post|put|delete)\(" -n
```

### Giải pháp

❌ **BAD**
```typescript
app.post('/api/getUsers', ...);
app.get('/api/deleteUser/:id', ...);
```

✅ **GOOD**
```typescript
const router = express.Router();
router.get('/users', listUsers);         // GET    /api/users
router.post('/users', createUser);       // POST   /api/users
router.get('/users/:id', getUser);       // GET    /api/users/:id
router.put('/users/:id', updateUser);    // PUT    /api/users/:id
router.delete('/users/:id', deleteUser); // DELETE /api/users/:id
app.use('/api', router);
```

### Phòng ngừa
- [ ] Nouns in URLs, verbs via HTTP methods
- [ ] Plural resource names
- [ ] Consistent naming convention
- Tool: OpenAPI linter

---

## Pattern 02: GraphQL N+1

### Tên
GraphQL N+1 (DataLoader Thiếu)

### Phân loại
API Design / GraphQL / Performance

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```typescript
// GraphQL resolver:
const resolvers = {
    Post: {
        author: (post) => db.users.findById(post.authorId),
        // 100 posts → 100 separate DB queries for authors!
    }
};
```

### Phát hiện

```bash
rg --type ts --type js "DataLoader|dataloader" -n
rg --type ts --type js "resolvers.*=.*\{" -A 10 | rg "findById|findOne"
```

### Giải pháp

❌ **BAD**
```typescript
author: async (post) => {
    return await db.users.findById(post.authorId); // N queries
}
```

✅ **GOOD**
```typescript
import DataLoader from 'dataloader';

// Create per-request DataLoader:
const userLoader = new DataLoader<string, User>(async (ids) => {
    const users = await db.users.findByIds([...ids]); // 1 query for all!
    const userMap = new Map(users.map(u => [u.id, u]));
    return ids.map(id => userMap.get(id)!);
});

const resolvers = {
    Post: {
        author: (post) => userLoader.load(post.authorId), // Batched!
    },
};
```

### Phòng ngừa
- [ ] DataLoader for ALL relationship resolvers
- [ ] Create new DataLoader per request (caching scope)
- [ ] Monitor query count with Apollo tracing
- Tool: `dataloader` npm package

---

## Pattern 03: Request Validation Thiếu

### Tên
Request Validation Thiếu (No Input Validation)

### Phân loại
API Design / Validation / Security

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```typescript
app.post('/users', async (req, res) => {
    await db.users.create(req.body); // No validation! Any fields accepted
});
```

### Phát hiện

```bash
rg --type ts --type js "req\.body" -n | rg -v "validate|schema|parse|zod|joi"
rg --type ts --type js "z\.object|Joi\.object|yup\.object" -n
```

### Giải pháp

❌ **BAD**
```typescript
app.post('/users', async (req, res) => {
    const user = await db.create(req.body); // Raw input!
});
```

✅ **GOOD**
```typescript
import { z } from 'zod';

const createUserSchema = z.object({
    name: z.string().min(2).max(100),
    email: z.string().email(),
    age: z.number().int().min(0).max(150).optional(),
});

app.post('/users', async (req, res) => {
    const result = createUserSchema.safeParse(req.body);
    if (!result.success) {
        return res.status(400).json({
            error: { code: 'VALIDATION_ERROR', details: result.error.issues },
        });
    }
    const user = await db.create(result.data); // Typed and validated
    res.status(201).json({ data: user });
});
```

### Phòng ngừa
- [ ] Zod/Joi for ALL endpoint validation
- [ ] Validate at API boundary
- [ ] Return structured validation errors
- Tool: `zod`, `joi`, `class-validator`

---

## Pattern 04: Response Format Inconsistent

### Tên
Response Format Inconsistent (Different Formats Per Endpoint)

### Phân loại
API Design / Response / Consistency

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```
GET /users/1   → { id: 1, name: "John" }
GET /users/999 → "User not found"
POST /users    → { error: "validation failed" }
GET /products  → [{ id: 1 }]
```

### Phát hiện

```bash
rg --type ts --type js "res\.(json|send)\(" -n
rg --type ts --type js "res\.status\(\d+\)" -n
```

### Giải pháp

❌ **BAD**
```typescript
res.send('Not found');
res.json(user);
res.json({ error: 'Failed' });
```

✅ **GOOD**
```typescript
interface ApiResponse<T> {
    data?: T;
    error?: { code: string; message: string; details?: unknown };
    meta?: { total: number; page: number; limit: number };
}

function success<T>(res: Response, data: T, status = 200) {
    res.status(status).json({ data });
}

function error(res: Response, status: number, code: string, message: string) {
    res.status(status).json({ error: { code, message } });
}

// Usage:
success(res, user);
success(res, user, 201);
error(res, 404, 'NOT_FOUND', 'User not found');
```

### Phòng ngừa
- [ ] Consistent response envelope
- [ ] Helper functions for success/error responses
- [ ] Always JSON Content-Type
- Tool: OpenAPI spec validation

---

## Pattern 05: API Versioning Thiếu

### Tên
API Versioning Thiếu (No Version Strategy)

### Phân loại
API Design / Versioning / Breaking Change

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```typescript
app.use('/api/users', userRoutes);
// Breaking change → all clients break immediately
```

### Phát hiện

```bash
rg --type ts --type js "/api/v\d" -n
rg --type ts --type js "version" -i -n --glob "*route*"
```

### Giải pháp

❌ **BAD**
```typescript
app.use('/api', routes); // No versioning
```

✅ **GOOD**
```typescript
app.use('/api/v1', v1Routes);
app.use('/api/v2', v2Routes);

// Shared logic with version-specific transformers:
// src/routes/v1/users.ts
// src/routes/v2/users.ts
```

### Phòng ngừa
- [ ] Version API from day one
- [ ] URL path versioning (simplest)
- [ ] Deprecation headers for old versions

---

## Pattern 06: Rate Limiting Thiếu

### Tên
Rate Limiting Thiếu (No Request Throttling)

### Phân loại
API Design / Security / DDoS

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```typescript
app.post('/api/login', loginHandler); // No rate limit → brute force
```

### Phát hiện

```bash
rg --type ts --type js "rate.*limit|rateLimit|express-rate-limit" -i -n
rg --type ts --type js "429|TooManyRequests" -n
```

### Giải pháp

❌ **BAD**
```typescript
app.post('/login', loginHandler); // Unlimited attempts
```

✅ **GOOD**
```typescript
import rateLimit from 'express-rate-limit';

const apiLimiter = rateLimit({
    windowMs: 60 * 1000,
    max: 100,
    standardHeaders: true,
    message: { error: { code: 'RATE_LIMITED', message: 'Too many requests' } },
});

const loginLimiter = rateLimit({
    windowMs: 15 * 60 * 1000,
    max: 5, // 5 attempts per 15 minutes
    skipSuccessfulRequests: true,
});

app.use('/api', apiLimiter);
app.post('/api/login', loginLimiter, loginHandler);
```

### Phòng ngừa
- [ ] Rate limit all API routes
- [ ] Stricter limits on auth endpoints
- [ ] Redis store for distributed rate limiting
- Tool: `express-rate-limit`, `rate-limiter-flexible`

---

## Pattern 07: Pagination Deep Offset

### Tên
Pagination Deep Offset (Slow For Large Page Numbers)

### Phân loại
API Design / Pagination / Performance

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```
GET /api/users?page=1000&limit=20
→ SELECT * FROM users OFFSET 20000 LIMIT 20
→ DB scans 20,000 rows then discards them
```

### Phát hiện

```bash
rg --type ts --type js "offset|OFFSET|skip" -n
rg --type ts --type js "cursor|after|before" -n
```

### Giải pháp

❌ **BAD**
```typescript
const users = await db.users.findMany({
    skip: (page - 1) * limit,
    take: limit,
}); // Slow for large page numbers
```

✅ **GOOD**
```typescript
// Cursor-based pagination:
async function listUsers(cursor?: string, limit = 20) {
    const users = await db.users.findMany({
        take: limit + 1,
        ...(cursor && { cursor: { id: cursor }, skip: 1 }),
        orderBy: { id: 'asc' },
    });

    const hasMore = users.length > limit;
    const data = hasMore ? users.slice(0, limit) : users;
    const nextCursor = hasMore ? data[data.length - 1].id : undefined;

    return { data, meta: { nextCursor, hasMore } };
}
```

### Phòng ngừa
- [ ] Cursor-based for large datasets
- [ ] Offset OK for small datasets (<10K)
- [ ] Include `hasMore` in response

---

## Pattern 08: Health Check Thiếu

### Tên
Health Check Thiếu (No Health Endpoint)

### Phân loại
API Design / Operations / Monitoring

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```
K8s/load balancer needs to check if service is healthy.
Without health check → traffic to unhealthy instances.
```

### Phát hiện

```bash
rg --type ts --type js "/health|/ready|/live" -n
rg --type ts --type js "healthz|readyz" -n
```

### Giải pháp

❌ **BAD**: No health endpoint

✅ **GOOD**
```typescript
// Liveness:
app.get('/healthz', (req, res) => {
    res.json({ status: 'ok', uptime: process.uptime() });
});

// Readiness (checks dependencies):
app.get('/readyz', async (req, res) => {
    try {
        await db.$queryRaw`SELECT 1`;
        await redis.ping();
        res.json({ status: 'ready', db: 'ok', redis: 'ok' });
    } catch (error) {
        res.status(503).json({ status: 'not ready', error: String(error) });
    }
});
```

### Phòng ngừa
- [ ] `/healthz` for liveness
- [ ] `/readyz` for readiness (check DB, Redis)
- [ ] Skip auth for health endpoints
- Tool: K8s liveness/readiness probes

---

## Pattern 09: OpenAPI Spec Out Of Sync

### Tên
OpenAPI Spec Out Of Sync (Docs Don't Match Code)

### Phân loại
API Design / Documentation / Consistency

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```
API docs say: POST /users accepts { name, email }
Code accepts: { name, email, role, department }
→ Frontend follows outdated docs
```

### Phát hiện

```bash
rg "openapi|swagger" -n --glob "*.yaml" --glob "*.json"
rg --type ts --type js "swagger|tsoa|zod-to-openapi" -n
```

### Giải pháp

❌ **BAD**: Manual OpenAPI spec

✅ **GOOD**
```typescript
// Generate from Zod schemas (zod-to-openapi):
import { extendZodWithOpenApi } from '@asteasolutions/zod-to-openapi';

const UserSchema = z.object({
    name: z.string().openapi({ example: 'John Doe' }),
    email: z.string().email().openapi({ example: 'john@example.com' }),
}).openapi('CreateUser');

// Or TSOA: generates OpenAPI from TypeScript types
// @Route("users") class UserController extends Controller {
//     @Post() public async create(@Body() body: CreateUserDto): Promise<User> {}
// }
```

### Phòng ngừa
- [ ] Generate OpenAPI from code/schemas
- [ ] CI: validate spec matches implementation
- [ ] Serve Swagger UI
- Tool: `tsoa`, `zod-to-openapi`, `swagger-jsdoc`

---

## Pattern 10: Webhook Idempotency Thiếu

### Tên
Webhook Idempotency Thiếu (Duplicate Processing)

### Phân loại
API Design / Webhook / Reliability

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```
Stripe webhook retry: same event sent multiple times
→ Without idempotency → payment processed twice!
```

### Phát hiện

```bash
rg --type ts --type js "webhook|Webhook" -n
rg --type ts --type js "idempotency|idempotent" -i -n
```

### Giải pháp

❌ **BAD**
```typescript
app.post('/webhooks/stripe', async (req, res) => {
    await processPayment(req.body.data.object); // May run twice!
    res.sendStatus(200);
});
```

✅ **GOOD**
```typescript
app.post('/webhooks/stripe', async (req, res) => {
    const eventId = req.body.id;

    // Idempotency check:
    const exists = await db.processedEvents.findUnique({ where: { eventId } });
    if (exists) return res.sendStatus(200);

    await db.$transaction(async (tx) => {
        await tx.processedEvents.create({ data: { eventId } });
        await processPayment(req.body.data.object);
    });

    res.sendStatus(200);
});
```

### Phòng ngừa
- [ ] Store processed event IDs
- [ ] Check before processing
- [ ] Database transaction for atomicity
- Tool: Unique constraint on event_id
