# Kiến trúc Secure Payment Processing

## Phạm vi Task 15

Module `payments` cung cấp abstraction `PaymentProvider` và adapter `SandboxPaymentProvider`. Sandbox chỉ tạo provider token giả lập; API không có field PAN, CVV, expiry hoặc cardholder data và strict schema từ chối field lạ. Module này không xử lý thanh toán thật.

## Trust boundary

- API tạo Payment Intent, đọc trạng thái, tạo Refund và đọc audit yêu cầu JWT, active tenant context và RBAC.
- Webhook không dùng JWT vì đại diện cho provider, nhưng bắt buộc HMAC-SHA256 trên raw request body qua `X-Payment-Signature`.
- Secret lấy từ `PAYMENT_WEBHOOK_SECRET`, tối thiểu 32 ký tự, không ghi vào log/audit/response.
- Verification dùng constant-time comparison.
- Sandbox simulation endpoints chỉ hoạt động ở `development` và `test`; staging/production trả `404`.
- Mọi Order/Payment/Refund lookup từ business API đều có `organization_id`. Cross-tenant ID trả `404`.

## Provider interface

`PaymentProvider` định nghĩa:

- `create_intent(amount, currency, idempotency_key)`
- `create_refund(payment_intent_id, amount, idempotency_key)`
- `verify_webhook(raw_body, signature)`
- sandbox event builder phục vụ test/simulation

Adapter thật trong tương lai phải giữ provider-side idempotency, timeout/retry policy, secret management và webhook verification tương đương. Không được đưa SDK/provider object vào domain model.

## State machine

### Payment

```text
pending ──payment.failed────> failed
   │                            │
   └──payment.succeeded─────────┴──> succeeded ──full refund──> refunded
```

- Intent chỉ được tạo cho Order `confirmed` có total lớn hơn 0.
- `payment.failed` giữ Order ở `confirmed`, cho phép cùng intent nhận event success sau retry.
- `payment.succeeded` chuyển Payment sang `succeeded` và Order từ `confirmed` sang `completed` trong cùng transaction.
- Event failure đến sau `succeeded/refunded` bị ghi audit dạng ignored, không đảo ngược lịch sử.
- Tổng Refund succeeded bằng Payment amount chuyển Payment sang `refunded`. Partial refund giữ Payment `succeeded`.

### Refund

```text
pending ──refund.failed────> failed
   │                          │
   └──refund.succeeded────────┴──> succeeded
```

Refund chỉ được tạo khi Payment đang `succeeded`. Tổng các Refund `pending` và `succeeded` không được vượt Payment amount.

## Idempotency và duplicate protection

- Tạo Payment Intent bắt buộc `Idempotency-Key`; unique constraint `(organization_id, idempotency_key)` và request fingerprint bảo vệ payload reuse.
- Một Order chỉ có một Payment Intent qua unique `(organization_id, order_id)`. Retry với key cũ trả cùng intent; key mới không tạo charge thứ hai.
- Refund cũng có tenant-scoped idempotency key và fingerprint.
- Provider event có unique `(provider, event_id)` và SHA-256 payload digest.
- Replay cùng event ID/cùng payload trả `duplicate=true`; cùng event ID nhưng payload khác trả `409`.
- Webhook handler khóa Payment/Refund và Order bằng `SELECT ... FOR UPDATE`; concurrent delivery không complete Order hai lần.

Sandbox provider sinh provider ID deterministic từ tenant-scoped idempotency key, mô phỏng provider-side retry safety.

## Transaction boundary

Webhook success thực hiện trong một database transaction:

1. Khóa Payment bằng provider intent ID.
2. Kiểm tra/deduplicate event.
3. Khóa Order liên quan.
4. Kiểm tra Order còn `confirmed` hoặc đã `completed` bởi cùng Payment.
5. Cập nhật Payment và Order.
6. Append audit log và webhook event.
7. Commit toàn bộ.

Nếu Order đã cancelled, payload không hợp lệ, event conflict, database constraint hoặc audit insert thất bại, toàn bộ transaction rollback. Payment không được ghi `succeeded` riêng lẻ.

## Audit và retention

`payment_audit_logs` ghi intent creation, payment transition, refund creation/transition và ignored events. `payment_webhook_events` lưu provider, event ID/type, payload digest và timestamp; không lưu card data hoặc secret.

PostgreSQL trigger:

- Cấm `DELETE` mọi Payment Intent và Refund.
- Cấm `UPDATE/DELETE` webhook event và payment audit log.
- Foreign keys dùng `RESTRICT` để confirmed financial history không bị cascade delete.

## Failure scenarios

| Scenario | Kết quả |
|---|---|
| Thiếu/sai webhook signature | `401 invalid_webhook_signature`, không ghi state/event |
| Payload webhook sai schema | `422 invalid_webhook_payload` |
| Event ID replay đúng payload | `200`, `duplicate=true`, không transition lần hai |
| Event ID replay khác payload | `409 payment_conflict` |
| Provider intent/refund không tồn tại | `404`, không ghi event |
| Order chưa confirmed hoặc đã cancelled | Intent/success webhook bị từ chối; transaction rollback |
| Payment failed | Order giữ `confirmed`; intent có thể nhận success retry |
| Reuse idempotency key khác payload | `409 payment_conflict` |
| Refund vượt amount còn lại | `409 payment_conflict` |
| Cross-tenant payment/refund ID | `404` |
| Card-like/unknown request field | `422` |

## API

| Method và path | Mô tả |
|---|---|
| `POST /api/v1/payments/intents` | Tạo/replay Payment Intent cho Order confirmed |
| `GET /api/v1/payments/intents/{payment_id}` | Theo dõi trạng thái Payment |
| `POST /api/v1/payments/intents/{payment_id}/refunds` | Tạo Refund pending |
| `GET /api/v1/payments/intents/{payment_id}/refunds/{refund_id}` | Đọc Refund state |
| `GET /api/v1/payments/intents/{payment_id}/audit` | Đọc append-only audit history |
| `POST /api/v1/payments/webhooks/sandbox` | Nhận HMAC-signed provider event |
| `POST /api/v1/payments/sandbox/intents/{payment_id}/simulate` | Simulation success/failure ở development/test |
| `POST /api/v1/payments/sandbox/refunds/{refund_id}/simulate` | Simulation refund ở development/test |

## Giới hạn

- Sandbox không kết nối payment network, không có settlement, dispute, chargeback hoặc reconciliation.
- Webhook timestamp/tolerance chưa có vì sandbox event không chứa provider timestamp; adapter thật phải chống replay theo timestamp ngoài unique event ID.
- Order `completed` không tự đổi sang `cancelled` khi refund; financial state và fulfillment state được giữ tách biệt.
- Currency conversion và multi-currency accounting chưa triển khai; amount snapshot dùng currency do intent chọn.
- Migration `0008` mở rộng Order status với `completed`; deployment phải chạy migration trước khi bật Payment API và không nên chạy đồng thời application revision cũ không hiểu status này. Downgrade về `0007` yêu cầu không còn Order `completed` hoặc phải có kế hoạch chuyển đổi dữ liệu được phê duyệt.

Payment transition append transactional outbox và immutable business audit trong cùng transaction; crash recovery, retry và reconciliation được mô tả tại [tài liệu độ tin cậy Order/Payment](order-payment-reliability.md).
