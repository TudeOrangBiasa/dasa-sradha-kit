# Domain 06: TypeScript Và Kiểu (TypeScript & Types)

> Node.js/TypeScript patterns liên quan đến type system, type safety, và TypeScript configuration.

---

## Pattern 01: Any Abuse

### Tên
Any Abuse (Lạm Dụng Type Any)

### Phân loại
TypeScript / Type Safety / Any

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```
TypeScript Type Checking Flow:

  Source Code → tsc compiler → Type Check → JavaScript Output
       │                          │
       ├── proper types     ✅ Catches errors at compile time
       │
       └── any types        ❌ Bypasses ALL type checking
                                  │
                                  ▼
              Runtime errors instead of compile errors
              "Cannot read property 'x' of undefined"
              "TypeError: foo is not a function"

  any spreads like virus:
    function getUser(): any { }
    const user = getUser();       ← user: any
    const name = user.name;       ← name: any (no check!)
    const upper = name.toFixed(); ← COMPILES! But crashes at runtime
                                    (string has no toFixed)
```

`any` type vô hiệu hóa hoàn toàn type checking. Khi một value là `any`, tất cả operations trên nó đều được compiler cho phép — lỗi chỉ phát hiện ở runtime.

### Phát hiện

```bash
# Tìm explicit any usage
rg --type ts ": any\b|: any\[|<any>" -n

# Tìm any trong function parameters
rg --type ts "function\s+\w+\(.*:\s*any" -n

# Tìm any trong return types
rg --type ts "\):\s*any\b" -n

# Count any usage per file
rg --type ts "\bany\b" -c | sort -t: -k2 -rn

# Tìm implicit any (tsconfig strict: false)
rg --type ts "\"noImplicitAny\":\s*false" -n
```

### Giải pháp

❌ **BAD**: any everywhere
```typescript
function processData(data: any): any {
  return data.items.map((item: any) => ({
    name: item.name,
    value: item.getValue(), // No type check — crashes if method doesn't exist
  }));
}
```

✅ **GOOD**: Proper types
```typescript
interface DataItem {
  name: string;
  getValue(): number;
}

interface DataPayload {
  items: DataItem[];
}

function processData(data: DataPayload): Array<{ name: string; value: number }> {
  return data.items.map((item) => ({
    name: item.name,
    value: item.getValue(), // Type checked!
  }));
}
```

✅ **GOOD**: unknown thay any cho external data
```typescript
function parseResponse(raw: unknown): User {
  if (!isUser(raw)) {
    throw new Error('Invalid user data');
  }
  return raw; // Type narrowed to User
}

function isUser(data: unknown): data is User {
  return (
    typeof data === 'object' && data !== null &&
    'name' in data && typeof (data as Record<string, unknown>).name === 'string'
  );
}
```

### Phòng ngừa

- [ ] `strict: true` trong tsconfig.json
- [ ] `noImplicitAny: true` — compiler error khi infer any
- [ ] Dùng `unknown` thay `any` cho untyped data
- [ ] ESLint rule: `@typescript-eslint/no-explicit-any`
- Tool: `typescript-eslint` — warn/error on any usage

---

## Pattern 02: Type Assertion Sai

### Tên
Type Assertion Sai (Incorrect Type Assertion)

### Phân loại
TypeScript / Type Safety / Assertion

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```
Type Assertions: as Type

  const data = JSON.parse(response) as User;
                                     ^^^^^^^^
  TypeScript: "OK, I trust you" → NO runtime check
       │
       ▼
  Nếu response KHÔNG phải User format:
    data.name    → undefined (not string)
    data.email   → undefined
    data.getId() → "TypeError: data.getId is not a function"

  Double assertion (force cast):
    const x = someValue as unknown as TargetType;
    ^^^ Bypasses ALL safety → guaranteed runtime error potential
```

`as Type` chỉ là compile-time assertion, KHÔNG có runtime validation. Nếu actual data không match, bugs chỉ phát hiện ở runtime.

### Phát hiện

