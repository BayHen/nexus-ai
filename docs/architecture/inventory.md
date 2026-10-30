# Kiến trúc Inventory Management

## Phạm vi Task 12

Module `inventory` quản lý on-hand stock theo Branch và Product, adjustment, transfer, low-stock threshold, reporting và immutable movement ledger. Branch đóng vai trò warehouse/location trong Task này.

## Mô hình dữ liệu và tenant isolation

`inventory_stock_levels` dùng composite primary key `(organization_id, branch_id, product_id)`. Composite foreign keys tới Branch và Product bảo đảm cả ba định danh thuộc cùng tenant. Client không gửi `organization_id`; service luôn lấy từ server-side `TenantContext`.

Quantity và threshold dùng `NUMERIC(19,4)`/Python `Decimal`. Threshold có database check `>= 0`.

## Concurrency và transaction boundary

Adjustment khóa stock row bằng `SELECT ... FOR UPDATE` trước khi tính quantity mới. Transfer khóa cả source và destination rows theo thứ tự UUID ổn định, sau đó cập nhật hai rows và thêm ledger entry trong cùng transaction.

Nếu validation, negative-stock policy, foreign key hoặc ledger insert thất bại, transaction rollback toàn bộ. Không có trạng thái source đã trừ nhưng destination chưa cộng.

## Negative stock policy

`inventory_policies.allow_negative_stock` là policy phía server, mặc định `false`. Owner có thể bật/tắt qua `/inventory/policy`; không thể tắt khi vẫn còn stock âm.

Service kiểm tra policy dưới row lock. PostgreSQL trigger `inventory_negative_stock_policy` kiểm tra lại mọi `INSERT/UPDATE quantity`, nên direct SQL cũng không thể tạo stock âm khi policy tắt.

## Idempotency

Adjustment và transfer bắt buộc header `Idempotency-Key` dài tối đa 128 ký tự. Ledger có unique constraint `(organization_id, idempotency_key)` và lưu SHA-256 request fingerprint.

- Replay cùng key và cùng payload trả movement cũ với `replayed=true`.
- Cùng key nhưng payload khác trả `409 idempotency_conflict`.
- Key của tenant khác không xung đột.
- Counter/state update và ledger insert cùng transaction, vì vậy failed request không giữ key hoặc partial quantity.

## Movement ledger

Mỗi movement lưu:

- `movement_type`: `adjustment` hoặc `transfer`.
- Product, source/destination Branch.
- Signed `quantity_delta` cho adjustment; positive quantity cho transfer.
- Source/destination quantity snapshots sau operation.
- `reference`, `reason`, actor, idempotency key và timestamp.

Database trigger `inventory_movements_immutable` từ chối `UPDATE` và `DELETE`. API chỉ expose read/list; không có endpoint sửa ledger.

## API

| Method và path | Mô tả |
|---|---|
| `POST /api/v1/inventory/stocks` | Khởi tạo stock record ở quantity 0 |
| `GET /api/v1/inventory/stocks` | Search/report theo Product, Branch và low-stock state |
| `PATCH /api/v1/inventory/stocks/{branch_id}/{product_id}` | Cập nhật low-stock threshold |
| `POST /api/v1/inventory/adjustments` | Điều chỉnh signed quantity, bắt buộc idempotency |
| `POST /api/v1/inventory/transfers` | Transfer atomic giữa hai Branch |
| `GET /api/v1/inventory/movements` | Movement history với Product/Branch/type/time filters |
| `GET /api/v1/inventory/policy` | Đọc negative-stock policy |
| `PATCH /api/v1/inventory/policy` | Owner thay đổi policy |

## Authorization

- Owner: read/manage/adjust/policy.
- Admin: read/manage/adjust.
- Manager: read/manage/adjust.
- Staff: read/adjust.
- Viewer: read-only.

Cross-tenant Branch/Product/stock IDs trả `404`; query/header tenant giả mạo không thay đổi context.
