# The minimal arm: 2 AZs, public subnets only, no NAT, one metadata instance,
# one secret, no ALB and no ECR (docs/cloud-architecture.md section 2).
arm                      = "minimal"
vpc_cidr                 = "10.0.0.0/16"
az_count                 = 2
enable_private_subnets   = false
rds_instance_class       = "db.t4g.micro"
rds_multi_az             = false
rds_allocated_storage_gb = 20
bucket_capacity_gb       = 100
enabled_secrets          = ["polaris-db"]
enable_alb               = false
enable_ecr               = false
