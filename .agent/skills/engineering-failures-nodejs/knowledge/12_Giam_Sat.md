# Domain 12: Giám Sát Và Quan Sát (Monitoring & Observability)

> Node.js patterns liên quan đến monitoring: console.log, structured logging, APM, event loop, heap, error tracking, tracing.

---

## Pattern 01: Console.log Trong Production

### Tên
Console.log Trong Production (No Structured Logging)

### Phân loại
Monitoring / Logging / Production

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề
```typescript
console.log("Processing user", userId); // Unstructured, no levels, no JSON
console.error("Error:", err.message);   // Lost in noise, can't filter
```

### Phát hiện
```bash
rg --type ts --type js "console\.(log|error|warn|info)\(" -n --glob "!*test*" --glob "!node_modules/*"
```

### Giải pháp
```typescript
import pino from 'pino';
const logger = pino({ level: process.env.LOG_LEVEL || 'info' });

logger.info({ userId, orderId }, 'Processing order');
logger.error({ err, userId }, 'Order processing failed');

// Child loggers for context:
const reqLogger = logger.child({ requestId, traceId });
reqLogger.info('Handling request');
```

### Phòng ngừa
- [ ] `pino` or `winston` instead of console.log
- [ ] JSON output for log aggregation
- [ ] ESLint `no-console` rule
- Tool: `pino`, `winston`, ESLint

---

## Pattern 02: Structured Logging Thiếu

### Tên
Structured Logging Thiếu (String Interpolation Logs)

### Phân loại
Monitoring / Logging / Format

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề
```typescript
logger.info(`User ${userId} created order ${orderId}`);
// Can't search by userId or orderId in log aggregation
```

### Phát hiện
```bash
rg --type ts --type js "logger\.\w+\(\`" -n --glob "!*test*"
rg --type ts --type js "logger\.\w+\(\"" -n --glob "!*test*"
```

### Giải pháp
```typescript
// BAD: String interpolation
logger.info(`User ${userId} created order ${orderId} total ${total}`);

// GOOD: Structured fields
logger.info({ userId, orderId, total }, 'Order created');
// → {"userId":123,"orderId":456,"total":99.99,"msg":"Order created","level":30}
// Searchable: userId=123 AND orderId=456
```

### Phòng ngừa
- [ ] Object-first logging (pino convention)
- [ ] Static message strings
- [ ] Structured fields for all variable data
- Tool: `pino`, `pino-pretty` (dev)

---

## Pattern 03: APM Integration Thiếu

### Tên
APM Thiếu (No Application Performance Monitoring)

### Phân loại
Monitoring / APM / Performance

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề
No visibility into request latency, DB query time, external call duration.

### Phát hiện
```bash
rg "datadog|newrelic|elastic-apm|@sentry" -n --glob "package.json"
rg --type ts "Sentry\.init|dd-trace|elastic-apm-node" -n
```

### Giải pháp
```typescript
// Sentry (error + performance):
import * as Sentry from '@sentry/node';
Sentry.init({
    dsn: process.env.SENTRY_DSN,
    tracesSampleRate: 0.1, // 10% of transactions
    integrations: [
        Sentry.httpIntegration(),
        Sentry.expressIntegration(),
        Sentry.prismaIntegration(),
    ],
});

// OpenTelemetry (vendor-neutral):
import { NodeSDK } from '@opentelemetry/sdk-node';
const sdk = new NodeSDK({ traceExporter, instrumentations: [getNodeAutoInstrumentations()] });
sdk.start();
```

### Phòng ngừa
- [ ] APM agent installed (Sentry/Datadog/New Relic)
- [ ] Auto-instrumentation for HTTP/DB
- Tool: Sentry, Datadog, OpenTelemetry

---

## Pattern 04: Event Loop Lag Monitoring Thiếu

### Tên
Event Loop Lag Monitoring (No EL Tracking)

