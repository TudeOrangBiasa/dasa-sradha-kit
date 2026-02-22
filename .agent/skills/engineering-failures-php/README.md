# Engineering Failures Audit Skill — PHP Edition

## Giới thiệu

Bộ công cụ tự động quét mã nguồn PHP để phát hiện **138 mẫu lỗi kỹ thuật phổ biến** trong phát triển PHP, phân loại thành **12 lĩnh vực**.

## Sử dụng

```bash
# Quét toàn bộ
/ef-php

# Chỉ quét domain cụ thể
/ef-php 01    # Type Coercion
/ef-php 02    # Web Security

# Chỉ quét theo mức nghiêm trọng
/ef-php critical

# Quét project khác
/ef-php all /path/to/php-project
```

## 12 Lĩnh vực

| # | Lĩnh vực | Số mẫu |
|---|----------|:------:|
| 01 | Kiểu Dữ Liệu Và So Sánh | 14 |
| 02 | Bảo Mật Web | 18 |
| 03 | Bảo Mật Và Xác Thực | 12 |
| 04 | Toàn Vẹn Dữ Liệu | 12 |
| 05 | Quản Lý Tài Nguyên | 10 |
| 06 | Thiết Kế Và Kiến Trúc | 12 |
| 07 | Xử Lý Lỗi | 10 |
| 08 | Hiệu Năng Và Mở Rộng | 12 |
| 09 | Thiết Kế API | 10 |
| 10 | Thử Nghiệm | 10 |
| 11 | Triển Khai Và Hạ Tầng | 8 |
| 12 | Giám Sát Và Quan Sát | 10 |
| | **Tổng** | **138** |

## Ngôn ngữ hỗ trợ

- PHP 8.x (Laravel, Symfony, WordPress)

## Tích hợp công cụ

- `PHPStan` — Static analysis
- `Psalm` — Taint analysis (security)
- `PHP CS Fixer` — Code style
- `composer audit` — CVE check
- `Rector` — Automated refactoring
