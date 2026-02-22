# Domain 08: Hiệu Năng (Performance)

> Java/Spring Boot patterns: N+1, caching, lazy loading, GC tuning, connection pool, batch processing.

---

## Pattern 01: N+1 Query Hibernate

### Phân loại
Performance / JPA / Query — CRITICAL 🔴

### Vấn đề
```java
List<Order> orders = orderRepo.findAll(); // 1 query
for (Order o : orders) {
    o.getCustomer().getName(); // N queries (1 per order)!
}
// 100 orders = 101 queries!
```

### Phát hiện
```bash
rg --type java "spring.jpa.show-sql" -n --glob "application*.yml"
rg --type java "@OneToMany|@ManyToOne" -n
rg --type java "getHibernateStatistics|hibernate.generate_statistics" -n
```

### Giải pháp
```java
// GOOD: JOIN FETCH
@Query("SELECT o FROM Order o JOIN FETCH o.customer WHERE o.status = :s")
List<Order> findByStatusWithCustomer(@Param("s") String status);

// GOOD: @EntityGraph
@EntityGraph(attributePaths = {"customer", "items"})
List<Order> findByStatus(String status);

// Enable statistics in dev:
// spring.jpa.properties.hibernate.generate_statistics=true
```

### Phòng ngừa
- [ ] `hibernate.generate_statistics=true` in dev
- [ ] `JOIN FETCH` or `@EntityGraph`
- [ ] DTO projections for read-only queries
- Tool: Hibernate Statistics, p6spy, Hypersistence Optimizer

---

## Pattern 02: Second-Level Cache Không Dùng

### Phân loại
Performance / Cache / Hibernate — HIGH 🟠

### Vấn đề
```java
// Frequently read, rarely changed entities (Country, Currency, Config)
// Every request hits DB for same data
Country country = countryRepo.findById(1L).orElseThrow(); // DB hit every time
```

### Phát hiện
```bash
rg --type java "@Cacheable|@CacheEvict" -n
rg "spring.cache|hibernate.cache" -n --glob "application*.yml"
rg --type java "Cache<|Caffeine" -n
```

### Giải pháp
```java
// Application-level cache (recommended):
@Cacheable(value = "countries", key = "#id")
public Country findById(Long id) {
    return countryRepo.findById(id).orElseThrow();
}

@CacheEvict(value = "countries", key = "#country.id")
public Country update(Country country) {
    return countryRepo.save(country);
}

// application.yml:
// spring.cache.type: caffeine
// spring.cache.caffeine.spec: maximumSize=1000,expireAfterWrite=30m
```

### Phòng ngừa
- [ ] `@Cacheable` for read-heavy, write-rare data
- [ ] Caffeine as cache provider
- [ ] `@CacheEvict` on mutations
- Tool: Spring Cache, Caffeine, Redis

---

## Pattern 03: findAll() Không Pagination

### Phân loại
Performance / Query / Memory — HIGH 🟠

### Vấn đề
```java
@GetMapping("/users")
public List<User> getUsers() {
    return userRepo.findAll(); // 1M users loaded into memory!
}
```

### Phát hiện
```bash
rg --type java "findAll\\(\\)" -n --glob "!*Test*"
rg --type java "List<.*>.*find" -n --glob "*Controller*"
```

### Giải pháp
```java
@GetMapping("/users")
public Page<UserDto> getUsers(
    @RequestParam(defaultValue = "0") int page,
    @RequestParam(defaultValue = "20") int size) {
    Pageable pageable = PageRequest.of(page, size, Sort.by("id"));
    return userRepo.findAll(pageable).map(UserDto::from);
}

// Limit max page size:
@GetMapping("/users")
public Page<UserDto> getUsers(@ParameterObject Pageable pageable) {
    int safeSize = Math.min(pageable.getPageSize(), 100);
    Pageable safe = PageRequest.of(pageable.getPageNumber(), safeSize);
    return userRepo.findAll(safe).map(UserDto::from);
}
```

### Phòng ngừa
- [ ] Always paginate list endpoints
- [ ] Max page size limit (e.g., 100)
- [ ] `spring.data.web.pageable.max-page-size=100`
- Tool: Spring Data Pageable

---

## Pattern 04: Lazy Loading Ngoài Session

### Phân loại
Performance / JPA / Session — HIGH 🟠

### Vấn đề
```java
@Service
public class ReportService {
    public void generateReport() {
        List<Order> orders = orderRepo.findAll();
        // Session closed after findAll()
        for (Order o : orders) {
            o.getItems().size(); // LazyInitializationException!
        }
    }
}
```

