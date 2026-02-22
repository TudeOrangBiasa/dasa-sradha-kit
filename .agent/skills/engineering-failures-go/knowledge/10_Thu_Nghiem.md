# Domain 10: Thử Nghiệm (Testing)

> Go patterns liên quan đến testing: table-driven tests, helpers, parallel, mocking, benchmarking, integration isolation.

---

## Pattern 01: Table-Driven Test Thiếu

### Tên
Table-Driven Test Thiếu (No Table-Driven Tests)

### Phân loại
Testing / Convention / Go Idiom

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```go
func TestAdd(t *testing.T) {
    if Add(1, 2) != 3 { t.Error("1+2 should be 3") }
    if Add(0, 0) != 0 { t.Error("0+0 should be 0") }
    if Add(-1, 1) != 0 { t.Error("-1+1 should be 0") }
    // Repetitive, hard to add cases, poor error messages
}
```

### Phát hiện

```bash
rg --type go "func Test\w+\(t \*testing.T\)" -A 10 | rg -v "tests|cases|tt\."
rg --type go "t\.Run\(" -n
```

### Giải pháp

❌ **BAD**
```go
func TestParse(t *testing.T) {
    r1, _ := Parse("123"); if r1 != 123 { t.Error("fail") }
    r2, _ := Parse("abc"); if r2 != 0 { t.Error("fail") }
}
```

✅ **GOOD**
```go
func TestParse(t *testing.T) {
    tests := []struct {
        name    string
        input   string
        want    int
        wantErr bool
    }{
        {"valid number", "123", 123, false},
        {"invalid string", "abc", 0, true},
        {"empty", "", 0, true},
        {"negative", "-42", -42, false},
    }
    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            got, err := Parse(tt.input)
            if (err != nil) != tt.wantErr {
                t.Errorf("Parse(%q) error = %v, wantErr %v", tt.input, err, tt.wantErr)
            }
            if got != tt.want {
                t.Errorf("Parse(%q) = %v, want %v", tt.input, got, tt.want)
            }
        })
    }
}
```

### Phòng ngừa
- [ ] Table-driven tests for all multi-case functions
- [ ] `t.Run()` for subtests with descriptive names
- [ ] Include edge cases in table
- Tool: Go testing conventions, `gotests` generator

---

## Pattern 02: t.Helper() Thiếu

### Tên
t.Helper() Thiếu (Test Helper Without t.Helper)

### Phân loại
Testing / Helpers / Error Reporting

### Mức nghiêm trọng
LOW 🟢

### Vấn đề

```go
func assertEqual(t *testing.T, got, want int) {
    // Missing t.Helper()!
    if got != want {
        t.Errorf("got %d, want %d", got, want) // Reports THIS line, not caller
    }
}
```

### Phát hiện

```bash
rg --type go "func \w+\(t \*testing\.(T|B)" -A 1 | rg -v "t\.Helper\(\)|func Test"
rg --type go "t\.Helper\(\)" -n
```

### Giải pháp

❌ **BAD**
```go
func assertNoError(t *testing.T, err error) {
    if err != nil { t.Fatalf("unexpected error: %v", err) } // Line 5
}
// Error shows helper.go:5, not the actual test line
```

✅ **GOOD**
```go
func assertNoError(t *testing.T, err error) {
    t.Helper() // Now error reports caller's line
    if err != nil { t.Fatalf("unexpected error: %v", err) }
}

func mustCreate(t *testing.T, db *sql.DB, name string) *User {
    t.Helper()
    user, err := CreateUser(db, name)
    if err != nil { t.Fatalf("mustCreate(%q): %v", name, err) }
    return user
}
```

### Phòng ngừa
- [ ] `t.Helper()` as first line of ALL test helpers
- [ ] Applies to both `*testing.T` and `*testing.B`
- [ ] Nest helpers correctly
- Tool: `go vet`, `testifylint`

---

## Pattern 03: Parallel Test Race Condition

### Tên
Parallel Test Race Condition (Data Race in Parallel Tests)

### Phân loại
Testing / Parallel / Race

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```go
func TestParallel(t *testing.T) {
    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            t.Parallel()
            got := Process(tt.input) // tt captured by reference — RACE!
            // All goroutines see last value of tt
        })
    }
}
```

