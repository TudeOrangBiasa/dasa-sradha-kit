# Domain 09: Thiết Kế API (API Design)

> Java/Spring Boot patterns: REST conventions, validation, versioning, pagination, OpenAPI, HATEOAS.

---

## Pattern 01: Validation Thiếu (@Valid)

### Phân loại
API / Validation / Input — HIGH 🟠

### Vấn đề
```java
@PostMapping("/users")
public User createUser(@RequestBody UserRequest req) {
    // No validation! req.email could be null, empty, or "not-an-email"
    return userService.create(req);
}
```

### Phát hiện
```bash
rg --type java "@RequestBody" -n | rg -v "@Valid"
rg --type java "@PostMapping|@PutMapping" -A 3 | rg "@RequestBody" | rg -v "@Valid"
```

### Giải pháp
```java
public record UserRequest(
    @NotBlank @Size(max = 100) String name,
    @NotBlank @Email String email,
    @NotNull @Min(0) @Max(150) Integer age
) {}

@PostMapping("/users")
public User createUser(@Valid @RequestBody UserRequest req) {
    return userService.create(req); // Auto-validated, 400 on failure
}
```

### Phòng ngừa
- [ ] `@Valid` on all `@RequestBody` params
- [ ] Jakarta Bean Validation annotations on DTOs
- [ ] `@RestControllerAdvice` for validation error formatting
- Tool: Jakarta Validation, Spring Validation

---

## Pattern 02: REST Convention Sai

### Phân loại
API / REST / Convention — MEDIUM 🟡

### Vấn đề
```java
@PostMapping("/getUsers")        // POST for read? "get" in URL?
@GetMapping("/user/delete/{id}") // GET for delete?
@PostMapping("/updateUser")      // Verb in URL
```

### Phát hiện
```bash
rg --type java "@GetMapping|@PostMapping|@PutMapping|@DeleteMapping" -n
rg --type java "Mapping.*get|Mapping.*delete|Mapping.*update|Mapping.*create" -n
```

### Giải pháp
```java
@RestController
@RequestMapping("/api/v1/users")
public class UserController {
    @GetMapping            public Page<UserDto> list(Pageable p) {}
    @GetMapping("/{id}")   public UserDto get(@PathVariable Long id) {}
    @PostMapping           public UserDto create(@Valid @RequestBody CreateReq r) {}
    @PutMapping("/{id}")   public UserDto update(@PathVariable Long id, @Valid @RequestBody UpdateReq r) {}
    @DeleteMapping("/{id}") @ResponseStatus(NO_CONTENT) public void delete(@PathVariable Long id) {}
}
```

### Phòng ngừa
- [ ] Nouns for resources, HTTP verbs for actions
- [ ] Plural resource names (`/users` not `/user`)
- [ ] Consistent URL patterns across all controllers
- Tool: OpenAPI spec validation

---

## Pattern 03: Response Format Không Nhất Quán

### Phân loại
API / Response / Contract — MEDIUM 🟡

### Vấn đề
```java
// Different endpoints return different shapes:
@GetMapping("/users") List<User> getUsers();           // Array
@GetMapping("/orders") Map<String, Object> getOrders(); // Object with random keys
@GetMapping("/products") ResponseEntity<?> getProducts(); // Unknown type
```

### Phát hiện
```bash
rg --type java "ResponseEntity<|List<|Map<String" -n --glob "*Controller*"
```

### Giải pháp
```java
// Consistent wrapper:
public record ApiResponse<T>(T data, PageMeta meta) {
    public static <T> ApiResponse<T> of(T data) {
        return new ApiResponse<>(data, null);
    }
    public static <T> ApiResponse<List<T>> ofPage(Page<T> page) {
        return new ApiResponse<>(page.getContent(),
            new PageMeta(page.getNumber(), page.getSize(), page.getTotalElements()));
    }
}
record PageMeta(int page, int size, long total) {}

@GetMapping("/users")
public ApiResponse<List<UserDto>> getUsers(Pageable pageable) {
    return ApiResponse.ofPage(userService.findAll(pageable));
}
```

### Phòng ngừa
- [ ] Standard response wrapper for all endpoints
- [ ] Consistent pagination metadata
- [ ] OpenAPI spec documents response shapes
- Tool: OpenAPI Generator, Springdoc

---

## Pattern 04: API Versioning Thiếu

### Phân loại
API / Versioning / Breaking Change — HIGH 🟠

### Vấn đề
```java
// Breaking change: renamed field "name" → "fullName"
// All clients break instantly, no migration path
@GetMapping("/users/{id}")
public UserDto getUser(@PathVariable Long id) {
    return new UserDto(user.getFullName()); // Was user.getName()
}
```

### Phát hiện
```bash
rg --type java "@RequestMapping.*/api/v" -n
rg --type java "@RequestMapping" -n --glob "*Controller*"
```

