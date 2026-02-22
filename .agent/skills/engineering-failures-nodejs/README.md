# Engineering Failures Audit Skill — Node.js Edition

## Giới thiệu

Bộ công cụ tự động quét mã nguồn Node.js/TypeScript để phát hiện **145 mẫu lỗi kỹ thuật phổ biến**, phân loại thành **12 lĩnh vực**.

## Sử dụng

```bash
# Quét toàn bộ
/ef-node

# Chỉ quét domain cụ thể
/ef-node 01    # Event Loop & Async
/ef-node 03    # Web Security
/ef-node 11    # NPM & Dependencies

# Chỉ quét theo mức nghiêm trọng
/ef-node critical

# Quét project khác
/ef-node all /path/to/node-project
```

## 12 Lĩnh vực

| # | Lĩnh vực | Số mẫu |
|---|----------|:------:|
| 01 | Event Loop Và Async | 18 |
| 02 | Hệ Thống Phân Tán | 12 |
| 03 | Bảo Mật Web | 16 |
| 04 | Toàn Vẹn Dữ Liệu | 10 |
| 05 | Quản Lý Tài Nguyên | 12 |
| 06 | TypeScript Và Kiểu | 12 |
| 07 | Xử Lý Lỗi | 12 |
| 08 | Hiệu Năng Và Mở Rộng | 13 |
| 09 | Thiết Kế API | 10 |
| 10 | Thử Nghiệm | 10 |
| 11 | NPM Và Dependencies | 10 |
| 12 | Giám Sát Và Quan Sát | 10 |
| | **Tổng** | **145** |

## Ngôn ngữ hỗ trợ

- TypeScript / JavaScript (Express, NestJS, Fastify, Next.js, Prisma, TypeORM)

## Tích hợp công cụ

- `ESLint` — Lint
- `tsc --noEmit` — Type check
- `npm audit` — CVE check
- `clinic.js` — Performance profiling
- `knip` — Dead code detection
- `madge` — Circular dependency
