# Báo cáo release readiness NEXUS AI

## Kết luận

**Trạng thái: CHƯA SẴN SÀNG cho `v1.0.0`.**

Audit ngày 01/11/2026 không phát hiện finding `CRITICAL`, nhưng còn hai finding `HIGH` tại Next.js BFF. Trong Docker, browser mutation có `Origin` hợp lệ vẫn bị CSRF guard trả 403; ngoài ra refresh token được lưu trong cookie `HttpOnly` nhưng BFF chưa có luồng rotate và cập nhật access cookie. Vì authentication/user journey cốt lõi chưa hoạt động bền vững, repository chưa đạt tiêu chí đề xuất `v1.0.0`.

Không tạo Git tag, không push image, không provision AWS và không deploy trong Task 30.

## Phạm vi và phương pháp

Audit đối chiếu source code, migration, tests, workflow, Terraform, Docker Compose, tài liệu và runtime local. Kết quả được chia thành:

- **Đã xác minh:** có command hoặc test thực thi trong phiên audit.
- **Static review:** đọc cấu hình/code nhưng chưa chạy trên dịch vụ đích.
- **Chưa xác minh:** thiếu công cụ, network, cloud account hoặc bài test phù hợp.

## Kết quả theo phạm vi

| Phạm vi | Kết quả | Bằng chứng | Trạng thái |
|---|---|---|---|
| Architecture consistency | Module business tách domain/application/infrastructure/presentation; shared platform nằm ngoài module | Ruff, mypy và review dependency path | Đã xác minh một phần |
| API contracts | FastAPI OpenAPI khởi tạo được; contract/error/health tests nằm trong full suite | 124 backend tests pass | Đã xác minh |
| Database migrations | Một Alembic head `20261031_0013`; database local đang ở head; upgrade trên database tạm nằm trong integration suite | `alembic heads`, `alembic current`, pytest | Đã xác minh |
| Authentication/authorization | Argon2id, JWT issuer/audience/expiry, refresh digest/rotation, generic errors và RBAC có tests | Full pytest; static security review | Đạt backend; frontend refresh còn HIGH |
| Tenant isolation | Active tenant resolve từ membership phía server; repository/service filter theo organization; malicious-ID tests | Integration suite | Đã xác minh |
| Product/inventory | Decimal validation, tenant SKU, row lock, idempotency và movement ledger | Integration/concurrency tests trong full suite | Đã xác minh |
| Order/payment | Server totals, price snapshot, state machine, stock transaction, webhook HMAC/idempotency và audit | Integration/concurrency tests | Đã xác minh |
| Background reliability | Worker import/startup, RabbitMQ connection, retry/idempotency/job state/outbox tests | Worker healthy; full pytest | Đã xác minh local |
| AI/RAG | Document ACL, tenant-filtered retrieval, citations/no-answer và fixed tool registry | Evaluation/integration tests dùng deterministic provider | Đã xác minh deterministic; live model chưa xác minh |
| MCP security | Bốn tool read-only, JWT decode, active tenant và RBAC | MCP integration/evaluation tests | Đạt nền tảng; resource-bound token còn MEDIUM |
| Frontend integration | Typecheck, lint, component tests, build và assistant E2E đạt | 16 Vitest + 2 Playwright | Không đạt release: Docker BFF mutation 403; auth refresh/full workflow chưa E2E |
| CI/CD | Workflow có least-privilege permissions, image scan gate, migration-before-service-update và manual staging environment | Static review | Chưa chạy workflow trên current worktree |
| Monitoring/logs | JSON allowlist logging, request/trace IDs, API/DB/worker metrics, Prometheus/Grafana/Tempo/OTel local | Endpoint và scrape-target checks | Đã xác minh local |
| README accuracy | Đã cập nhật kết quả Task 30, release status và giới hạn | Link/path review | Đã xác minh |
| Skills | Registry khớp filesystem và invalid fixtures fail | 14 skills; 9 tests pass | Đã xác minh |

## Findings

