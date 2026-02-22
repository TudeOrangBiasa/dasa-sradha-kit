# Domain 12: Giám Sát Và Quan Sát (Monitoring & Observability)

> .NET patterns: ILogger, OpenTelemetry, health checks, metrics, tracing, diagnostics.

---

## Pattern 01: ILogger Structured Logging Thiếu

### Phân loại
Monitoring / Logging — HIGH 🟠

### Vấn đề
```csharp
_logger.LogInformation($"User {userId} created order {orderId}");
// String interpolation → can't search by field, allocated even if disabled
```

### Phát hiện
```bash
rg --type cs "Log(Information|Warning|Error)\(\$\"" -n
```

### Giải pháp
```csharp
// Message templates (structured):
_logger.LogInformation("User {UserId} created order {OrderId}", userId, orderId);

// Source-generated (zero allocation):
[LoggerMessage(Level = LogLevel.Information, Message = "Order {OrderId} created")]
static partial void LogOrderCreated(ILogger logger, int orderId);
```

### Phòng ngừa
- [ ] Message templates, not interpolation
- [ ] `LoggerMessage.Define` for hot paths
- Tool: Serilog, `Microsoft.Extensions.Logging`

---

## Pattern 02: OpenTelemetry Integration Thiếu

### Phân loại
Monitoring / Telemetry — HIGH 🟠

### Vấn đề
No standardized telemetry → vendor lock-in, missing trace correlation.

### Phát hiện
```bash
rg "OpenTelemetry" -n --glob "*.csproj"
```

### Giải pháp
```csharp
builder.Services.AddOpenTelemetry()
    .WithTracing(t => t
        .AddAspNetCoreInstrumentation()
        .AddHttpClientInstrumentation()
        .AddOtlpExporter())
    .WithMetrics(m => m
        .AddAspNetCoreInstrumentation()
        .AddOtlpExporter());
```

### Phòng ngừa
- [ ] OpenTelemetry SDK for traces + metrics
- [ ] OTLP exporter to collector
- Tool: `OpenTelemetry.Extensions.Hosting`

---

## Pattern 03: Application Insights Overhead

### Phân loại
Monitoring / APM — MEDIUM 🟡

### Vấn đề
Default 100% sampling → high cost and data volume.

### Phát hiện
```bash
rg --type cs "AddApplicationInsightsTelemetry" -n
```

### Giải pháp
```csharp
builder.Services.AddApplicationInsightsTelemetry(o =>
    o.EnableAdaptiveSampling = true);
```

### Phòng ngừa
- [ ] Adaptive or fixed-rate sampling
- [ ] Filter health check telemetry
- Tool: Application Insights sampling

---

## Pattern 04: Health Check Superficial

### Phân loại
Monitoring / Health — MEDIUM 🟡

### Vấn đề
```csharp
app.MapHealthChecks("/health"); // Always healthy — doesn't check deps
```

### Phát hiện
```bash
rg --type cs "MapHealthChecks|AddHealthChecks" -n
```

### Giải pháp
```csharp
builder.Services.AddHealthChecks()
    .AddSqlServer(connStr, name: "db", tags: ["ready"])
    .AddRedis(redisConn, name: "cache", tags: ["ready"]);

app.MapHealthChecks("/healthz/live", new() { Predicate = c => c.Tags.Contains("live") });
app.MapHealthChecks("/healthz/ready", new() { Predicate = c => c.Tags.Contains("ready") });
```

### Phòng ngừa
- [ ] Separate live/ready endpoints
- [ ] Check dependencies in readiness
- Tool: `AspNetCore.HealthChecks.*`

---

## Pattern 05: Metrics Cardinality Explosion

### Phân loại
Monitoring / Metrics — HIGH 🟠

### Vấn đề
```csharp
counter.Add(1, new("user_id", userId), new("path", request.Path));
// Millions of unique series → Prometheus OOM
```

### Phát hiện
```bash
rg --type cs "CreateCounter|CreateHistogram" -n | rg "user|request_id"
```

### Giải pháp
```csharp
counter.Add(1,
    new("http.method", req.Method),
    new("http.status_code", res.StatusCode),
    new("http.route", endpoint?.RoutePattern ?? "unknown"));
```

### Phòng ngừa
- [ ] No IDs as metric tags
- [ ] Route patterns, not actual paths
- Tool: `System.Diagnostics.Metrics`

