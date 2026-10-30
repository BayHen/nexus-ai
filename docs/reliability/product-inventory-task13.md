# Báo cáo độ tin cậy Product và Inventory – Task 13

## Phạm vi và kết luận

Audit tập trung vào Product/Category và Inventory trên PostgreSQL thật: uniqueness, concurrency, rollback, tenant isolation, pagination/search và migration compatibility. Các consistency test quan trọng đều pass; không phát hiện lỗi consistency hoặc tenant escape còn mở trong phạm vi đã kiểm tra.

## Ma trận kiểm thử integration

| Kịch bản | Bằng chứng tự động | Kết quả |
|---|---|---|
| Duplicate SKU generation | 20 request tạo Product đồng thời; kiểm tra 20 SKU khác nhau, liên tục và không có duplicate group trong DB | Pass |
| Concurrent product creation | `asyncio.gather` qua 20 transaction/API request độc lập | Pass |
| Concurrent stock reduction | 4 request cùng giảm 3 từ quantity 10; chính xác 3 commit và 1 conflict, quantity cuối là 1 | Pass |
| Invalid stock adjustment | Zero delta, thiếu idempotency key, stock không tồn tại và giảm vượt tồn kho | Pass |
| Cross-tenant access | Kết hợp Branch/Product tenant khác, adjustment bằng ID tenant khác và tenant spoofing qua header/query | Pass |
| Failed transaction rollback | Transfer thất bại không đổi source/destination và không thêm movement | Pass |
| Category có Product phụ thuộc | Delete trả `409`, Product và Category không bị xóa ngầm | Pass |
| Pagination và search | Page đầu/cuối không trùng, total chính xác; search theo SKU và Product name đúng | Pass |
| Dataset Inventory lớn | 300 Product và 300 stock rows trong một tenant, đọc theo page 50 và search exact SKU | Pass trong integration benchmark |
| Migration compatibility | Dữ liệu Product tạo ở revision `20261030_0005` còn nguyên sau upgrade `0006` và downgrade về `0005` | Pass |

Hai concurrency test được chạy lặp lại 5 lần, tổng cộng 10 lần thực thi scenario, không có failure hoặc retry ẩn.

## Constraint và transaction boundary

| Invariant | Cơ chế database |
|---|---|
| SKU duy nhất trong tenant | `UNIQUE (organization_id, sku)` |
| SKU counter dương và tăng nguyên tử | Primary key theo organization, `CHECK next_value > 0`, PostgreSQL upsert/returning |
| Product không trỏ sang Category tenant khác | Composite FK `(organization_id, category_id)` |
| Giá không âm | `CHECK price >= 0` |
| Một stock row cho mỗi tenant/Branch/Product | Composite primary key `(organization_id, branch_id, product_id)` |
| Branch và Product của stock cùng tenant | Hai composite foreign keys chứa `organization_id` |
| Low-stock threshold không âm | `CHECK low_stock_threshold >= 0` |
| Idempotency key duy nhất trong tenant | `UNIQUE (organization_id, idempotency_key)` |
| Movement hợp lệ | Check constraints cho type, non-zero quantity, positive transfer và source/destination |
| Ledger không bị sửa/xóa | PostgreSQL trigger chặn `UPDATE` và `DELETE` |
| Tồn kho âm theo policy | Service row lock và PostgreSQL trigger |

Product creation cập nhật SKU counter và insert Product trong cùng transaction. Stock adjustment khóa policy và stock row bằng `FOR UPDATE`. Transfer khóa hai stock rows theo thứ tự UUID ổn định, rồi cập nhật cả hai phía và ledger trong một transaction.

## Phân tích index và query

Các query paths được đối chiếu với predicate và thứ tự sort hiện tại:

- Product tenant/category/status lookup có các index `(organization_id, category_id)`, `(organization_id, status)` và `(organization_id, name)`.
- Stock exact product/report path có primary-key prefix `(organization_id, branch_id, product_id)` và index `(organization_id, product_id)`.
- Movement timeline có `(organization_id, created_at)`; Product filter có `(organization_id, product_id)`.
- Tenant-scoped idempotency lookup dùng unique index `(organization_id, idempotency_key)`.

Không thêm index trong Task 13. Dataset integration 300 rows chưa phải bằng chứng đủ để thêm index chuyên biệt; PostgreSQL có thể chọn sequential scan cho bảng nhỏ hợp lý. Search hiện dùng `ILIKE '%term%'`, nên B-tree index không giải quyết substring search. Khi có workload production-like và `EXPLAIN (ANALYZE, BUFFERS)` cho thấy bottleneck, phương án phù hợp là đánh giá `pg_trgm` GIN/GiST index thay vì thêm B-tree trùng lặp.

## Security review

- Tenant ID không lấy từ body/query/header mà từ active `TenantContext` đã xác thực.
- Repository luôn nhận `organization_id`; composite FK là lớp bảo vệ cuối cho các write path.
- Cross-tenant object ID trả `404`, tránh xác nhận object tồn tại.
- Viewer không có quyền mutation; inventory policy chỉ Owner được đổi.
- Idempotency key scoped theo tenant, không tạo collision giữa hai organization.

Không tìm thấy finding mức Critical/High trong phạm vi Product/Inventory. Audit này không thay thế penetration test hoặc kiểm thử PostgreSQL Row-Level Security; hệ thống hiện dựa trên application-enforced tenant scope và database composite constraints, chưa dùng RLS.

## Giới hạn đã biết

- Pagination dùng offset/limit; page sâu trên hàng triệu rows có thể chậm và có thể thay đổi giữa các request khi dữ liệu được ghi đồng thời. Keyset pagination chưa triển khai.
- Substring search chưa có `pg_trgm`; hiệu năng production-scale chưa được benchmark.
- Integration benchmark là 300 stock rows trong một tenant, không phải load/stress test hàng triệu rows.
- Concurrency test chạy trong một process qua nhiều database connection; chưa mô phỏng nhiều API replica hoặc network fault.
- SKU counter tuần tự có thể trở thành hot row nếu một tenant tạo Product với throughput rất cao.
- PostgreSQL RLS chưa được bật; tenant isolation phụ thuộc vào service/repository scope và composite constraints.

Các giới hạn trên không làm sai consistency trong phạm vi hiện tại, nhưng cần được đo lại bằng dữ liệu và topology gần production trước khi quyết định index hoặc pagination strategy.
