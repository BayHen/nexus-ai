# AI Agent phân tích kinh doanh

## Phạm vi

Task 21 cung cấp endpoint `POST /api/v1/agent/ask` cho trợ lý phân tích chỉ đọc. Agent trả lời năm nhóm câu hỏi đã duyệt: doanh thu, sản phẩm bán chạy, cảnh báo tồn kho, so sánh hai giai đoạn và tóm tắt tài liệu mà người dùng được phép đọc. Agent không sinh hoặc chạy SQL, không có tool ghi dữ liệu và không tự mở rộng sang MCP.

## Workflow LangGraph

```text
START
  -> authorize
  -> plan
  -> execute_tool (tối đa một lần)
  -> compose_answer
  -> END
```

Mỗi bước được ghi vào `transitions`. `authorize` kiểm tra permission `ai-assistant:use`; `plan` ánh xạ câu hỏi vào allowlist tool cố định; `execute_tool` kiểm tra thêm permission nghiệp vụ, timeout và ghi audit; `compose_answer` chỉ định dạng kết quả có kiểu. Graph không có vòng lặp, không gọi tool động và mỗi request chỉ được gọi tối đa một tool.

Các trạng thái kết thúc gồm `completed`, `unsupported`, `denied` và `failed`. Câu hỏi ngoài phạm vi hoặc truy hồi không đủ bằng chứng trả `unsupported`; lỗi timeout trả `failed`; thiếu quyền Agent hoặc quyền tool trả `denied`.

## Tool contract và quyền

| Tool | Input chính | Nguồn dữ liệu | Permission nghiệp vụ |
|---|---|---|---|
| `get_revenue_summary` | ngày bắt đầu/kết thúc, currency | Analytics service | `audit:read` |
| `get_top_products` | ngày, currency, limit | Analytics service | `audit:read` |
| `get_inventory_alerts` | limit | Product, Branch và StockLevel | `inventory:read` |
| `compare_sales_periods` | hai khoảng ngày, currency | Analytics service | `audit:read` |
| `search_knowledge_base` | query | RAG service và pgvector | `knowledge:read` |

Input và output được kiểm tra bằng Pydantic. Khoảng ngày đảo ngược, limit ngoài biên và currency không hợp lệ bị từ chối trước khi truy vấn. Tenant context lấy từ access token và active organization phía server; request không nhận `organization_id`.

## Audit và giới hạn dữ liệu

`agent_runs` lưu trạng thái, tool được chọn, correlation ID, số transition và mã lỗi. `agent_tool_invocations` lưu tool, trạng thái, thời lượng và metadata giới hạn; trigger PostgreSQL cấm sửa hoặc xóa audit invocation. Nội dung câu hỏi RAG không được lưu: audit chỉ giữ độ dài và SHA-256. Kết quả audit không giữ nội dung tài liệu hoặc dữ liệu doanh thu chi tiết.

Timeout được cấu hình bằng `NEXUS_AGENT_TOOL_TIMEOUT_SECONDS`, mặc định 5 giây. Exception nội bộ được chuyển thành mã lỗi tổng quát và không đưa secret hay stack trace vào API.

## Chính sách write và RAG

Agent hiện chỉ đọc. Câu hỏi mang ý định `create`, `update`, `delete`, `change`, `refund` hoặc `adjust` bị chặn và hướng người dùng sang workflow riêng có authorization và xác nhận rõ ràng. Đây là boundary bắt buộc; Task 21 không triển khai workflow ghi.

Tool knowledge tái sử dụng kiểm tra document permission và tenant filter của RAG. Nội dung truy hồi là dữ liệu không tin cậy, không được phép thay đổi tool policy. Câu trả lời có bằng chứng kèm document ID, tên tài liệu, chunk ordinal và excerpt; không đủ bằng chứng thì không suy diễn.

## Evaluation và giới hạn

Bộ dữ liệu `backend/tests/evaluation/business_agent_tools.json` bao phủ đủ năm intent. Integration tests đối chiếu tool selection, số liệu từ order/payment thật, low-stock, chênh lệch giai đoạn, citation, timeout, quyền và cách ly chéo tenant.

Planner Task 21 dùng rule cố định để có hành vi xác định và audit được; chưa dùng model để phân loại câu hỏi hoặc diễn đạt câu trả lời. Câu hỏi cần nêu rõ intent và chủ đề tài liệu. Không có conversational memory, multi-tool planning, streaming, MCP hoặc write tool; các khả năng đó vẫn **PLANNED** và phải có evaluation/boundary riêng trước khi bật.
