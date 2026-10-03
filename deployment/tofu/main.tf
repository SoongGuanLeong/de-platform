data "aws_availability_zones" "available" {
  state = "available"
}

# The VPC, its subnets and its S3 gateway endpoint (docs/cloud-architecture.md
# section 2.2).
module "network" {
  source = "./modules/network"

  name_prefix          = var.name_prefix
  region               = var.region
  vpc_cidr             = var.vpc_cidr
  azs                  = local.azs
  public_subnet_cidrs  = local.public_subnet_cidrs
  private_subnet_cidrs = local.private_subnet_cidrs
  enable_private       = var.enable_private_subnets
  tags                 = local.common_tags
}

# The S3 layout: one bucket per concern, each with its own CMK, public access
# blocked and a lifecycle policy (docs/cloud-architecture.md section 2.6).
module "storage" {
  source = "./modules/storage"

  name_prefix   = var.name_prefix
  buckets       = local.buckets
  capacity_gb   = var.bucket_capacity_gb
  enable_ecr    = var.enable_ecr
  ecr_repo_name = "de-platform/marquez"
  tags          = local.common_tags
}

# The security groups: nodes, RDS and, in the reference arm, the ALB.
module "security" {
  source = "./modules/security"

  name_prefix = var.name_prefix
  vpc_id      = module.network.vpc_id
  enable_alb  = var.enable_alb
  tags        = local.common_tags
}

# The platform metadata store: the instance class and a custom parameter group.
module "rds" {
  source = "./modules/rds"

  name_prefix          = var.name_prefix
  subnet_ids           = var.enable_private_subnets ? module.network.private_subnet_ids : module.network.public_subnet_ids
  security_group_ids   = [module.security.rds_security_group_id]
  instance_class       = var.rds_instance_class
  multi_az             = var.rds_multi_az
  allocated_storage_gb = var.rds_allocated_storage_gb
  engine_version       = var.rds_engine_version
  kms_key_arn          = module.storage.platform_kms_key_arn
  tags                 = local.common_tags
}

# Secrets handling: the Secrets Manager secrets and the CSI projection template
# (ADR-0028, docs/security-model.md section 2.6). No secret value is tracked.
module "secrets" {
  source = "./modules/secrets"

  name_prefix = var.name_prefix
  inventory   = local.secret_inv
  enabled     = var.enabled_secrets
  kms_key_arn = module.storage.platform_kms_key_arn
  region      = var.region
  tags        = local.common_tags
}

# IAM: the node role with no S3 or Secrets Manager permission, one IRSA role per
# component, and the vending role Polaris assumes (docs/cloud-architecture.md
# section 2.4 and 2.5).
module "iam" {
  source = "./modules/iam"

  name_prefix       = var.name_prefix
  oidc_provider_arn = var.cluster_oidc_provider_arn
  oidc_issuer_url   = var.cluster_oidc_issuer_url
  iam               = local.iam
  roles             = local.iam_roles
  tags              = local.common_tags
}
