# No secret value is created here: a value is never a tracked artefact
# (ADR-0028). The demo runbook sets each value at run time, and the rotation
# class is declared in the inventory so rotation is a property of the component.
resource "aws_secretsmanager_secret" "this" {
  for_each = toset(var.enabled)

  name                    = "${var.name_prefix}/${each.value}"
  kms_key_id              = var.kms_key_arn
  recovery_window_in_days = 0

  tags = merge(var.tags, {
    Name          = "${var.name_prefix}/${each.value}"
    RotationClass = var.inventory[each.value].rotation_class
  })
}

# TLS-only access, so a client cannot read a value in the clear.
resource "aws_secretsmanager_secret_policy" "this" {
  for_each = toset(var.enabled)

  secret_arn = aws_secretsmanager_secret.this[each.value].arn
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "DenyNonTls"
      Effect    = "Deny"
      Principal = "*"
      Action    = "secretsmanager:*"
      Resource  = "*"
      Condition = { Bool = { "aws:SecureTransport" = "false" } }
    }]
  })
}

locals {
  projection_objects = join("\n", [
    for name in var.enabled :
    "      - objectName: \"${name}\"\n        objectType: \"secretsmanager\""
  ])
}
