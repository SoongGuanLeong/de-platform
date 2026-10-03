"""The TPC-C driver against live PostgreSQL (ticket #54).

Acceptance criteria: the declared volume is driven and the resulting row counts
are asserted; the scripted deterministic mode reproduces the same transaction
sequence on a second run; the driver is the only write path into the source
schema (asserted statically by ingestion/tests/test_tpcc_write_path.py).
"""

from __future__ import annotations

import os
from decimal import Decimal

import pytest
from de_ingestion.commerce import tpcc

WAREHOUSES = int(os.environ.get("TPCC_TEST_WAREHOUSES", "1"))


def test_the_population_loads_and_the_live_row_counts_are_asserted(tpcc_dsn):
    with tpcc.driver.connect(tpcc_dsn) as connection:
        result = tpcc.driver.run(
            connection,
            warehouses=WAREHOUSES,
            seed=tpcc.counts.DECLARED_SEED,
            count=100,
            mode="mix",
            reset=True,
        )
    # The loader tallied these; driver.load asserted them against SELECT count(*).
    for table, expected in tpcc.counts.fixed_counts(WAREHOUSES).items():
        assert result.loaded[table] == expected
    low, high = tpcc.counts.order_line_bounds(WAREHOUSES)
    assert low <= result.loaded["order_line"] <= high
    assert result.transactions == 100


def test_the_scripted_mode_replays_the_same_sequence_on_a_second_run(tpcc_dsn):
    with tpcc.driver.connect(tpcc_dsn) as connection:
        first = tpcc.driver.run(
            connection,
            warehouses=WAREHOUSES,
            seed=tpcc.counts.DECLARED_SEED,
            mode="scripted",
            case=tpcc.scripted.Case.ALL,
            reset=True,
        )
        second = tpcc.driver.run(
            connection,
            warehouses=WAREHOUSES,
            seed=tpcc.counts.DECLARED_SEED,
            mode="scripted",
            case=tpcc.scripted.Case.ALL,
            reset=True,
        )
    assert first.sequence_log == second.sequence_log
    assert first.sequence_log


def test_the_scripted_cases_change_the_rows_they_name(tpcc_dsn):
    with tpcc.driver.connect(tpcc_dsn) as connection:
        tpcc.driver.run(
            connection,
            warehouses=WAREHOUSES,
            seed=tpcc.counts.DECLARED_SEED,
            mode="scripted",
            case=tpcc.scripted.Case.ALL,
            reset=True,
        )
        with connection.cursor() as cursor:
            cursor.execute(
                "select o_carrier_id from tpcc.orders where o_w_id=1 and o_d_id=1 and o_id=2101"
            )
            assert cursor.fetchone()[0] == 7
            cursor.execute(
                "select count(*) from tpcc.new_order where no_w_id=1 and no_d_id=1 and no_o_id=2101"
            )
            assert cursor.fetchone()[0] == 0
            cursor.execute(
                "select c_balance from tpcc.customer where c_w_id=1 and c_d_id=1 and c_id=2"
            )
            assert cursor.fetchone()[0] == Decimal("-2.00")


@pytest.mark.skipif(WAREHOUSES < 1, reason="a warehouse count of at least one is required")
def test_a_second_mix_run_reproduces_the_same_transaction_sequence(tpcc_dsn):
    with tpcc.driver.connect(tpcc_dsn) as connection:
        first = tpcc.driver.run(
            connection,
            warehouses=WAREHOUSES,
            seed=tpcc.counts.DECLARED_SEED,
            count=100,
            mode="mix",
            reset=True,
        )
        second = tpcc.driver.run(
            connection,
            warehouses=WAREHOUSES,
            seed=tpcc.counts.DECLARED_SEED,
            count=100,
            mode="mix",
            reset=True,
        )
    assert first.sequence_log == second.sequence_log
