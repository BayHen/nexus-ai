# Hướng dẫn sử dụng Agent Skills

## Cơ chế phát hiện

Project skills nằm tại `.agents/skills/<skill-name>/SKILL.md`. Codex đọc metadata `name` và `description` để xác định skill có liên quan. Khi một skill được chọn, Codex phải đọc toàn bộ `SKILL.md` trước khi hành động và chỉ đọc reference được liên kết khi ngữ cảnh tương ứng cần đến.

Validator của dự án chỉ chứng minh cấu trúc, metadata, liên kết và registry nhất quán. Validator không thể chứng minh giao diện Codex đã load skill trong một lượt cụ thể, cũng không tự “kích hoạt” skill.

## Gọi tường minh

Người dùng có thể yêu cầu trực tiếp bằng tên, ưu tiên cú pháp `$skill-name`:

```text
Use $api-design to design the customer search API.
```

Hoặc nêu tên skill bằng văn bản rõ ràng:

```text
Use the security-review skill to inspect tenant isolation.
```

Khi được gọi tường minh, Codex phải nêu skill đang dùng và tuân theo workflow của skill trong phạm vi yêu cầu.

## Chọn tự động

Automatic selection được giữ ở chính sách mặc định vì các skill không đặt `allow_implicit_invocation: false`. Codex có thể chọn skill khi mô tả của nó khớp rõ với yêu cầu, ví dụ một thay đổi Alembic phù hợp với `database-design`.

Việc “có thể chọn tự động” không bảo đảm một skill sẽ luôn được chọn. Quyết định còn phụ thuộc yêu cầu, context và các chỉ dẫn có mức ưu tiên cao hơn. Codex phải thông báo khi skill tự chọn ảnh hưởng đến công việc.

## Kết hợp nhiều skill

Chỉ dùng tập skill nhỏ nhất bao phủ yêu cầu và nêu thứ tự. Ví dụ:

```text
Use $feature-delivery, then $python-backend and $test-engineering, to add a health endpoint.
```

`feature-delivery` điều phối kết quả tổng thể; skill chuyên môn cung cấp quy tắc cho phần việc tương ứng. Không load toàn bộ registry cho mọi Task.

## Kiểm tra hệ thống skill

Từ thư mục gốc repository:

```text
python scripts/validate_skills.py
python -m unittest discover -s tests/skills -p "test_*.py"
```

Validator kiểm tra:

- Cấu trúc thư mục skill và `SKILL.md`.
- YAML frontmatter bắt buộc `name` và `description`.
- Tên trùng lặp và sự khớp giữa tên với thư mục.
- Markdown reference cục bộ được liên kết từ `SKILL.md`.
- Sự nhất quán giữa filesystem và `docs/skills/registry.md`.

## Báo cáo

Sử dụng [mẫu báo cáo Task](task-report-template.md) khi bàn giao một Task đáng kể. Chỉ ghi skill là “đã load” khi `SKILL.md` của skill thực sự được đọc trong lượt làm việc; skill chỉ vượt qua validator phải được ghi là “đã xác thực”.
