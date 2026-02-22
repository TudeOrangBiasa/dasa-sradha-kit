# Domain 09: Thiết Kế API (API Design)

> Go patterns liên quan đến API design: REST conventions, middleware, validation, pagination, graceful shutdown.

---

## Pattern 01: REST Conventions Vi Phạm

### Tên
REST Conventions Vi Phạm (Verb Trong URL, Sai HTTP Method)

### Phân loại
API Design / REST / Convention

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```
❌ POST /api/getUsers         → verb in URL
❌ GET  /api/deleteUser/123   → GET for mutation
❌ POST /api/users/update     → verb instead of method
❌ GET  /api/user_list        → inconsistent naming
```

### Phát hiện

```bash
rg --type go "HandleFunc|Handle\(" -n | rg "(get|create|update|delete|list|fetch)"
rg --type go "r\.Method\s*==\s*\"GET\"" -n
rg --type go "mux\.(Get|Post|Put|Delete)\(" -n
```

### Giải pháp

❌ **BAD**
```go
http.HandleFunc("/api/getUsers", getUsers)
http.HandleFunc("/api/createUser", createUser)
http.HandleFunc("/api/deleteUser", deleteUser)
```

✅ **GOOD**
```go
r := chi.NewRouter()
r.Route("/api/users", func(r chi.Router) {
    r.Get("/", listUsers)        // GET    /api/users
    r.Post("/", createUser)      // POST   /api/users
    r.Get("/{id}", getUser)      // GET    /api/users/123
    r.Put("/{id}", updateUser)   // PUT    /api/users/123
    r.Delete("/{id}", deleteUser) // DELETE /api/users/123
})
```

### Phòng ngừa
- [ ] Nouns in URLs, verbs via HTTP methods
- [ ] Plural resource names (`/users` not `/user`)
- [ ] Consistent naming (kebab-case or snake_case)
- Tool: chi, gorilla/mux, echo routers

---

## Pattern 02: Middleware Chain Order Sai

### Tên
Middleware Chain Order Sai (Wrong Middleware Execution Order)

### Phân loại
API Design / Middleware / Order

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```go
r.Use(rateLimiter)    // 1. Rate limit ← checked before auth!
r.Use(authenticate)   // 2. Auth
r.Use(authorize)      // 3. Authz
// Unauthenticated users consume rate limit quota!
// Auth errors not logged with request ID
```

### Phát hiện

```bash
rg --type go "\.Use\(" -n
rg --type go "middleware\." -n
rg --type go "func.*http\.Handler.*http\.Handler" -n
```

### Giải pháp

❌ **BAD**
```go
r.Use(rateLimiter)
r.Use(cors)
r.Use(auth)
r.Use(requestID) // Too late — previous middleware don't have request ID
```

✅ **GOOD**
```go
r.Use(requestID)    // 1. Request ID (first — all logs need it)
r.Use(logger)       // 2. Logging (captures timing)
r.Use(recover)      // 3. Panic recovery
r.Use(cors)         // 4. CORS (before auth to handle preflight)
r.Use(authenticate) // 5. Auth
r.Use(rateLimiter)  // 6. Rate limit (after auth — per-user limits)
r.Use(authorize)    // 7. Authorization
```

### Phòng ngừa
- [ ] Request ID → Logger → Recovery → CORS → Auth → Rate Limit → Authz
- [ ] Document middleware order in comments
- [ ] Test middleware chain with integration tests

---

## Pattern 03: Graceful Shutdown Thiếu

### Tên
Graceful Shutdown Thiếu (Server Kills In-Flight Requests)

### Phân loại
API Design / Server / Lifecycle

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```go
log.Fatal(http.ListenAndServe(":8080", handler))
// SIGTERM → process killed immediately
// In-flight requests dropped
// DB connections not closed
```

### Phát hiện

```bash
rg --type go "http\.ListenAndServe\(" -n
rg --type go "server\.Shutdown\(" -n
rg --type go "signal\.Notify\(" -n
```

### Giải pháp

❌ **BAD**
```go
log.Fatal(http.ListenAndServe(":8080", handler))
```

