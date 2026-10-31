# Kiến trúc tổng quan NEXUS AI

## 1. Bối cảnh và mục tiêu

NEXUS AI là nền tảng SaaS đa tenant phục vụ quản trị doanh nghiệp và tích hợp AI. Kiến trúc cần thể hiện năng lực backend chuyên nghiệp nhưng vẫn phù hợp với quy mô một dự án portfolio: dễ chạy cục bộ, dễ kiểm thử, có đường nâng cấp rõ ràng và không tạo độ phức tạp phân tán quá sớm.

Các thuộc tính chất lượng ưu tiên:

1. Cô lập tenant và kiểm soát truy cập đúng đắn.
2. Tính toàn vẹn của workflow ghi dữ liệu.
3. Boundary module rõ ràng và khả năng thay đổi độc lập ở mức mã nguồn.
4. Khả năng quan sát, kiểm thử và triển khai lặp lại.
5. AI có guardrail, truy vết và evaluation thay vì hoạt động như một “hộp đen”.

## 2. Quyết định kiến trúc cấp cao

### 2.1 Modular Monolith

Backend là một deployable FastAPI và một cơ sở dữ liệu PostgreSQL, nhưng mã nguồn được chia theo bounded module. Lựa chọn này giữ transaction nội bộ đơn giản, giảm chi phí vận hành và vẫn buộc dự án thể hiện các boundary có thể tách ra sau này nếu có bằng chứng thực tế.

Module không được đọc trực tiếp bảng hoặc gọi repository nội bộ của module khác. Giao tiếp đồng bộ đi qua public application contract. Giao tiếp không đồng bộ dùng domain/application event và cơ chế phát tin đáng tin cậy khi được triển khai.

### 2.2 Clean Architecture theo từng module

Mỗi business module tương lai có cấu trúc dự kiến:

```text
module_name/
├── domain/          # Entity, value object, domain service, domain event
├── application/     # Use case, command/query, port, DTO
├── infrastructure/  # SQLAlchemy, client ngoài, adapter
└── presentation/    # FastAPI router và schema tại biên API
```

Quy tắc dependency:

- `domain` không phụ thuộc framework hoặc I/O.
- `application` phụ thuộc `domain` và định nghĩa port cần thiết.
- `infrastructure` và `presentation` phụ thuộc vào contract ở phía trong.
- `bootstrap` lắp ráp dependency và cấu hình runtime.
- `platform` cung cấp capability kỹ thuật dùng chung, không chứa business rule của module.

### 2.3 Multi-tenancy

Mô hình ban đầu dự kiến dùng shared database/shared schema với `tenant_id` trên mọi aggregate và bảng thuộc tenant. Đây là lựa chọn **PLANNED**, phải được xác nhận bằng ADR ở Task chuyên biệt.

Nguyên tắc bắt buộc:

- Tenant context được xác thực tại biên request hoặc background job.
- Repository yêu cầu tenant context; query thuộc tenant luôn có điều kiện tenant.
- Unique constraint và index bao gồm `tenant_id` khi uniqueness nằm trong phạm vi tenant.
- Authorization kiểm tra cả tenant membership và permission.
- Test phải cố tình thử truy cập chéo tenant.
- PostgreSQL Row-Level Security có thể là lớp phòng thủ bổ sung, không thay thế kiểm tra ở application.

### 2.4 Transaction và side effect

Một application use case sở hữu một transaction boundary. Domain rule được kiểm tra trước khi commit; lỗi phải rollback toàn bộ thay đổi liên quan. Không thực hiện lời gọi mạng không kiểm soát bên trong database transaction.

Order/Payment workflow đã dùng PostgreSQL transactional outbox và idempotent local consumer để không mất event sau commit. Adapter publish qua Celery/RabbitMQ vẫn **PLANNED**. Redis chỉ phục vụ cache, rate limit hoặc dữ liệu tạm; PostgreSQL vẫn là nguồn dữ liệu chuẩn.

