# Engineering Failures Bible — Java Spring Boot Edition

## Tổng Quan

Bộ kiến thức về các mẫu lỗi phổ biến trong Java 21+ và Spring Boot 3.x, được tổ chức theo 13 domain.

## Cấu Trúc Domain

| # | Domain | File | Patterns |
|---|--------|------|----------|
| 00 | Tổng Quan | `00_Tong_Quan.md` | Giới thiệu |
| 01 | Bộ Nhớ | `01_Bo_Nho.md` | Memory leaks, GC pressure, heap |
| 02 | Đồng Thời | `02_Dong_Thoi.md` | Thread safety, deadlock, virtual threads |
| 03 | Bảo Mật | `03_Bao_Mat.md` | Injection, auth, secrets, CSRF |
| 04 | Dữ Liệu | `04_Du_Lieu.md` | JPA/Hibernate, transactions, serialization |
| 05 | Mạng | `05_Mang.md` | HTTP clients, connection pools, timeouts |
| 06 | Hệ Thống Tập Tin | `06_He_Thong_Tap_Tin.md` | File I/O, resources, temp files |
| 07 | Xử Lý Lỗi | `07_Xu_Ly_Loi.md` | Exception handling, @ControllerAdvice |
| 08 | Hiệu Năng | `08_Hieu_Nang.md` | N+1, caching, lazy loading, GC tuning |
| 09 | Thiết Kế API | `09_Thiet_Ke_API.md` | REST conventions, validation, versioning |
| 10 | Thử Nghiệm | `10_Thu_Nghiem.md` | JUnit, Mockito, Testcontainers, slicing |
| 11 | Triển Khai | `11_Trien_Khai.md` | Docker, profiles, actuator, GraalVM |
| 12 | Giám Sát | `12_Giam_Sat.md` | Micrometer, OpenTelemetry, logging |

## Quy Tắc Phát Hiện

- Sử dụng `rg --type java` cho tất cả regex patterns
- Java 21+ features: virtual threads, pattern matching, records, sealed classes
- Spring Boot 3.x: Jakarta namespace, Micrometer, Observation API
- Build tools: Maven/Gradle
- Lọc nhiễu: bỏ `target/`, `build/`, `*.class`, `generated-sources/`

## Mức Nghiêm Trọng

| Mức | Ý nghĩa |
|-----|---------|
| CRITICAL 🔴 | Crash, data loss, security breach |
| HIGH 🟠 | Performance degradation, resource leak, data corruption |
| MEDIUM 🟡 | Maintenance burden, potential bugs |
| LOW 🟢 | Code quality, convention violation |

## Công Cụ Bổ Trợ

| Công cụ | Mục đích |
|---------|----------|
| SpotBugs | Static bug detection |
| SonarQube | Quality gate + security |
| ErrorProne | Compile-time bug detection |
| Checkstyle | Code style enforcement |
| OWASP Dependency-Check | CVE scanning |
| JaCoCo | Test coverage |
| VisualVM / JFR | Runtime profiling |
| Micrometer | Metrics + tracing |
