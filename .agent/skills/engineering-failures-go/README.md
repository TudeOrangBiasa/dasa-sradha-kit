# Engineering Failures Audit Skill — Go Edition

## Giới thiệu

Bộ công cụ tự động quét mã nguồn Go để phát hiện **140 mẫu lỗi kỹ thuật phổ biến** trong phát triển Go, phân loại thành **12 lĩnh vực**.

## Sử dụng

```bash
# Quét toàn bộ
/ef-go

# Chỉ quét domain cụ thể
/ef-go 01    # Goroutine & Channel
/ef-go 07    # Error Handling

# Chỉ quét theo mức nghiêm trọng
/ef-go critical

# Quét project khác
/ef-go all /path/to/go-project
```

## 12 Lĩnh vực

| # | Lĩnh vực | Số mẫu |
|---|----------|:------:|
| 01 | Goroutine Và Channel | 18 |
| 02 | Hệ Thống Phân Tán | 12 |
| 03 | Bảo Mật Và Xác Thực | 12 |
| 04 | Toàn Vẹn Dữ Liệu | 10 |
| 05 | Quản Lý Tài Nguyên | 12 |
| 06 | Interface Và Thiết Kế | 12 |
| 07 | Xử Lý Lỗi | 14 |
| 08 | Hiệu Năng Và Mở Rộng | 12 |
| 09 | Thiết Kế API | 10 |
| 10 | Thử Nghiệm | 10 |
| 11 | Triển Khai Và Build | 8 |
| 12 | Giám Sát Và Quan Sát | 10 |
| | **Tổng** | **140** |

## Ngôn ngữ hỗ trợ

- Go (Gin, Echo, Fiber, gRPC, GORM, sqlx)

## Tích hợp công cụ

- `go vet` — Built-in lint
- `staticcheck` — Advanced lint
- `golangci-lint` — Meta-linter
- `govulncheck` — CVE check
- `go test -race` — Race detector
