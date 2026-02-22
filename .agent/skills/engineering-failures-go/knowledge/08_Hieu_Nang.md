# Domain 08: Hiệu Năng Và Mở Rộng (Performance & Scalability)

> Go patterns liên quan đến performance: GC pressure, sync.Pool, string building, allocation, profiling.

---

## Pattern 01: GC Pressure

### Tên
GC Pressure (Áp Lực Garbage Collection Do Allocation Nhiều)

### Phân loại
Performance / Memory / GC

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```
Hot loop allocates heavily → GC runs frequently → STW pauses

Handler ──alloc──alloc──alloc──GC PAUSE──alloc──alloc──GC PAUSE──
                                 10ms                    10ms
Each request creates many small objects:
→ Strings, slices, maps, structs on heap
→ GC must scan and collect all of them
→ p99 latency spikes
```

### Phát hiện

```bash
rg --type go "make\(|new\(|append\(" -n --glob "!*_test.go"
rg --type go "runtime\.GC\(\)|debug\.FreeOSMemory" -n
# Runtime: GODEBUG=gctrace=1 go run main.go
```

### Giải pháp

❌ **BAD**
```go
func handleRequest(r *Request) Response {
    data := make([]byte, 0) // Grows repeatedly
    for _, item := range r.Items {
        buf := fmt.Sprintf("%s:%d", item.Name, item.Value) // New string each time
        data = append(data, []byte(buf)...)
    }
    return Response{Data: string(data)} // Another allocation
}
```

✅ **GOOD**
```go
func handleRequest(r *Request) Response {
    // Pre-allocate with known capacity
    var buf strings.Builder
    buf.Grow(len(r.Items) * 64) // Estimate capacity

    for i, item := range r.Items {
        if i > 0 {
            buf.WriteByte(',')
        }
        buf.WriteString(item.Name)
        buf.WriteByte(':')
        buf.WriteString(strconv.Itoa(item.Value))
    }
    return Response{Data: buf.String()}
}
```

### Phòng ngừa
- [ ] Pre-allocate slices/maps with `make([]T, 0, capacity)`
- [ ] Use `strings.Builder` instead of string concatenation
- [ ] Reuse objects via `sync.Pool`
- Tool: `go tool pprof -alloc_objects`, `GODEBUG=gctrace=1`

---

## Pattern 02: sync.Pool Misuse

### Tên
sync.Pool Misuse (Sử Dụng Pool Sai Cách)

### Phân loại
Performance / Memory / Pool

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```go
var pool = sync.Pool{
    New: func() interface{} { return new(Buffer) },
}

func process() {
    buf := pool.Get().(*Buffer)
    // Use buf...
    pool.Put(buf) // ← Forgot to reset buf!
    // Next Get() returns dirty buffer with leftover data
}
// Also: Pool items can be GC'd at any time — don't store expensive resources
```

### Phát hiện

```bash
rg --type go "sync\.Pool" -n
rg --type go "\.Get\(\)" -n | rg "Pool"
rg --type go "\.Put\(" -n | rg "Pool"
rg --type go "Reset\(\)" -n
```

### Giải pháp

❌ **BAD**
```go
var bufPool = sync.Pool{New: func() interface{} { return new(bytes.Buffer) }}

func handler(w http.ResponseWriter, r *http.Request) {
    buf := bufPool.Get().(*bytes.Buffer)
    buf.WriteString("response data") // Old data still in buffer!
    w.Write(buf.Bytes())
    bufPool.Put(buf) // Dirty buffer returned to pool
}
```

✅ **GOOD**
```go
var bufPool = sync.Pool{
    New: func() interface{} { return new(bytes.Buffer) },
}

func handler(w http.ResponseWriter, r *http.Request) {
    buf := bufPool.Get().(*bytes.Buffer)
    buf.Reset() // ← ALWAYS reset before use
    defer bufPool.Put(buf)

    buf.WriteString("response data")
    w.Write(buf.Bytes())
}

// For typed pool (Go 1.18+):
type Pool[T any] struct {
    pool sync.Pool
}

func NewPool[T any](newFn func() T) *Pool[T] {
    return &Pool[T]{pool: sync.Pool{New: func() interface{} { return newFn() }}}
}
```

