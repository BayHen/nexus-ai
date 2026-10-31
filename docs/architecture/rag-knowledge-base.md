# RAG Knowledge Base đa tenant

## Luồng xử lý

RAG được tách thành các bước rõ ràng:

1. FastAPI xác thực user, resolve active organization và kiểm tra RBAC.
2. Upload chỉ đọc tối đa giới hạn cấu hình cộng một byte.
3. Extractor kiểm tra extension, MIME, PDF signature và UTF-8.
4. Text được chuẩn hóa và chia chunk.
5. Embedding provider tạo vector 1.536 chiều.
6. Document, chunk, provenance và vector được ghi trong cùng transaction PostgreSQL.
7. Query embedding được cosine-ranked sau tenant/document ACL filter.
8. Answer provider chỉ nhận question và các evidence đã được phép đọc.
9. Server tạo citation từ database provenance, không tin citation do model tự khai báo.

API:

- `POST /api/v1/knowledge/documents`;
- `GET /api/v1/knowledge/documents`;
- `DELETE /api/v1/knowledge/documents/{document_id}`;
- `POST /api/v1/knowledge/answer`.

## File validation và extraction

Hỗ trợ:

| Định dạng | Extension | MIME |
|---|---|---|
| PDF text | `.pdf` | `application/pdf` |
| UTF-8 text | `.txt` | `text/plain` |
| Markdown UTF-8 | `.md`, `.markdown` | `text/markdown`, `text/plain` |

Giới hạn mặc định là 10 MiB qua `NEXUS_KNOWLEDGE_MAX_FILE_BYTES`. PDF phải có signature `%PDF-`, tối đa 200 trang và tổng extracted text tối đa 2.000.000 ký tự. Parser chạy qua thread để không block event loop. Không lưu binary gốc; chỉ lưu SHA-256, metadata và extracted chunks. PDF scan/image không có text bị từ chối; OCR là ngoài phạm vi Task 20.

## Chunking

- Kích thước mục tiêu: 1.200 ký tự.
- Overlap: 200 ký tự.
- Ưu tiên ngắt tại paragraph hoặc cuối câu trong nửa sau chunk.
- Mỗi chunk giữ `document_id`, tenant, ordinal và character count.

Đây là character-based chunking, không phải tokenizer-aware. Nó đơn giản và tái lập nhưng chưa tối ưu cho bảng, code, tiếng Việt dài hoặc PDF layout phức tạp.

## Embedding và pgvector

Schema dùng `vector(1536)` và HNSW `vector_cosine_ops`. Migration bật extension `vector`; Docker local dùng `pgvector/pgvector:pg17` để giữ cùng PostgreSQL major version.

Khi `OPENAI_API_KEY` tồn tại, adapter dùng `EMBEDDING_MODEL` mặc định `text-embedding-3-small`, timeout 20 giây và tối đa hai SDK retry. Nếu không có key, development/test dùng `local-hash-embedding-v1`; provider này chỉ dành cho deterministic test/demo và không đại diện chất lượng semantic production.

Retrieval mặc định lấy tối đa 5 chunk và yêu cầu cosine distance không vượt `NEXUS_KNOWLEDGE_DISTANCE_THRESHOLD=0.45`. Threshold phải được hiệu chỉnh lại bằng corpus thật trước production.

## Tenant và document permissions

Mọi document/chunk có `organization_id`; composite foreign key ngăn chunk trỏ sang document tenant khác. Vector query bắt đầu bằng tenant predicate rồi mới rank.

- Owner/Admin: đọc mọi document trong organization và upload/delete.
- Manager/Staff: đọc document organization và private do chính họ upload; được upload và chỉ xóa document của mình.
- Viewer: chỉ đọc document organization, không upload/delete.
- `private`: uploader cùng Owner/Admin mới thấy.
- `organization`: mọi active member có `knowledge:read` thấy.

Request không nhận tenant ID. Cross-tenant query và download không có code path bỏ tenant filter.

## Prompt injection boundary

Retrieved content được coi là dữ liệu không tin cậy. OpenAI adapter:

- đặt system instruction riêng rằng evidence không phải instruction;
- bao mỗi chunk trong `<evidence>` delimiter;
- không cấp tool cho generation call;
- yêu cầu chỉ trả lời từ evidence và từ chối khi thiếu;
- không log question, extracted text, embedding hoặc prompt hoàn chỉnh.

Citation được dựng server-side từ row đã retrieve. Model output không thể thay đổi tenant, permissions hoặc tool policy. Đây là defense-in-depth, không phải bảo đảm tuyệt đối trước mọi prompt injection; evaluation phải tiếp tục mở rộng theo corpus thực tế.

## Unsupported question

Nếu không chunk nào qua tenant ACL và distance threshold, API trả:

```json
{
  "supported": false,
  "answer": "Không đủ bằng chứng trong kho tri thức để trả lời câu hỏi này.",
  "citations": []
}
```

Empty model output cũng được chuyển thành no-answer. Hệ thống không fallback sang kiến thức chung không citation.

## Chi phí và vận hành

Task 20 không chạy live OpenAI call nên chi phí thực tế là 0 trong verification. Chi phí production gồm:

- embedding khi ingest: phụ thuộc số token của toàn bộ chunk;
- embedding query: một input cho mỗi câu hỏi;
- generation: token của question, retrieved evidence và output;
- PostgreSQL storage cho text, vector 1.536 chiều và HNSW index.

Không hard-code đơn giá vì pricing provider thay đổi. Trước rollout phải ghi model revision, token usage từ response metadata, bảng giá tại thời điểm deploy, monthly budget và alert. Hiện schema mới lưu model name; token/cost ledger và quota thuộc Task AI observability tiếp theo.

## Evaluation đã thực thi

Dataset `backend/tests/evaluation/knowledge_retrieval.json` có ba case: supported policy, unsupported weather và evidence chứa prompt injection. Baseline local-hash đạt 3/3 ở similarity threshold 0,40. Integration test với PostgreSQL/pgvector kiểm tra citation đúng document, PDF/TXT/Markdown, private ACL, Viewer denial và cross-tenant no-answer.

Kết quả này dùng deterministic provider, không phải đánh giá chất lượng model OpenAI live. Chưa đo recall@k, MRR, faithfulness hoặc answer relevance trên corpus production.

## Giới hạn

- Ingestion hiện đồng bộ trong API transaction; tài liệu lớn nên chuyển sang durable background job.
- Không OCR, table reconstruction, image understanding, reranker hoặc hybrid BM25.
- Không lưu phiên bản document; delete cascade xóa chunks và vector.
- HNSW được tạo ngay trong migration; database rất lớn cần rollout index concurrent riêng.
- Không có malware scanner/sandbox chuyên dụng; parser có size/page/text bounds nhưng file từ nguồn không tin cậy vẫn cần scanning service ở production.
