output "staging_url" {
  description = "Configured HTTPS staging origin."
  value       = var.staging_base_url
}

output "load_balancer_dns_name" {
  description = "Create or update the staging DNS alias to this ALB hostname."
  value       = aws_lb.main.dns_name
}

output "backend_repository_url" {
  value = aws_ecr_repository.backend.repository_url
}

output "frontend_repository_url" {
  value = aws_ecr_repository.frontend.repository_url
}

output "database_endpoint" {
  value = aws_db_instance.postgres.address
}

output "redis_endpoint" {
  value = aws_elasticache_replication_group.redis.primary_endpoint_address
}

output "rabbitmq_endpoints" {
  value     = aws_mq_broker.rabbitmq.instances[*].endpoints
  sensitive = true
}

output "ecs_cluster_name" { value = aws_ecs_cluster.main.name }
output "backend_task_definition_arn" { value = aws_ecs_task_definition.backend.arn }
output "frontend_task_definition_arn" { value = aws_ecs_task_definition.frontend.arn }
output "worker_task_definition_arn" { value = aws_ecs_task_definition.worker.arn }
output "ecs_public_subnet_ids" { value = aws_subnet.public[*].id }
output "ecs_security_group_id" { value = aws_security_group.ecs.id }
