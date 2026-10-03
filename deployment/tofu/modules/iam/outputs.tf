output "node_role_arn" {
  description = "The node instance role ARN."
  value       = aws_iam_role.node.arn
}

output "node_instance_profile_name" {
  description = "The node instance profile name."
  value       = aws_iam_instance_profile.node.name
}

output "component_role_arns" {
  description = "One IRSA role ARN per component."
  value       = { for k, r in aws_iam_role.component : k => r.arn }
}

output "vending_role_arn" {
  description = "The role Polaris assumes to vend a prefix-scoped credential."
  value       = aws_iam_role.vending.arn
}
