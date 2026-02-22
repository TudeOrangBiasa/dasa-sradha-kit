# Domain 12: Giám Sát (Monitoring & Observability)

> Java/Spring Boot patterns: Micrometer, OpenTelemetry, structured logging, health indicators, metrics.

---

## Pattern 01: Logging Không Structured

### Phân loại
Monitoring / Logging / Observability — HIGH 🟠

### Vấn đề
```java
log.info("Processing order " + orderId + " for user " + userId);
// Not structured → can't search/filter/aggregate in ELK/Grafana
// String concatenation even when log level disabled
```

### Phát hiện
```bash
rg --type java "log\\.(info|debug|error)\\(.*\\+" -n
rg --type java "System\\.out\\.print" -n --glob "!*Test*"
```

### Giải pháp
```java
// GOOD: SLF4J parameterized logging
log.info("Processing order orderId={} userId={}", orderId, userId);

// GOOD: Structured logging with Logback JSON
// logback-spring.xml:
// <encoder class="net.logstash.logback.encoder.LogstashEncoder"/>

// GOOD: MDC for request context
MDC.put("requestId", requestId);
MDC.put("userId", userId);
log.info("Processing order orderId={}", orderId);
// JSON output includes requestId and userId automatically
```

### Phòng ngừa
- [ ] SLF4J `{}` placeholders (not string concat)
- [ ] JSON log format for production (Logstash encoder)
- [ ] MDC for cross-cutting context (requestId, userId)
- Tool: Logback, Logstash Encoder, MDC

---

## Pattern 02: Metrics Cardinality Explosion

### Phân loại
Monitoring / Metrics / Prometheus — HIGH 🟠

### Vấn đề
```java
// user_id as tag → millions of unique time series!
Metrics.counter("http.requests", "userId", userId).increment();
// Prometheus OOM, slow queries, high storage cost
```

### Phát hiện
```bash
rg --type java "Metrics\\.|Counter\\.|Timer\\.|Gauge\\." -n
rg --type java "tag\\(.*[Ii]d|tag\\(.*email|tag\\(.*ip" -n
```

### Giải pháp
```java
// BAD: High-cardinality tags
Metrics.counter("requests", "userId", userId); // Millions of series

// GOOD: Low-cardinality tags only
Metrics.counter("http.server.requests",
    "method", request.getMethod(),
    "status", String.valueOf(response.getStatus()),
    "uri", "/api/users/{id}" // Template, not actual path!
).increment();

// Spring Boot auto-configures this via Micrometer
// Just use @Timed or ObservationRegistry
```

### Phòng ngừa
- [ ] Never use IDs/emails/IPs as metric tags
- [ ] URI templates, not actual paths
- [ ] < 10 unique values per tag
- Tool: Micrometer, Prometheus

---

## Pattern 03: Health Check Superficial

### Phân loại
Monitoring / Health / Kubernetes — HIGH 🟠

### Vấn đề
```java
// Default /actuator/health returns {"status":"UP"} even if:
// - Database connection pool exhausted
// - Redis unreachable
// - Disk full
// K8s thinks pod is healthy → routes traffic → errors
```

### Phát hiện
```bash
rg "health" -n --glob "application*.yml"
rg --type java "HealthIndicator|AbstractHealthIndicator" -n
```

### Giải pháp
```java
// Custom health indicator:
@Component
public class ExternalApiHealthIndicator extends AbstractHealthIndicator {
    private final RestClient restClient;
    @Override
    protected void doHealthCheck(Health.Builder builder) {
        try {
            restClient.get().uri("/health").retrieve().body(String.class);
            builder.up().withDetail("externalApi", "reachable");
        } catch (Exception e) {
            builder.down(e).withDetail("externalApi", "unreachable");
        }
    }
}
```

```yaml
management:
  endpoint:
    health:
      show-details: always
      group:
        liveness:
          include: livenessState
        readiness:
          include: readinessState,db,redis,externalApi
  health:
    livenessstate:
      enabled: true
    readinessstate:
      enabled: true
```

### Phòng ngừa
- [ ] Separate liveness (app alive) and readiness (can serve)
- [ ] Custom `HealthIndicator` for external dependencies
- [ ] K8s probes: `/actuator/health/liveness` + `/actuator/health/readiness`
- Tool: Spring Actuator Health Groups

---

## Pattern 04: OpenTelemetry Không Cấu Hình

### Phân loại
Monitoring / Tracing / Distributed — HIGH 🟠

### Vấn đề
```
// Microservices: Service A → B → C
// No distributed tracing → can't follow request flow
// Debugging latency issues requires checking logs of each service manually
```

### Phát hiện
```bash
rg "opentelemetry|micrometer-tracing" -n --glob "pom.xml" --glob "build.gradle*"
rg "tracing|otel" -n --glob "application*.yml"
```

### Giải pháp
```xml
<!-- pom.xml: Spring Boot 3.x + Micrometer Tracing -->
<dependency>
    <groupId>io.micrometer</groupId>
    <artifactId>micrometer-tracing-bridge-otel</artifactId>
</dependency>
<dependency>
    <groupId>io.opentelemetry</groupId>
    <artifactId>opentelemetry-exporter-otlp</artifactId>
</dependency>
```

