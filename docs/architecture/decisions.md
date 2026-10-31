# Danh mục quyết định kiến trúc

Tài liệu này theo dõi các quyết định cần được viết thành Architecture Decision Record (ADR) khi Task tương ứng được triển khai.

| Mã | Quyết định | Trạng thái | Task dự kiến |
|---|---|---|---|
| ADR-001 | Sử dụng Modular Monolith thay vì microservices | Chấp nhận sơ bộ | 01 |
| ADR-002 | Quy tắc Clean Architecture theo bounded module | Chấp nhận sơ bộ | 01 |
| ADR-003 | Shared schema với tenant-scoped repository và server-side active context | Chấp nhận | 09 |
| ADR-004 | JWT access token ngắn hạn, opaque refresh token rotation và session revocation | Chấp nhận | 08 |
| ADR-005 | Transactional outbox và idempotent consumer | PLANNED | 16 |
| ADR-006 | Cache-aside tenant-aware, post-commit invalidation và fail-open về PostgreSQL | Chấp nhận | 17 |
| ADR-007 | Chunk 1.200 ký tự/overlap 200, vector 1.536 chiều và tenant-filtered cosine search | Chấp nhận | 20 |
| ADR-008 | LangGraph state, tool policy và human approval | PLANNED | 22 |
| ADR-009 | MCP trust boundary | PLANNED | 23 |
| ADR-010 | Topology triển khai AWS | PLANNED | 28 |
| ADR-011 | Tenant RBAC allowlist, target-policy và immutable audit log | Chấp nhận | 10 |
| ADR-012 | Decimal catalog price, transactional tenant SKU và future order price snapshot | Chấp nhận | 11 |
| ADR-013 | Pessimistic stock locking, idempotent movements và server-side negative policy | Chấp nhận | 12 |
| ADR-014 | Deduct stock khi confirm, hoàn stock khi cancel và immutable Order price snapshot | Chấp nhận | 14 |
| ADR-015 | Provider abstraction, HMAC webhook, tenant idempotency và immutable financial audit | Chấp nhận | 15 |
| ADR-016 | PostgreSQL transactional outbox, leased worker, idempotent inbox và detection-only reconciliation | Chấp nhận | 16 |
| ADR-017 | RabbitMQ vận chuyển job ID, PostgreSQL giữ durable job state và Celery worker dùng retry backoff | Chấp nhận | 18 |
| ADR-018 | Net revenue theo successful payment trừ successful refund, ghi nhận tại payment success time | Chấp nhận | 19 |

“Chấp nhận sơ bộ” nghĩa là đủ để định hướng khởi tạo nhưng vẫn có thể được tinh chỉnh bằng ADR đầy đủ khi có code và trade-off cụ thể.
