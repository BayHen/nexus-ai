# NEXUS AI – Nền tảng quản trị doanh nghiệp đa tenant thông minh

## Giới thiệu dự án

NEXUS AI là dự án portfolio hướng tới một nền tảng SaaS quản trị doanh nghiệp đa tenant, kết hợp các quy trình nghiệp vụ an toàn giao dịch với AI Agent và RAG. Dự án được thiết kế cho vị trí Backend Python Engineer và AI Backend Engineer, ưu tiên chất lượng kiến trúc, khả năng kiểm thử, bảo mật và vận hành thực tế.

**Trạng thái hiện tại:** Task 01 đã hoàn thành phần khởi tạo và thiết kế kiến trúc. Toàn bộ chức năng nghiệp vụ bên dưới đang ở trạng thái **PLANNED**.

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
| Đăng ký, đăng nhập, refresh token và quản lý phiên | PLANNED |
| RBAC theo tenant | PLANNED |
| Danh mục khách hàng và liên hệ | PLANNED |
| Sản phẩm, tồn kho và điều chỉnh kho | PLANNED |
| Đơn hàng, hóa đơn và thanh toán | PLANNED |
| Workflow nền bằng Celery và RabbitMQ | PLANNED |
| Thông báo và audit log | PLANNED |
| Kho tri thức, tìm kiếm vector và RAG | PLANNED |
| AI Agent với LangGraph và công cụ MCP | PLANNED |
| Dashboard quản trị bằng Next.js | PLANNED |
| Triển khai AWS và quan sát hệ thống | PLANNED |

## Công nghệ sử dụng

- **Backend:** Python, FastAPI, SQLAlchemy 2, Alembic, PostgreSQL, pgvector.
- **Frontend:** Next.js, React, TypeScript.
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
│   ├── src/                    # Next.js/React source tương lai
│   └── tests/                  # Component và E2E tests
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

Task 01 chưa cài dependency hoặc cung cấp môi trường chạy hoàn chỉnh. Chuẩn bị ban đầu:

1. Cài Git, Python, Node.js, Docker và Docker Compose theo phiên bản sẽ được chốt ở Task 02.
2. Sao chép `.env.example` thành `.env` và thay các giá trị mẫu bằng secret cục bộ.
3. Không commit file `.env` hoặc credential.
4. Tiếp tục Task 02 để bootstrap backend và khai báo dependency tối thiểu.

Hiện chưa có lệnh khởi chạy ứng dụng vì mã nguồn ứng dụng đang **PLANNED**.

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

## Testing và CI/CD

- pytest sẽ bao phủ unit, integration và contract tests — **PLANNED**.
- Playwright sẽ kiểm tra các luồng end-to-end quan trọng — **PLANNED**.
- GitHub Actions sẽ chạy lint, type check, test, build và security checks — **PLANNED**.
- Docker image và Terraform plan sẽ được kiểm tra trước khi phát hành — **PLANNED**.

Task 01 chỉ kiểm tra cấu trúc và nội dung tĩnh; chưa có test suite để thực thi.

## Lộ trình phát triển 30 Task

Lộ trình gồm 30 Task, từ bootstrap backend, multi-tenancy, authentication và các workflow nghiệp vụ đến AI/RAG, frontend, CI/CD, AWS và hardening. Toàn bộ Task 02–30 đang **PLANNED**. Danh sách và tiêu chí đầu ra chi tiết nằm tại [lộ trình triển khai](docs/roadmap/30-tasks.md).

## Trạng thái hoàn thành dự án

| Phạm vi | Trạng thái |
|---|---|
| Task 01 – Khởi tạo và kiến trúc | Hoàn thành |
| Task 02–10 – Nền tảng backend và bảo mật | PLANNED |
| Task 11–18 – Nghiệp vụ và xử lý nền | PLANNED |
| Task 19–23 – AI, RAG và MCP | PLANNED |
| Task 24–26 – Frontend và E2E | PLANNED |
| Task 27–30 – CI/CD, AWS và hoàn thiện | PLANNED |

Mức hoàn thành theo roadmap: **1/30 Task**.