```bash
# Tìm type assertions
rg --type ts "\bas\s+\w+" -n

# Tìm double assertions (force cast)
rg --type ts "as unknown as|as any as" -n

# Tìm angle bracket assertions (old syntax)
rg --type ts "<\w+>\s*\w+" -n

# Tìm JSON.parse với assertion
rg --type ts "JSON\.parse.*\bas\b" -n
```

### Giải pháp

❌ **BAD**: Assert without validation
```typescript
interface Config {
  port: number;
  host: string;
  debug: boolean;
}

const config = JSON.parse(fs.readFileSync('config.json', 'utf-8')) as Config;
// If config.json is malformed → runtime crash
console.log(config.port.toFixed()); // TypeError if port is string
```

✅ **GOOD**: Runtime validation with Zod
```typescript
import { z } from 'zod';

const ConfigSchema = z.object({
  port: z.number().int().min(1).max(65535),
  host: z.string().min(1),
  debug: z.boolean(),
});

type Config = z.infer<typeof ConfigSchema>;

const raw = JSON.parse(fs.readFileSync('config.json', 'utf-8'));
const config = ConfigSchema.parse(raw);
// Throws ZodError with details if invalid
// config is correctly typed as Config
```

### Phòng ngừa

- [ ] NEVER `as Type` cho external data (API, files, user input)
- [ ] Dùng Zod, io-ts, ajv cho runtime validation
- [ ] `as const` cho literal types (safe assertion)
- [ ] Type guards (`is` keyword) cho custom narrowing
- Tool: ESLint rule `@typescript-eslint/consistent-type-assertions`

---

## Pattern 03: Enum Pitfalls

### Tên
Enum Pitfalls (Bẫy Khi Dùng Enum)

### Phân loại
TypeScript / Type System / Enum

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```
Numeric Enum Reverse Mapping:
  enum Direction { Up = 0, Down = 1, Left = 2, Right = 3 }

  Compiled JS:
    Direction[0] = "Up"     ← Reverse mapping!
    Direction["Up"] = 0
    Direction[1] = "Down"
    Direction["Down"] = 1

  Direction[99] = undefined  ← NO runtime error, just undefined
  typeof Direction[0] → "string" (not Direction!)

Const Enum Inline:
  const enum Color { Red, Green, Blue }
  let c = Color.Red;
  Compiled: let c = 0;  ← Inlined, enum disappears!
  // Cannot use Color at runtime (Object.keys, iteration)
  // Breaks when used across module boundaries (declaration files)
```

### Phát hiện

```bash
# Tìm numeric enums (potential reverse mapping issues)
rg --type ts "enum\s+\w+\s*\{" -n -A 5

# Tìm const enums
rg --type ts "const enum" -n

# Tìm enum access by number (reverse mapping)
rg --type ts "\w+\[\d+\]" -n

# Tìm enum iteration (doesn't work with const enum)
rg --type ts "Object\.(keys|values|entries)\(\w+Enum\)" -n
```

### Giải pháp

❌ **BAD**: Numeric enum issues
```typescript
enum Status { Active, Inactive, Pending }

function isValid(status: Status): boolean {
  return Status[status] !== undefined; // Reverse mapping confusion
}

isValid(999); // TypeScript allows this! Returns false at runtime
```

✅ **GOOD**: String enums (no reverse mapping)
```typescript
enum Status {
  Active = 'ACTIVE',
  Inactive = 'INACTIVE',
  Pending = 'PENDING',
}

// No reverse mapping — Status['ACTIVE'] is undefined
// Values are meaningful strings in JSON/DB
```

✅ **GOOD**: Union types (recommended over enums)
```typescript
const STATUS = {
  Active: 'ACTIVE',
  Inactive: 'INACTIVE',
  Pending: 'PENDING',
} as const;

type Status = (typeof STATUS)[keyof typeof STATUS];
// 'ACTIVE' | 'INACTIVE' | 'PENDING'

// Tree-shakable, no runtime overhead, works with isolatedModules
```

### Phòng ngừa

- [ ] Prefer string enums over numeric enums
- [ ] Consider union types: `type Status = 'active' | 'inactive'`
- [ ] Avoid `const enum` (breaks isolatedModules, declaration emit)
- [ ] NEVER access enum by numeric index
- Tool: ESLint `@typescript-eslint/prefer-literal-enum-member`

