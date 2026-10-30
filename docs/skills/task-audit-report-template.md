# Mẫu báo cáo audit Task

## 1. Thông tin Task

- **Task:** `<mã và tên>`
- **Ngày audit:** `<YYYY-MM-DD>`
- **Người/agent thực hiện:** `<tên>`
- **Commit hoặc revision:** `<SHA hoặc NOT COMMITTED>`
- **Phạm vi:** `<đường dẫn, component, environment>`

## 2. Yêu cầu và bằng chứng

| Yêu cầu | Trạng thái | Bằng chứng |
|---|---|---|
| `<acceptance criterion>` | PASS/FAIL/BLOCKED/NOT RUN | `<file, command, log hoặc giải thích>` |

## 3. Skills

| Skill | Trạng thái | Ảnh hưởng đến công việc |
|---|---|---|
| `<skill-name>` | LOADED/VALIDATED/CONSIDERED | `<quyết định hoặc workflow đã áp dụng>` |

- `LOADED`: `SKILL.md` đã được đọc và áp dụng trong Task.
- `VALIDATED`: validator chỉ kiểm tra cấu trúc/metadata.
- `CONSIDERED`: đã cân nhắc nhưng không load.

Không ghi `LOADED` chỉ vì skill có trong registry.

## 4. Files và thay đổi trạng thái

| File/tài nguyên | Thay đổi | Khả năng rollback |
|---|---|---|
| `<path>` | CREATED/MODIFIED/DELETED | `<cách rollback>` |

## 5. Verification đã chạy

| Lệnh hoặc kiểm tra | Kết quả | Môi trường | Ghi chú |
|---|---|---|---|
| `<command>` | PASS/FAIL | LOCAL/CI | `<số test, giới hạn, artifact>` |

## 6. Security và quyền

- **Secret được sử dụng:** `<không/có, không ghi giá trị>`
- **Quyền external:** `<read/write/deploy/không có>`
- **Dependency hoặc script bên thứ ba:** `<đã review/chưa chạy/không có>`
- **Tenant và dữ liệu nhạy cảm:** `<ảnh hưởng>`

## 7. Findings và rủi ro còn lại

| Mức độ | Finding | Hành động tiếp theo | Owner |
|---|---|---|---|
| LOW/MEDIUM/HIGH/BLOCKED | `<mô tả>` | `<hành động>` | `<owner>` |

## 8. Kết luận

- **Kết quả audit:** PASS/FAIL/BLOCKED
- **Sẵn sàng cho bước tiếp theo:** YES/NO
- **Điều kiện:** `<nếu có>`

Chỉ kết luận GitHub CI đã pass khi có run thực tế; kết quả local không thay thế bằng chứng đó.
