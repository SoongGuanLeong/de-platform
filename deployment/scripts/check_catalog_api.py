#!/usr/bin/env python3
"""The catalog-API boundary check.

The shared core reaches the catalog only through the Iceberg REST specification,
never through a Polaris-proprietary admin API (ADR-0010). The specification, not
the implementation, is the asset: replacing Polaris with Lakekeeper changes a
URI and credentials and nothing else, and that is only true while no code path
calls the management API.

This fails on the management path anywhere under `platform/src`, which is the
shared core every path imports. It reads the syntax tree, so a path written as
adjacent string literals or as a literal concatenation is caught, not only a
single literal.

There is deliberately no allow-list: the one-time bootstrap that creates the
catalog may use the Management API (ADR-0010), and it lives with the run that
bootstraps a profile rather than in the core, so the core has no reason to name
the path at all. The guard that must name the path it refuses holds it in a
name, so it is not a literal this check flags.

deployment/scripts/test-check-catalog-api.sh proves the check is load-bearing.

Run: deployment/scripts/check-catalog-api.sh
"""

from __future__ import annotations

import argparse
import ast
import os
import sys

# Assembled from two pieces so this file cannot itself be an offence if the scan
# is ever widened to the whole repository.
MANAGEMENT_PATH = "api/" + "management"

SKIP_DIRECTORIES = {".git", ".venv", "__pycache__", "node_modules"}


def source_files(root: str):
    for directory, subdirectories, names in os.walk(root):
        subdirectories[:] = sorted(name for name in subdirectories if name not in SKIP_DIRECTORIES)
        for name in sorted(names):
            if name.endswith(".py"):
                yield os.path.join(directory, name)


def _folded_string(node: ast.AST) -> str | None:
    """The string a literal expression evaluates to, or None.

    A constant is itself; an addition of two literal strings is their
    concatenation, nested to any depth. Python folds adjacent string literals
    into one constant before this ever sees them. A name or a call is not a
    literal and folds to None, which is how the guard that names the refused
    path stays out of the check's way.
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _folded_string(node.left)
        right = _folded_string(node.right)
        if left is not None and right is not None:
            return left + right
    return None


def offences(path: str) -> list[int]:
    with open(path, encoding="utf-8") as handle:
        tree = ast.parse(handle.read(), filename=path)
    lines = []
    for node in ast.walk(tree):
        value = _folded_string(node)
        if value is not None and MANAGEMENT_PATH in value:
            lines.append(node.lineno)
    return sorted(set(lines))


def main() -> int:
    parser = argparse.ArgumentParser(description="the catalog-API boundary check")
    parser.add_argument("--root", default=None, help="the repository root to scan")
    args = parser.parse_args()

    root = args.root or os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    core = os.path.join(root, "platform", "src")

    found = []
    for path in source_files(core):
        for number in offences(path):
            found.append(
                os.path.relpath(path, root)
                + ":"
                + str(number)
                + ": names the Polaris Management API"
            )

    if found:
        print(
            "::error::the shared core names the Polaris Management API, which the "
            "Iceberg REST specification replaces (ADR-0010)",
            file=sys.stderr,
        )
        for offence in found:
            print("  " + offence, file=sys.stderr)
        return 1

    print("catalog API: the shared core reaches the catalog only through the Iceberg REST spec")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
