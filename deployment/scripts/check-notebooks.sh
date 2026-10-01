#!/usr/bin/env bash
#
# Rule 5 of the repository boundary rules (ADR-0026): no .ipynb under any code
# path, and no pipeline logic in a notebook anywhere. Exploratory notebooks, if
# any, live outside every code path.
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

code_paths=(platform ingestion streaming batch serving governance orchestration observability deployment tests)

found=""
for path in "${code_paths[@]}"; do
  [ -d "${path}" ] || continue
  hits="$(find "${path}" -name '*.ipynb' -not -path '*/.venv/*' -not -path '*/node_modules/*' 2>/dev/null || true)"
  if [ -n "${hits}" ]; then
    found="${found}${hits}"$'\n'
  fi
done

if [ -n "${found}" ]; then
  echo "::error::notebooks under a code path; pipeline logic lives in modules, not notebooks (ADR-0026 rule 5)" >&2
  printf '%s' "${found}" >&2
  exit 1
fi

echo "rule 5: no .ipynb under any code path"
