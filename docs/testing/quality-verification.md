# Quy trình xác minh chất lượng

## Mục tiêu

Workflow Task 26 cung cấp bằng chứng theo hành vi và risk boundary. Coverage là tín hiệu phát hiện vùng chưa được thực thi, không chứng minh business rule đúng hoặc hệ thống an toàn.

## Test matrix

| Nhóm | Công cụ và vị trí | Rủi ro được chứng minh |
|---|---|---|
| Unit | `backend/tests/unit`, Vitest `frontend/tests` | Domain helper, crypto, config, validation, UI state |
| API contract/integration | `backend/tests/contract`, `backend/tests/integration` | HTTP schema, error contract, workflow end-to-end |
| Database transaction/migration | `test_database_manager.py`, `test_migrations.py`, reliability tests | Commit, rollback, upgrade/downgrade, immutable history |
| Multi-tenant isolation | Organization, Catalog, Inventory, Order, Payment, Knowledge, MCP tests | Malicious foreign ID và active-tenant boundary |
| Authorization | `test_rbac_api.py`, agent/MCP negative paths | Permission matrix, last owner, tool denial |
| Concurrency | Product/Inventory reliability, Order, Payment tests | Atomic SKU/stock, confirm once, duplicate webhook |
| Browser E2E | `frontend/e2e` với Playwright | Desktop/mobile user journey, BFF, security headers |
| AI evaluation | `backend/tests/evaluation`, knowledge/agent/MCP tests | Retrieval, no-answer, injection case, tool correctness |
| Load/performance | Locust `backend/tests/performance` | HTTP/middleware baseline bằng synthetic clients |

## Coverage targets ban đầu

Các target được kiểm tra bởi `scripts/check_critical_coverage.py` sau full PostgreSQL suite:

| Module | Target line coverage | Kết quả Task 26 |
|---|---:|---:|
| Auth | 80% | 95,69% |
| Organizations | 80% | 95,88% |
| Orders | 75% | 91,08% |
| Payments | 75% | 87,58% |
| Knowledge/RAG | 70% | 90,23% |
| Business Agent | 70% | 95,10% |

Full-suite line/branch-aware report đạt 89% tổng thể. Các con số này không thay thế assertions về transaction, tenant isolation, authorization và concurrency.

Baseline chỉ chạy unit/contract, không có PostgreSQL, đạt 47% tổng thể và không đạt target module. Điều này xác nhận integration suite là bắt buộc để đo coverage có ý nghĩa cho repository/service workflow.

## Chạy local

### Unit, contract và AI evaluation deterministic

```powershell
Set-Location backend
.venv\Scripts\python.exe -m pytest -q -m "not integration and not performance"
```

### PostgreSQL integration và coverage

`NEXUS_TEST_DATABASE_ADMIN_URL` phải trỏ tới database admin dành riêng cho test và có quyền tạo/drop database tạm. Không dùng production database.

```powershell
$env:NEXUS_TEST_DATABASE_ADMIN_URL = "postgresql://postgres:<synthetic-password>@127.0.0.1:55432/postgres"
.venv\Scripts\python.exe -m pytest -q --cov=nexus --cov-branch --cov-report=term --cov-report=json:coverage.json
.venv\Scripts\python.exe ..\scripts\check_critical_coverage.py
```

Mỗi fixture tạo database `nexus_test_<random>`, chạy migration và drop sau test. Nếu test crash, operator phải kiểm tra database tạm còn sót trước khi chạy lại.

### Frontend và browser

```powershell
Set-Location frontend
npm.cmd run typecheck
npm.cmd run lint
npm.cmd test
npm.cmd run test:e2e
```

### Load test

```powershell
Set-Location backend
.venv\Scripts\python.exe -m uvicorn tests.performance.benchmark_app:app --host 127.0.0.1 --port 8089 --no-access-log
```

Ở terminal khác:

```powershell
.venv\Scripts\python.exe -m locust -f tests/performance/locustfile.py --headless --host http://127.0.0.1:8089 -u 25 -r 5 -t 20s --csv ..\docs\performance\artifacts\task26-public-read-no-access-log --only-summary --exit-code-on-error 1
```

## CI

Workflow `.github/workflows/quality-verification.yml` có ba job:

- Backend: pgvector PostgreSQL tạm, Ruff, mypy, full pytest và coverage gates.
- Frontend: TypeScript, ESLint, Vitest, production build và Playwright.
- Load smoke: 10 synthetic clients trong 10 giây; mục tiêu là phát hiện regression thô, không phải capacity certification.

CI không gọi OpenAI live, không dùng private document và không chạy production load.

## Kết quả Task 26

- Backend full suite: 113 pass, 3 skip do Redis không chạy.
- Riêng PostgreSQL integration: 54 pass, 3 Redis test skip.
- Unit/contract/evaluation không PostgreSQL: 59 pass, 57 integration test deselected.
- Frontend Vitest: 16 pass.
- Playwright: 2 pass trên desktop/mobile Chromium.
- Ruff, mypy, TypeScript, ESLint và production build: pass.

Redis integration chưa được chạy trong phiên Task 26; ba test cache là **BLOCKED theo môi trường**, không được tính là pass.
