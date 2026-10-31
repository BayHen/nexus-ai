# Enterprise Dashboard

## Phạm vi Task 23

Dashboard Next.js cung cấp các route: đăng nhập, đăng ký, chọn tổ chức, tổng quan, sản phẩm, tồn kho, đơn hàng, thanh toán, analytics, đội ngũ và cài đặt tài khoản. Giao diện responsive sử dụng App Router, React Client Components cho tương tác và BFF Route Handler cho kết nối FastAPI.

## Authentication boundary

Browser gọi `/api/backend/*` cùng origin. Route Handler chuyển tiếp request tới `API_BASE_URL`, giữ access/refresh token trong cookie `HttpOnly`, `SameSite` và `Secure` ở production. Token không được trả lại cho Client Component sau login/register. BFF gắn Bearer token khi gọi FastAPI; backend vẫn là nơi thực thi authentication, active tenant và RBAC.

Client-side role-aware navigation chỉ cải thiện trải nghiệm, không phải authorization. Role được lấy từ organization mà backend trả về và được lưu trong `sessionStorage` sau khi activate. Mọi data request vẫn phải vượt qua backend permission check.

## Data integration

| Màn hình | Backend API | Trạng thái |
|---|---|---|
| Login/Register | `/auth/login`, `/auth/register` | Tích hợp |
| Chọn tổ chức | `/organizations`, `/organizations/{id}/activate` | Tích hợp |
| Tổng quan/Analytics | `/analytics/summary`, `/analytics/revenue` | Tích hợp |
| Sản phẩm | `/products` | Search, status filter, pagination |
| Tồn kho | `/inventory/stocks` | Search, low-stock filter, pagination |
| Đơn hàng | `/orders` | Status filter, pagination |
| Đội ngũ | `/members` | Search, role filter, pagination |
| Payment history | Chưa có collection endpoint | Hiển thị unavailable rõ ràng |
| Account settings | Chưa có update endpoint | Hiển thị unavailable rõ ràng |

Không có mock fallback. Lỗi network/API hiển thị error state; collection rỗng hiển thị empty state; request đang chạy hiển thị loading state.

## UI và accessibility

- Navigation drawer responsive, semantic landmarks và accessible names.
- Form có label, browser autocomplete, client validation và `role=alert` cho lỗi.
- Bảng có header semantic, horizontal scroll trên màn hình nhỏ và controls pagination có disabled state.
- Focus ring toàn cục, màu trạng thái không phải tín hiệu duy nhất vì luôn có text label.
- Dashboard không hiển thị production metric giả; analytics lấy trực tiếp từ backend.

## Chạy và kiểm tra

```powershell
Set-Location frontend
npm.cmd ci
$env:API_BASE_URL = "http://127.0.0.1:8000"
npm.cmd run dev
```

Kiểm tra chất lượng:

```powershell
npm.cmd run typecheck
npm.cmd run lint
npm.cmd test
npm.cmd run build
```

## Giới hạn

- Access token refresh tự động trong BFF chưa được triển khai; user phải đăng nhập lại khi access token hết hạn.
- Payment collection API và account update API cần backend Task riêng trước khi bật UI tương ứng.
- Create/edit workflows chi tiết cho Product, Inventory, Order và Team chưa nằm trong Task 23; dashboard hiện ưu tiên read/navigation foundation.
- Playwright browser E2E với backend thật vẫn **PLANNED**.
