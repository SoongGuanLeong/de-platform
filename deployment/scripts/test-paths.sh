#!/usr/bin/env bash
#
# Falsifiability evidence for the path-filter map (docs/ci-cd-strategy.md
# section 5). The `changes` job's outputs decide which jobs run, so a filter
# that is too narrow silently skips a check and one that is too broad pays for
# work that cannot fail.
#
# It runs the real deployment/scripts/paths.sh, unmodified, against a throwaway
# git repository: one commit per case, each adding a single path, and it asserts
# the whole key=value block the map emits for that diff. The fail-safe overrides
# are cases too: platform/ and contracts/ must select all five unit entries, and
# deployment/ must select observability.
#
# Usage: bash deployment/scripts/test-paths.sh
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"
paths_script="${PWD}/deployment/scripts/paths.sh"

tmp="$(mktemp -d)"
trap 'rm -rf "${tmp}"' EXIT

git -C "${tmp}" init -q
git -C "${tmp}" config user.email "paths-test@example.invalid"
git -C "${tmp}" config user.name "paths test"
git -C "${tmp}" commit -q --allow-empty -m base

failures=0
cases=0

# check <case> <path> <expected>
# Commits <path> as the only change in a new commit and compares the map's
# output for that single-file diff to <expected>.
check() {
  local name="$1" path="$2" expected="$3"
  mkdir -p "${tmp}/$(dirname "${path}")"
  : > "${tmp}/${path}"
  git -C "${tmp}" add -A
  git -C "${tmp}" commit -q -m "${name}"
  local actual
  actual="$(cd "${tmp}" && bash "${paths_script}" HEAD~1)"
  cases=$((cases + 1))
  if [ "${actual}" != "${expected}" ]; then
    failures=$((failures + 1))
    printf '::error::path filters: %s\n' "${name}" >&2
    diff <(printf '%s\n' "${expected}") <(printf '%s\n' "${actual}") >&2 || true
  fi
}

check "platform/ fans out to all five unit entries" "platform/core.py" \
'unit_platform=true
unit_ingestion=true
unit_batch=true
unit_governance=true
unit_orchestration=true
unit_any=true
unit_matrix=["platform","ingestion","batch","governance","orchestration"]
java=false
deployment=false
observability=false
images=false'

check "contracts/ fans out to all five and selects deployment" "contracts/commerce/orders.yml" \
'unit_platform=true
unit_ingestion=true
unit_batch=true
unit_governance=true
unit_orchestration=true
unit_any=true
unit_matrix=["platform","ingestion","batch","governance","orchestration"]
java=false
deployment=true
observability=false
images=false'

check "an Avro schema under contracts/<spine>/topics/ selects java" "contracts/commerce/topics/orders.avsc" \
'unit_platform=true
unit_ingestion=true
unit_batch=true
unit_governance=true
unit_orchestration=true
unit_any=true
unit_matrix=["platform","ingestion","batch","governance","orchestration"]
java=true
deployment=true
observability=false
images=false'

check "ingestion/ selects only its own unit entry" "ingestion/collector.py" \
'unit_platform=false
unit_ingestion=true
unit_batch=false
unit_governance=false
unit_orchestration=false
unit_any=true
unit_matrix=["ingestion"]
java=false
deployment=false
observability=false
images=false'

check "batch/ selects only its own unit entry" "batch/jobs.py" \
'unit_platform=false
unit_ingestion=false
unit_batch=true
unit_governance=false
unit_orchestration=false
unit_any=true
unit_matrix=["batch"]
java=false
deployment=false
observability=false
images=false'

check "governance/ selects only its own unit entry" "governance/validators.py" \
'unit_platform=false
unit_ingestion=false
unit_batch=false
unit_governance=true
unit_orchestration=false
unit_any=true
unit_matrix=["governance"]
java=false
deployment=false
observability=false
images=false'

check "orchestration/ selects only its own unit entry" "orchestration/assets.py" \
'unit_platform=false
unit_ingestion=false
unit_batch=false
unit_governance=false
unit_orchestration=true
unit_any=true
unit_matrix=["orchestration"]
java=false
deployment=false
observability=false
images=false'

check "streaming/ selects java and no unit entry" "streaming/jobs/Job.java" \
'unit_platform=false
unit_ingestion=false
unit_batch=false
unit_governance=false
unit_orchestration=false
unit_any=false
unit_matrix=[]
java=true
deployment=false
observability=false
images=false'

check "deployment/ fail-safe selects observability" "deployment/tofu/main.tf" \
'unit_platform=false
unit_ingestion=false
unit_batch=false
unit_governance=false
unit_orchestration=false
unit_any=false
unit_matrix=[]
java=false
deployment=true
observability=true
images=false'

check "the image context selects images, deployment and observability" "deployment/images/Dockerfile" \
'unit_platform=false
unit_ingestion=false
unit_batch=false
unit_governance=false
unit_orchestration=false
unit_any=false
unit_matrix=[]
java=false
deployment=true
observability=true
images=true'

check "observability/ selects only observability" "observability/rules.yml" \
'unit_platform=false
unit_ingestion=false
unit_batch=false
unit_governance=false
unit_orchestration=false
unit_any=false
unit_matrix=[]
java=false
deployment=false
observability=true
images=false'

check "an unrelated path selects nothing" "docs/note.md" \
'unit_platform=false
unit_ingestion=false
unit_batch=false
unit_governance=false
unit_orchestration=false
unit_any=false
unit_matrix=[]
java=false
deployment=false
observability=false
images=false'

# The default ref is HEAD~1 when none is given, so an invocation with no argument
# must agree with the explicit one.
explicit="$(cd "${tmp}" && bash "${paths_script}" HEAD~1)"
default="$(cd "${tmp}" && bash "${paths_script}")"
if [ "${explicit}" != "${default}" ]; then
  failures=$((failures + 1))
  printf '::error::path filters: the default ref (HEAD~1) disagrees with the explicit one\n' >&2
fi

if [ "${failures}" -ne 0 ]; then
  printf '::error::path filters: %d failure(s) across %d cases\n' "${failures}" "${cases}" >&2
  exit 1
fi
echo "path filters: ${cases} cases, every job's selection as declared"