---

## Pattern 06: Distributed Tracing Context Sai

### Phân loại
Monitoring / Tracing — HIGH 🟠

### Vấn đề
```csharp
var client = new HttpClient();
await client.GetAsync("http://service-b/api"); // No trace propagation
```

### Phát hiện
```bash
rg --type cs "new HttpClient\(\)" -n --glob "!*test*"
```

### Giải pháp
```csharp
// IHttpClientFactory auto-propagates trace context:
builder.Services.AddHttpClient("ServiceB", c => c.BaseAddress = new("http://service-b"));
builder.Services.AddOpenTelemetry().WithTracing(t => t.AddHttpClientInstrumentation());
```

### Phòng ngừa
- [ ] `IHttpClientFactory` (not `new HttpClient()`)
- [ ] OpenTelemetry HTTP instrumentation
- Tool: `IHttpClientFactory`, OpenTelemetry

---

## Pattern 07: EventCounter Thiếu

### Phân loại
Monitoring / Diagnostics — MEDIUM 🟡

### Vấn đề
No visibility into .NET runtime: GC pauses, thread pool, exception rate.

### Phát hiện
```bash
rg --type cs "EventCounter|EventSource" -n
```

### Giải pháp
```bash
# Monitor runtime counters:
dotnet-counters monitor --process-id <PID>
```

```csharp
[EventSource(Name = "MyApp")]
public sealed class AppEvents : EventSource {
    public static readonly AppEvents Instance = new();
    private readonly IncrementingEventCounter _requests;
    AppEvents() { _requests = new("requests", this); }
    public void RequestReceived() => _requests.Increment();
}
```

### Phòng ngừa
- [ ] `dotnet-counters` for runtime monitoring
- [ ] Custom EventCounters for app metrics
- Tool: `dotnet-counters`, `dotnet-trace`

---

## Pattern 08: DiagnosticSource Thiếu

### Phân loại
Monitoring / Diagnostics — MEDIUM 🟡

### Vấn đề
No custom diagnostic events → can't trace application-level operations.

### Phát hiện
```bash
rg --type cs "ActivitySource" -n
```

### Giải pháp
```csharp
private static readonly ActivitySource Source = new("MyApp.Orders");

public async Task<Order> Process(int orderId) {
    using var activity = Source.StartActivity("ProcessOrder");
    activity?.SetTag("order.id", orderId);
    try { return await Execute(orderId); }
    catch (Exception ex) { activity?.RecordException(ex); throw; }
}
```

### Phòng ngừa
- [ ] `ActivitySource` for custom spans
- [ ] Record exceptions on activities
- Tool: `System.Diagnostics.Activity`

---

## Pattern 09: Dump Analysis Thiếu

### Phân loại
Monitoring / Debug — MEDIUM 🟡

### Vấn đề
Production crash → no dump → can't analyze root cause.

### Phát hiện
```bash
rg "DOTNET_DbgEnableMiniDump" -n --glob "Dockerfile"
```

### Giải pháp
```dockerfile
ENV DOTNET_DbgEnableMiniDump=1
ENV DOTNET_DbgMiniDumpType=4
```

```bash
dotnet-dump collect --process-id <PID>
dotnet-dump analyze dump.dmp
> dumpheap -stat
```

### Phòng ngừa
- [ ] Auto-dump on crash enabled
- [ ] `dotnet-dump` available in container
- Tool: `dotnet-dump`, `dotnet-gcdump`

---

## Pattern 10: Performance Counter Export Thiếu

### Phân loại
Monitoring / Metrics — MEDIUM 🟡

### Vấn đề
.NET runtime exposes rich metrics but not exported to Prometheus/Grafana.

### Phát hiện
```bash
rg "prometheus-net|PrometheusExporter" -n --glob "*.csproj"
```

### Giải pháp
```csharp
builder.Services.AddOpenTelemetry()
    .WithMetrics(m => m
        .AddAspNetCoreInstrumentation()
        .AddRuntimeInstrumentation()
        .AddPrometheusExporter());
app.MapPrometheusScrapingEndpoint();
```

### Phòng ngừa
- [ ] `/metrics` endpoint for Prometheus
- [ ] Runtime instrumentation enabled
- Tool: `prometheus-net`, OpenTelemetry
