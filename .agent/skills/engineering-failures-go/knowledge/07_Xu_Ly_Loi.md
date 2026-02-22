# Domain 07: Xử Lý Lỗi (Error Handling)

> Go patterns liên quan đến error handling: if err != nil, error wrapping, sentinel errors, panic recovery.

---

## Pattern 01: Error Bỏ Qua (_ = err)

### Tên
Error Bỏ Qua (Discarded Error)

### Phân loại
Error Handling / Ignored / Critical

### Mức nghiêm trọng
CRITICAL 🔴

### Vấn đề

```
result, _ := doSomething()     ← Error discarded!
// hoặc
doSomething()                   ← Return value ignored entirely
// hoặc
_ = json.Unmarshal(data, &obj) ← Explicit discard
```

Errors bị bỏ qua → data corruption, silent failures, security vulnerabilities.

### Phát hiện

```bash
rg --type go "_ = \w+\.\w+\(" -n
rg --type go ",\s*_\s*:?=\s*\w+\(" -n
rg --type go "^\s+\w+\.\w+\(" -n | rg -v "(defer|go |fmt\.Print|log\.|t\.)"
```

### Giải pháp

❌ **BAD**
```go
data, _ := json.Marshal(user)
http.ListenAndServe(":8080", nil)
```

✅ **GOOD**
```go
data, err := json.Marshal(user)
if err != nil {
    return fmt.Errorf("marshaling user: %w", err)
}

if err := http.ListenAndServe(":8080", nil); err != nil {
    log.Fatalf("server failed: %v", err)
}
```

### Phòng ngừa
- [ ] NEVER discard errors (except in tests/defer edge cases)
- Tool: `errcheck` linter, `golangci-lint` với `errcheck`

---

## Pattern 02: Error Wrap Thiếu Context

### Tên
Error Wrap Thiếu Context (Error Without Context)

### Phân loại
Error Handling / Context / Debugging

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```
func getUser(id string) (*User, error) {
    user, err := db.Find(id)
    if err != nil {
        return nil, err  ← Bare return, no context
    }
    return user, nil
}
// Error: "connection refused" — which function? which DB call?
```

### Phát hiện

```bash
rg --type go "return.*,\s*err\s*$" -n
rg --type go "return nil, err" -n
rg --type go "fmt\.Errorf.*%w" -n  # Good pattern (reference)
```

### Giải pháp

❌ **BAD**
```go
if err != nil { return nil, err }
```

✅ **GOOD**
```go
if err != nil {
    return nil, fmt.Errorf("getting user %s: %w", id, err)
}
```

### Phòng ngừa
- [ ] Wrap errors at every return: `fmt.Errorf("context: %w", err)`
- [ ] Include relevant values (IDs, paths) in context
- Tool: `wrapcheck` linter

---

## Pattern 03: Error String Matching

### Tên
Error String Matching (So Sánh Error Bằng String)

### Phân loại
Error Handling / Comparison / Brittle

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```
if err.Error() == "not found" {  ← String comparison!
    // Brittle: error message changes → code breaks
    // Different wrapping → different string
}

if strings.Contains(err.Error(), "timeout") {  ← Substring match
    // Fragile: depends on error message format
}
```

### Phát hiện

```bash
rg --type go "err\.Error\(\)\s*==" -n
rg --type go "strings\.Contains\(.*err\.Error\(\)" -n
rg --type go "strings\.(HasPrefix|HasSuffix)\(.*err" -n
```

### Giải pháp

❌ **BAD**
```go
if err.Error() == "record not found" { }
if strings.Contains(err.Error(), "duplicate key") { }
```

✅ **GOOD**
```go
// errors.Is for sentinel errors
if errors.Is(err, sql.ErrNoRows) { }

// errors.As for error types
var pgErr *pgconn.PgError
if errors.As(err, &pgErr) && pgErr.Code == "23505" {
    // Handle unique violation
}
```