---

## Pattern 04: Interface vs Type Confusion

### Tên
Interface vs Type Confusion (Nhầm Lẫn Interface Và Type)

### Phân loại
TypeScript / Type System / Declaration

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```
interface User { name: string; }
interface User { email: string; }  ← Declaration merging!
// Result: User = { name: string; email: string; }

type Product = { name: string; }
type Product = { price: number; }  ← COMPILE ERROR!
// "Duplicate identifier 'Product'"

Declaration merging: interface tự động merge khi cùng tên
→ Bất ngờ khi 2 files define cùng interface name
→ Third-party library augmentation (intentional) vs bug (unintentional)
```

### Phát hiện

```bash
# Tìm interface declarations có thể merge
rg --type ts "^(export\s+)?interface\s+(\w+)" -n -o | sort | uniq -d

# Tìm type aliases
rg --type ts "^(export\s+)?type\s+\w+\s*=" -n

# Tìm module augmentation (intentional merge)
rg --type ts "declare module" -n

# Tìm interface extends patterns
rg --type ts "interface\s+\w+\s+extends" -n
```

### Giải pháp

❌ **BAD**: Accidental declaration merging
```typescript
// file1.ts
interface ApiResponse { data: unknown; }

// file2.ts (different developer)
interface ApiResponse { error: string; }

// Result: ApiResponse = { data: unknown; error: string; }
// Neither developer expected this!
```

✅ **GOOD**: Use type for data shapes, interface for contracts
```typescript
// Type: data shapes, unions, intersections
type ApiResponse<T> = {
  data: T;
  status: number;
  timestamp: Date;
};

type Result<T, E = Error> = { ok: true; value: T } | { ok: false; error: E };

// Interface: contracts that can be implemented
interface Repository<T> {
  findById(id: string): Promise<T | null>;
  create(data: Omit<T, 'id'>): Promise<T>;
}

class UserRepository implements Repository<User> { /* ... */ }
```

### Phòng ngừa

- [ ] `type` cho data shapes, unions, mapped types
- [ ] `interface` cho contracts (classes implement)
- [ ] Be aware of declaration merging — watch for duplicates
- [ ] Consistent convention within team
- Tool: ESLint `@typescript-eslint/consistent-type-definitions`

---

## Pattern 05: Strict Mode Thiếu

### Tên
Strict Mode Thiếu (Missing TypeScript Strict Mode)

### Phân loại
TypeScript / Configuration / Safety

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```
tsconfig.json: { "strict": false }
       │
       ▼
  Disabled checks:
  ├── noImplicitAny: false     → any inferred silently
  ├── strictNullChecks: false  → null/undefined ignored
  ├── strictFunctionTypes: false → function param bivariance
  ├── strictBindCallApply: false → bind/call/apply unchecked
  ├── strictPropertyInitialization: false → class fields uninitialized
  ├── noImplicitThis: false    → this type unknown
  └── alwaysStrict: false      → no "use strict"

  Ví dụ strictNullChecks: false:
    function getUser(id: string): User {
      return users.get(id);  ← Could be undefined!
    }
    const user = getUser("123");
    console.log(user.name);  ← Runtime crash nếu undefined
    // TypeScript: no error! (strictNullChecks disabled)
```

### Phát hiện

```bash
# Check tsconfig strict setting
rg "\"strict\"" -n --glob "tsconfig*.json"

# Check individual strict flags
rg "(noImplicitAny|strictNullChecks|strictFunctionTypes)" -n --glob "tsconfig*.json"

# Tìm potential null issues (khi strict off)
rg --type ts "\.get\(|\.find\(|\.querySelector\(" -n

# Count files affected
rg --type ts -l "." | wc -l
```

### Giải pháp

❌ **BAD**: Non-strict tsconfig
```json
{
  "compilerOptions": {
    "strict": false,
    "target": "ES2022"
  }
}
```

