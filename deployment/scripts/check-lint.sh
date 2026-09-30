#!/usr/bin/env bash
#
# The lint job (docs/ci-cd-strategy.md section 4): sqlfluff, yamllint and
# actionlint.
#
# yamllint's scope is the compose files under deployment/ and the contract files
# under contracts/, which is the scope docs/ci-cd-strategy.md gives it. The
# budget registers (docs/budgets.yaml, deployment/budgets/profiles.yaml) are not
# compose files and are read by their own validators instead.
#
# sqlfluff has no SQL to read until the serving DDL lands (issue #37), so it is
# deferred here rather than added as a dependency before it has a subject.
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

echo "== yamllint: compose files and contracts =="
mapfile -d '' files < <(find deployment contracts -type f \
  \( -name 'compose*.y*ml' -o -name 'docker-compose*.y*ml' -o -name '*.yml' -o -name '*.yaml' \) \
  -not -path 'deployment/budgets/*' -not -path 'deployment/security-harness/profiles/*' -print0 2>/dev/null)
if [ "${files[@]:-}" != "" ] && [ "${#files[@]}" -gt 0 ]; then
  uv run --frozen yamllint --strict "${files[@]}"
else
  echo "::notice::no compose or contract YAML yet; yamllint had nothing to read"
fi

echo "== actionlint =="
uv run --frozen actionlint

echo "== sqlfluff =="
if find serving contracts -name '*.sql' -print -quit 2>/dev/null | grep -q .; then
  echo "::error::SQL exists but the sqlfluff check is not implemented yet (issue #37)" >&2
  exit 1
fi
echo "::notice::no .sql files yet; sqlfluff check deferred to issue #37"
