#!/usr/bin/env bash
#
# The path filter map for the CI changes job (docs/ci-cd-strategy.md section 5).
#
# It prints one key=value line per filter on stdout, which the workflow appends
# to $GITHUB_OUTPUT. The map lives here rather than in nested workflow YAML so a
# filter change is reviewable as a diff.
#
# A job's filter includes every shared artefact that job really consumes, so a
# change to a shared artefact can never skip a check it invalidates.
#
# Usage: paths.sh [<base-ref>]
#   <base-ref>  the ref to compare against; the merge base of HEAD and this ref
#               is used, so a pull request is judged on the change it introduces
#               rather than on everything the base branch gained. In CI this is
#               the pull request's base SHA. On a push it defaults to HEAD~1, or
#               to the empty tree when there is no parent commit.
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

ref="${1:-}"
if [ -z "${ref}" ]; then
  if git rev-parse --verify --quiet HEAD~1 >/dev/null 2>&1; then
    ref="HEAD~1"
  else
    ref="$(git hash-object -t tree /dev/null)"
  fi
fi

if ! base="$(git merge-base HEAD "${ref}" 2>/dev/null)"; then
  base="${ref}"
fi

if ! changed="$(git diff --name-only "${base}" HEAD 2>/dev/null)"; then
  echo "paths.sh: cannot diff against '${base}'" >&2
  exit 1
fi

has() {
  printf '%s\n' "${changed}" | grep -Eq "$1"
}

# unit: the changed distribution's own path; platform/ or contracts/ runs all five.
unit_platform=false
unit_ingestion=false
unit_batch=false
unit_governance=false
unit_orchestration=false
if has '^platform/' || has '^contracts/'; then
  unit_platform=true
  unit_ingestion=true
  unit_batch=true
  unit_governance=true
  unit_orchestration=true
else
  if has '^ingestion/'; then unit_ingestion=true; fi
  if has '^batch/'; then unit_batch=true; fi
  if has '^governance/'; then unit_governance=true; fi
  if has '^orchestration/'; then unit_orchestration=true; fi
fi

unit_any=false
unit_matrix="[]"
items=""
for dist in platform ingestion batch governance orchestration; do
  eval "value=\${unit_${dist}}"
  if [ "${value}" = true ]; then
    unit_any=true
    items="${items}\"${dist}\","
  fi
done
if [ "${unit_any}" = true ]; then
  unit_matrix="[${items%,}]"
fi

# java: streaming/ and the Avro schema files.
java=false
if has '^streaming/' || has '^contracts/[^/]+/topics/'; then java=true; fi

# deployment: deployment/, with contracts/ as the fail-safe override.
deployment=false
if has '^deployment/' || has '^contracts/'; then deployment=true; fi

# observability: observability/, with deployment/ as the fail-safe override.
observability=false
if has '^observability/' || has '^deployment/'; then observability=true; fi

# images: the image context under deployment/.
images=false
if has '^deployment/images/'; then images=true; fi

cat <<EOF
unit_platform=${unit_platform}
unit_ingestion=${unit_ingestion}
unit_batch=${unit_batch}
unit_governance=${unit_governance}
unit_orchestration=${unit_orchestration}
unit_any=${unit_any}
unit_matrix=${unit_matrix}
java=${java}
deployment=${deployment}
observability=${observability}
images=${images}
EOF
