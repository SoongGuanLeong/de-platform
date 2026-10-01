#!/usr/bin/env bash
#
# The compose job (docs/ci-cd-strategy.md section 4, docs/completion-bar.md
# sections 11 and 12). The subset, the limit resolution, the peak recompute and
# the image pins are all decided by deployment/scripts/check_compose.py, which
# needs PyYAML; yamllint already pins it into the workspace environment, so this
# runs through uv rather than adding a second dependency set.
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

exec uv run --frozen python deployment/scripts/check_compose.py "$@"