### Phát hiện

```bash
rg --type go "t\.Parallel\(\)" -B 5 -n
rg --type go "range.*\{" -A 5 | rg "t\.Parallel"
```

### Giải pháp

❌ **BAD**
```go
for _, tt := range tests {
    t.Run(tt.name, func(t *testing.T) {
        t.Parallel()
        assert(Process(tt.input)) // tt is shared — race condition
    })
}
```

✅ **GOOD**
```go
// Go 1.22+: loop variable scoping fixed, but explicit is safer:
for _, tt := range tests {
    tt := tt // Shadow loop variable (pre-Go 1.22)
    t.Run(tt.name, func(t *testing.T) {
        t.Parallel()
        got := Process(tt.input) // tt is local copy — safe
        if got != tt.want {
            t.Errorf("got %v, want %v", got, tt.want)
        }
    })
}

// Go 1.22+: No need for shadow, but still good practice
```

### Phòng ngừa
- [ ] Shadow loop variable in parallel subtests (pre-Go 1.22)
- [ ] Run `go test -race` in CI
- [ ] No shared mutable state in parallel tests
- Tool: `go test -race`, `go vet`

---

## Pattern 04: Testify Assertion Overuse

### Tên
Testify Assertion Overuse (Over-reliance on Testify)

### Phân loại
Testing / Assertions / Dependency

### Mức nghiêm trọng
LOW 🟢

### Vấn đề

```go
import "github.com/stretchr/testify/assert"

func TestUser(t *testing.T) {
    assert.Equal(t, "Alice", user.Name)
    assert.Equal(t, 30, user.Age)
    assert.Nil(t, err) // Continues even after failure!
    // assert doesn't stop — subsequent assertions may panic
}
```

### Phát hiện

```bash
rg --type go "testify/assert" -n
rg --type go "assert\.\w+\(t," -n | rg -v "require"
rg --type go "testify/require" -n
```

### Giải pháp

❌ **BAD**
```go
assert.Nil(t, err)          // Continues after failure
assert.Equal(t, 1, result)  // May panic if err was not nil
```

✅ **GOOD**
```go
import "github.com/stretchr/testify/require"

func TestUser(t *testing.T) {
    user, err := GetUser(1)
    require.NoError(t, err)         // Stops test immediately if err
    require.NotNil(t, user)         // Stops if nil
    assert.Equal(t, "Alice", user.Name) // Non-fatal OK for value checks
    assert.Equal(t, 30, user.Age)
}
// require for preconditions, assert for value checks
```

### Phòng ngừa
- [ ] `require` for error/nil checks (fail-fast)
- [ ] `assert` for value comparisons (continue on fail)
- [ ] Standard library `if/t.Error` for simple cases
- Tool: `testifylint` linter

---

## Pattern 05: Mock Generation Thiếu

### Tên
Mock Generation Thiếu (No Interface Mocking)

### Phân loại
Testing / Mocking / Interface

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```go
type UserService struct {
    db *sql.DB // Concrete dependency — can't mock
}
func (s *UserService) GetUser(id int) (*User, error) {
    return s.db.QueryRow("SELECT ...") // Needs real DB in tests
}
```

### Phát hiện

```bash
rg --type go "mockgen|gomock|mock\." -n
rg --type go "type \w+ interface" -n
rg --type go "\*sql\.DB|\*gorm\.DB" -n --glob "!*test*"
```

### Giải pháp

❌ **BAD**
```go
type Service struct { db *sql.DB } // Untestable without real DB
```

✅ **GOOD**
```go
// Define interface at consumer:
type UserRepo interface {
    GetUser(ctx context.Context, id int) (*User, error)
    CreateUser(ctx context.Context, u *User) error
}

type UserService struct { repo UserRepo }

// Generate mock:
//go:generate mockgen -source=service.go -destination=mock_repo_test.go -package=service

func TestGetUser(t *testing.T) {
    ctrl := gomock.NewController(t)
    repo := NewMockUserRepo(ctrl)
    repo.EXPECT().GetUser(gomock.Any(), 1).Return(&User{Name: "Alice"}, nil)

    svc := &UserService{repo: repo}
    user, err := svc.GetUser(context.Background(), 1)
    require.NoError(t, err)
    assert.Equal(t, "Alice", user.Name)
}
```

