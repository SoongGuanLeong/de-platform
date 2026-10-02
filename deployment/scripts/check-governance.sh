#!/usr/bin/env bash
#
# The governance job (docs/ci-cd-strategy.md section 4). The completion-bar
# register and budget validator is owned by issue #32; the contract validator and
# breaking-change check land with issues #36 and #43, and the cross-path and
# layout-agreement checks with later phases.
#
# The validator reads committed artefacts and re-derives from them, and it re-runs
# no evidence: docs/ci-cd-strategy.md section 6 keeps the required set structural.
# It needs PyYAML, which yamllint already pins into the workspace environment, so
# this runs through uv rather than adding a second dependency set.
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

exec uv run --frozen python -m de_governance.register "$@"