✅ **GOOD**: Full strict mode
```json
{
  "compilerOptions": {
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "noImplicitReturns": true,
    "noFallthroughCasesInSwitch": true,
    "noImplicitOverride": true,
    "exactOptionalPropertyTypes": true,
    "target": "ES2022",
    "module": "NodeNext",
    "moduleResolution": "NodeNext"
  }
}
```

### Phòng ngừa

- [ ] `strict: true` từ ngày đầu project
- [ ] Migration: enable từng flag một nếu legacy project
- [ ] `noUncheckedIndexedAccess: true` cho array/object safety
- [ ] CI: `tsc --noEmit` trong pipeline
- Tool: `tsc --noEmit` — type check without output

---

## Pattern 06: Runtime Type Validation Thiếu

### Tên
Runtime Type Validation Thiếu (Missing Runtime Validation)

### Phân loại
TypeScript / Runtime / Validation

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```
TypeScript types: COMPILE TIME only
       │
       ▼
  tsc compiles → JavaScript (ALL types stripped!)
       │
       ▼
  Runtime: NO type information exists

  External data sources (NO type guarantee):
  ├── API responses (fetch, axios)
  ├── User input (forms, query params)
  ├── File reads (JSON, CSV, YAML)
  ├── Database queries
  ├── Environment variables
  ├── WebSocket messages
  └── Third-party webhooks

  const user = await fetch('/api/user').then(r => r.json());
  // TypeScript: user is any (or User if asserted)
  // Runtime: could be ANYTHING — null, string, wrong shape
```

### Phát hiện

```bash
# Tìm fetch/axios without validation
rg --type ts "\.json\(\)\s*as\b|\.data\s+as\b" -n

# Tìm JSON.parse without validation
rg --type ts "JSON\.parse" -n

# Tìm process.env access without validation
rg --type ts "process\.env\.\w+" -n

# Tìm request body direct access
rg --type ts "req\.body\.\w+|request\.body\.\w+" -n

# Tìm existing Zod/io-ts usage (good practice)
rg --type ts "z\.(object|string|number)|t\.(type|interface)" -n
```

### Giải pháp

❌ **BAD**: Trust external data
```typescript
interface CreateUserDTO {
  name: string;
  email: string;
  age: number;
}

app.post('/users', (req, res) => {
  const body = req.body as CreateUserDTO; // NO runtime check!
  // body.name could be undefined, number, null, anything
  db.users.create(body); // Garbage in → garbage in DB
});
```

✅ **GOOD**: Validate at boundaries with Zod
```typescript
import { z } from 'zod';

const CreateUserSchema = z.object({
  name: z.string().min(1).max(100),
  email: z.string().email(),
  age: z.number().int().min(0).max(150),
});

type CreateUserDTO = z.infer<typeof CreateUserSchema>;

app.post('/users', (req, res) => {
  const result = CreateUserSchema.safeParse(req.body);
  if (!result.success) {
    return res.status(400).json({ errors: result.error.flatten() });
  }
  // result.data is typed AND validated
  db.users.create(result.data);
});
```

### Phòng ngừa

- [ ] Validate ALL external data boundaries
- [ ] Zod schema = single source of truth (type + validation)
- [ ] Validate: API input, API responses, env vars, file reads
- [ ] `z.infer<typeof Schema>` cho DRY type definitions
- Tool: `zod`, `io-ts`, `ajv`, `class-validator`

---

## Pattern 07: Generic Constraint Thiếu

### Tên
Generic Constraint Thiếu (Missing Generic Constraints)

### Phân loại
TypeScript / Generics / Constraints

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```
function getProperty<T>(obj: T, key: string): unknown {
                     ^^            ^^^^^^
                     T unconstrained    key not keyof T
  │
  ▼
  getProperty(42, "name")      ← T = number, key "name" → undefined
  getProperty(null, "anything") ← T = null → crash
  // No compile-time protection
```

Generic type parameter `<T>` without constraints accepts ANY type, including primitives and null. Must constrain T to match intended usage.

### Phát hiện

```bash
# Tìm unconstrained generics
rg --type ts "function\s+\w+<T>" -n

# Tìm generic interfaces without extends
rg --type ts "<T>" -n --glob "!node_modules"

# Tìm generic classes
rg --type ts "class\s+\w+<T>" -n

# Tìm proper constraints (reference)
rg --type ts "<T\s+extends" -n
```

