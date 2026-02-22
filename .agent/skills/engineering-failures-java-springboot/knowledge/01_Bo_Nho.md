# Domain 01: Bộ Nhớ (Memory)

> Java/Spring Boot patterns liên quan đến memory: leaks, GC pressure, heap, classloader, ThreadLocal.

---

## Pattern 01: Memory Leak Qua Static Collections

### Phân loại
Memory / Leak / Static — HIGH 🟠

### Vấn đề
```java
public class CacheManager {
    private static final Map<String, Object> cache = new HashMap<>(); // Grows forever
    public static void put(String key, Object value) { cache.put(key, value); }
    // No eviction, no size limit → OOM
}
```

### Phát hiện
```bash
rg --type java "static.*Map|static.*List|static.*Set" -n --glob "!*Test*"
rg --type java "static final.*new (HashMap|ArrayList|HashSet)" -n
```

### Giải pháp
```java
// BAD: Unbounded static cache
private static final Map<String, Object> cache = new HashMap<>();

// GOOD: Bounded cache with eviction
private static final Cache<String, Object> cache = Caffeine.newBuilder()
    .maximumSize(10_000)
    .expireAfterWrite(Duration.ofMinutes(30))
    .build();

// Or use Spring @Cacheable:
@Cacheable(value = "users", key = "#id")
public User findById(Long id) { return userRepository.findById(id).orElseThrow(); }
```

### Phòng ngừa
- [ ] No unbounded static collections
- [ ] Caffeine or Spring Cache with TTL
- [ ] Monitor heap with JFR/VisualVM
- Tool: Caffeine, Spring Cache, JFR

---

## Pattern 02: ThreadLocal Leak

### Phân loại
Memory / Leak / ThreadLocal — HIGH 🟠

### Vấn đề
```java
private static final ThreadLocal<UserContext> context = new ThreadLocal<>();
// In servlet container: threads are pooled and reused
// ThreadLocal not cleaned → data leaks between requests
// Also prevents GC of UserContext and everything it references
```

### Phát hiện
```bash
rg --type java "ThreadLocal<" -n
rg --type java "\.remove\(\)" -n | rg "ThreadLocal"
```

### Giải pháp
```java
// ALWAYS clean up in finally/filter:
@Component
public class ContextFilter extends OncePerRequestFilter {
    @Override
    protected void doFilterInternal(HttpServletRequest req, HttpServletResponse res, FilterChain chain) {
        try {
            UserContext.set(extractUser(req));
            chain.doFilter(req, res);
        } finally {
            UserContext.clear(); // CRITICAL: always clean up
        }
    }
}

// Or use request-scoped bean instead:
@Bean @RequestScope
public UserContext userContext() { return new UserContext(); }
```

### Phòng ngừa
- [ ] `finally` block or Filter to clean ThreadLocal
- [ ] Prefer request-scoped beans over ThreadLocal
- [ ] Extra caution with virtual threads (carrier thread leak)
- Tool: SpotBugs, IntelliJ inspections

---

## Pattern 03: Connection/Resource Leak

### Phân loại
Memory / Leak / Resource — CRITICAL 🔴

### Vấn đề
```java
Connection conn = dataSource.getConnection();
PreparedStatement ps = conn.prepareStatement("SELECT ...");
ResultSet rs = ps.executeQuery();
// Exception thrown here → conn never closed → pool exhausted → app hangs
```

### Phát hiện
```bash
rg --type java "getConnection\(\)|prepareStatement\(|createStatement\(" -n
rg --type java "try.*getConnection" -n | rg -v "try-with"
```

### Giải pháp
```java
// GOOD: try-with-resources
try (Connection conn = dataSource.getConnection();
     PreparedStatement ps = conn.prepareStatement("SELECT * FROM users WHERE id = ?")) {
    ps.setLong(1, userId);
    try (ResultSet rs = ps.executeQuery()) {
        if (rs.next()) return mapUser(rs);
    }
}

// BEST: Use Spring JdbcTemplate (handles resources automatically):
return jdbcTemplate.queryForObject("SELECT * FROM users WHERE id = ?", userRowMapper, userId);
```

### Phòng ngừa
- [ ] Always try-with-resources for AutoCloseable
- [ ] Spring JdbcTemplate/JPA over raw JDBC
- [ ] Connection pool leak detection (HikariCP)
- Tool: SpotBugs `OBL_UNSATISFIED_OBLIGATION`, HikariCP leak detection

---

## Pattern 04: Large Object Heap Pressure

### Phân loại
Memory / GC / Heap — HIGH 🟠

