# Kiến trúc Order Management

## Phạm vi Task 14

Module `orders` quản lý draft Order, item mutations, confirmation, cancellation và lịch sử Order theo active organization. Client không gửi `organization_id`, giá snapshot hoặc total; service lấy toàn bộ dữ liệu này từ tenant context và database.

## State machine

```text
draft ──confirm──> confirmed ──payment success──> completed
  │
  └────────────cancel──────────> cancelled
                        confirmed ──cancel──> cancelled
```

- Order mới luôn ở `draft`.
- Chỉ `draft` được thêm, đổi quantity hoặc xóa item.
- `draft` chỉ được confirm khi có ít nhất một item và tất cả stock đều đủ.
- `draft` có thể cancel mà không thay đổi Inventory vì chưa giữ stock.
- `confirmed` có thể cancel; transaction hoàn lại đúng quantity đã trừ.
- `confirmed` chuyển sang `completed` khi Payment webhook success được commit atomically.
- `completed` là trạng thái kết thúc của Order; Refund không đảo ngược fulfillment state.
- `cancelled` là trạng thái kết thúc. Confirm lại, cancel lại hoặc sửa item đều trả `409 invalid_order_state`.

Database `CHECK` giới hạn status ở `draft`, `confirmed`, `cancelled`. Service khóa Order bằng `SELECT ... FOR UPDATE` trước mọi mutation hoặc transition, vì vậy hai confirmation đồng thời không thể cùng thành công.

## Chính sách Inventory

Task 14 dùng chính sách **deduct on confirmation**:

1. Draft không reserve và không làm thay đổi stock.
2. Confirmation khóa Order, đọc items, rồi khóa từng stock row theo thứ tự `(branch_id, product_id)` ổn định.
3. Nếu thiếu stock row hoặc bất kỳ quantity nào không đủ, toàn bộ transaction rollback; Order vẫn là `draft`, mọi stock và movement giữ nguyên.
4. Nếu đủ stock, service trừ tất cả stock, thêm immutable Inventory adjustment movement có `reference = ORDER:{order_id}`, rồi chuyển Order sang `confirmed` trong cùng transaction.
5. Cancellation của Order confirmed khóa lại các stock rows, cộng trả quantity, thêm movement hoàn kho và chuyển sang `cancelled` trong cùng transaction.

Negative-stock policy của Inventory không áp dụng cho confirmation: Order luôn yêu cầu đủ stock, kể cả organization đã cho phép manual adjustment âm.

## Price snapshot và total

Khi thêm item, server đọc Product active và lưu:

- `product_sku_snapshot`
- `product_name_snapshot`
- `unit_price_snapshot NUMERIC(19,4)`
- `quantity NUMERIC(19,4)`
- `line_total = unit_price_snapshot * quantity`

API không nhận `unit_price`, `line_total` hoặc `total_amount` từ client. Khi đổi quantity, line total và Order total được tính lại phía server từ snapshot. Việc Product đổi tên/giá hoặc bị soft-delete sau đó không thay đổi lịch sử Order.

PostgreSQL trigger từ chối thay đổi Product, Branch, SKU/name snapshot hoặc unit price snapshot trên item. Database check bảo đảm quantity dương, giá không âm và `line_total` đúng phép nhân.

## Tenant isolation và authorization

Order và OrderItem đều có `organization_id`. Item dùng composite foreign keys tới Order, Product và Branch, ngăn liên kết chéo tenant ở database.

| Permission | Owner | Admin | Manager | Staff | Viewer |
|---|:---:|:---:|:---:|:---:|:---:|
| `order:read` | Có | Có | Có | Có | Có |
| `order:write` | Có | Có | Có | Có | Không |
| `order:confirm` | Có | Có | Có | Có | Không |
| `order:cancel` | Có | Có | Có | Không | Không |

Cross-tenant Order/Product/Branch IDs trả `404`. Client không thể chọn tenant bằng query hoặc header tùy ý.

## API

| Method và path | Mô tả |
|---|---|
| `POST /api/v1/orders` | Tạo draft Order |
| `GET /api/v1/orders` | Lịch sử có status/date filter và pagination |
| `GET /api/v1/orders/{order_id}` | Đọc Order và item snapshots |
| `POST /api/v1/orders/{order_id}/items` | Thêm item vào draft |
| `PATCH /api/v1/orders/{order_id}/items/{item_id}` | Đổi quantity của draft item |
| `DELETE /api/v1/orders/{order_id}/items/{item_id}` | Xóa draft item |
| `POST /api/v1/orders/{order_id}/confirm` | Confirm và trừ stock atomically |
| `POST /api/v1/orders/{order_id}/cancel` | Cancel; hoàn stock nếu đã confirmed |

Filter lịch sử hỗ trợ `status`, `created_from`, `created_to`, `page`, `page_size`; `page_size` tối đa 100.

## Giới hạn đã biết

- Task 14 chưa có Customer, shipping, tax, discount, payment hoặc fulfillment workflow; các phần này là **PLANNED**.
- Confirmation retry sau khi thành công trả `409` theo state machine; command idempotency key cho client retry xuyên network chưa được triển khai.
- Draft không reserve stock, nên khả năng fulfill chỉ được bảo đảm tại thời điểm confirmation.
- Cancellation hiện luôn hợp lệ với Order `confirmed`; shipment/fulfillment eligibility sẽ cần policy bổ sung khi module tương ứng được triển khai.

Order transition quan trọng append transactional outbox và immutable business audit trong cùng transaction. Xem [độ tin cậy Order/Payment](order-payment-reliability.md).