```yaml
management:
  tracing:
    sampling:
      probability: 1.0  # 100% in dev, 10% in prod
  otlp:
    tracing:
      endpoint: http://otel-collector:4318/v1/traces
```

### Phòng ngừa
- [ ] Micrometer Tracing + OTLP exporter
- [ ] Trace context auto-propagated via Spring
- [ ] Sample rate: 100% dev, 1-10% production
- Tool: Micrometer Tracing, OpenTelemetry, Jaeger/Tempo

---

## Pattern 05: Custom Metrics Thiếu

### Phân loại
Monitoring / Business / Metrics — MEDIUM 🟡

### Vấn đề
```
// Only infrastructure metrics (CPU, memory, HTTP status)
// No business metrics → can't answer:
// - How many orders processed per minute?
// - What's the payment success rate?
// - How long does report generation take?
```

### Phát hiện
```bash
rg --type java "@Timed|@Counted|MeterRegistry" -n
rg --type java "Observation|ObservationRegistry" -n
```

### Giải pháp
```java
@Service
public class OrderService {
    private final MeterRegistry meterRegistry;
    private final Counter ordersCreated;
    private final Timer orderProcessingTime;

    public OrderService(MeterRegistry registry) {
        this.meterRegistry = registry;
        this.ordersCreated = Counter.builder("orders.created")
            .tag("type", "online").register(registry);
        this.orderProcessingTime = Timer.builder("orders.processing.time")
            .register(registry);
    }

    public Order createOrder(OrderRequest req) {
        return orderProcessingTime.record(() -> {
            Order order = processOrder(req);
            ordersCreated.increment();
            return order;
        });
    }
}

// Or use @Timed annotation:
@Timed(value = "orders.create", description = "Time to create order")
public Order createOrder(OrderRequest req) { /* ... */ }
```

### Phòng ngừa
- [ ] Business metrics (orders, payments, errors by type)
- [ ] `@Timed` for method-level timing
- [ ] Dashboards for business KPIs
- Tool: Micrometer, Prometheus, Grafana

---

## Pattern 06: Log Level Sai Production

### Phân loại
Monitoring / Logging / Performance — MEDIUM 🟡

### Vấn đề
```yaml
logging:
  level:
    root: DEBUG  # DEBUG in production → massive log volume
    org.hibernate.SQL: DEBUG  # Every SQL query logged
    org.springframework: TRACE  # Framework internals
# Result: 100GB/day logs, high I/O, slow performance
```

### Phát hiện
```bash
rg "level.*DEBUG|level.*TRACE" -n --glob "application*.yml" --glob "application-prod*"
rg "show-sql.*true|show_sql.*true" -n --glob "application*.yml"
```

### Giải pháp
```yaml
# application-prod.yml:
logging:
  level:
    root: WARN
    com.myapp: INFO         # App code at INFO
    org.springframework: WARN
    org.hibernate: WARN
    org.hibernate.SQL: OFF  # No SQL logging in prod

# Dynamic level change via actuator:
# POST /actuator/loggers/com.myapp {"configuredLevel":"DEBUG"}
```

```yaml
management:
  endpoint:
    loggers:
      enabled: true  # Enable runtime log level changes
```

### Phòng ngừa
- [ ] `WARN` for frameworks, `INFO` for app code in prod
- [ ] `show-sql: false` in production
- [ ] Actuator `/loggers` for dynamic level changes
- Tool: Logback, Spring Actuator loggers endpoint

---

## Pattern 07: Error Rate Alerting Thiếu

### Phân loại
Monitoring / Alerting / SRE — HIGH 🟠

### Vấn đề
```
// Errors increasing but no one knows
// 5xx rate goes from 0.1% to 10% → users report issues
// No automated alerting → issues discovered by customers
```

### Phát hiện
```bash
rg "alert" -n --glob "*.yml" --glob "prometheus*"
rg --type java "ErrorController|@ExceptionHandler" -n
```

### Giải pháp
```java
// Spring Boot auto-exposes http.server.requests metric
// Configure Prometheus alerting rules:
```

```yaml
# prometheus-rules.yml:
groups:
  - name: spring-boot-alerts
    rules:
      - alert: HighErrorRate
        expr: >
          sum(rate(http_server_requests_seconds_count{status=~"5.."}[5m]))
          / sum(rate(http_server_requests_seconds_count[5m])) > 0.05
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Error rate > 5% for 5 minutes"

      - alert: HighLatency
        expr: >
          histogram_quantile(0.99, rate(http_server_requests_seconds_bucket[5m])) > 2
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "P99 latency > 2 seconds"
```

### Phòng ngừa
- [ ] Error rate alerting (> 5% = critical)
- [ ] Latency alerting (P99 > threshold)
- [ ] PagerDuty/Slack integration
- Tool: Prometheus Alertmanager, Grafana Alerts
