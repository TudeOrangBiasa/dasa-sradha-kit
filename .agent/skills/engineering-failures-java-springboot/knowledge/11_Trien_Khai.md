# Domain 11: Triển Khai (Deployment)

> Java/Spring Boot patterns: Docker, JVM flags, profiles, actuator, GraalVM, graceful shutdown.

---

## Pattern 01: Docker Image Quá Lớn

### Phân loại
Deployment / Docker / Size — HIGH 🟠

### Vấn đề
```dockerfile
FROM eclipse-temurin:21
COPY target/app.jar /app.jar
ENTRYPOINT ["java", "-jar", "/app.jar"]
# Image: 600MB+ (full JDK included)
```

### Phát hiện
```bash
rg "FROM.*jdk|FROM.*eclipse-temurin" -n --glob "Dockerfile*"
rg "COPY.*\\.jar" -n --glob "Dockerfile*"
```

### Giải pháp
```dockerfile
# Multi-stage build:
FROM eclipse-temurin:21 AS build
WORKDIR /app
COPY pom.xml mvnw ./
COPY .mvn .mvn
RUN ./mvnw dependency:resolve
COPY src src
RUN ./mvnw package -DskipTests

FROM eclipse-temurin:21-jre-alpine
COPY --from=build /app/target/*.jar /app.jar
RUN addgroup -S app && adduser -S app -G app
USER app
ENTRYPOINT ["java", "-jar", "/app.jar"]
# Image: ~200MB (JRE only, Alpine base)
```

### Phòng ngừa
- [ ] Multi-stage build (build + runtime)
- [ ] JRE (not JDK) for runtime
- [ ] Alpine base for smaller image
- Tool: Docker, Spring Boot Buildpacks (`./mvnw spring-boot:build-image`)

---

## Pattern 02: JVM Memory Không Tune

### Phân loại
Deployment / JVM / OOM — CRITICAL 🔴

### Vấn đề
```dockerfile
# No JVM memory flags → defaults to 25% of container memory
# Container: 512MB, JVM heap: ~128MB → frequent GC → OOM kill
ENTRYPOINT ["java", "-jar", "/app.jar"]
```

### Phát hiện
```bash
rg "Xmx|Xms|MaxRAMPercentage" -n --glob "Dockerfile*" --glob "*.yml"
rg "JAVA_OPTS|JVM_OPTS|JAVA_TOOL_OPTIONS" -n --glob "Dockerfile*"
```

### Giải pháp
```dockerfile
ENTRYPOINT ["java", \
    "-XX:MaxRAMPercentage=75.0", \
    "-XX:InitialRAMPercentage=50.0", \
    "-XX:+UseG1GC", \
    "-XX:+ExitOnOutOfMemoryError", \
    "-jar", "/app.jar"]

# Or via environment variable:
ENV JAVA_TOOL_OPTIONS="-XX:MaxRAMPercentage=75.0 -XX:+UseG1GC"
```

### Phòng ngừa
- [ ] `MaxRAMPercentage=75` (leave room for native memory)
- [ ] `+ExitOnOutOfMemoryError` (restart instead of hang)
- [ ] Container memory limit ≥ 2× heap
- Tool: JVM flags, Kubernetes resource limits

---

## Pattern 03: Profile Sai Môi Trường

### Phân loại
Deployment / Config / Profile — CRITICAL 🔴

### Vấn đề
```yaml
# application.yml (default profile):
spring:
  datasource:
    url: jdbc:h2:mem:testdb  # H2 in production!
  jpa:
    hibernate:
      ddl-auto: create-drop  # Drops tables on restart!
```

### Phát hiện
```bash
rg "spring.profiles.active|SPRING_PROFILES_ACTIVE" -n --glob "Dockerfile*" --glob "*.yml"
rg "ddl-auto.*create|ddl-auto.*update" -n --glob "application*.yml"
rg "h2:" -n --glob "application.yml"
```

### Giải pháp
```yaml
# application.yml (default — safe for production):
spring:
  jpa:
    hibernate:
      ddl-auto: none

# application-dev.yml:
spring:
  datasource:
    url: jdbc:h2:mem:testdb
  jpa:
    hibernate:
      ddl-auto: create-drop

# application-prod.yml:
spring:
  datasource:
    url: ${DB_URL}
    password: ${DB_PASSWORD}
```

```dockerfile
ENV SPRING_PROFILES_ACTIVE=prod
```

### Phòng ngừa
- [ ] Default profile = production-safe
- [ ] `ddl-auto: none` + Flyway/Liquibase in production
- [ ] `SPRING_PROFILES_ACTIVE` explicitly set in deployment
- Tool: Spring Profiles, Flyway

---

## Pattern 04: Actuator Endpoint Exposed

### Phân loại
Deployment / Security / Actuator — CRITICAL 🔴

### Vấn đề
```yaml
management:
  endpoints:
    web:
      exposure:
        include: "*"  # ALL actuator endpoints public!
# /actuator/env → shows DB passwords, API keys
# /actuator/heapdump → downloads JVM heap (contains secrets)
```

### Phát hiện
```bash
rg "actuator|management.endpoints" -n --glob "application*.yml"
rg "include.*\\*" -n --glob "application*.yml"
```

