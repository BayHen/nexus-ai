# Hướng dẫn phỏng vấn kỹ thuật với NEXUS AI

## Mục đích

Tài liệu này giúp trình bày NEXUS AI như một hệ thống có quyết định và bằng chứng, không phải danh sách công nghệ. Khi trả lời, phân biệt rõ implementation trong repository, kết quả test đã chạy và phần chưa deploy.

## Bài giới thiệu 60 giây

> NEXUS AI là Modular Monolith cho quản trị doanh nghiệp đa tenant. Tôi dùng FastAPI, SQLAlchemy và PostgreSQL để xây transaction-safe workflow cho Inventory, Order và Payment; tenant isolation/RBAC được thực thi phía server. Celery, RabbitMQ, Redis và transactional outbox xử lý async/reliability. Phần AI gồm pgvector RAG và LangGraph agent chỉ gọi read-only tools có authorization/audit, cùng MCP adapter giới hạn. Next.js cung cấp dashboard; pytest, Playwright, Locust, OpenTelemetry và Terraform tạo bằng chứng về quality và vận hành. AWS staging đã được định nghĩa nhưng chưa provision.

## Trình tự trình bày 10 phút

1. Bài toán: dữ liệu và audit bị phân mảnh giữa catalog, stock, order, payment và knowledge.
2. Kiến trúc: mở Mermaid diagram trong README; giải thích vì sao Modular Monolith.
3. Security boundary: JWT → membership → active organization → permission → tenant-scoped query.
4. Workflow khó nhất: Order confirmation hoặc Payment webhook trong transaction.
5. Reliability: outbox/inbox, idempotency, retry/dead-letter, correlation ID.
6. AI safety: retrieved content untrusted, tool allowlist, không model-generated SQL.
7. Evidence: tenant/concurrency/rollback tests, coverage gates, benchmark có giới hạn.
8. Operations: health/readiness, JSON logs, Prometheus, traces, alerts và rollback.
9. Trade-off và limitation: single-AZ staging, sandbox providers, chưa public deploy.

## Code path nên mở

| Chủ đề | Điểm bắt đầu | Điều cần chỉ ra |
|---|---|---|
| Composition | `backend/src/nexus/bootstrap/application.py` | Factory, dependency composition, telemetry, fail-fast DB |
| Transaction | `backend/src/nexus/platform/database/manager.py` | `session.begin()`, pool/SQL metrics không lộ query |
| Tenant/RBAC | `backend/src/nexus/modules/organizations/` | Active tenant từ auth context, permission checks |
| Inventory | `backend/src/nexus/modules/inventory/` | Atomic update/locking, movement ledger, idempotency |
| Order | `backend/src/nexus/modules/orders/` | State machine, server totals, price snapshots |
| Payment | `backend/src/nexus/modules/payments/` | Provider interface, HMAC, duplicate webhook protection |
| Reliability | `backend/src/nexus/platform/reliability/` | Outbox lease, inbox receipt, reconciliation |
| RAG | `backend/src/nexus/modules/knowledge/` | Validation, chunk/vector tenant filter, citations |
| Agent | `backend/src/nexus/modules/business_agent/` | Typed tools, transitions, read-only policy, audit |
| MCP | `backend/src/nexus/mcp/` | Approved tool surface và auth boundary |
| Frontend | `frontend/src/app/` và `frontend/src/lib/` | BFF, typed client, safe rendering, API error state |
| Delivery | `.github/workflows/`, `infrastructure/terraform/` | OIDC, scan, migrate-before-update, no apply claim |

## Câu hỏi thường gặp

### Vì sao không microservices?

Domain và team size chưa biện minh distributed transactions, service discovery và operational overhead. Module ownership vẫn rõ; outbox tạo seam nếu một capability cần tách sau này.

### Tenant isolation được chứng minh thế nào?

Tenant không lấy từ body/query. Authentication resolve membership và active organization; service/repository query luôn có tenant predicate; uniqueness/FK chứa tenant scope khi cần. Negative integration tests dùng ID của tenant khác.

### Làm sao tránh overselling security?

Nêu threat model, remediation report và test boundary, sau đó nói rõ không có hệ thống “fully secure”. WAF, production DR và live penetration test chưa có.

### Tại sao dùng row lock?

Inventory/order confirmation có invariant không âm và chỉ confirm một lần. Lock/atomic update trong cùng transaction ưu tiên correctness. Với write scale cao hơn có thể partition/hot-key analysis hoặc reservation model riêng.

### Payment retry có charge hai lần không?

Request có idempotency key; webhook có signature và durable duplicate record; state transition khóa row và chỉ hoàn thành order một lần. Provider hiện là sandbox, không tuyên bố PCI integration.

### RAG có chống prompt injection tuyệt đối không?

Không. Retrieved text bị coi là data, không policy; agent chỉ có allowlisted read-only tools và authorization server-side. Evaluation bao phủ injection cases nhưng không chứng minh mọi attack đều bị chặn.

### Coverage 89% có nghĩa gì?

Đó là Task 26 full-suite line/branch-aware signal, không phải bằng chứng duy nhất. Assertions về transaction rollback, cross-tenant denial, concurrency và invalid transitions mới chứng minh risk quan trọng.

### Benchmark có đại diện production không?

Không. 168,72 req/s và p95 7 ms là loopback HTTP baseline cho hai public endpoint, 25 synthetic clients trong 20 giây, không có database/auth/business work.

### AWS đã chạy chưa?

Chưa. Terraform validate và container builds đã chạy local; không có `terraform apply`, ECR push hoặc public URL. Đây là ranh giới chi phí/quyền được giữ có chủ ý.

## STAR stories có thể dùng

### Concurrency và consistency

- Situation: hai request cùng trừ stock/confirm order.
- Task: giữ stock/order invariant sau concurrent/failure paths.
- Action: PostgreSQL transaction, row lock, state transition validation, idempotency, rollback tests.
- Result: các concurrency/rollback scenarios pass trong integration suite; không dựa vào frontend lock.

### AI authorization

- Situation: model có thể chọn sai tool hoặc retrieved document chứa instruction độc hại.
- Task: bảo đảm AI không vượt quyền tenant.
- Action: typed tool schemas, trusted tenant context, allowlist read-only, timeout, immutable audit, citation/no-answer.
- Result: evaluation test tool selection, injection boundary và tenant isolation; limitation được ghi rõ.

### Delivery safety

- Situation: deploy image mới có migration.
- Task: không chuyển service nếu migration lỗi.
- Action: Git SHA image, OIDC, Trivy, đăng ký task revision, migration one-off, chỉ update ECS sau exit code 0.
- Result: workflow/config được validate; deployment thực tế chưa chạy.

## Checklist trước phỏng vấn

- Chạy demo script bằng synthetic data và ghi lại command/result mới nhất.
- Không dùng con số Task cũ như kết quả hiện tại nếu chưa chạy lại.
- Chuẩn bị giải thích một test thất bại từng phát hiện lỗi thật.
- Mở sẵn README architecture diagram, threat model, benchmark report và một workflow.
- Nói “chưa deploy/chưa verify” khi không có bằng chứng.