### Phòng ngừa
- [ ] `errors.Is()` cho sentinel errors
- [ ] `errors.As()` cho typed errors
- [ ] NEVER compare `.Error()` strings
- Tool: `golangci-lint` với `errorlint`

---

## Pattern 04: Sentinel Error Public

### Tên
Sentinel Error Public (Exported Sentinel Error)

### Phân loại
Error Handling / API / Coupling

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```
package mylib
var ErrNotFound = errors.New("not found")  ← Public sentinel
// External packages: if errors.Is(err, mylib.ErrNotFound)
// Now ErrNotFound is part of PUBLIC API
// Changing error = BREAKING CHANGE
```

### Phát hiện

```bash
rg --type go "var Err\w+\s*=\s*errors\.New" -n
rg --type go "var Err\w+\s*=\s*fmt\.Errorf" -n
```

### Giải pháp

❌ **BAD**: Export sentinel when not needed
```go
var ErrInternalParsing = errors.New("internal parsing failed") // Implementation detail
```

✅ **GOOD**: Export only intentional API errors
```go
// Public: callers need to check this
var ErrNotFound = errors.New("not found")
var ErrUnauthorized = errors.New("unauthorized")

// Private: internal implementation detail
var errParseFailed = errors.New("parse failed")
```

### Phòng ngừa
- [ ] Export sentinels chỉ khi callers need to check
- [ ] Private sentinels cho internal errors
- [ ] Document exported errors in package docs

---

## Pattern 05: Panic Thay Error

### Tên
Panic Thay Error (Panic Instead of Error Return)

### Phân loại
Error Handling / Panic / Flow

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```
func ParseConfig(path string) Config {
    data, err := os.ReadFile(path)
    if err != nil {
        panic(err)  ← Kills goroutine/process!
    }
    var config Config
    if err := json.Unmarshal(data, &config); err != nil {
        panic(err)  ← For recoverable error!
    }
    return config
}
```

### Phát hiện

```bash
rg --type go "panic\(" -n --glob "!*test*"
rg --type go "log\.Fatal" -n --glob "!main.go" --glob "!*cmd*"
rg --type go "os\.Exit" -n --glob "!main.go" --glob "!*cmd*"
```

### Giải pháp

❌ **BAD**
```go
func Connect(url string) *DB {
    db, err := sql.Open("postgres", url)
    if err != nil { panic(err) }
    return db
}
```

✅ **GOOD**
```go
func Connect(url string) (*DB, error) {
    db, err := sql.Open("postgres", url)
    if err != nil {
        return nil, fmt.Errorf("connecting to %s: %w", url, err)
    }
    return db, nil
}
```

### Phòng ngừa
- [ ] panic() chỉ cho truly unrecoverable (programmer bugs)
- [ ] log.Fatal chỉ trong main()
- [ ] Return error cho all expected failure cases

---

## Pattern 06: fmt.Errorf Thiếu %w

### Tên
fmt.Errorf Thiếu %w (Missing Error Wrapping Verb)

### Phân loại
Error Handling / Wrapping / Chain

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```
return fmt.Errorf("db error: %v", err)
                             ^^
// %v → formats error as string → chain LOST
// errors.Is(wrappedErr, originalErr) → FALSE
// errors.As(wrappedErr, &target) → FALSE

return fmt.Errorf("db error: %w", err)
                             ^^
// %w → wraps error → chain preserved
// errors.Is and errors.As work correctly
```

### Phát hiện

```bash
rg --type go 'fmt\.Errorf\(".*%v.*",.*err' -n
rg --type go 'fmt\.Errorf\(".*%s.*",.*err' -n
rg --type go 'fmt\.Errorf\(".*%w' -n  # Good (reference)
```

### Giải pháp

❌ **BAD**
```go
return fmt.Errorf("failed to connect: %v", err) // Chain broken
```