✅ **GOOD**
```go
srv := &http.Server{Addr: ":8080", Handler: handler}

go func() {
    if err := srv.ListenAndServe(); err != http.ErrServerClosed {
        log.Fatalf("HTTP server error: %v", err)
    }
}()

// Wait for shutdown signal
quit := make(chan os.Signal, 1)
signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
<-quit

log.Println("Shutting down...")
ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
defer cancel()

if err := srv.Shutdown(ctx); err != nil {
    log.Fatalf("Forced shutdown: %v", err)
}
// Close DB, Redis, etc.
db.Close()
log.Println("Server stopped gracefully")
```

### Phòng ngừa
- [ ] `server.Shutdown()` with timeout context
- [ ] Handle SIGTERM + SIGINT
- [ ] Close all resources after shutdown
- Tool: `signal.Notify`, context timeout

---

## Pattern 04: Request Validation Thiếu

### Tên
Request Validation Thiếu (No Input Validation)

### Phân loại
API Design / Validation / Security

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```go
func createUser(w http.ResponseWriter, r *http.Request) {
    var user User
    json.NewDecoder(r.Body).Decode(&user)
    db.Create(&user) // No validation! Empty name? Invalid email? Negative age?
}
```

### Phát hiện

```bash
rg --type go "json\.NewDecoder|json\.Unmarshal" -A 5 | rg -v "validate|Validate"
rg --type go "validator\." -n
```

### Giải pháp

❌ **BAD**
```go
json.NewDecoder(r.Body).Decode(&req)
// Directly use req without validation
```

✅ **GOOD**
```go
import "github.com/go-playground/validator/v10"

var validate = validator.New()

type CreateUserRequest struct {
    Name  string `json:"name" validate:"required,min=2,max=100"`
    Email string `json:"email" validate:"required,email"`
    Age   int    `json:"age" validate:"required,min=0,max=150"`
}

func createUser(w http.ResponseWriter, r *http.Request) {
    var req CreateUserRequest
    if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
        respondError(w, http.StatusBadRequest, "Invalid JSON")
        return
    }
    if err := validate.Struct(req); err != nil {
        respondValidationError(w, err.(validator.ValidationErrors))
        return
    }
    // req is validated
}
```

### Phòng ngừa
- [ ] Validate ALL input before processing
- [ ] Use `go-playground/validator` for struct validation
- [ ] Return structured error messages
- Tool: `go-playground/validator`

---

## Pattern 05: Response Format Inconsistent

### Tên
Response Format Inconsistent (Different Error/Success Formats)

### Phân loại
API Design / Response / Consistency

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```
GET /users/1  → {"id":1,"name":"John"}
GET /users/99 → "User not found"           ← plain text!
POST /users   → {"error":"validation failed"} ← different structure
GET /products → [{"id":1}]                  ← no wrapper
```

### Phát hiện

```bash
rg --type go "json\.NewEncoder|json\.Marshal" -n
rg --type go "http\.Error\(" -n
rg --type go "w\.Write\(|fmt\.Fprint" -n
```

### Giải pháp

❌ **BAD**
```go
w.Write([]byte("Not found"))
json.NewEncoder(w).Encode(user)
json.NewEncoder(w).Encode(map[string]string{"error": msg})
```

✅ **GOOD**
```go
type APIResponse struct {
    Data    interface{} `json:"data,omitempty"`
    Error   *APIError   `json:"error,omitempty"`
    Meta    *Meta       `json:"meta,omitempty"`
}

type APIError struct {
    Code    string `json:"code"`
    Message string `json:"message"`
}

func respondJSON(w http.ResponseWriter, status int, data interface{}) {
    w.Header().Set("Content-Type", "application/json")
    w.WriteHeader(status)
    json.NewEncoder(w).Encode(APIResponse{Data: data})
}

func respondError(w http.ResponseWriter, status int, code, message string) {
    w.Header().Set("Content-Type", "application/json")
    w.WriteHeader(status)
    json.NewEncoder(w).Encode(APIResponse{Error: &APIError{Code: code, Message: message}})
}
```

