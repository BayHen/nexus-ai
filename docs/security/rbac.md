# Role-Based Access Control theo tenant

## Mô hình authorization

RBAC được áp dụng sau hai bước xác thực bắt buộc:

1. JWT access token xác định user.
2. Server-side active organization context xác định tenant và active membership.

Client không gửi role hoặc tenant ID cho business API. `TenantContext` chứa `organization_id`, `user_id` và role đọc trực tiếp từ membership trong database. Service kiểm tra permission trước khi đọc hoặc thay đổi resource được bảo vệ.

## Permissions matrix

| Permission | Owner | Admin | Manager | Staff | Viewer |
|---|:---:|:---:|:---:|:---:|:---:|
| `branch:read` | Có | Có | Có | Có | Có |
| `branch:create` | Có | Có | Có | Không | Không |
| `branch:update` | Có | Có | Có | Có | Không |
| `member:read` | Có | Có | Có | Không | Không |
| `member:invite` | Có | Có | Không | Không | Không |
| `member:role:manage` | Có | Có | Không | Không | Không |
| `member:remove` | Có | Có | Không | Không | Không |
| `audit:read` | Có | Có | Có | Không | Không |
| `catalog:read` | Có | Có | Có | Có | Có |
| `catalog:write` | Có | Có | Có | Không | Không |
| `catalog:delete` | Có | Có | Không | Không | Không |
| `inventory:read` | Có | Có | Có | Có | Có |
| `inventory:manage` | Có | Có | Có | Không | Không |
| `inventory:adjust` | Có | Có | Có | Có | Không |
| `inventory:policy` | Có | Không | Không | Không | Không |
| `order:read` | Có | Có | Có | Có | Có |
| `order:write` | Có | Có | Có | Có | Không |
| `order:confirm` | Có | Có | Có | Có | Không |
| `order:cancel` | Có | Có | Có | Không | Không |

Permission matrix là allowlist trong `ROLE_PERMISSIONS`. Role không có permission tương ứng luôn nhận `403 tenant_access_denied`.

## Chính sách chống privilege escalation

Permission `member:role:manage` chưa đủ để tùy ý gán role. Target-policy bổ sung quy định:

- Owner có thể gán mọi role.
- Admin không thể tạo, promote, demote hoặc remove Owner/Admin.
- Admin không thể tự promote thành Owner.
- Manager, Staff và Viewer không thể thay đổi role hoặc remove member.
- Chỉ Owner có thể tạo Owner khác bằng cách promote một membership đã tồn tại.
- Lookup member luôn kèm active `organization_id`; user ID của tenant khác trả `404`.

## Bảo vệ owner cuối cùng

Trước khi demote hoặc remove một active Owner, service khóa toàn bộ active owner rows của organization bằng `SELECT ... FOR UPDATE`. Nếu chỉ còn một Owner, transaction dừng với `409 last_owner_protected`. Cơ chế khóa ngăn hai request đồng thời cùng vượt qua phép kiểm tra cuối-owner.

## API quản lý role và member

| Method và path | Permission | Mô tả |
|---|---|---|
| `GET /api/v1/members` | `member:read` | Danh sách member theo active tenant; hỗ trợ `query`, `role`, `status`, pagination |
| `PATCH /api/v1/members/{user_id}/role` | `member:role:manage` | Thay đổi role sau target-policy và last-owner check |
| `DELETE /api/v1/members/{user_id}` | `member:remove` | Xóa membership sau target-policy và last-owner check |
| `GET /api/v1/audit-events` | `audit:read` | Đọc audit event theo active tenant; hỗ trợ `event_type`, pagination |

Không có API tạo, sửa hoặc xóa audit event.

## Audit event schema

Audit event được ghi cùng transaction với thay đổi nhạy cảm:

| Field | Kiểu | Ý nghĩa |
|---|---|---|
| `id` | UUID | Định danh event |
| `organization_id` | UUID | Tenant sở hữu event; luôn dùng làm query scope |
| `actor_user_id` | UUID nullable | User thực hiện; giữ event khi user bị xóa |
| `event_type` | string | Tên event ổn định |
| `target_type` | string | Loại đối tượng bị tác động |
| `target_id` | UUID nullable | Định danh đối tượng hoặc user đích |
| `details` | JSONB | Metadata tối thiểu như role trước/sau; không chứa token hoặc secret |
| `created_at` | timestamptz | Thời điểm database ghi event |

Event type hiện có:

- `organization.created`
- `membership.invited`
- `membership.accepted`
- `membership.role_changed`
- `membership.removed`

PostgreSQL trigger `organization_audit_events_immutable` từ chối mọi `UPDATE` hoặc `DELETE`, kể cả khi code application vô tình gọi trực tiếp. Việc retention/archive audit log là **PLANNED** và phải dùng quy trình vận hành riêng, không mở write API cho user.

## Migration role cũ

Migration `0004` đổi role `member` từ Task 09 thành `viewer` để không vô tình tăng quyền ghi. Downgrade ánh xạ `manager`, `staff`, `viewer` về `member` trước khi khôi phục constraint cũ.

## Bằng chứng kiểm thử

Automated tests bao phủ permission allow/deny, Admin escalation attempts, Manager/Staff/Viewer behavior, last-owner protection, cross-tenant member IDs, audit tenant scope, API write rejection và PostgreSQL trigger immutability.
