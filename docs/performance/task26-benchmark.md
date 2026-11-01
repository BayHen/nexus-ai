# Báo cáo benchmark Task 26

## Phạm vi

Benchmark này đo baseline HTTP và middleware của hai endpoint public, deterministic: `GET /health/live` và `GET /api/v1`. Nó không đo PostgreSQL, Redis, RabbitMQ, OpenAI, pgvector, xác thực hoặc workflow nghiệp vụ. Vì vậy kết quả chỉ dùng để phát hiện regression ở lớp HTTP, không phải capacity certification cho production.

Toàn bộ request và cấu hình đều là dữ liệu synthetic. Không có dữ liệu khách hàng hoặc tenant thật.

## Môi trường

| Thuộc tính | Giá trị |
|---|---|
| Ngày đo | 01/11/2026 |
| Hệ điều hành | Windows x64, release 10.0.26200 |
| CPU | Intel Core i5-13400F, 16 logical CPU |
| RAM | 15,8 GiB |
| Python | 3.14.3 trong project virtual environment |
| Locust | 2.47.0 |
| Application server | Uvicorn, một process, access log tắt |
| Network | Client và server trên cùng máy |

Python local khác phiên bản 3.12 được dùng trong CI; không nên so sánh trực tiếp hai môi trường khi theo dõi regression.

## Dataset và workload

- Dataset: không có bản ghi database; response cố định từ application factory và database lifecycle double luôn healthy.
- Số concurrent clients: 25.
- Ramp-up: 5 clients/giây.
- Thời lượng cấu hình: 20 giây.
- Tỷ lệ request: `health/live` 80%, `api/v1` 20%.
- Think time: ngẫu nhiên 50–200 ms giữa các request của mỗi client.

## Kết quả thực tế

| Endpoint | Requests | Throughput | p50 | p95 | Error rate |
|---|---:|---:|---:|---:|---:|
| `GET /health/live` | 2.581 | 135,07 req/s | 3 ms | 7 ms | 0% |
| `GET /api/v1` | 643 | 33,65 req/s | 4 ms | 7 ms | 0% |
| Tổng | 3.224 | 168,72 req/s | 3 ms | 7 ms | 0% |

Aggregate p99 là 10 ms. Max latency 184,62 ms cho thấy vẫn có outlier dù p95 thấp; bài đo ngắn chưa đủ để xác định nguyên nhân hoặc tần suất dài hạn.

CSV gốc nằm tại `docs/performance/artifacts/task26-public-read-no-access-log_stats.csv`. Các file history và failures cùng prefix được giữ để tái kiểm tra.

## Quan sát access log

Một lần đo đối chứng với Uvicorn access log bật đạt 159,33 req/s, p50 5 ms và p95 32 ms, không lỗi. Khi tắt access log, throughput tăng khoảng 5,9% và p95 giảm từ 32 ms xuống 7 ms trên máy đo này. Đây là tín hiệu về chi phí console I/O trong benchmark local, không phải lý do tắt structured application logs hoặc audit logs trong production.

## Bottleneck và giới hạn còn lại

- Console access logging tác động đáng kể tới tail latency trong môi trường local.
- Outlier p99/max cần một soak test dài hơn và profiling trước khi kết luận.
- Chưa benchmark endpoint có PostgreSQL, tenant authorization, serialization lớn, cache hoặc queue.
- Chưa chạy Redis integration trong phiên này; ba cache test bị skip theo điều kiện môi trường.
- Chưa đo memory, CPU saturation, database pool saturation hoặc giới hạn số connection.
- Kết quả loopback không đại diện network latency, TLS, reverse proxy hoặc hạ tầng AWS.

## Hướng benchmark tiếp theo

1. Tạo dataset synthetic có quy mô và phân bố được version hóa cho catalog, orders và analytics.
2. Đo read/write workflow đã xác thực trên PostgreSQL disposable, tách cold-cache và warm-cache.
3. Chạy nhiều mức concurrency, thời lượng ít nhất 10–30 phút và ghi CPU/RAM/database pool.
4. Đặt regression threshold dựa trên nhiều lần chạy ổn định trong CI runner cùng loại; không dùng một lần đo local làm SLO.

