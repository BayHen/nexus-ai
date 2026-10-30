# NEXUS AI – Nền tảng quản trị doanh nghiệp đa tenant thông minh

## Giới thiệu dự án

NEXUS AI là dự án portfolio hướng tới một nền tảng SaaS quản trị doanh nghiệp đa tenant, kết hợp các quy trình nghiệp vụ an toàn giao dịch với AI Agent và RAG. Dự án được thiết kế cho vị trí Backend Python Engineer và AI Backend Engineer, ưu tiên chất lượng kiến trúc, khả năng kiểm thử, bảo mật và vận hành thực tế.

**Trạng thái hiện tại:** Nền tảng FastAPI đã hoạt động với API versioning, typed settings, error handling, structured logging, request ID và health checks. Frontend Next.js đã có dashboard shell responsive, typed API client và trạng thái loading/empty/error dùng chung. Toàn bộ chức năng nghiệp vụ bên dưới vẫn ở trạng thái **PLANNED**.

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
| Quản lý tenant, tổ chức và thành viên | PLANNED |
| Đăng ký, đăng nhập, refresh rotation, logout và password reset grant | Hoàn thành nền tảng |
| RBAC theo tenant | PLANNED |
| Danh mục khách hàng và liên hệ | PLANNED |
| Sản phẩm, tồn kho và điều chỉnh kho | PLANNED |
| Đơn hàng, hóa đơn và thanh toán | PLANNED |
| Workflow nền bằng Celery và RabbitMQ | PLANNED |
| Thông báo và audit log | PLANNED |
| Kho tri thức, tìm kiếm vector và RAG | PLANNED |
| AI Agent với LangGraph và công cụ MCP | PLANNED |
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

Tenant context phải được xác lập ở biên request/job và truyền tường minh đến application/persistence. PostgreSQL là nguồn dữ liệu chuẩn; Redis không thay thế dữ liệu nghiệp vụ. Celery xử lý tác vụ nền, còn các side effect liên hệ hệ thống ngoài sẽ dùng cơ chế tin cậy như transactional outbox khi được triển khai.

Chi tiết xem [tài liệu kiến trúc](docs/architecture/overview.md).

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
| Task 09–10 – Nền tảng bảo mật tiếp theo | PLANNED |
| Task 11–18 – Nghiệp vụ và xử lý nền | PLANNED |
| Task 19–23 – AI, RAG và MCP | PLANNED |
| Task 24–26 – Frontend và E2E | PLANNED |
| Task 27–30 – CI/CD, AWS và hoàn thiện | PLANNED |

Mức hoàn thành theo chuỗi Task đã giao: **8/30 Task**.
