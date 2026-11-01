resource "aws_ecr_repository" "backend" {
  name                 = "${local.name}-backend"
  image_tag_mutability = "IMMUTABLE"
  image_scanning_configuration { scan_on_push = true }
  encryption_configuration { encryption_type = "AES256" }
}

resource "aws_ecr_repository" "frontend" {
  name                 = "${local.name}-frontend"
  image_tag_mutability = "IMMUTABLE"
  image_scanning_configuration { scan_on_push = true }
  encryption_configuration { encryption_type = "AES256" }
}

resource "aws_ecr_lifecycle_policy" "repositories" {
  for_each   = { backend = aws_ecr_repository.backend.name, frontend = aws_ecr_repository.frontend.name }
  repository = each.value
  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Retain the latest 20 staging images"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 20
      }
      action = { type = "expire" }
    }]
  })
}

resource "aws_cloudwatch_log_group" "application" {
  name              = "/ecs/${local.name}"
  retention_in_days = 14
}

resource "aws_ecs_cluster" "main" {
  name = local.name
  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

data "aws_iam_policy_document" "ecs_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "execution" {
  name               = "${local.name}-execution"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume.json
}

resource "aws_iam_role_policy_attachment" "execution" {
  role       = aws_iam_role.execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

data "aws_iam_policy_document" "runtime_secrets" {
  statement {
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [var.application_secret_arn]
  }
}

resource "aws_iam_role_policy" "runtime_secrets" {
  name   = "runtime-secrets"
  role   = aws_iam_role.execution.id
  policy = data.aws_iam_policy_document.runtime_secrets.json
}

resource "aws_iam_role" "task" {
  name               = "${local.name}-task"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume.json
}

locals {
  log_configuration = {
    logDriver = "awslogs"
    options = {
      awslogs-group         = aws_cloudwatch_log_group.application.name
      awslogs-region        = var.aws_region
      awslogs-stream-prefix = "application"
    }
  }
  backend_secrets = [
    for key in ["DATABASE_URL", "JWT_SECRET_KEY", "PAYMENT_WEBHOOK_SECRET", "REDIS_URL", "CELERY_BROKER_URL", "CELERY_RESULT_BACKEND", "OPENAI_API_KEY"] : {
      name      = key
      valueFrom = "${var.application_secret_arn}:${key}::"
    }
  ]
}

resource "aws_ecs_task_definition" "backend" {
  family                   = "${local.name}-backend"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 512
  memory                   = 1024
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn
  container_definitions = jsonencode([{
    name         = "backend"
    image        = var.backend_image
    essential    = true
    portMappings = [{ containerPort = 8000, protocol = "tcp" }]
    environment = [
      { name = "NEXUS_ENVIRONMENT", value = "staging" },
      { name = "NEXUS_LOG_LEVEL", value = "INFO" }
    ]
    secrets          = local.backend_secrets
    logConfiguration = local.log_configuration
    healthCheck = {
      command     = ["CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/live', timeout=2)\" || exit 1"]
      interval    = 30
      timeout     = 5
      retries     = 3
      startPeriod = 20
    }
  }])
}

resource "aws_ecs_task_definition" "frontend" {
  family                   = "${local.name}-frontend"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 256
  memory                   = 512
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn
  container_definitions = jsonencode([{
    name         = "frontend"
    image        = var.frontend_image
    essential    = true
    portMappings = [{ containerPort = 3000, protocol = "tcp" }]
    environment  = [{ name = "API_BASE_URL", value = var.staging_base_url }]
    logConfiguration = merge(local.log_configuration, {
      options = merge(local.log_configuration.options, { awslogs-stream-prefix = "frontend" })
    })
  }])
}

resource "aws_ecs_task_definition" "worker" {
  family                   = "${local.name}-worker"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 512
  memory                   = 1024
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn
  container_definitions = jsonencode([{
    name      = "worker"
    image     = var.backend_image
    essential = true
    command   = ["celery", "-A", "nexus.platform.background.celery_app:celery_app", "worker", "--loglevel=INFO", "--concurrency=2"]
    environment = [
      { name = "NEXUS_ENVIRONMENT", value = "staging" },
      { name = "NEXUS_LOG_LEVEL", value = "INFO" }
    ]
    secrets = local.backend_secrets
    logConfiguration = merge(local.log_configuration, {
      options = merge(local.log_configuration.options, { awslogs-stream-prefix = "worker" })
    })
  }])
}