### Phòng ngừa
- [ ] Interface at consumer, not provider
- [ ] `mockgen` or `moq` for mock generation
- [ ] `go:generate` for reproducible mocks
- Tool: `mockgen`, `moq`, `counterfeiter`

---

## Pattern 06: Integration Test Không Isolated

### Tên
Integration Test Không Isolated (Shared Test Database)

### Phân loại
Testing / Integration / Isolation

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```go
var testDB *sql.DB // Shared across all tests

func TestMain(m *testing.M) {
    testDB, _ = sql.Open("postgres", "...")
    os.Exit(m.Run())
}
// All tests share same DB — order-dependent, flaky
```

### Phát hiện

```bash
rg --type go "func TestMain" -A 10 -n
rg --type go "var testDB|var db" -n --glob "*test*"
rg --type go "testcontainers|dockertest" -n
```

### Giải pháp

❌ **BAD**: Shared database, no cleanup between tests

✅ **GOOD**
```go
// Per-test isolation with testcontainers:
func setupTestDB(t *testing.T) *sql.DB {
    t.Helper()
    ctx := context.Background()
    container, _ := postgres.Run(ctx, "postgres:16",
        postgres.WithDatabase("test"),
        testcontainers.WithWaitStrategy(wait.ForListeningPort("5432/tcp")),
    )
    t.Cleanup(func() { container.Terminate(ctx) })

    connStr, _ := container.ConnectionString(ctx)
    db, _ := sql.Open("postgres", connStr)
    runMigrations(db)
    return db
}

func TestCreateUser(t *testing.T) {
    db := setupTestDB(t) // Fresh DB per test
    // ... test with clean state
}

// Or transaction-based isolation:
func withTx(t *testing.T, db *sql.DB, fn func(*sql.Tx)) {
    t.Helper()
    tx, _ := db.Begin()
    t.Cleanup(func() { tx.Rollback() })
    fn(tx)
}
```

### Phòng ngừa
- [ ] `testcontainers-go` for ephemeral databases
- [ ] Transaction rollback per test
- [ ] `t.Cleanup()` for resource cleanup
- Tool: `testcontainers-go`, `dockertest`

---

## Pattern 07: Benchmark Không Reliable

### Tên
Benchmark Không Reliable (Unreliable Go Benchmarks)

### Phân loại
Testing / Benchmark / Performance

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```go
func BenchmarkSort(b *testing.B) {
    data := []int{3, 1, 2} // Too small, measures overhead
    for i := 0; i < b.N; i++ {
        sort.Ints(data) // Already sorted after first iteration!
    }
}
```

### Phát hiện

```bash
rg --type go "func Benchmark" -A 10 -n
rg --type go "b\.ResetTimer|b\.StopTimer|b\.ReportAllocs" -n
```

### Giải pháp

❌ **BAD**
```go
func BenchmarkProcess(b *testing.B) {
    for i := 0; i < b.N; i++ {
        Process(data) // Includes setup time in measurement
    }
}
```

✅ **GOOD**
```go
func BenchmarkSort(b *testing.B) {
    sizes := []int{100, 1000, 10000}
    for _, size := range sizes {
        b.Run(fmt.Sprintf("size=%d", size), func(b *testing.B) {
            original := generateData(size) // Setup outside loop
            b.ResetTimer()
            b.ReportAllocs()
            for i := 0; i < b.N; i++ {
                data := make([]int, len(original))
                copy(data, original) // Fresh copy each iteration
                sort.Ints(data)
            }
        })
    }
}
// Run: go test -bench=. -benchmem -count=5
```

### Phòng ngừa
- [ ] `b.ResetTimer()` after setup
- [ ] `b.ReportAllocs()` for allocation tracking
- [ ] Fresh data each iteration
- Tool: `benchstat` for statistical comparison

---

## Pattern 08: Golden File Test Outdated

### Tên
Golden File Test Outdated (Stale Golden Files)

