# Domain 12: Giám Sát Và Quan Sát (Monitoring & Observability)

> Rust patterns liên quan đến monitoring: tracing, metrics, logging, panic hooks, health checks, distributed tracing.

---

## Pattern 01: Tracing Span Leak

### Tên
Tracing Span Leak (Unclosed Spans)

### Phân loại
Monitoring / Tracing / Memory

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề
```rust
fn process(data: &[u8]) {
    let span = tracing::info_span!("process");
    let _enter = span.enter();
    // If function returns early or panics, span stays open
    if data.is_empty() { return; } // Span leaked!
}
```

### Phát hiện
```bash
rg --type rust "span\.enter\(\)" -n
rg --type rust "#\[instrument\]" -n
rg --type rust "info_span!|debug_span!|error_span!" -n
```

### Giải pháp
```rust
// Use #[instrument] attribute (auto-closes):
#[tracing::instrument(skip(data), fields(size = data.len()))]
fn process(data: &[u8]) -> Result<(), Error> {
    if data.is_empty() { return Ok(()); } // Span auto-closed
    Ok(())
}

// Or use span.in_scope():
fn process(data: &[u8]) {
    let span = info_span!("process", size = data.len());
    span.in_scope(|| { /* work */ }); // Auto-closes
}
```

### Phòng ngừa
- [ ] `#[instrument]` over manual span management
- [ ] `span.in_scope()` for closures
- Tool: `tracing`, `tracing-subscriber`

---

## Pattern 02: Metrics Cardinality Explosion

### Tên
Metrics Cardinality Explosion (Too Many Label Values)

### Phân loại
Monitoring / Metrics / Prometheus

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề
```rust
// user_id as label → millions of unique time series!
counter!("http_requests", "user_id" => user_id.to_string());
// Prometheus OOM, slow queries, high storage cost
```

### Phát hiện
```bash
rg --type rust "counter!|gauge!|histogram!" -n
rg --type rust "metrics::" -n | rg "user_id|request_id|trace_id"
```

### Giải pháp
```rust
// BAD: High-cardinality labels
counter!("requests", "user_id" => user.id); // Millions of series

// GOOD: Low-cardinality labels only
counter!("http_requests_total", "method" => method, "status" => status_code, "path" => path_template);
// path_template: "/api/users/{id}" not "/api/users/12345"

histogram!("http_request_duration_seconds", "method" => method, "path" => path_template)
    .record(duration.as_secs_f64());
```

### Phòng ngừa
- [ ] Never use IDs/emails/IPs as metric labels
- [ ] Use path templates, not actual paths
- [ ] < 10 unique values per label
- Tool: `metrics`, `prometheus`

---

## Pattern 03: Structured Logging Thiếu

### Tên
Structured Logging Thiếu (Unstructured println!)

### Phân loại
Monitoring / Logging / Observability

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề
```rust
println!("Processing user {}", user_id); // Not structured, no levels
eprintln!("Error: {}", err);              // Can't filter, search, aggregate
```

### Phát hiện
```bash
rg --type rust "println!|eprintln!|dbg!" -n --glob "!*test*"
rg --type rust "tracing::|log::" -n
```

### Giải pháp
```rust
use tracing::{info, warn, error, instrument};

#[instrument]
fn process_order(order_id: u64, user_id: u64) {
    info!(order_id, user_id, "Processing order");
    match execute(order_id) {
        Ok(result) => info!(order_id, total = result.total, "Order completed"),
        Err(e) => error!(order_id, error = %e, "Order failed"),
    }
}

// Setup subscriber:
tracing_subscriber::fmt()
    .json()  // JSON output for log aggregation
    .with_env_filter("myapp=info,tower_http=debug")
    .init();
```

### Phòng ngừa
- [ ] `tracing` crate (not println!)
- [ ] JSON format for production
- [ ] Structured fields (not string interpolation)
- Tool: `tracing`, `tracing-subscriber`

---

## Pattern 04: Panic Hook Không Set

### Tên
Panic Hook Không Set (Silent Panics)

### Phân loại
Monitoring / Panic / Alerting

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề
Default panic handler prints to stderr and aborts. In containerized environments, this output may be lost.

### Phát hiện
```bash
rg --type rust "panic::set_hook|panic_hook" -n
rg --type rust "color_eyre|human_panic" -n --glob "Cargo.toml"
```

### Giải pháp
```rust
fn main() {
    // Custom panic hook:
    std::panic::set_hook(Box::new(|info| {
        let payload = info.payload().downcast_ref::<&str>().unwrap_or(&"unknown");
        let location = info.location().map(|l| format!("{}:{}", l.file(), l.line()));
        tracing::error!(panic = payload, location = ?location, "PANIC occurred");
        // Send to error tracking (Sentry, etc.):
        // sentry::capture_event(...)
    }));
}
```

### Phòng ngừa
- [ ] Custom panic hook with structured logging
- [ ] Error tracking integration (Sentry)
- [ ] `color-eyre` for development, custom hook for production
- Tool: `color-eyre`, `sentry-rust`

---

## Pattern 05: Backtrace Disabled

### Tên
Backtrace Disabled (No Stack Traces)

### Phân loại
Monitoring / Debugging / Backtrace

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề
`RUST_BACKTRACE` not set → panics show no stack trace → impossible to debug.

### Phát hiện
```bash
rg "RUST_BACKTRACE" -n --glob "Dockerfile" --glob "*.yml"
rg "RUST_LIB_BACKTRACE" -n
```

### Giải pháp
```dockerfile
ENV RUST_BACKTRACE=1
# Or RUST_BACKTRACE=full for complete traces
```

```rust
// Or capture programmatically:
use std::backtrace::Backtrace;
let bt = Backtrace::capture();
error!("Error with backtrace: {}", bt);
```

