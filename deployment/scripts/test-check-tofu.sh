#!/usr/bin/env bash
#
# Proves the OpenTofu structural policy scan is load-bearing rather than
# decorative. It builds a throwaway root containing the deployment tree and the
# workflow, asserts the clean tree passes, then mutates one thing at a time and
# asserts each mutation fails. A scan that survives every mutation asserts
# nothing, which is the failure this script exists to catch.
#
# The copy is removed with rm and rmdir rather than a recursive delete.
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

work="$(mktemp -d "${TMPDIR:-/tmp}/de-platform-tofu-scan.XXXXXX")"

remove_tree() {
  find "$1" -type f 2>/dev/null | while IFS= read -r file; do rm -f "${file}"; done
  find "$1" -depth -type d 2>/dev/null | while IFS= read -r dir; do rmdir "${dir}" 2>/dev/null || true; done
}

cleanup() { remove_tree "${work}"; }
trap cleanup EXIT

mkdir -p "${work}/deployment/scripts" "${work}/.github/workflows"
cp -r deployment/tofu "${work}/deployment/tofu"
cp deployment/scripts/check-tofu.sh "${work}/deployment/scripts/check-tofu.sh"
cp .github/workflows/ci.yml "${work}/.github/workflows/ci.yml"

run() {
  uv run --frozen --package governance python deployment/scripts/check_tofu.py --root "${work}" >/dev/null 2>&1
}

expect_pass() {
  if ! run; then
    echo "::error::the clean tree failed the tofu policy scan" >&2
    exit 1
  fi
}

restore() {
  remove_tree "${work}/deployment/tofu"
  cp -r deployment/tofu "${work}/deployment/tofu"
  cp .github/workflows/ci.yml "${work}/.github/workflows/ci.yml"
}

expect_fail() {
  if run; then
    echo "::error::$1 was mutated and the scan still passed" >&2
    exit 1
  fi
  printf 'mutation caught: %s\n' "$1"
  restore
}

expect_pass
printf 'clean tree passes\n'

# 1. The node role gains an S3 action.
python3 - "${work}/deployment/tofu/policies/iam.json" <<'PY'
import json, sys
path = sys.argv[1]
doc = json.load(open(path))
doc["node"]["policy"]["Statement"][0]["Action"].append("s3:GetObject")
json.dump(doc, open(path, "w"), indent=2)
PY
expect_fail "a node role with an S3 action"

# 2. The node role gains a Secrets Manager action.
python3 - "${work}/deployment/tofu/policies/iam.json" <<'PY'
import json, sys
path = sys.argv[1]
doc = json.load(open(path))
doc["node"]["policy"]["Statement"][0]["Action"].append("secretsmanager:GetSecretValue")
json.dump(doc, open(path, "w"), indent=2)
PY
expect_fail "a node role with a Secrets Manager action"

# 3. A component loses its service account.
python3 - "${work}/deployment/tofu/policies/iam.json" <<'PY'
import json, sys
path = sys.argv[1]
doc = json.load(open(path))
doc["components"]["polaris"]["service_account"] = ""
json.dump(doc, open(path, "w"), indent=2)
PY
expect_fail "a component with no service account"

# 4. A component policy gains a service wildcard.
python3 - "${work}/deployment/tofu/policies/iam.json" <<'PY'
import json, sys
path = sys.argv[1]
doc = json.load(open(path))
doc["components"]["polaris"]["policy"]["Statement"][0]["Action"].append("s3:*")
json.dump(doc, open(path, "w"), indent=2)
PY
expect_fail "a component policy with s3:*"

# 5. The IRSA trust condition loses its per-service-account scope.
python3 - "${work}/deployment/tofu/policies/trust-irsa.json.tmpl" <<'PY'
import sys
path = sys.argv[1]
text = open(path).read()
open(path, "w").write(text.replace(
    '"system:serviceaccount:${namespace}:${service_account}"', '"*"'))
PY
expect_fail "an IRSA trust policy with no sub scope"

# 6. The vending role's trust principal becomes a wildcard.
python3 - "${work}/deployment/tofu/policies/trust-role.json.tmpl" <<'PY'
import sys
path = sys.argv[1]
text = open(path).read()
open(path, "w").write(text.replace('"${trusted_role_arn}"', '"*"'))
PY
expect_fail "a vending trust policy with a wildcard principal"

# 7. The vending role's warehouse scope is widened.
python3 - "${work}/deployment/tofu/policies/iam.json" <<'PY'
import json, sys
path = sys.argv[1]
doc = json.load(open(path))
doc["vending"]["policy"]["Statement"][0]["Resource"] = ["arn:aws:s3:::de-platform-lake/*"]
json.dump(doc, open(path, "w"), indent=2)
PY
expect_fail "a vending role scoped to the whole bucket"

# 8. The secret projection's filePermission becomes the driver default.
python3 - "${work}/deployment/tofu/secrets/secret-projection.yaml.tmpl" <<'PY'
import sys
path = sys.argv[1]
text = open(path).read()
open(path, "w").write(text.replace('filePermission: "0400"', 'filePermission: "0644"'))
PY
expect_fail "a secret projection with the 0644 default"

# 9. A secret loses its rotation class.
python3 - "${work}/deployment/tofu/policies/secrets.json" <<'PY'
import json, sys
path = sys.argv[1]
doc = json.load(open(path))
del doc["polaris-db"]["rotation_class"]
json.dump(doc, open(path, "w"), indent=2)
PY
expect_fail "a secret with no rotation class"

# 10. The minimal profile gains private subnets.
python3 - "${work}/deployment/tofu/profiles/minimal.tfvars" <<'PY'
import sys
path = sys.argv[1]
text = open(path).read()
open(path, "w").write(text.replace("enable_private_subnets   = false", "enable_private_subnets   = true"))
PY
expect_fail "a minimal arm with private subnets"

# 11. The HCL stops consuming the IAM data.
python3 - "${work}/deployment/tofu/locals.tf" <<'PY'
import sys
path = sys.argv[1]
text = open(path).read()
open(path, "w").write(text.replace("policies/iam.json", "policies/iam-renamed.json"))
PY
expect_fail "HCL that no longer consumes iam.json"

# 12. The arm filter is removed, so a reference-only role leaks into minimal.
python3 - "${work}/deployment/tofu/locals.tf" <<'PY'
import sys
path = sys.argv[1]
text = open(path).read()
open(path, "w").write(text.replace("if contains(role.arms, var.arm)", "if true"))
PY
expect_fail "no arm filter on the component roles"

# 13. CI reverts to the stub.
python3 - "${work}/.github/workflows/ci.yml" <<'PY'
import sys
path = sys.argv[1]
text = open(path).read()
text = text.replace("bash deployment/scripts/check-tofu.sh", "bash deployment/scripts/check-stub.sh deployment 74")
open(path, "w").write(text)
PY
expect_fail "CI back on the deployment stub"

printf 'the OpenTofu policy scan is load-bearing\n'