### Phân loại
Testing / Golden File / Maintenance

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```go
func TestRender(t *testing.T) {
    got := Render(template, data)
    golden := readFile("testdata/render.golden")
    if got != golden {
        t.Errorf("mismatch") // Golden file outdated, test always fails
    }
}
// No way to update golden files automatically
```

### Phát hiện

```bash
rg --type go "golden|\.golden|testdata" -n
rg --type go "update.*flag|flag.*update" -n --glob "*test*"
```

### Giải pháp

❌ **BAD**: Manual golden file management

✅ **GOOD**
```go
var update = flag.Bool("update", false, "update golden files")

func TestRender(t *testing.T) {
    got := Render(template, data)
    golden := filepath.Join("testdata", t.Name()+".golden")

    if *update {
        os.WriteFile(golden, []byte(got), 0644)
        return
    }

    want, err := os.ReadFile(golden)
    require.NoError(t, err)
    if diff := cmp.Diff(string(want), got); diff != "" {
        t.Errorf("mismatch (-want +got):\n%s", diff)
    }
}
// Update: go test -run TestRender -update
```

### Phòng ngừa
- [ ] `-update` flag for golden file regeneration
- [ ] `go-cmp` for diff output
- [ ] Golden files in `testdata/` (ignored by go tool)
- Tool: `go-cmp`, `cupaloy` (snapshot testing)

---

## Pattern 09: Coverage Report Sai Do Build Tags

### Tên
Coverage Sai Do Build Tags (Misleading Coverage Reports)

### Phân loại
Testing / Coverage / Accuracy

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```go
//go:build integration
// +build integration

func TestDBIntegration(t *testing.T) { ... }
// go test -cover → Shows 40% coverage
// But integration tests (60% more) excluded by default!
```

### Phát hiện

```bash
rg --type go "//go:build|// \\+build" -n --glob "*test*"
rg --type go "-tags" -n --glob "Makefile"
rg --type go "coverprofile|covermode" -n
```

### Giải pháp

❌ **BAD**
```bash
go test -cover ./... # Misses build-tagged tests
```

✅ **GOOD**
```makefile
# Makefile:
test-unit:
	go test -cover -coverprofile=unit.cov ./...

test-integration:
	go test -tags=integration -cover -coverprofile=int.cov ./...

test-all:
	go test -tags=integration -cover -coverprofile=all.cov -covermode=atomic ./...

coverage-report:
	go tool cover -html=all.cov -o coverage.html
```

```go
// Use short flag instead of build tags when possible:
func TestDBIntegration(t *testing.T) {
    if testing.Short() {
        t.Skip("skipping integration test in short mode")
    }
    // ...
}
// go test -short → skips integration
// go test → runs all
```

### Phòng ngừa
- [ ] `testing.Short()` over build tags when possible
- [ ] Combined coverage report in CI
- [ ] `-covermode=atomic` for parallel tests
- Tool: `go tool cover`, `gocovmerge`

---

## Pattern 10: Test Fixture Hardcoded Path

### Tên
Test Fixture Hardcoded Path (Brittle File Paths)

### Phân loại
Testing / Fixtures / Portability

### Mức nghiêm trọng
LOW 🟢

### Vấn đề

```go
func TestParse(t *testing.T) {
    data, _ := os.ReadFile("/home/dev/project/testdata/input.json")
    // Absolute path — fails on other machines, CI
}
```

### Phát hiện

```bash
rg --type go "ReadFile|Open\(" -n --glob "*test*" | rg "\"/"
rg --type go "testdata" -n
```

### Giải pháp

❌ **BAD**
```go
os.ReadFile("/absolute/path/testdata/input.json")
os.ReadFile("../../testdata/input.json") // Relative — fragile
```

✅ **GOOD**
```go
func TestParse(t *testing.T) {
    // testdata/ is special in Go — ignored by go build
    data, err := os.ReadFile(filepath.Join("testdata", "input.json"))
    require.NoError(t, err)

    // Or embed for hermetic tests:
    //go:embed testdata/input.json
    var testInput []byte

    result, err := Parse(testInput)
    require.NoError(t, err)
}
```

### Phòng ngừa
- [ ] `testdata/` directory (Go convention)
- [ ] Relative to test file, not absolute
- [ ] `//go:embed` for hermetic tests
- Tool: Go `testdata` convention, `embed`
