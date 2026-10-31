# Độ tin cậy Order và Payment

## Phạm vi Task 16

Task 16 triển khai transactional outbox, idempotent local consumer, retry/dead-letter policy, crash recovery, immutable business audit, correlation ID và reconciliation cho Order/Payment trong cùng Modular Monolith. Không tạo microservice, broker hoặc network hop mới.

## Consistency guarantees

### Atomic business state và event

Order/Payment transition, `outbox_events` và `business_audit_events` được insert bằng cùng `AsyncSession` transaction. Vì vậy:

- Commit thành công: business state, event và audit cùng tồn tại.
- Constraint/audit/outbox insert thất bại: toàn bộ transaction rollback.
- Không có trạng thái Payment `succeeded` hoặc Order `completed` đã commit nhưng event tương ứng bị mất do application crash trước một commit thứ hai.

Các event hiện có gồm `order.confirmed`, `order.cancelled`, `order.completed`, `payment.intent.created`, `payment.succeeded`, `payment.failed` và các transition Refund.

### Delivery semantics

Outbox cung cấp **at-least-once delivery**. Consumer dùng `inbox_receipts` với unique `(consumer_name, event_id)` để đạt **effectively-once side effects** cho từng consumer:

1. Worker claim event bằng `SELECT ... FOR UPDATE SKIP LOCKED`.
2. Claim ghi `processing`, `locked_by`, `locked_at` và được commit trước khi xử lý.
3. Consumer kiểm tra inbox receipt trong transaction.
4. Nếu chưa có, consumer ghi receipt và chuyển event sang `published` atomically.
5. Redelivery sau commit thấy receipt, không chạy side effect lần hai.

Không tuyên bố exactly-once delivery trên network. Adapter broker tương lai vẫn phải dùng event ID và idempotent consumer.

## Crash recovery và retry

- Worker crash sau claim để lại event `processing`.
- Worker khác reclaim khi `locked_at` cũ hơn lease timeout.
- Worker ID phải khớp lease; worker khác không thể xử lý event chưa hết lease.
- Failure tăng `attempt_count`, lưu error code bounded và trả event về `pending`.
- Exponential backoff: `base_seconds × 2^(attempt-1)`, tối đa 300 giây.
- Khi `attempt_count >= max_attempts`, event chuyển `dead` và cần operator review.
- Error code, event type, attempt count và correlation ID được log; payload không được log.

`max_attempts` được lưu trên từng event để policy có thể thay đổi cho event mới mà không làm thay đổi event đang chờ.

## Ordering trade-off

Outbox sắp xếp claim theo `available_at`, `created_at`, `id`, nhưng không cam kết global ordering khi có nhiều worker hoặc retry. Consumer phải xử lý out-of-order delivery và không suy diễn current business state chỉ từ event đến cuối cùng. Source of truth vẫn là PostgreSQL Order/Payment state.

Test Task 16 cố ý consume hai event theo thứ tự ngược và xác nhận mỗi event chỉ có một inbox receipt.

## Duplicate protection

- HTTP command tiếp tục dùng tenant-scoped idempotency key.
- Payment webhook dùng unique provider event ID và payload digest.
- Outbox event có stable UUID.
- Inbox receipt unique theo consumer/event.
- Concurrent claim dùng row lock và `SKIP LOCKED`.

Các lớp này giải quyết duplicate ở boundary tương ứng; không thay thế lẫn nhau.

## Immutable business audit

Mỗi outbox append đồng thời tạo `business_audit_events` chứa tenant, aggregate, event type, correlation ID, bounded business details và timestamp. PostgreSQL trigger cấm `UPDATE` và `DELETE` audit/inbox history.

Outbox row không immutable vì worker phải cập nhật lease/retry/published state. Business payload và event identity chỉ do writer tạo; public API không có mutation endpoint.

## Correlation và observability

`X-Request-ID` hợp lệ được middleware đưa vào ContextVar. Outbox và audit lưu correlation ID; worker logs tiếp tục dùng correlation từ event dù xử lý sau request ban đầu.

Structured signals:

| Event log | Câu hỏi vận hành |
|---|---|
| `outbox_claimed` | Worker có lấy được event hay backlog đứng yên? |
| `outbox_published` | Event nào hoàn tất, attempt bao nhiêu, correlation nào? |
| `outbox_consumer_failed` | Event type nào retry/dead-letter và error code nào? |
| `payment_reconciliation_completed` | Lần kiểm tra phát hiện bao nhiêu inconsistency? |

Payload, webhook secret, token và tenant business content không được log. Task 16 chưa thêm metrics exporter/dashboard; log attributes và database diagnostics đã được kiểm thử, dashboard/alert vẫn **PLANNED**.

Operational checks:

- `dead > 0`: điều tra consumer error trước khi replay thủ công.
- `processing` quá lease: worker crash hoặc mất commit; recovery worker sẽ reclaim.
- `pending` có `available_at` trong quá khứ tăng liên tục: worker không chạy hoặc database contention.
- Reconciliation finding mới: đóng băng thao tác tài chính liên quan và điều tra audit/correlation chain.

## Reconciliation

`POST /api/v1/reliability/reconcile` chỉ Owner/Admin (`payment:refund`) được chạy. Check hiện tại:

- Payment `succeeded/refunded` nhưng Order không `completed`.
- Order `completed` nhưng không có Payment `succeeded/refunded`.
- Payment amount khác Order total snapshot.

Finding được deduplicate bằng `(organization_id, finding_code, aggregate_id)` và không tự sửa financial state. Operator phải điều tra trước khi remediation. `GET /api/v1/reliability/findings` và `/outbox` luôn tenant-scoped; role cần `audit:read`.

## Failure scenarios được kiểm thử

| Scenario | Guarantee được chứng minh |
|---|---|
| Duplicate HTTP/payment request | Một Payment Intent qua idempotency và unique Order |
| Concurrent payment webhook | Một state transition, webhook retry trả duplicate |
| Worker crash sau claim | Lease timeout cho phép worker khác reclaim |
| Consumer failure | Backoff, attempt counter và dead-letter |
| Database transaction failure | Business event/audit rollback cùng transaction |
| Out-of-order consume | Receipt độc lập, không duplicate side effect |
| Duplicate consumer delivery | Một inbox receipt |
| Cross-tenant diagnostics | Outbox/finding chỉ hiển thị active tenant |
| Tamper business audit | PostgreSQL trigger từ chối |

## Trade-offs và giới hạn

- Local consumer hiện chỉ chứng minh durable dispatch/idempotency boundary; chưa publish tới RabbitMQ/Celery. Kết nối broker là bước sau và phải giữ inbox contract.
- PostgreSQL outbox tăng write amplification và cần retention/archive policy khi volume lớn.
- Reconciliation là detection, không auto-repair để tránh biến lỗi quan sát thành mutation tài chính nguy hiểm.
- Không có strict aggregate event ordering giữa nhiều worker; consumer được thiết kế idempotent và source-of-truth based.
- Không có UI/operator replay endpoint trong Task 16; dead-letter replay cần workflow được authorization và audit ở task sau.