### Vấn đề
```java
public byte[] exportReport() {
    List<Record> all = repository.findAll(); // 1M records into memory
    byte[] csv = convertToCsv(all);          // Another copy in memory
    return csv;                               // Peak: 3x data size
}
```

### Phát hiện
```bash
rg --type java "findAll\(\)" -n --glob "!*Test*"
rg --type java "byte\[\]|ByteArrayOutputStream" -n
rg --type java "toList\(\)|collect\(Collectors" -n
```

### Giải pháp
```java
// GOOD: Stream processing with pagination
@Transactional(readOnly = true)
public void exportReport(OutputStream out) {
    try (Stream<Record> stream = repository.streamAll()) {
        stream.forEach(record -> {
            writeCsvLine(out, record); // Write one at a time
        });
    }
}

// Or pagination:
Pageable page = PageRequest.of(0, 1000);
Page<Record> result;
do {
    result = repository.findAll(page);
    result.forEach(r -> writeCsvLine(out, r));
    page = page.next();
} while (result.hasNext());
```

### Phòng ngừa
- [ ] Stream large datasets, don't collect
- [ ] Pagination for batch processing
- [ ] `-Xmx` appropriate for workload
- Tool: JFR, VisualVM heap dump

---

## Pattern 05: String Concatenation In Loop

### Phân loại
Memory / GC / String — MEDIUM 🟡

### Vấn đề
```java
String result = "";
for (var item : items) {
    result += item.toString() + ","; // O(n²) — new String each iteration
}
```

### Phát hiện
```bash
rg --type java "\+= .*\.toString\(\)|result \+= |sql \+= " -n
rg --type java "for.*\{" -A 5 | rg "\+="
```

### Giải pháp
```java
// GOOD: StringBuilder
StringBuilder sb = new StringBuilder();
for (var item : items) { sb.append(item).append(","); }

// BEST: String.join or Collectors.joining
String result = items.stream()
    .map(Object::toString)
    .collect(Collectors.joining(","));

// Or: String.join(",", stringList);
```

### Phòng ngừa
- [ ] StringBuilder for loops
- [ ] `Collectors.joining()` for streams
- [ ] `String.join()` for simple cases
- Tool: SpotBugs `SBSC_USE_STRINGBUFFER_CONCATENATION`

---

## Pattern 06: Classloader Leak

### Phân loại
Memory / Leak / Classloader — HIGH 🟠

### Vấn đề
```java
// JDBC driver registered but not deregistered on redeploy
// Static references to application classes from JVM-level objects
// → Previous classloader can't be GC'd → Metaspace OOM
```

### Phát hiện
```bash
rg --type java "Class\.forName|DriverManager\.register" -n
rg --type java "static.*Thread|static.*Timer|static.*Executor" -n
```

### Giải pháp
```java
// Deregister drivers on shutdown:
@PreDestroy
public void cleanup() {
    Enumeration<Driver> drivers = DriverManager.getDrivers();
    while (drivers.hasMoreElements()) {
        try { DriverManager.deregisterDriver(drivers.nextElement()); }
        catch (SQLException e) { log.warn("Deregister failed", e); }
    }
}

// Spring Boot handles this automatically with connection pools
// Just ensure no static references to application beans
```

### Phòng ngừa
- [ ] No `Class.forName()` for JDBC (use connection pool)
- [ ] Clean up static resources on shutdown
- [ ] Monitor Metaspace usage
- Tool: `-XX:MaxMetaspaceSize=256m`, JFR

---

## Pattern 07: InputStream/Response Body Not Consumed

### Phân loại
Memory / Leak / HTTP — MEDIUM 🟡

### Vấn đề
```java
HttpResponse<InputStream> response = httpClient.send(request, BodyHandlers.ofInputStream());
if (response.statusCode() != 200) {
    return; // Body not consumed → connection not released back to pool
}
```

### Phát hiện
```bash
rg --type java "BodyHandlers\.ofInputStream|getEntity\(\)" -n
rg --type java "EntityUtils\.consume" -n
```

### Giải pháp
```java
// GOOD: Always consume or close response body
try (InputStream body = response.body()) {
    if (response.statusCode() != 200) {
        body.readAllBytes(); // Consume to release connection
        throw new ApiException(response.statusCode());
    }
    return objectMapper.readValue(body, MyDto.class);
}

// Spring RestClient/WebClient handles this automatically
var result = restClient.get()
    .uri("/api/users/{id}", id)
    .retrieve()
    .body(UserDto.class);
```

### Phòng ngừa
- [ ] Always close/consume HTTP response bodies
- [ ] Use Spring RestClient (auto-managed)
- Tool: Spring RestClient, WebClient
