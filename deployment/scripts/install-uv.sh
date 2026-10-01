#!/usr/bin/env bash
#
# Installs the pinned uv, so every CI job pays for the same setup and the version
# lives in one place (deployment/tools.lock, docs/ci-cd-strategy.md section 9).
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

# shellcheck source=../tools.lock
. deployment/tools.lock

python -m pip install --user "uv==${UV_VERSION}"

if [ -n "${GITHUB_PATH:-}" ]; then
  echo "${HOME}/.local/bin" >> "${GITHUB_PATH}"
fi