### Phòng ngừa
- [ ] ALWAYS `Reset()` pooled objects before use
- [ ] Don't store DB connections or file handles in Pool
- [ ] Pool items may be GC'd — don't rely on them persisting
- Tool: `go vet` for Pool misuse

---

## Pattern 03: String Concatenation Trong Loop

### Tên
String Concatenation Trong Loop (Nối Chuỗi Bằng + Trong Vòng Lặp)

### Phân loại
Performance / String / Allocation

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```go
func buildCSV(rows [][]string) string {
    result := ""
    for _, row := range rows {
        result += strings.Join(row, ",") + "\n"
        // ← Each += allocates a NEW string
        // 10,000 rows: O(n²) allocations
    }
    return result
}
```

### Phát hiện

```bash
rg --type go "\+= .*\"|\+ \"" -n | rg "for|range"
rg --type go "strings\.Builder|bytes\.Buffer" -n
rg --type go "fmt\.Sprintf" -n
```

### Giải pháp

❌ **BAD**
```go
s := ""
for _, item := range items {
    s += item.Name + "," // O(n²) — copies entire string each time
}
```

✅ **GOOD**
```go
// strings.Builder — most efficient:
var b strings.Builder
b.Grow(len(items) * 32) // Pre-allocate estimate
for i, item := range items {
    if i > 0 {
        b.WriteByte(',')
    }
    b.WriteString(item.Name)
}
result := b.String()

// Or bytes.Buffer for byte-level operations:
var buf bytes.Buffer
for _, item := range items {
    buf.WriteString(item.Name)
    buf.WriteByte('\n')
}
```

### Phòng ngừa
- [ ] NEVER `+=` strings in loops
- [ ] `strings.Builder` for string building
- [ ] `Grow()` to pre-allocate capacity
- Tool: `go vet`, benchmarks with `testing.B`

---

## Pattern 04: Slice Pre-allocation Thiếu

### Tên
Slice Pre-allocation Thiếu (Slice Grow Without Capacity)

### Phân loại
Performance / Slice / Allocation

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```go
func transform(users []User) []UserDTO {
    var result []UserDTO // len=0, cap=0
    for _, u := range users {
        result = append(result, toDTO(u))
        // append doubles capacity when full:
        // cap: 0→1→2→4→8→16→32→64→128→256→512→1024
        // 10 allocations + copies for 1000 items
    }
    return result
}
```

### Phát hiện

```bash
rg --type go "var\s+\w+\s+\[\]" -n | rg -v "make"
rg --type go "append\(" -n
rg --type go "make\(\[\].*,\s*0\s*\)" -n  # make with cap=0
```

### Giải pháp

❌ **BAD**
```go
var ids []int64
for _, user := range users {
    ids = append(ids, user.ID) // Multiple reallocations
}
```

✅ **GOOD**
```go
// Pre-allocate with known length:
ids := make([]int64, 0, len(users))
for _, user := range users {
    ids = append(ids, user.ID) // No reallocation
}

// Or direct assignment when length known:
ids := make([]int64, len(users))
for i, user := range users {
    ids[i] = user.ID
}
```

### Phòng ngừa
- [ ] `make([]T, 0, n)` when approximate size known
- [ ] Direct index assignment when exact size known
- Tool: `prealloc` linter

---

## Pattern 05: Map Pre-allocation Thiếu

### Tên
Map Pre-allocation Thiếu (Map Grows Without Hint)

### Phân loại
Performance / Map / Allocation

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```go
m := make(map[string]int) // Default small bucket count
for _, item := range largeSlice {
    m[item.Key] = item.Value // Map rehashes and grows multiple times
}
```

### Phát hiện

```bash
rg --type go "make\(map\[" -n | rg -v ",\s*\d"
rg --type go "map\[.*\]\w+\{" -n
```

### Giải pháp

❌ **BAD**
```go
userMap := make(map[int64]*User)
for _, u := range users {
    userMap[u.ID] = &u // Map rehashes as it grows
}
```

✅ **GOOD**
```go
userMap := make(map[int64]*User, len(users)) // Pre-allocate
for _, u := range users {
    u := u // Capture loop variable (Go <1.22)
    userMap[u.ID] = &u
}
```

### Phòng ngừa
- [ ] `make(map[K]V, expectedSize)` when size known
- [ ] Especially important for large maps (>100 entries)
- Tool: `prealloc` linter

