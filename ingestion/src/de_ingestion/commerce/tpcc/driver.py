"""The TPC-C driver: create, load, drive, and assert.

The driver is the only write path into the tpcc source schema. It creates the
schema, loads the deterministic population through COPY, asserts the live row
counts against the loader's own tally, and drives either the specified
transaction mix or the scripted deterministic mode. A run is replayable: the
same (warehouses, seed, mode) produces the same population, the same transaction
sequence, and the same rendered sequence log.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from de_ingestion.commerce.tpcc import counts, population, schema, scripted, transactions

DEFAULT_DSN = "postgresql://deplatform@127.0.0.1:55432/deplatform"


def connect(dsn: str | None = None):
    """Open a connection to the TPC-C source database."""
    import psycopg

    return psycopg.connect(dsn or os.environ.get("TPCC_DSN", DEFAULT_DSN))


def create_schema(conn) -> None:
    with conn.cursor() as cursor:
        for statement in schema.ddl():
            cursor.execute(statement)
    conn.commit()


def drop_schema(conn) -> None:
    """Remove the source schema, so a replay starts from a known-empty state."""
    with conn.cursor() as cursor:
        cursor.execute("drop schema if exists " + schema.SCHEMA_NAME + " cascade")
    conn.commit()


def live_counts(conn) -> dict[str, int]:
    """The row count of every table, read from PostgreSQL itself."""
    result: dict[str, int] = {}
    with conn.cursor() as cursor:
        for table in schema.LOAD_ORDER:
            cursor.execute("select count(*) from " + schema.SCHEMA_NAME + "." + table)
            result[table] = cursor.fetchone()[0]
    return result


def count_mismatches(expected: dict[str, int], live: dict[str, int]) -> dict[str, tuple]:
    """The tables where the live count disagrees with the expected count."""
    return {
        table: (expected[table], live.get(table))
        for table in expected
        if expected[table] != live.get(table)
    }


def assert_counts(conn, expected: dict[str, int]) -> dict[str, int]:
    """Assert the live count equals the loader's tally, and return the live counts."""
    live = live_counts(conn)
    mismatches = count_mismatches(expected, live)
    if mismatches:
        raise AssertionError(
            "the live row counts disagree with the loader's tally "
            "(table: (expected, live)): " + repr(mismatches)
        )
    return live


@dataclass(frozen=True)
class RunResult:
    """What one driver run did, enough for a replay to be compared."""

    warehouses: int
    seed: int
    mode: str
    loaded: dict[str, int]
    final: dict[str, int]
    transactions: int
    sequence_log: str


def load(conn, warehouses: int, seed: int, reset: bool = False) -> dict[str, int]:
    """Create the schema, load the population, and assert the row counts."""
    if reset:
        drop_schema(conn)
    create_schema(conn)
    loaded = population.load(conn, warehouses, seed)
    assert_counts(conn, loaded)
    return loaded


def run(
    conn,
    warehouses: int,
    seed: int,
    count: int = 1_000,
    mode: str = "mix",
    case: scripted.Case | None = None,
    reset: bool = False,
) -> RunResult:
    """Load the population and drive one of the two modes.

    The counts are asserted straight after the load, before any transaction runs,
    so the assertion is of the population the driver wrote rather than of a state
    a later transaction changed.
    """
    loaded = load(conn, warehouses, seed, reset=reset)
    if mode == "scripted":
        sequence = scripted.sequence(warehouses, seed, case or scripted.Case.ALL)
        log = scripted.render(sequence)
    elif mode == "mix":
        sequence = transactions.sequence(warehouses, count, seed)
        log = transactions.render(sequence)
    else:
        raise ValueError("unknown mode: " + mode)
    applied = transactions.apply(conn, sequence)
    return RunResult(
        warehouses=warehouses,
        seed=seed,
        mode=mode,
        loaded=loaded,
        final=live_counts(conn),
        transactions=applied,
        sequence_log=log,
    )


def declared_counts(warehouses: int = counts.DECLARED_WAREHOUSES) -> dict[str, int]:
    """The closed-form counts at a warehouse count, for a report or an assertion."""
    return counts.fixed_counts(warehouses)
