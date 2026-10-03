output "node_security_group_id" {
  description = "The node group security group id."
  value       = aws_security_group.nodes.id
}

output "rds_security_group_id" {
  description = "The RDS security group id."
  value       = aws_security_group.rds.id
}

output "alb_security_group_id" {
  description = "The ALB security group id, empty in the minimal arm."
  value       = var.enable_alb ? aws_security_group.alb[0].id : ""
}
