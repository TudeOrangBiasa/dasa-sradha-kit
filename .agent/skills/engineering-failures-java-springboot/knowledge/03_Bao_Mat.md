# Domain 03: Bảo Mật (Security)

> Java/Spring Boot patterns: SQL injection, XSS, CSRF, authentication, secrets, SSRF.

---

## Pattern 01: SQL Injection

### Phân loại
Security / Injection / SQL — CRITICAL 🔴

### Vấn đề
```java
String sql = "SELECT * FROM users WHERE name = '" + name + "'";
jdbcTemplate.queryForList(sql);
// name = "'; DROP TABLE users; --" → SQL injection
```

### Phát hiện
```bash
rg --type java "\"SELECT.*\+|\"INSERT.*\+|\"UPDATE.*\+|\"DELETE.*\+" -n
rg --type java "createNativeQuery\(.*\+" -n
rg --type java "nativeQuery.*true" -n
```

### Giải pháp
```java
// GOOD: Parameterized query
jdbcTemplate.queryForList("SELECT * FROM users WHERE name = ?", name);

// GOOD: JPA named parameters
@Query("SELECT u FROM User u WHERE u.name = :name")
List<User> findByName(@Param("name") String name);

// GOOD: Criteria API
cb.equal(root.get("name"), name);
```

### Phòng ngừa
- [ ] Never concatenate user input into SQL
- [ ] Parameterized queries or JPA
- [ ] `@Query` with named parameters
- Tool: SpotBugs `SQL_INJECTION`, SonarQube

---

## Pattern 02: XSS (Cross-Site Scripting)

### Phân loại
Security / XSS / Output — HIGH 🟠

### Vấn đề
```java
@GetMapping("/search")
public String search(@RequestParam String q, Model model) {
    model.addAttribute("query", q); // Unescaped in Thymeleaf template
    return "search";
}
// Template: <p th:utext="${query}"></p>  ← utext = unescaped!
```

### Phát hiện
```bash
rg "th:utext" -n --glob "*.html"
rg --type java "HttpServletResponse.*getWriter\(\).*write\(" -n
rg --type java "ResponseEntity.*body\(.*request\.getParameter" -n
```

### Giải pháp
```html
<!-- GOOD: th:text escapes automatically -->
<p th:text="${query}"></p>

<!-- If HTML needed, sanitize first: -->
```

```java
// Sanitize HTML input:
import org.owasp.html.PolicyFactory;
import org.owasp.html.Sanitizers;
PolicyFactory policy = Sanitizers.FORMATTING.and(Sanitizers.LINKS);
String safe = policy.sanitize(userInput);
```

### Phòng ngừa
- [ ] `th:text` (not `th:utext`) in Thymeleaf
- [ ] OWASP Java HTML Sanitizer for HTML input
- [ ] Content-Security-Policy headers
- Tool: OWASP HTML Sanitizer, CSP

---

## Pattern 03: Hardcoded Secrets

### Phân loại
Security / Secrets / Configuration — CRITICAL 🔴

### Vấn đề
```yaml
# application.yml:
spring:
  datasource:
    password: MyS3cr3tP@ssw0rd  # Committed to git!
jwt:
  secret: myJwtSecretKey123      # Hardcoded!
```

### Phát hiện
```bash
rg "password|secret|api[_-]?key|token" -n --glob "application*.yml" --glob "application*.properties"
rg --type java "\"(sk-|api_key|password|secret)" -n
```

### Giải pháp
```yaml
# application.yml:
spring:
  datasource:
    password: ${DB_PASSWORD}  # From environment variable
jwt:
  secret: ${JWT_SECRET}
```

```java
// Or use Spring Vault:
@Value("${vault.db.password}")
private String dbPassword;

// Or K8s secrets mounted as env vars
```

### Phòng ngừa
- [ ] Environment variables for secrets
- [ ] Never commit secrets to git
- [ ] `.gitignore` includes `application-local.yml`
- Tool: `git-secrets`, Spring Vault, AWS Secrets Manager

---

## Pattern 04: CSRF Protection Disabled

### Phân loại
Security / CSRF / Spring Security — HIGH 🟠

### Vấn đề
```java
@Bean
public SecurityFilterChain securityFilterChain(HttpSecurity http) throws Exception {
    http.csrf(csrf -> csrf.disable()); // Disabled for ALL endpoints!
    return http.build();
}
```

### Phát hiện
```bash
rg --type java "csrf.*disable|csrf\(\)\.disable" -n
rg --type java "CsrfConfigurer" -n
```

