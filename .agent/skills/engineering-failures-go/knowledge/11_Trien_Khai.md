# Domain 11: Triển Khai Và Build (Deployment & Build)

> Go patterns liên quan đến deployment: Docker builds, CGo, go.sum, build tags, reproducibility, binary versioning.

---

## Pattern 01: Multi-Stage Docker Build Thiếu

### Tên
Multi-Stage Docker Build Thiếu (Bloated Container)

### Phân loại
Deployment / Docker / Size

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```dockerfile
FROM golang:1.22
WORKDIR /app
COPY . .
RUN go build -o server .
CMD ["./server"]
# Image size: 1.2GB (includes Go toolchain, source code, build cache)
```

### Phát hiện

```bash
rg "FROM golang" -A 10 -n --glob "Dockerfile"
rg "FROM.*AS" -n --glob "Dockerfile"
rg "scratch|distroless|alpine" -n --glob "Dockerfile"
```

### Giải pháp

❌ **BAD**
```dockerfile
FROM golang:1.22
# Single stage — 1.2GB image with Go toolchain
```

✅ **GOOD**
```dockerfile
# Build stage:
FROM golang:1.22 AS builder
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" -o server .

# Runtime stage:
FROM gcr.io/distroless/static-debian12
COPY --from=builder /app/server /server
USER nonroot:nonroot
CMD ["/server"]
# Image size: ~10MB
```

### Phòng ngừa
- [ ] Multi-stage builds for all Go services
- [ ] `CGO_ENABLED=0` for static binary
- [ ] `distroless` or `scratch` base image
- Tool: Docker multi-stage, `ko` for Go images

---

## Pattern 02: CGo Trong Container Alpine

### Tên
CGo Trong Container Alpine (CGo Binary Fails on Alpine)

### Phân loại
Deployment / CGo / Linking

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```dockerfile
FROM golang:1.22 AS builder
RUN go build -o app .  # CGO_ENABLED=1 by default → links to glibc

FROM alpine:3.19       # Uses musl, not glibc!
COPY --from=builder /app/app /app
CMD ["/app"]
# Runtime error: not found (dynamic linker mismatch)
```

### Phát hiện

```bash
rg "CGO_ENABLED" -n --glob "Dockerfile" --glob "Makefile"
rg "FROM alpine" -n --glob "Dockerfile"
rg "import \"C\"" -n --type go
```

### Giải pháp

❌ **BAD**
```dockerfile
RUN go build -o app .  # CGO on → glibc dependency
FROM alpine            # musl → binary fails
```

✅ **GOOD**
```dockerfile
# Option 1: Disable CGo (preferred):
RUN CGO_ENABLED=0 go build -o app .
FROM scratch
COPY --from=builder /app/app /app

# Option 2: If CGo required, use Alpine in build too:
FROM golang:1.22-alpine AS builder
RUN apk add --no-cache gcc musl-dev
RUN go build -o app .
FROM alpine:3.19
COPY --from=builder /app/app /app

# Option 3: Static linking with CGo:
RUN CGO_ENABLED=1 go build -ldflags '-linkmode external -extldflags "-static"' -o app .
```

### Phòng ngừa
- [ ] `CGO_ENABLED=0` unless C libraries needed
- [ ] Match build and runtime libc (glibc or musl)
- [ ] Test binary in target container
- Tool: `ldd`, Docker multi-stage

---

## Pattern 03: go.sum Không Commit

### Tên
go.sum Không Commit (Missing Lockfile)

### Phân loại
Deployment / Dependencies / Reproducibility

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```
.gitignore:
go.sum  ← WRONG! go.sum is the lockfile

Without go.sum:
- CI downloads different versions than local
- Supply chain attack possible (modified module)
- Non-reproducible builds
```

### Phát hiện

```bash
rg "go\.sum" -n --glob ".gitignore"
rg "go mod download|go mod tidy" -n --glob "Dockerfile"
```

