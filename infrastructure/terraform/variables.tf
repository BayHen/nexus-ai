variable "aws_region" {
  description = "AWS region for the staging environment."
  type        = string
  default     = "ap-southeast-1"
}

variable "project_name" {
  description = "Short resource-name prefix."
  type        = string
  default     = "nexus-ai"
}

variable "environment" {
  description = "Deployment environment."
  type        = string
  default     = "staging"

  validation {
    condition     = contains(["staging"], var.environment)
    error_message = "This root module is intentionally limited to staging."
  }
}

variable "vpc_cidr" {
  description = "CIDR allocated to the staging VPC."
  type        = string
  default     = "10.42.0.0/16"
}

variable "backend_image" {
  description = "Immutable backend ECR image URI, preferably pinned by git SHA."
  type        = string
}

variable "frontend_image" {
  description = "Immutable frontend ECR image URI, preferably pinned by git SHA."
  type        = string
}

variable "application_secret_arn" {
  description = "Existing Secrets Manager JSON secret with application runtime values."
  type        = string
  sensitive   = true
}

variable "certificate_arn" {
  description = "ACM certificate ARN for the staging HTTPS listener."
  type        = string
}

variable "staging_base_url" {
  description = "Public HTTPS origin whose DNS record points to the ALB."
  type        = string

  validation {
    condition     = startswith(var.staging_base_url, "https://")
    error_message = "staging_base_url must use HTTPS."
  }
}

variable "db_password" {
  description = "Staging database password supplied through TF_VAR_db_password; stored in encrypted remote state."
  type        = string
  sensitive   = true
}

variable "mq_username" {
  description = "RabbitMQ application username."
  type        = string
  sensitive   = true
}

variable "mq_password" {
  description = "RabbitMQ password supplied through TF_VAR_mq_password; stored in encrypted remote state."
  type        = string
  sensitive   = true
}

variable "deletion_protection" {
  description = "Protect stateful resources from accidental deletion. Enable after initial staging validation."
  type        = bool
  default     = false
}

variable "backend_desired_count" {
  type    = number
  default = 1
}

variable "frontend_desired_count" {
  type    = number
  default = 1
}

variable "worker_desired_count" {
  type    = number
  default = 1
}
