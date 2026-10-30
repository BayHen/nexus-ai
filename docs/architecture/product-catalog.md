# Kiến trúc Product Catalog

## Phạm vi Task 11

Module `catalog` triển khai CRUD cho Product và Category dưới active organization context. Mọi query và uniqueness constraint đều có `organization_id`; client không được gửi tenant ID để chọn dữ liệu.

## Mô hình dữ liệu

### Category

- `name`, `slug`, `description`.
- Soft delete bằng `deleted_at`.
- Partial unique index cho `(organization_id, name)` và `(organization_id, slug)` khi `deleted_at IS NULL`.
- Composite unique `(organization_id, id)` làm đích cho foreign key tenant-safe từ Product.

### Product

- `sku` do server sinh, không có trong request schema.
- `name`, `description`, `price`, `status`, optional `category_id`.
- `price` dùng PostgreSQL `NUMERIC(19,4)` và Python `Decimal`; API và `CHECK price >= 0` cùng bảo vệ giá không âm.
- `status` chỉ nhận `draft`, `active`, `archived` bằng API enum và database check constraint.
- Soft delete đặt `deleted_at` và chuyển status thành `archived`.
- Composite foreign key `(organization_id, category_id)` ngăn Product tenant A trỏ tới Category tenant B.

### SKU counter

`catalog_sku_counters` có một row cho mỗi organization. PostgreSQL `INSERT ... ON CONFLICT DO UPDATE ... RETURNING` tăng counter nguyên tử trong cùng transaction tạo Product. SKU có dạng `PRD-000001` và unique trong tenant. Hai tenant có thể có cùng chuỗi SKU mà không xung đột.

Nếu transaction Product rollback, counter update cũng rollback; request thất bại không làm tiêu hao SKU.

## Quy tắc xóa Category

`DELETE /categories/{id}` khóa Category row. Nếu còn Product chưa soft-delete, API trả `409 catalog_conflict`; không cascade và không tự gỡ category khỏi Product. Sau khi toàn bộ Product liên quan đã soft-delete, Category mới được soft-delete.

Product creation/category reassignment cũng khóa Category row khi kiểm tra. Điều này tránh race trong đó Category bị xóa đồng thời với Product mới.

## Giá và future Order snapshots

`Product.price` là giá catalog hiện tại, không phải lịch sử tài chính. Khi Order module được triển khai, mỗi Order Line bắt buộc copy giá tại thời điểm xác nhận vào trường riêng như `unit_price NUMERIC(19,4)`. Order totals phải tính từ snapshot đó và không đọc lại `Product.price`; việc đổi giá hoặc soft-delete Product không được thay đổi order lịch sử. Order module vẫn **PLANNED**.

## API

| Method và path | Mô tả |
|---|---|
| `POST /api/v1/categories` | Tạo Category |
| `GET /api/v1/categories` | Search, sort và paginate Category active |
| `GET /api/v1/categories/{id}` | Đọc Category tenant-scoped |
| `PATCH /api/v1/categories/{id}` | Cập nhật Category |
| `DELETE /api/v1/categories/{id}` | Soft-delete nếu không còn Product active |
| `POST /api/v1/products` | Tạo Product và sinh SKU |
| `GET /api/v1/products` | Search/filter/sort/paginate Product active |
| `GET /api/v1/products/{id}` | Đọc Product tenant-scoped |
| `PATCH /api/v1/products/{id}` | Cập nhật Product; SKU không thay đổi |
| `DELETE /api/v1/products/{id}` | Soft-delete Product |

Product search kiểm tra `name`, `description`, `sku`; filter hỗ trợ `category_id`, `status`, `min_price`, `max_price`; sort hỗ trợ `name`, `price`, `sku`, `created_at`. Category search kiểm tra `name`, `description`; sort hỗ trợ `name`, `created_at`. `page_size` tối đa 100.

## Authorization

- Owner/Admin: read, create, update, soft-delete.
- Manager: read, create, update; không delete.
- Staff/Viewer: read-only.

Cross-tenant IDs trả `404`; cross-tenant `category_id` trả `422 category_unavailable`. Header hoặc query `organization_id` không thay đổi server-side tenant context.
