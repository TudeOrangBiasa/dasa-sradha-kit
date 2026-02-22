# Domain 12: Giám Sát Và Quan Sát (Monitoring & Observability)

> Go patterns liên quan đến monitoring: Prometheus metrics, OpenTelemetry, structured logging, health checks, pprof, tracing.

---

## Pattern 01: Prometheus Metric Cardinality Explosion

### Tên
Metric Cardinality Explosion (High-Cardinality Labels)

### Phân loại
Monitoring / Metrics / Prometheus

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề
```go
httpRequests.WithLabelValues(userID, requestPath, traceID).Inc()
// user_id: millions, path: /users/12345 (not template) → OOM
```

### Phát hiện
```bash
rg --type go "WithLabelValues|NewCounterVec|NewHistogramVec" -n
rg --type go "prometheus\." -n | rg "user_id|request_id|trace_id"
```

### Giải pháp
```go
// BAD:
httpRequests.WithLabelValues(userID, r.URL.Path).Inc()

// GOOD:
httpRequests.WithLabelValues(r.Method, statusCode, routePattern).Inc()
// routePattern: "/api/users/:id" not "/api/users/12345"

var httpRequests = promauto.NewCounterVec(prometheus.CounterOpts{
    Name: "http_requests_total",
}, []string{"method", "status", "path"})
```

### Phòng ngừa
- [ ] No IDs/emails as metric labels
- [ ] Route patterns, not actual paths
- [ ] < 10 unique values per label
- Tool: `prometheus/client_golang`, `promlint`

---

## Pattern 02: OpenTelemetry Span Leak

### Tên
OpenTelemetry Span Leak (Unclosed Spans)

### Phân loại
Monitoring / Tracing / Memory

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề
```go
ctx, span := tracer.Start(ctx, "process")
// Missing span.End()! Span never exported, memory leak
```

### Phát hiện
```bash
rg --type go "tracer\.Start\(" -n
rg --type go "span\.End\(\)" -n
rg --type go "defer.*span\.End" -n
```

### Giải pháp
```go
// ALWAYS defer span.End():
func processOrder(ctx context.Context, orderID int) error {
    ctx, span := tracer.Start(ctx, "processOrder",
        trace.WithAttributes(attribute.Int("order_id", orderID)),
    )
    defer span.End()

    if err := validate(ctx, orderID); err != nil {
        span.RecordError(err)
        span.SetStatus(codes.Error, err.Error())
        return err
    }
    return nil
}
```

### Phòng ngừa
- [ ] `defer span.End()` immediately after Start
- [ ] `span.RecordError()` for error tracking
- Tool: `go.opentelemetry.io/otel`

---

## Pattern 03: Structured Logging Thiếu

### Tên
Structured Logging Thiếu (fmt.Println in Production)

### Phân loại
Monitoring / Logging / Observability

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề
```go
fmt.Println("Processing user", userID)
log.Printf("Error: %v", err)
// Unstructured, can't filter, no levels, no JSON
```

### Phát hiện
```bash
rg --type go "fmt\.Print|log\.Print|log\.Fatal" -n --glob "!*test*"
rg --type go "slog\.|zerolog\.|zap\." -n
```

### Giải pháp
```go
// Use slog (Go 1.21+ stdlib):
logger := slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{
    Level: slog.LevelInfo,
}))

logger.Info("processing order",
    slog.Int("order_id", orderID),
    slog.String("user_id", userID),
    slog.Duration("elapsed", elapsed),
)

// Or zerolog:
log.Info().Int("order_id", orderID).Msg("processing order")
```

### Phòng ngừa
- [ ] `slog` (stdlib) or `zerolog`/`zap`
- [ ] JSON output for log aggregation
- [ ] Structured fields, not string formatting
- Tool: `slog`, `zerolog`, `zap`

---

## Pattern 04: Health Check Superficial

### Tên
Health Check Superficial (Always Returns OK)

