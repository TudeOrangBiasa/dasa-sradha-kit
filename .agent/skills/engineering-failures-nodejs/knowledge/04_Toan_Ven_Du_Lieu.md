# Domain 04: Toàn Vẹn Dữ Liệu (Data Integrity)

| Trường thông tin | Giá trị |
|-----------------|---------|
| **Tên miền** | Toàn Vẹn Dữ Liệu (Data Integrity) |
| **Lĩnh vực** | Database / ORM / Data Consistency |
| **Số lượng pattern** | 10 |
| **Ngôn ngữ** | TypeScript / Node.js |
| **Cập nhật** | 2026-02-18 |

---

## Tổng quan Toàn Vẹn Dữ Liệu

```
┌─────────────────────────────────────────────────────────────────┐
│                  DATA INTEGRITY LAYERS                          │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Application Layer  (Validation, Type Safety, BigInt)    │   │
│  └────────────────────────────┬─────────────────────────────┘   │
│                               │                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  ORM Layer  (N+1, Transactions, Migrations, Soft Delete) │   │
│  └────────────────────────────┬─────────────────────────────┘   │
│                               │                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Database Layer  (Isolation, Indexes, Schema Design)     │   │
│  └────────────────────────────┬─────────────────────────────┘   │
│                               │                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Runtime Layer  (Race Conditions, Timezone, Encoding)    │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                 │
│  Failure Cost:                                                  │
│  Application  ──▶  ORM  ──▶  Database  ──▶  Runtime            │
│     (cheap)                              (expensive to fix)     │
└─────────────────────────────────────────────────────────────────┘
```

---

## Pattern 01: ORM N+1 Query

### 1. Tên
**Truy Vấn N+1 Trong ORM** (ORM N+1 Query Problem)

### 2. Phân loại
- **Domain:** Data Integrity / Performance
- **Subcategory:** ORM Misuse, Database Overhead, Prisma / Sequelize / TypeORM

### 3. Mức nghiêm trọng
🟠 **HIGH** - Làm sập database khi dataset lớn, response time tăng theo hệ số N, dễ bị bỏ sót trong code review

### 4. Vấn đề

N+1 xảy ra khi code thực hiện 1 query lấy danh sách N items, sau đó thực hiện thêm N query riêng lẻ để lấy dữ liệu liên quan của từng item. Với N=1000 orders, hệ thống thực thi 1001 queries thay vì 1-2.

```
N+1 QUERY EXECUTION FLOW:
┌─────────────────────────────────────────────────────────────────┐
│  Code: orders.forEach(o => db.query(user WHERE id = o.userId))  │
│                                                                 │
│  Query 1: SELECT * FROM orders          ──▶ [o1, o2, ..., oN]  │
│  Query 2: SELECT * FROM users WHERE id = o1.userId             │
│  Query 3: SELECT * FROM users WHERE id = o2.userId             │
│  Query 4: SELECT * FROM users WHERE id = o3.userId             │
│  ...                                                            │
│  Query N+1: SELECT * FROM users WHERE id = oN.userId           │
│                                                                 │
│  Total: 1 + N queries  (N=1000 → 1001 round trips to DB!)      │
│                                                                 │
│  SOLUTION: Eager loading / JOIN / IN clause                     │
│  Query 1: SELECT * FROM orders                                  │
│  Query 2: SELECT * FROM users WHERE id IN (id1, id2, ..., idN) │
│  Total: 2 queries  ✅                                           │
└─────────────────────────────────────────────────────────────────┘
```

### 5. Phát hiện trong mã nguồn

**Dấu hiệu nhận biết:**
- `forEach` / `map` chứa `await db.find()` / `await repository.findOne()`
- Không dùng `include` / `relations` / `populate` trong ORM query đầu tiên
- Log database cho thấy nhiều query gần giống nhau liên tiếp

**Ripgrep regex để tìm:**
```bash
# Tìm await trong vòng lặp (dấu hiệu N+1)
rg --type ts "for.*\{[^}]*await.*find|forEach\(.*async.*await.*find" -n

# Tìm prisma findMany không có include
rg --type ts "\.findMany\(\s*\{(?![^}]*include)" -n

# Tìm TypeORM findOne trong loop
rg --type ts "(for|forEach|map).*\n.*findOne\(" -n --multiline

# Tìm Sequelize findAll trong forEach
rg --type ts "forEach.*async|map.*async" -A 5 -n | grep -A 3 "findOne\|findAll\|findByPk"
```

### 6. Giải pháp

```typescript
// ❌ BAD: N+1 với Prisma
async function getOrdersWithUsers_BAD(): Promise<OrderWithUser[]> {
  const orders = await prisma.order.findMany(); // Query 1

  const result = [];
  for (const order of orders) {
    // N queries - 1 per order!
    const user = await prisma.user.findUnique({
      where: { id: order.userId }
    });
    result.push({ ...order, user });
  }
  return result;
}

// ✅ GOOD: Eager loading với Prisma include
async function getOrdersWithUsers_GOOD(): Promise<OrderWithUser[]> {
  // 1 query với JOIN
  return prisma.order.findMany({
    include: {
      user: true,
      items: {
        include: { product: true }
      }
    }
  });
}

// ❌ BAD: N+1 với TypeORM
async function getPostsWithAuthors_BAD() {
  const posts = await postRepository.find(); // Không load relations

  return Promise.all(
    posts.map(async (post) => {
      // N queries!
      const author = await userRepository.findOneBy({ id: post.authorId });
      return { ...post, author };
    })
  );
}

// ✅ GOOD: TypeORM với relations
async function getPostsWithAuthors_GOOD() {
  return postRepository.find({
    relations: {
      author: true,
      comments: {
        author: true
      }
    }
  });
}

// ❌ BAD: N+1 với Sequelize
async function getProductsWithCategory_BAD() {
  const products = await Product.findAll(); // Không include

  return Promise.all(
    products.map(async (p) => {
      const category = await Category.findByPk(p.categoryId); // N queries
      return { ...p.toJSON(), category: category?.toJSON() };
    })
  );
}

// ✅ GOOD: Sequelize với include
async function getProductsWithCategory_GOOD() {
  return Product.findAll({
    include: [
      {
        model: Category,
        attributes: ['id', 'name', 'slug']
      }
    ]
  });
}

// ✅ ADVANCED: Khi cần custom logic - dùng IN clause thủ công
async function getOrdersCustom(orderIds: number[]) {
  const orders = await prisma.order.findMany({
    where: { id: { in: orderIds } }
  });

  // Collect all userIds (deduplicated)
  const userIds = [...new Set(orders.map((o) => o.userId))];

  // 1 query lấy tất cả users
  const users = await prisma.user.findMany({
    where: { id: { in: userIds } }
  });

  // Build lookup map O(1)
  const userMap = new Map(users.map((u) => [u.id, u]));

  // Merge in memory
  return orders.map((order) => ({
    ...order,
    user: userMap.get(order.userId)
  }));
}
```

### 7. Phòng ngừa

```javascript
// ESLint rule: eslint-plugin-no-await-in-loop (cảnh báo await trong vòng lặp)
// .eslintrc.js
module.exports = {
  rules: {
    'no-await-in-loop': 'warn', // Cảnh báo khi await trong for/while
  }
};

// Bật Prisma query logging để phát hiện N+1 trong dev:
// prisma.ts
const prisma = new PrismaClient({
  log: process.env.NODE_ENV === 'development'
    ? [{ level: 'query', emit: 'event' }]
    : []
});

if (process.env.NODE_ENV === 'development') {
  let queryCount = 0;
  prisma.$on('query', (e) => {
    queryCount++;
    if (queryCount > 10) {
      console.warn(`[N+1 Warning] Query #${queryCount}: ${e.query}`);
    }
  });
}
```

---

## Pattern 02: Transaction Isolation Sai

### 1. Tên
**Mức Cô Lập Transaction Không Đúng** (Transaction Isolation Level Mismatch)

### 2. Phân loại
- **Domain:** Data Integrity / Concurrency
- **Subcategory:** ACID Properties, Database Transactions, Race Conditions

### 3. Mức nghiêm trọng
🔴 **CRITICAL** - Gây mất dữ liệu, double-spending, phantom reads, inconsistent state trong môi trường concurrent

### 4. Vấn đề

SQL databases có 4 mức isolation: READ UNCOMMITTED, READ COMMITTED, REPEATABLE READ, SERIALIZABLE. Dùng sai mức hoặc không dùng transaction khiến concurrent operations gây ra dirty reads, non-repeatable reads, phantom reads, và lost updates.

```
ISOLATION PROBLEMS MATRIX:
┌──────────────────┬───────────┬─────────────┬─────────────┬────────────┐
│ Isolation Level  │  Dirty    │ Non-repeat  │  Phantom    │ Lost       │
│                  │  Read     │ Read        │  Read       │ Update     │
├──────────────────┼───────────┼─────────────┼─────────────┼────────────┤
│ READ UNCOMMITTED │    YES    │     YES     │     YES     │    YES     │
│ READ COMMITTED   │    NO     │     YES     │     YES     │    YES     │
│ REPEATABLE READ  │    NO     │     NO      │     YES     │    NO      │
│ SERIALIZABLE     │    NO     │     NO      │     NO      │    NO      │
└──────────────────┴───────────┴─────────────┴─────────────┴────────────┘

