# Domain 07: Xử Lý Lỗi (Error Handling)

> Java/Spring Boot patterns: exception handling, @ControllerAdvice, error responses, logging.

---

## Pattern 01: Exception Bị Nuốt

### Phân loại
Error / Swallowed / Silent — CRITICAL 🔴

### Vấn đề
```java
try {
    processPayment(order);
} catch (Exception e) {
    // Silently swallowed! No logging, no re-throw
}
// Or worse:
catch (Exception e) { e.printStackTrace(); } // Goes to stderr, not to logs
```

### Phát hiện
```bash
rg --type java "catch.*Exception.*\\{\\s*\\}" -n
rg --type java "catch.*\\{" -A 2 | rg "printStackTrace"
rg --type java "catch.*\\{\\s*//|catch.*\\{\\s*$" -n
```

### Giải pháp
```java
try {
    processPayment(order);
} catch (PaymentException e) {
    log.error("Payment failed for order {}", order.getId(), e);
    throw new OrderProcessingException("Payment failed", e);
}

// Or re-throw with context:
catch (Exception e) {
    throw new ServiceException("Failed processing order " + orderId, e);
}
```

### Phòng ngừa
- [ ] Never empty catch blocks
- [ ] `log.error()` with exception as last param (stack trace)
- [ ] Re-throw or handle meaningfully
- Tool: SpotBugs `DE_MIGHT_IGNORE`, SonarQube

---

## Pattern 02: @ControllerAdvice Thiếu

### Phân loại
Error / REST / Response — HIGH 🟠

### Vấn đề
```java
@GetMapping("/users/{id}")
public User getUser(@PathVariable Long id) {
    return userRepo.findById(id).orElseThrow(); // → 500 with stack trace!
}
// Client sees: {"timestamp":"...","status":500,"error":"Internal Server Error",
//   "trace":"java.util.NoSuchElementException\n\tat ..."}
// Stack trace leaked to client!
```

### Phát hiện
```bash
rg --type java "@ControllerAdvice|@RestControllerAdvice" -n
rg --type java "@ExceptionHandler" -n
rg --type java "orElseThrow\\(\\)" -n
```

### Giải pháp
```java
@RestControllerAdvice
public class GlobalExceptionHandler {
    @ExceptionHandler(EntityNotFoundException.class)
    public ResponseEntity<ErrorResponse> handleNotFound(EntityNotFoundException e) {
        return ResponseEntity.status(404)
            .body(new ErrorResponse("NOT_FOUND", e.getMessage()));
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<ErrorResponse> handleValidation(MethodArgumentNotValidException e) {
        var errors = e.getBindingResult().getFieldErrors().stream()
            .map(f -> f.getField() + ": " + f.getDefaultMessage()).toList();
        return ResponseEntity.badRequest()
            .body(new ErrorResponse("VALIDATION_ERROR", errors.toString()));
    }

    @ExceptionHandler(Exception.class)
    public ResponseEntity<ErrorResponse> handleGeneral(Exception e) {
        log.error("Unhandled exception", e);
        return ResponseEntity.status(500)
            .body(new ErrorResponse("INTERNAL_ERROR", "An error occurred"));
    }
}

record ErrorResponse(String code, String message) {}
```

### Phòng ngừa
- [ ] Global `@RestControllerAdvice` for all APIs
- [ ] Never expose stack traces to clients
- [ ] Structured error response format
- Tool: Spring `@RestControllerAdvice`, ProblemDetail (RFC 7807)

---

## Pattern 03: Checked Exception Abuse

### Phân loại
Error / Design / Java — MEDIUM 🟡

### Vấn đề
```java
public User findUser(Long id) throws UserNotFoundException,
    DatabaseException, ValidationException, SerializationException {
    // Every caller must handle 4 checked exceptions
    // Leads to: catch (Exception e) { /* give up */ }
}
```

### Phát hiện
```bash
rg --type java "throws.*,.*," -n
rg --type java "extends Exception" -n | rg -v "Runtime"
```

### Giải pháp
```java
// Use unchecked exceptions for business logic:
public class UserNotFoundException extends RuntimeException {
    public UserNotFoundException(Long id) {
        super("User not found: " + id);
    }
}

// Clean service:
public User findUser(Long id) {
    return userRepo.findById(id)
        .orElseThrow(() -> new UserNotFoundException(id));
}
// Let @ControllerAdvice handle the mapping to HTTP response
```

### Phòng ngừa
- [ ] Runtime exceptions for business errors
- [ ] Checked exceptions only for recoverable conditions
- [ ] `@ControllerAdvice` maps exceptions to HTTP status
- Tool: Spring exception hierarchy

---

## Pattern 04: Error Response Không Nhất Quán

### Phân loại
Error / API / Contract — MEDIUM 🟡

### Vấn đề
```java
// Different endpoints return different error formats:
// GET /users/999 → {"message": "Not found"}
// POST /orders   → {"error": "Invalid", "details": [...]}
// PUT /products  → "Something went wrong"  (plain text!)
```

