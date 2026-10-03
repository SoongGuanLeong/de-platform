"""The independent row-count model for the TPC-C population.

These are the counts the driver asserts a live load against. The eight fixed
tables have a closed form from the TPC-C population model (section 4.3), and
ORDER_LINE does not, because O_OL_CNT is random within [5, 15] per order; its
count is the sum of the generated O_OL_CNT values and is checked separately.
"""

from __future__ import annotations

from de_ingestion.commerce import tpcc


def test_fixed_counts_at_the_declared_volume():
    assert tpcc.counts.fixed_counts(100) == {
        "warehouse": 100,
        "district": 1_000,
        "customer": 3_000_000,
        "history": 3_000_000,
        "orders": 3_000_000,
        "new_order": 900_000,
        "item": 100_000,
        "stock": 10_000_000,
    }


def test_fixed_counts_scale_with_the_warehouse_count():
    counts = tpcc.counts.fixed_counts(1)
    assert counts["warehouse"] == 1
    assert counts["district"] == 10
    assert counts["customer"] == 30_000
    assert counts["stock"] == 100_000
    # ITEM is fixed: one catalogue shared by every warehouse.
    assert counts["item"] == 100_000
    assert tpcc.counts.fixed_counts(1)["item"] == tpcc.counts.fixed_counts(50)["item"]


def test_the_declared_volume_is_the_dataset_selection_figure():
    assert tpcc.counts.DECLARED_WAREHOUSES == 100
    assert tpcc.counts.DECLARED_SEED == 20261003


def test_order_line_bounds_follow_from_five_to_fifteen_lines_per_order():
    orders = tpcc.counts.fixed_counts(100)["orders"]
    assert tpcc.counts.order_line_bounds(100) == (5 * orders, 15 * orders)