LOST UPDATE SCENARIO (race condition không có proper isolation):
┌────────────────────────────────────────────────────────────────┐
│  T=0: stock = 10                                               │
│                                                                │
│  Transaction A              Transaction B                      │
│  ─────────────              ─────────────                      │
│  READ stock = 10            READ stock = 10                    │
│  Calculate: 10 - 3 = 7      Calculate: 10 - 8 = 2             │
│  WRITE stock = 7            WRITE stock = 2   ← overwrites A! │
│                                                                │
│  T=end: stock = 2  (should be -1 → out of stock error!)       │
│  Result: OVERSOLD! Data integrity violated                     │
└────────────────────────────────────────────────────────────────┘
```

### 5. Phát hiện trong mã nguồn

**Dấu hiệu nhận biết:**
- Read-then-write (select rồi update) mà không có `FOR UPDATE` hoặc optimistic locking
- Multiple DB operations không được bọc trong transaction
- `prisma.$transaction` / `sequelize.transaction` vắng mặt trong business-critical flows

**Ripgrep regex để tìm:**
```bash
# Tìm update sau findFirst/findUnique mà không có transaction
rg --type ts "findFirst|findUnique" -A 10 -n | grep -B 5 "update\|save\(\)"

# Tìm stock/balance/quantity update không dùng transaction
rg --type ts "(stock|balance|quantity|amount).*update" -n

# Tìm $transaction usage (để biết đâu CÓ dùng, đâu THIẾU)
rg --type ts "\.\$transaction\|sequelize\.transaction\|queryRunner\.startTransaction" -n

# Tìm các hàm transferFunds / deductBalance không có transaction wrapper
rg --type ts "async.*transfer|async.*deduct|async.*withdraw|async.*charge" -n
```

### 6. Giải pháp

```typescript
// ❌ BAD: Không dùng transaction - race condition
async function purchaseItem_BAD(userId: number, productId: number, qty: number) {
  const product = await prisma.product.findUnique({
    where: { id: productId }
  });

  if (!product || product.stock < qty) {
    throw new Error('Insufficient stock');
  }

  // RACE CONDITION: Another request can change stock between read and write!
  await prisma.product.update({
    where: { id: productId },
    data: { stock: product.stock - qty }
  });

  await prisma.order.create({
    data: { userId, productId, quantity: qty }
  });
}

// ✅ GOOD: Prisma transaction với pessimistic locking
async function purchaseItem_GOOD(userId: number, productId: number, qty: number) {
  return prisma.$transaction(
    async (tx) => {
      // Raw SQL FOR UPDATE locks the row until transaction ends
      const [product] = await tx.$queryRaw<Product[]>`
        SELECT * FROM products WHERE id = ${productId} FOR UPDATE
      `;

      if (!product || product.stock < qty) {
        throw new Error('Insufficient stock');
      }

      const updatedProduct = await tx.product.update({
        where: { id: productId },
        data: { stock: { decrement: qty } }
      });

      const order = await tx.order.create({
        data: { userId, productId, quantity: qty, totalPrice: product.price * qty }
      });

      return { order, remainingStock: updatedProduct.stock };
    },
    {
      isolationLevel: Prisma.TransactionIsolationLevel.Serializable,
      maxWait: 5000,
      timeout: 10000
    }
  );
}

// ✅ GOOD: Optimistic locking với version field
interface Product {
  id: number;
  stock: number;
  version: number;
}

async function purchaseOptimistic(userId: number, productId: number, qty: number) {
  const MAX_RETRIES = 3;

  for (let attempt = 0; attempt < MAX_RETRIES; attempt++) {
    const product = await prisma.product.findUniqueOrThrow({
      where: { id: productId }
    });

    if (product.stock < qty) throw new Error('Insufficient stock');

    try {
      return await prisma.$transaction(async (tx) => {
        // Update chỉ thành công nếu version chưa thay đổi
        const result = await tx.product.updateMany({
          where: {
            id: productId,
            version: product.version // Optimistic lock check
          },
          data: {
            stock: { decrement: qty },
            version: { increment: 1 }
          }
        });

        if (result.count === 0) {
          throw new Error('OPTIMISTIC_LOCK_FAILED'); // Sẽ được retry
        }

        return tx.order.create({
          data: { userId, productId, quantity: qty }
        });
      });
    } catch (error) {
      if (error instanceof Error && error.message === 'OPTIMISTIC_LOCK_FAILED') {
        if (attempt === MAX_RETRIES - 1) throw new Error('Too many conflicts, try again');
        await new Promise((r) => setTimeout(r, 50 * (attempt + 1))); // Exponential backoff
        continue;
      }
      throw error;
    }
  }
}

// ✅ GOOD: TypeORM với isolation level
import { DataSource, IsolationLevel } from 'typeorm';

async function transferBalance(
  dataSource: DataSource,
  fromId: number,
  toId: number,
  amount: number
) {
  await dataSource.transaction(
    IsolationLevel.SERIALIZABLE,
    async (manager) => {
      const from = await manager.findOneOrFail(Account, {
        where: { id: fromId },
        lock: { mode: 'pessimistic_write' }
      });

      const to = await manager.findOneOrFail(Account, {
        where: { id: toId },
        lock: { mode: 'pessimistic_write' }
      });

      if (from.balance < amount) throw new Error('Insufficient balance');

      from.balance -= amount;
      to.balance += amount;

      await manager.save([from, to]);
    }
  );
}
```

### 7. Phòng ngừa

```javascript
// Custom ESLint rule để phát hiện update sau findUnique mà không có transaction
// Cần dùng eslint-plugin-custom hoặc review manual

// Prisma middleware để log transactions
prisma.$use(async (params, next) => {
  if (['update', 'updateMany', 'delete', 'deleteMany'].includes(params.action)) {
    // Kiểm tra có trong transaction context không
    if (!params.runInTransaction) {
      console.warn(
        `[TX Warning] ${params.model}.${params.action} called outside transaction`
      );
    }
  }
  return next(params);
});
```

---

## Pattern 03: MongoDB Schema Design Sai

### 1. Tên
**Thiết Kế Schema MongoDB Không Phù Hợp** (MongoDB Embedding vs Referencing Mismatch)

### 2. Phân loại
- **Domain:** Data Integrity / Schema Design
- **Subcategory:** NoSQL Design, Document Model, MongoDB

### 3. Mức nghiêm trọng
🟠 **HIGH** - Document size limit 16MB, query performance degraded, data duplication gây inconsistency khó sửa sau khi production

### 4. Vấn đề

MongoDB cho phép embed documents hoặc reference (như foreign key). Chọn sai strategy dẫn đến: document vượt 16MB limit, unbounded array growth, stale data do duplication, hoặc quá nhiều round-trips do over-referencing.

```
EMBEDDING vs REFERENCING DECISION TREE:
┌────────────────────────────────────────────────────────────────┐
│  Q1: Data có unbounded growth không? (comments, events, logs)  │
│       YES ──▶ REFERENCE (embed sẽ vượt 16MB limit)            │
│       NO  ──▶ Q2                                               │
│                                                                │
│  Q2: Data có được query độc lập không?                         │
│       YES ──▶ REFERENCE (nếu query riêng lẻ thường xuyên)     │
│       NO  ──▶ Q3                                               │
│                                                                │
│  Q3: Tỷ lệ đọc vs ghi của sub-document?                       │
│       Luôn đọc cùng parent ──▶ EMBED (1 read, tối ưu)         │
│       Đọc/ghi độc lập      ──▶ REFERENCE                      │
│                                                                │
│  RULE OF THUMB:                                                │
│  Embed: address trong user, items trong invoice (bounded)      │
│  Reference: comments (unbounded), orders của user (unbounded)  │
└────────────────────────────────────────────────────────────────┘

DOCUMENT SIZE GROWTH PROBLEM:
┌────────────────────────────────────────────────────────────────┐
│  { _id: "post123",                                             │
│    title: "...",                                               │
│    comments: [                ← EMBEDDED unbounded array       │
│      { text: "..." },         ← Day 1: 10 comments = 5KB      │
│      { text: "..." },         ← Day 30: 1000 comments = 500KB │
│      ...                      ← Day 365: 50000 = 25MB ❌      │
│    ]                          ← EXCEEDS 16MB LIMIT!            │
│  }                                                             │
└────────────────────────────────────────────────────────────────┘
```

### 5. Phát hiện trong mã nguồn

**Dấu hiệu nhận biết:**
- `$push` vào array field mà không có `$slice` giới hạn
- Schema có `[{ type: Schema.Types.ObjectId }]` nhưng dữ liệu thực tế là bounded
- Schema có sub-document array nhưng dữ liệu là unbounded (comments, logs, events)
- `populate()` trong mọi query thay vì embed data thường xuyên đọc cùng nhau

**Ripgrep regex để tìm:**
```bash
# Tìm $push vào array mà không có giới hạn
rg --type ts "\\\$push.*\\\$slice" -n
rg --type ts "\\\$push" -n  # Tìm tất cả $push để review