---

## Pattern 06: Reflect Lạm Dụng

### Tên
Reflect Lạm Dụng (Overuse Of Reflection In Hot Path)

### Phân loại
Performance / Reflect / Overhead

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```go
func mapFields(src, dst interface{}) {
    srcVal := reflect.ValueOf(src).Elem()
    dstVal := reflect.ValueOf(dst).Elem()
    for i := 0; i < srcVal.NumField(); i++ {
        name := srcVal.Type().Field(i).Name
        dstField := dstVal.FieldByName(name)
        if dstField.IsValid() {
            dstField.Set(srcVal.Field(i)) // reflect.Set is 100x slower
        }
    }
}
// Called per request × per field = massive overhead
```

### Phát hiện

```bash
rg --type go "reflect\.(ValueOf|TypeOf|Indirect)" -n
rg --type go "\.FieldByName\(|\.MethodByName\(" -n
rg --type go "reflect\.DeepEqual" -n
```

### Giải pháp

❌ **BAD**
```go
// Per-request reflection:
func serialize(v interface{}) []byte {
    val := reflect.ValueOf(v)
    // Reflect on every call
}
```

✅ **GOOD**
```go
// Option 1: Code generation
//go:generate go run gen.go  // Generate typed mappers at compile time

// Option 2: Cache reflection metadata
var fieldCache sync.Map

func getCachedFields(t reflect.Type) []reflect.StructField {
    if v, ok := fieldCache.Load(t); ok {
        return v.([]reflect.StructField)
    }
    fields := make([]reflect.StructField, t.NumField())
    for i := 0; i < t.NumField(); i++ {
        fields[i] = t.Field(i)
    }
    fieldCache.Store(t, fields)
    return fields
}

// Option 3: Generics (Go 1.18+)
func Map[S, D any](src S, mapFn func(S) D) D {
    return mapFn(src)
}
```

### Phòng ngừa
- [ ] Avoid reflect in hot paths
- [ ] Cache reflection metadata if unavoidable
- [ ] Use code generation for typed serialization
- Tool: `go-swagger`, `easyjson` for codegen

---

## Pattern 07: JSON Encoder Reuse Thiếu

### Tên
JSON Encoder Reuse Thiếu (Creating New Encoder Per Request)

### Phân loại
Performance / JSON / Allocation

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```go
func handler(w http.ResponseWriter, r *http.Request) {
    data := getData()
    bytes, _ := json.Marshal(data) // Allocates encoder + buffer each time
    w.Write(bytes)
}
```

### Phát hiện

```bash
rg --type go "json\.Marshal\(" -n
rg --type go "json\.NewEncoder\(" -n
rg --type go "json\.NewDecoder\(" -n
rg --type go "easyjson|jsoniter|sonic" -n
```

### Giải pháp

❌ **BAD**
```go
func handler(w http.ResponseWriter, r *http.Request) {
    body, _ := json.Marshal(response) // Allocates internal buffer
    w.Header().Set("Content-Type", "application/json")
    w.Write(body)
}
```

✅ **GOOD**
```go
// Option 1: Encode directly to writer (fewer allocations)
func handler(w http.ResponseWriter, r *http.Request) {
    w.Header().Set("Content-Type", "application/json")
    json.NewEncoder(w).Encode(response) // Streams to writer
}

// Option 2: Fast JSON libraries
import jsoniter "github.com/json-iterator/go"
var json = jsoniter.ConfigCompatibleWithStandardLibrary

// Option 3: Pool buffers for Marshal
var bufPool = sync.Pool{
    New: func() interface{} { return new(bytes.Buffer) },
}

func marshalPooled(v interface{}) ([]byte, error) {
    buf := bufPool.Get().(*bytes.Buffer)
    buf.Reset()
    defer bufPool.Put(buf)
    enc := json.NewEncoder(buf)
    if err := enc.Encode(v); err != nil {
        return nil, err
    }
    return bytes.Clone(buf.Bytes()), nil
}
```

### Phòng ngừa
- [ ] `json.NewEncoder(w).Encode()` for HTTP responses
- [ ] Consider `jsoniter` or `sonic` for high-throughput
- [ ] Pool buffers for heavy serialization
- Tool: Benchmark with `testing.B`

