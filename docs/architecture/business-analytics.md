# Revenue và business analytics

## Phạm vi API

Các endpoint đều yêu cầu authentication, active tenant context và quyền `audit:read`:

- `GET /api/v1/analytics/summary`;
- `GET /api/v1/analytics/revenue?granularity=day|month`;
- `GET /api/v1/analytics/products/best-selling`;
- `GET /api/v1/analytics/inventory-valuation`;
- `GET /api/v1/analytics/revenue/branches`;
- `POST /api/v1/analytics/exports` với `Idempotency-Key`;
- `GET /api/v1/analytics/exports/{job_id}/download`.

Các endpoint revenue nhận `date_from`, `date_to` theo ngày UTC, bao gồm trọn `date_to`. Query dùng khoảng nửa mở `[date_from 00:00, date_to + 1 ngày 00:00)` để tránh lỗi precision ở cuối ngày. `currency` là mã ISO ba chữ in hoa và mặc định `USD`; hệ thống không cộng nhiều currency vào một số tổng.

## Chính sách revenue recognition

Một Order chỉ được ghi nhận khi đồng thời:

1. Order có trạng thái `completed`;
2. PaymentIntent thuộc cùng organization và Order;
3. PaymentIntent có trạng thái `succeeded` hoặc `refunded`;
4. `succeeded_at` tồn tại và nằm trong date range.

Công thức:

```text
gross revenue = tổng PaymentIntent.amount hợp lệ
refund = tổng PaymentRefund.amount có status = succeeded của các payment hợp lệ
net revenue = gross revenue - refund
order count = số payment/order hợp lệ, mỗi payment đúng một order theo unique constraint
average order value = net revenue / order count
```

Refund được quy về kỳ `succeeded_at` của payment gốc, không phải ngày refund. Vì vậy báo cáo lịch sử có thể thay đổi khi refund thành công sau đó. Refund `pending` hoặc `failed` không làm giảm revenue. Base CTE tạo đúng một dòng cho mỗi PaymentIntent trước khi join `order_items`, tránh nhân doanh thu theo số item.

## Revenue theo ngày, tháng và branch

Revenue theo ngày/tháng nhóm net revenue bằng PostgreSQL `date_trunc` trên `succeeded_at` UTC.

Một Order có thể lấy hàng từ nhiều branch. Net revenue được phân bổ theo tỷ lệ line snapshot:

```text
branch net revenue = line_total × (payment net amount / payment gross amount)
```

Do PaymentIntent amount phải dương và bằng Order total tại payment workflow, mẫu số không bằng 0. Tổng branch allocation reconciles với total net revenue, ngoại trừ sai số Decimal được chuẩn hóa về bốn chữ số thập phân ở API boundary.

## Best-selling Product

Xếp hạng dùng tổng `OrderItem.quantity` của các paid completed Order và giữ SKU/name/price snapshot tại thời điểm Order. `gross_sales` là tổng `line_total` snapshot. Refund không làm giảm quantity vì hệ thống hiện chưa có return-item ledger để biết sản phẩm nào được trả; đây là chỉ số gross unit sales, không phải net units retained.

## Inventory valuation

Policy hiện tại là `current_retail_price`:

```text
valuation = tổng current StockLevel.quantity × current Product.price
```

Đây là retail valuation, không phải inventory cost, COGS hay chuẩn kế toán. Product chưa có currency riêng nên valuation được trả theo reporting currency do caller chọn; production multi-currency cần price currency và FX policy trước khi sử dụng số liệu tài chính.

## Query và index

Migration `20261031_0011` bổ sung:

- `ix_payment_intents_analytics (organization_id, currency, status, succeeded_at, order_id)` cho tenant/currency/date recognition scan;
- `ix_payment_refunds_org_status_payment (organization_id, status, payment_id)` cho refund aggregation;
- `ix_order_items_org_branch_order (organization_id, branch_id, order_id)` cho branch allocation;
- index export theo `(organization_id, created_at)`.

Tất cả query bắt đầu bằng `organization_id`. Payment refund được aggregate trước khi join; Product và branch grouping chạy hoàn toàn trong PostgreSQL, không tải toàn bộ source rows về Python.

## Export CSV và Excel

`POST /analytics/exports` tạo durable background job `export_business_analytics`. Celery/RabbitMQ xử lý job và lưu artifact immutable trong PostgreSQL:

- CSV dùng UTF-8 BOM để tương thích Excel;
- XLSX có sheet `Summary` và `Revenue by day`;
- download luôn kiểm tra active tenant trước khi trả nội dung;
- `(organization_id, task_name, idempotency_key)` ngăn tạo export trùng.

Lưu binary trong PostgreSQL phù hợp artifact nhỏ của portfolio hiện tại. Production report lớn nên chuyển sang object storage, checksum, size limit, retention và signed URL; PostgreSQL chỉ giữ metadata.

## Giới hạn báo cáo

- Chưa có timezone theo organization; mọi kỳ dùng UTC.
- Refund được back-attribute về kỳ thanh toán ban đầu.
- Chưa có tax, discount, shipping, FX, COGS hoặc item-level return allocation riêng.
- Inventory valuation dùng giá bán hiện tại và có thể thay đổi khi Product price đổi.
- Analytics là query trực tiếp source-of-truth, chưa có materialized view; cần EXPLAIN ANALYZE trên production-like volume trước khi thêm aggregate table.
- XLSX/CSV hiện chứa summary và daily revenue; các sheet chi tiết khác có thể bổ sung khi có yêu cầu nghiệp vụ rõ ràng.