### Phòng ngừa
- [ ] Consistent response envelope for all endpoints
- [ ] Always JSON `Content-Type`
- [ ] Error responses with code + message
- Tool: OpenAPI spec validation

---

## Pattern 06: API Versioning Thiếu

### Tên
API Versioning Thiếu (No API Version Strategy)

### Phân loại
API Design / Versioning / Breaking Change

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```
Breaking change to /api/users response:
→ All clients break immediately
→ No migration path
→ Can't run old and new simultaneously
```

### Phát hiện

```bash
rg --type go "/api/v\d" -n
rg --type go "version|Version" -n --glob "*route*" --glob "*router*"
rg --type go "Accept.*version|X-API-Version" -n
```

### Giải pháp

❌ **BAD**
```go
r.Route("/api/users", func(r chi.Router) { /* ... */ })
// No versioning — breaking changes affect everyone
```

✅ **GOOD**
```go
// URL path versioning (most common):
r.Route("/api/v1", func(r chi.Router) {
    r.Route("/users", func(r chi.Router) { r.Get("/", listUsersV1) })
})
r.Route("/api/v2", func(r chi.Router) {
    r.Route("/users", func(r chi.Router) { r.Get("/", listUsersV2) })
})

// Or header-based:
r.Route("/api/users", func(r chi.Router) {
    r.With(apiVersion("v1")).Get("/", listUsersV1)
    r.With(apiVersion("v2")).Get("/", listUsersV2)
})
```

### Phòng ngừa
- [ ] Version API from day one
- [ ] URL path versioning for simplicity
- [ ] Deprecation headers for old versions
- Tool: API gateway for version routing

---

## Pattern 07: Rate Limiting Thiếu

### Tên
Rate Limiting Thiếu (No Request Rate Limiting)

### Phân loại
API Design / Security / DDoS

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```
No rate limiting:
→ Single client can exhaust all resources
→ DDoS amplification
→ Brute force attacks on login
→ API abuse (scraping)
```

### Phát hiện

```bash
rg --type go "rate\.Limiter|x/time/rate" -n
rg --type go "RateLimit|rateLimit|throttle" -i -n
rg --type go "429|TooManyRequests" -n
```

### Giải pháp

❌ **BAD**
```go
r.Post("/api/login", loginHandler) // No rate limiting
```

✅ **GOOD**
```go
import "golang.org/x/time/rate"

func rateLimitMiddleware(rps float64, burst int) func(http.Handler) http.Handler {
    limiter := rate.NewLimiter(rate.Limit(rps), burst)
    return func(next http.Handler) http.Handler {
        return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
            if !limiter.Allow() {
                w.Header().Set("Retry-After", "1")
                http.Error(w, "Too Many Requests", http.StatusTooManyRequests)
                return
            }
            next.ServeHTTP(w, r)
        })
    }
}

r.With(rateLimitMiddleware(10, 20)).Post("/api/login", loginHandler)
```

### Phòng ngừa
- [ ] Rate limit all public endpoints
- [ ] Per-IP or per-user limits
- [ ] Stricter limits on auth endpoints
- Tool: `golang.org/x/time/rate`, Redis-based for distributed

---

## Pattern 08: Pagination Offset Problem

### Tên
Pagination Offset Problem (Deep Offset Performance)

### Phân loại
API Design / Pagination / Performance

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```
GET /api/users?page=1000&limit=20
→ SELECT * FROM users OFFSET 20000 LIMIT 20
→ DB scans and discards 20,000 rows!
→ Slower as page number increases
```

### Phát hiện

```bash
rg --type go "OFFSET|offset" -n
rg --type go "page.*limit|Page.*Limit" -n
rg --type go "cursor|Cursor" -n
```

### Giải pháp

❌ **BAD**
```go
// Offset pagination:
query := fmt.Sprintf("SELECT * FROM users ORDER BY id LIMIT %d OFFSET %d",
    limit, (page-1)*limit) // Slow for large offsets
```