### Phát hiện
```bash
rg --type java "ResponseEntity.*bad|ResponseEntity.*status" -n
rg --type java "ErrorResponse|ErrorDto|ApiError" -n
```

### Giải pháp
```java
// Spring 6+ ProblemDetail (RFC 7807):
@RestControllerAdvice
public class GlobalExceptionHandler extends ResponseEntityExceptionHandler {
    @ExceptionHandler(UserNotFoundException.class)
    public ProblemDetail handleNotFound(UserNotFoundException e) {
        ProblemDetail pd = ProblemDetail.forStatus(HttpStatus.NOT_FOUND);
        pd.setTitle("User Not Found");
        pd.setDetail(e.getMessage());
        pd.setProperty("errorCode", "USER_NOT_FOUND");
        return pd;
    }
}
// Response: {"type":"about:blank","title":"User Not Found",
//   "status":404,"detail":"User not found: 123","errorCode":"USER_NOT_FOUND"}
```

### Phòng ngừa
- [ ] `ProblemDetail` (RFC 7807) for all error responses
- [ ] Single `@RestControllerAdvice` for consistency
- [ ] Document error codes in OpenAPI spec
- Tool: Spring ProblemDetail, RFC 7807

---

## Pattern 05: Logging Exception Sai

### Phân loại
Error / Logging / Stack Trace — HIGH 🟠

### Vấn đề
```java
catch (Exception e) {
    log.error("Failed: " + e.getMessage()); // Lost stack trace!
    log.error("Failed: " + e);              // toString() only, no trace
    log.error("Failed: {}", e.getMessage()); // Still no stack trace
}
```

### Phát hiện
```bash
rg --type java "log\\.error\\(.*getMessage\\(\\)" -n
rg --type java "log\\.error\\(.*\\+ e\\)" -n
rg --type java "log\\.(error|warn)\\(" -n | rg -v ", e\\)$|, ex\\)$"
```

### Giải pháp
```java
// GOOD: Exception as LAST parameter (SLF4J auto-logs stack trace)
catch (Exception e) {
    log.error("Payment failed for order {}", orderId, e);
    //                                                 ↑ exception as last arg
}

// Pattern: message with context + exception
log.error("Failed to process order={} user={}", orderId, userId, e);
```

### Phòng ngừa
- [ ] Exception as last param in SLF4J `log.error()`
- [ ] Include business context (IDs, state)
- Tool: SLF4J, Logback

---

## Pattern 06: @Transactional Rollback Sai

### Phân loại
Error / Transaction / Rollback — CRITICAL 🔴

### Vấn đề
```java
@Transactional
public void processOrder(Order order) {
    save(order);
    throw new BusinessException("Validation failed");
    // BusinessException extends Exception (checked) → NO rollback!
    // Spring only rolls back on RuntimeException by default
}
```

### Phát hiện
```bash
rg --type java "@Transactional" -n | rg -v "rollbackFor"
rg --type java "extends Exception" -n | rg -v "Runtime"
```

### Giải pháp
```java
// Option 1: Specify rollbackFor
@Transactional(rollbackFor = Exception.class)
public void processOrder(Order order) {
    save(order);
    if (!valid(order)) throw new BusinessException("Invalid"); // Will rollback
}

// Option 2 (preferred): Use RuntimeException
public class BusinessException extends RuntimeException { /* ... */ }
// @Transactional rolls back by default for RuntimeException
```

### Phòng ngừa
- [ ] `rollbackFor = Exception.class` if using checked exceptions
- [ ] Business exceptions extend `RuntimeException`
- [ ] Test rollback behavior
- Tool: Spring `@Transactional`, TransactionTemplate

---

## Pattern 07: Generic Exception Catch

### Phân loại
Error / Design / Catch — MEDIUM 🟡

### Vấn đề
```java
try {
    parseInput(data);
    validateBusiness(data);
    saveToDb(data);
} catch (Exception e) { // Catches EVERYTHING: NPE, OOM, StackOverflow
    return "Invalid input"; // NPE silently treated as validation error
}
```

### Phát hiện
```bash
rg --type java "catch\\s*\\(Exception " -n
rg --type java "catch\\s*\\(Throwable " -n
```

### Giải pháp
```java
try {
    parseInput(data);
    validateBusiness(data);
    saveToDb(data);
} catch (ValidationException e) {
    return ResponseEntity.badRequest().body(e.getMessage());
} catch (DataAccessException e) {
    log.error("DB error saving data", e);
    throw new ServiceException("Save failed", e);
}
// Let unexpected exceptions propagate to @ControllerAdvice
```

### Phòng ngừa
- [ ] Catch specific exceptions, not `Exception`
- [ ] Let unexpected errors propagate
- [ ] `@ControllerAdvice` as safety net
- Tool: SonarQube `squid:S2142`
