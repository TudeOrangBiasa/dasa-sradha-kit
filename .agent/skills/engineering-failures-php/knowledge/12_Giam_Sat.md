# Domain 12: Giám Sát Và Quan Sát (Monitoring & Observability)

> PHP/Laravel patterns liên quan đến monitoring: error logging, slow queries, APM, queue monitoring, PHP-FPM, cron jobs.

---

## Pattern 01: Error Log Không Structured

### Tên
Error Log Không Structured (Unstructured Logs)

### Phân loại
Monitoring / Logging / Format

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề
```php
error_log("Something went wrong for user $userId");
Log::error("Order failed: " . $exception->getMessage());
// Unstructured — can't filter, aggregate, or search efficiently
```

### Phát hiện
```bash
rg --type php "error_log\(|Log::error\(" -n --glob "!*test*"
rg --type php "Log::\w+\(" -n | rg -v "context"
```

### Giải pháp
```php
// BAD: String concatenation
Log::error("Order failed for user $userId: $error");

// GOOD: Structured context
Log::error('Order processing failed', [
    'user_id' => $userId,
    'order_id' => $orderId,
    'error' => $exception->getMessage(),
    'trace' => $exception->getTraceAsString(),
]);

// config/logging.php — JSON format for production:
'production' => [
    'driver' => 'daily',
    'formatter' => Monolog\Formatter\JsonFormatter::class,
],
```

### Phòng ngừa
- [ ] Context arrays in all Log calls
- [ ] JSON formatter for production
- [ ] No string concatenation in log messages
- Tool: Monolog, Laravel Log

---

## Pattern 02: Slow Query Log Thiếu

### Tên
Slow Query Log Thiếu (No Query Performance Tracking)

### Phân loại
Monitoring / Database / Performance

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề
Slow queries degrade performance silently. No visibility into DB bottlenecks.

### Phát hiện
```bash
rg --type php "DB::listen|enableQueryLog" -n
rg --type php "slow.*query|query.*log" -n
```

### Giải pháp
```php
// AppServiceProvider:
DB::listen(function ($query) {
    if ($query->time > 1000) { // > 1 second
        Log::warning('Slow query detected', [
            'sql' => $query->sql,
            'bindings' => $query->bindings,
            'time_ms' => $query->time,
        ]);
    }
});

// Or use Laravel Telescope (development):
// Or use MySQL slow query log:
// SET GLOBAL slow_query_log = 'ON';
// SET GLOBAL long_query_time = 1;
```

### Phòng ngừa
- [ ] `DB::listen` for slow query logging
- [ ] MySQL slow query log enabled
- [ ] APM for query performance tracking
- Tool: Laravel Telescope, MySQL slow log

---

## Pattern 03: APM Integration Thiếu

### Tên
APM Integration Thiếu (No Application Performance Monitoring)

### Phân loại
Monitoring / APM / Performance

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề
No APM → can't identify bottlenecks, slow endpoints, error patterns.

### Phát hiện
```bash
rg "datadog|newrelic|elastic-apm|sentry" -n --glob "composer.json"
rg --type php "Sentry|NewRelic|dd_trace" -n
```

### Giải pháp
```php
// Sentry (error tracking + performance):
// composer require sentry/sentry-laravel
// .env: SENTRY_LARAVEL_DSN=https://...@sentry.io/...

// config/sentry.php:
'traces_sample_rate' => env('SENTRY_TRACES_SAMPLE_RATE', 0.1), // 10% sampling

// Custom span:
\Sentry\SentrySdk::getCurrentHub()->getSpan()?->startChild(
    SpanContext::make()->setOp('db.query')->setDescription('Find user')
);
```

### Phòng ngừa
- [ ] APM agent installed (Sentry/Datadog/New Relic)
- [ ] Sampling rate configured
- [ ] Custom spans for critical operations
- Tool: Sentry, Datadog, New Relic

---

## Pattern 04: Queue Job Failure Monitoring Thiếu

### Tên
Queue Job Failure Monitoring Thiếu (Silent Job Failures)

