# Lộ trình triển khai NEXUS AI – 30 Task

## Nguyên tắc thực hiện

- Mỗi Task có phạm vi độc lập, đầu ra kiểm chứng được và không tự động kéo theo Task kế tiếp.
- Tất cả Task chưa hoàn thành được ghi là **PLANNED**.
- Mỗi Task phải cập nhật tài liệu tiếng Việt, `.env.example` khi cần và báo cáo lệnh kiểm tra thực tế.
- Security, tenant isolation, transaction safety và observability là yêu cầu xuyên suốt.

## Danh sách Task

### Task 01 – Khởi tạo dự án và kiến trúc — HOÀN THÀNH

Tạo cấu trúc repository, quy tắc Codex, chính sách ngôn ngữ, tài liệu kiến trúc, cấu hình môi trường mẫu và roadmap. Không triển khai business module.

### Task 02 – Bootstrap backend Python/FastAPI — PLANNED

Khởi tạo package Python, quản lý dependency tối thiểu, application factory, cấu hình typed, health endpoint và bộ kiểm tra nền tảng.

### Task 03 – Môi trường phát triển bằng Docker Compose — PLANNED

Tạo container cho API, PostgreSQL, Redis và RabbitMQ; thêm health check, volume và lệnh phát triển nhất quán.

### Task 04 – Nền tảng persistence và Alembic — PLANNED

Cấu hình SQLAlchemy 2 async, session/transaction boundary, metadata convention, Alembic và migration kiểm chứng đầu tiên.

### Task 05 – Tenant foundation và isolation — PLANNED

Thiết kế tenant model, tenant context, repository guard, constraint/index theo tenant và test truy cập chéo tenant.

### Task 06 – Module tổ chức và thành viên — PLANNED

Triển khai aggregate tổ chức, membership, invitation và các use case cơ bản theo Clean Architecture.

### Task 07 – Authentication an toàn — PLANNED

Triển khai đăng ký/đăng nhập, password hashing, access/refresh token, rotation, revocation và session audit.

### Task 08 – RBAC theo tenant — PLANNED

Thiết kế role, permission, policy enforcement, dependency FastAPI và test matrix authorization.

### Task 09 – REST API foundation — PLANNED

Chuẩn hóa `/api/v1`, error envelope, pagination, filtering, correlation ID, idempotency contract và OpenAPI validation.

### Task 10 – Audit log và security baseline — PLANNED

Ghi audit event bất biến, redact dữ liệu nhạy cảm, rate limit, security headers và baseline threat model.

### Task 11 – Product Catalog Management — HOÀN THÀNH

Triển khai Product/Category, SKU theo tenant, Decimal price, search/filter/pagination, soft delete và constraint database.

### Task 12 – Inventory Management — HOÀN THÀNH

Triển khai stock theo Branch/Product, adjustment, transfer, low-stock threshold, policy tồn kho âm, idempotency và immutable movement ledger.

### Task 13 – Inventory Reliability & Integration — HOÀN THÀNH

Audit Product/Inventory bằng integration test cho concurrency, rollback, tenant isolation, pagination/search, dataset lớn và migration compatibility. Xem [báo cáo Task 13](../reliability/product-inventory-task13.md).

### Task 14 – Order Management System — HOÀN THÀNH

Triển khai draft Order, item mutations, state transition, immutable pricing snapshot, server-side totals và transaction-safe Inventory deduction/restoration. Xem [kiến trúc Order Management](../architecture/orders.md).

### Task 15 – Secure Payment Processing — HOÀN THÀNH

Triển khai Payment provider abstraction, sandbox intent/refund state, idempotency, HMAC webhook, duplicate protection, atomic Order completion và immutable financial audit. Xem [kiến trúc Payment](../architecture/payments.md).

### Task 16 – Order and Payment Reliability — HOÀN THÀNH

Triển khai PostgreSQL transactional outbox, leased local worker, retry/backoff, dead-letter, idempotent inbox consumer, correlation, immutable business audit và reconciliation. RabbitMQ/Celery publisher vẫn **PLANNED**. Xem [tài liệu reliability](../architecture/order-payment-reliability.md).

### Task 17 – Redis cache và distributed controls — HOÀN THÀNH NỀN TẢNG

