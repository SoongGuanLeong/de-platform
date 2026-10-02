#!/usr/bin/env bash
#
# The governance job (docs/ci-cd-strategy.md section 4). The completion-bar
# register and budget validator is owned by issue #32; the contract validator and
# breaking-change check land with issues #36 and #43, and the cross-path and
# layout-agreement checks with later phases.
#
# The validator reads committed artefacts and re-derives from them, and it re-runs
# no evidence: docs/ci-cd-strategy.md section 6 keeps the required set structural.
# PyYAML is a dependency of the governance distribution, so the run names the
# package: the repository root is a virtual project, and `uv run` without
# --package installs no distribution at all.
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

exec uv run --frozen --package governance python -m de_governance.register "$@"