### Phân loại
Monitoring / Queue / Alerting

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề
Queue jobs fail silently. Failed jobs accumulate in `failed_jobs` table unnoticed.

### Phát hiện
```bash
rg --type php "failed_jobs|Queue::failing" -n
rg --type php "horizon" -n --glob "composer.json"
```

### Giải pháp
```php
// AppServiceProvider:
Queue::failing(function (JobFailed $event) {
    Log::critical('Queue job failed', [
        'job' => $event->job->resolveName(),
        'connection' => $event->connectionName,
        'exception' => $event->exception->getMessage(),
    ]);
    // Alert via Slack/PagerDuty
});

// Or use Horizon dashboard:
// composer require laravel/horizon
// php artisan horizon:install

// Horizon notification:
Horizon::routeMailNotificationsTo('ops@example.com');
Horizon::routeSlackNotificationsTo($webhookUrl, '#alerts');
```

### Phòng ngừa
- [ ] `Queue::failing` listener
- [ ] Laravel Horizon for Redis queues
- [ ] Alert on failed job count
- Tool: Laravel Horizon, Slack notifications

---

## Pattern 05: PHP-FPM Status Page Thiếu

### Tên
PHP-FPM Status Page Thiếu (No FPM Metrics)

### Phân loại
Monitoring / FPM / Infrastructure

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề
No visibility into PHP-FPM: active/idle workers, request queue, slow requests.

### Phát hiện
```bash
rg "pm.status_path|pm.status" -n --glob "*.conf" --glob "php-fpm*"
rg "status_path" -n --glob "www.conf"
```

### Giải pháp
```ini
; php-fpm.d/www.conf:
pm.status_path = /status
pm.status_listen = 127.0.0.1:9001
ping.path = /ping

; Tune pool:
pm = dynamic
pm.max_children = 50
pm.start_servers = 10
pm.min_spare_servers = 5
pm.max_spare_servers = 20
pm.max_requests = 500
```

```nginx
# Nginx — internal only:
location /fpm-status {
    fastcgi_pass php:9000;
    fastcgi_param SCRIPT_FILENAME $document_root$fastcgi_script_name;
    include fastcgi_params;
    allow 10.0.0.0/8;
    deny all;
}
```

### Phòng ngừa
- [ ] FPM status page on internal endpoint
- [ ] Export to Prometheus via exporter
- [ ] Monitor active processes and queue length
- Tool: `php-fpm_exporter`, Prometheus

---

## Pattern 06: Memory Usage Alert Thiếu

### Tên
Memory Alert Thiếu (PHP Memory Exhaustion)

### Phân loại
Monitoring / Memory / Resource

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề
```
Fatal error: Allowed memory size of 134217728 bytes exhausted
// No alert, no monitoring — discovered when requests start failing
```

### Phát hiện
```bash
rg "memory_limit|memory_get_usage" -n --glob "php.ini" --glob "*.php"
```

### Giải pháp
```php
// Log memory usage for heavy operations:
$memBefore = memory_get_usage(true);
$result = processLargeDataset($data);
$memAfter = memory_get_usage(true);

if (($memAfter - $memBefore) > 50 * 1024 * 1024) { // > 50MB
    Log::warning('High memory usage', [
        'operation' => 'processLargeDataset',
        'memory_delta_mb' => ($memAfter - $memBefore) / 1024 / 1024,
        'peak_mb' => memory_get_peak_usage(true) / 1024 / 1024,
    ]);
}
```

### Phòng ngừa
- [ ] Monitor PHP-FPM memory per worker
- [ ] `memory_limit` appropriate for workload
- [ ] Alert on peak memory usage
- Tool: `php-fpm_exporter`, Datadog

---

## Pattern 07: OPcache Hit Rate Monitoring Thiếu

### Tên
OPcache Hit Rate Monitoring (No Cache Metrics)

### Phân loại
Monitoring / OPcache / Performance

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề
Low OPcache hit rate → PHP recompiles scripts every request → 3-5x slower.

### Phát hiện
```bash
rg "opcache" -n --glob "php.ini"
rg --type php "opcache_get_status" -n
```

