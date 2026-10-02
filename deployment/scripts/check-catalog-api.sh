#!/usr/bin/env bash
#
# The catalog-API boundary check (docs/ci-cd-strategy.md section 4). The shared
# core reaches the catalog only through the Iceberg REST specification, never
# through a Polaris-proprietary admin API (ADR-0010).
#
# The check imports only the standard library, so it needs no distribution and
# the run does not name a package.
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

exec uv run --frozen python deployment/scripts/check_catalog_api.py "$@"
