# Domain 04: Dữ Liệu (Data)

> Java/Spring Boot patterns: JPA/Hibernate, transactions, serialization, validation, entity mapping.

---

## Pattern 01: N+1 Query Problem

### Phân loại
Data / JPA / Query — CRITICAL 🔴

### Vấn đề
```java
@Entity
public class Order {
    @OneToMany(mappedBy = "order", fetch = FetchType.LAZY)
    private List<OrderItem> items; // Each access triggers separate query
}
// orderRepository.findAll() → 1 query for orders + N queries for items
```

### Phát hiện
```bash
rg --type java "@OneToMany|@ManyToOne|@ManyToMany" -n
rg --type java "fetch\s*=\s*FetchType" -n
rg --type java "spring.jpa.show-sql" -n --glob "application*.yml"
```

### Giải pháp
```java
// GOOD: JOIN FETCH
@Query("SELECT o FROM Order o JOIN FETCH o.items WHERE o.status = :status")
List<Order> findByStatusWithItems(@Param("status") String status);

// GOOD: @EntityGraph
@EntityGraph(attributePaths = {"items", "items.product"})
List<Order> findByStatus(String status);

// GOOD: @BatchSize on collection
@OneToMany(mappedBy = "order")
@BatchSize(size = 20) // Fetches 20 collections at once
private List<OrderItem> items;
```

### Phòng ngừa
- [ ] `spring.jpa.show-sql=true` in dev to detect N+1
- [ ] `JOIN FETCH` or `@EntityGraph` for known associations
- [ ] `@BatchSize` as fallback
- Tool: Hibernate Statistics, p6spy

---

## Pattern 02: LazyInitializationException

### Phân loại
Data / JPA / Session — HIGH 🟠

### Vấn đề
```java
@Service
public class OrderService {
    public Order getOrder(Long id) {
        Order order = orderRepository.findById(id).orElseThrow();
        return order; // Session closed
    }
}
// Controller: order.getItems() → LazyInitializationException!
```

### Phát hiện
```bash
rg --type java "LazyInitializationException" -n
rg --type java "enable_lazy_load_no_trans" -n --glob "application*.yml"
rg --type java "FetchType.LAZY" -n
```

### Giải pháp
```java
// GOOD: Fetch in service with @Transactional(readOnly = true)
@Transactional(readOnly = true)
public OrderDto getOrder(Long id) {
    Order order = orderRepository.findById(id).orElseThrow();
    return OrderDto.from(order); // Map to DTO inside transaction
}

// GOOD: Use DTO projection
@Query("SELECT new com.app.dto.OrderSummary(o.id, o.status, SIZE(o.items)) FROM Order o")
List<OrderSummary> findOrderSummaries();

// BAD: open-in-view=true (anti-pattern, hides N+1)
// spring.jpa.open-in-view=false  ← recommended
```

### Phòng ngừa
- [ ] `spring.jpa.open-in-view=false`
- [ ] DTO projection or fetch in `@Transactional`
- [ ] Never expose entities directly to controllers
- Tool: Spring Data JPA, MapStruct

---

## Pattern 03: Transaction Propagation Sai

### Phân loại
Data / Transaction / Spring — CRITICAL 🔴

### Vấn đề
```java
@Service
public class OrderService {
    @Transactional
    public void createOrder(OrderRequest req) {
        save(req);
        notificationService.sendNotification(req); // If this fails → order rolled back!
    }
}
// Or: calling @Transactional method from same class (proxy bypass)
@Service
public class UserService {
    public void register(User user) {
        saveUser(user); // @Transactional IGNORED — same class call!
    }
    @Transactional
    public void saveUser(User user) { userRepo.save(user); }
}
```

### Phát hiện
```bash
rg --type java "@Transactional" -n
rg --type java "Propagation\." -n
rg --type java "this\.\w+\(" -n --glob "*Service*"
```

### Giải pháp
```java
// Separate non-critical operations:
@Transactional
public void createOrder(OrderRequest req) {
    save(req);
}

@TransactionalEventListener(phase = AFTER_COMMIT)
public void onOrderCreated(OrderCreatedEvent event) {
    notificationService.sendNotification(event); // Fails independently
}

// Self-invocation fix: inject self or use ApplicationContext
@Service
public class UserService {
    @Lazy @Autowired private UserService self;
    public void register(User user) {
        self.saveUser(user); // Goes through proxy → @Transactional works
    }
}
```

### Phòng ngừa
- [ ] `REQUIRES_NEW` for independent operations
- [ ] No self-invocation of `@Transactional` methods
- [ ] `@TransactionalEventListener` for post-commit actions
- Tool: Spring AOP, TransactionTemplate

---

## Pattern 04: Optimistic Locking Không Handle

### Phân loại
Data / JPA / Concurrency — HIGH 🟠

### Vấn đề
```java
@Entity
public class Product {
    @Version
    private Long version; // Optimistic locking enabled
}
// Two users edit same product → OptimisticLockException → 500 error
// No retry, no user-friendly message
```

### Phát hiện
```bash
rg --type java "@Version" -n
rg --type java "OptimisticLock|StaleObjectState" -n
rg --type java "LockModeType" -n
```