✅ **GOOD**
```go
return fmt.Errorf("failed to connect: %w", err) // Chain preserved
```

### Phòng ngừa
- [ ] ALWAYS `%w` khi wrapping errors
- [ ] `%v` chỉ khi intentionally breaking chain
- Tool: `golangci-lint` với `errorlint`

---

## Pattern 07: Defer Error Bỏ Qua

### Tên
Defer Error Bỏ Qua (Deferred Error Ignored)

### Phân loại
Error Handling / Defer / Resource

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```
func writeFile(path string, data []byte) error {
    f, err := os.Create(path)
    if err != nil { return err }
    defer f.Close()  ← Error from Close() IGNORED!
    _, err = f.Write(data)
    return err
}
// f.Close() can fail (disk full, NFS error)
// Data not flushed → file corrupted
```

### Phát hiện

```bash
rg --type go "defer\s+\w+\.Close\(\)" -n
rg --type go "defer\s+\w+\.(Close|Flush|Sync)\(\)" -n
```

### Giải pháp

❌ **BAD**
```go
defer f.Close()  // Error silently ignored
```

✅ **GOOD**
```go
func writeFile(path string, data []byte) (retErr error) {
    f, err := os.Create(path)
    if err != nil { return err }
    defer func() {
        closeErr := f.Close()
        if retErr == nil {
            retErr = closeErr
        }
    }()
    _, err = f.Write(data)
    return err
}
```

### Phòng ngừa
- [ ] Named return for capturing defer errors
- [ ] Close errors matter for writes (not reads)
- Tool: `golangci-lint` với `errcheck` — checks defer

---

## Pattern 08: Error Trong Goroutine

### Tên
Error Trong Goroutine (Error Lost in Goroutine)

### Phân loại
Error Handling / Goroutine / Concurrency

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```
go func() {
    result, err := process(item)
    if err != nil {
        log.Println(err)  ← Error logged but not propagated!
        return
    }
}()
// Parent goroutine doesn't know about error
// No retry, no error aggregation
```

### Phát hiện

```bash
rg --type go "go func\(\)" -A 10 | rg "err"
rg --type go "go\s+\w+\(" -n
```

### Giải pháp

❌ **BAD**
```go
for _, item := range items {
    go func(i Item) {
        if err := process(i); err != nil {
            log.Println(err) // Lost!
        }
    }(item)
}
```

✅ **GOOD**
```go
type result struct {
    value string
    err   error
}

results := make(chan result, len(items))
for _, item := range items {
    go func(i Item) {
        val, err := process(i)
        results <- result{value: val, err: err}
    }(item)
}

var errs []error
for range items {
    r := <-results
    if r.err != nil {
        errs = append(errs, r.err)
    }
}
if len(errs) > 0 {
    return errors.Join(errs...)
}
```

✅ **GOOD**: errgroup
```go
g, ctx := errgroup.WithContext(ctx)
for _, item := range items {
    g.Go(func() error {
        return process(ctx, item)
    })
}
if err := g.Wait(); err != nil {
    return err
}
```

### Phòng ngừa
- [ ] Channel cho error propagation từ goroutines
- [ ] `errgroup` package cho concurrent error handling
- [ ] NEVER just log errors in goroutines

---

## Pattern 09: Error Shadowing

### Tên
Error Shadowing (:= Shadow Outer err)

### Phân loại
Error Handling / Variable / Scoping

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```
func process() error {
    var err error
    if condition {
        result, err := doSomething()  ← NEW err (shadowed!)
                 ^^^
        // This err is scoped to if block
        // Outer err still nil
        _ = result
    }
    return err  ← Returns nil even if doSomething failed!
}
```

### Phát hiện

```bash
rg --type go ":=" -n  # Look for := inside if/for blocks
# go vet catches some cases
```

### Giải pháp

❌ **BAD**
```go
var err error
if x > 0 {
    val, err := compute(x) // Shadows outer err!
    use(val)
}
return err // Always nil if entered if block
```