---

## Pattern 08: Escape Analysis Thất Bại

### Tên
Escape Analysis Thất Bại (Heap Allocation Khi Stack Đủ)

### Phân loại
Performance / Compiler / Allocation

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```go
func getUser() *User {
    u := User{Name: "test"} // Allocated on stack?
    return &u               // ← Escapes! Must be on heap
}
// Go compiler decides stack vs heap via escape analysis
// Returning pointers, storing in interfaces → forces heap allocation
```

### Phát hiện

```bash
# Build with escape analysis output:
# go build -gcflags="-m" ./...
rg --type go "return &" -n
rg --type go "interface\{\}" -n
```

### Giải pháp

❌ **BAD**
```go
func newConfig() *Config {
    c := Config{} // Escapes to heap due to &
    c.Load()
    return &c
}

func process(v interface{}) { // interface{} prevents escape analysis
    // v is always on heap
}
```

✅ **GOOD**
```go
// Return by value when struct is small:
func newConfig() Config {
    c := Config{}
    c.Load()
    return c // Copied — may stay on stack at call site
}

// Use concrete types instead of interface{} in hot paths:
func process(v Config) { // Compiler can keep on stack
    // ...
}

// Check escape analysis:
// go build -gcflags="-m -m" 2>&1 | grep "escapes to heap"
```

### Phòng ngừa
- [ ] Return values instead of pointers for small structs
- [ ] Avoid `interface{}` in hot paths
- [ ] `go build -gcflags="-m"` to check escape analysis
- Tool: `go build -gcflags="-m"`, pprof alloc

---

## Pattern 09: Regexp Compile Trong Loop

### Tên
Regexp Compile Trong Loop (Compiling Regex Every Iteration)

### Phân loại
Performance / Regex / Compilation

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```go
func validate(items []string) []bool {
    results := make([]bool, len(items))
    for i, item := range items {
        re := regexp.MustCompile(`^[a-zA-Z0-9]+$`) // Compiled EVERY iteration!
        results[i] = re.MatchString(item)
    }
    return results
}
```

### Phát hiện

```bash
rg --type go "regexp\.(MustCompile|Compile)\(" -n
rg --type go "regexp\.(MustCompile|Compile)" -B 3 -n | rg "for|func "
```

### Giải pháp

❌ **BAD**
```go
func handler(w http.ResponseWriter, r *http.Request) {
    re := regexp.MustCompile(`\d{4}-\d{2}-\d{2}`) // Per request!
    if re.MatchString(r.URL.Query().Get("date")) { /* ... */ }
}
```

✅ **GOOD**
```go
// Package-level compiled regex (compiled once):
var dateRegex = regexp.MustCompile(`\d{4}-\d{2}-\d{2}`)

func handler(w http.ResponseWriter, r *http.Request) {
    if dateRegex.MatchString(r.URL.Query().Get("date")) { /* ... */ }
}

// For simple patterns, avoid regex entirely:
func isAlphanumeric(s string) bool {
    for _, r := range s {
        if !unicode.IsLetter(r) && !unicode.IsDigit(r) {
            return false
        }
    }
    return true
}
```

### Phòng ngừa
- [ ] Compile regex at package level (global var)
- [ ] `MustCompile` for known-valid patterns
- [ ] Simple string checks instead of regex when possible
- Tool: `go vet`, `staticcheck`

---

## Pattern 10: Pprof Profiling Sai Metric

### Tên
Pprof Profiling Sai Metric (Profiling Wrong Metric)

### Phân loại
Performance / Profiling / Methodology

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```
Problem: "API is slow"
Developer runs: go tool pprof cpu.prof
→ CPU profile shows nothing abnormal
→ Real issue: I/O wait, mutex contention, GC pause

Profiling wrong metric = waste of time
CPU profile ≠ latency profile ≠ memory profile
```

### Phát hiện

```bash
rg --type go "pprof" -n
rg --type go "runtime/pprof|net/http/pprof" -n
rg --type go "trace\.Start|runtime/trace" -n
```

### Giải pháp

❌ **BAD**
```go
// Only CPU profiling when issue is memory:
import _ "net/http/pprof"  // Only registered, never analyzed properly
```

