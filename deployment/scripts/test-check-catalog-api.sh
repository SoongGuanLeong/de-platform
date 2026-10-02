#!/usr/bin/env bash
#
# Proves the catalog-API boundary check is load-bearing rather than decorative.
#
# It builds a throwaway copy of platform/src under /tmp, asserts the clean copy
# passes, then adds a Polaris Management API path in three forms - a single
# literal, a literal concatenation, and adjacent string literals - and asserts
# each fails. A check that survives a mutation is a check that asserts nothing.
#
# The copy is removed with rm and rmdir rather than a recursive delete.
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

work="$(mktemp -d "${TMPDIR:-/tmp}/de-platform-catalog-api.XXXXXX")"

remove_tree() {
  find "$1" -type f 2>/dev/null | while IFS= read -r file; do rm -f "${file}"; done
  find "$1" -depth -type d 2>/dev/null | while IFS= read -r dir; do rmdir "${dir}" 2>/dev/null || true; done
}

cleanup() { remove_tree "${work}"; }
trap cleanup EXIT

run() {
  uv run --frozen python deployment/scripts/check_catalog_api.py --root "${work}" >/dev/null 2>&1
}

reset() {
  if [ -d "${work}/platform" ]; then remove_tree "${work}/platform"; fi
  mkdir -p "${work}/platform"
  cp -r platform/src "${work}/platform/src"
}

# The banned path is assembled from two pieces for the same reason the check
# assembles it: keeping the literal out of the source tree is cheap insurance.
banned="api/"'management'

reset
if ! run; then
  echo "::error::the clean copy failed the catalog-API boundary check" >&2
  exit 1
fi
printf 'clean copy passes\n'

reset
printf '\n\ndef call(token):\n    return "http://polaris:8181/%s/v1/catalogs"\n' \
  "${banned}" >> "${work}/platform/src/de_platform/catalog.py"
if run; then
  echo "::error::a literal Management API path did not fail the check" >&2
  exit 1
fi
printf 'mutation caught: a literal Management API path\n'

reset
printf '\n\ndef call(token):\n    return "/api/" + "management"\n' \
  >> "${work}/platform/src/de_platform/catalog.py"
if run; then
  echo "::error::a concatenated Management API path did not fail the check" >&2
  exit 1
fi
printf 'mutation caught: a concatenated Management API path\n'

reset
printf '\n\ndef call(token):\n    return "api/" "management"\n' \
  >> "${work}/platform/src/de_platform/catalog.py"
if run; then
  echo "::error::an adjacent-literal Management API path did not fail the check" >&2
  exit 1
fi
printf 'mutation caught: an adjacent-literal Management API path\n'

printf 'the catalog-API boundary check is load-bearing\n'
