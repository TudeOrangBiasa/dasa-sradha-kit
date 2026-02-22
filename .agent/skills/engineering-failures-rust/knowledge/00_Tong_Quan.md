# Bách Khoa Toàn Thư Về Lỗi Kỹ Thuật — Rust Edition
# Encyclopedia of Software Engineering Failures — Rust

> **Phiên bản:** 1.0
> **Ngày tạo:** 2026-02-18
> **Mục đích:** Tài liệu tham khảo toàn diện về các mẫu lỗi kỹ thuật phổ biến trong phát triển Rust
> **Nguồn gốc:** Tổng hợp từ Rust Nomicon, Clippy lints, RustSec Advisory, Tokio docs, và kinh nghiệm thực tiễn

---

## Giới thiệu

Tài liệu này tổng hợp **142 mẫu lỗi kỹ thuật** phổ biến nhất trong phát triển Rust, được phân loại thành **12 lĩnh vực**. Mỗi mẫu lỗi bao gồm mô tả vấn đề, cách phát hiện trong mã nguồn (kèm regex), giải pháp Rust idiomatic, và danh sách phòng ngừa kèm Clippy lints.

## Mục lục

| # | Lĩnh vực | File | Số mẫu |
|---|----------|------|:------:|
| 01 | Ownership Và Borrowing | `01_Ownership_Va_Borrowing.md` | 15 |
| 02 | Đồng Thời Và Async | `02_Dong_Thoi_Va_Async.md` | 18 |
| 03 | Unsafe Và FFI | `03_Unsafe_Va_FFI.md` | 12 |
| 04 | Bảo Mật Và Xác Thực | `04_Bao_Mat_Va_Xac_Thuc.md` | 12 |
| 05 | Quản Lý Bộ Nhớ | `05_Quan_Ly_Bo_Nho.md` | 12 |
| 06 | Hệ Thống Kiểu | `06_He_Thong_Kieu.md` | 10 |
| 07 | Xử Lý Lỗi | `07_Xu_Ly_Loi.md` | 12 |
| 08 | Hiệu Năng Và Mở Rộng | `08_Hieu_Nang_Va_Mo_Rong.md` | 12 |
| 09 | Thiết Kế API Và Crate | `09_Thiet_Ke_API_Va_Crate.md` | 10 |
| 10 | Thử Nghiệm Và Fuzzing | `10_Thu_Nghiem_Va_Fuzzing.md` | 10 |
| 11 | Triển Khai Và Build | `11_Trien_Khai_Va_Build.md` | 9 |
| 12 | Giám Sát Và Quan Sát | `12_Giam_Sat_Va_Quan_Sat.md` | 10 |
| | **Tổng cộng** | | **142** |

## Phân bố mức nghiêm trọng

| Mức độ | Ký hiệu | Số lượng | Ý nghĩa |
|--------|----------|:--------:|---------|
| Nghiêm trọng | 🔴 CRITICAL | 38 | UB, memory corruption, security vulnerability, data loss |
| Cao | 🟠 HIGH | 48 | Performance degradation, deadlock, resource leak |
| Trung bình | 🟡 MEDIUM | 50 | Code smell, non-idiomatic, maintainability issue |
| Thấp | 🔵 LOW | 6 | Style, minor optimization |

## Đặc điểm Rust-specific

Rust có borrow checker và ownership model giúp loại bỏ nhiều lỗi ở compile-time. Tuy nhiên:

- **unsafe blocks** vẫn cho phép UB nếu dùng sai
- **async/await** có pitfalls riêng (blocking in async, cancellation unsafety)
- **FFI** là ranh giới nơi safety guarantees bị mất
- **Clone/Copy abuse** tạo performance issues
- **Error handling** (`unwrap`, `expect`) gây panic trong production

## Công cụ hỗ trợ

| Công cụ | Mục đích | Lệnh |
|---------|----------|------|
| Clippy | Static analysis | `cargo clippy -- -W clippy::all` |
| Miri | UB detection | `cargo +nightly miri test` |
| cargo audit | CVE check | `cargo audit` |
| cargo deny | License/advisory | `cargo deny check` |
| cargo fuzz | Fuzzing | `cargo fuzz run target` |
| cargo flamegraph | Profiling | `cargo flamegraph` |
| cargo semver-checks | API compat | `cargo semver-checks check-release` |

## Nguồn tham khảo

- [The Rustonomicon](https://doc.rust-lang.org/nomicon/)
- [Rust API Guidelines](https://rust-lang.github.io/api-guidelines/)
- [Clippy Lints](https://rust-lang.github.io/rust-clippy/master/)
- [RustSec Advisory Database](https://rustsec.org/)
- [Tokio Tutorial](https://tokio.rs/tokio/tutorial)
- [Rust Performance Book](https://nnethercote.github.io/perf-book/)
