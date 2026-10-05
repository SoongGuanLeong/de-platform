output "endpoint" {
  description = "The instance endpoint."
  value       = aws_db_instance.this.endpoint
}

output "identifier" {
  description = "The instance identifier."
  value       = aws_db_instance.this.identifier
}

output "parameter_group_name" {
  description = "The custom parameter group name."
  value       = aws_db_parameter_group.this.name
}
