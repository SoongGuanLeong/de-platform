#!/usr/bin/env bash
#
# The governance job (docs/ci-cd-strategy.md section 4). Its validators are owned
# by other tickets: the completion-bar register and budget validators by issue
# #32, the contract validator and breaking-change check by issues #36 and #43,
# and the cross-path and layout-agreement checks by later phases.
#
# Until one of them lands, the job asserts that no validator module exists yet,
# so it cannot pass once a validator has been written without being wired in.
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

bash deployment/scripts/check-stub.sh governance 32 \
  governance/src/de_governance ! -name '__init__.py' -name '*.py' -print -quit
