"""The deterministic TPC-C population generator.

The generator is the fixture: the driver is authored here, so the seed is part
of the fixture (docs/testing-strategy.md section 4.1). These tests assert the
properties a replay depends on, at a small warehouse count; the declared volume
is exercised by the counts model and, on demand, by the live driver.
"""

from __future__ import annotations

from de_ingestion.commerce import tpcc


def _column(table, name):
    return tpcc.columns(table).index(name)


def test_the_same_seed_generates_the_same_rows():
    first = list(tpcc.population.iter_rows("warehouse", 3, 42))
    second = list(tpcc.population.iter_rows("warehouse", 3, 42))
    assert first == second


def test_a_different_seed_generates_different_rows():
    first = list(tpcc.population.iter_rows("warehouse", 3, 1))
    second = list(tpcc.population.iter_rows("warehouse", 3, 2))
    assert first != second


def test_every_fixed_table_generates_its_closed_form_count():
    for table, expected in tpcc.counts.fixed_counts(1).items():
        assert sum(1 for _ in tpcc.population.iter_rows(table, 1, 7)) == expected


def test_order_line_count_is_the_sum_of_the_generated_o_ol_cnt():
    orders = list(tpcc.population.iter_rows("orders", 1, 7))
    line_count = sum(1 for _ in tpcc.population.iter_rows("order_line", 1, 7))
    assert line_count == sum(row[_column("orders", "o_ol_cnt")] for row in orders)
    low, high = tpcc.counts.order_line_bounds(1)
    assert low <= line_count <= high


def test_the_last_two_thousand_customers_share_the_deterministic_surname():
    last = _column("customer", "c_last")
    customers = list(tpcc.population.iter_rows("customer", 1, 7))
    # C_ID restarts in every district, so the deterministic block is positions
    # 1000 to 2999 within each district, not a single suffix of the table.
    deterministic = [
        row[last]
        for index, row in enumerate(customers)
        if index % tpcc.counts.CUSTOMERS_PER_DISTRICT >= 1000
    ]
    assert set(deterministic) == {"BARBARBAR"}
    assert len(deterministic) == 2000 * tpcc.counts.DISTRICTS_PER_WAREHOUSE


def test_customer_credit_is_bc_for_roughly_one_in_ten():
    credit = _column("customer", "c_credit")
    customers = list(tpcc.population.iter_rows("customer", 1, 7))
    bad_credit = sum(1 for row in customers if row[credit] == "BC")
    assert 0.05 < bad_credit / len(customers) < 0.15


def test_the_first_two_thousand_one_hundred_orders_are_delivered_and_the_rest_are_not():
    carrier = _column("orders", "o_carrier_id")
    orders = list(tpcc.population.iter_rows("orders", 1, 7))
    for index, row in enumerate(orders):
        district = index // tpcc.counts.ORDERS_PER_DISTRICT
        position = index % tpcc.counts.ORDERS_PER_DISTRICT
        if position < 2100:
            assert 1 <= row[carrier] <= 10
        else:
            assert row[carrier] is None
        assert district < 10


def test_new_order_covers_the_undelivered_orders():
    new_order_ids = {
        row[_column("new_order", "no_o_id")] for row in tpcc.population.iter_rows("new_order", 1, 7)
    }
    assert new_order_ids == set(range(2101, 3001))


def test_order_line_delivery_timestamp_is_null_only_for_new_orders():
    delivery = _column("order_line", "ol_delivery_d")
    order_id = _column("order_line", "ol_o_id")
    lines = list(tpcc.population.iter_rows("order_line", 1, 7))
    for row in lines:
        if row[order_id] <= 2100:
            assert row[delivery] is not None
        else:
            assert row[delivery] is None


def test_copy_encoding_is_tab_separated_with_a_null_marker():
    assert tpcc.population.encode_copy_row(("a", None, 3)) == "a\t\\N\t3"


def test_generated_strings_respect_their_declared_column_widths():
    # The live COPY fails on a value wider than its column, so the widths are
    # asserted here rather than discovered against PostgreSQL.
    limits = {
        "item": {"i_name": 24, "i_data": 50},
        "stock": {"s_data": 50},
        "warehouse": {"w_name": 10, "w_street_1": 20, "w_state": 2, "w_zip": 9},
        "customer": {"c_first": 16, "c_last": 16, "c_data": 500, "c_phone": 16},
        "order_line": {"ol_dist_info": 24},
        "history": {"h_data": 24},
    }
    for table, widths in limits.items():
        columns = tpcc.columns(table)
        for row in tpcc.population.iter_rows(table, 1, 7):
            for name, limit in widths.items():
                assert len(row[columns.index(name)]) <= limit, (
                    table,
                    name,
                    row[columns.index(name)],
                )
