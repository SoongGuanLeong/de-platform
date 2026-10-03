"""The driver is the only write path into the tpcc source schema.

The acceptance criterion is a property of the repository, not of one module, so
the check scans every Python and SQL file outside the driver package and fails on
a write statement that names the tpcc schema. The positive control below proves
the scan is not vacuous: the driver package does contain the writes.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = Path("ingestion/src/de_ingestion/commerce/tpcc")

_WRITE = re.compile(
    r"(?i)\b(insert\s+into|update|delete\s+from|copy|truncate|drop\s+(table|schema)"
    r"|create\s+(table|schema|index|publication)|alter\s+table)\b[^\n]*\btpcc\b"
)

_EXCLUDED_PARTS = (".git", "docs", "tests")


def _files():
    for path in ROOT.rglob("*"):
        if path.suffix not in (".py", ".sql") or not path.is_file():
            continue
        relative = path.relative_to(ROOT)
        if any(part in relative.parts for part in _EXCLUDED_PARTS):
            continue
        yield path, relative


def _hits(path):
    text = path.read_text(encoding="utf-8", errors="ignore")
    return [line for line in text.splitlines() if _WRITE.search(line)]


def test_only_the_tpcc_package_writes_to_the_source_schema():
    offenders = []
    for path, relative in _files():
        if relative.is_relative_to(PACKAGE):
            continue
        for line in _hits(path):
            offenders.append(str(relative) + ": " + line.strip())
    assert offenders == [], "writes to the tpcc schema outside the driver:\n" + "\n".join(offenders)


def test_the_scan_is_not_vacuous_because_the_driver_package_does_write():
    package_hits = 0
    for path, relative in _files():
        if relative.is_relative_to(PACKAGE):
            package_hits += len(_hits(path))
    assert package_hits > 0