### Phát hiện
```bash
rg --type java "LazyInitializationException" -n
rg --type java "open-in-view" -n --glob "application*.yml"
```

### Giải pháp
```java
// GOOD: @Transactional(readOnly = true) keeps session open
@Transactional(readOnly = true)
public void generateReport() {
    List<Order> orders = orderRepo.findAllWithItems(); // JOIN FETCH
    orders.forEach(o -> processItems(o.getItems()));
}

// Disable open-in-view (anti-pattern):
// spring.jpa.open-in-view=false
```

### Phòng ngừa
- [ ] `spring.jpa.open-in-view=false`
- [ ] Fetch needed data in `@Transactional` scope
- [ ] DTO projection to avoid lazy traps
- Tool: Spring Data JPA, MapStruct

---

## Pattern 05: GC Pressure Từ Boxing

### Phân loại
Performance / GC / Boxing — MEDIUM 🟡

### Vấn đề
```java
// Autoboxing in hot path:
Map<Long, Integer> counts = new HashMap<>();
for (long id : ids) {
    counts.merge(id, 1, Integer::sum); // Long autobox + Integer autobox per iteration
}
// Millions of short-lived wrapper objects → GC pressure
```

### Phát hiện
```bash
rg --type java "Map<Long|Map<Integer|List<Integer" -n
rg --type java "HashMap<.*Long.*Integer" -n
```

### Giải pháp
```java
// Use primitive-friendly collections (Eclipse Collections, Koloboke):
// import org.eclipse.collections.impl.map.mutable.primitive.*;
LongIntHashMap counts = new LongIntHashMap();
for (long id : ids) {
    counts.addToValue(id, 1); // No boxing
}

// Or for simple counters:
long[] counts = new long[maxId + 1]; // Array-based if IDs are dense
```

### Phòng ngừa
- [ ] Primitive collections for hot paths
- [ ] Profile with JFR to detect boxing
- Tool: Eclipse Collections, JFR allocation profiling

---

## Pattern 06: @Transactional(readOnly=true) Thiếu

### Phân loại
Performance / JPA / Read — MEDIUM 🟡

### Vấn đề
```java
@Transactional // Read-write transaction for read-only operation!
public List<User> getUsers() {
    return userRepo.findAll();
    // Hibernate tracks dirty state → unnecessary overhead
    // DB uses read-write locks instead of read locks
}
```

### Phát hiện
```bash
rg --type java "@Transactional" -n | rg -v "readOnly"
rg --type java "findAll|findBy|get|list|search" -n --glob "*Service*"
```

### Giải pháp
```java
@Transactional(readOnly = true) // Hibernate skips dirty checking, DB uses read locks
public List<UserDto> getUsers() {
    return userRepo.findAll().stream().map(UserDto::from).toList();
}

// Or at class level for read-heavy services:
@Service
@Transactional(readOnly = true)
public class ReportService {
    public List<Report> getReports() { /* ... */ }

    @Transactional // Override for write operations
    public Report createReport(ReportRequest req) { /* ... */ }
}
```

### Phòng ngừa
- [ ] `readOnly = true` for all read operations
- [ ] Class-level `@Transactional(readOnly = true)` for read services
- Tool: Spring `@Transactional`

---

## Pattern 07: Spring Boot Startup Chậm

### Phân loại
Performance / Startup / Spring — MEDIUM 🟡

### Vấn đề
```
// Component scanning entire classpath
// Hibernate DDL auto-update on large schema
// Unnecessary auto-configurations loaded
// Startup: 30+ seconds
```

### Phát hiện
```bash
rg "spring.jpa.hibernate.ddl-auto" -n --glob "application*.yml"
rg --type java "@ComponentScan" -n
rg --type java "@SpringBootApplication" -n
```

### Giải pháp
```yaml
# application.yml:
spring:
  jpa:
    hibernate:
      ddl-auto: none          # Use Flyway/Liquibase instead
    defer-datasource-initialization: false
    open-in-view: false
  autoconfigure:
    exclude:
      - org.springframework.boot.autoconfigure.mail.MailAutoConfiguration
      # Exclude unused auto-configs
```

```java
// Lazy bean initialization (dev only):
// spring.main.lazy-initialization=true

// AOT processing (Spring Boot 3.x):
// ./mvnw spring-boot:build-image -Pnative
```

### Phòng ngừa
- [ ] `ddl-auto: none` + Flyway/Liquibase in production
- [ ] Exclude unused auto-configurations
- [ ] Lazy init for development
- Tool: Spring AOT, GraalVM Native Image, Flyway
