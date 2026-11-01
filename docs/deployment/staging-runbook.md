# Runbook triển khai staging

## Phạm vi và điều kiện an toàn

Runbook này mô tả provisioning và deployment có kiểm soát. Không có lệnh nào đã được chạy trên AWS trong Task 27. `terraform plan` chỉ mô tả thay đổi; `terraform apply` mới tạo tài nguyên có phí và phải có phê duyệt rõ ràng.

## Công cụ cần có

- Docker Engine và Docker Compose.
- Terraform 1.9–1.x.
- AWS CLI v2 và `jq` cho thao tác rollback thủ công.
- AWS account, domain staging và ACM certificate cùng region với ALB.
- S3 state bucket đã bật encryption, versioning, public-access block và state locking.
- GitHub Environment tên `staging` có required reviewers.

## Chạy local bằng Docker Compose

Sao chép `.env.example` thành `.env`, thay toàn bộ placeholder secret bằng giá trị local ngẫu nhiên, sau đó:

```powershell
docker compose --env-file .env -f infrastructure/docker/compose.yml config
docker compose --env-file .env -f infrastructure/docker/compose.yml build
docker compose --env-file .env -f infrastructure/docker/compose.yml up -d
docker compose --env-file .env -f infrastructure/docker/compose.yml ps
```

Backend chạy migration trước khi mở Uvicorn. Worker chỉ khởi động sau khi backend ready. Dừng môi trường mà không xóa volume:

```powershell
docker compose --env-file .env -f infrastructure/docker/compose.yml down
```

Không chạy `down --volumes` trừ khi đã xác nhận muốn xóa dữ liệu local.

## Bootstrap AWS thủ công

1. Tạo S3 state bucket và GitHub OIDC provider/role bằng quy trình bootstrap được quản trị riêng.
2. Tạo ACM certificate, DNS staging và một Secrets Manager JSON secret theo danh sách trong tài liệu kiến trúc.
3. Sao chép `staging.tfvars.example` thành file ngoài Git hoặc truyền non-secret bằng CLI.
4. Truyền secret bằng biến môi trường `TF_VAR_application_secret_arn`, `TF_VAR_db_password`, `TF_VAR_mq_username`, `TF_VAR_mq_password`.
5. Khởi tạo backend và kiểm tra plan:

```powershell
Set-Location infrastructure/terraform
terraform init -backend-config="bucket=<state-bucket>" -backend-config="key=nexus-ai/staging/terraform.tfstate" -backend-config="region=ap-southeast-1" -backend-config="use_lockfile=true" -backend-config="encrypt=true"
terraform fmt -check -recursive
terraform validate
terraform plan -var-file=staging.tfvars -out=staging.tfplan
terraform show staging.tfplan
```

Lần bootstrap có vòng phụ thuộc ECR/image. Đặt ba `desired_count` bằng `0`, dùng URI image placeholder hợp lệ, review và apply để tạo ECR cùng nền tảng. Push image đầu tiên, cập nhật URI theo Git SHA, sau đó plan/apply lần hai với `desired_count = 1`.

Không chạy lệnh sau nếu chưa có phê duyệt chi phí và review plan:

```powershell
terraform apply staging.tfplan
```

Sau apply, tạo DNS alias tới output `load_balancer_dns_name`. Không truy cập staging bằng ALB hostname nếu certificate chỉ cấp cho custom domain.

## Cấu hình GitHub Environment

Secret:

- `AWS_DEPLOY_ROLE_ARN`

Variables:

- `AWS_REGION`
- `BACKEND_REPOSITORY`
- `FRONTEND_REPOSITORY`
- `ECS_CLUSTER`
- `ECS_PUBLIC_SUBNET_IDS`: hai subnet ID phân cách bằng dấu phẩy, không có dấu nháy.
- `ECS_SECURITY_GROUP_ID`

Deploy role dùng trust policy OIDC giới hạn repository và Environment `staging`; permission policy bắt đầu từ `infrastructure/iam/github-deploy-policy.json` sau khi thay placeholder account/region. Không cấp AdministratorAccess.

## Luồng CI/CD

Pull request chạy:

- backend/frontend lint, type check, test, build và Playwright;
- build hai production images;
- Trivy fail với vulnerability đã có bản sửa ở mức HIGH/CRITICAL;
- `docker compose config`;
- `terraform fmt`, `init -backend=false` và `validate`.

Workflow `Deploy staging` chỉ chạy thủ công và phải qua GitHub Environment approval. Nó:

1. Checkout đúng `git_ref` và dùng commit SHA làm immutable tag.
2. Assume AWS role bằng OIDC credential ngắn hạn.
3. Build/push hai image lên ECR.
4. Đăng ký task revisions nhưng chưa đổi services.
5. Chạy `alembic upgrade head` bằng backend task revision mới.
6. Chỉ khi migration exit code 0 mới cập nhật backend/frontend/worker và chờ stable.

## Rollback

Nếu deployment circuit breaker tự rollback, kiểm tra ECS events và CloudWatch Logs trước khi thử lại. Để rollback image thủ công:

```powershell
aws ecs list-task-definitions --family-prefix nexus-ai-staging-backend --sort DESC
aws ecs update-service --cluster nexus-ai-staging --service backend --task-definition <previous-backend-arn>
aws ecs update-service --cluster nexus-ai-staging --service frontend --task-definition <previous-frontend-arn>
aws ecs update-service --cluster nexus-ai-staging --service worker --task-definition <previous-worker-arn>
aws ecs wait services-stable --cluster nexus-ai-staging --services backend frontend worker
```

Rollback application không tự downgrade database. Chỉ dùng Alembic downgrade khi migration cụ thể đã được chứng minh an toàn và backup đã được xác nhận. Mặc định là roll-forward bằng migration sửa lỗi. Trước thay đổi phá vỡ dữ liệu, tạo manual RDS snapshot và kiểm tra khả năng restore.

## Blocker hiện tại

- Chưa có AWS account/role, remote state bucket, ACM certificate, DNS hoặc application secret được cấp cho phiên này.
- Terraform đã được format và validate qua container CLI 1.10.5; chưa có AWS-backed `terraform plan` vì không có credentials/backend.
- Hai production images đã build local thành công. Trivy được cấu hình trong CI/CD nhưng local vulnerability scan chưa chạy; không cấp Docker socket cho scanner container và không gửi image metadata ra Docker Scout trong phiên này.
- `npm audit` trong lúc đồng bộ lockfile báo 16 vulnerability mức moderate; không có auto-fix hoặc breaking upgrade nào được áp dụng trong Task 27.
- Frontend dependency tree và Terraform provider có lockfile; Docker base images được pin bằng digest. Backend Python hiện chỉ constrain version ranges trong `pyproject.toml`, chưa có transitive lockfile đa nền tảng nên build backend chưa byte-for-byte reproducible — đây là hạng mục hardening còn lại.
- Không có AWS resource nào được tạo, image nào được push hoặc staging nào được public.

