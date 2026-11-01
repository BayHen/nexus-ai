resource "aws_db_subnet_group" "main" {
  name       = local.name
  subnet_ids = aws_subnet.private[*].id
}

resource "aws_db_instance" "postgres" {
  identifier                  = local.name
  engine                      = "postgres"
  engine_version              = "17"
  instance_class              = "db.t4g.micro"
  allocated_storage           = 20
  max_allocated_storage       = 50
  storage_type                = "gp3"
  storage_encrypted           = true
  db_name                     = "nexus_ai"
  username                    = "nexus_ai"
  password                    = var.db_password
  db_subnet_group_name        = aws_db_subnet_group.main.name
  vpc_security_group_ids      = [aws_security_group.data.id]
  publicly_accessible         = false
  multi_az                    = false
  backup_retention_period     = 3
  deletion_protection         = var.deletion_protection
  skip_final_snapshot         = false
  final_snapshot_identifier   = "${local.name}-final"
  auto_minor_version_upgrade  = true
  allow_major_version_upgrade = false
  apply_immediately           = false
}

resource "aws_elasticache_subnet_group" "main" {
  name       = local.name
  subnet_ids = aws_subnet.private[*].id
}

resource "aws_elasticache_replication_group" "redis" {
  replication_group_id       = local.name
  description                = "NEXUS AI staging cache"
  engine                     = "redis"
  engine_version             = "7.1"
  node_type                  = "cache.t4g.micro"
  num_cache_clusters         = 1
  port                       = 6379
  subnet_group_name          = aws_elasticache_subnet_group.main.name
  security_group_ids         = [aws_security_group.data.id]
  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
  automatic_failover_enabled = false
  snapshot_retention_limit   = 1
  apply_immediately          = false
}

resource "aws_mq_broker" "rabbitmq" {
  broker_name                = local.name
  engine_type                = "RABBITMQ"
  engine_version             = "3.13"
  host_instance_type         = "mq.t3.micro"
  deployment_mode            = "SINGLE_INSTANCE"
  publicly_accessible        = false
  auto_minor_version_upgrade = true
  security_groups            = [aws_security_group.data.id]
  subnet_ids                 = [aws_subnet.private[0].id]

  user {
    username = var.mq_username
    password = var.mq_password
  }

  logs {
    general = true
  }
}
