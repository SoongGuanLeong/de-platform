variable "region" {
  description = "The AWS region both arms are modelled in."
  type        = string
  default     = "ap-southeast-5"
}

variable "arm" {
  description = "Which arm this profile renders: minimal or reference."
  type        = string
  default     = "minimal"

  validation {
    condition     = contains(["minimal", "reference"], var.arm)
    error_message = "arm must be one of: minimal, reference."
  }
}

variable "name_prefix" {
  description = "Prefix for every named resource and every bucket."
  type        = string
  default     = "de-platform"
}

variable "account_id" {
  description = "The AWS account id, substituted into the policy ARNs."
  type        = string
  default     = "000000000000"
}

variable "vpc_cidr" {
  description = "The arm's VPC CIDR: 10.0.0.0/16 minimal, 10.1.0.0/16 reference."
  type        = string
  default     = "10.0.0.0/16"
}

variable "az_count" {
  description = "Availability Zones the arm spans: the EKS floor of 2 minimal, 3 reference."
  type        = number
  default     = 2
}

variable "enable_private_subnets" {
  description = "Whether the arm has private subnets and one NAT gateway per AZ (reference only)."
  type        = bool
  default     = false
}

variable "cluster_oidc_provider_arn" {
  description = "The EKS cluster's IAM OIDC provider ARN, the Federated principal every IRSA trust policy names. The cluster is a prerequisite authored outside this ticket."
  type        = string
  default     = "arn:aws:iam::000000000000:oidc-provider/oidc.eks.ap-southeast-5.amazonaws.com/id/EXAMPLE"
}

variable "cluster_oidc_issuer_url" {
  description = "The EKS cluster's OIDC issuer URL, the condition key prefix for every IRSA trust policy."
  type        = string
  default     = "oidc.eks.ap-southeast-5.amazonaws.com/id/EXAMPLE"
}

variable "rds_instance_class" {
  description = "The RDS instance class. db.t4g.micro is free-plan eligible and is the arm's floor."
  type        = string
  default     = "db.t4g.micro"
}

variable "rds_multi_az" {
  description = "Whether RDS runs Multi-AZ (reference arm only)."
  type        = bool
  default     = false
}

variable "rds_allocated_storage_gb" {
  description = "RDS gp3 storage in GB."
  type        = number
  default     = 20
}

variable "rds_engine_version" {
  description = "PostgreSQL engine version, the 18.x line."
  type        = string
  default     = "18"
}

variable "bucket_capacity_gb" {
  description = "The arm's declared S3 budget in GB, carried as a tag on every bucket."
  type        = number
  default     = 100
}

variable "enabled_secrets" {
  description = "The secrets the arm creates in AWS Secrets Manager. Values are never tracked (ADR-0028)."
  type        = list(string)
  default     = ["polaris-db"]
}

variable "enable_alb" {
  description = "Whether the reference arm's ALB security group exists."
  type        = bool
  default     = false
}

variable "enable_ecr" {
  description = "Whether the authored-but-unused ECR repository exists (reference arm only, ADR-0034)."
  type        = bool
  default     = false
}
