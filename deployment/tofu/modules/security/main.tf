# The node security group. It is the only ingress path to the RDS security
# group, so a pod reaches the metadata store through its node's group rather
# than through an open CIDR.
resource "aws_security_group" "nodes" {
  name        = "${var.name_prefix}-nodes"
  description = "EKS managed node groups"
  vpc_id      = var.vpc_id

  tags = merge(var.tags, { Name = "${var.name_prefix}-nodes" })
}

resource "aws_vpc_security_group_ingress_rule" "nodes_self" {
  security_group_id            = aws_security_group.nodes.id
  description                  = "Node and pod traffic within the node group"
  ip_protocol                  = "-1"
  referenced_security_group_id = aws_security_group.nodes.id
}

resource "aws_vpc_security_group_ingress_rule" "nodes_from_alb" {
  count = var.enable_alb ? 1 : 0

  security_group_id            = aws_security_group.nodes.id
  description                  = "The ALB's traffic to the pods"
  from_port                    = 1024
  to_port                      = 65535
  ip_protocol                  = "tcp"
  referenced_security_group_id = aws_security_group.alb[0].id
}

resource "aws_vpc_security_group_egress_rule" "nodes_all" {
  security_group_id = aws_security_group.nodes.id
  description       = "Egress to the S3 gateway endpoint, RDS and the internet"
  ip_protocol       = "-1"
  cidr_ipv4         = "0.0.0.0/0"
}

# The RDS security group: PostgreSQL from the node group and nothing else.
resource "aws_security_group" "rds" {
  name        = "${var.name_prefix}-rds"
  description = "The platform metadata store"
  vpc_id      = var.vpc_id

  tags = merge(var.tags, { Name = "${var.name_prefix}-rds" })
}

resource "aws_vpc_security_group_ingress_rule" "rds_from_nodes" {
  security_group_id            = aws_security_group.rds.id
  description                  = "PostgreSQL from the node group"
  from_port                    = 5432
  to_port                      = 5432
  ip_protocol                  = "tcp"
  referenced_security_group_id = aws_security_group.nodes.id
}

resource "aws_vpc_security_group_egress_rule" "rds_all" {
  security_group_id = aws_security_group.rds.id
  description       = "Egress for RDS-managed maintenance"
  ip_protocol       = "-1"
  cidr_ipv4         = "0.0.0.0/0"
}

# The reference arm's ALB security group, which the AWS Load Balancer Controller
# attaches to the ALB it provisions. Only the reference arm has an ALB, and the
# group is part of this module's security-groups area (#74); the requirement is
# docs/cloud-architecture.md section 2.4 and section 4.2.
resource "aws_security_group" "alb" {
  count = var.enable_alb ? 1 : 0

  name        = "${var.name_prefix}-alb"
  description = "The reference arm's application load balancer"
  vpc_id      = var.vpc_id

  tags = merge(var.tags, { Name = "${var.name_prefix}-alb" })
}

resource "aws_vpc_security_group_ingress_rule" "alb_https" {
  count = var.enable_alb ? 1 : 0

  security_group_id = aws_security_group.alb[0].id
  description       = "HTTPS from the internet"
  from_port         = 443
  to_port           = 443
  ip_protocol       = "tcp"
  cidr_ipv4         = "0.0.0.0/0"
}

resource "aws_vpc_security_group_egress_rule" "alb_to_nodes" {
  count = var.enable_alb ? 1 : 0

  security_group_id            = aws_security_group.alb[0].id
  description                  = "The ALB's traffic to the node group"
  ip_protocol                  = "-1"
  referenced_security_group_id = aws_security_group.nodes.id
}
