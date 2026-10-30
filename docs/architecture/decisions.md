# Danh mục quyết định kiến trúc

Tài liệu này theo dõi các quyết định cần được viết thành Architecture Decision Record (ADR) khi Task tương ứng được triển khai.

| Mã | Quyết định | Trạng thái | Task dự kiến |
|---|---|---|---|
| ADR-001 | Sử dụng Modular Monolith thay vì microservices | Chấp nhận sơ bộ | 01 |
| ADR-002 | Quy tắc Clean Architecture theo bounded module | Chấp nhận sơ bộ | 01 |
| ADR-003 | Shared schema với tenant-scoped repository và server-side active context | Chấp nhận | 09 |
| ADR-004 | JWT access token ngắn hạn, opaque refresh token rotation và session revocation | Chấp nhận | 08 |
| ADR-005 | Transactional outbox và idempotent consumer | PLANNED | 16 |
| ADR-006 | Chiến lược cache và invalidation | PLANNED | 17 |
| ADR-007 | Chunking, embedding và vector search | PLANNED | 20 |
| ADR-008 | LangGraph state, tool policy và human approval | PLANNED | 22 |
| ADR-009 | MCP trust boundary | PLANNED | 23 |
| ADR-010 | Topology triển khai AWS | PLANNED | 28 |
| ADR-011 | Tenant RBAC allowlist, target-policy và immutable audit log | Chấp nhận | 10 |
| ADR-012 | Decimal catalog price, transactional tenant SKU và future order price snapshot | Chấp nhận | 11 |

“Chấp nhận sơ bộ” nghĩa là đủ để định hướng khởi tạo nhưng vẫn có thể được tinh chỉnh bằng ADR đầy đủ khi có code và trade-off cụ thể.
