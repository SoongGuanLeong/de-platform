# One CMK per bucket, because lifecycle, versioning and IAM policy differ per
# concern (docs/cloud-architecture.md section 2.6).
resource "aws_kms_key" "bucket" {
  for_each = var.buckets

  description             = "CMK for the ${var.name_prefix}-${each.value.suffix} bucket"
  deletion_window_in_days = 7
  enable_key_rotation     = true

  tags = merge(var.tags, { Name = "${var.name_prefix}-${each.value.suffix}" })
}

resource "aws_kms_alias" "bucket" {
  for_each = var.buckets

  name          = "alias/${var.name_prefix}-${each.value.suffix}"
  target_key_id = aws_kms_key.bucket[each.key].key_id
}

resource "aws_s3_bucket" "this" {
  for_each = var.buckets

  bucket = "${var.name_prefix}-${each.value.suffix}"
  tags = merge(var.tags, {
    Name               = "${var.name_prefix}-${each.value.suffix}"
    DeclaredCapacityGb = tostring(var.capacity_gb)
  })
}

resource "aws_s3_bucket_versioning" "this" {
  for_each = var.buckets

  bucket = aws_s3_bucket.this[each.key].id
  versioning_configuration {
    status = each.value.versioned ? "Enabled" : "Suspended"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "this" {
  for_each = var.buckets

  bucket = aws_s3_bucket.this[each.key].id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.bucket[each.key].arn
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "this" {
  for_each = var.buckets

  bucket                  = aws_s3_bucket.this[each.key].id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "this" {
  for_each = var.buckets

  bucket = aws_s3_bucket.this[each.key].id

  rule {
    id     = "abort-incomplete-and-expire-noncurrent"
    status = "Enabled"
    filter {}

    dynamic "expiration" {
      for_each = each.value.expiration_days > 0 ? [each.value.expiration_days] : []
      content {
        days = expiration.value
      }
    }

    noncurrent_version_expiration {
      noncurrent_days = 30
    }

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}

# Authored and never used. ADR-0034 keeps this resource in the reference arm as
# the documented production target; no run pulls from it, and the minimal profile
# does not declare it. It is not one of #74's six module areas, but it stays
# because ADR-0034 decides it: removing it would overturn that accepted decision.
resource "aws_ecr_repository" "marquez" {
  count = var.enable_ecr ? 1 : 0

  name                 = var.ecr_repo_name
  image_tag_mutability = "IMMUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "KMS"
  }

  tags = merge(var.tags, { Name = var.ecr_repo_name })
}