# Tìm schema với array references (cần review xem bounded hay không)
rg --type ts "type:.*Schema\.Types\.ObjectId.*\]|\[.*ObjectId" -n

# Tìm nested populate sâu (dấu hiệu over-referencing)
rg --type ts "populate\(.*populate\(" -n

# Tìm schema arrays không có maxlength
rg --type ts "type.*\[.*\]" -B 2 -A 2 -n | grep -v "maxlength\|limit\|max"
```

### 6. Giải pháp

```typescript
import { Schema, model, Types } from 'mongoose';

// ❌ BAD: Embed comments (unbounded growth → vượt 16MB)
const PostSchema_BAD = new Schema({
  title: String,
  content: String,
  // Sẽ có hàng nghìn comments → document quá lớn
  comments: [
    {
      author: String,
      text: String,
      createdAt: Date
    }
  ]
});

// ✅ GOOD: Reference comments (unbounded array)
const PostSchema_GOOD = new Schema({
  title: String,
  content: String,
  commentCount: { type: Number, default: 0 } // Denormalize counter (read-friendly)
});

const CommentSchema = new Schema({
  postId: { type: Types.ObjectId, ref: 'Post', index: true }, // Index bắt buộc
  author: String,
  text: String,
  createdAt: { type: Date, default: Date.now }
});

// ❌ BAD: Reference address (luôn đọc cùng user, bounded, không query độc lập)
const UserSchema_BAD = new Schema({
  name: String,
  email: String,
  addressId: { type: Types.ObjectId, ref: 'Address' } // Over-referenced
});

// ✅ GOOD: Embed address (bounded, always read with user)
const UserSchema_GOOD = new Schema({
  name: String,
  email: String,
  address: {
    // Embedded - 1 read thay vì 2
    street: String,
    city: String,
    country: String,
    zipCode: String
  }
});

// ✅ GOOD: Hybrid pattern - embed recent + reference all
const ArticleSchema = new Schema({
  title: String,
  content: String,
  // Chỉ embed 5 comments gần nhất (bounded, for display)
  recentComments: {
    type: [
      {
        author: String,
        text: String,
        createdAt: Date
      }
    ],
    validate: {
      validator: (v: unknown[]) => v.length <= 5,
      message: 'recentComments cannot exceed 5 items'
    }
  },
  commentCount: { type: Number, default: 0 }
});

// Service: thêm comment và cập nhật recentComments
async function addComment(articleId: string, comment: { author: string; text: string }) {
  const session = await mongoose.startSession();
  session.startTransaction();

  try {
    // Tạo comment trong collection riêng
    const newComment = await Comment.create([{ articleId, ...comment }], { session });

    // Cập nhật article: push vào recent (giữ tối đa 5), tăng counter
    await Article.findByIdAndUpdate(
      articleId,
      {
        $push: {
          recentComments: {
            $each: [{ ...comment, createdAt: new Date() }],
            $sort: { createdAt: -1 },
            $slice: 5 // Chỉ giữ 5 gần nhất
          }
        },
        $inc: { commentCount: 1 }
      },
      { session }
    );

    await session.commitTransaction();
    return newComment[0];
  } catch (error) {
    await session.abortTransaction();
    throw error;
  } finally {
    session.endSession();
  }
}
```

### 7. Phòng ngừa

```javascript
// Mongoose plugin để giới hạn array size
const boundedArrayPlugin = (schema, { fields = [], maxSize = 100 } = {}) => {
  schema.pre('save', function (next) {
    for (const field of fields) {
      if (Array.isArray(this[field]) && this[field].length > maxSize) {
        next(new Error(`Array field "${field}" exceeds max size of ${maxSize}`));
        return;
      }
    }
    next();
  });
};

// Áp dụng:
PostSchema.plugin(boundedArrayPlugin, {
  fields: ['tags', 'attachments'],
  maxSize: 20
});
```

---

## Pattern 04: JSON BigInt Loss

### 1. Tên
**Mất Độ Chính Xác BigInt Qua JSON** (JSON BigInt Precision Loss)

### 2. Phân loại
- **Domain:** Data Integrity / Type Safety
- **Subcategory:** JavaScript Number Limits, Serialization, API Response

### 3. Mức nghiêm trọng
🟠 **HIGH** - ID bị sai âm thầm, không có lỗi nào được throw, gây bug khó debug ở production

### 4. Vấn đề

`Number.MAX_SAFE_INTEGER = 2^53 - 1 = 9007199254740991`. Mọi integer lớn hơn giá trị này không thể biểu diễn chính xác bằng JavaScript `number`. Database IDs (PostgreSQL bigint, Twitter Snowflake IDs, MongoDB ObjectId dạng số) thường vượt giới hạn này.

```
BIGINT PRECISION LOSS FLOW:
┌─────────────────────────────────────────────────────────────────┐
│  Database: id = 9007199254740993 (2^53 + 1)                     │
│                     │                                           │
│  Prisma / Driver    ▼                                           │
│  JSON.stringify: "9007199254740993"  ──▶  "9007199254740992"   │
│                                          ^^^^^^^^^^^^^^^^        │
│                                          WRONG! (rounded)        │
│                     │                                           │
│  Frontend receives: 9007199254740992                            │
│  API call: GET /users/9007199254740992  ──▶  404 Not Found!    │
│                                                                 │
│  Số bị affected:                                               │
│  9007199254740993 ──▶ 9007199254740992  (off by 1!)            │
│  9007199254740995 ──▶ 9007199254740996  (off by 1!)            │
│  9007199254740997 ──▶ 9007199254740996  (off by 1!)            │
└─────────────────────────────────────────────────────────────────┘
```

### 5. Phát hiện trong mã nguồn

**Dấu hiệu nhận biết:**
- Database dùng `bigint` / `bigserial` cho ID nhưng TypeScript dùng `number`
- `JSON.parse()` / `JSON.stringify()` trực tiếp với response từ DB có bigint
- Prisma schema dùng `BigInt` nhưng DTO serialize sang `number`

**Ripgrep regex để tìm:**
```bash
# Tìm BigInt trong Prisma schema
rg "BigInt|bigint" prisma/schema.prisma -n

# Tìm nơi convert BigInt sang Number (nguy hiểm)
rg --type ts "Number\(.*[Bb]ig[Ii]nt\|parseInt.*[Bb]ig[Ii]nt\|as number" -n

# Tìm JSON.stringify với potential BigInt fields
rg --type ts "JSON\.stringify" -n -A 2

# Tìm id fields typed as number thay vì string/bigint
rg --type ts "id\s*:\s*number" -n

# Tìm Snowflake ID / Twitter ID patterns
rg --type ts "snowflake|twitterId|discordId" -n
```

### 6. Giải pháp

```typescript
// ❌ BAD: BigInt ID bị mất precision qua JSON
interface User {
  id: number; // WRONG: sẽ mất precision nếu id > 2^53
  name: string;
}

async function getUser_BAD(id: number): Promise<User> {
  const user = await prisma.user.findUnique({ where: { id } });
  // Prisma trả về BigInt, implicit convert sang number → mất precision!
  return user as User;
}

// API response
app.get('/users/:id', async (req, res) => {
  const user = await prisma.user.findUnique({
    where: { id: BigInt(req.params.id) }
  });
  // JSON.stringify không handle BigInt → TypeError!
  res.json(user); // ❌ Throws: "Do not know how to serialize a BigInt"
});

// ✅ GOOD: Serialize BigInt thành String
interface UserDTO {
  id: string; // String để giữ full precision
  name: string;
  createdAt: string;
}

function serializeUser(user: { id: bigint; name: string; createdAt: Date }): UserDTO {
  return {
    id: user.id.toString(), // BigInt → String (không mất precision)
    name: user.name,
    createdAt: user.createdAt.toISOString()
  };
}

// ✅ GOOD: Global BigInt JSON serializer (Express middleware)
function bigIntJsonMiddleware(
  _req: Request,
  res: Response,
  next: NextFunction
): void {
  const originalJson = res.json.bind(res);

  res.json = (body: unknown) => {
    const serialized = JSON.stringify(body, (_key, value) =>
      typeof value === 'bigint' ? value.toString() : value
    );
    res.setHeader('Content-Type', 'application/json');
    return res.send(serialized);
  };

  next();
}

// ✅ GOOD: Prisma - configure BigInt serialization globally
// prisma/client.ts
import Prisma from '@prisma/client';

// Override BigInt prototype để JSON.stringify hoạt động
(BigInt.prototype as unknown as { toJSON: () => string }).toJSON = function () {
  return this.toString();
};

