# Threat model NEXUS AI

## Phạm vi và giả định

Threat model này phản ánh repository tại Task 25. Phạm vi gồm FastAPI, Next.js BFF, PostgreSQL, Redis, RabbitMQ/Celery, AI/RAG, MCP và sandbox payment. Đây không phải chứng nhận ứng dụng an toàn tuyệt đối và chưa thay thế penetration test độc lập hoặc đánh giá môi trường AWS thực tế.

## Tài sản cần bảo vệ

- Password hash, JWT signing secret, refresh token, password-reset token và payment webhook secret.
- Dữ liệu nghiệp vụ theo organization: sản phẩm, tồn kho, order, payment, analytics và audit event.
- Tài liệu private/organization, chunks, embeddings, citations và AI prompt.
- Quyền Owner/Admin và active organization context.
- Tính toàn vẹn của stock, order, payment, outbox và background job.
- OpenAI API key, database URL, broker URL và AWS credentials.

## Actor và trust boundary

| Actor | Quyền dự kiến | Rủi ro chính |
|---|---|---|
| Người dùng chưa xác thực | Register, login, password-reset request | Credential stuffing, enumeration, resource exhaustion |
| Thành viên tenant | Chỉ dữ liệu và permission của organization hiện tại | IDOR, cross-tenant access, privilege escalation |
| Owner/Admin | Quản trị thành viên và dữ liệu nhạy cảm | Account takeover có blast radius lớn |
| Webhook provider | Gửi event có chữ ký | Forgery, replay, duplicate event |
| AI provider | Nhận prompt/evidence được chọn | Prompt injection, data disclosure, hallucination |
| MCP client | Gọi allowlisted read-only tools bằng access token | Token confusion, unauthorized tool invocation |
| Worker/queue | Xử lý job và outbox | Duplicate delivery, tenant context spoofing |

Trust boundary chính:

1. Browser → Next.js BFF: cookie `HttpOnly`, CSRF/Origin và XSS boundary.
2. BFF/MCP client → FastAPI: JWT signature, issuer, audience và active membership.
3. FastAPI → PostgreSQL: parameterized SQLAlchemy queries và transaction boundary.
4. FastAPI/worker → Redis/RabbitMQ/OpenAI: secrets, timeout, retry và content disclosure.
5. Document upload → parser/embedding/model: file validation và untrusted-content boundary.

## Threat theo STRIDE

| Nhóm | Kịch bản | Control hiện tại | Rủi ro còn lại |
|---|---|---|---|
| Spoofing | JWT giả, hết hạn hoặc sai audience | HS256 allowlist, `iss`, `aud`, `exp`, `type`, `jti` bắt buộc | Access token chưa có server-side revocation tức thời |
| Tampering | Client sửa tenant ID, total hoặc payment event | Tenant lấy từ active membership; server tính total; webhook HMAC và duplicate protection | Cần key rotation runbook cho webhook/JWT |
| Repudiation | Thành viên phủ nhận thay đổi role/payment/tool call | Audit event bất biến ở application API, correlation ID, tool invocation metadata | Chưa có append-only storage ngoài database/operator boundary |
| Information disclosure | Cross-tenant IDOR hoặc private document leakage | Repository query có `organization_id`; document ACL trước vector ranking; generic auth errors | Chưa có database Row-Level Security như defense-in-depth |
| Denial of service | Argon2 registration/login, PDF parsing, random limiter keys | Rate limit register/login, giới hạn key, file byte/page/character cap | Limiter in-process; PDF parsing chưa có hard timeout/process isolation |
| Elevation of privilege | Role escalation, arbitrary SQL/tool call | Permission matrix, service checks, fixed AI/MCP tool allowlist, typed inputs | MCP dùng chung JWT audience và tự cấp scope `mcp:read` |

## AI và MCP boundary

- Retrieved content và user question là dữ liệu không tin cậy.
- RAG provider có instruction không làm theo nội dung evidence, không có tool access và chỉ trả lời từ evidence.
- Runtime agent chỉ chọn trong năm tool định nghĩa trước; không sinh hoặc thực thi SQL tùy ý.
- `BusinessTools` kiểm tra permission lại cho từng tool và luôn áp `organization_id` từ server context.
- MCP chỉ expose bốn analytics tool read-only, validate schema và resolve active tenant từ token subject.
- Rủi ro prompt injection không thể loại bỏ hoàn toàn; citation và no-answer behavior là control giảm thiểu, không phải bằng chứng tuyệt đối về factual correctness.

## Không nằm trong xác minh hiện tại

- AWS IAM, WAF, TLS termination, backup encryption và network policy production.
- Penetration test trên deployment thực.
- Live OpenAI evaluation với private corpus.
- Compromise của database administrator, CI runner hoặc host operating system.
