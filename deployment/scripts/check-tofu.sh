#!/usr/bin/env bash
#
# The deployment job: the OpenTofu static checks (docs/ci-cd-strategy.md
# section 4, docs/cloud-architecture.md section 7). It runs tofu fmt, tofu
# init -backend=false, tofu validate and tflint against both tfvars profiles,
# then the structural policy scan.
#
# No tofu plan and no apply runs anywhere in CI, and no LocalStack is used. The
# check greps the workflows for both at the end, so the absence is asserted
# rather than assumed. The static checks are the only evidence M19 can produce,
# so the gate is the deliverable (docs/cloud-architecture.md section 7).
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

tofu_dir="deployment/tofu"
profiles="minimal reference"

command -v tofu >/dev/null 2>&1 || { echo "::error::tofu is not installed" >&2; exit 1; }
command -v tflint >/dev/null 2>&1 || { echo "::error::tflint is not installed" >&2; exit 1; }

echo "== tofu fmt -check =="
tofu -chdir="${tofu_dir}" fmt -check -recursive

echo "== tofu init -backend=false (read-only lock file) =="
tofu -chdir="${tofu_dir}" init -backend=false -input=false -lockfile=readonly

echo "== tofu validate =="
for profile in ${profiles}; do
  echo "-- ${profile}"
  tofu -chdir="${tofu_dir}" validate -var-file="profiles/${profile}.tfvars"
done

echo "== tflint =="
(cd "${tofu_dir}" && tflint --init)
for profile in ${profiles}; do
  echo "-- ${profile}"
  (cd "${tofu_dir}" && tflint --var-file="profiles/${profile}.tfvars")
done

echo "== structural policy scan =="
uv run --frozen --package governance python deployment/scripts/check_tofu.py

echo "== no plan, no apply, no LocalStack in CI =="
if grep -RInE 'tofu[[:space:]]+(plan|apply)|terraform[[:space:]]+(plan|apply)|localstack' .github/workflows/; then
  echo "::error::CI must not plan, apply or use LocalStack" >&2
  exit 1
fi
echo "no plan, apply or LocalStack reference in .github/workflows"
