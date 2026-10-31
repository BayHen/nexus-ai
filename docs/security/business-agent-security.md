# Mô hình bảo mật AI Agent phân tích kinh doanh

## Boundary tin cậy

- Access token và active organization phía server là nguồn duy nhất của user/tenant context.
- Permission `ai-assistant:use` chỉ cho phép vào Agent; từng tool tiếp tục kiểm tra permission nghiệp vụ tương ứng.
- Tool dùng truy vấn dựng sẵn hoặc application service hiện hữu; model và client không cung cấp SQL.
- RAG chỉ truy hồi document đã qua tenant filter và document-level permission.
- Retrieved content là dữ liệu không tin cậy, không phải system instruction hay tool instruction.

## Kiểm soát chính

- Registry tool là allowlist cố định, input/output có kiểu và một run chỉ gọi tối đa một tool.
- Không có write tool. Ý định ghi bị dừng trước bước execute; mọi write workflow tương lai phải có authorization và xác nhận riêng.
- Timeout giới hạn thời gian tool; API chỉ trả mã lỗi tổng quát.
- Audit invocation là append-only ở database; correlation ID nối request với run và invocation.
- Query RAG, nội dung tài liệu, secret và raw business result không được ghi vào audit.
- Tenant filter được áp dụng trong chính tool/service, không dựa vào prompt hay dữ liệu client.

## Threat cases đã kiểm thử

| Mối đe dọa | Kết quả mong đợi |
|---|---|
| Viewer yêu cầu doanh thu khi thiếu `audit:read` | `denied`, không trả dữ liệu |
| User tenant B hỏi doanh thu | Chỉ nhận số liệu tenant B |
| Ý định write qua câu hỏi tự nhiên | `unsupported`, không gọi tool |
| Tool vượt timeout | `failed` với `tool_timeout` |
| Sửa audit invocation | PostgreSQL từ chối transaction |
| RAG không đủ bằng chứng | `unsupported`, không tạo câu trả lời giả |

## Rủi ro còn lại

Rule-based intent matching không hiểu mọi cách diễn đạt và có thể trả `unsupported`; đây là fail-closed. SHA-256 của query không thay thế mã hóa và có thể bị dictionary attack với câu hỏi quá dễ đoán, nên audit chỉ dành cho vận hành có quyền. Task 21 chưa cung cấp rate limit riêng cho endpoint Agent, model-based planner, prompt-injection red-team dataset hoặc approval workflow cho write; các mục này vẫn **PLANNED**.