### Giải pháp
```java
// Handle in service with retry:
@Retryable(value = OptimisticLockingFailureException.class, maxAttempts = 3)
@Transactional
public Product updateProduct(Long id, UpdateRequest req) {
    Product product = productRepo.findById(id).orElseThrow();
    product.updateFrom(req);
    return productRepo.save(product);
}

// Or handle in @ControllerAdvice:
@ExceptionHandler(OptimisticLockingFailureException.class)
public ResponseEntity<ErrorResponse> handleConflict() {
    return ResponseEntity.status(HttpStatus.CONFLICT)
        .body(new ErrorResponse("Resource was modified by another user"));
}
```

### Phòng ngừa
- [ ] `@Version` on all mutable entities
- [ ] `@Retryable` or manual retry for concurrent updates
- [ ] Return 409 Conflict to clients
- Tool: Spring Retry, `@Version`

---

## Pattern 05: Cascade Type Sai

### Phân loại
Data / JPA / Mapping — HIGH 🟠

### Vấn đề
```java
@Entity
public class User {
    @OneToMany(cascade = CascadeType.ALL, orphanRemoval = true)
    private List<Order> orders;
}
// deleteUser(user) → deletes ALL orders! Data loss!
// Or: CascadeType.ALL on @ManyToOne → deleting child deletes parent
```

### Phát hiện
```bash
rg --type java "CascadeType\.(ALL|REMOVE)" -n
rg --type java "orphanRemoval" -n
rg --type java "cascade\s*=" -n
```

### Giải pháp
```java
// GOOD: Specific cascade types
@Entity
public class Order {
    @OneToMany(cascade = {CascadeType.PERSIST, CascadeType.MERGE}, mappedBy = "order")
    private List<OrderItem> items; // Only cascade save/update, not delete
}

// Separate delete logic:
@Transactional
public void deleteOrder(Long orderId) {
    orderItemRepo.deleteByOrderId(orderId); // Explicit delete children
    orderRepo.deleteById(orderId);
}
```

### Phòng ngừa
- [ ] Never `CascadeType.ALL` without careful analysis
- [ ] `PERSIST` + `MERGE` for parent-child
- [ ] Explicit delete for complex relationships
- Tool: Hibernate logging, DB foreign key constraints

---

## Pattern 06: Entity Equals/HashCode Sai

### Phân loại
Data / JPA / Entity — HIGH 🟠

### Vấn đề
```java
@Entity
public class User {
    @Id @GeneratedValue
    private Long id;
    // Default equals/hashCode → uses object identity
    // Set<User> breaks when entity detached and re-attached
    // Or: equals based on @Id → null before persist
}
```

### Phát hiện
```bash
rg --type java "@Entity" -l | xargs rg "equals|hashCode" -l
rg --type java "@Entity" -l | xargs rg -L "equals"
```

### Giải pháp
```java
@Entity
public class User {
    @Id @GeneratedValue
    private Long id;

    // GOOD: Use business key or UUID
    @Column(unique = true, updatable = false)
    private UUID uuid = UUID.randomUUID();

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (!(o instanceof User other)) return false;
        return uuid != null && uuid.equals(other.uuid);
    }

    @Override
    public int hashCode() {
        return uuid.hashCode();
    }
}
```

### Phòng ngừa
- [ ] Business key or UUID for equals/hashCode
- [ ] Never use `@Id` (generated) for equals
- [ ] Consistent across all entities
- Tool: Lombok `@EqualsAndHashCode(of = "uuid")`, Hibernate docs

---

## Pattern 07: Bulk Insert Chậm

### Phân loại
Data / JPA / Performance — HIGH 🟠

### Vấn đề
```java
for (int i = 0; i < 10_000; i++) {
    repository.save(new Item(i)); // 10,000 INSERT statements!
    // Each save: dirty check + flush + individual INSERT
}
```

### Phát hiện
```bash
rg --type java "\.save\(|\.saveAll\(" -n --glob "*Service*"
rg --type java "batch_size|batch-size" -n --glob "application*.yml"
rg --type java "for.*save\(" -n
```

### Giải pháp
```java
// application.yml:
// spring.jpa.properties.hibernate.jdbc.batch_size: 50
// spring.jpa.properties.hibernate.order_inserts: true

// GOOD: saveAll with batch_size configured
@Transactional
public void importItems(List<ItemRequest> requests) {
    List<Item> items = requests.stream().map(Item::from).toList();
    repository.saveAll(items); // Batched with configured batch_size
}

// BEST: JdbcTemplate for pure inserts
@Transactional
public void bulkInsert(List<Item> items) {
    jdbcTemplate.batchUpdate(
        "INSERT INTO items (name, price) VALUES (?, ?)",
        items, 1000, // batch size
        (ps, item) -> {
            ps.setString(1, item.getName());
            ps.setBigDecimal(2, item.getPrice());
        });
}
```

### Phòng ngừa
- [ ] Configure `hibernate.jdbc.batch_size`
- [ ] `saveAll()` over loop `save()`
- [ ] `JdbcTemplate.batchUpdate()` for high-volume inserts
- Tool: Hibernate batch config, JdbcTemplate