// ✅ GOOD: Zod schema với string-coerced BigInt
import { z } from 'zod';

const BigIntString = z.string().refine(
  (val) => {
    try {
      BigInt(val);
      return true;
    } catch {
      return false;
    }
  },
  { message: 'Must be a valid BigInt string' }
);

const UserIdSchema = z.object({
  id: BigIntString
});

// ✅ GOOD: Nhận ID từ request params an toàn
app.get('/users/:id', async (req, res) => {
  const { id } = UserIdSchema.parse(req.params);

  const user = await prisma.user.findUnique({
    where: { id: BigInt(id) }
  });

  if (!user) return res.status(404).json({ error: 'User not found' });

  res.json(serializeUser(user));
});
```

### 7. Phòng ngừa

```javascript
// ESLint: không cho phép implicit any trên BigInt fields
// .eslintrc.js
module.exports = {
  rules: {
    '@typescript-eslint/no-loss-of-precision': 'error',
    // Bắt buộc explicit type annotation
    '@typescript-eslint/no-explicit-any': 'error',
  }
};

// tsconfig.json - bật strict để phát hiện type mismatch
{
  "compilerOptions": {
    "strict": true,
    "noImplicitAny": true
  }
}
```

---

## Pattern 05: Date Timezone Pitfalls

### 1. Tên
**Bẫy Múi Giờ Với Date** (Date Timezone Pitfalls)

### 2. Phân loại
- **Domain:** Data Integrity / Localization
- **Subcategory:** Date Handling, UTC, Timezone Conversion

### 3. Mức nghiêm trọng
🟠 **HIGH** - Appointment bị sai giờ, báo cáo tài chính sai ngày, dữ liệu bị group sai do offset timezone server/client khác nhau

### 4. Vấn đề

JavaScript `Date` không lưu timezone info, chỉ lưu UTC milliseconds. `new Date()` dùng timezone của process. Server chạy UTC, client chạy Asia/Tokyo (+9), database lưu timestamp without timezone → mọi tầng interpret khác nhau.

```
TIMEZONE CHAOS SCENARIO:
┌────────────────────────────────────────────────────────────────┐
│  User đặt lịch hẹn: "2026-02-18 09:00" (Asia/Tokyo, +9)       │
│                                                                │
│  Frontend (Tokyo, +9):                                         │
│    new Date('2026-02-18 09:00')  →  2026-02-18T00:00:00Z (UTC)│
│                    │                                           │
│  Server (UTC, +0): │                                           │
│    Receives UTC    →  Saves "2026-02-18 00:00:00"             │
│                    │                                           │
│  Database (no tz): │                                           │
│    Stores literally: 2026-02-18 00:00:00                      │
│                    │                                           │
│  Other server (US/New York, -5):                              │
│    Reads: "2026-02-18 00:00:00"                               │
│    Interprets as local: 2026-02-18T05:00:00Z (UTC)            │
│                                                                │
│  Result: Appointment appears 5 hours late for NY server! ❌   │
│                                                                │
│  FIX: ALWAYS store UTC, always send ISO 8601 with timezone    │
└────────────────────────────────────────────────────────────────┘
```

### 5. Phát hiện trong mã nguồn

**Dấu hiệu nhận biết:**
- `new Date(dateString)` với string không có timezone info
- `date.toLocaleDateString()` / `date.toLocaleTimeString()` trong backend
- Prisma/TypeORM column `timestamp` (without timezone) thay vì `timestamptz`
- `moment()` hoặc `new Date()` không specify timezone

**Ripgrep regex để tìm:**
```bash
# Tìm new Date với string không có Z hoặc offset
rg --type ts "new Date\(['\"][\d-]+['\"]" -n

# Tìm toLocaleDateString/toLocaleString trong backend code
rg --type ts "toLocaleDateString\|toLocaleString\|toLocaleTimeString" -n

# Tìm timestamp column type trong TypeORM (cần kiểm tra có timezone không)
rg --type ts "type.*timestamp\b" -n

# Tìm Prisma DateTime mà không có @db.Timestamptz
rg "DateTime" prisma/schema.prisma -n | grep -v "Timestamptz\|updatedAt\|createdAt"

# Tìm date comparison trực tiếp (sai khi có timezone)
rg --type ts "\.getDate\(\)\|\.getMonth\(\)\|\.getFullYear\(\)" -n
```

### 6. Giải pháp

```typescript
// ❌ BAD: Tạo Date từ string không rõ timezone
const appointmentDate = new Date('2026-02-18 09:00'); // Timezone phụ thuộc server!
const startOfDay = new Date('2026-02-18');             // Cũng không rõ timezone

// ❌ BAD: So sánh date string trực tiếp
function isToday_BAD(dateStr: string): boolean {
  const today = new Date().toLocaleDateString(); // Server timezone!
  return new Date(dateStr).toLocaleDateString() === today; // Sai khi client ≠ server timezone
}

// ✅ GOOD: Luôn dùng UTC, luôn parse ISO 8601 với timezone
const appointmentDate = new Date('2026-02-18T09:00:00+09:00'); // Explicit JST
const utcTimestamp = appointmentDate.toISOString(); // "2026-02-18T00:00:00.000Z"

// ✅ GOOD: Temporal API (Node.js 18+ với polyfill, hoặc dùng date-fns-tz)
import { zonedTimeToUtc, utcToZonedTime, format } from 'date-fns-tz';

const TIMEZONE_JST = 'Asia/Tokyo';

// Convert user input (assumed JST) sang UTC để lưu DB
function parseUserDateToUtc(localDateStr: string, userTimezone: string): Date {
  return zonedTimeToUtc(localDateStr, userTimezone);
}

// Convert UTC từ DB sang timezone của user để hiển thị
function formatForUser(utcDate: Date, userTimezone: string): string {
  const zonedDate = utcToZonedTime(utcDate, userTimezone);
  return format(zonedDate, 'yyyy-MM-dd HH:mm:ss', { timeZone: userTimezone });
}

// ✅ GOOD: Tính start/end of day trong timezone cụ thể
function getDayBoundsInUtc(
  localDateStr: string, // 'YYYY-MM-DD'
  userTimezone: string
): { start: Date; end: Date } {
  const startOfDay = zonedTimeToUtc(`${localDateStr}T00:00:00`, userTimezone);
  const endOfDay = zonedTimeToUtc(`${localDateStr}T23:59:59.999`, userTimezone);
  return { start: startOfDay, end: endOfDay };
}

// Usage trong API query
async function getAppointmentsByDate(
  localDate: string,   // '2026-02-18' theo timezone user
  userTimezone: string // 'Asia/Tokyo'
) {
  const { start, end } = getDayBoundsInUtc(localDate, userTimezone);

  return prisma.appointment.findMany({
    where: {
      scheduledAt: {
        gte: start, // UTC start of day in user's timezone
        lte: end    // UTC end of day in user's timezone
      }
    }
  });
}

// ✅ GOOD: Prisma schema - dùng @db.Timestamptz (PostgreSQL)
// schema.prisma
// model Appointment {
//   id          Int      @id @default(autoincrement())
//   scheduledAt DateTime @db.Timestamptz(6)  ← Lưu timezone info
//   createdAt   DateTime @default(now()) @db.Timestamptz(6)
// }

// ✅ GOOD: Express middleware - set process timezone
// Đầu file main.ts / app.ts
process.env.TZ = 'UTC'; // Force server luôn dùng UTC
```

### 7. Phòng ngừa

```javascript
// ESLint rule: cấm Date constructor với string không có timezone
module.exports = {
  rules: {
    'no-restricted-syntax': [
      'warn',
      {
        selector: "NewExpression[callee.name='Date'][arguments.length=1]",
        message: 'Use explicit UTC strings (ISO 8601 with Z or offset) when creating Date objects'
      }
    ]
  }
};

