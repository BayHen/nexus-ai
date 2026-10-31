# Xử lý nền với Celery và RabbitMQ

## Kiến trúc

Task 18 giữ NEXUS AI là Modular Monolith. Celery worker chạy cùng source code và database schema với API; RabbitMQ chỉ vận chuyển thông điệp chứa `job_id`. PostgreSQL lưu tenant context, payload, trạng thái, attempt count, kết quả và error code trong `background_jobs` nên Celery result backend không phải nguồn trạng thái nghiệp vụ.

Bốn loại job được hỗ trợ:

- `generate_business_report`: tạo snapshot đếm Product và Order, lưu vào `business_reports`;
- `send_notification_email`: dùng test provider xác định, không gửi email ra Internet, lưu `notification_deliveries`;
- `process_low_stock_alerts`: tìm stock có `quantity <= low_stock_threshold`, lưu `low_stock_alerts`;
- `process_transactional_outbox`: claim event theo đúng organization rồi dùng inbox receipt hiện có để consume idempotent.

Các bảng output là immutable bằng PostgreSQL trigger. Chúng không chứa credential, token hoặc nội dung email body.

## Idempotency và tenant boundary

Unique constraint `(organization_id, task_name, idempotency_key)` bảo đảm cùng một yêu cầu chỉ tạo một job. Worker khóa row bằng `SELECT ... FOR UPDATE`; delivery lặp lại của job đã `succeeded` không chạy handler lần nữa. Output có unique constraint theo `job_id`, và outbox tiếp tục dùng unique inbox receipt.

Scheduler kiểm tra organization tồn tại trước khi tạo job. Executor kiểm tra lại tenant từ durable state trước mỗi lần chạy. Celery message không được phép cung cấp hoặc ghi đè `organization_id`; worker chỉ nhận `job_id` rồi đọc tenant từ PostgreSQL.

## Retry và dead-letter

Lỗi infrastructure không vĩnh viễn đặt job thành `retrying`. Celery retry theo exponential backoff từ `NEXUS_BACKGROUND_JOB_RETRY_BASE_SECONDS`, tối đa 300 giây và không vượt `max_attempts`. Input không hợp lệ hoặc hết attempt đặt job thành `dead` và giữ `error_code` bounded.

RabbitMQ khai báo hai durable queue:

- `nexus.jobs`: queue xử lý chính, có dead-letter exchange;
- `nexus.jobs.dead`: giữ message bị broker reject/expire.

Job `dead` trong PostgreSQL là nguồn phục hồi nghiệp vụ chính. RabbitMQ DLQ xử lý lỗi transport; khi durable job chuyển `dead`, task adapter trả trạng thái đó và không retry tiếp, nên không giả định mọi failure đều tự xuất hiện trong RabbitMQ DLQ.

## Quan sát

Structured log gồm `job_id`, `task_name`, `organization_id`, `attempt_count`, `max_attempts` và `correlation_id`; không log payload hoặc broker URL. API có quyền `audit:read` có thể dùng:

- `GET /api/v1/background/jobs`: 100 job gần nhất của active tenant;
- `GET /api/v1/background/metrics`: số job theo trạng thái của active tenant.

Metric hiện là query PostgreSQL tại thời điểm request, chưa export Prometheus. Alert production nên cảnh báo khi `dead > 0`, job `running` quá lease dự kiến, hoặc queue depth tăng liên tục; dashboard/alert tự động vẫn thuộc Task observability sau.

## Khởi động local

Tạo `.env` từ `.env.example`, thay password local, sau đó:

```powershell
docker compose --env-file .env -f infrastructure/docker/compose.yml up -d postgres redis rabbitmq

Set-Location backend
.\.venv\Scripts\Activate.ps1
alembic upgrade head
celery -A nexus.platform.background.celery_app:celery_app worker --pool=solo --loglevel=INFO
```

`--pool=solo` phù hợp Windows local. Linux có thể dùng prefork mặc định. Kiểm tra worker:

```powershell
celery -A nexus.platform.background.celery_app:celery_app inspect ping --timeout=5
```

RabbitMQ management UI local nằm tại `http://127.0.0.1:15672`; không expose management port công khai ở production.

## Recovery runbook

1. Kiểm tra RabbitMQ health, queue depth và worker log theo correlation ID.
2. Kiểm tra `/api/v1/background/metrics` và job `dead`; không sửa trực tiếp output immutable.
3. Với job `retrying`, khôi phục dependency rồi để Celery retry. Nếu worker crash sau DB commit nhưng trước ACK, redelivery là an toàn nhờ trạng thái `succeeded`.
4. Với job `dead`, xác định error code và sửa nguyên nhân. Tạo job mới với idempotency key mới sau khi được operator phê duyệt; không đổi job cũ thành `queued` vì sẽ xóa dấu vết failure.
5. Với message trong `nexus.jobs.dead`, đối chiếu `job_id` với PostgreSQL trước khi republish. Không bulk replay khi chưa xác minh tenant và tính idempotent.
6. Khi rollback code, dừng worker trước, rollback application, và chỉ downgrade migration nếu chắc chắn không cần giữ lịch sử job. Backup PostgreSQL và RabbitMQ volume trước thao tác stateful.

## Giới hạn

- Chưa có scheduler API công khai; application service ở Task nghiệp vụ sau sẽ tạo durable job rồi dispatch sau commit.
- Test provider chỉ ghi delivery record, không mô phỏng SMTP.
- Chưa có Celery Beat schedule hoặc autoscaling worker.
- RabbitMQ local dùng credential development; production cần secret manager, TLS, private network và account least privilege.
