# Domain 02: Đồng Thời (Concurrency)

> Java/Spring Boot patterns: thread safety, deadlock, race conditions, virtual threads, synchronized.

---

## Pattern 01: Singleton Bean Mutable State

### Phân loại
Concurrency / Spring / Thread Safety — CRITICAL 🔴

### Vấn đề
```java
@Service // Singleton by default
public class OrderService {
    private int orderCount = 0; // Shared mutable state!
    public void createOrder() { orderCount++; } // Race condition
}
```

### Phát hiện
```bash
rg --type java "@Service|@Component|@Repository" -A 10 | rg "private.*= (0|new |null)"
rg --type java "private.*int|private.*List|private.*Map" -n --glob "*Service*"
```

### Giải pháp
```java
@Service
public class OrderService {
    private final AtomicInteger orderCount = new AtomicInteger(0); // Thread-safe
    public void createOrder() { orderCount.incrementAndGet(); }
}

// Or use stateless design (preferred):
@Service
public class OrderService {
    private final OrderRepository orderRepository; // Injected, immutable
    public Order createOrder(OrderRequest req) {
        return orderRepository.save(new Order(req)); // No shared state
    }
}
```

### Phòng ngừa
- [ ] No mutable instance fields in Spring beans
- [ ] `final` on all injected dependencies
- [ ] `AtomicXxx` for counters
- Tool: SpotBugs `IS2_INCONSISTENT_SYNC`

---

## Pattern 02: Synchronized Quá Rộng

### Phân loại
Concurrency / Lock / Performance — HIGH 🟠

### Vấn đề
```java
public synchronized Map<String, Object> processAll(List<Item> items) {
    // Entire method synchronized → only 1 thread at a time
    // 100ms DB call × 1000 requests = bottleneck
    return items.stream().map(this::process).collect(toMap(...));
}
```

### Phát hiện
```bash
rg --type java "synchronized" -n
rg --type java "ReentrantLock|Lock\." -n
```

### Giải pháp
```java
// Narrow the critical section:
private final ConcurrentHashMap<String, Object> cache = new ConcurrentHashMap<>();

public Object getOrCompute(String key) {
    return cache.computeIfAbsent(key, k -> expensiveCompute(k)); // Only locks per-key
}

// Or use lock-free structures:
private final AtomicReference<Config> config = new AtomicReference<>(loadConfig());
public Config getConfig() { return config.get(); }
public void reload() { config.set(loadConfig()); }
```

### Phòng ngừa
- [ ] `ConcurrentHashMap` over `synchronized Map`
- [ ] Minimize synchronized scope
- [ ] Lock-free atomics when possible
- Tool: `jconsole`, thread dump analysis

---

## Pattern 03: Deadlock

### Phân loại
Concurrency / Deadlock / Lock Order — CRITICAL 🔴

### Vấn đề
```java
// Thread 1: lock(A) → lock(B)
// Thread 2: lock(B) → lock(A)
// → Deadlock!
synchronized(accountA) {
    synchronized(accountB) { transfer(accountA, accountB, amount); }
}
```

### Phát hiện
```bash
rg --type java "synchronized\(" -n
rg --type java "\.lock\(\)" -n
```

### Giải pháp
```java
// Consistent lock ordering:
public void transfer(Account from, Account to, BigDecimal amount) {
    Account first = from.getId() < to.getId() ? from : to;
    Account second = from.getId() < to.getId() ? to : from;
    synchronized (first) {
        synchronized (second) {
            from.debit(amount);
            to.credit(amount);
        }
    }
}

// Or use database-level locking:
@Transactional
public void transfer(Long fromId, Long toId, BigDecimal amount) {
    Account from = accountRepo.findByIdForUpdate(fromId); // SELECT FOR UPDATE
    Account to = accountRepo.findByIdForUpdate(toId);
    // DB handles lock ordering
}
```

### Phòng ngừa
- [ ] Consistent lock ordering
- [ ] Database locks over in-memory locks
- [ ] `tryLock()` with timeout
- Tool: Thread dumps, `jstack`, VisualVM

---

## Pattern 04: Virtual Threads Misuse (Java 21+)

### Phân loại
Concurrency / Virtual Threads / Java 21 — HIGH 🟠

### Vấn đề
```java
// Virtual threads pinned to carrier thread:
synchronized(lock) {
    dbCall(); // Blocks carrier thread — defeats purpose of virtual threads!
}

// Or: Using thread-local with virtual threads (millions of threads = millions of copies)
```

### Phát hiện
```bash
rg --type java "Thread\.ofVirtual|Executors\.newVirtualThread" -n
rg --type java "synchronized" -n | rg -v "test|Test"
rg --type java "ThreadLocal" -n
```

