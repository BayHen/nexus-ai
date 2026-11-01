# Các quyết định kỹ thuật quan trọng

## Cách đọc

Mỗi quyết định ghi context, lựa chọn, hệ quả và điều kiện xem xét lại. Đây không phải tuyên bố một công nghệ luôn tốt hơn công nghệ khác.

## Bảng quyết định

| Quyết định | Lựa chọn | Lựa chọn thay thế | Lý do chính | Chi phí/trade-off |
|---|---|---|---|---|
| Kiến trúc backend | Modular Monolith | Microservices | Transaction và module collaboration đơn giản, phù hợp scope/team | Cần enforcement boundary; scale theo deployment unit |
| Persistence | PostgreSQL + SQLAlchemy 2 | NoSQL-first | Relational invariants, transaction, lock, reporting, pgvector cùng nền | Schema/migration discipline; hot rows có thể contention |
| Tenant model | Shared schema + `organization_id` | Database/schema per tenant | Chi phí staging thấp, query/report đơn giản | Mọi persistence boundary phải tenant-aware |
| Auth | JWT access + opaque rotating refresh | Server session only | API stateless ngắn hạn, refresh revocation/audit | Token lifecycle phức tạp; CSRF/BFF policy cần rõ |
| Stock correctness | Row locking/atomic transaction | Eventual stock ledger only | Chặn negative stock và concurrent oversell | Throughput giảm trên hot product/branch |
| Async consistency | Transactional outbox/inbox | Dual-write trực tiếp broker | DB commit và event intent atomic | Eventual delivery, worker/reconciliation complexity |
| Cache | Redis cache-aside fail-open | Write-through/fail-closed | Không dùng cache để bypass auth; Redis lỗi không làm API mất hoàn toàn | DB load tăng khi cache down; invalidation khó |
| Payment | Provider interface + sandbox | Gắn trực tiếp provider thật | Test state/idempotency không xử lý card | Chưa chứng minh provider/PCI production integration |
| RAG vector store | pgvector | Dedicated vector database | Tenant/business data cùng transaction/backup boundary | Scale/vector tuning giới hạn hơn hệ chuyên dụng |
| Agent orchestration | Explicit LangGraph state + typed tools | Free-form autonomous loop | Audit, timeout và transition dễ test | Ít linh hoạt hơn agent tự trị |
| Agent SQL | Curated service tools | Model-generated SQL | Authorization/business formula nằm server-side | Phải viết tool mới cho câu hỏi mới |
| MCP | Dedicated read-only adapter | Expose DB/generic RPC | Interoperability nhưng giữ allowlist/tenant boundary | Tool surface nhỏ; auth integration cần client support |
| Frontend integration | Next.js BFF + typed client | Browser gọi FastAPI trực tiếp | HttpOnly cookie/same-origin boundary và server config | Thêm proxy hop, phải propagate error/correlation |
| Background worker | Celery + RabbitMQ | In-process task/cron | Durable broker/retry/visibility | Vận hành thêm broker/worker |
| Telemetry | OTel + Prometheus + Tempo + Grafana | Vendor-only APM | Portable, local verification, bounded metrics | Tự vận hành; alert routing/AWS collection còn thiếu |
| Staging compute | ECS Fargate | EKS/Kubernetes, EC2 Compose | Ít operational overhead, OIDC/ECS rollout | ALB/managed services có fixed cost; single-AZ mặc định |
| CI credentials | GitHub OIDC | Long-lived AWS keys | Short-lived và trust policy scope | Cần bootstrap IAM/OIDC ngoài application state |

## Invariant và enforcement layer

| Invariant | Enforcement |
|---|---|
| Email/SKU/idempotency uniqueness | PostgreSQL constraints + conflict handling |
| Tenant ownership | Auth context, service filters, composite constraints/FK khi cần |
| Price/amount không âm | Pydantic/domain validation + DB constraints |
| Stock không âm | Row lock/atomic mutation + transaction |
| Order transition hợp lệ | Domain state machine + locked persistence row |
| Payment/order chỉ hoàn tất một lần | Idempotency + locked state + duplicate webhook record |
| Financial/audit history không sửa/xóa | Service policy + database trigger/immutable tables |
| AI tool không vượt quyền | Server authorization + trusted tenant + fixed tool contract |

## Reliability semantics

- PostgreSQL transaction: atomic trong một write workflow.
- Outbox: at-least-once delivery intent; consumer phải idempotent.
- Celery: retry/backoff; durable job row là nguồn trạng thái, broker message chỉ mang ID.
- Cache: không có consistency guarantee mạnh; invalidation sau commit và fallback DB.
- RAG: retrieval là probabilistic; citation/no-answer không đảm bảo knowledge completeness.
- ECS rollback: rollback image không rollback schema; migration phải expand-contract/roll-forward.

## Security/privacy quyết định

- Generic auth errors giảm user enumeration.
- Refresh secret chỉ lưu hash; log formatter dùng allowlist.
- Route template thay raw URL trong metrics để tránh PII và cardinality cao.
- SQL metrics chỉ label `select|insert|update|delete|other`.
- AI audit giữ metadata bounded, không giữ prompt/document content không cần thiết.
- `/metrics`, Grafana và Prometheus không được ALB expose public.

## Khi nào cần xem xét lại

- Tách service khi một module có ownership/deploy/scale độc lập và outbox seam đủ rõ.
- Chuyển tenant database riêng khi compliance/data residency hoặc noisy-neighbor yêu cầu.
- Dùng vector database chuyên dụng khi corpus/query scale vượt benchmark pgvector thực tế.
- Dùng reservation thay immediate deduction nếu order/payment journey cần giữ stock dài.
- Multi-AZ/autoscaling/WAF khi staging được nâng thành production-like hoặc có external users.
- Backend lockfile khi chuẩn hóa build đa nền tảng/release artifact.

## Quyết định chưa hoàn tất

- Production RTO/RPO, data retention và legal/compliance requirements — **PLANNED**.
- Alertmanager/on-call provider và escalation ownership — **PLANNED**.
- OpenAI production model/cost budget và data-processing agreement — **PLANNED**.
- Real payment/email provider selection — **PLANNED**.
- Public hosting/domain/demo account — chưa được phê duyệt.