// Set TZ=UTC trong package.json scripts
// "scripts": {
//   "start": "TZ=UTC node dist/main.js",
//   "test": "TZ=UTC jest"
// }
```

---

## Pattern 06: Buffer Encoding Mismatch

### 1. Tên
**Không Khớp Encoding Buffer** (Buffer Encoding Mismatch)

### 2. Phân loại
- **Domain:** Data Integrity / Encoding
- **Subcategory:** Binary Data, Character Encoding, File Processing

### 3. Mức nghiêm trọng
🟡 **MEDIUM** - Data corruption âm thầm khi xử lý file binary, character bị mất hoặc sai khi xử lý text đa ngôn ngữ

### 4. Vấn đề

Node.js Buffer không tự biết encoding của data. Dùng sai encoding (utf8 vs latin1 vs base64 vs binary) khi read/write dẫn đến data corruption không có lỗi nào báo. Đặc biệt nguy hiểm với: file binary (PDF, image), dữ liệu mã hóa (base64 token, hash), text tiếng Nhật/Việt/Arabic.

```
ENCODING MISMATCH CORRUPTION:
┌────────────────────────────────────────────────────────────────┐
│  Vietnamese text: "Xin chào"                                   │
│  UTF-8 bytes: [58 69 6E 20 63 68 C3 A0 6F]                    │
│                                  ^^^^^ 2-byte UTF-8 char       │
│                                                                │
│  Read as latin1:                                               │
│  Buffer.from([...]).toString('latin1')                         │
│  Result: "Xin ch\xC3\xA0o"  ← CORRUPTED! Multi-byte split     │
│                                                                │
│  BASE64 TOKEN CORRUPTION:                                      │
│  Original token: "abc+def/ghi=="                               │
│  URL-transmitted: "abc def/ghi==" (+ became space!)            │
│  Decoded wrong: different bytes → auth fails silently          │
└────────────────────────────────────────────────────────────────┘
```

### 5. Phát hiện trong mã nguồn

**Dấu hiệu nhận biết:**
- `Buffer.from(str)` không chỉ định encoding
- `toString('binary')` hoặc `toString('ascii')` với non-ASCII data
- Base64 token trong URL mà không dùng base64url encoding
- `fs.readFile` kết quả được xử lý như string mà không detect encoding

**Ripgrep regex để tìm:**
```bash
# Tìm Buffer.from không chỉ định encoding
rg --type ts "Buffer\.from\([^,)]+\)" -n

# Tìm toString với encoding không an toàn
rg --type ts "\.toString\('binary'\|'ascii'\|'latin1'\)" -n

# Tìm base64 không phải base64url trong JWT/token context
rg --type ts "base64(?!url)" -n

# Tìm btoa/atob (browser API, không an toàn cho binary trong Node)
rg --type ts "\bbtoa\b|\batob\b" -n
```

### 6. Giải pháp

```typescript
import crypto from 'crypto';
import { Buffer } from 'buffer';

// ❌ BAD: Encoding không rõ ràng
function encodeToken_BAD(data: string): string {
  return Buffer.from(data).toString('base64'); // Default utf8 nhưng không rõ ràng
}

function decodeToken_BAD(token: string): string {
  return Buffer.from(token, 'base64').toString(); // Có thể bị corrupted nếu token có +, /
}

// ✅ GOOD: Explicit encoding, dùng base64url cho URL-safe tokens
function encodeTokenUrlSafe_GOOD(data: string): string {
  return Buffer.from(data, 'utf8')
    .toString('base64url'); // URL-safe: không có +, /, = characters
}

function decodeTokenUrlSafe_GOOD(token: string): string {
  return Buffer.from(token, 'base64url').toString('utf8');
}

// ✅ GOOD: Hash với explicit encoding
function hashPassword_GOOD(password: string): string {
  return crypto
    .createHash('sha256')
    .update(password, 'utf8') // Explicit input encoding
    .digest('hex');            // Explicit output encoding
}

// ❌ BAD: Xử lý file binary như text
import fs from 'fs/promises';
async function processFile_BAD(path: string): Promise<string> {
  return fs.readFile(path, 'utf8'); // Sai nếu file là PDF/image!
}

// ✅ GOOD: Detect và xử lý đúng encoding
async function processFile_GOOD(path: string): Promise<Buffer | string> {
  const buffer = await fs.readFile(path); // Đọc raw Buffer trước

  // Detect nếu là text file (BOM check)
  const hasBOM = buffer[0] === 0xEF && buffer[1] === 0xBB && buffer[2] === 0xBF;
  const isUtf8 = hasBOM || isValidUtf8(buffer);

  if (isUtf8) {
    return buffer.toString('utf8').replace(/^\uFEFF/, ''); // Remove BOM nếu có
  }

  return buffer; // Trả về raw Buffer cho binary data
}

function isValidUtf8(buffer: Buffer): boolean {
  try {
    const decoder = new TextDecoder('utf-8', { fatal: true });
    decoder.decode(buffer);
    return true;
  } catch {
    return false;
  }
}

// ✅ GOOD: Stream với encoding đúng
import { createReadStream, createWriteStream } from 'fs';
function copyTextFile(src: string, dest: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const reader = createReadStream(src, { encoding: 'utf8' });
    const writer = createWriteStream(dest, { encoding: 'utf8' });
    reader.pipe(writer);
    writer.on('finish', resolve);
    writer.on('error', reject);
  });
}
```

### 7. Phòng ngừa

```javascript
// ESLint: warn khi dùng Buffer.from không chỉ encoding
module.exports = {
  rules: {
    'no-restricted-syntax': [
      'warn',
      {
        selector: "CallExpression[callee.object.name='Buffer'][callee.property.name='from'][arguments.length=1]",
        message: 'Specify encoding explicitly: Buffer.from(str, "utf8")'
      }
    ]
  }
};
```

---

## Pattern 07: Race Condition Read-Modify-Write

### 1. Tên
**Race Condition Đọc-Sửa-Ghi** (Read-Modify-Write Race Condition)

### 2. Phân loại
- **Domain:** Data Integrity / Concurrency
- **Subcategory:** Concurrent Operations, Shared State, Atomic Operations

### 3. Mức nghiêm trọng
🟠 **HIGH** - Inventory sai, coupon dùng nhiều hơn giới hạn, điểm thưởng bị mất khi concurrent requests hit cùng lúc

### 4. Vấn đề

Pattern: (1) đọc giá trị, (2) tính giá trị mới trong app, (3) ghi lại → không phải atomic. Khi 2 requests chạy đồng thời, cả 2 đọc cùng giá trị cũ, cả 2 tính toán độc lập, cả 2 ghi → một write bị mất.

```
READ-MODIFY-WRITE RACE CONDITION:
┌────────────────────────────────────────────────────────────────┐
│  Coupon "SAVE10" có limit = 1 (chỉ dùng được 1 lần)           │
│                                                                │
│  Request A (User 1)         Request B (User 2)                 │
│  ──────────────────         ──────────────────                 │
│  READ: usedCount = 0        READ: usedCount = 0               │
│  CHECK: 0 < 1 → OK          CHECK: 0 < 1 → OK                │
│  WRITE: usedCount = 1       WRITE: usedCount = 1              │
│                                                                │
│  Result: BOTH users applied coupon!                            │
│  usedCount = 1 but 2 uses happened ← DATA INTEGRITY VIOLATED  │
│                                                                │
│  FIX: Atomic increment + DB constraint                         │
│  UPDATE coupons SET usedCount = usedCount + 1                  │
│  WHERE id = X AND usedCount < maxUses                          │
│  ── Nếu UPDATE 0 rows → coupon đã hết → reject                │
└────────────────────────────────────────────────────────────────┘
```

### 5. Phát hiện trong mã nguồn

**Dấu hiệu nhận biết:**
- `find` rồi `update` với giá trị tính trong app (không dùng `$inc` / `increment`)
- Kiểm tra điều kiện trong app code trước khi update (check-then-act không atomic)
- Counter / balance update không dùng atomic DB operation
- Không có `WHERE condition` trong UPDATE để làm guard

**Ripgrep regex để tìm:**
```bash
# Tìm pattern: findOne rồi update (cần kiểm tra có atomic không)
rg --type ts "findOne|findUnique|findFirst" -A 15 -n | grep -B 5 "\.update\|\.save\("

# Tìm counter update không atomic (nguy hiểm)
rg --type ts "(count|counter|views|likes|stock)\s*[+-]=" -n
rg --type ts "\.count\s*=\s*.*\.count\s*[+-]" -n

# Tìm update với calculated value (potential race condition)
rg --type ts "update.*data.*:\s*\{[^}]*(balance|stock|count|amount)" -n

# Tìm Redis increment không dùng atomic ops
rg --type ts "redis\.get.*\n.*redis\.set\|client\.get.*\n.*client\.set" --multiline -n
```

### 6. Giải pháp

```typescript
import { Redis } from 'ioredis';

// ❌ BAD: Read-Modify-Write không atomic
async function applyCoupon_BAD(couponCode: string, userId: number) {
  const coupon = await prisma.coupon.findUnique({
    where: { code: couponCode }
  });

  if (!coupon || coupon.usedCount >= coupon.maxUses) {
    throw new Error('Coupon not available');
  }

  // RACE CONDITION: Hai requests có thể pass check cùng lúc!
  await prisma.coupon.update({
    where: { id: coupon.id },
    data: { usedCount: coupon.usedCount + 1 } // Non-atomic!
  });

  return applyDiscountToOrder(userId, coupon.discount);
}

// ✅ GOOD: Atomic UPDATE với WHERE guard
async function applyCoupon_GOOD(couponCode: string, userId: number) {
  // Single atomic operation: update ONLY IF condition met
  const result = await prisma.$executeRaw`
    UPDATE coupons
    SET used_count = used_count + 1
    WHERE code = ${couponCode}
      AND used_count < max_uses
      AND is_active = true
      AND (expires_at IS NULL OR expires_at > NOW())
  `;

  if (result === 0) {
    // 0 rows updated = coupon exhausted or invalid (no race condition possible)
    throw new Error('Coupon not available or already exhausted');
  }

  const coupon = await prisma.coupon.findUnique({ where: { code: couponCode } });
  return applyDiscountToOrder(userId, coupon!.discount);
}

