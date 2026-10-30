# Alembic migrations

Thư mục này chứa migration có thứ tự của backend. Revision đầu tiên là baseline rỗng vì Task 06 chưa được phép tạo business schema.

Từ thư mục `backend`, dùng `python -m alembic upgrade head` để nâng cấp và `python -m alembic downgrade -1` để rollback một revision. URL database được lấy từ `DATABASE_URL` hoặc file `.env` tại repository root; không ghi credential vào `alembic.ini`.
