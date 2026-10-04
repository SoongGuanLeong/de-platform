# The OpenTofu and provider pins (ADR-0005, docs/cloud-architecture.md section 7).
#
# OpenTofu 1.12.0 is the pinned CLI in the technology table, so the floor is the
# pinned version rather than the newest release. The AWS provider is pinned to a
# minor line and the exact resolved version is recorded in the committed
# .terraform.lock.hcl, which is what makes the tree reproducible.
terraform {
  required_version = ">= 1.12.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.67"
    }
  }

  # Authored, never initialised against a real backend in CI: every check runs
  # `tofu init -backend=false`. A real run needs the state bucket first, and the
  # backend cannot read a resource it is about to create, so the demo operator
  # bootstraps it out of band:
  #
  #   1. Create the bucket the backend names, before `tofu init`:
  #        aws s3api create-bucket --bucket de-platform-platform \
  #          --region ap-southeast-5 \
  #          --create-bucket-configuration LocationConstraint=ap-southeast-5
  #   2. Initialise against the real backend:
  #        tofu -chdir=deployment/tofu init
  #   3. Adopt the bucket the storage module also declares, before the first
  #      apply, so the module does not try to create it again:
  #        tofu -chdir=deployment/tofu import \
  #          -var-file=profiles/minimal.tfvars \
  #          'module.storage.aws_s3_bucket.this["platform"]' de-platform-platform
  #
  # No cloud arm is ever applied outside a priced demo window (ADR-0033).
  backend "s3" {
    bucket       = "de-platform-platform"
    key          = "tofu/platform.tfstate"
    region       = "ap-southeast-5"
    encrypt      = true
    use_lockfile = true
  }
}
