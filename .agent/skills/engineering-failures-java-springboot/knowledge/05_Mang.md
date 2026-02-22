# Domain 05: Mạng (Networking)

> Java/Spring Boot patterns: HTTP clients, connection pools, timeouts, retry, DNS, WebClient.

---

## Pattern 01: RestTemplate Không Timeout

### Phân loại
Network / HTTP / Blocking — HIGH 🟠

### Vấn đề
```java
RestTemplate rt = new RestTemplate(); // No timeout configured!
rt.getForObject(url, String.class);  // Blocks forever if service hangs
```

### Phát hiện
```bash
rg --type java "new RestTemplate\\(\\)" -n
rg --type java "connectTimeout|readTimeout" -n
```

### Giải pháp
```java
@Bean
public RestClient restClient() {
    return RestClient.builder()
        .baseUrl("https://api.example.com")
        .requestFactory(new JdkClientHttpRequestFactory(
            HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(3)).build()))
        .build();
}
```

### Phòng ngừa
- [ ] Always configure connect + read timeouts
- [ ] `RestClient` (Spring 6.1+) over `RestTemplate`
- Tool: RestClient, Micrometer HTTP metrics

---

## Pattern 02: Connection Pool Exhaustion

### Phân loại
Network / Pool / HikariCP — CRITICAL 🔴

### Vấn đề
```
// Default HikariCP: maximumPoolSize=10
// Slow queries hold connections → pool exhausted → app hangs
// HikariPool-1 - Connection not available, timed out after 30000ms
```

### Phát hiện
```bash
rg "maximumPoolSize|maximum-pool-size|leak-detection" -n --glob "application*.yml"
rg --type java "HikariDataSource|getConnection" -n
```

### Giải pháp
```yaml
spring:
  datasource:
    hikari:
      maximum-pool-size: 20
      minimum-idle: 5
      connection-timeout: 5000
      leak-detection-threshold: 60000
```

### Phòng ngừa
- [ ] Pool size = `(CPU cores * 2) + disk spindles`
- [ ] `leak-detection-threshold` in dev/staging
- [ ] Monitor `hikaricp.*` metrics
- Tool: HikariCP, Micrometer

---

## Pattern 03: Cascading Timeout Failure

### Phân loại
Network / Timeout / Cascading — CRITICAL 🔴

### Vấn đề
```java
// No timeout → downstream hangs → your service hangs → caller hangs
WebClient.create().get().uri("http://slow-service/api")
    .retrieve().bodyToMono(String.class)
    .block(); // Blocks forever!
```

### Phát hiện
```bash
rg --type java "\\.block\\(\\)" -n
rg --type java "WebClient\\.create\\(\\)" -n
```

### Giải pháp
```java
@Bean
public WebClient webClient() {
    HttpClient httpClient = HttpClient.create()
        .responseTimeout(Duration.ofSeconds(10))
        .option(ChannelOption.CONNECT_TIMEOUT_MILLIS, 3000);
    return WebClient.builder()
        .clientConnector(new ReactorClientHttpConnector(httpClient))
        .build();
}

// With circuit breaker:
@CircuitBreaker(name = "external-api", fallbackMethod = "fallback")
public String callApi() { return restClient.get().uri("/api").retrieve().body(String.class); }
```

### Phòng ngừa
- [ ] Timeout on ALL HTTP clients
- [ ] Circuit breaker for external services
- Tool: Resilience4j, WebClient

---

## Pattern 04: Retry Không Backoff

### Phân loại
Network / Retry / Thundering Herd — HIGH 🟠

### Vấn đề
```java
for (int i = 0; i < 3; i++) {
    try { return callApi(); }
    catch (Exception e) { /* retry immediately → overwhelms failing service */ }
}
```

### Phát hiện
```bash
rg --type java "@Retryable|@Retry" -n
rg --type java "for.*try.*catch" -n
```

### Giải pháp
```java
@Retryable(
    retryFor = {HttpServerErrorException.class},
    maxAttempts = 3,
    backoff = @Backoff(delay = 1000, multiplier = 2, maxDelay = 10000)
)
public String callExternalApi() {
    return restClient.get().uri("/api").retrieve().body(String.class);
}

@Recover
public String fallback(HttpServerErrorException e) {
    log.warn("API unavailable after retries", e);
    return cachedResponse();
}
```

### Phòng ngừa
- [ ] Exponential backoff with jitter
- [ ] `@Recover` fallback method
- [ ] Circuit breaker + retry together
- Tool: Spring Retry, Resilience4j

---

## Pattern 05: DNS Cache Quá Lâu

### Phân loại
Network / DNS / Cloud — MEDIUM 🟡

### Vấn đề
```
// JVM caches DNS forever by default (networkaddress.cache.ttl=-1)
// Cloud services change IPs → app connects to old IP → failures
```

### Phát hiện
```bash
rg "networkaddress.cache.ttl" -n --glob "*.properties"
```

### Giải pháp
```
# JVM args:
-Dnetworkaddress.cache.ttl=60
-Dnetworkaddress.cache.negative.ttl=10
```

### Phòng ngừa
- [ ] `networkaddress.cache.ttl=60` for cloud
- Tool: JVM security properties

---

## Pattern 06: block() Trên Reactor Thread

### Phân loại
Network / Reactive / Thread — CRITICAL 🔴

### Vấn đề
```java
@GetMapping("/api/data")
public Mono<Data> getData() {
    String result = webClient.get().uri("/ext").retrieve()
        .bodyToMono(String.class).block(); // IllegalStateException on reactive thread!
    return Mono.just(new Data(result));
}
```

### Phát hiện
```bash
rg --type java "\\.block\\(\\)" -n
rg --type java "Mono<|Flux<" -n
```

### Giải pháp
```java
@GetMapping("/api/data")
public Mono<Data> getData() {
    return webClient.get().uri("/ext").retrieve()
        .bodyToMono(String.class)
        .map(Data::new); // Chain reactively, no block()
}

// Bridge to blocking I/O:
Mono.fromCallable(() -> jdbcTemplate.queryForObject("SELECT ...", String.class))
    .subscribeOn(Schedulers.boundedElastic());
```

### Phòng ngừa
- [ ] Never `block()` in reactive pipelines
- [ ] `Schedulers.boundedElastic()` for blocking I/O
- Tool: BlockHound, Project Reactor

---

## Pattern 07: HTTP Client Không Reuse

### Phân loại
Network / HTTP / Resource — HIGH 🟠

### Vấn đề
```java
public String callApi() {
    RestTemplate rt = new RestTemplate(); // New client per call!
    return rt.getForObject(url, String.class);
}
```

### Phát hiện
```bash
rg --type java "new RestTemplate\\(\\)|new OkHttpClient\\(\\)" -n --glob "*Service*"
```

### Giải pháp
```java
@Bean
public RestClient restClient() {
    return RestClient.builder().baseUrl("https://api.example.com").build();
}

@Service
public class ApiService {
    private final RestClient restClient; // Singleton bean, shared pool
    public String callApi() {
        return restClient.get().uri("/data").retrieve().body(String.class);
    }
}
```

### Phòng ngừa
- [ ] HTTP clients as Spring beans (singleton)
- [ ] Share connection pools across calls
- Tool: RestClient, WebClient