### Giải pháp

❌ **BAD**
```
# .gitignore:
go.sum  # Don't ignore this!
```

✅ **GOOD**
```
# .gitignore:
# Do NOT add go.sum here

# Commit both:
git add go.mod go.sum
git commit -m "chore: update dependencies"

# CI verification:
go mod verify  # Checks checksums match go.sum
```

```dockerfile
COPY go.mod go.sum ./
RUN go mod download && go mod verify
COPY . .
RUN go build -o app .
```

### Phòng ngừa
- [ ] Always commit `go.sum`
- [ ] `go mod verify` in CI
- [ ] `GOFLAGS=-mod=readonly` to prevent CI modifications
- Tool: `go mod verify`, `GONOSUMCHECK`

---

## Pattern 04: Build Tags Sai

### Tên
Build Tags Sai (Wrong Build Constraints)

### Phân loại
Deployment / Build / Conditional

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```go
// +build linux  ← Old syntax (pre-Go 1.17), still works but deprecated
//go:build linux  ← New syntax

// Wrong: space means AND, comma means OR (old syntax)
// +build linux,amd64  → linux AND amd64
// +build linux amd64  → linux OR amd64 ← SURPRISE!
```

### Phát hiện

```bash
rg --type go "//go:build|// \+build" -n
rg --type go "//go:build" -B1 -A1 -n | rg "\+build"
```

### Giải pháp

❌ **BAD**
```go
// +build linux amd64
// Means: linux OR amd64 (not AND!)
```

✅ **GOOD**
```go
//go:build linux && amd64

//go:build !windows

//go:build integration

//go:build (linux || darwin) && amd64
```

```bash
# Verify build tags:
go vet ./...
# List files matching tag:
go list -tags=integration ./...
```

### Phòng ngừa
- [ ] Use `//go:build` syntax (Go 1.17+)
- [ ] `go vet` catches mismatched build tags
- [ ] Test with `-tags` flag in CI
- Tool: `go vet`, `buildssa`

---

## Pattern 05: GOPROXY Không Set

### Tên
GOPROXY Không Set (Module Download Issues)

### Phân loại
Deployment / Dependencies / Registry

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```
CI in restricted network:
go mod download → connection to proxy.golang.org timed out

Private modules:
go mod download → 404 for github.com/company/private-module
```

### Phát hiện

```bash
rg "GOPROXY|GONOSUMDB|GOPRIVATE" -n --glob "*.yml" --glob "Makefile"
rg "GOPRIVATE" -n --glob ".env*"
```

### Giải pháp

❌ **BAD**: Default GOPROXY with private modules

✅ **GOOD**
```bash
# For private modules:
export GOPRIVATE="github.com/mycompany/*"
export GONOSUMDB="github.com/mycompany/*"

# For corporate proxy:
export GOPROXY="https://goproxy.mycompany.com,https://proxy.golang.org,direct"

# For air-gapped environments:
go mod vendor
go build -mod=vendor ./...
```

```yaml
# CI:
env:
  GOPRIVATE: "github.com/mycompany/*"
  GONOSUMDB: "github.com/mycompany/*"
steps:
  - run: git config --global url."https://${GITHUB_TOKEN}@github.com/".insteadOf "https://github.com/"
  - run: go mod download
```

### Phòng ngừa
- [ ] `GOPRIVATE` for private modules
- [ ] `go mod vendor` for reproducible builds
- [ ] Corporate proxy for restricted networks
- Tool: Athens proxy, `go mod vendor`

---

## Pattern 06: Binary Reproducibility

### Tên
Binary Reproducibility Thiếu (Non-Reproducible Builds)

### Phân loại
Deployment / Reproducibility / Security

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```bash
# Two builds of same code produce different binaries:
go build -o app1 .
go build -o app2 .
sha256sum app1 app2  # Different hashes!
# Cause: embedded build paths, timestamps
```

### Phát hiện

