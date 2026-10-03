# The reference arm: 3 AZs, private subnets with one NAT gateway per AZ, a
# Multi-AZ metadata instance, five secrets, an ALB and the authored-but-unused
# ECR repository (docs/cloud-architecture.md section 2, ADR-0034).
arm                      = "reference"
vpc_cidr                 = "10.1.0.0/16"
az_count                 = 3
enable_private_subnets   = true
rds_instance_class       = "db.t4g.micro"
rds_multi_az             = true
rds_allocated_storage_gb = 50
bucket_capacity_gb       = 500
enabled_secrets          = ["polaris-db", "kafka-tls", "flink-keystore", "clickhouse", "dagster-db"]
enable_alb               = true
enable_ecr               = true
