# CI Validation cho Agent Skills

## Mục tiêu

Workflow `Skills validation` bảo vệ cấu trúc project skills và registry trước khi thay đổi được merge. Workflow không cài dependency của external skill, không chạy script nằm trong skill và chỉ cần Python standard library.

File workflow: `.github/workflows/skills-validation.yml`.

## Khi nào CI chạy

Workflow chạy trong các trường hợp:

- Pull request thay đổi skill, validator, test, tài liệu skill, `AGENTS.md`, README hoặc chính workflow.
- Push vào nhánh `main` có thay đổi các đường dẫn trên.
- Người duy trì chạy thủ công bằng `workflow_dispatch`.

Job dùng quyền `contents: read`, timeout 5 phút và concurrency cancellation theo Git ref. Không có quyền ghi repository, package, deployment hoặc cloud resource.

## Các bước validation

CI thực hiện theo thứ tự:

```text
python -m py_compile scripts/validate_skills.py tests/skills/test_validate_skills.py
python -m unittest discover -s tests/skills -p "test_*.py" -v
python scripts/validate_skills.py
```

Test suite bao gồm repository hợp lệ và các fixture lỗi có chủ đích:

- Thiếu `SKILL.md`.
- Thiếu metadata `name` hoặc `description`.
- Tên metadata không hợp lệ.
- Trùng tên skill.
- Reference không tồn tại.
- Registry thiếu, thừa hoặc trùng dòng.

Validator trả exit code khác 0 nếu có lỗi, vì vậy step và job CI thất bại. Repository hợp lệ trả exit code 0 và in danh sách skill đã phát hiện.

## Validation có thể chứng minh gì

- `.agents/skills/` tồn tại và mỗi thư mục skill có `SKILL.md`.
- YAML frontmatter dạng được project hỗ trợ có `name` và `description`.
- Tên dùng lowercase/kebab-case và khớp tên thư mục.
- Không có duplicate skill name.
- Markdown reference cục bộ từ `SKILL.md` tồn tại và không thoát khỏi thư mục skill.
- Registry và filesystem có cùng tập tên, không có dòng registry trùng.
- Validator chạy được trên Python được cấu hình trong CI.

## Validation không thể chứng minh gì

- Codex đã chọn hoặc load skill trong một Task cụ thể.
- Nội dung skill tạo ra quyết định đúng, an toàn hoặc có chất lượng cao.
- Script trong skill an toàn khi chạy hoặc dependency runtime đáng tin cậy.
- External source, license và pinned revision vẫn hợp lệ nếu registry ghi sai nhưng vẫn đúng định dạng.
- Tool, MCP server, credential, browser hoặc dịch vụ ngoài đang khả dụng.
- Workflow đã pass trên GitHub trước khi commit được push và GitHub Actions thực sự chạy.

Vì vậy code review và trust review vẫn bắt buộc. CI không được dùng làm bằng chứng thay thế cho behavioral evaluation hoặc security review.

## Kiểm tra thủ công việc Codex sử dụng Skill

1. Bắt đầu Codex session mới để catalog được làm mới sau khi thêm hoặc đổi skill.
2. Yêu cầu tường minh, ví dụ: `Use $api-design to review this endpoint contract.`
3. Kiểm tra Codex thông báo skill được dùng trước khi thực hiện workflow.
4. Đối chiếu hành vi với responsibilities, workflow, acceptance criteria và verification trong `SKILL.md`.
5. Yêu cầu báo cáo cuối liệt kê riêng skill **đã load** và skill chỉ **đã xác thực**.
6. Với automatic invocation, dùng một prompt khớp rõ description nhưng không nêu tên skill; ghi nhận kết quả như behavioral observation, không coi đó là bảo đảm cho mọi session.

Không dùng câu “skill đã kích hoạt” chỉ vì validator liệt kê tên. Validator chứng minh discoverable structure, không quan sát runtime context của Codex.

## Chạy cục bộ

Từ repository root:

```text
python -m unittest discover -s tests/skills -p "test_*.py" -v
python scripts/validate_skills.py
```

Kết quả cục bộ cần được báo cáo riêng với kết quả GitHub Actions; không tuyên bố CI trên GitHub đã pass nếu chỉ chạy lệnh local.
