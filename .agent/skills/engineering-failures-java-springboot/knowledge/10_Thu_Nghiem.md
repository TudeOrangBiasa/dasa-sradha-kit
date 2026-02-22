# Domain 10: Thử Nghiệm (Testing)

> Java/Spring Boot patterns: JUnit 5, Mockito, Testcontainers, test slicing, @SpringBootTest.

---

## Pattern 01: @SpringBootTest Quá Nặng

### Phân loại
Testing / Spring / Performance — HIGH 🟠

### Vấn đề
```java
@SpringBootTest // Loads ENTIRE application context for every test class!
class UserServiceTest {
    @Test
    void testFindById() { /* Only tests service logic */ }
}
// 50 test classes × full context load = 10+ minute test suite
```

### Phát hiện
```bash
rg --type java "@SpringBootTest" -n
rg --type java "@DataJpaTest|@WebMvcTest|@JsonTest" -n
```

### Giải pháp
```java
// Unit test (no Spring context):
@ExtendWith(MockitoExtension.class)
class UserServiceTest {
    @Mock UserRepository userRepo;
    @InjectMocks UserService userService;

    @Test
    void findById_returnsUser() {
        when(userRepo.findById(1L)).thenReturn(Optional.of(new User("test")));
        var user = userService.findById(1L);
        assertThat(user.getName()).isEqualTo("test");
    }
}

// Test slicing (only loads relevant beans):
@WebMvcTest(UserController.class)     // Controller layer only
@DataJpaTest                          // JPA layer only
@WebFluxTest                          // WebFlux layer only
```

### Phòng ngừa
- [ ] Unit tests with Mockito (no Spring)
- [ ] Test slicing (`@WebMvcTest`, `@DataJpaTest`)
- [ ] `@SpringBootTest` only for integration tests
- Tool: JUnit 5, Mockito, Spring Test Slicing

---

## Pattern 02: @MockBean Lạm Dụng

### Phân loại
Testing / Spring / Context Cache — HIGH 🟠

### Vấn đề
```java
@SpringBootTest
class OrderServiceTest {
    @MockBean UserService userService;     // New context!
    @MockBean PaymentService paymentService; // Different combo → another context
}
// Each unique @MockBean combination creates a NEW application context
// 20 test classes with different mocks = 20 context loads
```

### Phát hiện
```bash
rg --type java "@MockBean" -n
rg --type java "@MockBean" -l | wc -l
```

### Giải pháp
```java
// Option 1: Use @Mock instead (no Spring context needed)
@ExtendWith(MockitoExtension.class)
class OrderServiceTest {
    @Mock UserService userService;
    @InjectMocks OrderService orderService;
}

// Option 2: Shared test configuration
@TestConfiguration
public class SharedMockConfig {
    @Bean @Primary
    public PaymentService paymentService() { return mock(PaymentService.class); }
}

// Option 3: @MockitoBean (Spring Boot 3.4+) with consistent set
```

### Phòng ngừa
- [ ] `@Mock` over `@MockBean` when possible
- [ ] Shared `@TestConfiguration` for common mocks
- [ ] Consistent mock sets across test classes
- Tool: Mockito, Spring Test

---

## Pattern 03: Test Database Không Isolate

### Phân loại
Testing / Database / Isolation — HIGH 🟠

### Vấn đề
```java
@SpringBootTest
class UserServiceTest {
    @Test void test1() { userRepo.save(new User("alice")); }
    @Test void test2() { assertEquals(0, userRepo.count()); } // FAILS: alice exists!
}
// Tests depend on execution order → flaky
```

### Phát hiện
```bash
rg --type java "@Sql|@DirtiesContext|@Transactional" -n --glob "*Test*"
rg --type java "deleteAll\\(\\)" -n --glob "*Test*"
```

### Giải pháp
```java
// Option 1: @Transactional (auto-rollback after each test)
@DataJpaTest // Already @Transactional
class UserRepositoryTest {
    @Test void test1() { userRepo.save(new User("alice")); } // Rolled back
    @Test void test2() { assertEquals(0, userRepo.count()); } // Clean state
}

// Option 2: Testcontainers (real DB, fresh per class)
@SpringBootTest
@Testcontainers
class UserServiceIT {
    @Container
    static PostgreSQLContainer<?> pg = new PostgreSQLContainer<>("postgres:16");

    @DynamicPropertySource
    static void props(DynamicPropertyRegistry r) {
        r.add("spring.datasource.url", pg::getJdbcUrl);
        r.add("spring.datasource.username", pg::getUsername);
        r.add("spring.datasource.password", pg::getPassword);
    }
}
```

### Phòng ngừa
- [ ] `@Transactional` on test classes for auto-rollback
- [ ] Testcontainers for integration tests
- [ ] Never depend on test execution order
- Tool: Testcontainers, @DataJpaTest

---

## Pattern 04: Mock Verify Quá Strict

### Phân loại
Testing / Mockito / Brittle — MEDIUM 🟡

### Vấn đề
```java
@Test
void createOrder() {
    orderService.createOrder(req);
    verify(orderRepo).save(any(Order.class));
    verify(eventPublisher).publishEvent(any()); // Brittle!
    verify(auditLog).log(any());                // Implementation detail
    verifyNoMoreInteractions(orderRepo, eventPublisher, auditLog); // Over-specified
}
// Any refactoring breaks test even if behavior is correct
```

