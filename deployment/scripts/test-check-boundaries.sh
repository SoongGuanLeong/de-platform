#!/usr/bin/env bash
#
# Falsifiability evidence for the boundary gate: a deliberate cross-path import
# must fail the build. The check proves the .importlinter contracts are
# load-bearing rather than decorative.
#
# It runs the real config on the clean tree and asserts it passes, then injects a
# cross-path import into a real module, asserts lint-imports fails, and restores
# the file. The trap restores the file even if the script aborts.
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

target="batch/src/de_batch/__init__.py"
backup="$(mktemp)"
cp "${target}" "${backup}"
trap 'cp "${backup}" "${target}"; rm -f "${backup}"' EXIT

echo "== the clean tree passes =="
uv run --frozen lint-imports --config .importlinter >/dev/null
echo "clean tree: import-linter passed"

echo "== a deliberate cross-path import fails =="
printf '\nimport de_ingestion.commerce  # deliberate rule-2 violation for this test\n' >> "${target}"
if uv run --frozen lint-imports --config .importlinter >/dev/null 2>&1; then
  echo "::error::import-linter passed with a cross-path import in ${target}" >&2
  exit 1
fi
echo "cross-path import: import-linter failed as required"
