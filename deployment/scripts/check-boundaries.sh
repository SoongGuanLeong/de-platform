#!/usr/bin/env bash
#
# The boundaries job (docs/ci-cd-strategy.md section 4): ruff, the packaging
# graph, import-linter rules 1 to 4, and rule 5 (the notebook path check).
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

echo "== ruff check =="
uv run --frozen ruff check .
echo "== ruff format --check =="
uv run --frozen ruff format --check .
echo "== packaging graph =="
uv run --frozen python deployment/scripts/check_packaging_graph.py
echo "== import-linter rules 1 to 4 =="
uv run --frozen --all-packages lint-imports --config .importlinter
echo "== rule 5: no notebooks under a code path =="
bash deployment/scripts/check-notebooks.sh