### Giải pháp

❌ **BAD**: Unconstrained generic
```typescript
function merge<T>(a: T, b: T): T {
  return { ...a, ...b }; // Error: spread only works on objects
  // T could be number, string, null
}

function getLength<T>(item: T): number {
  return item.length; // Error: T might not have length
}
```

✅ **GOOD**: Properly constrained
```typescript
function merge<T extends Record<string, unknown>>(a: T, b: Partial<T>): T {
  return { ...a, ...b };
}

function getLength<T extends { length: number }>(item: T): number {
  return item.length;
}

function getProperty<T extends object, K extends keyof T>(obj: T, key: K): T[K] {
  return obj[key]; // Type safe: key must exist on T
}
```

### Phòng ngừa

- [ ] `extends object` để exclude primitives
- [ ] `extends Record<string, unknown>` cho object operations
- [ ] `keyof T` cho property access
- [ ] Think: "What operations do I perform on T?"
- Tool: `tsc` strict mode catches most issues

---

## Pattern 08: Discriminated Union Thiếu

### Tên
Discriminated Union Thiếu (Missing Discriminated Union)

### Phân loại
TypeScript / Type System / Union

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```
type Result = { data: User } | { error: string };

function handle(result: Result) {
    if (result.data) {     ← Property 'data' does not exist on type Result
        // TypeScript cannot narrow!
        // Both branches have different shapes but no discriminant
    }
}

Thiếu discriminant field:
  { type: 'success', data: User } vs { type: 'error', error: string }
  ^^^^^^                              ^^^^^^
  discriminant field cho TypeScript narrow
```

### Phát hiện

```bash
# Tìm union types không có discriminant
rg --type ts "type\s+\w+\s*=\s*\{" -A 5 -n

# Tìm switch statements trên union types
rg --type ts "switch\s*\(" -A 10 -n

# Tìm type narrowing patterns
rg --type ts "\"type\"\s*:" -n

# Tìm potential non-exhaustive switches
rg --type ts "default:" -n
```

### Giải pháp

❌ **BAD**: Union without discriminant
```typescript
type Shape =
  | { radius: number }
  | { width: number; height: number }
  | { sideLength: number };

function area(shape: Shape): number {
  if ('radius' in shape) return Math.PI * shape.radius ** 2;
  if ('width' in shape) return shape.width * shape.height;
  // sideLength case: no exhaustive check!
  return 0; // Bug: forgot triangle
}
```

✅ **GOOD**: Discriminated union with exhaustive check
```typescript
type Shape =
  | { kind: 'circle'; radius: number }
  | { kind: 'rectangle'; width: number; height: number }
  | { kind: 'square'; sideLength: number };

function area(shape: Shape): number {
  switch (shape.kind) {
    case 'circle': return Math.PI * shape.radius ** 2;
    case 'rectangle': return shape.width * shape.height;
    case 'square': return shape.sideLength ** 2;
    default: {
      const _exhaustive: never = shape;
      throw new Error(`Unknown shape: ${_exhaustive}`);
    }
  }
}
// Adding new shape variant → compiler error at never check!
```

### Phòng ngừa

- [ ] Always add discriminant field (`kind`, `type`, `status`)
- [ ] `never` check in default case cho exhaustiveness
- [ ] `noFallthroughCasesInSwitch: true` trong tsconfig
- Tool: ESLint `@typescript-eslint/switch-exhaustiveness-check`

---

## Pattern 09: Null Assertion Operator (!)

### Tên
Null Assertion Operator Lạm Dụng (Non-Null Assertion Abuse)

### Phân loại
TypeScript / Type Safety / Null

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```
const element = document.getElementById('app')!;
                                              ^
                                              Non-null assertion
  │
  ▼
  TypeScript: "Trust me, this is never null"
  Runtime: getElementById returns null → CRASH
           "Cannot read properties of null"

  element!.textContent = 'Hello';
  ^^^^^^^^ Skip null check → undefined behavior

  Chaining: user!.profile!.avatar!.url
            ^^^^^^^^^^^^^^^^^^^^^^^^^^
            ANY null in chain → crash
```

