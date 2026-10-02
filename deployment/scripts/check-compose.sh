#!/usr/bin/env bash
#
# The compose job (docs/ci-cd-strategy.md section 4, docs/completion-bar.md
# sections 11 and 12). The subset, the limit resolution, the peak recompute and
# the image pins are all decided by deployment/scripts/check_compose.py, which
# needs PyYAML. That dependency is the governance distribution's, and the strict
# YAML loader the script reads through is de_governance's, so the run names the
# package: the repository root is a virtual project, and a `uv run` without
# --package installs no distribution at all.
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

exec uv run --frozen --package governance python deployment/scripts/check_compose.py "$@"
