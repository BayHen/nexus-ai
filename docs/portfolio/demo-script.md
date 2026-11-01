# Kịch bản demo NEXUS AI

## Phạm vi

Demo chạy local bằng synthetic data. Không có public URL, account dựng sẵn hoặc screenshot đã xác minh. Không nhập card, secret thật, tài liệu khách hàng hoặc production credential.

## Chuẩn bị

1. Docker Desktop đang chạy.
2. Sao chép `.env.example` thành `.env` và thay toàn bộ placeholder secret bằng giá trị local ngẫu nhiên.
3. Để `OPENAI_API_KEY` trống nếu không muốn gọi provider live; AI provider deterministic chỉ phù hợp kiểm thử/demo giới hạn.
4. Khởi động:

```powershell
docker compose --env-file .env -f infrastructure/docker/compose.yml config
docker compose --env-file .env -f infrastructure/docker/compose.yml up -d --build
docker compose --env-file .env -f infrastructure/docker/compose.yml ps
```

5. Xác minh `http://127.0.0.1:8000/health/ready` trả `ready` và mở `http://127.0.0.1:3000`.

## Demo 12–15 phút

### 1. Authentication và tenant boundary

- Mở `/register`, tạo user bằng email synthetic.
- Tạo Organization đầu tiên hoặc chọn Organization hiện có.
- Chỉ ra role-aware navigation và active organization.
- Expected: token/session không hiển thị trong UI; business request đi qua active tenant context.

Thông điệp: client không gửi một `organization_id` tùy ý để vượt tenant; backend resolve membership.

### 2. Product và Inventory

- Tạo Category và Product với giá Decimal hợp lệ.
- Quan sát SKU được server sinh.
- Tạo stock tại Branch, adjustment tăng stock và một transfer nếu có hai Branch.
- Thử adjustment làm stock âm.
- Expected: mutation hợp lệ tạo movement history; negative stock bị từ chối và transaction không để partial state.

### 3. Order lifecycle

- Tạo draft Order, thêm Product, sửa quantity.
- Chỉ ra total do server tính và unit price snapshot.
- Confirm Order.
- Expected: state chuyển đúng, Inventory bị trừ trong cùng transaction; transition lặp/không hợp lệ bị từ chối.

### 4. Sandbox Payment

- Tạo Payment Intent với idempotency key.
- Dùng sandbox success flow hoặc signed test webhook theo API contract.
- Gửi lại cùng idempotency/webhook event.
- Expected: không duplicate payment/order completion; history/audit vẫn còn.

Không nhập card number. Đây không phải real payment integration.

### 5. Analytics

- Mở `/analytics`, chọn date range chứa Order vừa hoàn tất.
- Expected: revenue/order count/AOV lấy từ backend; không fallback mock nếu API lỗi.
- Giải thích refund accounting và formula từ `docs/architecture/business-analytics.md`.

### 6. Knowledge và AI Assistant

- Tải một file Markdown synthetic, ví dụ policy hoàn tiền tự viết.
- Kiểm tra indexing status/chunk count.
- Hỏi trợ lý tóm tắt tài liệu hoặc câu revenue/top products.
- Expected: tool status hiển thị; answer có citation với knowledge query; câu ngoài evidence trả unsupported/no-answer.
- Thử đưa instruction độc hại trong document và giải thích retrieved text không được phép thay policy/tool authorization.

Nếu không cấu hình OpenAI live, nói rõ demo dùng deterministic provider và không dùng kết quả đó để claim model quality/cost production.

### 7. Observability và failure handling

Khởi động profile nếu chưa chạy:

```powershell
docker compose --env-file .env -f infrastructure/docker/compose.yml --profile observability up -d
```

- Mở Grafana `http://127.0.0.1:3001` và dashboard `NEXUS AI Overview`.
- Chỉ ra request rate, p95, DB operations, worker outcomes và readiness.
- Correlate một `X-Request-ID` từ response với JSON log/trace.
- Failure drill an toàn: dừng Redis và gọi cached read; expected fallback PostgreSQL. Khởi động lại Redis sau demo.

Không dừng PostgreSQL trong demo có dữ liệu chưa backup trừ khi đang dùng disposable environment.

## Demo API thay cho UI

Nếu UI flow gặp lỗi, dùng Swagger UI tại `/docs` để thực hiện đúng endpoint với synthetic payload. Không giả lập response. Ghi lại status/request ID và chuyển sang code/test tương ứng.

## Bằng chứng nên mở

- README architecture diagram.
- Cross-tenant/concurrency integration tests.
- `docs/security/threat-model.md` và remediation report.
- Task 26 benchmark report với giới hạn.
- GitHub Actions delivery workflow và Terraform, đồng thời nói rõ chưa deploy.

## Cleanup

```powershell
docker compose --env-file .env -f infrastructure/docker/compose.yml down
```

Lệnh này giữ volume. Không dùng `--volumes` nếu chưa chủ động quyết định xóa toàn bộ demo data.

## Tiêu chí demo thành công

- Không dùng private/production data.
- Không che giấu API failure bằng mock.
- Mỗi claim chỉ ra code, test hoặc metric hỗ trợ.
- Nêu rõ sandbox/deterministic/unverified boundary.
- Không claim AWS deployment, production capacity hoặc security tuyệt đối.

