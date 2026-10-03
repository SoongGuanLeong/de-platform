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
  # `tofu init -backend=false`. The state bucket is the -platform bucket the
  # storage module authors, bootstrapped out of band because a backend block
  # cannot read a resource it is about to create. No cloud arm is ever applied
  # outside a priced demo window (ADR-0033).
  backend "s3" {
    bucket       = "de-platform-platform"
    key          = "tofu/platform.tfstate"
    region       = "ap-southeast-5"
    encrypt      = true
    use_lockfile = true
  }
}
