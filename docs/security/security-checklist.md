# Checklist bảo mật

## Authentication và secrets

- [x] Password được hash bằng Argon2id; không lưu plaintext.
- [x] Refresh token và password-reset token chỉ lưu digest.
- [x] JWT kiểm tra algorithm allowlist, issuer, audience, expiry và token type.
- [x] Refresh rotation, replay detection và logout revocation có automated tests.
- [x] Production từ chối placeholder JWT/payment secret.
- [ ] Thiết kế access-token denylist hoặc giảm TTL theo risk assessment.
- [ ] Lập runbook rotation cho JWT, webhook, database và broker credentials.

## Authorization và tenant isolation

- [x] Active tenant được resolve từ authenticated user và membership phía server.
- [x] Permission matrix được kiểm tra trong service/tool boundary.
- [x] Các repository nghiệp vụ lọc theo `organization_id`.
- [x] Cross-tenant malicious-ID tests tồn tại cho module chính.
- [ ] Cân nhắc PostgreSQL Row-Level Security như defense-in-depth.

## Web và API

- [x] BFF từ chối cross-site mutation dựa trên `Origin`/`Sec-Fetch-Site`.
- [x] Cookie auth dùng `HttpOnly`, `Secure` ở production và `SameSite`.
- [x] Security headers gồm CSP, frame denial, `nosniff`, referrer và permissions policy.
- [x] React render AI/user data dưới dạng text; không dùng `dangerouslySetInnerHTML`.
- [x] Pydantic giới hạn type, length, enum, currency và date range.
- [x] SQLAlchemy expression API parameter hóa input; không có arbitrary model-generated SQL.
- [x] OpenAPI/Swagger bị tắt ở production.
- [ ] CSP vẫn cần `'unsafe-inline'` cho Next.js hiện tại; triển khai nonce trước khi loại bỏ.

## Rate limiting và availability

- [x] Login, registration và password-reset request có limiter.
- [x] Limiter giới hạn số key trong memory để tránh tăng trưởng vô hạn.
- [ ] Chuyển limiter sang Redis atomic trước khi horizontal scaling.
- [ ] Thêm edge/WAF rate limit theo IP, account và route.
- [ ] Cách ly PDF parsing trong process có hard timeout và resource limit.

## File, AI và MCP

- [x] Upload có byte limit, extension/MIME allowlist, PDF signature, page và extracted-character cap.
- [x] Document ACL được áp trước semantic ranking.
- [x] AI tool là read-only, typed, timeout-bounded và có audit metadata không lưu raw query.
- [x] MCP tool có allowlist và permission check theo active tenant.
- [ ] Dùng MCP-specific audience/resource validation và scope phát hành từ authorization server.
- [ ] Chạy live prompt-injection evaluation trong môi trường dữ liệu giả được phê duyệt.

## Logging và dependencies

- [x] Access log chỉ ghi method/path/status/duration/request ID, không ghi body/token.
- [x] Secret config dùng `SecretStr`.
- [x] `npm audit --omit=dev` không phát hiện production advisory tại thời điểm audit.
- [x] `pip check` không phát hiện broken requirement.
- [ ] Python vulnerability audit bị BLOCKED vì `pip-audit` chưa được cài.
- [ ] Theo dõi và xử lý 16 moderate advisory trong frontend dev-tool chain khi upstream có đường nâng cấp tương thích.