### Phân loại
Monitoring / Event Loop / Performance

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề
Event loop blocked → all requests stall. No metric → issue invisible until timeout.

### Phát hiện
```bash
rg --type ts --type js "monitorEventLoopDelay|eventLoopLag" -n
rg --type ts --type js "perf_hooks" -n
```

### Giải pháp
```typescript
import { monitorEventLoopDelay } from 'perf_hooks';

const histogram = monitorEventLoopDelay({ resolution: 20 });
histogram.enable();

// Expose as metric:
setInterval(() => {
    const p99 = histogram.percentile(99) / 1e6; // ns → ms
    gauge.set({ quantile: '0.99' }, p99);
    if (p99 > 100) {
        logger.warn({ eventLoopLagMs: p99 }, 'High event loop lag');
    }
    histogram.reset();
}, 10000);
```

### Phòng ngừa
- [ ] `monitorEventLoopDelay` in production
- [ ] Alert on P99 > 100ms
- [ ] Profile with `--prof` or `clinic.js`
- Tool: `perf_hooks`, `clinic.js`

---

## Pattern 05: Heap Snapshot Không Capture

### Tên
Heap Snapshot Thiếu (No Memory Leak Detection)

### Phân loại
Monitoring / Memory / Debugging

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề
Memory grows over time but no heap snapshot capability → can't debug leaks in production.

### Phát hiện
```bash
rg --type ts --type js "writeHeapSnapshot|heapSnapshot" -n
rg --type ts --type js "v8|process\.memoryUsage" -n
```

### Giải pháp
```typescript
import v8 from 'v8';

// Expose endpoint for on-demand snapshots:
app.get('/debug/heap', (req, res) => {
    const filename = v8.writeHeapSnapshot();
    logger.info({ filename }, 'Heap snapshot written');
    res.json({ filename });
});

// Monitor memory:
setInterval(() => {
    const mem = process.memoryUsage();
    gauge.set({ type: 'heapUsed' }, mem.heapUsed);
    gauge.set({ type: 'rss' }, mem.rss);
    if (mem.heapUsed > 500 * 1024 * 1024) {
        logger.warn({ heapMb: mem.heapUsed / 1024 / 1024 }, 'High heap usage');
    }
}, 30000);
```

### Phòng ngừa
- [ ] Memory usage metrics exported
- [ ] Alert on heap growth trend
- [ ] On-demand heap snapshot endpoint (internal only)
- Tool: `v8.writeHeapSnapshot()`, Chrome DevTools

---

## Pattern 06: Error Tracking Thiếu

### Tên
Error Tracking Thiếu (No Sentry/Similar)

### Phân loại
Monitoring / Errors / Alerting

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề
Errors logged but not tracked → duplicates, no grouping, no trend, no assignment.

### Phát hiện
```bash
rg "@sentry|sentry" -n --glob "package.json"
rg --type ts "Sentry\." -n
```

### Giải pháp
```typescript
import * as Sentry from '@sentry/node';
Sentry.init({
    dsn: process.env.SENTRY_DSN,
    environment: process.env.NODE_ENV,
    release: process.env.APP_VERSION,
});

// Express error handler:
app.use(Sentry.Handlers.errorHandler());

// Manual capture:
try { await riskyOperation(); }
catch (err) {
    Sentry.captureException(err, { extra: { userId, context } });
    throw err;
}
```

### Phòng ngừa
- [ ] Error tracking service (Sentry/Bugsnag)
- [ ] Environment and release tags
- [ ] User context for debugging
- Tool: Sentry, Bugsnag

---

## Pattern 07: Health Check Endpoint Thiếu

### Tên
Health Check Thiếu (No /health Endpoint)

### Phân loại
Monitoring / Health / Kubernetes

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề
No health endpoint → load balancer can't remove unhealthy instances.

### Phát hiện
```bash
rg --type ts --type js "health|healthz|readyz" -n --glob "!*test*"
```

