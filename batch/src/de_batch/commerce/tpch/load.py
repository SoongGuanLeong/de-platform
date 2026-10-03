"""The bronze load plan and the row-count assertion.

The plan is one target per TPC-H source table, and each target carries the count
read independently from the flat file. The assertion compares the loaded table's
count with that independent count, and the idempotence check is that a second run
leaves every count unchanged.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from de_batch.commerce.tpch import flatfiles, spec


@dataclass(frozen=True)
class LoadTarget:
    """One bronze table to load, and the independent count it must match."""

    table: str
    source: str
    flat_file: str
    expected_rows: int


class CountMismatch(AssertionError):
    """A loaded table's row count differs from its flat file's row count."""


def plan(directory: str) -> tuple[LoadTarget, ...]:
    """The load targets, one per source table, with independent counts."""
    counted = flatfiles.counts(directory)
    return tuple(
        LoadTarget(
            table=table.bronze_identifier(),
            source=table.name,
            flat_file=table.flat_file,
            expected_rows=counted[table.name],
        )
        for table in spec.source_tables()
    )


def verify(expected: Mapping[str, int], actual: Mapping[str, int]) -> None:
    """Assert every loaded table's count equals its independent flat-file count.

    A table present in one mapping and absent from the other is a mismatch too,
    so a load that silently skipped a table cannot pass.
    """
    for table, rows in expected.items():
        if table not in actual:
            raise CountMismatch(table + ": expected " + str(rows) + " rows but the table is absent")
        if actual[table] != rows:
            raise CountMismatch(
                table + ": flat-file count " + str(rows) + " != loaded count " + str(actual[table])
            )
    for table in actual:
        if table not in expected:
            raise CountMismatch(table + ": loaded but not in the plan")


def same_counts(before: Mapping[str, int], after: Mapping[str, int]) -> bool:
    """Whether a second run left every row count unchanged."""
    return dict(before) == dict(after)
