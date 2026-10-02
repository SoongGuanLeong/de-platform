#!/usr/bin/env bash
#
# The YAML single-entry-point check (docs/ci-cd-strategy.md section 4). Every
# reader goes through de_governance.yaml_loader, which rejects a duplicate
# mapping key; this fails on any safe_load left in the source tree.
#
# The check imports only the standard library, so it needs no distribution and
# the run does not name a package.
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

exec uv run --frozen python deployment/scripts/check_yaml_loading.py "$@"
