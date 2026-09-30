#!/usr/bin/env bash
#
# A stub check. The job exists in the graph (docs/ci-cd-strategy.md section 4)
# but its subject does not exist yet, so the check is enumerated rather than
# fabricated. The caller passes the find expression that would locate the
# subject: while it matches nothing the job reports a notice and passes, and the
# moment the subject appears the job fails until the owning ticket implements the
# real check. A stub therefore cannot silently become a green that checks nothing.
#
# Usage: check-stub.sh <name> <issue> <find-args...>
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

name="$1"
issue="$2"
shift 2

subject="$(find "$@" 2>/dev/null || true)"
if [ -n "${subject}" ]; then
  echo "::error::${name}: subject exists (${subject}) but the check is not implemented yet (issue #${issue})" >&2
  exit 1
fi

echo "::notice::${name}: no subject yet; check deferred to issue #${issue}"
