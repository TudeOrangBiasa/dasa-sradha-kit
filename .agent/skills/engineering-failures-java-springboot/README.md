# Engineering Failures Audit Skill — Java Spring Boot Edition

## Giới thiệu

Bộ công cụ tự động quét mã nguồn Java/Spring Boot để phát hiện **~90 mẫu lỗi kỹ thuật phổ biến** trong phát triển Java 21+ và Spring Boot 3.x, phân loại thành **12 lĩnh vực**.

## Sử dụng

```bash
# Quét toàn bộ
/ef-java

# Chỉ quét domain cụ thể
/ef-java 01    # Bộ Nhớ (Memory)
/ef-java 03    # Bảo Mật (Security)
/ef-java 04    # Dữ Liệu / JPA

# Chỉ quét theo mức nghiêm trọng
/ef-java critical

# Quét project khác
/ef-java all /path/to/spring-boot-project
```

## 12 Lĩnh vực

| # | Lĩnh vực | Số mẫu |
|---|----------|:------:|
| 01 | Bộ Nhớ (Memory) | 7 |
| 02 | Đồng Thời (Concurrency) | 7 |
| 03 | Bảo Mật (Security) | 7 |
| 04 | Dữ Liệu / JPA (Data) | 7 |
| 05 | Mạng (Networking) | 7 |
| 06 | Hệ Thống Tập Tin (File System) | 6 |
| 07 | Xử Lý Lỗi (Error Handling) | 7 |
| 08 | Hiệu Năng (Performance) | 7 |
| 09 | Thiết Kế API (API Design) | 7 |
| 10 | Thử Nghiệm (Testing) | 7 |
| 11 | Triển Khai (Deployment) | 7 |
| 12 | Giám Sát (Monitoring) | 7 |
| | **Tổng** | **~90** |

## Công nghệ hỗ trợ

- Java 21+ (virtual threads, records, pattern matching, sealed classes)
- Spring Boot 3.x (Jakarta namespace, Micrometer, Observation API)
- JPA / Hibernate 6.x
- Spring Security 6.x
- Spring Data JPA
- HikariCP, Flyway/Liquibase
- Testcontainers, JUnit 5, Mockito
- Micrometer, OpenTelemetry
- Docker, GraalVM Native Image

## Tích hợp công cụ

- SpotBugs — Static bug detection
- SonarQube — Quality gate + security
- ErrorProne — Compile-time bug detection
- OWASP Dependency-Check — CVE scanning
- JaCoCo — Test coverage
- VisualVM / JFR — Runtime profiling
- Micrometer — Metrics + tracing