### Phân loại
Monitoring / Health / Kubernetes

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề
```go
http.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
    w.WriteHeader(200) // Always OK — even when DB is down!
})
```

### Phát hiện
```bash
rg --type go "health|healthz|readyz|livez" -n
rg --type go "Ping\(|PingContext\(" -n
```

### Giải pháp
```go
// Separate liveness (app running) and readiness (deps ready):
func livenessHandler(w http.ResponseWriter, r *http.Request) {
    w.WriteHeader(http.StatusOK) // Simple — app is running
}

func readinessHandler(db *sql.DB, redis *redis.Client) http.HandlerFunc {
    return func(w http.ResponseWriter, r *http.Request) {
        ctx, cancel := context.WithTimeout(r.Context(), 2*time.Second)
        defer cancel()

        if err := db.PingContext(ctx); err != nil {
            http.Error(w, "db unhealthy", http.StatusServiceUnavailable)
            return
        }
        if err := redis.Ping(ctx).Err(); err != nil {
            http.Error(w, "redis unhealthy", http.StatusServiceUnavailable)
            return
        }
        w.WriteHeader(http.StatusOK)
    }
}
```

### Phòng ngừa
- [ ] Check actual dependencies in readiness
- [ ] Timeout on health checks (2s)
- [ ] Separate liveness and readiness
- Tool: K8s probes, `alexliesenfeld/health`

---

## Pattern 05: Expvar Không Expose

### Tên
Expvar Không Expose (No Runtime Metrics)

### Phân loại
Monitoring / Runtime / Debug

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề
No visibility into Go runtime: goroutine count, memory allocations, GC pauses.

### Phát hiện
```bash
rg --type go "expvar|runtime\." -n
rg --type go "debug/vars|/debug/" -n
```

### Giải pháp
```go
import _ "expvar" // Auto-registers /debug/vars

// Custom expvar:
var activeConns = expvar.NewInt("active_connections")
activeConns.Add(1)

// Or expose via Prometheus:
import "github.com/prometheus/client_golang/prometheus/collectors"
prometheus.MustRegister(collectors.NewGoCollector())
```

### Phòng ngừa
- [ ] `expvar` or Prometheus Go collector
- [ ] Monitor goroutine count, heap size, GC
- Tool: `expvar`, `prometheus/collectors`

---

## Pattern 06: Pprof Production Access

### Tên
Pprof Production Access (Profiling Not Available)

### Phân loại
Monitoring / Profiling / Debug

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề
No pprof in production → can't diagnose CPU/memory issues during incidents.

### Phát hiện
```bash
rg --type go "net/http/pprof" -n
rg --type go "pprof" -n
```

### Giải pháp
```go
import _ "net/http/pprof"

// Serve on separate port (not public!):
go func() {
    debugMux := http.NewServeMux()
    debugMux.HandleFunc("/debug/pprof/", pprof.Index)
    log.Println(http.ListenAndServe("localhost:6060", debugMux))
}()

// Usage during incident:
// go tool pprof http://pod-ip:6060/debug/pprof/heap
// go tool pprof http://pod-ip:6060/debug/pprof/profile?seconds=30
```

### Phòng ngừa
- [ ] pprof on internal-only port
- [ ] Never expose pprof to public
- Tool: `go tool pprof`, `fgprof`

---

## Pattern 07: Runtime Metrics Thiếu

### Tên
Runtime Metrics Thiếu (No GC/Goroutine Tracking)

### Phân loại
Monitoring / Runtime / Performance

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề
No runtime metrics → goroutine leak undetected, GC pressure invisible.

### Phát hiện
```bash
rg --type go "runtime\.NumGoroutine|runtime\.MemStats" -n
rg --type go "GoCollector|ProcessCollector" -n
```

### Giải pháp
```go
// Prometheus Go collector (recommended):
prometheus.MustRegister(
    collectors.NewGoCollector(),
    collectors.NewProcessCollector(collectors.ProcessCollectorOpts{}),
)

// Key metrics to watch:
// go_goroutines — goroutine count (leak detection)
// go_gc_duration_seconds — GC pause time
// go_memstats_heap_alloc_bytes — heap usage
// process_open_fds — file descriptor count
```