### Giải pháp
```php
// Health check endpoint:
Route::get('/metrics/opcache', function () {
    $status = opcache_get_status(false);
    return [
        'hit_rate' => $status['opcache_statistics']['hit_rate'],
        'used_memory_mb' => $status['memory_usage']['used_memory'] / 1024 / 1024,
        'free_memory_mb' => $status['memory_usage']['free_memory'] / 1024 / 1024,
        'cached_scripts' => $status['opcache_statistics']['num_cached_scripts'],
    ];
});
```

### Phòng ngừa
- [ ] OPcache status endpoint (internal only)
- [ ] Alert on hit rate < 95%
- [ ] `opcache.validate_timestamps=0` in production
- Tool: `opcache-gui`, Prometheus exporter

---

## Pattern 08: Cron Job Monitoring Thiếu

### Tên
Cron Job Monitoring (Silent Cron Failures)

### Phân loại
Monitoring / Cron / Scheduling

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề
Scheduled commands fail silently. No notification when daily report doesn't run.

### Phát hiện
```bash
rg --type php "->cron\(|->daily\(|->hourly\(" -n
rg --type php "withoutOverlapping|onFailure|onSuccess" -n
```

### Giải pháp
```php
// app/Console/Kernel.php:
$schedule->command('reports:daily')
    ->daily()
    ->withoutOverlapping()
    ->onFailure(function () {
        Log::critical('Daily report cron failed');
        // Notify Slack/PagerDuty
    })
    ->onSuccess(function () {
        Log::info('Daily report completed');
    })
    ->pingOnSuccess($healthCheckUrl)
    ->pingOnFailure($alertUrl);
```

### Phòng ngừa
- [ ] `onFailure` callbacks for all scheduled commands
- [ ] Health check pings (Healthchecks.io, Better Stack)
- [ ] `withoutOverlapping` for long-running jobs
- Tool: Healthchecks.io, Laravel Scheduler

---

## Pattern 09: HTTP Error Rate Alert Thiếu

### Tên
HTTP Error Rate Alert (No 5xx Monitoring)

### Phân loại
Monitoring / HTTP / Alerting

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề
5xx errors spike but no alert → users experience errors before team notices.

### Phát hiện
```bash
rg --type php "exception.*handler|report\(" -n --glob "Handler*"
rg "error_rate|5xx" -n --glob "*.yml"
```

### Giải pháp
```php
// App\Exceptions\Handler:
public function register(): void
{
    $this->reportable(function (\Throwable $e) {
        // Track error metrics:
        Counter::increment('http_errors_total', [
            'type' => get_class($e),
            'code' => $e instanceof HttpException ? $e->getStatusCode() : 500,
        ]);
    });
}
```

```yaml
# Prometheus alert:
- alert: HighErrorRate
  expr: rate(http_errors_total{code=~"5.."}[5m]) > 0.1
  for: 5m
```

### Phòng ngừa
- [ ] Error counter metrics
- [ ] Alert on 5xx rate increase
- Tool: Sentry, Prometheus, Grafana

---

## Pattern 10: Dependency Vulnerability Scanning Thiếu

### Tên
Dependency Scanning Thiếu (No CVE Monitoring)

### Phân loại
Monitoring / Security / Dependencies

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề
Known vulnerabilities in Composer packages go undetected.

### Phát hiện
```bash
rg "audit" -n --glob "*.yml" --glob "Makefile"
```

### Giải pháp
```bash
# Composer audit (built-in since 2.4):
composer audit

# CI pipeline:
composer audit --format=json
# Fail on critical:
composer audit --locked || exit 1
```

```yaml
# GitHub Dependabot:
# .github/dependabot.yml:
version: 2
updates:
  - package-ecosystem: "composer"
    directory: "/"
    schedule:
      interval: "weekly"
```

### Phòng ngừa
- [ ] `composer audit` in CI
- [ ] Dependabot/Renovate for auto-updates
- [ ] Monthly dependency review
- Tool: `composer audit`, Snyk, Dependabot
