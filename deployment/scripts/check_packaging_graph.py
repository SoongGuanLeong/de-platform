"""Assert the declared packaging graph is exactly the permitted one (ADR-0026).

The packaging graph is the first line of the boundary rules: a distribution that
is not declared as a dependency cannot be imported. This check reads each
distribution's [project].dependencies and fails when it is not the permitted set,
so a path cannot gain a dependency on another path by editing one pyproject.toml.

Run: uv run --frozen python deployment/scripts/check_packaging_graph.py
"""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# The permitted dependency edges. platform/ is the shared core and depends on
# nothing; orchestration/ is the composition root and may import both spines.
PERMITTED: dict[str, frozenset[str]] = {
    "platform": frozenset(),
    "ingestion": frozenset({"platform"}),
    "batch": frozenset({"platform"}),
    "governance": frozenset({"platform"}),
    "orchestration": frozenset({"platform", "ingestion", "batch", "governance"}),
}

_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


def declared_dependencies(pyproject: Path) -> set[str]:
    """The distribution names a pyproject declares, without version specifiers."""
    project = tomllib.loads(pyproject.read_text(encoding="utf-8")).get("project", {})
    declared: set[str] = set()
    for raw in project.get("dependencies", []):
        match = _NAME.match(raw.strip())
        if match:
            declared.add(match.group(0))
    return declared


def main() -> int:
    failures: list[str] = []

    root = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    members = set(root.get("tool", {}).get("uv", {}).get("workspace", {}).get("members", []))
    if members != set(PERMITTED):
        failures.append(f"workspace members are {sorted(members)}, expected {sorted(PERMITTED)}")

    for distribution, permitted in PERMITTED.items():
        pyproject = REPO_ROOT / distribution / "pyproject.toml"
        if not pyproject.is_file():
            failures.append(f"{distribution}/pyproject.toml is missing")
            continue
        declared = declared_dependencies(pyproject)
        if declared != set(permitted):
            failures.append(
                f"{distribution} declares {sorted(declared)}, permitted {sorted(permitted)}"
            )

    if failures:
        for failure in failures:
            print(f"::error::packaging graph: {failure}", file=sys.stderr)
        return 1

    print(f"packaging graph: {len(PERMITTED)} distributions, edges as permitted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