### Phòng ngừa
- [ ] `RUST_BACKTRACE=1` in production containers
- [ ] Debug symbols in separate file for production
- Tool: `RUST_BACKTRACE`, `std::backtrace`

---

## Pattern 06: Health Check Endpoint Thiếu

### Tên
Health Check Endpoint Thiếu (No Health Probe)

### Phân loại
Monitoring / Health / Kubernetes

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề
No health endpoint → K8s can't check liveness/readiness → traffic to unhealthy pods.

### Phát hiện
```bash
rg --type rust "health|healthz|readyz|livez" -n
rg --type rust "actuator|status" -n
```

### Giải pháp
```rust
// Axum example:
async fn health_live() -> StatusCode { StatusCode::OK }

async fn health_ready(State(pool): State<PgPool>) -> StatusCode {
    match sqlx::query("SELECT 1").execute(&pool).await {
        Ok(_) => StatusCode::OK,
        Err(_) => StatusCode::SERVICE_UNAVAILABLE,
    }
}

let app = Router::new()
    .route("/healthz/live", get(health_live))
    .route("/healthz/ready", get(health_ready));
```

### Phòng ngừa
- [ ] Separate liveness and readiness endpoints
- [ ] Check dependencies in readiness probe
- Tool: `axum`, `actix-web`

---

## Pattern 07: Resource Monitoring Thiếu

### Tên
Resource Monitoring Thiếu (No FD/Memory Tracking)

### Phân loại
Monitoring / Resources / System

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề
No visibility into file descriptors, memory usage, thread count → silent resource exhaustion.

### Phát hiện
```bash
rg --type rust "process_collector|sys_info|sysinfo" -n
rg --type rust "fd_count|memory_usage" -n
```

### Giải pháp
```rust
use prometheus::{process_collector::ProcessCollector, Registry};

let registry = Registry::new();
let process_collector = ProcessCollector::for_self();
registry.register(Box::new(process_collector)).unwrap();

// Custom metrics:
gauge!("app_connections_active").set(pool.active_count() as f64);
gauge!("app_memory_bytes").set(get_rss_bytes() as f64);
```

### Phòng ngừa
- [ ] Process collector for CPU/memory/FD metrics
- [ ] Connection pool metrics
- Tool: `prometheus`, `sysinfo`

---

## Pattern 08: Slow Log Thiếu

### Tên
Slow Log Thiếu (No Slow Request Tracking)

### Phân loại
Monitoring / Performance / Latency

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề
No visibility into slow requests → latency issues go unnoticed until users complain.

### Phát hiện
```bash
rg --type rust "tower_http|TraceLayer|MakeSpan" -n
rg --type rust "elapsed|duration|latency" -n
```

### Giải pháp
```rust
use tower_http::trace::TraceLayer;

let app = Router::new()
    .route("/api/users", get(list_users))
    .layer(
        TraceLayer::new_for_http()
            .on_response(|response: &Response, latency: Duration, _span: &Span| {
                if latency > Duration::from_secs(1) {
                    warn!(latency_ms = latency.as_millis(), "Slow request");
                }
            }),
    );
```

### Phòng ngừa
- [ ] Request duration logging via middleware
- [ ] Alert on P99 latency thresholds
- Tool: `tower-http`, `tracing`

---

## Pattern 09: Distributed Tracing Context Lost

### Tên
Distributed Tracing Context Lost (No Context Propagation)

### Phân loại
Monitoring / Tracing / Distributed

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề
Service A calls Service B — trace context not propagated → separate traces, can't follow request flow.

### Phát hiện
```bash
rg --type rust "opentelemetry|propagat|traceparent" -n
rg --type rust "HeaderMap|header" -n | rg "trace"
```

### Giải pháp
```rust
use opentelemetry::global;
use opentelemetry_sdk::trace::TracerProvider;
use tracing_opentelemetry::OpenTelemetryLayer;

// Setup:
let provider = TracerProvider::builder()
    .with_batch_exporter(exporter)
    .build();
global::set_tracer_provider(provider);

let telemetry = OpenTelemetryLayer::new(global::tracer("myapp"));
tracing_subscriber::registry().with(telemetry).init();

// Propagate context in HTTP calls:
let mut headers = HeaderMap::new();
global::get_text_map_propagator(|prop| {
    prop.inject_context(&cx, &mut HeaderInjector(&mut headers));
});
```

### Phòng ngừa
- [ ] OpenTelemetry SDK for trace propagation
- [ ] W3C TraceContext headers between services
- Tool: `opentelemetry`, `tracing-opentelemetry`

---

## Pattern 10: Error Rate Alerting Thiếu

### Tên
Error Rate Alerting Thiếu (No Error Alerts)

### Phân loại
Monitoring / Alerting / SRE

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề
Errors increase but no alert → issues discovered by users, not by team.

### Phát hiện
```bash
rg --type rust "alert|threshold|error_rate" -n
rg "alert" -n --glob "*.yml" --glob "prometheus*"
```

### Giải pháp
```rust
// Track error rate:
counter!("http_responses_total", "status" => if status.is_success() { "2xx" } else { "5xx" });
```

```yaml
# Prometheus alert rule:
- alert: HighErrorRate
  expr: rate(http_responses_total{status="5xx"}[5m]) / rate(http_responses_total[5m]) > 0.05
  for: 5m
  labels: { severity: critical }
  annotations:
    summary: "Error rate > 5% for 5 minutes"
```

### Phòng ngừa
- [ ] Error rate metrics with status labels
- [ ] Prometheus alerting rules
- [ ] PagerDuty/Slack integration
- Tool: Prometheus, Alertmanager, Grafana
