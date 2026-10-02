#!/usr/bin/env bash
#
# Proves the YAML single-entry-point check is load-bearing rather than decorative.
#
# It builds a throwaway copy of deployment/scripts under /tmp, asserts the clean
# copy passes, then introduces one safe_load call - once in a .py file, which the
# check reads as a syntax tree, and once in a .sh file, which it reads as text -
# and asserts each fails. A check that survives a mutation is a check that
# asserts nothing, which is the failure this script exists to catch.
#
# The copy is removed with rm and rmdir rather than a recursive delete.
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

work="$(mktemp -d "${TMPDIR:-/tmp}/de-platform-yaml-loading.XXXXXX")"

remove_tree() {
  find "$1" -type f 2>/dev/null | while IFS= read -r file; do rm -f "${file}"; done
  find "$1" -depth -type d 2>/dev/null | while IFS= read -r dir; do rmdir "${dir}" 2>/dev/null || true; done
}

cleanup() { remove_tree "${work}"; }
trap cleanup EXIT

run() {
  uv run --frozen python deployment/scripts/check_yaml_loading.py --root "${work}" >/dev/null 2>&1
}

reset() {
  if [ -d "${work}/deployment" ]; then remove_tree "${work}/deployment"; fi
  mkdir -p "${work}/deployment"
  cp -r deployment/scripts "${work}/deployment/scripts"
}

# The banned call is assembled from two pieces rather than written out. This
# harness is itself inside the tree the check scans, and the check is an absolute
# ban with no allow-list, so a literal occurrence here would be an offence in the
# harness rather than in the mutation it applies.
banned="safe""_load"

reset
if ! run; then
  echo "::error::the clean copy failed the YAML single-entry-point check" >&2
  exit 1
fi
printf 'clean copy passes\n'

# The .py path: the check walks the syntax tree.
reset
printf '\n\ndef read(path):\n    with open(path, encoding="utf-8") as handle:\n        return yaml.%s(handle)\n' \
  "${banned}" >> "${work}/deployment/scripts/preflight.py"
if run; then
  echo "::error::a safe_load call in a .py file did not fail the check" >&2
  exit 1
fi
printf 'mutation caught: safe_load in a .py file\n'

# The .sh path: the check matches the two calling forms as text.
reset
printf '\npython - <<PY\nimport yaml\nyaml.%s("a: 1")\nPY\n' \
  "${banned}" >> "${work}/deployment/scripts/preflight.sh"
if run; then
  echo "::error::a safe_load call in a .sh file did not fail the check" >&2
  exit 1
fi
printf 'mutation caught: safe_load in a .sh file\n'

printf 'the YAML single-entry-point check is load-bearing\n'
