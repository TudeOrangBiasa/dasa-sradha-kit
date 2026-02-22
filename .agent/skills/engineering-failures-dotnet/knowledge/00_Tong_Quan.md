# Bách Khoa Toàn Thư Về Lỗi Kỹ Thuật — .NET Edition
# Encyclopedia of Software Engineering Failures — .NET

> **Phiên bản:** 1.0
> **Ngày tạo:** 2026-02-18
> **Mục đích:** Tài liệu tham khảo toàn diện về các mẫu lỗi kỹ thuật phổ biến trong phát triển .NET/C#
> **Nguồn gốc:** Tổng hợp từ Microsoft docs, .NET Blog, Roslyn analyzers, OWASP, và kinh nghiệm thực tiễn

---

## Giới thiệu

Tài liệu này tổng hợp **143 mẫu lỗi kỹ thuật** phổ biến nhất trong phát triển .NET/C#, được phân loại thành **12 lĩnh vực**. Mỗi mẫu lỗi bao gồm mô tả vấn đề, cách phát hiện trong mã nguồn (kèm regex), giải pháp C# idiomatic (.NET 8+), và danh sách phòng ngừa kèm Roslyn analyzer rules.

## Mục lục

| # | Lĩnh vực | File | Số mẫu |
|---|----------|------|:------:|
| 01 | Async/Await Và Task | `01_Async_Await_Va_Task.md` | 16 |
| 02 | Hệ Thống Phân Tán | `02_He_Thong_Phan_Tan.md` | 12 |
| 03 | Bảo Mật Và Xác Thực | `03_Bao_Mat_Va_Xac_Thuc.md` | 14 |
| 04 | Entity Framework Và Dữ Liệu | `04_Entity_Framework_Va_Du_Lieu.md` | 14 |
| 05 | Quản Lý Tài Nguyên | `05_Quan_Ly_Tai_Nguyen.md` | 12 |
| 06 | Thiết Kế Và Kiến Trúc | `06_Thiet_Ke_Va_Kien_Truc.md` | 12 |
| 07 | Xử Lý Lỗi | `07_Xu_Ly_Loi.md` | 11 |
| 08 | Hiệu Năng Và Mở Rộng | `08_Hieu_Nang_Va_Mo_Rong.md` | 14 |
| 09 | Thiết Kế API | `09_Thiet_Ke_API.md` | 10 |
| 10 | Thử Nghiệm | `10_Thu_Nghiem.md` | 10 |
| 11 | Triển Khai Và Build | `11_Trien_Khai_Va_Build.md` | 8 |
| 12 | Giám Sát Và Quan Sát | `12_Giam_Sat_Va_Quan_Sat.md` | 10 |
| | **Tổng cộng** | | **143** |

## Phân bố mức nghiêm trọng

| Mức độ | Ký hiệu | Số lượng | Ý nghĩa |
|--------|----------|:--------:|---------|
| Nghiêm trọng | 🔴 CRITICAL | 30 | Async void crash, SQL injection, socket exhaustion, deadlock |
| Cao | 🟠 HIGH | 50 | N+1 queries, resource leak, DI lifetime mismatch |
| Trung bình | 🟡 MEDIUM | 55 | Performance, code smell, maintainability |
| Thấp | 🔵 LOW | 8 | Style, minor optimization |

## Đặc điểm .NET-specific

- **Async/Await** — `async void`, `.Result`/`.Wait()` deadlock, ConfigureAwait
- **Entity Framework** — N+1, tracking, DbContext lifetime
- **DI Container** — Scoped/Singleton/Transient lifetime mixing
- **IDisposable** — Resource management via `using` statement
- **LINQ** — Deferred execution, multiple enumeration
- **GC** — Gen 2 collections, LOH fragmentation

## Công cụ hỗ trợ

| Công cụ | Mục đích | Lệnh |
|---------|----------|------|
| Roslyn Analyzers | Static analysis | Built-in với `dotnet build` |
| dotnet format | Code style | `dotnet format` |
| NuGet Audit | CVE check | `dotnet list package --vulnerable` |
| dotnet-counters | Perf counters | `dotnet-counters monitor` |
| dotnet-dump | Memory analysis | `dotnet-dump collect` |
| dotnet-trace | Tracing | `dotnet-trace collect` |
| BenchmarkDotNet | Benchmarking | NuGet package |

## Nguồn tham khảo

- [Microsoft .NET Documentation](https://learn.microsoft.com/en-us/dotnet/)
- [.NET Blog](https://devblogs.microsoft.com/dotnet/)
- [ASP.NET Core Security](https://learn.microsoft.com/en-us/aspnet/core/security/)
- [EF Core Performance](https://learn.microsoft.com/en-us/ef/core/performance/)
- [Roslyn Analyzers](https://learn.microsoft.com/en-us/dotnet/fundamentals/code-analysis/overview)
- [Stephen Cleary: Async Best Practices](https://blog.stephencleary.com/)
