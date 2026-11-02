# Known issues trước release

Danh sách này chỉ bao gồm vấn đề còn mở hoặc trade-off cần công khai. Severity phản ánh impact và khả năng xảy ra trong phạm vi NEXUS AI hiện tại; không đồng nghĩa ứng dụng đã được pentest đầy đủ.

## HIGH

### REL-000 – CSRF origin validation chặn browser mutation trong Docker

- **Affected:** `frontend/src/lib/api/csrf.ts` và BFF route handler.
- **Bằng chứng runtime:** POST qua `http://127.0.0.1:3000` với `Origin` là `http://127.0.0.1:3000` hoặc `http://localhost:3000` đều trả 403 `csrf_validation_failed`; cùng POST không có `Origin` trả 201.
- **Impact:** browser fetch gửi `Origin` cho mutation nên login/register và business writes bị chặn trong Docker deployment. So sánh trực tiếp với `request.nextUrl.origin` không xử lý đúng trusted proxy/forwarded host boundary.
- **Remediation:** cấu hình explicit trusted frontend origin; chỉ tin `Forwarded`/`X-Forwarded-*` từ trusted proxy; từ chối missing Origin cho cookie-authenticated unsafe methods nếu không có non-browser contract riêng; thêm tests cho same-origin, cross-origin, proxy và Docker runtime.
- **Release:** chặn `v1.0.0`.

### REL-001 – Web session không tự refresh

- **Affected:** `frontend/src/app/api/backend/[...path]/route.ts`.
- **Bằng chứng:** BFF tạo `nexus_refresh_token` cookie khi login/register và chỉ đọc cookie đó khi logout. Không có code path gọi `/api/v1/auth/refresh` bằng cookie rồi cập nhật access/refresh cookies.
- **Impact:** sau 15 phút, request dùng access cookie hết hạn nhận 401 và UI không thể dùng refresh token `HttpOnly` để phục hồi.
- **Remediation:** thêm BFF refresh handler, rotation atomic phía client boundary, retry đúng một lần cho request idempotent, xóa cookie khi refresh bị revoke/replay; thêm Vitest và Playwright real-backend.
- **Release:** chặn `v1.0.0`.

## MEDIUM

### REL-002 – Chưa có dependency scan cho current worktree

`pip-audit`, Trivy và Terraform CLI không có local; `npm audit` không truy cập được advisory endpoint trong phiên audit. CI có Trivy gate nhưng chưa chạy trên current worktree. Không được suy diễn “không có vulnerability”.

### REL-003 – MCP token chưa resource-bound

MCP verifier chấp nhận API audience, gán `mcp:read` và đặt `validate_token_resource=False`. Tool vẫn resolve tenant và RBAC nên chưa có bằng chứng cross-tenant bypass, nhưng token contract chưa tách resource/audience.

### REL-004 – Rate limit không dùng distributed state

Limiter authentication nằm trong memory của từng API process. Scale ngang hoặc restart làm thay đổi enforcement. Cần Redis atomic limiter và edge/WAF policy trước multi-instance production.

### REL-005 – PDF parser chưa có hard isolation

Upload có size/type/signature/page/text caps, nhưng parsing trong thread không giới hạn cứng CPU/RAM. Cần process sandbox, timeout và dependency monitoring.

### REL-006 – Browser E2E chưa chứng minh full application journey

Hai Playwright test hiện tập trung AI assistant và dùng route mocks. Chưa có browser test dùng FastAPI/PostgreSQL thật cho auth, tenant, product/inventory/order/payment.

### REL-007 – Cloud operations chưa được diễn tập

AWS chưa deploy. Terraform format pass nhưng init/validate chưa chạy local; backup/restore, migration rollback strategy và ECS rollback chưa được diễn tập trên staging.

## LOW

### REL-008 – CSP còn `unsafe-inline`

Next.js compatibility hiện cần inline script/style. Tiếp tục render dữ liệu không tin cậy dưới dạng text và chuyển sang nonce/hash CSP khi deployment hỗ trợ.

### REL-009 – GitHub Actions chưa pin SHA

Official actions và Trivy action dùng version tag. Nên pin full commit SHA và dùng dependency update automation có review.

### REL-010 – Access token revocation có độ trễ

Logout/reset/replay revoke refresh sessions; access JWT hiện tại có thể hợp lệ đến hết TTL 15 phút. Đây là trade-off stateless JWT, cần risk assessment nếu áp dụng cho dữ liệu nhạy cảm hơn.

## Không phải finding đã xác nhận

- Không phát hiện cross-tenant bypass trong các đường dẫn đã test.
- Không phát hiện arbitrary model-generated SQL hoặc privileged MCP database tool.
- Không phát hiện plaintext password, refresh token hoặc payment card storage.
- Không có bằng chứng AWS deployment hoặc production capacity; đây là trạng thái chưa xác minh, không phải sự cố runtime.
