# Security review – RAG Knowledge Base

## Trust boundaries đã kiểm tra

- Upload bytes, filename, MIME, extracted text và question đều do attacker kiểm soát.
- OpenAI là external processor khi API key được cấu hình.
- Document content và model output không được coi là authorization input.
- PostgreSQL tenant/document ACL là boundary bắt buộc trước vector ranking.

## Biện pháp đã triển khai

- Size, extension, MIME, PDF signature, page và extracted-text bounds.
- Không dùng filename làm filesystem path và không ghi upload ra disk.
- RBAC riêng `knowledge:read`/`knowledge:write` cùng private document ACL.
- Composite tenant foreign key cho chunks.
- Query tenant-filtered trước cosine order/limit.
- Generation không có tool, evidence delimiters và explicit untrusted-content instruction.
- Server-owned citations; unsupported question không dùng general model knowledge.
- Log không chứa document text, question, embedding, API key hoặc full prompt.

## Residual risks

- PDF parser là dependency xử lý input phức tạp; cần dependency scanning và sandbox/scanner production.
- Prompt injection không thể được loại bỏ tuyệt đối bằng prompt; không cấp tools giúp giảm impact.
- Local hash provider không đủ chất lượng production.
- OpenAI data handling, retention và regional requirements cần legal/privacy review trước khi gửi private document.
- Không có per-tenant token quota/rate limit riêng cho AI trong Task 20.

Không phát hiện code path đã kiểm thử cho phép đọc document tenant khác. Kết luận này giới hạn ở implementation và automated tests hiện tại, không phải penetration test production.