### Phát hiện

```bash
# Tìm non-null assertions
rg --type ts "\w+!" -n | rg -v "!=|!=="

# Tìm chained non-null assertions
rg --type ts "\w+!\.\w+!\." -n

# Tìm assertions sau DOM queries
rg --type ts "(getElementById|querySelector|querySelector)\(.*\)!" -n

# Count non-null assertions per file
rg --type ts "!\." -c | sort -t: -k2 -rn
```

### Giải pháp

❌ **BAD**: Non-null assertion everywhere
```typescript
function setupApp() {
  const root = document.getElementById('root')!;
  const header = document.querySelector('.header')!;
  const user = getUser()!;

  root.innerHTML = user!.profile!.displayName!;
  // Any null → crash
}
```

✅ **GOOD**: Proper null handling
```typescript
function setupApp() {
  const root = document.getElementById('root');
  if (!root) {
    throw new Error('Root element not found — check index.html');
  }
  // root is now HTMLElement (narrowed)

  const user = getUser();
  if (!user) {
    renderLoginPage(root);
    return;
  }

  root.innerHTML = user.profile?.displayName ?? 'Anonymous';
  //                            ^^           ^^
  //                     optional chain    nullish coalesce
}
```

### Phòng ngừa

- [ ] Optional chaining `?.` thay `!.`
- [ ] Nullish coalescing `??` cho defaults
- [ ] Throw descriptive error nếu null unexpected
- [ ] `!` chỉ acceptable sau definite assignment assertion trong class
- Tool: ESLint `@typescript-eslint/no-non-null-assertion`

---

## Pattern 10: Index Signature Sai

### Tên
Index Signature Sai (Incorrect Index Signature)

### Phân loại
TypeScript / Type System / Object

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```
interface Config {
  [key: string]: any;   ← Accepts ANY key with ANY value
}

const config: Config = {};
config.databse = "postgres";  ← Typo! No error
config.port = "not-a-number"; ← Wrong type! No error
config[Symbol()] = true;      ← Symbol key! No error

// Mất hoàn toàn type safety
// Equivalent to: Record<string, any>
```

### Phát hiện

```bash
# Tìm index signatures
rg --type ts "\[key:\s*string\]:\s*any" -n

# Tìm Record<string, any>
rg --type ts "Record<string,\s*any>" -n

# Tìm object with string index
rg --type ts "\[\w+:\s*string\]" -n

# Tìm proper alternatives (reference)
rg --type ts "Map<string," -n
```

### Giải pháp

❌ **BAD**: Loose index signature
```typescript
interface Translations {
  [key: string]: any; // No structure
}

const t: Translations = {};
t.hello = 42; // Should be string, no error
t.nonExistent; // undefined, no error
```

✅ **GOOD**: Typed index signature or Map
```typescript
// Option 1: Known keys + typed index
interface Translations {
  [locale: string]: {
    greeting: string;
    farewell: string;
  };
}

// Option 2: Map for dynamic keys
const translations = new Map<string, TranslationBundle>();

// Option 3: Record with specific value type
type Config = Record<string, string | number | boolean>;

// Option 4: Explicit optional keys
interface AppConfig {
  port: number;
  host: string;
  debug?: boolean;
  logLevel?: 'info' | 'warn' | 'error';
}
```

### Phòng ngừa

- [ ] Avoid `[key: string]: any`
- [ ] Use known property names when possible
- [ ] `noUncheckedIndexedAccess: true` cho safe index access
- [ ] Map<K, V> cho dynamic key-value stores
- Tool: `tsc` with `noUncheckedIndexedAccess`

---

## Pattern 11: Module Augmentation Conflict

### Tên
Module Augmentation Conflict (Xung Đột Khi Mở Rộng Module)

### Phân loại
TypeScript / Module / Declaration

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```
// @types/express augmentation in file A:
declare module 'express' {
  interface Request {
    user: User;
    sessionId: string;
  }
}

// Different augmentation in file B:
declare module 'express' {
  interface Request {
    user: AdminUser;    ← CONFLICT with file A!
    tenantId: number;
  }
}

Result: Request.user = User & AdminUser (merged!)
        Unexpected type, neither developer intended this
```

