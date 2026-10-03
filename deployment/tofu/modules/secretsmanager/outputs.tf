# The declared cloud projection: Secrets Manager values through the Secrets
# Store CSI driver, filePermission 0400 (docs/security-model.md section 2.6).
# The Helm chart that mounts it is issue #75.
output "secret_projection_manifest" {
  description = "The SecretProviderClass and its pod volume, rendered for this arm."
  value = templatefile("${path.module}/../../templates/secret-projection.yaml.tmpl", {
    name_prefix = var.name_prefix
    namespace   = "platform"
    region      = var.region
    objects     = local.projection_objects
  })
}

output "secret_arns" {
  description = "The secret ARN per inventory name."
  value       = { for k, s in aws_secretsmanager_secret.this : k => s.arn }
}

output "secret_names" {
  description = "The secret name per inventory name."
  value       = { for k, s in aws_secretsmanager_secret.this : k => s.name }
}
