# NEXUS AI – Nền tảng quản trị doanh nghiệp đa tenant thông minh

## Giới thiệu dự án

NEXUS AI là dự án portfolio hướng tới một nền tảng SaaS quản trị doanh nghiệp đa tenant, kết hợp các quy trình nghiệp vụ an toàn giao dịch với AI Agent và RAG. Dự án được thiết kế cho vị trí Backend Python Engineer và AI Backend Engineer, ưu tiên chất lượng kiến trúc, khả năng kiểm thử, bảo mật và vận hành thực tế.

**Trạng thái hiện tại:** Nền tảng FastAPI, PostgreSQL, xác thực, multi-tenancy, RBAC, catalog, tồn kho, order/payment reliability, Redis cache, background processing, analytics, RAG và AI business assistant bằng LangGraph đã có implementation cùng kiểm thử tương ứng. Frontend Next.js đã có dashboard shell responsive, typed API client và trạng thái loading/empty/error dùng chung. Các phạm vi chưa triển khai được đánh dấu **PLANNED**.

## Mục tiêu dự án

- Xây dựng backend FastAPI theo Modular Monolith và Clean Architecture.
- Bảo đảm cô lập dữ liệu đa tenant, xác thực an toàn và RBAC.
- Mô hình hóa các workflow nghiệp vụ có transaction boundary rõ ràng.
- Tích hợp AI Agent, RAG, pgvector và MCP theo các boundary kiểm soát được.
- Cung cấp frontend Next.js có type safety và trải nghiệm quản trị chuyên nghiệp.
- Tự động hóa kiểm thử, CI/CD và hạ tầng AWS bằng Infrastructure as Code.
- Áp dụng Skill-Driven Development để Codex thực hiện công việc nhất quán.

## Các chức năng dự kiến

| Nhóm chức năng | Trạng thái |
|---|---|
| Organization, membership, invitation và active tenant context | Hoàn thành nền tảng |
| Đăng ký, đăng nhập, refresh rotation, logout và password reset grant | Hoàn thành nền tảng |
| RBAC theo tenant với Owner, Admin, Manager, Staff và Viewer | Hoàn thành nền tảng |
| Danh mục khách hàng và liên hệ | PLANNED |
| Product/Category catalog, generated SKU và Decimal pricing | Hoàn thành nền tảng |
| Tồn kho, adjustment, transfer và immutable movement ledger | Hoàn thành nền tảng |
| Đơn hàng và sandbox payment | Hoàn thành nền tảng |
| Redis cache tenant-aware cho Product/Category detail | Hoàn thành nền tảng |
| Workflow nền bằng Celery và RabbitMQ | Hoàn thành nền tảng |
| Revenue và business analytics, CSV/XLSX export | Hoàn thành nền tảng |
| Tenant-aware RAG knowledge base với pgvector | Hoàn thành nền tảng |
| Thông báo và audit log | PLANNED |
| AI business assistant với LangGraph và năm tool chỉ đọc | Hoàn thành nền tảng |
| MCP integration cho AI Agent | PLANNED |
| Dashboard shell và kiểm tra trạng thái hệ thống | Hoàn thành nền tảng |
| Dashboard nghiệp vụ và dữ liệu tenant | PLANNED |
| Triển khai AWS và quan sát hệ thống | PLANNED |

## Công nghệ sử dụng

- **Backend:** Python, FastAPI, SQLAlchemy 2, Alembic, PostgreSQL, pgvector.
- **Frontend:** Next.js, React, TypeScript, Tailwind CSS.
- **Bất đồng bộ và cache:** Celery, RabbitMQ, Redis.
- **AI:** OpenAI API, LangGraph, RAG, MCP.
- **Hạ tầng:** Docker, AWS, Terraform, GitHub Actions.
- **Kiểm thử:** pytest, Playwright.
- **Quy trình phát triển:** Codex và Agent Skills.

Các dependency cụ thể chưa được cài đặt trong Task 01 và sẽ được khóa phiên bản ở các Task phù hợp.

## Kiến trúc hệ thống

Hệ thống sử dụng **Modular Monolith**: một đơn vị triển khai backend nhưng chia thành các module nghiệp vụ có ownership và dependency rule rõ ràng. Mỗi module sẽ tổ chức theo các lớp `domain`, `application`, `infrastructure` và `presentation`; dependency hướng vào trong. Các capability dùng chung nằm trong `platform`, còn composition root nằm trong `bootstrap`.

Tenant context phải được xác lập ở biên request/job và truyền tường minh đến application/persistence. PostgreSQL là nguồn dữ liệu chuẩn; Redis không thay thế dữ liệu nghiệp vụ. Order/Payment dùng PostgreSQL transactional outbox và idempotent consumer. Celery/RabbitMQ vận chuyển durable background job ID cho report, test notification, low-stock alert và outbox processing; chi tiết startup và recovery nằm tại [tài liệu xử lý nền](docs/architecture/background-processing.md).

