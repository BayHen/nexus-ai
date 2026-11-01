# Observability và reliability runbook

## Mục tiêu

Hệ thống telemetry trả lời bốn câu hỏi: API có phục vụ được không, request chậm ở đâu, dependency nào suy giảm và background job có hoàn tất không. Metrics không chứa tenant ID, user ID, document content, prompt, token, SQL text hoặc bind values.

## Signal và SLO ban đầu

Các mục tiêu dưới đây là baseline staging, chưa phải cam kết production:

| Service indicator | Cách đo | Objective ban đầu |
|---|---|---|
| API availability | `1 - 5xx / total requests`, loại trừ `/health/live` và scrape | ≥ 99,5% trong 30 ngày |
| API latency | p95 `nexus_http_request_duration_seconds` | < 500 ms trong cửa sổ 5 phút |
| Database latency | p95 `nexus_db_operation_duration_seconds` | < 100 ms trong cửa sổ 5 phút |
| Database readiness | `nexus_dependency_ready{dependency="database"}` | Luôn bằng 1 khi service nhận traffic |
| Worker success | `success / total worker tasks` | ≥ 99% trong 30 ngày |
| Worker latency | p95 `nexus_worker_task_duration_seconds` | < 60 giây; export lớn cần SLO riêng |

Coverage hiện đo HTTP status và latency, SQLAlchemy operation, pool checkout, PostgreSQL exporter, worker outcomes và readiness. Nó chưa đo browser RUM, RabbitMQ queue depth, Redis server metrics hoặc OpenAI provider SLI.

## Dashboard

Dashboard `NEXUS AI Overview` được provision từ `infrastructure/observability/grafana/dashboards/nexus-overview.json` và gồm:

- API availability, request rate, p50/p95 latency và 5xx rate.
- Database p95, operation errors, application pool checkout và PostgreSQL active connections.
- Worker success/retry/failure rate và duration.
- Dependency readiness timeline.

Grafana dùng Prometheus làm datasource mặc định và Tempo để tra trace. Request log chứa `request_id`, `trace_id` và `span_id`, cho phép đi từ log sang trace mà không dùng customer identifier.

## Chạy local

Thay `GRAFANA_ADMIN_PASSWORD` trong `.env`, sau đó:

```powershell
docker compose --env-file .env -f infrastructure/docker/compose.yml --profile observability up -d --build
docker compose --env-file .env -f infrastructure/docker/compose.yml --profile observability ps
```

Endpoint local:

- Grafana: `http://127.0.0.1:3001`
- Prometheus: `http://127.0.0.1:9090`
- API metrics: `http://127.0.0.1:8000/metrics`
- API liveness/readiness: `/health/live`, `/health/ready`

Không expose Grafana, Prometheus, worker metrics hoặc `/metrics` ra Internet. AWS ALB hiện chỉ forward `/api/*` và `/health/*`; metrics cần private collector hoặc VPC-only scrape khi triển khai staging.

## Alert thresholds

| Alert | Điều kiện | Thời gian | Owner/action |
|---|---|---:|---|
| `NexusApiHighErrorRate` | 5xx rate > 5% | 10 phút | Backend on-call, kiểm tra deploy và trace lỗi |
| `NexusApiP95LatencyHigh` | API p95 > 500 ms | 10 phút | Backend, phân rã HTTP/DB trace |
| `NexusDatabaseNotReady` | readiness database = 0 | 2 phút | Platform, kiểm tra PostgreSQL/network/pool |
| `NexusDatabaseP95LatencyHigh` | DB p95 > 100 ms | 10 phút | Backend/DB owner, query plan và saturation |
| `NexusWorkerFailureRateHigh` | worker failure > 5% | 10 phút | Platform, broker/job/dead-letter inspection |

Các threshold cần được hiệu chỉnh sau tối thiểu hai tuần dữ liệu staging. Alert hiện là Prometheus rules; Alertmanager/on-call routing chưa được cấu hình nên chưa có notification delivery.

## Quy trình điều tra incident

1. Xác nhận impact bằng availability/error/latency panel; ghi timestamp và request ID mẫu.
2. Kiểm tra `/health/live` và `/health/ready`. Liveness fail nghĩa là process/container; readiness fail nghĩa là dependency không sẵn sàng.
3. Tìm structured log theo `request_id`, sau đó mở Tempo trace bằng `trace_id`.
4. Nếu DB chậm: kiểm tra DB histogram, checked-out pool, `pg_stat_activity_count`, RDS health và migration gần nhất. Không log hoặc copy raw customer SQL parameters.
5. Nếu worker lỗi: kiểm tra success/retry/failure rate, Celery log theo correlation ID, RabbitMQ health và durable job/dead-letter state.
6. Đối chiếu deployment revision, ECS events và dependency changes. Không rotate/delete audit records để “khắc phục” signal.
7. Chọn recovery nhỏ nhất, xác minh readiness và theo dõi ít nhất hai cửa sổ alert trước khi đóng incident.

## Recovery procedures

- API regression: rollback ECS task definitions theo `docs/deployment/staging-runbook.md`; schema chỉ roll-forward trừ khi downgrade đã được chứng minh an toàn.
- PostgreSQL unavailable: tạm ngừng deployment/write workflows, kiểm tra RDS event/storage/connections, restore snapshot vào instance mới nếu data corruption được xác nhận.
- Redis unavailable: cache fail-open; theo dõi DB load trước khi restart/replace cache.
- RabbitMQ/worker unavailable: API durable job rows vẫn là nguồn sự thật; khôi phục broker/worker rồi replay theo idempotency policy, không tạo job duplicate thủ công.
- OTel/Prometheus/Grafana unavailable: application tiếp tục phục vụ; khôi phục collector sau vì telemetry failure không được làm fail business request.

## Privacy và cardinality

- HTTP metrics dùng route template, không dùng raw URL hoặc query string.
- DB metrics chỉ có `select`, `insert`, `update`, `delete`, `other`; không export statement/parameter.
- Worker metrics chỉ có task name bounded và status; không có job/tenant ID.
- JSON formatter dùng allowlist và bỏ `authorization`, `user_id`, `organization_id` cùng arbitrary extras.
- Trace instrumentation không capture request/response body hoặc headers.
- Trace sampling mặc định 10%; local observability profile dùng 100% để kiểm chứng.

## Kết quả xác minh Task 28

- Controlled readiness failure trả HTTP 503 và chuyển `nexus_dependency_ready` về 0.
- Metrics test xác nhận route template `/api/v1`; raw private path được gộp thành `unmatched`.
- Logging test xác nhận bearer token, tenant/user ID không xuất hiện; trace/span ID được correlate.
- Worker test xác nhận success/failure metrics không chứa job ID.
- OpenTelemetry in-memory exporter xác nhận server span chứa request ID nhưng không capture authorization header hoặc body.
- PostgreSQL disposable integration test xác nhận success/error timings, pool gauge trở về 0 và SQL/table name không xuất hiện trong metrics.
- Grafana dashboard JSON, Prometheus rules, OTel Collector và Tempo config đã được static-validated; UI dashboard chưa được kiểm chứng trực quan trong phiên này.
- Regression không phụ thuộc hạ tầng: 65 pass, 58 integration/performance tests deselected. Database metrics integration riêng: 2 pass trên PostgreSQL disposable.