### 2.5 Xác thực và RBAC

Authentication dự kiến dùng access token ngắn hạn và refresh token có rotation/revocation. Password phải được băm bằng thuật toán phù hợp tại thời điểm triển khai. RBAC nằm trong application policy và luôn được đánh giá theo tenant; frontend không phải ranh giới bảo mật.

### 2.6 AI Agent, RAG và MCP

AI là capability riêng, không được truy cập database tùy ý. Công cụ Agent gọi application contract có schema, authorization và audit. RAG phân tách ingest, chunking, embedding, retrieval và generation; tài liệu và vector đều mang tenant scope. pgvector được dùng cùng PostgreSQL để giảm số thành phần vận hành trong giai đoạn đầu.

LangGraph quản lý state và luồng Agent. MCP là boundary tích hợp công cụ, không bỏ qua policy của hệ thống. Prompt, model, nguồn trích dẫn, latency và token usage cần được quan sát; thay đổi AI phải có evaluation phù hợp.

## 3. Thành phần runtime dự kiến

```text
Trình duyệt
   │ HTTPS
   ▼
Next.js ───────► FastAPI Modular Monolith ───────► PostgreSQL + pgvector
                      │        │
                      │        ├───────────────► Redis
                      │        │
                      │        └── publish ────► RabbitMQ ───► Celery Worker
                      │
                      └── AI boundary ─────────► OpenAI API / MCP tools
```

Trong môi trường phát triển, các dependency hạ tầng sẽ chạy bằng Docker Compose. Trên AWS, cách ánh xạ dịch vụ cụ thể sẽ được quyết định ở Task hạ tầng, ưu tiên managed services khi hợp lý.

## 4. Ownership thư mục

- `backend/src/nexus/modules`: business capability; chưa được tạo module trong Task 01.
- `backend/src/nexus/platform`: auth primitives, database foundation, messaging, observability và AI foundation dùng chung khi được triển khai.
- `backend/src/nexus/bootstrap`: application factory, dependency wiring và lifecycle.
- `backend/migrations`: Alembic environment và migration có thứ tự.
- `frontend/src`: route, feature UI, API client và design system.
- `infrastructure/docker`: image và cấu hình container.
- `infrastructure/terraform`: module và environment AWS.
- `tests`: kiểm thử cấp hệ thống; test gần code nằm trong từng workspace tương ứng.
- `.agents/skills`: skill cấp repository hỗ trợ quy trình phát triển.

## 5. API và lỗi

REST API dự kiến được version dưới `/api/v1`. Resource dùng danh từ, HTTP status code đúng ngữ nghĩa và error envelope ổn định có correlation ID. Idempotency key sẽ được áp dụng cho các command nhạy cảm như tạo thanh toán hoặc đơn hàng. OpenAPI là contract được kiểm tra, không chỉ là tài liệu tự sinh.

## 6. Kiểm thử

Chiến lược kiểm thử dự kiến gồm:

- Unit test cho domain và application policy.
- Integration test với PostgreSQL/Redis/RabbitMQ thật qua container khi cần.
- Contract test cho API và event schema.
- Security test cho tenant isolation, RBAC và authentication.
- Evaluation dataset cho retrieval và Agent behavior.
- Playwright cho các hành trình người dùng quan trọng.

## 7. Quan sát và vận hành

Log có cấu trúc phải chứa correlation ID, tenant ID đã được xử lý an toàn và tên use case; tuyệt đối không ghi secret hoặc nội dung nhạy cảm không cần thiết. Metrics và tracing bao phủ HTTP, database, queue, worker và AI call. Health check phân biệt liveness và readiness.

## 8. Các ràng buộc của Task 01

Task 01 chỉ quyết định hướng kiến trúc và tạo cấu trúc. Chưa có package Python/Node, database schema, API, Docker service, Terraform resource, business module hoặc Agent Skill nghiệp vụ nào được triển khai. Những mục đó đều **PLANNED** theo roadmap.