Cache hiện áp dụng cache-aside cho API đọc chi tiết Product và Category. Hệ thống xác thực và resolve tenant trước khi truy cập Redis; key chứa `organization_id`, mutation chỉ invalidation sau khi transaction commit, và lỗi Redis tự fallback về PostgreSQL. Chi tiết chiến lược, metric và benchmark thực tế nằm tại [tài liệu Redis caching](docs/architecture/redis-caching.md).

Chi tiết xem [tài liệu kiến trúc](docs/architecture/overview.md).

AI business assistant cung cấp `POST /api/v1/agent/ask` với LangGraph hữu hạn, tool allowlist chỉ đọc, server-side tenant/permission checks, timeout, immutable tool audit và citation từ RAG. Agent không chạy SQL do model sinh và từ chối write intent; workflow ghi tương lai phải có authorization cùng xác nhận riêng. Xem [workflow AI Agent](docs/architecture/business-intelligence-agent.md) và [mô hình bảo mật](docs/security/business-agent-security.md).

## Cấu trúc thư mục

```text
nexus-ai/
├── .agents/skills/             # Agent Skills riêng của dự án
├── backend/
│   ├── src/nexus/
│   │   ├── bootstrap/          # Composition root và cấu hình khởi động
│   │   ├── modules/            # Các bounded module nghiệp vụ tương lai
│   │   └── platform/           # Capability kỹ thuật dùng chung
│   ├── migrations/             # Alembic migrations tương lai
│   └── tests/                  # Unit, integration, contract tests
├── frontend/
│   ├── src/app/                # App Router, page và Route Handler
│   ├── src/components/         # Layout và UI state dùng chung
│   ├── src/lib/api/            # Typed API client và error contract
│   └── tests/                  # Unit và component tests
├── infrastructure/
│   ├── docker/                 # Docker assets
│   └── terraform/              # Hạ tầng AWS theo môi trường/module
├── docs/
│   ├── architecture/           # Tài liệu và quyết định kiến trúc
│   └── roadmap/                # Lộ trình triển khai
├── scripts/                    # Script phát triển/vận hành có kiểm soát
└── tests/                      # Kiểm thử end-to-end cấp hệ thống
```

Các thư mục rỗng hiện được giữ bằng `.gitkeep`; chưa có business module nào được triển khai.

## Hướng dẫn cài đặt

Yêu cầu hiện tại: Python 3.12 trở lên. Từ repository root trên Windows PowerShell:

```powershell
python -m venv backend/.venv
backend/.venv/Scripts/python.exe -m pip install -e "backend[dev]"
Copy-Item .env.example .env
docker compose --env-file .env -f infrastructure/docker/compose.yml up -d postgres
backend/.venv/Scripts/python.exe -m alembic -c backend/alembic.ini upgrade head
backend/.venv/Scripts/python.exe -m uvicorn nexus.main:app --host 127.0.0.1 --port 8000
```

File `.env` là cấu hình cục bộ và không được commit. Các giá trị `NEXUS_*` trong `.env.example` điều khiển app name, environment, debug, log level và API prefix.

Sau khi server khởi động:

- API metadata: `http://127.0.0.1:8000/api/v1`
- Liveness: `http://127.0.0.1:8000/health/live`
- Readiness: `http://127.0.0.1:8000/health/ready`
- Swagger UI: `http://127.0.0.1:8000/docs`
- OpenAPI schema: `http://127.0.0.1:8000/openapi.json`

Các lệnh trên đã được kiểm chứng với Python 3.14.3 trong môi trường phát triển hiện tại. Nhấn `Ctrl+C` để dừng Uvicorn.

API dùng fail-fast startup: Uvicorn không hoàn tất startup nếu PostgreSQL không reachable. Quy trình migration, transaction, backup, restore và reset volume nằm tại [tài liệu database cục bộ](docs/database/local-development.md).

### Authentication

Sau khi chạy migration mới nhất, các endpoint authentication nằm dưới `/api/v1/auth`. Hệ thống dùng Argon2id, JWT access token ngắn hạn, opaque refresh token rotation/revocation, login rate limiting và password-reset grant single-use. Xem [tài liệu xác thực](docs/security/authentication.md) để biết contract, biến môi trường, giới hạn rate limiter và trạng thái email delivery **PLANNED**.

### Multi-tenancy

Organization, membership, active organization selection, invitation cho user đã đăng ký và tenant-scoped Branch API đã được triển khai. Business API resolve tenant từ access token và active context phía server, không tin `organization_id` do client tự gửi. Xem [kiến trúc multi-tenancy](docs/architecture/multi-tenancy.md) để biết invariant database, role matrix, pagination và threat model chống cross-tenant bypass.