### Giải pháp
```java
// URL versioning (most common in Spring Boot):
@RestController
@RequestMapping("/api/v1/users")
public class UserControllerV1 { /* original */ }

@RestController
@RequestMapping("/api/v2/users")
public class UserControllerV2 { /* new version with breaking changes */ }

// Or header versioning:
@GetMapping(value = "/users", headers = "X-API-Version=2")
public UserDtoV2 getUsersV2() { /* ... */ }
```

### Phòng ngừa
- [ ] Version prefix in all API URLs (`/api/v1/`)
- [ ] Additive changes (new fields) don't need new version
- [ ] Deprecation period before removing old versions
- Tool: Springdoc OpenAPI, API versioning strategy

---

## Pattern 05: Pagination Response Thiếu Metadata

### Phân loại
API / Pagination / UX — MEDIUM 🟡

### Vấn đề
```java
@GetMapping("/orders")
public List<Order> getOrders(@RequestParam int page) {
    return orderRepo.findAll(PageRequest.of(page, 20)).getContent();
    // Client doesn't know: total pages, total elements, has next page?
}
```

### Phát hiện
```bash
rg --type java "getContent\\(\\)" -n --glob "*Controller*"
rg --type java "Page<" -n --glob "*Controller*"
```

### Giải pháp
```java
@GetMapping("/orders")
public ResponseEntity<PageResponse<OrderDto>> getOrders(
    @RequestParam(defaultValue = "0") int page,
    @RequestParam(defaultValue = "20") int size) {
    Page<OrderDto> result = orderService.findAll(PageRequest.of(page, size));
    return ResponseEntity.ok(PageResponse.of(result));
}

record PageResponse<T>(List<T> content, int page, int size,
    long totalElements, int totalPages, boolean hasNext) {
    static <T> PageResponse<T> of(Page<T> p) {
        return new PageResponse<>(p.getContent(), p.getNumber(), p.getSize(),
            p.getTotalElements(), p.getTotalPages(), p.hasNext());
    }
}
```

### Phòng ngừa
- [ ] Always include pagination metadata
- [ ] Use Spring `Page<T>` or custom wrapper
- [ ] Max page size to prevent abuse
- Tool: Spring Data Pageable

---

## Pattern 06: OpenAPI Spec Không Sync

### Phân loại
API / Documentation / Contract — HIGH 🟠

### Vấn đề
```java
// Code has new field "priority" but OpenAPI spec doesn't mention it
// Or spec says field is required but code accepts null
// Clients built from spec get unexpected responses
```

### Phát hiện
```bash
rg --type java "@Schema|@Operation|@ApiResponse" -n
rg "springdoc|swagger" -n --glob "pom.xml" --glob "build.gradle*"
```

### Giải pháp
```java
// Auto-generate from code with Springdoc:
// pom.xml: springdoc-openapi-starter-webmvc-ui

@Operation(summary = "Create user", description = "Creates a new user account")
@ApiResponse(responseCode = "201", description = "User created")
@ApiResponse(responseCode = "400", description = "Validation error")
@PostMapping
public ResponseEntity<UserDto> createUser(@Valid @RequestBody CreateUserRequest req) {
    return ResponseEntity.status(HttpStatus.CREATED).body(userService.create(req));
}

// Access: http://localhost:8080/swagger-ui.html
// JSON:   http://localhost:8080/v3/api-docs
```

### Phòng ngừa
- [ ] Springdoc auto-generates from code (always in sync)
- [ ] `@Operation`, `@Schema` annotations for clarity
- [ ] CI: validate OpenAPI spec on build
- Tool: Springdoc OpenAPI, OpenAPI Generator

---

## Pattern 07: Rate Limiting Thiếu

### Phân loại
API / Security / DoS — HIGH 🟠

### Vấn đề
```java
@PostMapping("/login")
public Token login(@RequestBody LoginRequest req) {
    return authService.login(req); // No rate limit → brute force attack!
}
// Or: expensive endpoint with no throttling → single client can DoS
```

### Phát hiện
```bash
rg --type java "RateLimiter|Bucket4j|rate.limit" -n
rg "rate" -n --glob "application*.yml"
```

### Giải pháp
```java
// Using Bucket4j + Spring:
@Bean
public FilterRegistrationBean<RateLimitFilter> rateLimitFilter() {
    // 10 requests per minute per IP
}

// Or Spring Cloud Gateway rate limiter:
// Or simple annotation-based with AOP:
@RateLimit(requests = 10, period = 60) // Custom annotation
@PostMapping("/login")
public Token login(@RequestBody LoginRequest req) {
    return authService.login(req);
}

// Resilience4j RateLimiter:
@RateLimiter(name = "login")
public Token login(LoginRequest req) { /* ... */ }
```

### Phòng ngừa
- [ ] Rate limit on auth endpoints
- [ ] Per-IP or per-user throttling
- [ ] Return 429 Too Many Requests
- Tool: Bucket4j, Resilience4j, API Gateway
