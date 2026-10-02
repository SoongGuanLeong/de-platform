#!/usr/bin/env python3
"""The single-entry-point check for YAML reads.

Every YAML read in this repository goes through de_governance.yaml_loader, which
rejects a duplicate mapping key. PyYAML's safe_load keeps the last of a repeated
key, so a reader built on it silently judges a document other than the one on
disk - and the register, the budgets and the compose files all carry values that
a check exists to enforce.

The check is absolute: there is no allow-list. The one module permitted to parse
YAML does so through yaml.load with a loader that raises on a duplicate, not
through safe_load, so no file has a reason to name safe_load at all.

deployment/scripts/test-check-yaml-loading.sh proves the check is load-bearing.

Run: deployment/scripts/check-yaml-loading.sh
"""

from __future__ import annotations

import argparse
import ast
import os
import re
import sys

# In a .sh file a YAML read is inline Python inside a heredoc, so there is no
# syntax tree to walk and the two calling forms are matched as text. A comment
# that merely names the call is not one of them, which is why the pattern wants
# the parenthesis or the import rather than the bare name.
SHELL_PATTERN = re.compile(r"safe_load\s*\(|import\s+safe_load\b")

SOURCE_SUFFIXES = (".py", ".sh")

# docs/ is prose and committed data, and a dot-directory is a tool's own tree
# (.venv, .git); neither is source this check has an opinion about.
SKIP_DIRECTORIES = {".git", ".venv", "__pycache__", "node_modules", "docs"}


def source_files(root: str):
    for directory, subdirectories, names in os.walk(root):
        subdirectories[:] = sorted(
            name
            for name in subdirectories
            if name not in SKIP_DIRECTORIES and not name.startswith(".")
        )
        for name in sorted(names):
            if name.endswith(SOURCE_SUFFIXES):
                yield os.path.join(directory, name)


def python_offences(path: str) -> list[int]:
    """The lines of a .py file that call safe_load.

    The syntax tree is walked rather than the text, so a comment or a docstring
    that names safe_load - and this repository has both, deliberately - is not
    an offence.
    """
    with open(path, encoding="utf-8") as handle:
        tree = ast.parse(handle.read(), filename=path)
    lines = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr == "safe_load":
            lines.append(node.lineno)
        elif isinstance(node, ast.Name) and node.id == "safe_load":
            lines.append(node.lineno)
        elif isinstance(node, ast.ImportFrom) and any(
            alias.name == "safe_load" for alias in node.names
        ):
            lines.append(node.lineno)
    return sorted(set(lines))


def shell_offences(path: str) -> list[int]:
    with open(path, encoding="utf-8") as handle:
        return [number for number, line in enumerate(handle, start=1) if SHELL_PATTERN.search(line)]


def main() -> int:
    parser = argparse.ArgumentParser(description="the YAML single-entry-point check")
    parser.add_argument("--root", default=None, help="the tree to scan")
    args = parser.parse_args()

    root = args.root or os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    offences = []
    for path in source_files(root):
        numbers = python_offences(path) if path.endswith(".py") else shell_offences(path)
        for number in numbers:
            offences.append(
                os.path.relpath(path, root) + ":" + str(number) + ": reads YAML through safe_load"
            )

    if offences:
        print(
            "::error::YAML is read through safe_load, which keeps the last of a duplicate key",
            file=sys.stderr,
        )
        for offence in offences:
            print("  " + offence, file=sys.stderr)
        print("  read through de_governance.yaml_loader.load_mapping instead", file=sys.stderr)
        return 1

    print("yaml reads: every reader goes through de_governance.yaml_loader")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
