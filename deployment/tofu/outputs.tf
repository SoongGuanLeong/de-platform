output "vpc_id" {
  description = "The arm's VPC id."
  value       = module.network.vpc_id
}

output "bucket_names" {
  description = "The S3 buckets, one per concern."
  value       = module.storage.bucket_names
}

output "rds_endpoint" {
  description = "The RDS instance endpoint."
  value       = module.rds.endpoint
}

output "secret_names" {
  description = "The Secrets Manager secrets the arm creates."
  value       = module.secretsmanager.secret_names
}

output "component_role_arns" {
  description = "One IRSA role ARN per component, the arm's role topology."
  value       = module.iam.component_role_arns
}

output "node_role_arn" {
  description = "The node instance role, which carries no S3 or Secrets Manager permission."
  value       = module.iam.node_role_arn
}
