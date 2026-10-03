resource "aws_db_subnet_group" "this" {
  name       = "${var.name_prefix}-rds"
  subnet_ids = var.subnet_ids

  tags = merge(var.tags, { Name = "${var.name_prefix}-rds" })
}

# A custom parameter group rather than the engine default, so the platform's
# settings are reviewable as a diff.
resource "aws_db_parameter_group" "this" {
  name   = "${var.name_prefix}-postgres${var.engine_version}"
  family = "postgres${var.engine_version}"

  parameter {
    name  = "rds.force_ssl"
    value = "1"
  }

  parameter {
    name  = "log_statement"
    value = "ddl"
  }

  parameter {
    name  = "log_min_duration_statement"
    value = "1000"
  }

  tags = merge(var.tags, { Name = "${var.name_prefix}-postgres${var.engine_version}" })
}

resource "aws_db_instance" "this" {
  identifier = "${var.name_prefix}-metadata"

  engine         = "postgres"
  engine_version = var.engine_version
  instance_class = var.instance_class

  allocated_storage = var.allocated_storage_gb
  storage_type      = "gp3"
  storage_encrypted = true
  kms_key_id        = var.kms_key_arn

  multi_az = var.multi_az

  db_subnet_group_name   = aws_db_subnet_group.this.name
  parameter_group_name   = aws_db_parameter_group.this.name
  vpc_security_group_ids = var.security_group_ids

  publicly_accessible = false

  backup_retention_period = 7

  # The master credential is managed by RDS and never written to a tracked file
  # (ADR-0028). The per-component database users are separate Secrets Manager
  # values, created by the secrets module.
  username                      = "dbadmin"
  manage_master_user_password   = true
  master_user_secret_kms_key_id = var.kms_key_arn

  # The demo window is torn down rather than left running, so no final snapshot
  # and no deletion protection (docs/cloud-architecture.md section 4.3).
  skip_final_snapshot = true
  deletion_protection = false
  apply_immediately   = true

  tags = merge(var.tags, { Name = "${var.name_prefix}-metadata" })
}