// ✅ GOOD: Prisma atomic increment
async function incrementViewCount_GOOD(articleId: number) {
  // Prisma's increment is atomic (translates to SET views = views + 1)
  return prisma.article.update({
    where: { id: articleId },
    data: { viewCount: { increment: 1 } } // Atomic!
  });
}

// ✅ GOOD: Redis atomic counter với Lua script
const redis = new Redis();

async function rateLimitCheck(userId: string, limit: number): Promise<boolean> {
  const key = `rate:${userId}:${Math.floor(Date.now() / 60000)}`; // Per minute

  // INCR là atomic trong Redis
  const count = await redis.incr(key);
  if (count === 1) {
    await redis.expire(key, 60); // Set TTL on first increment
  }

  return count <= limit;
}

// ✅ GOOD: Lua script cho complex atomic operation trong Redis
async function redeemPoints_GOOD(
  redis: Redis,
  userId: string,
  pointsToRedeem: number
): Promise<boolean> {
  const key = `points:${userId}`;

  // Lua script: check và deduct atomic (EVALSHA)
  const luaScript = `
    local current = tonumber(redis.call('GET', KEYS[1]) or 0)
    local redeem = tonumber(ARGV[1])
    if current >= redeem then
      redis.call('DECRBY', KEYS[1], redeem)
      return 1
    else
      return 0
    end
  `;

  const result = await redis.eval(luaScript, 1, key, pointsToRedeem.toString());
  return result === 1; // 1 = success, 0 = insufficient points
}

// ✅ GOOD: Database-level unique constraint để prevent duplicate
// schema.prisma:
// model CouponUsage {
//   id       Int    @id @default(autoincrement())
//   userId   Int
//   couponId Int
//   @@unique([userId, couponId])  ← DB constraint prevents duplicate redemption
// }

async function redeemCouponOnce_GOOD(userId: number, couponId: number) {
  try {
    return await prisma.couponUsage.create({
      data: { userId, couponId }
    });
  } catch (error) {
    // Unique constraint violation = already redeemed
    if (error instanceof Prisma.PrismaClientKnownRequestError && error.code === 'P2002') {
      throw new Error('Coupon already redeemed by this user');
    }
    throw error;
  }
}
```

### 7. Phòng ngừa

```javascript
// Code review checklist:
// 1. Mọi counter/balance update phải dùng increment/decrement atomic
// 2. Check-then-act pattern phải trong transaction với proper isolation
// 3. Unique constraints ở DB level cho "one per user" operations

// ESLint: warn khi assignment từ property của object (potential RMW)
module.exports = {
  rules: {
    'no-restricted-syntax': [
      'warn',
      {
        // Phát hiện: obj.count = obj.count + n (thay vì atomic DB op)
        selector: "AssignmentExpression[right.type='BinaryExpression'][right.left.type='MemberExpression']",
        message: 'Potential race condition. Use atomic DB operations (increment/decrement) instead.'
      }
    ]
  }
};
```

---

## Pattern 08: Migration Rollback Thiếu

### 1. Tên
**Migration Database Thiếu Rollback** (Missing Migration Rollback Strategy)

### 2. Phân loại
- **Domain:** Data Integrity / DevOps
- **Subcategory:** Database Migration, Schema Management, Deployment

### 3. Mức nghiêm trọng
🟡 **MEDIUM** - Khi deploy lỗi, không thể rollback về trạng thái trước → downtime kéo dài, dữ liệu có thể bị mất

### 4. Vấn đề

Nhiều migration chỉ có "up" (apply) mà không có "down" (rollback). Destructive operations (DROP COLUMN, DROP TABLE) là irreversible. Migration không idempotent, chạy 2 lần sẽ fail. Không test migration trên staging trước production.

```
MIGRATION WITHOUT ROLLBACK RISK:
┌────────────────────────────────────────────────────────────────┐
│  Deploy v2.0.0:                                                │
│    Migration 001_add_user_profile.up:                          │
│      ALTER TABLE users ADD COLUMN profile_data JSONB;         │
│      ← OK                                                      │
│    Migration 002_drop_old_column.up:                           │
│      ALTER TABLE users DROP COLUMN legacy_field; ← RUNS OK    │
│                                                                │
│  v2.0.0 has critical bug → need rollback to v1.9.0!           │
│                                                                │
│  Migration 002_drop_old_column.DOWN:  ← DOES NOT EXIST!       │
│    Cannot restore "legacy_field" data → STUCK!                 │
│                                                                │
│  Result: Cannot rollback. Must hotfix forward. Downtime!       │
│                                                                │
│  SAFE PATTERN: Expand-Contract (Blue-Green Migration)          │
│  Phase 1: ADD new column (backward compatible)                 │
│  Phase 2: Deploy app using both columns                        │
│  Phase 3: Migrate data                                         │
│  Phase 4: Deploy app using only new column                     │
│  Phase 5: DROP old column (only after confirmed stable)        │
└────────────────────────────────────────────────────────────────┘
```

### 5. Phát hiện trong mã nguồn

**Dấu hiệu nhận biết:**
- Migration files chỉ có `up` function, không có `down`
- `DROP COLUMN` / `DROP TABLE` trong migration mà không có data backup step
- Migration không kiểm tra idempotency (`IF EXISTS` / `IF NOT EXISTS`)
- Không có migration test trong CI/CD

**Ripgrep regex để tìm:**
```bash
# Tìm migration files thiếu down function
rg "exports\.up|module\.exports\.up|async up" migrations/ -l | while read f; do
  rg "exports\.down|module\.exports\.down|async down" "$f" -l 2>/dev/null || echo "MISSING DOWN: $f"
done

# Tìm DROP statements trong migrations (nguy hiểm)
rg --type ts "DROP TABLE|DROP COLUMN|TRUNCATE" migrations/ -n

# Tìm ALTER TABLE không có IF EXISTS (không idempotent)
rg "ALTER TABLE" migrations/ -n | grep -v "IF EXISTS\|IF NOT EXISTS"

# Tìm migration files với Prisma
rg "migration" prisma/migrations/ -l 2>/dev/null
```

### 6. Giải pháp

```typescript
// ❌ BAD: Migration chỉ có up, không có down
// migrations/001_add_email_verified.ts
import { Knex } from 'knex';

export async function up(knex: Knex): Promise<void> {
  await knex.schema.table('users', (table) => {
    table.boolean('email_verified').defaultTo(false);
    table.timestamp('email_verified_at').nullable();
  });
}
// ← Không có down() function!

// ✅ GOOD: Migration với down rollback đầy đủ
// migrations/001_add_email_verified.ts
export async function up(knex: Knex): Promise<void> {
  // Kiểm tra idempotency trước
  const hasColumn = await knex.schema.hasColumn('users', 'email_verified');
  if (!hasColumn) {
    await knex.schema.table('users', (table) => {
      table.boolean('email_verified').defaultTo(false).notNullable();
      table.timestamp('email_verified_at').nullable();
    });
  }
}

export async function down(knex: Knex): Promise<void> {
  const hasColumn = await knex.schema.hasColumn('users', 'email_verified');
  if (hasColumn) {
    await knex.schema.table('users', (table) => {
      table.dropColumn('email_verified');
      table.dropColumn('email_verified_at');
    });
  }
}

// ✅ GOOD: Expand-Contract pattern cho breaking changes
// Phase 1 migration: ADD new column (keep old)
// migrations/002_add_full_name_expand.ts
export async function up(knex: Knex): Promise<void> {
  await knex.schema.table('users', (table) => {
    // ADD new columns, keep old 'name' column
    table.string('first_name', 100).nullable();
    table.string('last_name', 100).nullable();
  });

  // Migrate existing data
  await knex.raw(`
    UPDATE users
    SET first_name = SPLIT_PART(name, ' ', 1),
        last_name  = NULLIF(SPLIT_PART(name, ' ', 2), '')
    WHERE first_name IS NULL
  `);

  // Make not-null after data migration
  await knex.schema.table('users', (table) => {
    table.string('first_name', 100).notNullable().alter();
  });
}

export async function down(knex: Knex): Promise<void> {
  // Safe rollback: just drop new columns, old 'name' column still exists
  await knex.schema.table('users', (table) => {
    table.dropColumn('first_name');
    table.dropColumn('last_name');
  });
}

// Phase 2 migration (SEPARATE deploy, after Phase 1 confirmed stable):
// migrations/003_drop_name_contract.ts
export async function up(knex: Knex): Promise<void> {
  await knex.schema.table('users', (table) => {
    table.dropColumn('name'); // Now safe to drop
  });
}

