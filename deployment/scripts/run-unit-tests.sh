#!/usr/bin/env bash
#
# Runs one distribution's co-located unit tests. Invoked once per matrix entry
# of the unit job. A distribution with no tests fails rather than passing
# vacuously: "run this distribution's tests" is meant to be a real command.
#
# Usage: run-unit-tests.sh <distribution>
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

distribution="$1"
if [ ! -d "${distribution}/tests" ]; then
  echo "::error::${distribution}/tests does not exist" >&2
  exit 1
fi

uv run --frozen pytest "${distribution}/tests" -q