### Phát hiện

```bash
# Tìm module augmentations
rg --type ts "declare module" -n

# Tìm duplicate augmentations cho cùng module
rg --type ts "declare module" -n | sort | uniq -d -f1

# Tìm express Request augmentation
rg --type ts "interface Request" --glob "*.d.ts" -n

# Tìm global augmentations
rg --type ts "declare global" -n
```

### Giải pháp

❌ **BAD**: Scattered augmentations
```typescript
// auth.d.ts
declare module 'express' {
  interface Request { user: AuthUser; }
}

// tenant.d.ts
declare module 'express' {
  interface Request { user: TenantUser; } // Merges with above!
}
```

✅ **GOOD**: Single augmentation file
```typescript
// types/express.d.ts (single source of truth)
import { AuthUser } from '../models/auth';

declare module 'express' {
  interface Request {
    user?: AuthUser;
    tenantId?: string;
    requestId: string;
  }
}

// Use throughout app:
app.use((req, res, next) => {
  if (req.user) { // Optional, properly typed
    console.log(req.user.email);
  }
});
```

### Phòng ngừa

- [ ] Single `*.d.ts` file per augmented module
- [ ] Centralize in `types/` directory
- [ ] Review merge conflicts in declaration files
- [ ] Document augmentations in README
- Tool: `tsc` — shows merged interface types

---

## Pattern 12: Inferred Return Type Thay Đổi

### Tên
Inferred Return Type Thay Đổi (Changing Inferred Return Type)

### Phân loại
TypeScript / Type System / Inference

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```
// Before refactor:
function getUser(id: string) {
  return { name: "John", age: 30 };
}
// Inferred return: { name: string; age: number }

// After refactor (add nullable):
function getUser(id: string) {
  if (!id) return null;              ← Added null case
  return { name: "John", age: 30 };
}
// Inferred return: { name: string; age: number } | null
//                                                  ^^^^
//                                         BREAKING CHANGE!

// All callers:
const user = getUser("123");
user.name;  ← COMPILE ERROR: Object possibly null
// 50+ callers broken by "simple" refactor
```

### Phát hiện

```bash
# Tìm functions without explicit return types
rg --type ts "function\s+\w+\([^)]*\)\s*\{" -n | rg -v ":\s*\w+"

# Tìm arrow functions without return types
rg --type ts "const\s+\w+\s*=\s*\([^)]*\)\s*=>" -n | rg -v ":\s*\w+\s*=>"

# Tìm exported functions without return types
rg --type ts "export\s+(async\s+)?function\s+\w+\([^)]*\)\s*\{" -n

# Tìm functions with return type annotations (good practice)
rg --type ts "function\s+\w+\([^)]*\):\s*\w+" -n
```

### Giải pháp

❌ **BAD**: Inferred return type
```typescript
// Library/shared function
export function parseConfig(raw: string) {
  const parsed = JSON.parse(raw);
  return {
    host: parsed.host ?? 'localhost',
    port: parsed.port ?? 3000,
  };
}
// Return type inferred: { host: any; port: any }
// Change implementation → return type changes silently
```

✅ **GOOD**: Explicit return type
```typescript
interface AppConfig {
  host: string;
  port: number;
}

export function parseConfig(raw: string): AppConfig {
  const parsed = JSON.parse(raw);
  return {
    host: parsed.host ?? 'localhost',
    port: parsed.port ?? 3000,
  };
}
// Return type locked: changes inside won't affect callers
// Adding return null → COMPILE ERROR (not AppConfig)
```

### Phòng ngừa

- [ ] Explicit return types cho exported functions
- [ ] Implicit OK cho local/private functions
- [ ] Explicit OK cho complex return types (unions, generics)
- [ ] API boundaries: always explicit
- Tool: ESLint `@typescript-eslint/explicit-function-return-type`
- Tool: ESLint `@typescript-eslint/explicit-module-boundary-types`
