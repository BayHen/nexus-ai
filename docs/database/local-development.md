# PostgreSQL và database workflow cục bộ

## Tổng quan

Backend dùng PostgreSQL, SQLAlchemy 2 async, driver asyncpg và Alembic. Psycopg sync chỉ là dev dependency để integration test tạo/drop database tạm. PostgreSQL chạy bằng Docker Compose với named volume `nexus_postgres_data`. API thực hiện connection check khi startup: nếu database không khả dụng, startup thất bại thay vì phục vụ traffic trong trạng thái sai. Sau startup, `/health/ready` tiếp tục chạy `SELECT 1` và trả `503` nếu kết nối bị mất.

Không có business table trong Task 06. Revision `20261030_0001` là migration baseline rỗng để thiết lập migration chain mà không tạo schema giả.

## Cấu hình môi trường

Tạo file `.env` từ `.env.example` và thay toàn bộ giá trị `replace-with-*` bằng secret cục bộ:

```powershell
Copy-Item .env.example .env
```

Các biến database chính:

- `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`: dùng khi container PostgreSQL được khởi tạo lần đầu.
- `POSTGRES_PORT`: port chỉ bind vào `127.0.0.1`.
- `DATABASE_URL`: URL async SQLAlchemy cho API và Alembic.
- `NEXUS_DATABASE_CONNECT_TIMEOUT_SECONDS`: giới hạn thời gian connection check.

Không commit `.env`, backup chứa dữ liệu, hoặc credential thật. Nếu password chứa ký tự đặc biệt, URL-encode password trong `DATABASE_URL`.

## Khởi động và dừng PostgreSQL

Từ repository root:

```powershell
docker compose --env-file .env -f infrastructure/docker/compose.yml up -d postgres
docker compose --env-file .env -f infrastructure/docker/compose.yml ps
```

Container có health check bằng `pg_isready`. Dừng container nhưng giữ dữ liệu:

```powershell
docker compose --env-file .env -f infrastructure/docker/compose.yml down
```

## Migration

Sau khi PostgreSQL healthy, từ repository root:

```powershell
backend/.venv/Scripts/python.exe -m alembic -c backend/alembic.ini upgrade head
backend/.venv/Scripts/python.exe -m alembic -c backend/alembic.ini current
```

Rollback một revision khi revision hỗ trợ downgrade:

```powershell
backend/.venv/Scripts/python.exe -m alembic -c backend/alembic.ini downgrade -1
```

Luôn review migration và backup trước rollback trên dữ liệu quan trọng. Một downgrade kỹ thuật thành công không chứng minh data loss là chấp nhận được.

## Transaction strategy

`DatabaseManager` sở hữu async engine và `async_sessionmaker`. Mỗi application command tương lai phải mở một transaction scope:

```python
async with database_manager.transaction() as session:
    # Call repositories with this session.
    ...
```

Scope commit khi block hoàn tất, rollback khi có exception và luôn đóng session. Không giữ transaction mở trong khi gọi network service; side effect sau commit sẽ dùng outbox ở Task phù hợp.

## Backup

Tạo thư mục `backups` ngoài Git hoặc ở vị trí được bảo vệ. Ví dụ tạo logical backup tùy chỉnh:

```powershell
New-Item -ItemType Directory -Force backups
docker compose --env-file .env -f infrastructure/docker/compose.yml exec -T postgres sh -c 'pg_dump --format=custom --no-owner -U "$POSTGRES_USER" "$POSTGRES_DB"' > backups/nexus_ai.dump
```

Kiểm tra file có kích thước lớn hơn 0 và bảo vệ file vì backup có thể chứa dữ liệu nhạy cảm. Thử restore định kỳ vào database tạm; backup chưa được thử restore chưa phải bằng chứng khôi phục được.

Restore vào database rỗng đã được chọn rõ ràng:

```powershell
Get-Content -AsByteStream backups/nexus_ai.dump | docker compose --env-file .env -f infrastructure/docker/compose.yml exec -T postgres sh -c 'pg_restore --clean --if-exists --no-owner -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
```

`--clean` có thể xóa object hiện hữu. Không chạy với database cần giữ dữ liệu nếu chưa có backup và xác nhận đúng target.

## Reset dữ liệu cục bộ

Reset volume là thao tác phá hủy, xóa toàn bộ database trong `nexus_postgres_data` và không thể hoàn tác nếu không có backup:

```powershell
docker compose --env-file .env -f infrastructure/docker/compose.yml down --volumes
docker compose --env-file .env -f infrastructure/docker/compose.yml up -d postgres
backend/.venv/Scripts/python.exe -m alembic -c backend/alembic.ini upgrade head
```

Trước khi chạy, dùng `docker volume inspect nexus_postgres_data` để xác nhận đúng volume và tạo backup nếu dữ liệu có giá trị.

## Integration tests

Migration tests tạo database tạm có tên ngẫu nhiên rồi luôn drop database đó. Cung cấp admin URL cục bộ chỉ cho lệnh test:

```powershell
$env:NEXUS_TEST_DATABASE_ADMIN_URL='postgresql://nexus_ai:<local-password>@127.0.0.1:5432/postgres'
Set-Location backend
.venv/Scripts/python.exe -m pytest -m integration -v
```

Không dùng production credential hoặc server dùng chung cho fixture này. Nếu biến không tồn tại, integration tests được skip thay vì kết nối nhầm database.