✅ **GOOD**
```go
import _ "net/http/pprof"

// 1. CPU profile: "where is CPU time spent?"
// go tool pprof http://localhost:6060/debug/pprof/profile?seconds=30

// 2. Heap profile: "what's allocating memory?"
// go tool pprof http://localhost:6060/debug/pprof/heap

// 3. Goroutine profile: "what's blocking/waiting?"
// go tool pprof http://localhost:6060/debug/pprof/goroutine

// 4. Mutex profile: "where is lock contention?"
runtime.SetMutexProfileFraction(5)
// go tool pprof http://localhost:6060/debug/pprof/mutex

// 5. Block profile: "where are goroutines blocked?"
runtime.SetBlockProfileRate(1)
// go tool pprof http://localhost:6060/debug/pprof/block

// 6. Execution trace: "what happened over time?"
// curl -o trace.out http://localhost:6060/debug/pprof/trace?seconds=5
// go tool trace trace.out
```

### Phòng ngừa
- [ ] Match profiling type to symptom
- [ ] CPU → CPU profile, Memory → heap, Latency → trace/block
- [ ] `runtime.SetMutexProfileFraction` for contention
- Tool: `go tool pprof`, `go tool trace`, Grafana/Pyroscope

---

## Pattern 11: Binary.Read Performance

### Tên
Binary.Read Performance (Slow Binary Parsing)

### Phân loại
Performance / Encoding / Binary

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```go
// binary.Read uses reflection internally:
var header Header
err := binary.Read(reader, binary.BigEndian, &header)
// Reflection overhead on every call
// Fine for occasional use, slow in hot path
```

### Phát hiện

```bash
rg --type go "binary\.(Read|Write)\(" -n
rg --type go "encoding/binary" -n
```

### Giải pháp

❌ **BAD**
```go
// In hot loop:
for i := 0; i < 1_000_000; i++ {
    var record Record
    binary.Read(buf, binary.BigEndian, &record) // Reflect per iteration
}
```

✅ **GOOD**
```go
// Manual parsing (no reflection):
func parseRecord(data []byte) Record {
    return Record{
        ID:     binary.BigEndian.Uint32(data[0:4]),
        Length: binary.BigEndian.Uint16(data[4:6]),
        Flags:  data[6],
    }
}

// Or unsafe cast for exact-layout structs (careful with alignment):
// Only when struct layout exactly matches wire format
```

### Phòng ngừa
- [ ] Manual parsing for hot-path binary data
- [ ] `binary.BigEndian.Uint32()` etc. for field-by-field
- [ ] `binary.Read` OK for cold paths
- Tool: Benchmarks with `testing.B`

---

## Pattern 12: False Sharing Cache Line

### Tên
False Sharing Cache Line (Atomic Counters Share Cache Line)

### Phân loại
Performance / Cache / Multi-thread

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```go
type Counters struct {
    reads  atomic.Int64 // byte 0-7
    writes atomic.Int64 // byte 8-15 ← SAME cache line!
}
// Thread A increments reads, Thread B increments writes
// Both on same 64-byte cache line → cache thrashing
```

### Phát hiện

```bash
rg --type go "atomic\.(Int|Uint|Value)" -n
rg --type go "struct.*\{" -A 5 | rg "atomic"
rg --type go "CacheLine|_pad|padding" -n
```

### Giải pháp

❌ **BAD**
```go
type Stats struct {
    Requests atomic.Int64  // Same cache line
    Errors   atomic.Int64  // Same cache line — false sharing!
}
```

✅ **GOOD**
```go
type Stats struct {
    Requests atomic.Int64
    _pad1    [56]byte       // Pad to 64-byte cache line boundary
    Errors   atomic.Int64
    _pad2    [56]byte
}

// Or use per-CPU counters for extreme throughput:
type ShardedCounter struct {
    shards [runtime.GOMAXPROCS(0)]struct {
        value atomic.Int64
        _pad  [56]byte
    }
}

func (c *ShardedCounter) Inc() {
    shard := runtime_procPin() // Pin to current P
    c.shards[shard].value.Add(1)
    runtime_procUnpin()
}
```

### Phòng ngừa
- [ ] Pad atomic fields to 64-byte boundaries
- [ ] Sharded counters for extreme write throughput
- [ ] Profile with `perf stat -e cache-misses`
- Tool: `perf`, Go benchmark with `-count=10`
