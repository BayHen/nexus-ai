# Hệ thống xác thực

## Phạm vi đã triển khai

Task 08 cung cấp các API sau dưới `/api/v1/auth`:

| API | Mục đích |
|---|---|
| `POST /register` | Tạo user và phát cặp access/refresh token |
| `POST /login` | Xác thực email/password và phát session mới |
| `POST /refresh` | Rotation refresh token và phát cặp token mới |
| `POST /logout` | Thu hồi refresh session |
| `GET /me` | Kiểm tra access token và trả identity hiện tại |
| `POST /password-reset/request` | Tạo password-reset grant với response chống dò tài khoản |
| `POST /password-reset/confirm` | Đổi password bằng grant single-use và thu hồi mọi refresh session |

User identity hiện là global. Tenant membership và RBAC không thuộc Task 08; chúng phải được thêm ở Task sau mà không đưa `tenant_id` giả vào JWT hiện tại.

## Quyết định bảo mật

- Password được hash bằng Argon2id với salt ngẫu nhiên; database không lưu plaintext password.
- Access token là JWT ký bằng HS256, có `iss`, `aud`, `sub`, `jti`, `iat`, `exp` và `type=access`. Thời hạn mặc định là 15 phút.
- Refresh token là opaque token gồm session ID và secret 256-bit. Database chỉ lưu SHA-256 digest của secret.
- Rotation khóa row bằng `SELECT ... FOR UPDATE`. Token cũ bị revoke ngay khi token mới được phát. Phát hiện replay sẽ revoke toàn bộ refresh session đang hoạt động của user.
- Logout thu hồi refresh session. Access token đã phát vẫn hợp lệ đến khi hết hạn tối đa 15 phút; không duy trì blacklist access token.
- Password-reset token là opaque, single-use, có expiry và chỉ lưu digest. Reset thành công thu hồi mọi refresh session của user.
- Response của login dùng cùng một lỗi cho email không tồn tại, password sai và account không hoạt động. Password-reset request luôn trả cùng status/body.
- Audit event chỉ chứa loại event và định danh nội bộ cần thiết; password, JWT, refresh token và reset token không được ghi log.

## Cấu hình môi trường

Các biến quan trọng nằm trong `.env.example`:

- `JWT_SECRET_KEY`: bắt buộc, tối thiểu 32 ký tự và không được giữ placeholder ngoài test.
- `JWT_ALGORITHM`: cố định `HS256` để tránh algorithm confusion.
- `NEXUS_JWT_ISSUER`, `NEXUS_JWT_AUDIENCE`: ràng buộc issuer và audience.
- `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS`.
- `NEXUS_PASSWORD_RESET_EXPIRE_MINUTES`.
- `NEXUS_AUTH_RATE_LIMIT_ATTEMPTS`, `NEXUS_AUTH_RATE_LIMIT_WINDOW_SECONDS`.

Tạo secret cục bộ bằng công cụ sinh số ngẫu nhiên an toàn của hệ điều hành. Không commit `.env`, secret thật hoặc token từ response.

## Rate limiting

Login và password-reset request được giới hạn theo operation, client IP và normalized email. Request reset vượt giới hạn vẫn nhận cùng response generic nhưng không tạo thêm grant. Implementation hiện tại là bộ nhớ trong từng API process, phù hợp local development và một process. Khi triển khai nhiều replica, phải thay adapter này bằng Redis để có giới hạn phân tán nhất quán; đây là **PLANNED** và không được xem implementation hiện tại là production-distributed rate limiting.

## Password reset delivery

API request đã tạo grant an toàn nhưng không trả token và không ghi token vào log. Email delivery adapter chưa được triển khai, vì vậy việc gửi link reset ra ngoài hệ thống là **PLANNED**. Test integration tạo grant trực tiếp ở persistence boundary để kiểm tra confirm, single-use, đổi password và session revocation mà không làm yếu public API.

## Kiểm thử

Từ `backend/`:

```powershell
.venv/Scripts/python.exe -m ruff format --check .
.venv/Scripts/python.exe -m ruff check .
.venv/Scripts/python.exe -m mypy .
.venv/Scripts/python.exe -m pytest -q -m "not integration"
```

Integration test cần PostgreSQL và quyền tạo database tạm:

```powershell
$env:NEXUS_TEST_DATABASE_ADMIN_URL = "postgresql://<user>:<password>@127.0.0.1:5432/postgres"
.venv/Scripts/python.exe -m pytest -q -m integration
```

Fixture tạo database riêng cho từng test và xóa sau khi hoàn tất. Không dùng database ứng dụng hoặc production.
