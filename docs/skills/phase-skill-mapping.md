# Mapping giữa giai đoạn phát triển và Agent Skills

Mapping này giúp chọn tập skill nhỏ nhất phù hợp với từng phase. Đây là routing guidance, không buộc Codex load mọi skill trong một dòng.

| Phase | Skill chính | Skill hỗ trợ khi cần | Kết quả điển hình |
|---|---|---|---|
| Khám phá và lập kế hoạch | `project-planner` | `documentation`, `security-review` | Scope, dependency, risk và acceptance criteria |
| Giao feature xuyên lớp | `feature-delivery` | Các skill chuyên môn theo component | Vertical slice đã kiểm chứng và handoff |
| Backend foundation và nghiệp vụ | `python-backend` | `api-design`, `database-design`, `test-engineering` | Domain/use case/adapter và test |
| API contract | `api-design` | `python-backend`, `security-review`, `test-engineering` | REST/OpenAPI contract nhất quán |
| Database và migration | `database-design` | `python-backend`, `security-review`, `test-engineering` | Schema/migration an toàn và tenant-aware |
| Authentication, RBAC và hardening | `security-review` | `python-backend`, `api-design`, `test-engineering` | Findings hoặc control có regression test |
| Frontend | `frontend-engineering` | `api-design`, `test-engineering`, `playwright` | UI accessible, typed và browser-verified |
| AI và RAG | `ai-rag-engineering` | `database-design`, `security-review`, `test-engineering`, `observability` | Retrieval/generation có evaluation |
| Agent và MCP | `agent-orchestration` | `ai-rag-engineering`, `security-review`, `observability` | Graph/tool flow có giới hạn và audit |
| CI/CD và AWS | `devops-cloud` | `security-review`, `test-engineering`, `observability` | Pipeline/IaC có least privilege và plan |
| Vận hành | `observability` | `devops-cloud`, `security-review` | Log/metric/trace/alert có thể hành động |
| Browser validation | `playwright` | `frontend-engineering`, `test-engineering` | Evidence cho UI flow trong browser thật |
| Tài liệu và bàn giao | `documentation` | Skill chính của Task | README, ADR, runbook và báo cáo đúng trạng thái |
| Audit Task | `feature-delivery` hoặc skill chuyên môn | `documentation`, `security-review`, `test-engineering` | Báo cáo bằng chứng, rủi ro và readiness |

## Quy tắc chọn

1. Chọn skill chính theo outcome quan trọng nhất của Task.
2. Chỉ load skill hỗ trợ khi phần việc tương ứng thực sự có trong scope.
3. Nêu thứ tự dùng khi có nhiều skill.
4. Không dùng mapping để mở rộng quyền, tự động deploy hoặc chạy external script.
5. Báo cáo phân biệt `LOADED`, `VALIDATED` và `CONSIDERED`.