### Giải pháp
```java
@Bean
public SecurityFilterChain securityFilterChain(HttpSecurity http) throws Exception {
    http.csrf(csrf -> csrf
        .csrfTokenRepository(CookieCsrfTokenRepository.withHttpOnlyFalse())
        .ignoringRequestMatchers("/api/**") // Only disable for stateless API
    );
    return http.build();
}

// For pure REST API with JWT (stateless) — CSRF disable is OK:
http.csrf(AbstractHttpConfigurer::disable)
    .sessionManagement(s -> s.sessionCreationPolicy(STATELESS));
```

### Phòng ngừa
- [ ] CSRF enabled for session-based auth
- [ ] Disable only for stateless JWT APIs
- [ ] `CookieCsrfTokenRepository` for SPA
- Tool: Spring Security, OWASP ZAP

---

## Pattern 05: Insecure Deserialization

### Phân loại
Security / Deserialization / RCE — CRITICAL 🔴

### Vấn đề
```java
ObjectInputStream ois = new ObjectInputStream(untrustedInput);
Object obj = ois.readObject(); // Remote Code Execution!
// Attacker sends crafted serialized object → arbitrary code execution
```

### Phát hiện
```bash
rg --type java "ObjectInputStream|readObject\(\)|readUnshared\(\)" -n
rg --type java "Serializable" -n
rg --type java "enableDefaultTyping|@JsonTypeInfo" -n
```

### Giải pháp
```java
// NEVER deserialize untrusted Java objects
// Use JSON (Jackson) instead:
ObjectMapper mapper = new ObjectMapper();
mapper.activateDefaultTyping(/* NEVER with untrusted input */);

// If Java serialization needed, use filter:
ObjectInputFilter filter = ObjectInputFilter.Config
    .createFilter("com.myapp.*;!*");
ois.setObjectInputFilter(filter);
```

### Phòng ngừa
- [ ] JSON over Java serialization
- [ ] `ObjectInputFilter` if serialization required
- [ ] No `enableDefaultTyping()` in Jackson
- Tool: SpotBugs, OWASP Dependency-Check

---

## Pattern 06: SSRF (Server-Side Request Forgery)

### Phân loại
Security / SSRF / Network — HIGH 🟠

### Vấn đề
```java
@GetMapping("/fetch")
public String fetch(@RequestParam String url) {
    return restTemplate.getForObject(url, String.class);
    // url = "http://169.254.169.254/latest/meta-data/" → AWS metadata exposed!
}
```

### Phát hiện
```bash
rg --type java "getForObject\(.*@RequestParam|exchange\(.*@RequestParam" -n
rg --type java "new URL\(.*request\.|URI\.create\(.*request\." -n
```

### Giải pháp
```java
private static final Set<String> ALLOWED_HOSTS = Set.of("api.example.com", "cdn.example.com");

@GetMapping("/fetch")
public String fetch(@RequestParam String url) {
    URI uri = URI.create(url);
    if (!ALLOWED_HOSTS.contains(uri.getHost())) {
        throw new ForbiddenException("Host not allowed");
    }
    // Also block internal IPs:
    InetAddress addr = InetAddress.getByName(uri.getHost());
    if (addr.isLoopbackAddress() || addr.isSiteLocalAddress()) {
        throw new ForbiddenException("Internal addresses not allowed");
    }
    return restClient.get().uri(uri).retrieve().body(String.class);
}
```

### Phòng ngừa
- [ ] Allowlist of permitted hosts
- [ ] Block internal/private IPs
- [ ] No user-controlled URLs to internal services
- Tool: OWASP ZAP, network policies

---

## Pattern 07: Missing Authorization Check

### Phân loại
Security / Authorization / IDOR — HIGH 🟠

### Vấn đề
```java
@GetMapping("/users/{id}/orders")
public List<Order> getUserOrders(@PathVariable Long id) {
    return orderRepository.findByUserId(id);
    // Any authenticated user can view ANY user's orders!
}
```

### Phát hiện
```bash
rg --type java "@GetMapping|@PostMapping|@PutMapping|@DeleteMapping" -A 5 | rg -v "@PreAuthorize|SecurityContext|principal"
rg --type java "findBy.*Id\(@PathVariable" -n
```

### Giải pháp
```java
@GetMapping("/users/{id}/orders")
@PreAuthorize("#id == authentication.principal.id or hasRole('ADMIN')")
public List<Order> getUserOrders(@PathVariable Long id) {
    return orderRepository.findByUserId(id);
}

// Or check in service:
public List<Order> getUserOrders(Long userId, UserPrincipal currentUser) {
    if (!userId.equals(currentUser.getId()) && !currentUser.isAdmin()) {
        throw new AccessDeniedException("Not authorized");
    }
    return orderRepository.findByUserId(userId);
}
```

### Phòng ngừa
- [ ] `@PreAuthorize` on all endpoints
- [ ] IDOR check: current user owns resource
- [ ] Method-level security enabled
- Tool: Spring Security `@PreAuthorize`, `@Secured`
