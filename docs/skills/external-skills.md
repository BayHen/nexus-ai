# Tích hợp External Skills

## Phạm vi và nguyên tắc tin cậy

External Skill là mã và chỉ dẫn có thể ảnh hưởng đến cách Codex lập kế hoạch, gọi tool và chạy command. Vì vậy mỗi skill phải được xem là untrusted cho đến khi đã kiểm tra source, revision, license, toàn bộ script, dependency và quyền cần thiết.

Task này chỉ cài một skill bổ sung capability chưa có. Các skill software engineering, testing, documentation và security tổng quát không được cài vì trùng với project skill nội bộ.

## Môi trường đã kiểm tra

- Codex executable: `codex-cli 0.165.0-alpha.1.2`.
- Project skill location: `.agents/skills/<skill-name>/SKILL.md`.
- User skill location được quan sát: `%USERPROFILE%/.codex/skills/`.
- Project location được chọn để skill đi cùng repository và có thể review bằng Git.

Tài liệu OpenAI xác nhận repo-local skills tại `.agents/skills/` và mô hình discovery qua metadata `name`/`description`. Việc file tồn tại và vượt qua validator chứng minh cấu trúc discoverable; không chứng minh skill đã được load trong một Codex turn cụ thể.

## Shortlist và quyết định

| Ứng viên | Nguồn | Quyết định | Lý do |
|---|---|---|---|
| `playwright` | `openai/skills` curated | Cài đặt | Bổ sung browser CLI validation; source chính thức, revision pin, Apache-2.0. |
| `playwright-interactive` | `openai/skills` curated | Loại | Yêu cầu `danger-full-access`, không phù hợp nguyên tắc quyền tối thiểu. |
| Skill security/testing/docs tổng quát | Nhiều nguồn | Không cài | Trùng với `security-review`, `test-engineering` và `documentation` nội bộ. |
| Các listing không có repository/revision cụ thể trên agentskills.io | agentskills.io | BLOCKED | Không đủ artifact cụ thể để audit và pin tái lập. |

## Skill đã cài

### playwright

- Source: [openai/skills – playwright](https://github.com/openai/skills/tree/49f948faa9258a0c61caceaf225e179651397431/skills/.curated/playwright).
- Revision: `49f948faa9258a0c61caceaf225e179651397431`.
- License: Apache-2.0; giữ nguyên `LICENSE.txt` và `NOTICE.txt`.
- Nội dung đã review: `SKILL.md`, `agents/openai.yaml`, hai reference, hai asset và `scripts/playwright_cli.sh`.
- Script: Bash wrapper kiểm tra `npx`, sau đó gọi `npx --yes --package @playwright/cli playwright-cli`.
- Dependency runtime: Node.js/npm và package `@playwright/cli` chỉ khi wrapper được chạy.
- Permission: browser automation và network theo URL được kiểm tra; không yêu cầu quyền administrator trong bản thân skill.

Task tích hợp **không chạy wrapper**, không tải `@playwright/cli`, không cài browser binary và không thực hiện browser session. Dependency động `@playwright/cli` chưa được pin trong upstream wrapper; trước khi sử dụng thực tế, Task triển khai frontend phải quyết định version dependency trong project và xin phép nếu cần download.

## Cài đặt tái lập

Lệnh dưới đây dùng bundled `skill-installer` của Codex và full commit SHA. Điều chỉnh đường dẫn installer theo Codex installation hiện tại nếu cần:

```text
python <codex-skill-installer>/scripts/install-skill-from-github.py \
  --repo openai/skills \
  --path skills/.curated/playwright \
  --ref 49f948faa9258a0c61caceaf225e179651397431 \
  --dest <repository>/.agents/skills \
  --method download
```

Installer phải dừng nếu `.agents/skills/playwright` đã tồn tại. Không dùng `main` thay cho SHA đã pin.

Sau khi cài:

```text
python scripts/validate_skills.py
python -m unittest discover -s tests/skills -p "test_*.py"
```

Validator phải liệt kê `playwright` trong tập skill được phát hiện. Khởi động một Codex turn/session mới sau khi cài để runtime làm mới skill catalog; không tuyên bố session hiện tại đã hot-load skill vừa copy.

## Rollback

Nếu thay đổi chưa commit, xóa đúng thư mục `.agents/skills/playwright/`, xóa dòng `playwright` khỏi `docs/skills/registry.md`, gỡ phần tích hợp tương ứng khỏi README và chạy lại validator/test. Không xóa toàn bộ `.agents/skills/`.

Nếu thay đổi đã commit, dùng một commit mới để revert các file của integration nhằm giữ lịch sử audit. Việc rollback skill không tự động gỡ package hoặc browser binary nếu chúng đã được cài riêng ở một Task khác.

## Nâng cấp

Không cập nhật tự động. Khi nâng cấp, audit diff giữa revision hiện tại và revision mới, kiểm tra lại license/script/dependency/permission, cập nhật SHA trong registry và tài liệu, rồi chạy validator/test. Không chạy script mới trước khi review hoàn tất.
