# Engineering Failures Audit Skill — .NET Edition

## Giới thiệu

Bộ công cụ tự động quét mã nguồn .NET/C# để phát hiện **143 mẫu lỗi kỹ thuật phổ biến**, phân loại thành **12 lĩnh vực**.

## Sử dụng

```bash
# Quét toàn bộ
/ef-dotnet

# Chỉ quét domain cụ thể
/ef-dotnet 01    # Async/Await & Task
/ef-dotnet 04    # Entity Framework
/ef-dotnet 05    # Resource Management

# Chỉ quét theo mức nghiêm trọng
/ef-dotnet critical

# Quét project khác
/ef-dotnet all /path/to/dotnet-project
```

## 12 Lĩnh vực

| # | Lĩnh vực | Số mẫu |
|---|----------|:------:|
| 01 | Async/Await Và Task | 16 |
| 02 | Hệ Thống Phân Tán | 12 |
| 03 | Bảo Mật Và Xác Thực | 14 |
| 04 | Entity Framework Và Dữ Liệu | 14 |
| 05 | Quản Lý Tài Nguyên | 12 |
| 06 | Thiết Kế Và Kiến Trúc | 12 |
| 07 | Xử Lý Lỗi | 11 |
| 08 | Hiệu Năng Và Mở Rộng | 14 |
| 09 | Thiết Kế API | 10 |
| 10 | Thử Nghiệm | 10 |
| 11 | Triển Khai Và Build | 8 |
| 12 | Giám Sát Và Quan Sát | 10 |
| | **Tổng** | **143** |

## Ngôn ngữ hỗ trợ

- C# / .NET 8+ (ASP.NET Core, EF Core, MassTransit, MediatR, gRPC)

## Tích hợp công cụ

- Roslyn Analyzers — Built-in static analysis
- `dotnet format` — Code style
- `dotnet list package --vulnerable` — CVE check
- `dotnet-counters` — Performance counters
- `dotnet-dump` — Memory analysis
- BenchmarkDotNet — Micro-benchmarking