export async function down(knex: Knex): Promise<void> {
  // Restore old column from new ones
  await knex.schema.table('users', (table) => {
    table.string('name', 255).nullable();
  });
  await knex.raw(`
    UPDATE users SET name = CONCAT(first_name, ' ', COALESCE(last_name, ''))
  `);
}
```

### 7. Phòng ngừa

```javascript
// CI/CD: Test migration up + down + up trong pipeline
// package.json scripts:
// "migration:test": "knex migrate:latest && knex migrate:rollback && knex migrate:latest"

// Custom script để validate tất cả migrations có down():
// scripts/validate-migrations.ts
import fs from 'fs';
import path from 'path';

const migrationsDir = path.join(process.cwd(), 'migrations');
const files = fs.readdirSync(migrationsDir).filter((f) => f.endsWith('.ts'));

let hasError = false;
for (const file of files) {
  const content = fs.readFileSync(path.join(migrationsDir, file), 'utf8');
  if (!content.includes('export async function down')) {
    console.error(`MISSING DOWN: ${file}`);
    hasError = true;
  }
}

if (hasError) process.exit(1);
console.log('All migrations have down() functions.');
```

---

## Pattern 09: Index Thiếu Cho Query Patterns

### 1. Tên
**Thiếu Index Cho Các Patterns Truy Vấn** (Missing Database Indexes for Query Patterns)

### 2. Phân loại
- **Domain:** Data Integrity / Performance
- **Subcategory:** Database Indexing, Query Optimization, Full Table Scan

### 3. Mức nghiêm trọng
🟠 **HIGH** - Full table scan với N triệu records làm timeout query, database CPU spike, ảnh hưởng toàn bộ hệ thống

### 4. Vấn đề

Index thiếu khiến database phải scan toàn bộ bảng (Sequential Scan / Full Table Scan) thay vì dùng index O(log N). Với 1 triệu records, full scan có thể mất vài giây, làm timeout requests và exhaust database connection pool.

```
QUERY PERFORMANCE: WITH vs WITHOUT INDEX
┌────────────────────────────────────────────────────────────────┐
│  Table: orders (1,000,000 rows)                                │
│  Query: SELECT * FROM orders WHERE user_id = 12345            │
│                                                                │
│  WITHOUT INDEX (Sequential Scan):                              │
│  DB reads ALL 1,000,000 rows one by one                        │
│  ┌──┬──┬──┬──┬──┬──┬─────────────────────────────┬──┐        │
│  │r1│r2│r3│r4│r5│r6│... 999,994 more rows ...    │rN│        │
│  └──┴──┴──┴──┴──┴──┴─────────────────────────────┴──┘        │
│  Time: ~2,000ms  ← Unacceptable!                               │
│                                                                │
│  WITH INDEX (B-Tree Index on user_id):                         │
│  DB navigates tree: O(log 1,000,000) ≈ 20 comparisons         │
│  ┌─────────────┐                                               │
│  │  Index Node │──▶ 3 matching rows found directly            │
│  └─────────────┘                                               │
│  Time: ~2ms  ✅  (1000x faster!)                              │
└────────────────────────────────────────────────────────────────┘
```

### 5. Phát hiện trong mã nguồn

**Dấu hiệu nhận biết:**
- `WHERE` clause trên columns không có `@index` / `@@index` trong Prisma schema
- `findMany` với `where` + `orderBy` nhưng không có composite index
- Foreign key columns không có index (Prisma không tự tạo index cho FK trong tất cả DB)
- Query logs show "Seq Scan" hoặc "Full Table Scan"

**Ripgrep regex để tìm:**
```bash
# Tìm Prisma findMany với where complex (cần kiểm tra index)
rg --type ts "findMany\s*\(\s*\{[^}]*where" -n -A 10

# Tìm columns thường dùng trong where nhưng thiếu @index
rg "findMany.*where.*status\|findMany.*where.*type\|findMany.*where.*userId" --type ts -n

# Kiểm tra Prisma schema có đủ index không
rg "@@index\|@unique\|@@unique" prisma/schema.prisma -n

# Tìm orderBy fields (cần index nếu kết hợp với where)
rg --type ts "orderBy.*createdAt\|orderBy.*updatedAt\|orderBy.*status" -n

# Tìm LIKE query (cần GIN index với pg_trgm)
rg --type ts "contains\|startsWith\|mode.*insensitive" -n
```

### 6. Giải pháp

```prisma
// ❌ BAD: Schema thiếu index cho query patterns thực tế
// schema.prisma
model Order {
  id        Int      @id @default(autoincrement())
  userId    Int      // ← Thường query WHERE userId = ? nhưng không có index!
  status    String   // ← Thường filter WHERE status = 'pending'
  createdAt DateTime @default(now())
  updatedAt DateTime @updatedAt
  // Không có @@index nào!
}

// ✅ GOOD: Index phù hợp với query patterns
model Order {
  id        Int      @id @default(autoincrement())
  userId    Int
  status    String
  createdAt DateTime @default(now())
  updatedAt DateTime @updatedAt

  // Index đơn cho FK lookup
  @@index([userId])

  // Composite index cho query: WHERE userId = ? AND status = ? ORDER BY createdAt DESC
  @@index([userId, status, createdAt(sort: Desc)])

  // Index cho status filtering (nếu query riêng)
  @@index([status, createdAt(sort: Desc)])
}

model Product {
  id          Int      @id @default(autoincrement())
  name        String
  categoryId  Int
  price       Decimal
  isActive    Boolean  @default(true)
  createdAt   DateTime @default(now())

  // Full-text search cần GIN index (raw SQL migration)
  // @@index([name]) ← B-tree không tốt cho LIKE %keyword%

  // Composite cho listing page: active products by category, sorted by price
  @@index([categoryId, isActive, price])

  // Partial index tương đương cần raw SQL
}
```

```typescript
// TypeScript: Thêm index qua Prisma migration
// Sau khi cập nhật schema.prisma, chạy:
// npx prisma migrate dev --name add_order_indexes

// ✅ GOOD: Raw SQL để thêm specialized indexes
// migrations/add_specialized_indexes.ts
import { Knex } from 'knex';

export async function up(knex: Knex): Promise<void> {
  // GIN index cho full-text search (PostgreSQL)
  await knex.raw(`
    CREATE EXTENSION IF NOT EXISTS pg_trgm;
    CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_products_name_trgm
      ON products USING GIN (name gin_trgm_ops);
  `);

  // Partial index: chỉ index active orders (tiết kiệm space)
  await knex.raw(`
    CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_orders_pending_created
      ON orders (created_at DESC)
      WHERE status = 'pending';
  `);

  // Covering index: index bao gồm tất cả columns cần SELECT (tránh table lookup)
  await knex.raw(`
    CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_orders_user_covering
      ON orders (user_id, status, created_at DESC)
      INCLUDE (total_amount, currency);
  `);
}

export async function down(knex: Knex): Promise<void> {
  await knex.raw('DROP INDEX IF EXISTS idx_products_name_trgm');
  await knex.raw('DROP INDEX IF EXISTS idx_orders_pending_created');
  await knex.raw('DROP INDEX IF EXISTS idx_orders_user_covering');
}

// ✅ GOOD: Detect slow queries với EXPLAIN ANALYZE
async function debugSlowQuery(prisma: PrismaClient, userId: number) {
  const explain = await prisma.$queryRaw`
    EXPLAIN ANALYZE
    SELECT * FROM orders
    WHERE user_id = ${userId}
      AND status = 'pending'
    ORDER BY created_at DESC
    LIMIT 20
  `;
  console.log('Query plan:', explain);
  // Look for "Seq Scan" → needs index
  // Look for "Index Scan" → index working
}
```

### 7. Phòng ngừa

```javascript
// Prisma: Enable query logging và detect slow queries
const prisma = new PrismaClient({
  log: [{ level: 'query', emit: 'event' }]
});

prisma.$on('query', (e) => {
  if (e.duration > 100) { // Query > 100ms
    console.warn(`[SLOW QUERY] ${e.duration}ms: ${e.query}`);
  }
});