### Giải pháp
```typescript
app.get('/healthz/live', (req, res) => res.status(200).json({ status: 'ok' }));

app.get('/healthz/ready', async (req, res) => {
    try {
        await db.$queryRaw`SELECT 1`;
        await redis.ping();
        res.status(200).json({ status: 'ready', db: 'ok', redis: 'ok' });
    } catch (err) {
        res.status(503).json({ status: 'not ready', error: err.message });
    }
});
```

### Phòng ngừa
- [ ] Separate liveness and readiness
- [ ] Check dependencies in readiness
- Tool: K8s probes, `@godaddy/terminus`

---

## Pattern 08: Metrics Cardinality Explosion

### Tên
Metrics Cardinality Explosion (Prometheus OOM)

### Phân loại
Monitoring / Metrics / Prometheus

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề
```typescript
httpRequests.labels(userId, req.path, traceId).inc();
// user_id × path × traceId = millions of time series → Prometheus OOM
```

### Phát hiện
```bash
rg --type ts --type js "labels\(|labelValues" -n | rg "userId|user_id|requestId"
```

### Giải pháp
```typescript
import { Counter, Histogram, register } from 'prom-client';

const httpRequests = new Counter({
    name: 'http_requests_total',
    labelNames: ['method', 'status', 'path'], // Low cardinality only
});

// path = route pattern, not actual path:
httpRequests.labels(req.method, String(res.statusCode), req.route?.path || 'unknown').inc();
```

### Phòng ngừa
- [ ] No IDs as metric labels
- [ ] Route patterns, not actual URLs
- [ ] < 10 unique values per label
- Tool: `prom-client`

---

## Pattern 09: Distributed Tracing Context Sai

### Tên
Distributed Tracing Context Propagation Sai

### Phân loại
Monitoring / Tracing / Distributed

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề
Service A → Service B: trace context not propagated → separate traces.

### Phát hiện
```bash
rg --type ts --type js "traceparent|W3CTraceContext|propagat" -n
rg --type ts --type js "opentelemetry" -n --glob "package.json"
```

### Giải pháp
```typescript
import { NodeSDK } from '@opentelemetry/sdk-node';
import { getNodeAutoInstrumentations } from '@opentelemetry/auto-instrumentations-node';

const sdk = new NodeSDK({
    traceExporter: new OTLPTraceExporter({ url: 'http://jaeger:4318/v1/traces' }),
    instrumentations: [getNodeAutoInstrumentations()],
    // Auto-propagates W3C TraceContext headers
});
sdk.start();
```

### Phòng ngừa
- [ ] OpenTelemetry SDK with auto-instrumentation
- [ ] W3C TraceContext propagation
- Tool: OpenTelemetry, Jaeger, Zipkin

---

## Pattern 10: Resource Monitoring Thiếu

### Tên
Resource Monitoring Thiếu (No CPU/Memory/FD Metrics)

### Phân loại
Monitoring / Resources / System

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề
No visibility into process resources → silent resource exhaustion.

### Phát hiện
```bash
rg --type ts --type js "collectDefaultMetrics|process\.memoryUsage" -n
```

### Giải pháp
```typescript
import { collectDefaultMetrics, register } from 'prom-client';

// Collects: CPU, memory, event loop lag, handles, GC
collectDefaultMetrics({ prefix: 'myapp_' });

// Custom metrics:
const activeConnections = new Gauge({
    name: 'myapp_active_connections',
    help: 'Number of active connections',
});

// Expose:
app.get('/metrics', async (req, res) => {
    res.set('Content-Type', register.contentType);
    res.send(await register.metrics());
});
```

### Phòng ngừa
- [ ] `collectDefaultMetrics()` for Node.js runtime
- [ ] `/metrics` endpoint for Prometheus
- [ ] Alert on resource thresholds
- Tool: `prom-client`, Prometheus, Grafana