### Phòng ngừa
- [ ] Go collector for runtime metrics
- [ ] Alert on goroutine count growth
- [ ] Dashboard for GC pauses and heap
- Tool: Prometheus, Grafana

---

## Pattern 08: Distributed Tracing Context Sai

### Tên
Distributed Tracing Context Propagation Sai

### Phân loại
Monitoring / Tracing / Distributed

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề
```go
// Service A → Service B: context not propagated
resp, err := http.Get("http://service-b/api")
// Service B creates new trace → can't correlate
```

### Phát hiện
```bash
rg --type go "otelhttp|propagation" -n
rg --type go "http\.Get\(|http\.Post\(" -n --glob "!*test*"
```

### Giải pháp
```go
import "go.opentelemetry.io/contrib/instrumentation/net/http/otelhttp"

// Outgoing requests — auto-inject trace context:
client := &http.Client{Transport: otelhttp.NewTransport(http.DefaultTransport)}

// Incoming requests — auto-extract trace context:
handler := otelhttp.NewHandler(mux, "server")

// Manual propagation:
otel.GetTextMapPropagator().Inject(ctx, propagation.HeaderCarrier(req.Header))
```

### Phòng ngừa
- [ ] `otelhttp` transport for outgoing calls
- [ ] `otelhttp` handler for incoming requests
- [ ] W3C TraceContext propagation
- Tool: `otelhttp`, OpenTelemetry SDK

---

## Pattern 09: Error Rate Alerting Thiếu

### Tên
Error Rate Alerting Thiếu (No Alerts on Errors)

### Phân loại
Monitoring / Alerting / SRE

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề
Error rate increases but no one notices until users report.

### Phát hiện
```bash
rg --type go "error_rate|alert" -n
rg "alert" -n --glob "*.yml" --glob "prometheus*"
```

### Giải pháp
```go
var httpResponses = promauto.NewCounterVec(prometheus.CounterOpts{
    Name: "http_responses_total",
}, []string{"method", "status_class"})

// Record:
statusClass := fmt.Sprintf("%dxx", statusCode/100)
httpResponses.WithLabelValues(r.Method, statusClass).Inc()
```

```yaml
# Prometheus alert:
- alert: HighErrorRate
  expr: rate(http_responses_total{status_class="5xx"}[5m]) / rate(http_responses_total[5m]) > 0.05
  for: 5m
```

### Phòng ngừa
- [ ] Status class labels (2xx, 4xx, 5xx)
- [ ] Error rate alerting rules
- Tool: Prometheus, Alertmanager

---

## Pattern 10: SLO Definition Thiếu

### Tên
SLO Definition Thiếu (No Service Level Objectives)

### Phân loại
Monitoring / SRE / SLO

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề
No SLOs defined → no way to measure reliability → reactive firefighting instead of proactive monitoring.

### Phát hiện
```bash
rg "slo|sli|error_budget" -n --glob "*.yml"
rg --type go "histogram|latency|duration" -n
```

### Giải pháp
```go
// SLI: Request latency histogram
var requestDuration = promauto.NewHistogramVec(prometheus.HistogramOpts{
    Name:    "http_request_duration_seconds",
    Buckets: []float64{0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5},
}, []string{"method", "path"})
```

```yaml
# SLO: 99.9% of requests < 500ms
- record: slo:http_latency:ratio
  expr: histogram_quantile(0.999, rate(http_request_duration_seconds_bucket[5m]))

- alert: SLOBreach
  expr: slo:http_latency:ratio > 0.5
  labels: { severity: warning }
```

### Phòng ngừa
- [ ] Define SLIs (latency, error rate, throughput)
- [ ] Set SLOs (99.9% < 500ms)
- [ ] Error budget tracking
- Tool: Prometheus, Grafana, `sloth`
