# Kết quả AI Evaluation – Task 22

## Cấu hình

- Dataset: `backend/tests/evaluation/mcp_ai_evaluation.json`, version `task22-v1`.
- MCP SDK: 2.3.0.
- Embedding/answer provider: `local-hash-embedding-v1` và `local-evidence-answer-v1`.
- Similarity threshold: 0,40.
- Chế độ: deterministic offline; không gọi OpenAI API, không có token cost.

## Metric và kết quả thực tế

| Metric | Kết quả |
|---|---:|
| MCP tool allowlist chính xác | 4/4 (100%) |
| Tool output có đủ expected fields | 4/4 (100%) |
| Factual business assertions | 5/5 (100%) |
| Retrieval supported/unsupported classification | 3/3 (100%) |
| Supported answer chứa expected evidence token | 2/2 (100%) |
| Unauthorized/malformed/timeout/tenant security scenarios | 4/4 (100%) |

Factual assertions gồm net revenue, tên sản phẩm bán chạy, sản phẩm low-stock và doanh thu của hai giai đoạn. Kết quả được đối chiếu với order/payment/inventory source rows được tạo trong integration test, không dùng fixture output giả.

## Phạm vi chứng minh

Kết quả chứng minh contract MCP, schema, tool correctness trên dataset nhỏ, tenant isolation và deterministic retrieval baseline. Nó không chứng minh chất lượng trên corpus production, khả năng hiểu mọi cách diễn đạt, độ an toàn tuyệt đối trước prompt injection hoặc chất lượng của model OpenAI live. Live evaluation không chạy vì Task 22 không được cấp API credential/cost authorization.

Khi thay model, embedding, threshold, tool schema hoặc revenue formula, phải tăng version dataset và chạy lại cả unit evaluation lẫn PostgreSQL integration suite.