✅ **GOOD**
```go
var err error
var val int
if x > 0 {
    val, err = compute(x) // Assigns to outer err (=, not :=)
    use(val)
}
return err
```

### Phòng ngừa
- [ ] `=` cho assigning to existing variables
- [ ] `:=` chỉ cho declaring new variables
- Tool: `go vet` — `-shadow` flag
- Tool: `golangci-lint` với `govet` shadow check

---

## Pattern 10: Log Và Return Error

### Tên
Log Và Return Error (Log Then Return Same Error)

### Phân loại
Error Handling / Logging / Duplication

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```
func process() error {
    err := doWork()
    if err != nil {
        log.Printf("error: %v", err)  ← Log here
        return err                      ← Also return
    }
}

// Caller:
if err := process(); err != nil {
    log.Printf("process failed: %v", err)  ← Log AGAIN
}

// Result: same error logged 2-3 times at different levels
// Log noise, harder to diagnose
```

### Phát hiện

```bash
rg --type go "log\.(Print|Error|Warn).*err" -A 2 | rg "return.*err"
rg --type go "(log\.\w+|fmt\.Print).*err.*\n.*return.*err" -n
```

### Giải pháp

❌ **BAD**
```go
func getUser(id string) (*User, error) {
    user, err := db.Find(id)
    if err != nil {
        log.Printf("db error: %v", err) // Log
        return nil, err                   // And return
    }
    return user, nil
}
```

✅ **GOOD**: Handle OR return, not both
```go
func getUser(id string) (*User, error) {
    user, err := db.Find(id)
    if err != nil {
        return nil, fmt.Errorf("finding user %s: %w", id, err)
        // Let caller decide to log or propagate
    }
    return user, nil
}

// Log only at the top-level handler:
func handler(w http.ResponseWriter, r *http.Request) {
    user, err := getUser(r.URL.Query().Get("id"))
    if err != nil {
        log.Printf("handler error: %v", err) // Log ONCE
        http.Error(w, "internal error", 500)
    }
}
```

### Phòng ngừa
- [ ] Return errors (with context) — don't log them
- [ ] Log errors at the top-level boundary only
- [ ] Choose: handle (log + recover) OR propagate (return)

---

## Pattern 11: Custom Error Thiếu Unwrap

### Tên
Custom Error Thiếu Unwrap (Custom Error Missing Unwrap)

### Phân loại
Error Handling / Custom / Interface

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```
type AppError struct {
    Code    int
    Message string
    Cause   error  ← Wrapped error
}

func (e *AppError) Error() string { return e.Message }
// Missing: Unwrap() method
// errors.Is(appErr, io.EOF) → FALSE even if Cause is io.EOF
// errors.As(appErr, &target) → can't reach Cause
```

### Phát hiện

```bash
rg --type go "type\s+\w+Error\s+struct" -A 10 -n
rg --type go "func.*Error\(\)\s*string" -n
rg --type go "func.*Unwrap\(\)" -n  # Good (reference)
```

### Giải pháp

❌ **BAD**
```go
type AppError struct { Code int; Message string; Cause error }
func (e *AppError) Error() string { return e.Message }
```

✅ **GOOD**
```go
type AppError struct {
    Code    int
    Message string
    Cause   error
}

func (e *AppError) Error() string { return e.Message }
func (e *AppError) Unwrap() error { return e.Cause } // Enable errors.Is/As chain

// For multiple wrapped errors (Go 1.20+):
func (e *AppError) Unwrap() []error { return []error{e.Cause} }
```

### Phòng ngừa
- [ ] Implement `Unwrap()` for custom errors wrapping other errors
- [ ] Test: `errors.Is(custom, wrapped)` returns true
- [ ] Go 1.20+: `errors.Join()` for multiple errors

---

## Pattern 12: os.Exit Thay Error

