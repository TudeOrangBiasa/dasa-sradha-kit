# Engineering Failures Audit Skill — Rust Edition

## Giới thiệu

Bộ công cụ tự động quét mã nguồn Rust để phát hiện **142 mẫu lỗi kỹ thuật phổ biến** trong phát triển Rust, phân loại thành **12 lĩnh vực**.

## Sử dụng

```bash
# Quét toàn bộ
/ef-rust

# Chỉ quét domain cụ thể
/ef-rust 01    # Ownership & Borrowing
/ef-rust 02    # Async & Concurrency
/ef-rust 03    # Unsafe & FFI

# Chỉ quét theo mức nghiêm trọng
/ef-rust critical

# Quét project khác
/ef-rust all /path/to/rust-project
```

## 12 Lĩnh vực

| # | Lĩnh vực | Số mẫu |
|---|----------|:------:|
| 01 | Ownership Và Borrowing | 15 |
| 02 | Đồng Thời Và Async | 18 |
| 03 | Unsafe Và FFI | 12 |
| 04 | Bảo Mật Và Xác Thực | 12 |
| 05 | Quản Lý Bộ Nhớ | 12 |
| 06 | Hệ Thống Kiểu | 10 |
| 07 | Xử Lý Lỗi | 12 |
| 08 | Hiệu Năng Và Mở Rộng | 12 |
| 09 | Thiết Kế API Và Crate | 10 |
| 10 | Thử Nghiệm Và Fuzzing | 10 |
| 11 | Triển Khai Và Build | 9 |
| 12 | Giám Sát Và Quan Sát | 10 |
| | **Tổng** | **142** |

## Ngôn ngữ hỗ trợ

- Rust (Tokio, Actix, Axum, Rocket, Diesel, SQLx)

## Tích hợp công cụ

- `cargo clippy` — Static analysis
- `cargo miri` — UB detection
- `cargo audit` — CVE check
- `cargo deny` — License/advisory
- `cargo fuzz` — Fuzzing
