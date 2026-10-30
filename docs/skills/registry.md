# Danh mục Agent Skills của NEXUS AI

Danh mục này là nguồn đối chiếu cho các project skill trong `.agents/skills/`. Một skill xuất hiện ở đây và vượt qua validator nghĩa là cấu trúc của nó hợp lệ và có thể được Codex phát hiện từ repository; điều đó không có nghĩa skill luôn được load hoặc tự động thực thi trong mọi lượt.

| Skill | Khi nên chọn |
|---|---|
| `feature-delivery` | Khi một feature cần được giao trọn vẹn qua nhiều lớp kỹ thuật. |
| `project-planner` | Khi đầu ra chính là kế hoạch, thứ tự triển khai, dependency và rủi ro. |
| `python-backend` | Khi xây dựng hoặc chỉnh sửa Python, FastAPI, use case, domain hoặc worker. |
| `api-design` | Khi thiết kế hoặc review REST contract, schema, error và OpenAPI. |
| `database-design` | Khi thay đổi PostgreSQL, SQLAlchemy, Alembic, transaction hoặc pgvector. |
| `security-review` | Khi thực hiện security review tập trung hoặc rà soát trust boundary. |
| `test-engineering` | Khi thiết kế, triển khai hoặc sửa pytest, Playwright và test strategy. |
| `frontend-engineering` | Khi thay đổi Next.js, React, TypeScript hoặc hành vi UI. |
| `ai-rag-engineering` | Khi xây dựng OpenAI integration, ingestion, retrieval, RAG hoặc evaluation. |
| `agent-orchestration` | Khi xây dựng LangGraph, tool, MCP, checkpoint hoặc approval flow. |
| `devops-cloud` | Khi thay đổi Docker, GitHub Actions, Terraform, AWS hoặc release workflow. |
| `observability` | Khi xây dựng log, metric, trace, health check, dashboard hoặc alert. |
| `documentation` | Khi tạo hoặc cập nhật README, tài liệu kiến trúc, runbook và task report. |

## Quy tắc đồng bộ

- Tên trong bảng phải trùng chính xác với trường `name` trong YAML frontmatter.
- Mỗi tên chỉ xuất hiện một lần và phải có thư mục cùng tên.
- Chạy `python scripts/validate_skills.py` sau mỗi thay đổi skill hoặc registry.
- Không thêm skill vào danh mục trước khi có `SKILL.md` hoàn chỉnh.