### Tên
os.Exit Thay Error (os.Exit Instead of Error Return)

### Phân loại
Error Handling / Exit / Library

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```
func LoadConfig(path string) Config {
    data, err := os.ReadFile(path)
    if err != nil {
        fmt.Fprintf(os.Stderr, "error: %v\n", err)
        os.Exit(1)  ← Kills process! Defers don't run!
    }
    // ...
}
// os.Exit: no defer cleanup, no graceful shutdown
// In library code: caller can't recover
```

### Phát hiện

```bash
rg --type go "os\.Exit\(" -n --glob "!*main.go" --glob "!*cmd*"
rg --type go "log\.Fatal\(" -n --glob "!*main.go" --glob "!*cmd*"
```

### Giải pháp

❌ **BAD**
```go
// In library/service package
func Initialize() {
    if err := setup(); err != nil {
        log.Fatal(err) // Kills process, no cleanup
    }
}
```

✅ **GOOD**
```go
func Initialize() error {
    if err := setup(); err != nil {
        return fmt.Errorf("initialization: %w", err)
    }
    return nil
}

// os.Exit / log.Fatal ONLY in main():
func main() {
    if err := app.Initialize(); err != nil {
        log.Fatal(err) // OK in main
    }
}
```

### Phòng ngừa
- [ ] os.Exit / log.Fatal ONLY in main()
- [ ] Library code: ALWAYS return error
- [ ] Defers don't run after os.Exit

---

## Pattern 13: Error Type Assertion Sai

### Tên
Error Type Assertion Sai (Wrong Error Type Assertion)

### Phân loại
Error Handling / Assertion / Type

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```
err := doWork()
if appErr, ok := err.(*AppError); ok {  ← Direct assertion
    // Only works if err is EXACTLY *AppError
    // Fails if err was wrapped: fmt.Errorf("ctx: %w", appErr)
}
```

### Phát hiện

```bash
rg --type go "\.\(\*\w+Error\)" -n
rg --type go "err\.\(\*" -n
rg --type go "errors\.As\(" -n  # Good pattern
```

### Giải pháp

❌ **BAD**
```go
if e, ok := err.(*net.OpError); ok { } // Breaks with wrapping
```

✅ **GOOD**
```go
var opErr *net.OpError
if errors.As(err, &opErr) { // Works through wrapping chain
    log.Printf("op: %s, addr: %s", opErr.Op, opErr.Addr)
}
```

### Phòng ngừa
- [ ] `errors.As()` thay direct type assertion
- [ ] `errors.Is()` thay `==` comparison

---

## Pattern 14: Multi-Error Handling Thiếu

### Tên
Multi-Error Handling Thiếu (Missing Multi-Error Aggregation)

### Phân loại
Error Handling / Aggregation / Batch

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```
func validateAll(items []Item) error {
    for _, item := range items {
        if err := validate(item); err != nil {
            return err  ← Returns FIRST error only
            // Remaining items not validated
            // User fixes one error, gets another → frustrating
        }
    }
    return nil
}
```

### Phát hiện

```bash
rg --type go "for.*range" -A 5 | rg "return.*err"
rg --type go "errors\.Join" -n  # Good (Go 1.20+)
```

### Giải pháp

❌ **BAD**
```go
func validate(items []Item) error {
    for _, i := range items {
        if err := check(i); err != nil {
            return err // First error only
        }
    }
    return nil
}
```

✅ **GOOD** (Go 1.20+)
```go
func validate(items []Item) error {
    var errs []error
    for _, i := range items {
        if err := check(i); err != nil {
            errs = append(errs, fmt.Errorf("item %s: %w", i.ID, err))
        }
    }
    return errors.Join(errs...) // nil if no errors
}
```

### Phòng ngừa
- [ ] `errors.Join()` (Go 1.20+) cho multi-error
- [ ] Collect all errors, not just first
- [ ] Return nil when no errors collected
