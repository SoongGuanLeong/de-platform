output "vpc_id" {
  description = "The arm's VPC id."
  value       = aws_vpc.this.id
}

output "public_subnet_ids" {
  description = "The public subnet ids, one per Availability Zone."
  value       = aws_subnet.public[*].id
}

output "private_subnet_ids" {
  description = "The private subnet ids, one per Availability Zone; empty in the minimal arm."
  value       = aws_subnet.private[*].id
}

output "s3_endpoint_id" {
  description = "The S3 gateway endpoint id."
  value       = aws_vpc_endpoint.s3.id
}