### Giải pháp
```java
// Use ReentrantLock instead of synchronized (avoids pinning):
private final ReentrantLock lock = new ReentrantLock();
public void process() {
    lock.lock();
    try { dbCall(); } // Virtual thread can unmount during blocking I/O
    finally { lock.unlock(); }
}

// Spring Boot 3.2+: Enable virtual threads
// application.yml:
// spring.threads.virtual.enabled: true

// Avoid ThreadLocal — use scoped values (Java 21 preview):
// ScopedValue<UserContext> CONTEXT = ScopedValue.newInstance();
```

### Phòng ngừa
- [ ] `ReentrantLock` over `synchronized` with virtual threads
- [ ] Avoid `ThreadLocal` with virtual threads
- [ ] `-Djdk.tracePinnedThreads=full` to detect pinning
- Tool: JFR, `-Djdk.tracePinnedThreads`

---

## Pattern 05: @Async Without Proper Executor

### Phân loại
Concurrency / Spring / Thread Pool — HIGH 🟠

### Vấn đề
```java
@Async
public void sendEmail(String to, String body) { /* ... */ }
// Default: SimpleAsyncTaskExecutor → creates NEW thread per call!
// Under load: thousands of threads → OOM
```

### Phát hiện
```bash
rg --type java "@Async" -n
rg --type java "TaskExecutor|ThreadPoolTaskExecutor" -n
rg --type java "@EnableAsync" -n
```

### Giải pháp
```java
@Configuration
@EnableAsync
public class AsyncConfig {
    @Bean("taskExecutor")
    public Executor taskExecutor() {
        ThreadPoolTaskExecutor executor = new ThreadPoolTaskExecutor();
        executor.setCorePoolSize(5);
        executor.setMaxPoolSize(20);
        executor.setQueueCapacity(100);
        executor.setThreadNamePrefix("async-");
        executor.setRejectedExecutionHandler(new CallerRunsPolicy());
        executor.initialize();
        return executor;
    }
}

@Async("taskExecutor") // Specify which executor
public CompletableFuture<Void> sendEmail(String to, String body) {
    // ...
    return CompletableFuture.completedFuture(null);
}
```

### Phòng ngừa
- [ ] Custom `ThreadPoolTaskExecutor` configured
- [ ] Named executor beans
- [ ] `CallerRunsPolicy` for backpressure
- Tool: Spring `@Async`, Micrometer thread pool metrics

---

## Pattern 06: CompletableFuture Exception Swallowed

### Phân loại
Concurrency / Async / Error Handling — HIGH 🟠

### Vấn đề
```java
CompletableFuture.supplyAsync(() -> riskyOperation());
// Exception thrown → silently swallowed, no logging, no notification
```

### Phát hiện
```bash
rg --type java "CompletableFuture\." -n | rg -v "exceptionally|handle|whenComplete"
rg --type java "supplyAsync|runAsync" -n
```

### Giải pháp
```java
CompletableFuture.supplyAsync(() -> riskyOperation())
    .thenAccept(result -> process(result))
    .exceptionally(ex -> {
        log.error("Async operation failed", ex);
        return null;
    });

// Or with handle:
CompletableFuture.supplyAsync(() -> riskyOperation())
    .handle((result, ex) -> {
        if (ex != null) { log.error("Failed", ex); return fallback(); }
        return result;
    });
```

### Phòng ngừa
- [ ] Always chain `.exceptionally()` or `.handle()`
- [ ] Log exceptions in async pipelines
- Tool: ErrorProne `FutureReturnValueIgnored`

---

## Pattern 07: @Transactional Trên Wrong Thread

### Phân loại
Concurrency / Spring / Transaction — CRITICAL 🔴

### Vấn đề
```java
@Transactional
public void processOrder(Order order) {
    save(order);
    CompletableFuture.runAsync(() -> {
        updateInventory(order); // Different thread → NO transaction!
        // Uses separate DB connection, no rollback on failure
    });
}
```

### Phát hiện
```bash
rg --type java "@Transactional" -A 10 | rg "runAsync|supplyAsync|@Async|new Thread"
rg --type java "CompletableFuture" -n --glob "*Service*"
```

### Giải pháp
```java
@Transactional
public void processOrder(Order order) {
    save(order);
    updateInventory(order); // Same thread, same transaction

    // If async needed, use event:
    applicationEventPublisher.publishEvent(new OrderCreatedEvent(order.getId()));
}

@TransactionalEventListener(phase = AFTER_COMMIT)
public void onOrderCreated(OrderCreatedEvent event) {
    // Runs after main transaction commits
    asyncService.sendNotification(event.getOrderId());
}
```

### Phòng ngừa
- [ ] No `@Async`/`CompletableFuture` inside `@Transactional`
- [ ] Use `@TransactionalEventListener` for post-commit async
- [ ] Transaction propagation awareness
- Tool: Spring events, `TransactionSynchronization`
