# MCP Integration cho Business Intelligence

## Mục tiêu và tương thích

NEXUS triển khai một MCP server riêng bằng Python SDK chính thức `mcp` 2.3.x. Transport là Streamable HTTP tại `/mcp`, chạy stateless và trả JSON response. Server tương thích với protocol revision `2025-11-25`; SDK 2.3 còn hỗ trợ revision mới hơn thông qua negotiation. Phiên bản 2.3 được chọn thay cho các bản đến 2.1.1 có advisory về giới hạn session; chế độ stateless cũng loại bỏ session state không cần thiết.

MCP process độc lập với FastAPI business API nhưng dùng cùng application services và PostgreSQL transaction boundary. MCP không cung cấp SQL console, database resource, prompt, filesystem hoặc write tool.

## Tool được công bố

| MCP tool | Quyền nghiệp vụ | Tác động |
|---|---|---|
| `get_revenue_summary` | `audit:read` | Chỉ đọc |
| `get_top_products` | `audit:read` | Chỉ đọc |
| `get_inventory_alerts` | `inventory:read` | Chỉ đọc |
| `compare_sales_periods` | `audit:read` | Chỉ đọc |

Mỗi tool có JSON Schema input/output do Pydantic và MCP SDK sinh. Limit, date, currency và output shape được kiểm tra. `organization_id`, user ID và role không xuất hiện trong tool input.

## Authentication, authorization và tenant

Client gửi NEXUS JWT access token qua `Authorization: Bearer`. `NexusTokenVerifier` kiểm tra signature, issuer, audience, expiry và token type bằng cùng auth configuration với API. Server lấy user ID từ verified claim, sau đó resolve active organization và Membership trực tiếp từ PostgreSQL. Permission `ai-assistant:use` và permission riêng của tool đều được kiểm tra trước khi trả dữ liệu.

Mọi truy vấn nhận `organization_id` từ trusted `TenantContext`. Model hoặc MCP client không thể chọn tenant ID. Việc thay active organization phải thực hiện qua business API đã authorization trước khi gọi MCP.

## Timeout, audit và lỗi

Tool dùng `NEXUS_AGENT_TOOL_TIMEOUT_SECONDS`. Mỗi invocation tạo `agent_runs` và `agent_tool_invocations` với correlation ID, trạng thái, thời lượng và metadata giới hạn. Tool audit là immutable tại database. Error response không chứa stack trace, secret, SQL hoặc raw token.

Malformed JSON/schema bị MCP SDK từ chối trước application service. Authentication thiếu hoặc sai trả HTTP 401. Thiếu permission, timeout và lỗi tool trả MCP `CallToolResult` với `isError=true`.

## Cài đặt và chạy

Từ repository root trên PowerShell:

```powershell
backend/.venv/Scripts/python.exe -m pip install -e "backend[dev]"
Copy-Item .env.example .env
docker compose --env-file .env -f infrastructure/docker/compose.yml up -d postgres
backend/.venv/Scripts/python.exe -m alembic -c backend/alembic.ini upgrade head
backend/.venv/Scripts/python.exe -m nexus.mcp
```

Mặc định server lắng nghe `127.0.0.1:8001`, endpoint `http://127.0.0.1:8001/mcp`. Production phải dùng HTTPS, reverse proxy có request/body/rate limit và cấu hình issuer/resource URL chính xác. Không truyền token qua query string hoặc file cấu hình được commit.

## Ví dụ protocol call

```http
POST /mcp HTTP/1.1
Authorization: Bearer <NEXUS_ACCESS_TOKEN>
Content-Type: application/json
Accept: application/json, text/event-stream
MCP-Protocol-Version: 2025-11-25

{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"get_revenue_summary","arguments":{"date_from":"2026-10-01","date_to":"2026-10-31","currency":"USD"}}}
```

Client nên gọi `tools/list` để đọc schema thay vì hard-code contract. Token ví dụ không được lưu trong shell history dùng chung.

## Phân biệt bốn khái niệm

| Khái niệm | Chạy ở đâu | Mục đích | Có phải business feature? |
|---|---|---|---|
| Codex development Skills | Môi trường phát triển Codex | Hướng dẫn cách agent phát triển/review repository | Không |
| MCP tools | MCP server runtime | Protocol boundary để client đã xác thực gọi capability hẹp | Không tự thân; là adapter |
| Runtime AI Agent tools | Trong LangGraph application process | Capability mà Business Intelligence Agent chọn trong graph | Không tự thân; là orchestration adapter |
| Business application features | Domain/application modules | Analytics, inventory, order, RAG và các quy tắc nghiệp vụ thật | Có |

Skills không được deploy thành MCP tool. MCP và LangGraph cùng tái sử dụng application service nhưng vẫn phải authorization độc lập. Business rules nằm trong module nghiệp vụ, không nằm trong prompt hay MCP description.

## Rủi ro và giới hạn

- Token bị lộ cho phép gọi trong phạm vi quyền của user đến khi hết hạn; bắt buộc HTTPS và access token ngắn hạn.
- MCP tool output là dữ liệu không tin cậy đối với client/model; client không được biến output thành write action nếu chưa có workflow xác nhận.
- MCP server chưa có OAuth authorization-server flow riêng; nó nhận first-party NEXUS JWT. External/public client onboarding vẫn **PLANNED**.
- Rate limit riêng cho MCP, distributed tracing và production reverse-proxy policy vẫn **PLANNED**.
- RAG search không được công bố qua MCP trong Task 22 để giữ document-content boundary hẹp; Agent nội bộ vẫn có tool RAG được authorization riêng.

Rollback: dừng process `python -m nexus.mcp`, gỡ cấu hình `NEXUS_MCP_*` và dependency `mcp`; không cần rollback schema vì Task 22 tái sử dụng audit tables Task 21.

## Nguồn tương thích đã kiểm tra

- [MCP specification – Tools](https://modelcontextprotocol.io/specification/2025-11-25/server/tools)
- [MCP specification – Authorization](https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization)
- [Python SDK – triển khai ASGI/Streamable HTTP](https://github.com/modelcontextprotocol/python-sdk/blob/main/docs/run/asgi.md)
- [Python SDK security advisory về session lifecycle](https://github.com/modelcontextprotocol/python-sdk/security/advisories/GHSA-84m7-p3x7-pcfv)
