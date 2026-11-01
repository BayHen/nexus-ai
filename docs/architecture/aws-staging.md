# Kiến trúc AWS staging

## Quyết định

Staging dùng ECS Fargate thay vì Kubernetes. Quy mô hiện tại không cần control plane, operator hoặc autoscaling phức tạp của Kubernetes; ECS giảm chi phí vận hành và vẫn cung cấp task isolation, health check, rolling deployment và deployment circuit breaker.

Kiến trúc gồm:

- ALB public với HTTPS/TLS 1.2 trở lên; HTTP chỉ redirect sang HTTPS.
- ECS Fargate chạy `frontend`, `backend` và `worker` ở hai public subnet. Task có public IP để pull image và gọi dịch vụ ngoài mà không cần NAT Gateway; security group không cho Internet truy cập trực tiếp, chỉ nhận traffic từ ALB.
- RDS PostgreSQL 17, ElastiCache Redis và Amazon MQ RabbitMQ nằm trong private subnet, không public endpoint.
- ECR lưu image immutable theo Git SHA và scan khi push.
- Secrets Manager cung cấp runtime secrets cho ECS execution role.
- CloudWatch Logs giữ log ứng dụng 14 ngày và ECS Container Insights cung cấp baseline vận hành.

## Luồng mạng

```text
Internet -> ALB HTTPS -> frontend:3000
                    \-> backend:8000 (/api/*, /health/*)

backend/worker -> RDS PostgreSQL
backend/worker -> ElastiCache Redis
backend/worker -> Amazon MQ RabbitMQ
backend        -> OpenAI API (khi được cấu hình)
```

Private data subnets không có route Internet. ECS tasks dùng public subnet là trade-off có chủ ý để tránh NAT Gateway trong staging. Security group của ECS chỉ nhận port 3000/8000 từ ALB; database/cache/broker chỉ nhận từ ECS security group. Production nên đánh giá VPC endpoints và private ECS subnets thay cho trade-off này.

## Lựa chọn tiết kiệm chi phí

- Một task cho mỗi service và không bật autoscaling mặc định.
- RDS `db.t4g.micro`, 20 GiB gp3, single-AZ và backup ba ngày.
- Một Redis `cache.t4g.micro` và một RabbitMQ `mq.t3.micro` single-instance.
- Không dùng NAT Gateway, EKS hoặc multi-AZ data service trong staging mặc định.
- ECR chỉ giữ 20 image gần nhất; CloudWatch Logs giữ 14 ngày.

RDS, ALB, ElastiCache và Amazon MQ vẫn tạo chi phí cố định ngay cả khi ít traffic. Phải kiểm tra AWS Pricing Calculator tại thời điểm triển khai và đặt AWS Budget trước `terraform apply`. Kiến trúc này không được xem là free-tier.

## Trust boundary và secrets

GitHub Actions dùng OIDC để assume một deploy role ngắn hạn. Không lưu `AWS_ACCESS_KEY_ID` hoặc `AWS_SECRET_ACCESS_KEY` trong repository/GitHub secrets. Trust policy của role phải giới hạn đúng organization, repository, branch hoặc GitHub Environment `staging`.

ECS execution role chỉ được `secretsmanager:GetSecretValue` trên một application secret ARN. Secret JSON cần các key:

- `DATABASE_URL`
- `JWT_SECRET_KEY`
- `PAYMENT_WEBHOOK_SECRET`
- `REDIS_URL` dùng `rediss://`
- `CELERY_BROKER_URL` dùng `amqps://`
- `CELERY_RESULT_BACKEND`
- `OPENAI_API_KEY` nếu bật AI provider
- `OTEL_EXPORTER_OTLP_ENDPOINT` trỏ tới private OTLP collector; không trỏ thẳng tới endpoint public không được xác thực

Terraform không tạo secret value. Giá trị `db_password` và `mq_password` vẫn đi vào encrypted Terraform state vì provider cần chúng để tạo managed service. Remote state phải dùng S3 encryption, versioning, public-access block và quyền truy cập tối thiểu. Không đưa `.tfvars` chứa secret vào Git.

## Giới hạn và hướng production

- Single-AZ không có high availability; phù hợp staging, không phải production.
- Chưa định nghĩa WAF, Route 53 record, AWS Budget, alarm, autoscaling hoặc cross-region recovery.
- Terraform chưa tạo state bucket/OIDC provider để tránh bootstrapping bằng quyền rộng trong cùng state.
- Database migration phải theo expand-contract; rollback image không tự rollback schema.
- Cần load test trên AWS staging trước khi chọn kích thước production.

