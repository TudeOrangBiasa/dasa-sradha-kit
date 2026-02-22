# Bách Khoa Toàn Thư Về Lỗi Kỹ Thuật — Go Edition
# Encyclopedia of Software Engineering Failures — Go

> **Phiên bản:** 1.0
> **Ngày tạo:** 2026-02-18
> **Mục đích:** Tài liệu tham khảo toàn diện về các mẫu lỗi kỹ thuật phổ biến trong phát triển Go
> **Nguồn gốc:** Tổng hợp từ Go Blog, Effective Go, Go Wiki, staticcheck docs, và kinh nghiệm thực tiễn

---

## Giới thiệu

Tài liệu này tổng hợp **140 mẫu lỗi kỹ thuật** phổ biến nhất trong phát triển Go, được phân loại thành **12 lĩnh vực**. Mỗi mẫu lỗi bao gồm mô tả vấn đề, cách phát hiện trong mã nguồn (kèm regex), giải pháp Go idiomatic, và danh sách phòng ngừa kèm staticcheck/go vet rules.

## Mục lục

| # | Lĩnh vực | File | Số mẫu |
|---|----------|------|:------:|
| 01 | Goroutine Và Channel | `01_Goroutine_Va_Channel.md` | 18 |
| 02 | Hệ Thống Phân Tán | `02_He_Thong_Phan_Tan.md` | 12 |
| 03 | Bảo Mật Và Xác Thực | `03_Bao_Mat_Va_Xac_Thuc.md` | 12 |
| 04 | Toàn Vẹn Dữ Liệu | `04_Toan_Ven_Du_Lieu.md` | 10 |
| 05 | Quản Lý Tài Nguyên | `05_Quan_Ly_Tai_Nguyen.md` | 12 |
| 06 | Interface Và Thiết Kế | `06_Interface_Va_Thiet_Ke.md` | 12 |
| 07 | Xử Lý Lỗi | `07_Xu_Ly_Loi.md` | 14 |
| 08 | Hiệu Năng Và Mở Rộng | `08_Hieu_Nang_Va_Mo_Rong.md` | 12 |
| 09 | Thiết Kế API | `09_Thiet_Ke_API.md` | 10 |
| 10 | Thử Nghiệm | `10_Thu_Nghiem.md` | 10 |
| 11 | Triển Khai Và Build | `11_Trien_Khai_Va_Build.md` | 8 |
| 12 | Giám Sát Và Quan Sát | `12_Giam_Sat_Va_Quan_Sat.md` | 10 |
| | **Tổng cộng** | | **140** |

## Phân bố mức nghiêm trọng

| Mức độ | Ký hiệu | Số lượng | Ý nghĩa |
|--------|----------|:--------:|---------|
| Nghiêm trọng | 🔴 CRITICAL | 28 | Goroutine leak, data race, crash, security hole |
| Cao | 🟠 HIGH | 52 | Resource leak, deadlock, error handling failure |
| Trung bình | 🟡 MEDIUM | 52 | Non-idiomatic, performance issue, code smell |
| Thấp | 🔵 LOW | 8 | Style, minor optimization |

## Đặc điểm Go-specific

Go có triết lý "simplicity" nhưng vẫn có nhiều pitfalls:

- **Goroutine leaks** — lightweight nhưng dễ leak, khó detect
- **Error handling** — `if err != nil` pattern dễ bỏ qua hoặc xử lý sai
- **Nil interface trap** — interface chứa nil concrete ≠ nil interface
- **Channel semantics** — nil channel, closed channel, buffer size gotchas
- **Implicit interfaces** — không khai báo implement, dễ break contract
- **Loop variable capture** — đã fix ở Go 1.22 nhưng legacy code vẫn nhiều

## Công cụ hỗ trợ

| Công cụ | Mục đích | Lệnh |
|---------|----------|------|
| go vet | Built-in lint | `go vet ./...` |
| staticcheck | Advanced lint | `staticcheck ./...` |
| golangci-lint | Meta-linter | `golangci-lint run` |
| govulncheck | CVE check | `govulncheck ./...` |
| race detector | Data race | `go test -race ./...` |
| pprof | Profiling | `go tool pprof` |
| dlv | Debugging | `dlv debug` |

## Nguồn tham khảo

- [Effective Go](https://go.dev/doc/effective_go)
- [Go Blog](https://go.dev/blog/)
- [Go Wiki: Common Mistakes](https://go.dev/wiki/CommonMistakes)
- [Go Wiki: CodeReviewComments](https://go.dev/wiki/CodeReviewComments)
- [Staticcheck Checks](https://staticcheck.dev/docs/checks/)
- [Uber Go Style Guide](https://github.com/uber-go/guide/blob/master/style.md)
