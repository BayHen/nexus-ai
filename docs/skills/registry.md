# Danh mục Agent Skills của NEXUS AI

Danh mục này là nguồn đối chiếu cho các project skill trong `.agents/skills/`. Một skill xuất hiện ở đây và vượt qua validator nghĩa là cấu trúc của nó hợp lệ và có thể được Codex phát hiện từ repository; điều đó không có nghĩa skill luôn được load hoặc tự động thực thi trong mọi lượt.

| Skill | Khi nên chọn | Nguồn | Revision | License |
|---|---|---|---|---|
| `feature-delivery` | Khi một feature cần được giao trọn vẹn qua nhiều lớp kỹ thuật. | Nội bộ | Repository hiện tại | Nội bộ |
| `project-planner` | Khi đầu ra chính là kế hoạch, thứ tự triển khai, dependency và rủi ro. | Nội bộ | Repository hiện tại | Nội bộ |
| `python-backend` | Khi xây dựng hoặc chỉnh sửa Python, FastAPI, use case, domain hoặc worker. | Nội bộ | Repository hiện tại | Nội bộ |
| `api-design` | Khi thiết kế hoặc review REST contract, schema, error và OpenAPI. | Nội bộ | Repository hiện tại | Nội bộ |
| `database-design` | Khi thay đổi PostgreSQL, SQLAlchemy, Alembic, transaction hoặc pgvector. | Nội bộ | Repository hiện tại | Nội bộ |
| `security-review` | Khi thực hiện security review tập trung hoặc rà soát trust boundary. | Nội bộ | Repository hiện tại | Nội bộ |
| `test-engineering` | Khi thiết kế, triển khai hoặc sửa pytest, Playwright và test strategy. | Nội bộ | Repository hiện tại | Nội bộ |
| `frontend-engineering` | Khi thay đổi Next.js, React, TypeScript hoặc hành vi UI. | Nội bộ | Repository hiện tại | Nội bộ |
| `ai-rag-engineering` | Khi xây dựng OpenAI integration, ingestion, retrieval, RAG hoặc evaluation. | Nội bộ | Repository hiện tại | Nội bộ |
| `agent-orchestration` | Khi xây dựng LangGraph, tool, MCP, checkpoint hoặc approval flow. | Nội bộ | Repository hiện tại | Nội bộ |
| `devops-cloud` | Khi thay đổi Docker, GitHub Actions, Terraform, AWS hoặc release workflow. | Nội bộ | Repository hiện tại | Nội bộ |
| `observability` | Khi xây dựng log, metric, trace, health check, dashboard hoặc alert. | Nội bộ | Repository hiện tại | Nội bộ |
| `documentation` | Khi tạo hoặc cập nhật README, tài liệu kiến trúc, runbook và task report. | Nội bộ | Repository hiện tại | Nội bộ |
| `playwright` | Khi cần điều khiển trình duyệt thật từ terminal để kiểm tra navigation, form, screenshot hoặc UI flow. | [openai/skills](https://github.com/openai/skills/tree/49f948faa9258a0c61caceaf225e179651397431/skills/.curated/playwright) | `49f948faa9258a0c61caceaf225e179651397431` | Apache-2.0 |

## Quy tắc đồng bộ

- Tên trong bảng phải trùng chính xác với trường `name` trong YAML frontmatter.
- Mỗi tên chỉ xuất hiện một lần và phải có thư mục cùng tên.
- Chạy `python scripts/validate_skills.py` sau mỗi thay đổi skill hoặc registry.
- Không thêm skill vào danh mục trước khi có `SKILL.md` hoàn chỉnh.
- External skill phải có source URL, full commit SHA và license; không dùng branch động làm revision cài đặt.
