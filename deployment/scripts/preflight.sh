#!/usr/bin/env bash
#
# The preflight (docs/local-development.md section 5). The checks live in
# deployment/scripts/preflight.py because they read the register and the compose
# files, both YAML; this wrapper is the documented entry point and runs them
# through the pinned uv environment so PyYAML is the same one CI uses.
#
# Usage: preflight.sh <profile> [--reduced]
#   exit 0  the profile may run
#   exit 1  refused
#   exit 3  refused, and the reduced variant would fit
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

exec uv run --frozen python deployment/scripts/preflight.py "$@"
