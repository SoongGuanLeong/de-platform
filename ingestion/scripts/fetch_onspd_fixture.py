"""Fetch the bounded ONSPD fixture the loader's tests read (issue #50).

No fixture bytes are committed (docs/testing-strategy.md section 4). This script
is the pinned generator: it reads the ONS Postcode Directory's hosted table for
the May 2026 release through the loader's own fetch path and writes a bounded
subset to `runtime/` (gitignored). The subset, its source and its declared volume
are recorded in `tests/fixtures.yaml`.

Usage:
    uv run --package ingestion python ingestion/scripts/fetch_onspd_fixture.py [destination]
"""

from __future__ import annotations

import sys

from de_ingestion.network import onspd

DEFAULT_DESTINATION = "runtime/fixtures/onspd_may2026_subset.csv"


def main() -> int:
    destination = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_DESTINATION
    count = onspd.fetch_subset(destination)
    print("wrote " + str(count) + " ONSPD " + onspd.ONSPD_RELEASE + " rows to " + destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