### Phát hiện
```bash
rg --type java "verifyNoMoreInteractions|verify\\(" -n --glob "*Test*"
rg --type java "verify.*times\\(" -n --glob "*Test*"
```

### Giải pháp
```java
@Test
void createOrder_savesAndReturns() {
    when(orderRepo.save(any())).thenReturn(savedOrder);
    Order result = orderService.createOrder(req);
    assertThat(result.getStatus()).isEqualTo("CREATED"); // Test behavior
    verify(orderRepo).save(argThat(o -> o.getTotal().equals(req.total())));
    // Only verify essential interactions
}
```

### Phòng ngừa
- [ ] Assert output/behavior, not implementation
- [ ] Verify only essential interactions
- [ ] Avoid `verifyNoMoreInteractions`
- Tool: AssertJ, Mockito

---

## Pattern 05: H2 vs Production DB Khác Biệt

### Phân loại
Testing / Database / Compatibility — HIGH 🟠

### Vấn đề
```java
// Test uses H2 in-memory, production uses PostgreSQL
// H2 doesn't support: JSON columns, window functions, array types, JSONB
// Tests pass on H2 but fail on PostgreSQL
```

### Phát hiện
```bash
rg "h2" -n --glob "application-test*.yml" --glob "pom.xml"
rg --type java "nativeQuery.*true" -n
rg --type java "@Column.*columnDefinition" -n
```

### Giải pháp
```java
// Use Testcontainers with real database:
@SpringBootTest
@Testcontainers
class OrderRepositoryIT {
    @Container
    static PostgreSQLContainer<?> db = new PostgreSQLContainer<>("postgres:16");

    @DynamicPropertySource
    static void props(DynamicPropertyRegistry r) {
        r.add("spring.datasource.url", db::getJdbcUrl);
    }

    @Test
    void nativeQueryWorks() {
        // Tests against real PostgreSQL, not H2
    }
}
```

### Phòng ngừa
- [ ] Testcontainers for DB-specific features
- [ ] H2 only for simple JPQL tests
- [ ] Same DB engine in test and production
- Tool: Testcontainers PostgreSQL/MySQL

---

## Pattern 06: Test Coverage Chỉ Happy Path

### Phân loại
Testing / Coverage / Edge Cases — MEDIUM 🟡

### Vấn đề
```java
@Test
void createUser_success() {
    var user = userService.create(validRequest);
    assertNotNull(user);
}
// No tests for: null input, duplicate email, DB failure, validation error
```

### Phát hiện
```bash
rg --type java "@Test" -n | wc -l
rg --type java "assertThrows|assertThatThrownBy" -n --glob "*Test*"
```

### Giải pháp
```java
@Nested
class CreateUser {
    @Test void success() { /* happy path */ }

    @Test void duplicateEmail_throwsConflict() {
        when(userRepo.existsByEmail("a@b.com")).thenReturn(true);
        assertThatThrownBy(() -> userService.create(req))
            .isInstanceOf(DuplicateEmailException.class);
    }

    @Test void nullName_throwsValidation() {
        assertThatThrownBy(() -> userService.create(invalidReq))
            .isInstanceOf(ConstraintViolationException.class);
    }

    @ParameterizedTest
    @NullAndEmptySource @ValueSource(strings = {"invalid-email", " "})
    void invalidEmail_rejected(String email) {
        assertThatThrownBy(() -> userService.create(new Req(email)))
            .isInstanceOf(ValidationException.class);
    }
}
```

### Phòng ngừa
- [ ] `@Nested` to group test cases
- [ ] `@ParameterizedTest` for edge cases
- [ ] Test error paths, not just happy path
- Tool: JUnit 5 `@Nested`, `@ParameterizedTest`, JaCoCo

---

## Pattern 07: WebMvcTest Thiếu Security

### Phân loại
Testing / Controller / Security — HIGH 🟠

### Vấn đề
```java
@WebMvcTest(UserController.class)
class UserControllerTest {
    @Test
    void getUser_returns200() {
        mockMvc.perform(get("/api/users/1"))
            .andExpect(status().isOk()); // Fails: 401 Unauthorized!
    }
}
// Spring Security auto-configured but no authentication in test
```

### Phát hiện
```bash
rg --type java "@WebMvcTest" -n
rg --type java "@WithMockUser|SecurityMockMvc" -n --glob "*Test*"
```

### Giải pháp
```java
@WebMvcTest(UserController.class)
class UserControllerTest {
    @Autowired MockMvc mockMvc;
    @MockBean UserService userService;

    @Test
    @WithMockUser(roles = "USER")
    void getUser_authenticated_returns200() {
        when(userService.findById(1L)).thenReturn(new UserDto("test"));
        mockMvc.perform(get("/api/users/1"))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.name").value("test"));
    }

    @Test
    void getUser_unauthenticated_returns401() {
        mockMvc.perform(get("/api/users/1"))
            .andExpect(status().isUnauthorized());
    }
}
```

### Phòng ngừa
- [ ] `@WithMockUser` for authenticated tests
- [ ] Test both authenticated and unauthenticated
- [ ] `@WithMockUser(roles=...)` for role-based tests
- Tool: Spring Security Test, `@WithMockUser`
