output "bucket_names" {
  description = "The bucket name per concern."
  value       = { for k, b in aws_s3_bucket.this : k => b.bucket }
}

output "bucket_arns" {
  description = "The bucket ARN per concern."
  value       = { for k, b in aws_s3_bucket.this : k => b.arn }
}

output "platform_kms_key_arn" {
  description = "The CMK for the -platform bucket, used for secrets and RDS."
  value       = aws_kms_key.bucket["platform"].arn
}

output "ecr_repository_url" {
  description = "The ECR repository URL, empty in the minimal arm."
  value       = var.enable_ecr ? aws_ecr_repository.marquez[0].repository_url : ""
}
