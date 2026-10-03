"""Row counts read independently from dbgen's own flat files.

The point of this module is independence: the count a bronze table is asserted
against must not come from the engine that loaded it. Counting lines of the
generated .tbl files is the independent count.
"""

from __future__ import annotations

import os

from de_batch.commerce.tpch import spec


def count_rows(path: str) -> int:
    """The number of data rows in a .tbl file.

    dbgen terminates every record with a newline, so a line count is the row
    count. A final line without a newline is still a row, and an empty file is
    zero rows.
    """
    rows = 0
    with open(path, "rb") as handle:
        for _ in handle:
            rows += 1
    return rows


def counts(directory: str) -> dict[str, int]:
    """One row count per TPC-H source table, from that table's flat file.

    A missing flat file is refused rather than counted as zero: a count of zero
    would make the row-count assertion pass against an empty table.
    """
    counted: dict[str, int] = {}
    for table in spec.source_tables():
        path = os.path.join(directory, table.flat_file)
        if not os.path.isfile(path):
            raise FileNotFoundError(
                "the flat file for " + table.name + " is missing: " + table.flat_file
            )
        counted[table.name] = count_rows(path)
    return counted