```bash
rg "trimpath|ldflags" -n --glob "Makefile" --glob "*.yml"
rg "go version -m" -n --glob "*.sh"
```

### Giải pháp

❌ **BAD**
```bash
go build -o app .  # Embeds build path, non-reproducible
```

✅ **GOOD**
```bash
# Reproducible build:
go build -trimpath -ldflags="-s -w -buildid=" -o app .

# Verify embedded info:
go version -m app

# With version info:
VERSION=$(git describe --tags --always)
go build -trimpath \
    -ldflags="-s -w -X main.version=${VERSION} -X main.buildTime=$(date -u +%Y%m%d)" \
    -o app .
```

### Phòng ngừa
- [ ] `-trimpath` for reproducible builds
- [ ] `-ldflags="-s -w"` to strip debug info
- [ ] Version injection via `-X` ldflags
- Tool: `go build -trimpath`, `govulncheck`

---

## Pattern 07: Ldflags Version Thiếu

### Tên
Ldflags Version Thiếu (No Build Version Info)

### Phân loại
Deployment / Versioning / Observability

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```go
func main() {
    fmt.Println("Starting server...")
    // No way to know: what version? when built? what commit?
}
// In production: "which version is running?" → unknown
```

### Phát hiện

```bash
rg --type go "var version|var Version|var commit" -n
rg "ldflags.*-X" -n --glob "Makefile" --glob "*.yml"
```

### Giải pháp

❌ **BAD**: No version information embedded

✅ **GOOD**
```go
// main.go:
var (
    version   = "dev"
    commit    = "unknown"
    buildTime = "unknown"
)

func main() {
    if os.Args[1] == "--version" {
        fmt.Printf("version=%s commit=%s built=%s\n", version, commit, buildTime)
        return
    }
}
```

```makefile
VERSION ?= $(shell git describe --tags --always --dirty)
COMMIT  ?= $(shell git rev-parse --short HEAD)
BUILD   ?= $(shell date -u '+%Y-%m-%d_%H:%M:%S')

build:
	go build -ldflags "\
		-X main.version=$(VERSION) \
		-X main.commit=$(COMMIT) \
		-X main.buildTime=$(BUILD)" \
		-o bin/app .
```

### Phòng ngừa
- [ ] Version, commit, build time in all binaries
- [ ] `--version` flag for runtime inspection
- [ ] Expose in health check endpoint
- Tool: `ldflags -X`, `debug/buildinfo`

---

## Pattern 08: Scratch Container Thiếu CA Certs

### Tên
Scratch Container Thiếu CA Certs (TLS Fails in Minimal Container)

### Phân loại
Deployment / Docker / TLS

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```dockerfile
FROM scratch
COPY --from=builder /app/server /server
CMD ["/server"]
# Runtime: x509: certificate signed by unknown authority
# No CA certificates in scratch image!
```

### Phát hiện

```bash
rg "FROM scratch" -A 5 -n --glob "Dockerfile"
rg "ca-certificates|certs" -n --glob "Dockerfile"
```

### Giải pháp

❌ **BAD**
```dockerfile
FROM scratch
COPY --from=builder /app /app  # No CA certs, no timezone data
```

✅ **GOOD**
```dockerfile
FROM golang:1.22 AS builder
RUN CGO_ENABLED=0 go build -o /app .

FROM scratch
# Copy CA certificates:
COPY --from=builder /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/
# Copy timezone data:
COPY --from=builder /usr/share/zoneinfo /usr/share/zoneinfo
# Copy binary:
COPY --from=builder /app /app
USER 65534:65534
CMD ["/app"]

# Or use distroless (includes certs):
FROM gcr.io/distroless/static-debian12
COPY --from=builder /app /app
CMD ["/app"]
```

### Phòng ngừa
- [ ] CA certificates in scratch containers
- [ ] `distroless/static` as simpler alternative
- [ ] Test HTTPS calls in container
- Tool: `distroless`, Docker multi-stage