| ID | Severity | Module | Finding | Ảnh hưởng | Trạng thái |
|---|---|---|---|---|---|
| REL-000 | HIGH | Next.js BFF/CSRF | Trong Docker, POST có `Origin: http://127.0.0.1:3000` hoặc `http://localhost:3000` bị 403; cùng POST không có Origin được chuyển tiếp | Login/register và mọi browser mutation không hoạt động; origin comparison không phản ánh proxy boundary | Mở, chặn v1.0.0 |
| REL-001 | HIGH | Next.js BFF/Auth | Refresh cookie được tạo nhưng không có handler dùng cookie để gọi backend refresh và rotate lại cookies | Phiên dashboard hỏng sau access-token TTL; người dùng phải đăng nhập lại | Mở, chặn v1.0.0 |
| REL-002 | MEDIUM | Security CI | `pip-audit` và Trivy không có local; `npm audit` hiện không truy cập được advisory endpoint | Chưa có CVE evidence cho current worktree ngoài cấu hình CI | Mở |
| REL-003 | MEDIUM | MCP | API JWT được gán `mcp:read`; resource validation tắt | Token chưa audience/resource-bound riêng cho MCP | Mở |
| REL-004 | MEDIUM | Availability | Authentication limiter là in-memory theo process | Không nhất quán khi scale ngang hoặc restart | Mở |
| REL-005 | MEDIUM | File ingestion | PDF parsing chưa cách ly bằng process/resource hard limit | File độc hại có thể gây resource exhaustion | Mở |
| REL-006 | MEDIUM | Release verification | Playwright chỉ kiểm tra assistant với route mocks; chưa có real-backend browser flow cho auth → tenant → business workflow | Frontend/backend contract regression có thể lọt | Mở |
| REL-007 | MEDIUM | Deployment | AWS chưa provision; Terraform validate, backup/restore, rollback và failure drill chưa chạy trong môi trường staging | Không có bằng chứng vận hành cloud end-to-end | Mở |
| REL-008 | LOW | Web security | CSP vẫn cần `'unsafe-inline'` cho compatibility | XSS defense-in-depth yếu hơn nonce/hash CSP | Chấp nhận tạm thời |
| REL-009 | LOW | Supply chain | GitHub Actions chủ yếu pin theo major/version tag, không pin commit SHA | Rủi ro mutable action reference | Mở |
| REL-010 | LOW | Auth | Access JWT đã phát hành còn hợp lệ tối đa 15 phút sau logout/replay | Revocation không tức thời cho access token | Trade-off đã biết |

## Automated verification thực tế

| Command/nhóm kiểm tra | Kết quả |
|---|---|
| Ruff | Pass |
| mypy strict | Pass trên 142 source files |
| pytest với PostgreSQL local | 124 pass, 0 skip, coverage 90% |
| Critical coverage gates | Tất cả module critical vượt target |
| Frontend typecheck/lint | Pass |
| Vitest | 16 pass |
| Next.js production build | Pass, 14 routes được build |
| Playwright | 2 pass trên Chromium desktop/mobile |
| Skills validator | 14 skills hợp lệ |
| Skills tests | 9 pass |
| Compose config | Pass |
| Alembic | Một head; runtime database ở head |
| Terraform format | Pass bằng `hashicorp/terraform:1.10.5` |
| Terraform init/validate | Chưa chạy: local CLI không có; cần CI hoặc môi trường có provider cache/network |
| Dependency/CVE scan | Chưa xác minh current worktree: công cụ/network không sẵn sàng |
| Observability | API metrics, Prometheus readiness/targets và Grafana health HTTP 200; 4 scrape jobs `up` |

Lượt pytest đầu tiên bị invalid vì toàn bộ Docker stack bị dừng từ bên ngoài. Sau khi khởi động lại PostgreSQL, full suite được chạy lại và đạt 124/124; chỉ kết quả chạy lại được dùng làm release evidence.

## Điều kiện xem xét lại

Chỉ đánh giá lại `v1.0.0` sau khi:

1. Sửa REL-000 bằng trusted-origin/proxy-aware validation, đồng thời giữ nguyên việc từ chối cross-site mutation; có Docker/BFF regression tests.
2. Sửa REL-001 và có tests cho success, expiry, invalid/revoked/replayed refresh token và cookie rotation.
3. Có real-backend Playwright flow ít nhất cho đăng ký/đăng nhập, tenant activation và một business read/write.
4. Chạy dependency/container scan trên đúng commit release và xử lý mọi `HIGH`/`CRITICAL` reachable.
5. Chạy Terraform `init -backend=false` và `validate`; nếu staging được phê duyệt, thực hiện backup/restore và rollback drill.
6. Tất cả mục bắt buộc trong `v1.0-checklist.md` được đánh dấu bằng link tới bằng chứng.
