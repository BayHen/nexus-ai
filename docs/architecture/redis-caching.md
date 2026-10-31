# Redis caching tenant-aware

## Phạm vi

Task 17 bổ sung Redis làm cache tùy chọn cho hai API đọc nhiều:

- `GET /api/v1/products/{product_id}`;
- `GET /api/v1/categories/{category_id}`.

Các API danh sách chưa được cache vì tổ hợp filter, sort và pagination làm tăng mạnh số key và độ phức tạp invalidation. Order, payment và inventory không dùng cache làm nguồn quyết định nghiệp vụ. PostgreSQL luôn là source of truth.

## Boundary bảo mật

Request phải hoàn tất xác thực, resolve active organization từ trạng thái server-side và kiểm tra quyền `catalog:read` trước khi đọc Redis. Client không cung cấp tenant ID cho cache lookup. Key có dạng:

```text
nexus:v1:tenant:{organization_id}:{resource}:{resource_id}
```

Vì vậy cùng một resource ID ở hai organization không dùng chung key. Cache hit chỉ thay thế bước đọc PostgreSQL sau authorization; cache không thể cấp quyền truy cập.

## TTL và invalidation

- TTL mặc định là 60 giây, cấu hình bằng `NEXUS_CACHE_TTL_SECONDS` trong khoảng 1–3600 giây.
- Product/Category update hoặc delete đăng ký key cần xóa trong transaction hiện tại.
- Dependency transaction chỉ xóa key sau khi database commit thành công. Rollback không invalidation một giá trị vẫn còn hợp lệ.
- Nếu thao tác xóa Redis thất bại, dữ liệu cũ bị giới hạn bởi TTL; request mutation vẫn thành công vì database đã commit.
- Create không xóa key vì ID mới chưa có cache entry. Negative result không được cache.

Redis local được cấu hình không persistence và dùng eviction `allkeys-lru`; đây là cache có thể tái tạo, không phải data store nghiệp vụ.

## Fallback và metric

`RedisCacheService` xử lý lỗi kết nối, timeout và payload JSON không hợp lệ như cache miss, ghi structured warning không chứa URL hay secret, rồi đọc PostgreSQL. Redis không tham gia readiness gate nên API vẫn hoạt động khi cache unavailable.

`GET /api/v1/cache/metrics` chỉ cho role có quyền `audit:read` và trả về counter `hits`, `misses`, `errors`, `sets`, `deletes`. Counter hiện nằm trong memory của từng API process, reset khi restart và chưa tổng hợp giữa nhiều replica. Đây là metric cơ bản phục vụ Task 17, chưa thay thế Prometheus/OpenTelemetry ở Task observability sau.

## Benchmark đã thực thi

Ngày 31/10/2026, benchmark integration chạy 30 cặp request tuần tự trên Windows local, PostgreSQL 17 và Redis 7.4 trong Docker. Mỗi cold request xóa đúng product key trước khi gọi API; warm request kế tiếp đọc cùng resource từ Redis. Kết quả median:

| Trường hợp | Median |
|---|---:|
| Cache miss, đọc PostgreSQL rồi ghi Redis | 8,568 ms |
| Cache hit Redis | 6,601 ms |

Trong phép đo này, cache hit giảm khoảng 1,967 ms, tương đương 23,0% median latency. Đây là micro-benchmark local với 30 mẫu, không phải load test production; kết quả sẽ thay đổi theo network, connection pool, concurrency và kích thước payload. Test chỉ xác nhận cả hai đường đi trả cùng payload và ghi lại số đo, không dùng chênh lệch tốc độ làm assertion để tránh flaky test.

Lệnh tái lập:

```powershell
Set-Location backend
$env:NEXUS_TEST_DATABASE_ADMIN_URL = "postgresql://<user>:<local-password>@127.0.0.1:5432/postgres"
.\.venv\Scripts\python.exe -m pytest tests/integration/test_cache_api.py -q -s
```

## Giới hạn đã biết

- Chưa có single-flight/request coalescing nên nhiều cache miss đồng thời có thể cùng đọc PostgreSQL.
- Invalidation là best-effort sau commit; Redis outage có thể giữ dữ liệu cũ đến hết TTL.
- Counter metric theo process, chưa có histogram latency hay export backend.
- Redis Compose chỉ bind localhost và không bật authentication, phù hợp local development. Production phải dùng endpoint private, TLS, authentication và secret management thích hợp.
