# Bách Khoa Toàn Thư Về Lỗi Kỹ Thuật — PHP Edition
# Encyclopedia of Software Engineering Failures — PHP

> **Phiên bản:** 1.0
> **Ngày tạo:** 2026-02-18
> **Mục đích:** Tài liệu tham khảo toàn diện về các mẫu lỗi kỹ thuật phổ biến trong phát triển PHP
> **Nguồn gốc:** Tổng hợp từ OWASP, PHP The Right Way, PHPStan docs, Laravel docs, và kinh nghiệm thực tiễn

---

## Giới thiệu

Tài liệu này tổng hợp **138 mẫu lỗi kỹ thuật** phổ biến nhất trong phát triển PHP, được phân loại thành **12 lĩnh vực**. Mỗi mẫu lỗi bao gồm mô tả vấn đề, cách phát hiện trong mã nguồn (kèm regex), giải pháp PHP idiomatic (Laravel/Symfony), và danh sách phòng ngừa kèm PHPStan/Psalm rules.

## Mục lục

| # | Lĩnh vực | File | Số mẫu |
|---|----------|------|:------:|
| 01 | Kiểu Dữ Liệu Và So Sánh | `01_Kieu_Du_Lieu_Va_So_Sanh.md` | 14 |
| 02 | Bảo Mật Web | `02_Bao_Mat_Web.md` | 18 |
| 03 | Bảo Mật Và Xác Thực | `03_Bao_Mat_Va_Xac_Thuc.md` | 12 |
| 04 | Toàn Vẹn Dữ Liệu | `04_Toan_Ven_Du_Lieu.md` | 12 |
| 05 | Quản Lý Tài Nguyên | `05_Quan_Ly_Tai_Nguyen.md` | 10 |
| 06 | Thiết Kế Và Kiến Trúc | `06_Thiet_Ke_Va_Kien_Truc.md` | 12 |
| 07 | Xử Lý Lỗi | `07_Xu_Ly_Loi.md` | 10 |
| 08 | Hiệu Năng Và Mở Rộng | `08_Hieu_Nang_Va_Mo_Rong.md` | 12 |
| 09 | Thiết Kế API | `09_Thiet_Ke_API.md` | 10 |
| 10 | Thử Nghiệm | `10_Thu_Nghiem.md` | 10 |
| 11 | Triển Khai Và Hạ Tầng | `11_Trien_Khai_Va_Ha_Tang.md` | 8 |
| 12 | Giám Sát Và Quan Sát | `12_Giam_Sat_Va_Quan_Sat.md` | 10 |
| | **Tổng cộng** | | **138** |

## Phân bố mức nghiêm trọng

| Mức độ | Ký hiệu | Số lượng | Ý nghĩa |
|--------|----------|:--------:|---------|
| Nghiêm trọng | 🔴 CRITICAL | 32 | SQL injection, XSS, RCE, auth bypass |
| Cao | 🟠 HIGH | 48 | N+1 query, type coercion bugs, resource leak |
| Trung bình | 🟡 MEDIUM | 50 | Code smell, maintainability, minor security |
| Thấp | 🔵 LOW | 8 | Style, optimization suggestions |

## Đặc điểm PHP-specific

- **Type coercion** — `==` traps là nguồn bugs phổ biến nhất
- **Web security** — PHP là target #1 cho web attacks
- **Legacy code** — Nhiều deprecated functions vẫn được dùng
- **Framework diversity** — Laravel, Symfony, WordPress có anti-patterns riêng
- **Shared-nothing** — Mỗi request tạo context mới, stateless

## Công cụ hỗ trợ

| Công cụ | Mục đích | Lệnh |
|---------|----------|------|
| PHPStan | Static analysis | `./vendor/bin/phpstan analyse --level=max` |
| Psalm | Taint analysis | `./vendor/bin/psalm --taint-analysis` |
| PHP CS Fixer | Code style | `./vendor/bin/php-cs-fixer fix` |
| composer audit | CVE check | `composer audit` |
| Rector | Refactoring | `./vendor/bin/rector process` |
| Xdebug | Debugging | PHP extension |
| Blackfire | Profiling | Blackfire agent |

## Nguồn tham khảo

- [PHP: The Right Way](https://phptherightway.com/)
- [OWASP PHP Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/PHP_Configuration_Cheat_Sheet.html)
- [PHPStan Documentation](https://phpstan.org/user-guide/getting-started)
- [Laravel Security Best Practices](https://laravel.com/docs/security)
- [Symfony Security](https://symfony.com/doc/current/security.html)