Thiết kế cache key theo tenant, invalidation, rate limiting và distributed lock chỉ ở nơi có bằng chứng cần thiết.

### Task 18 – Background processing với Celery và RabbitMQ — HOÀN THÀNH NỀN TẢNG

Tạo notification preference, template, channel adapter, job nền và lịch sử gửi có retry an toàn.

### Task 19 – Revenue & Business Analytics — HOÀN THÀNH NỀN TẢNG

Triển khai revenue recognition, refund reconciliation, order/product/branch metrics, inventory valuation và CSV/XLSX export bất đồng bộ.

### Task 20 – Knowledge ingestion và pgvector — HOÀN THÀNH NỀN TẢNG

Triển khai document ingestion, chunking, embedding, vector schema, tenant isolation và pipeline bất đồng bộ.

### Task 21 – Business Intelligence AI Agent — HOÀN THÀNH NỀN TẢNG

Triển khai LangGraph hữu hạn với năm tool phân tích/RAG chỉ đọc, typed contracts, tenant authorization, timeout, immutable invocation audit, citation và evaluation tích hợp.

### Task 22 – MCP Integration và AI Evaluation — HOÀN THÀNH NỀN TẢNG

Triển khai MCP server stateless với four-tool allowlist chỉ đọc, JWT/tenant authorization, schema validation, audit và deterministic evaluation baseline.

### Task 23 – Enterprise Dashboard — HOÀN THÀNH NỀN TẢNG

Triển khai login/register, organization selection, role-aware responsive shell, analytics và các màn hình nghiệp vụ đọc dữ liệu thật qua typed BFF API.

### Task 24 – AI Assistant & Analytics UI — HOÀN THÀNH

Tích hợp AI chat, lịch sử theo organization, upload/indexing status, citations, tool status, analytics date range, revenue comparison, inventory alerts và kiểm thử component/E2E.

Khởi tạo TypeScript, layout, design tokens, API client typed, authentication shell và test nền tảng.

### Task 25 – Security Engineering Audit — HOÀN THÀNH

Threat model, checklist, remediation report và các sửa lỗi ưu tiên cao cho CSRF, auth rate limiting, limiter memory bound, production API docs và browser security headers.

Triển khai dashboard, tenant switcher và UI cho các module đã có, với loading/error/accessibility states.

### Task 26 – Testing & Performance Engineering — HOÀN THÀNH

Thiết lập workflow xác minh tổng hợp cho unit, API, PostgreSQL transaction, tenant isolation, authorization, concurrency, browser E2E và AI evaluation; bổ sung coverage gate theo module, Locust load test bằng dữ liệu synthetic, CI và báo cáo benchmark có thể tái lập.

### Task 27 – CI/CD & Cloud Deployment — HOÀN THÀNH CẤU HÌNH

Bổ sung production container images, local Compose đầy đủ, CI quality/delivery gates, Trivy scanning, GitHub OIDC deployment workflow, Terraform cho AWS staging và runbook rollback. Việc provision/deploy AWS vẫn **BLOCKED** cho tới khi có phê duyệt chi phí và credentials phù hợp.

### Task 28 – Terraform và AWS foundation — PLANNED

Thiết kế network, compute, database, cache, queue, storage, secrets, IAM và remote state theo least privilege.

### Task 29 – Observability, performance và resilience — PLANNED

Thêm structured logging, metrics, tracing, dashboard, alert, load test, backup/restore và failure drills.

### Task 30 – Production hardening và portfolio release — PLANNED

Hoàn tất security review, tenant isolation review, runbook, demo data, architecture diagrams, release checklist và portfolio narrative.

## Mốc phát hành

| Mốc | Task | Kết quả |
|---|---|---|
| Nền móng | 01–10 | Backend foundation, multi-tenancy, auth và security baseline |
| Nghiệp vụ | 11–18 | Workflow quản trị doanh nghiệp và xử lý nền |
| AI | 19–23 | OpenAI, RAG, LangGraph và MCP có kiểm soát |
| Sản phẩm | 24–26 | Frontend và hành trình E2E |
| Vận hành | 27–30 | CI/CD, AWS, observability và bản phát hành portfolio |
