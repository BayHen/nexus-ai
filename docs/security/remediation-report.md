# Báo cáo remediation bảo mật – Task 25

## Cách đánh giá

Finding được xếp hạng theo impact, khả năng khai thác và phạm vi tenant. Trạng thái **Đã sửa** chỉ được dùng khi code và regression test đã chạy. **Mở** nghĩa là rủi ro còn tồn tại hoặc cần quyết định kiến trúc.

## Findings

| ID | Severity | Module | Finding và ảnh hưởng | Mitigation | Trạng thái xác minh |
|---|---|---|---|---|---|
| SEC-01 | High | Next.js BFF | Cookie-authenticated mutation chưa kiểm tra `Origin`; site bên ngoài hoặc same-site không tin cậy có thể thử CSRF vào write endpoint. | Từ chối `Sec-Fetch-Site: cross-site` và `Origin` khác request origin; thêm regression tests. | Đã sửa; Vitest pass |
| SEC-02 | High | Auth | Registration thực hiện Argon2id nhưng không rate limit, cho phép resource exhaustion và account spam. | Dùng limiter chung theo IP + normalized email; response 429 generic. | Đã sửa; backend tests pass |
| SEC-03 | Medium | Auth limiter | Map key có thể tăng vô hạn khi attacker thay đổi email/IP. | Giới hạn 10.000 key, prune key hết hạn và fail closed khi đầy. | Đã sửa; unit test pass |
| SEC-04 | Medium | Auth/Deployment | Limiter chỉ nằm trong một process nên không nhất quán khi scale ngang và mất state khi restart. | Redis atomic limiter + edge rate limit. | Mở – PLANNED |
| SEC-05 | Medium | MCP | MCP tái sử dụng API JWT audience, `validate_token_resource=False` và verifier gán `mcp:read` cho mọi access token hợp lệ. Tool vẫn kiểm tra tenant/RBAC nhưng token chưa resource-bound. | Phát hành MCP-specific audience/scope và bật resource validation. | Mở – cần thay đổi token contract |
| SEC-06 | Medium | Knowledge | PDF có byte/page/text cap nhưng parsing trong thread không có hard CPU/memory isolation. PDF độc hại có thể gây resource exhaustion. | Parse trong process sandbox với timeout/resource limit; theo dõi parser CVE. | Mở – PLANNED |
| SEC-07 | Medium | Frontend CSP | CSP chặn external origin và framing nhưng còn `'unsafe-inline'` cho script/style để tương thích Next.js. | Chuyển sang nonce/hash CSP trong deployment task. | Giảm thiểu một phần |
| SEC-08 | Medium | Dependencies/dev | `npm audit` báo 16 moderate advisory qua `minimatch` trong ESLint/TypeScript dev-tool chain; production dependency audit không có finding. Suggested auto-fix là downgrade major không tương thích. | Không chạy `npm audit fix --force`; theo dõi bản vá tương thích. | Mở, dev-only |
| SEC-09 | Low | FastAPI | Swagger/OpenAPI public làm tăng information disclosure ở production. | Tắt `/docs`, `/redoc`, `/openapi.json` khi `environment=production`. | Đã sửa; contract test pass |
| SEC-10 | Low | HTTP | Thiếu baseline browser security headers. | Thêm CSP, `frame-ancestors`, `X-Frame-Options`, `nosniff`, Referrer-Policy và Permissions-Policy. | Đã sửa; build pass |
| SEC-11 | Low | JWT | Logout/replay revoke refresh sessions nhưng access JWT đã phát hành còn hợp lệ tối đa 15 phút. | Chấp nhận short-lived token hiện tại; cân nhắc denylist cho sự kiện rủi ro cao. | Mở – documented trade-off |
| SEC-12 | Informational | Python dependencies | `pip check` chỉ xác minh consistency; môi trường không có `pip-audit`, nên chưa có bằng chứng CVE scan Python. | Thêm `pip-audit` vào security CI sau khi phê duyệt dependency/tooling. | BLOCKED |

## Controls đã kiểm tra không tạo finding

- Argon2id password hashing, generic login/reset responses và timing-equalized unknown-user login.
- Refresh token rotation/digest/replay behavior.
- Tenant context từ active membership; repository filters và cross-tenant tests.
- SQLAlchemy parameterized expressions, không có arbitrary SQL từ AI.
- Payment webhook HMAC, event uniqueness và transaction-safe state transition.
- Document type/signature/size/page/text validation và document ACL trước retrieval.
- AI evidence được đánh dấu untrusted; runtime tools và MCP tools có fixed allowlist.
- Structured request log không ghi authorization header, body, password, token hay document content.

## Kết quả dependency và configuration checks

| Command | Kết quả |
|---|---|
| `npm.cmd audit --omit=dev --json` | 0 production vulnerabilities |
| `npm.cmd audit --json` | 16 moderate, đều trong dev-tool dependency graph |
| `python -m pip check` | Không có broken requirements |
| `python -m pip_audit --version` | BLOCKED: module chưa được cài |
| Secret-pattern scan bằng `git grep` | Không tìm thấy credential pattern; command exit 1 vì không có match |

Kết luận này chỉ phản ánh code và dependency snapshot đã kiểm tra. Không được diễn giải là NEXUS AI hoàn toàn an toàn.
