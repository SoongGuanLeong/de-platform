#!/usr/bin/env python3
"""The catalog-API boundary check.

The shared core reaches the catalog only through the Iceberg REST specification,
never through a Polaris-proprietary admin API (ADR-0010). The specification, not
the implementation, is the asset: replacing Polaris with Lakekeeper changes a
URI and credentials and nothing else, and that is only true while no code path
calls the management API.

This fails on the management path anywhere under `platform/src`, which is the
shared core every path imports. There is deliberately no allow-list: the
one-time bootstrap that creates the catalog may use the Management API
(ADR-0010), and it lives with the run that bootstraps a profile rather than in
the core, so the core has no reason to name the path at all.

deployment/scripts/test-check-catalog-api.sh proves the check is load-bearing.

Run: deployment/scripts/check-catalog-api.sh
"""

from __future__ import annotations

import argparse
import os
import re
import sys

# The Polaris Management API path. Assembled from two pieces so this file, which
# lives outside the scanned tree, cannot itself be an offence if the scan is ever
# widened to the whole repository.
MANAGEMENT_PATH = re.compile("api/" + "management")

SKIP_DIRECTORIES = {".git", ".venv", "__pycache__", "node_modules"}


def source_files(root: str):
    for directory, subdirectories, names in os.walk(root):
        subdirectories[:] = sorted(name for name in subdirectories if name not in SKIP_DIRECTORIES)
        for name in sorted(names):
            if name.endswith(".py"):
                yield os.path.join(directory, name)


def main() -> int:
    parser = argparse.ArgumentParser(description="the catalog-API boundary check")
    parser.add_argument("--root", default=None, help="the repository root to scan")
    args = parser.parse_args()

    root = args.root or os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    core = os.path.join(root, "platform", "src")

    offences = []
    for path in source_files(core):
        with open(path, encoding="utf-8") as handle:
            for number, line in enumerate(handle, start=1):
                if MANAGEMENT_PATH.search(line):
                    offences.append(
                        os.path.relpath(path, root)
                        + ":"
                        + str(number)
                        + ": names the Polaris Management API"
                    )

    if offences:
        print(
            "::error::the shared core names the Polaris Management API, which the "
            "Iceberg REST specification replaces (ADR-0010)",
            file=sys.stderr,
        )
        for offence in offences:
            print("  " + offence, file=sys.stderr)
        return 1

    print("catalog API: the shared core reaches the catalog only through the Iceberg REST spec")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
