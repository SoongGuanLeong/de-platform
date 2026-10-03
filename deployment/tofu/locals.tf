locals {
  azs = slice(data.aws_availability_zones.available.names, 0, var.az_count)

  common_tags = {
    Project   = "de-platform"
    Arm       = var.arm
    ManagedBy = "opentofu"
  }

  # Public subnets are /24s carved from the low half of the VPC; private subnets
  # are /20s from the high half. The minimal arm's /24s are sized against the
  # ENI and secondary-IP ceiling with a /22 as the documented fallback, and the
  # reference arm's /20s are headroom (docs/cloud-architecture.md section 2.2).
  public_subnet_cidrs  = [for i in range(var.az_count) : cidrsubnet(var.vpc_cidr, 8, i)]
  private_subnet_cidrs = [for i in range(var.az_count) : cidrsubnet(var.vpc_cidr, 4, i + 8)]

  # Bucket per concern, because lifecycle, versioning and IAM policy differ per
  # concern (docs/cloud-architecture.md section 2.6).
  buckets = {
    lake = {
      suffix          = "lake"
      versioned       = true
      expiration_days = 0
    }
    flink = {
      suffix          = "flink"
      versioned       = false
      expiration_days = 30
    }
    kafka = {
      suffix          = "kafka"
      versioned       = false
      expiration_days = 7
    }
    platform = {
      suffix          = "platform"
      versioned       = true
      expiration_days = 0
    }
  }

  # The role topology is expressed as data, so the boundary is reviewable as a
  # diff (docs/cloud-architecture.md section 2.4). The account, region and name
  # prefix are substituted into the policy ARNs here, so the documents carry no
  # environment literal. The arm filter is applied too: the load balancer
  # controller is authored for the reference arm only.
  iam = jsondecode(
    replace(
      replace(
        replace(file("${path.module}/policies/iam.json"), "$${ACCOUNT_ID}", var.account_id),
        "$${REGION}", var.region
      ),
      "$${NAME_PREFIX}", var.name_prefix
    )
  )
  iam_roles  = { for name, role in local.iam.components : name => role if contains(role.arms, var.arm) }
  secret_inv = jsondecode(file("${path.module}/policies/secrets.json"))
}
