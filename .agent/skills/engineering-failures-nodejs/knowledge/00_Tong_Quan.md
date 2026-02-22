# Bách Khoa Toàn Thư Về Lỗi Kỹ Thuật — Node.js Edition
# Encyclopedia of Software Engineering Failures — Node.js

> **Phiên bản:** 1.0
> **Ngày tạo:** 2026-02-18
> **Mục đích:** Tài liệu tham khảo toàn diện về các mẫu lỗi kỹ thuật phổ biến trong phát triển Node.js/TypeScript
> **Nguồn gốc:** Tổng hợp từ Node.js docs, TypeScript handbook, OWASP, npm advisories, và kinh nghiệm thực tiễn

---

## Giới thiệu

Tài liệu này tổng hợp **145 mẫu lỗi kỹ thuật** phổ biến nhất trong phát triển Node.js/TypeScript, được phân loại thành **12 lĩnh vực**. Mỗi mẫu lỗi bao gồm mô tả vấn đề, cách phát hiện trong mã nguồn (kèm regex), giải pháp TypeScript idiomatic, và danh sách phòng ngừa kèm ESLint rules.

## Mục lục

| # | Lĩnh vực | File | Số mẫu |
|---|----------|------|:------:|
| 01 | Event Loop Và Async | `01_Event_Loop_Va_Async.md` | 18 |
| 02 | Hệ Thống Phân Tán | `02_He_Thong_Phan_Tan.md` | 12 |
| 03 | Bảo Mật Web | `03_Bao_Mat_Web.md` | 16 |
| 04 | Toàn Vẹn Dữ Liệu | `04_Toan_Ven_Du_Lieu.md` | 10 |
| 05 | Quản Lý Tài Nguyên | `05_Quan_Ly_Tai_Nguyen.md` | 12 |
| 06 | TypeScript Và Kiểu | `06_TypeScript_Va_Kieu.md` | 12 |
| 07 | Xử Lý Lỗi | `07_Xu_Ly_Loi.md` | 12 |
| 08 | Hiệu Năng Và Mở Rộng | `08_Hieu_Nang_Va_Mo_Rong.md` | 13 |
| 09 | Thiết Kế API | `09_Thiet_Ke_API.md` | 10 |
| 10 | Thử Nghiệm | `10_Thu_Nghiem.md` | 10 |
| 11 | NPM Và Dependencies | `11_NPM_Va_Dependencies.md` | 10 |
| 12 | Giám Sát Và Quan Sát | `12_Giam_Sat_Va_Quan_Sat.md` | 10 |
| | **Tổng cộng** | | **145** |

## Phân bố mức nghiêm trọng

| Mức độ | Ký hiệu | Số lượng | Ý nghĩa |
|--------|----------|:--------:|---------|
| Nghiêm trọng | 🔴 CRITICAL | 30 | Event loop block, prototype pollution, supply chain attack |
| Cao | 🟠 HIGH | 52 | Memory leak, unhandled rejection, XSS, type safety loss |
| Trung bình | 🟡 MEDIUM | 55 | Code smell, performance, non-idiomatic patterns |
| Thấp | 🔵 LOW | 8 | Style, minor optimization |

## Đặc điểm Node.js-specific

- **Single-threaded event loop** — CPU-bound work blocks everything
- **Async/Await pitfalls** — Floating promises, unhandled rejections
- **npm ecosystem** — Supply chain attacks, dependency hell
- **TypeScript gap** — Types disappear at runtime
- **Memory leaks** — Closures, event listeners, global caches
- **Prototype pollution** — Deep merge attacks

## Công cụ hỗ trợ

| Công cụ | Mục đích | Lệnh |
|---------|----------|------|
| ESLint | Lint | `npx eslint .` |
| TypeScript | Type check | `npx tsc --noEmit` |
| npm audit | CVE check | `npm audit` |
| clinic.js | Profiling | `npx clinic doctor` |
| depcheck | Unused deps | `npx depcheck` |
| madge | Circular deps | `npx madge --circular .` |
| knip | Dead code | `npx knip` |

## Nguồn tham khảo

- [Node.js Best Practices](https://github.com/goldbergyoni/nodebestpractices)
- [TypeScript Handbook](https://www.typescriptlang.org/docs/handbook/)
- [OWASP Node.js Security](https://cheatsheetseries.owasp.org/cheatsheets/Nodejs_Security_Cheat_Sheet.html)
- [npm Security Best Practices](https://docs.npmjs.com/packages-and-modules/securing-your-code)
- [Node.js Diagnostics Guide](https://nodejs.org/en/docs/guides/diagnostics)
