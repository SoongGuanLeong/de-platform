# The node instance role. It carries no S3 and no Secrets Manager permission, so
# a compromised pod cannot borrow the node's identity and read the warehouse or
# a projected secret (docs/cloud-architecture.md section 2.4).
resource "aws_iam_role" "node" {
  name = "${var.name_prefix}-node"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = merge(var.tags, { Name = "${var.name_prefix}-node" })
}

resource "aws_iam_role_policy" "node" {
  name   = "${var.name_prefix}-node"
  role   = aws_iam_role.node.id
  policy = jsonencode(var.iam.node.policy)
}

resource "aws_iam_instance_profile" "node" {
  name = "${var.name_prefix}-node"
  role = aws_iam_role.node.name
}

# One IRSA role per component, each trusted only through the cluster's OIDC
# provider and only for its own service account.
resource "aws_iam_role" "component" {
  for_each = var.roles

  name = "${var.name_prefix}-${each.key}"

  assume_role_policy = templatefile("${path.module}/../../policies/trust-irsa.json.tmpl", {
    oidc_provider_arn = var.oidc_provider_arn
    oidc_issuer_url   = var.oidc_issuer_url
    namespace         = each.value.namespace
    service_account   = each.value.service_account
  })

  tags = merge(var.tags, { Name = "${var.name_prefix}-${each.key}", Component = each.key })
}

resource "aws_iam_role_policy" "component" {
  for_each = var.roles

  name   = "${var.name_prefix}-${each.key}"
  role   = aws_iam_role.component[each.key].id
  policy = jsonencode(each.value.policy)
}

# The vending role Polaris assumes to issue a prefix-scoped session credential.
# Its trust policy names Polaris's IRSA role as the only principal, tightening
# the local run's permissive trust policy (docs/cloud-architecture.md 2.5).
resource "aws_iam_role" "vending" {
  name = "${var.name_prefix}-${var.iam.vending.role_name}"

  assume_role_policy = templatefile("${path.module}/../../policies/trust-role.json.tmpl", {
    trusted_role_arn = aws_iam_role.component[var.iam.vending.assumed_by].arn
  })

  tags = merge(var.tags, { Name = "${var.name_prefix}-${var.iam.vending.role_name}" })
}

resource "aws_iam_role_policy" "vending" {
  name   = "${var.name_prefix}-${var.iam.vending.role_name}"
  role   = aws_iam_role.vending.id
  policy = jsonencode(var.iam.vending.policy)
}