### Giải pháp
```yaml
management:
  endpoints:
    web:
      exposure:
        include: health,info,metrics,prometheus
      base-path: /internal/actuator  # Non-standard path
  endpoint:
    health:
      show-details: when-authorized
    env:
      enabled: false
    heapdump:
      enabled: false
```

```java
// Secure actuator endpoints:
@Bean
public SecurityFilterChain actuatorSecurity(HttpSecurity http) throws Exception {
    return http
        .securityMatcher("/internal/actuator/**")
        .authorizeHttpRequests(a -> a
            .requestMatchers("/internal/actuator/health").permitAll()
            .anyRequest().hasRole("ADMIN"))
        .build();
}
```

### Phòng ngừa
- [ ] Never `include: "*"` in production
- [ ] Disable `env`, `heapdump`, `shutdown`
- [ ] Secure actuator with Spring Security
- Tool: Spring Actuator, Spring Security

---

## Pattern 05: Graceful Shutdown Thiếu

### Phân loại
Deployment / Shutdown / K8s — HIGH 🟠

### Vấn đề
```
# Pod killed → in-flight requests dropped → 502 errors
# DB transactions interrupted → data corruption
# Scheduled tasks cut mid-execution
```

### Phát hiện
```bash
rg "graceful|shutdown" -n --glob "application*.yml"
rg --type java "@PreDestroy|DisposableBean|SmartLifecycle" -n
```

### Giải pháp
```yaml
# application.yml:
server:
  shutdown: graceful
spring:
  lifecycle:
    timeout-per-shutdown-phase: 30s
```

```java
@Bean
public GracefulShutdown gracefulShutdown() {
    return new GracefulShutdown();
}

@PreDestroy
public void onShutdown() {
    log.info("Shutting down — completing in-flight requests");
    // Close external connections, flush caches
}
```

```yaml
# Kubernetes:
spec:
  terminationGracePeriodSeconds: 60
  containers:
    - lifecycle:
        preStop:
          exec:
            command: ["sh", "-c", "sleep 10"] # Wait for LB to drain
```

### Phòng ngừa
- [ ] `server.shutdown: graceful` in Spring Boot
- [ ] K8s `preStop` hook for load balancer drain
- [ ] `terminationGracePeriodSeconds` > shutdown timeout
- Tool: Spring Boot graceful shutdown, K8s lifecycle

---

## Pattern 06: GraalVM Native Image Reflection

### Phân loại
Deployment / GraalVM / AOT — HIGH 🟠

### Vấn đề
```
# GraalVM native image compile fails:
# - Reflection-based libraries not detected at build time
# - Jackson serialization fails at runtime
# - Spring proxies missing
# Error: Class not found at runtime (was optimized away)
```

### Phát hiện
```bash
rg "native" -n --glob "pom.xml" --glob "build.gradle*"
rg --type java "@RegisterReflection|@ImportRuntimeHints" -n
rg "reflect-config.json" -n
```

### Giải pháp
```java
// Register reflection hints:
@RegisterReflectionForBinding({UserDto.class, OrderDto.class})
@SpringBootApplication
public class Application { }

// Or custom RuntimeHints:
public class MyRuntimeHints implements RuntimeHintsRegistrar {
    @Override
    public void registerHints(RuntimeHints hints, ClassLoader cl) {
        hints.reflection().registerType(MyEntity.class,
            MemberCategory.INVOKE_DECLARED_CONSTRUCTORS,
            MemberCategory.INVOKE_DECLARED_METHODS);
    }
}
```

```bash
# Build native image:
./mvnw -Pnative native:compile
# Or with Buildpacks:
./mvnw spring-boot:build-image -Pnative
```

### Phòng ngừa
- [ ] Test with `native:compile` in CI
- [ ] `@RegisterReflectionForBinding` for DTOs
- [ ] Spring AOT processing handles most Spring proxies
- Tool: GraalVM, Spring AOT, `RuntimeHintsRegistrar`

---

## Pattern 07: Flyway Migration Thiếu Idempotent

### Phân loại
Deployment / Database / Migration — HIGH 🟠

### Vấn đề
```sql
-- V1__create_users.sql
CREATE TABLE users (id BIGINT PRIMARY KEY, name VARCHAR(255));
-- Deploy twice → "Table already exists" error → app won't start
```

### Phát hiện
```bash
rg "flyway|liquibase" -n --glob "pom.xml" --glob "application*.yml"
rg "CREATE TABLE|ALTER TABLE|DROP" -n --glob "V*__*.sql"
```

### Giải pháp
```sql
-- V1__create_users.sql (idempotent):
CREATE TABLE IF NOT EXISTS users (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name VARCHAR(255) NOT NULL
);

-- V2__add_email.sql (safe additive change):
ALTER TABLE users ADD COLUMN IF NOT EXISTS email VARCHAR(255);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
```

```yaml
spring:
  flyway:
    enabled: true
    baseline-on-migrate: true
    locations: classpath:db/migration
```

### Phòng ngừa
- [ ] `IF NOT EXISTS` / `IF EXISTS` in DDL
- [ ] Never modify executed migrations (create new ones)
- [ ] Test migrations in CI with real DB
- Tool: Flyway, Liquibase, Testcontainers
