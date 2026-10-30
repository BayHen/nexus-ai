# Kiến trúc multi-tenant organization

## Phạm vi Task 09

Task 09 triển khai tenant boundary đầu tiên với bốn thành phần persistence:

- `organizations`: tenant gốc.
- `organization_memberships`: quan hệ nhiều-nhiều giữa user và organization, kèm role và trạng thái invitation.
- `organization_active_contexts`: active organization được chọn ở server cho từng user.
- `organization_branches`: business resource đầu tiên bắt buộc tenant scope.

Một user có thể là thành viên active của nhiều organization nhưng chỉ có một active organization tại một thời điểm.

## Invariant ở database

- Membership dùng composite primary key `(organization_id, user_id)`, ngăn membership trùng.
- `role` chỉ nhận `owner`, `admin`, `member`; `status` chỉ nhận `pending`, `active` bằng `CHECK` constraint.
- Active context có composite foreign key `(organization_id, user_id)` tới membership. Database không thể lưu active context cho một cặp không có membership.
- Branch có unique constraint `(organization_id, slug)` và index `(organization_id, name)` phục vụ tenant-scoped lookup/filter.
- Foreign key dùng `CASCADE`, `SET NULL` hoặc `RESTRICT` theo ownership; migration `0003` có downgrade đầy đủ.

## Tenant context và chống bypass

Business API không nhận `organization_id` từ request body, query parameter hoặc `X-Organization-ID`. Dependency `get_tenant_context` lấy user từ access token, sau đó resolve active organization và active membership từ database.

Client chỉ truyền organization ID ở hai identity workflow:

- `POST /organizations/{organization_id}/activate`: chỉ thành công nếu user có membership `active` trong organization đó.
- `POST /organizations/{organization_id}/invitations/accept`: chỉ thành công nếu chính user có membership `pending` tương ứng.

Mọi branch query luôn có đồng thời `Branch.organization_id == context.organization_id` và `Branch.id == branch_id`. Vì vậy branch ID hợp lệ của tenant khác vẫn trả `404`; API không xác nhận tài nguyên ngoài tenant có tồn tại.

## Role trong Task 09

| Hành động | owner | admin | member |
|---|---:|---:|---:|
| Đọc branch trong active organization | Có | Có | Có |
| Tạo/cập nhật branch | Có | Có | Không |
| Mời member/admin | Có | Có | Không |
| Chọn organization có membership active | Có | Có | Có |

RBAC permission catalog chi tiết hơn vẫn **PLANNED**. Role checks hiện chỉ bảo vệ các workflow thuộc Task 09.

## API

| Method và path | Mô tả |
|---|---|
| `POST /api/v1/organizations` | Tạo organization, owner membership và chọn làm active |
| `GET /api/v1/organizations` | Liệt kê organization active membership của user |
| `POST /api/v1/organizations/{id}/activate` | Chọn active organization sau membership check |
| `POST /api/v1/organizations/current/invitations` | Owner/admin mời user đã đăng ký |
| `POST /api/v1/organizations/{id}/invitations/accept` | User được mời accept membership |
| `POST /api/v1/branches` | Tạo branch trong active organization |
| `GET /api/v1/branches` | Liệt kê branch trong active organization |
| `GET /api/v1/branches/{id}` | Đọc branch với tenant-scoped lookup |
| `PATCH /api/v1/branches/{id}` | Cập nhật branch với tenant-scoped lookup và role check |

Các list endpoint dùng `page` từ 1, `page_size` từ 1 đến 100. Organization hỗ trợ `query` theo tên. Branch hỗ trợ `query` theo tên và `is_active`.

Invitation cho email chưa đăng ký và email đã có membership đều trả lỗi generic `invitation_unavailable`. Gửi invitation qua email và invitation token riêng là **PLANNED**; Task 09 chỉ tạo pending membership cho user đã đăng ký.

## Kiểm thử cô lập tenant

Integration tests tạo database PostgreSQL riêng và kiểm tra:

- Token tenant A không đọc hoặc patch được branch ID của tenant B.
- User tenant A không activate được organization của tenant B.
- Header và query parameter giả mạo organization ID không đổi tenant context.
- Pending invitation không cấp quyền trước khi accept.
- Member của nhiều organization chỉ thấy branch của active organization.
- Role `member` không thể tạo branch.
- Pagination/filtering không làm rò dữ liệu tenant khác.