### RBAC và audit

Permission allowlist được thực thi trong service cho năm role Owner, Admin, Manager, Staff và Viewer. Role management có target-policy chống privilege escalation, active owner cuối cùng được bảo vệ bằng row lock, và sensitive membership changes tạo immutable audit event. Xem [permissions matrix và audit schema](docs/security/rbac.md).

### Product Catalog

Product và Category CRUD đã hỗ trợ tenant isolation, generated SKU theo organization, `Decimal` pricing, search/filter/sort/pagination và soft deletion. Category có Product active không thể bị xóa âm thầm. Xem [kiến trúc Product Catalog](docs/architecture/product-catalog.md) để biết database constraints và quy tắc future Order price snapshot.

### Inventory

Stock theo Branch/Product, adjustment, atomic transfer, low-stock reporting, negative-stock policy và idempotent immutable movement ledger đã được triển khai. Mutation dùng row locking và transaction boundary để giữ consistency khi request đồng thời hoặc thất bại. Xem [kiến trúc Inventory](docs/architecture/inventory.md).

### Order Management

Draft Order, item mutations, server-calculated total, immutable Product price snapshot, confirmation và cancellation đã được triển khai. Confirmation trừ Inventory bằng pessimistic locking trong cùng transaction; cancellation của Order confirmed hoàn stock và ghi movement audit. Xem [state machine và chính sách Inventory](docs/architecture/orders.md).

### Secure Payment Processing

Payment abstraction và sandbox provider đã hỗ trợ tenant-scoped Payment Intent, idempotency, HMAC webhook, duplicate protection, atomic Order completion, Refund state và immutable financial audit. Sandbox không nhận hoặc lưu card data và simulation chỉ bật ở development/test. Xem [state machine và threat boundary của Payment](docs/architecture/payments.md).

### Order và Payment Reliability

Order/Payment transitions đã append transactional outbox và immutable business audit trong cùng PostgreSQL transaction. Leased worker hỗ trợ crash recovery, exponential retry/dead-letter, idempotent inbox consumer, correlation ID và tenant-scoped reconciliation diagnostics. Xem [consistency guarantees và trade-offs](docs/architecture/order-payment-reliability.md).

### Kiểm tra backend

```powershell
Set-Location backend
.venv/Scripts/python.exe -m ruff format --check .
.venv/Scripts/python.exe -m ruff check .
.venv/Scripts/python.exe -m mypy .
.venv/Scripts/python.exe -m pytest -q
```

### Chạy frontend cục bộ

Yêu cầu Node.js 24 trở lên và npm. Khởi động backend ở cổng `8000` trước, sau đó mở terminal mới tại repository root:

```powershell
Set-Location frontend
npm ci
$env:API_BASE_URL = "http://127.0.0.1:8000"
npm run dev
```

Mở `http://127.0.0.1:3000`. Browser gọi Route Handler cùng origin tại `/api/backend/health`; Next.js gọi FastAPI bằng `API_BASE_URL`, vì vậy URL nội bộ của backend không được đưa vào browser bundle.

Kiểm tra chất lượng và production build:

```powershell
Set-Location frontend
npm run lint
npm run typecheck
npm test
npm run build
npm start
```

Chạy frontend bằng Docker Compose, sau khi đã tạo `.env` với các biến PostgreSQL bắt buộc:

```powershell
docker compose --env-file .env -f infrastructure/docker/compose.yml up --build frontend
```

Dashboard chỉ hiển thị trạng thái lấy từ health API thật. Khu vực chưa có dữ liệu được ghi rõ là trạng thái trống; các mục điều hướng chưa triển khai được gắn nhãn **Planned** và không dùng số liệu production giả.

## Hướng dẫn sử dụng Codex

1. Mở repository tại thư mục gốc để Codex đọc được `AGENTS.md`.
2. Giao đúng một Task trong [lộ trình 30 Task](docs/roadmap/30-tasks.md) cho mỗi phiên làm việc.
3. Yêu cầu Codex kiểm tra thay đổi hiện có trước khi chỉnh sửa và không mở rộng sang Task tiếp theo.
4. Yêu cầu báo cáo file thay đổi, lệnh kiểm tra đã chạy, kết quả và vấn đề còn lại.
5. Dùng Git commit message bằng tiếng Anh; tài liệu trong `docs/` và README phải bằng tiếng Việt.

## Hệ thống Agent Skills dự kiến

Thư mục `.agents/skills/` là nơi chứa Agent Skills cấp dự án. Mỗi skill tương lai có một thư mục riêng với `SKILL.md`, trigger rõ ràng và tài nguyên tối thiểu. Các skill dự kiến gồm:

- `backend-module`: tạo skeleton module đúng dependency rule — **PLANNED**.
- `database-migration`: tạo và kiểm tra migration an toàn — **PLANNED**.
- `tenant-security-review`: rà soát tenant isolation và authorization — **PLANNED**.
- `api-contract`: chuẩn hóa REST API và OpenAPI contract — **PLANNED**.
- `ai-evaluation`: xây dựng evaluation cho RAG/Agent — **PLANNED**.
- `release-readiness`: kiểm tra chất lượng trước triển khai — **PLANNED**.

Task 01 chỉ chuẩn bị vị trí và quy ước, chưa tạo các skill nghiệp vụ.

### External Skill

Dự án tích hợp có kiểm soát external skill `playwright` từ repository chính thức `openai/skills` để hỗ trợ browser-based validation. Skill được lưu trong `.agents/skills/playwright`, pin bằng full commit SHA, giữ nguyên license/notice và đã được review tĩnh trước khi cài.

Quy trình không tự động chạy script hoặc cài npm dependency của external skill. Hướng dẫn audit, cài đặt tái lập, rollback và nâng cấp nằm tại [tài liệu External Skills](docs/skills/external-skills.md). Danh sách source và revision chuẩn nằm trong [Skills registry](docs/skills/registry.md).

Sau khi cài hoặc nâng cấp external skill, chạy validator và bắt đầu một Codex session mới để catalog được làm mới.

## Testing và CI/CD

- pytest đã bao phủ foundation unit, contract, PostgreSQL migration và authentication integration tests; coverage nghiệp vụ tiếp tục mở rộng theo từng Task.
- Vitest và Testing Library đã kiểm tra typed API client, responsive navigation và các UI state dùng chung.
- Playwright sẽ kiểm tra các luồng end-to-end quan trọng — **PLANNED**.
- GitHub Actions sẽ chạy lint, type check, test, build và security checks — **PLANNED**.
- Docker image và Terraform plan sẽ được kiểm tra trước khi phát hành — **PLANNED**.

Riêng hệ thống Agent Skills đã có GitHub Actions workflow `Skills validation`. Workflow chạy automated tests và `scripts/validate_skills.py` để kiểm tra metadata, reference, duplicate name và registry consistency. Chi tiết về phạm vi bằng chứng và giới hạn của CI nằm tại [tài liệu Skills CI](docs/skills/ci-validation.md).

Mapping giữa phase và skill nằm tại [phase-to-skill mapping](docs/skills/phase-skill-mapping.md); audit có thể dùng [mẫu báo cáo audit Task](docs/skills/task-audit-report-template.md).

Backend và frontend đã có application test suite nền tảng. Các bài kiểm thử nghiệp vụ và E2E vẫn **PLANNED**.

## Lộ trình phát triển 30 Task

Lộ trình gồm 30 Task, từ bootstrap backend, multi-tenancy, authentication và các workflow nghiệp vụ đến AI/RAG, frontend, CI/CD, AWS và hardening. Trạng thái thực thi hiện hành được ghi ở bảng bên dưới; các phạm vi chưa hoàn thành vẫn là **PLANNED**. Danh sách và tiêu chí đầu ra chi tiết nằm tại [lộ trình triển khai](docs/roadmap/30-tasks.md).

## Trạng thái hoàn thành dự án

| Phạm vi | Trạng thái |
|---|---|
| Task 01 – Khởi tạo và kiến trúc | Hoàn thành |
| Task 02–06 – Agent Skills, backend và database foundation | Hoàn thành |
| Task 07 – Frontend foundation | Hoàn thành |
| Task 08 – Authentication system | Hoàn thành nền tảng |
| Task 09 – Multi-Tenant Organizations | Hoàn thành nền tảng |
| Task 10 – Role-Based Access Control | Hoàn thành nền tảng |
| Task 11 – Product Catalog Management | Hoàn thành nền tảng |
| Task 12 – Inventory Management | Hoàn thành nền tảng |
| Task 13 – Inventory Reliability & Integration | Hoàn thành audit và integration test |
| Task 14 – Order Management System | Hoàn thành nền tảng |
| Task 15 – Secure Payment Processing | Hoàn thành sandbox foundation |
| Task 16 – Order and Payment Reliability | Hoàn thành nền tảng |
| Task 17 – Redis Caching | Hoàn thành nền tảng |
| Task 18 – Background Processing | Hoàn thành nền tảng |
| Task 19 – Revenue & Business Analytics | Hoàn thành nền tảng |
| Task 20 – RAG Knowledge Base | Hoàn thành nền tảng |
| Task 21 – Business Intelligence AI Agent | Hoàn thành nền tảng |
| Task 22–23 – Evaluation mở rộng và MCP | PLANNED |
| Task 24–26 – Frontend và E2E | PLANNED |
| Task 27–30 – CI/CD, AWS và hoàn thiện | PLANNED |

Mức hoàn thành theo chuỗi Task đã giao: **21/30 Task**.