✅ **GOOD**
```go
// Cursor-based pagination:
type PageInfo struct {
    NextCursor string `json:"next_cursor,omitempty"`
    HasMore    bool   `json:"has_more"`
}

func listUsers(cursor string, limit int) ([]User, PageInfo, error) {
    query := "SELECT * FROM users WHERE id > $1 ORDER BY id LIMIT $2"
    rows, err := db.Query(query, cursor, limit+1)
    // Fetch limit+1 to check if more exist
    users := parseRows(rows)
    hasMore := len(users) > limit
    if hasMore {
        users = users[:limit]
    }
    var nextCursor string
    if hasMore {
        nextCursor = users[len(users)-1].ID
    }
    return users, PageInfo{NextCursor: nextCursor, HasMore: hasMore}, nil
}
```

### Phòng ngừa
- [ ] Cursor-based pagination for large datasets
- [ ] Offset OK for small datasets (<10K rows)
- [ ] Always include `has_more` in response
- Tool: DB EXPLAIN to verify query plan

---

## Pattern 09: Health Check Thiếu

### Tên
Health Check Thiếu (No Health Check Endpoint)

### Phân loại
API Design / Operations / Monitoring

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```
Kubernetes/load balancer needs to know if service is healthy
Without health check:
→ Traffic sent to unhealthy instances
→ DB connection lost but service still "up"
→ No automated recovery
```

### Phát hiện

```bash
rg --type go "/health|/ready|/live" -n
rg --type go "healthz|readyz|livez" -n
```

### Giải pháp

❌ **BAD**
```go
// No health endpoint — K8s can't check readiness
```

✅ **GOOD**
```go
// Liveness: "is the process alive?"
r.Get("/healthz", func(w http.ResponseWriter, r *http.Request) {
    w.WriteHeader(http.StatusOK)
    json.NewEncoder(w).Encode(map[string]string{"status": "ok"})
})

// Readiness: "can it serve traffic?"
r.Get("/readyz", func(w http.ResponseWriter, r *http.Request) {
    if err := db.Ping(); err != nil {
        w.WriteHeader(http.StatusServiceUnavailable)
        json.NewEncoder(w).Encode(map[string]string{"status": "not ready", "db": err.Error()})
        return
    }
    w.WriteHeader(http.StatusOK)
    json.NewEncoder(w).Encode(map[string]string{"status": "ready"})
})
```

### Phòng ngừa
- [ ] `/healthz` for liveness (lightweight)
- [ ] `/readyz` for readiness (checks dependencies)
- [ ] Skip auth middleware for health endpoints
- Tool: K8s liveness/readiness probes

---

## Pattern 10: OpenAPI Spec Out Of Sync

### Tên
OpenAPI Spec Out Of Sync (API Docs Don't Match Code)

### Phân loại
API Design / Documentation / Consistency

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```
API documentation says: POST /api/users accepts { name, email }
Actual code accepts: { name, email, role }
→ Frontend follows docs → missing field → unexpected behavior
→ Docs become untrustworthy
```

### Phát hiện

```bash
rg --type go "swagger|swag\." -n
rg --type go "@Summary|@Description|@Param" -n
rg "openapi|swagger" -n --glob "*.yaml" --glob "*.json"
```

### Giải pháp

❌ **BAD**
```yaml
# Manual OpenAPI spec — gets outdated quickly
```

✅ **GOOD**
```go
// Generate from code annotations:
// swaggo/swag
// @Summary Create a user
// @Tags users
// @Accept json
// @Produce json
// @Param user body CreateUserRequest true "User to create"
// @Success 201 {object} APIResponse{data=User}
// @Failure 400 {object} APIResponse{error=APIError}
// @Router /api/users [post]
func createUser(w http.ResponseWriter, r *http.Request) { ... }

// Generate: swag init
// Serve: r.Get("/swagger/*", httpSwagger.Handler())
```

### Phòng ngừa
- [ ] Generate OpenAPI from code (swag, ogen)
- [ ] CI: validate spec matches code
- [ ] Serve Swagger UI from app
- Tool: `swaggo/swag`, `ogen`, `oapi-codegen`