// PostgreSQL: Bật auto_explain để log slow queries
// postgresql.conf:
// shared_preload_libraries = 'auto_explain'
// auto_explain.log_min_duration = '100ms'
// auto_explain.log_analyze = true
```

---

## Pattern 10: Soft Delete Inconsistency

### 1. Tên
**Không Nhất Quán Khi Xóa Mềm** (Soft Delete Inconsistency)

### 2. Phân loại
- **Domain:** Data Integrity / Data Management
- **Subcategory:** Soft Delete Pattern, Data Consistency, Query Filters

### 3. Mức nghiêm trọng
🟡 **MEDIUM** - Dữ liệu "đã xóa" vẫn xuất hiện trong queries, unique constraints bị vi phạm, business logic sai

### 4. Vấn đề

Soft delete dùng `deletedAt` / `isDeleted` field thay vì xóa thật. Nhưng nếu không filter nhất quán trong mọi query, "deleted" records vẫn xuất hiện. Unique indexes không hoạt động đúng cho soft-deleted records. Relations lấy về cả deleted records.

```
SOFT DELETE INCONSISTENCY SCENARIOS:
┌────────────────────────────────────────────────────────────────┐
│  SCENARIO 1: Leaked soft-deleted data                          │
│  users table: [Alice(active), Bob(deleted), Carol(active)]     │
│                                                                │
│  Query: prisma.user.findMany()  ← No filter!                   │
│  Result: [Alice, Bob, Carol]  ← Bob should NOT appear!         │
│                                                                │
│  SCENARIO 2: Unique constraint bypass                          │
│  User "alice@mail.com" soft-deleted (deletedAt = now())       │
│  New user registers with "alice@mail.com"                      │
│  Error: UNIQUE CONSTRAINT VIOLATION!                           │
│  ← Old soft-deleted record blocks new registration            │
│                                                                │
│  SCENARIO 3: Foreign key returns deleted records              │
│  Order.include({ user: true })                                 │
│  ← Returns order even if associated user is soft-deleted       │
└────────────────────────────────────────────────────────────────┘
```

### 5. Phát hiện trong mã nguồn

**Dấu hiệu nhận biết:**
- `findMany()` không có `where: { deletedAt: null }` filter
- Unique index trên email/username không handle soft-deleted records
- `include` relations không filter deleted
- Prisma middleware cho soft delete không được áp dụng cho tất cả models

**Ripgrep regex để tìm:**
```bash
# Tìm findMany không có deletedAt filter (trong project dùng soft delete)
rg --type ts "\.findMany\(\s*\)" -n
rg --type ts "\.findMany\(\s*\{[^}]*\}\s*\)" -n | grep -v "deletedAt\|isDeleted"

# Tìm findUnique/findFirst không filter deletedAt
rg --type ts "\.findFirst\(\s*\{[^}]*where[^}]*\}" -n | grep -v "deletedAt"

# Tìm delete operations (nên là soft delete nhưng có thể là hard delete)
rg --type ts "\.delete\(\|\.deleteMany\(" -n

# Kiểm tra Prisma schema có deletedAt không
rg "deletedAt\|isDeleted\|deleted_at" prisma/schema.prisma -n
```

### 6. Giải pháp

```typescript
import { PrismaClient, Prisma } from '@prisma/client';

// ❌ BAD: Soft delete không nhất quán
const prisma = new PrismaClient();

// Delete thật thay vì soft delete
async function deleteUser_BAD(id: number) {
  return prisma.user.delete({ where: { id } }); // Hard delete!
}

// Query không filter deleted records
async function getActiveUsers_BAD() {
  return prisma.user.findMany(); // Trả về cả deleted users!
}

// ✅ GOOD: Prisma middleware cho soft delete toàn cục
// prisma/client.ts
const prisma = new PrismaClient();

// Middleware tự động:
// 1. Chuyển delete → update với deletedAt
// 2. Thêm filter deletedAt = null vào mọi findMany/findFirst
prisma.$use(async (params, next) => {
  const SOFT_DELETE_MODELS = ['User', 'Post', 'Comment'];

  if (!SOFT_DELETE_MODELS.includes(params.model ?? '')) {
    return next(params);
  }

  // Chuyển delete → soft delete
  if (params.action === 'delete') {
    params.action = 'update';
    params.args.data = { deletedAt: new Date() };
  }

  if (params.action === 'deleteMany') {
    params.action = 'updateMany';
    params.args.data = { deletedAt: new Date() };
  }

  // Auto-filter: exclude soft-deleted records
  const readActions = ['findUnique', 'findFirst', 'findMany', 'count', 'aggregate'];
  if (readActions.includes(params.action)) {
    if (!params.args) params.args = {};
    if (!params.args.where) params.args.where = {};

    // Chỉ filter nếu chưa có deletedAt condition
    if (params.args.where.deletedAt === undefined) {
      params.args.where.deletedAt = null;
    }
  }

  return next(params);
});

// ✅ GOOD: Utility để bypass filter (admin use case)
async function getAllUsersIncludingDeleted() {
  // Dùng $queryRaw để bypass middleware
  return prisma.$queryRaw<User[]>`
    SELECT * FROM users ORDER BY created_at DESC
  `;
}

// ✅ GOOD: Unique constraint cho soft delete (PostgreSQL partial index)
// migration: add partial unique index
// CREATE UNIQUE INDEX users_email_active_unique
//   ON users (email)
//   WHERE deleted_at IS NULL;
// ← Chỉ enforce unique cho non-deleted records!

// migrations/add_soft_delete_unique_indexes.ts
import { Knex } from 'knex';

export async function up(knex: Knex): Promise<void> {
  // Xóa unique index cũ (nếu có)
  await knex.raw('DROP INDEX IF EXISTS users_email_unique');

  // Partial unique index: unique chỉ với active records
  await knex.raw(`
    CREATE UNIQUE INDEX IF NOT EXISTS users_email_active_unique
      ON users (email)
      WHERE deleted_at IS NULL
  `);
}

export async function down(knex: Knex): Promise<void> {
  await knex.raw('DROP INDEX IF EXISTS users_email_active_unique');
  await knex.schema.table('users', (t) => {
    t.unique(['email']); // Restore original unique
  });
}

// ✅ GOOD: Soft delete với cascade (cập nhật related records)
async function softDeleteUser(userId: number) {
  return prisma.$transaction(async (tx) => {
    const now = new Date();

    // Soft delete user
    await tx.user.update({
      where: { id: userId },
      data: { deletedAt: now }
    });

    // Cascade soft delete related data
    await tx.userSession.updateMany({
      where: { userId, deletedAt: null },
      data: { deletedAt: now }
    });

    await tx.post.updateMany({
      where: { authorId: userId, deletedAt: null },
      data: { deletedAt: now }
    });
  });
}
```

### 7. Phòng ngừa

```javascript
// ESLint: cảnh báo khi gọi .delete() trực tiếp trong project dùng soft delete
module.exports = {
  rules: {
    'no-restricted-syntax': [
      'warn',
      {
        // Phát hiện prisma.model.delete() call
        selector:
          "CallExpression[callee.type='MemberExpression'][callee.property.name='delete']",
        message:
          'Use soft delete (update with deletedAt) instead of hard delete. If intentional, add // eslint-disable-next-line comment.'
      }
    ]
  }
};

// Test để đảm bảo middleware hoạt động
// __tests__/soft-delete.test.ts
describe('Soft Delete Middleware', () => {
  it('should filter deleted records from findMany', async () => {
    await prisma.user.update({
      where: { id: testUserId },
      data: { deletedAt: new Date() }
    });

    const users = await prisma.user.findMany({
      where: { id: testUserId }
    });

    expect(users).toHaveLength(0); // Phải không thấy user đã xóa
  });
});
```

---

## Tóm Tắt Domain 04

| # | Pattern | Mức độ | Impact chính |
|---|---------|--------|--------------|
| 01 | ORM N+1 Query | 🟠 HIGH | Database quá tải, timeout |
| 02 | Transaction Isolation Sai | 🔴 CRITICAL | Lost update, overselling |
| 03 | MongoDB Schema Design Sai | 🟠 HIGH | Document size limit, inconsistency |
| 04 | JSON BigInt Loss | 🟠 HIGH | ID sai âm thầm, 404 errors |
| 05 | Date Timezone Pitfalls | 🟠 HIGH | Appointment sai giờ, report sai ngày |
| 06 | Buffer Encoding Mismatch | 🟡 MEDIUM | Data corruption, token sai |
| 07 | Race Condition Read-Modify-Write | 🟠 HIGH | Oversell, double-redeem |
| 08 | Migration Rollback Thiếu | 🟡 MEDIUM | Không rollback được khi lỗi |
| 09 | Index Thiếu Cho Query Patterns | 🟠 HIGH | Full table scan, timeout |
| 10 | Soft Delete Inconsistency | 🟡 MEDIUM | Dữ liệu "xóa" vẫn xuất hiện |

### Thống kê theo mức nghiêm trọng
- 🔴 **CRITICAL**: 1 pattern (Transaction Isolation)
- 🟠 **HIGH**: 6 patterns
- 🟡 **MEDIUM**: 3 patterns

### Checklist Phòng Ngừa Nhanh
```
Database Layer:
  [ ] Mọi FK column có @index
  [ ] Composite index cho query patterns thực tế
  [ ] Partial unique index cho soft-deleted records
  [ ] PostgreSQL: dùng TIMESTAMPTZ, BIGINT đúng chỗ

ORM Layer:
  [ ] Prisma: include/TypeORM: relations thay vì N+1
  [ ] Transaction wrap cho multi-step operations
  [ ] Middleware soft delete áp dụng toàn cục
  [ ] Migration có down() function

Application Layer:
  [ ] BigInt serialize sang String trong API response
  [ ] Date luôn UTC, parse với timezone explicit
  [ ] Buffer.from() luôn chỉ định encoding
  [ ] Atomic operations cho counter/balance updates

Process:
  [ ] Test migration up/down/up trong CI
  [ ] EXPLAIN ANALYZE cho queries mới
  [ ] Query logging trong development
```
