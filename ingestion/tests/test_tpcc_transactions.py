"""The TPC-C transaction mix and the deterministic sequence it produces.

The driver's normal mode is the specified transaction mix (New-Order 45%,
Payment 43%, Order-Status 4%, Delivery 4%, Stock-Level 4%), selected from a
seeded deck so the mix is exact over every 100 transactions and the sequence
replays. The tests assert the mix and the CDC-relevant statements, not the
driver's internals.
"""

from __future__ import annotations

from collections import Counter

from de_ingestion.commerce import tpcc


def test_the_mix_is_exact_over_one_hundred_transactions():
    sequence = tpcc.transactions.sequence(1, 100, 7)
    assert Counter(t.name for t in sequence) == {
        "new_order": 45,
        "payment": 43,
        "order_status": 4,
        "delivery": 4,
        "stock_level": 4,
    }


def test_the_same_seed_replays_the_same_sequence():
    assert tpcc.transactions.sequence(2, 60, 7) == tpcc.transactions.sequence(2, 60, 7)


def test_a_different_seed_gives_a_different_sequence():
    assert tpcc.transactions.sequence(2, 60, 7) != tpcc.transactions.sequence(2, 60, 8)


def test_the_render_is_a_stable_sequence_log():
    first = tpcc.transactions.render(tpcc.transactions.sequence(1, 25, 7))
    second = tpcc.transactions.render(tpcc.transactions.sequence(1, 25, 7))
    assert first == second
    assert first.count("new_order") > 0


def test_new_order_advances_the_district_order_counter():
    new_orders = [t for t in tpcc.transactions.sequence(1, 100, 7) if t.name == "new_order"]
    assert new_orders
    for transaction in new_orders:
        assert any("d_next_o_id" in statement.sql for statement in transaction.statements)
        assert any(
            statement.sql.startswith("insert into tpcc.orders")
            for statement in transaction.statements
        )
        assert any(
            statement.sql.startswith("insert into tpcc.new_order")
            for statement in transaction.statements
        )


def test_delivery_deletes_a_new_order_and_sets_the_carrier():
    deliveries = [t for t in tpcc.transactions.sequence(1, 100, 7) if t.name == "delivery"]
    assert deliveries
    for transaction in deliveries:
        assert any(
            statement.sql.startswith("delete from tpcc.new_order")
            for statement in transaction.statements
        )
        assert any("o_carrier_id" in statement.sql for statement in transaction.statements)


def test_payment_updates_the_customer_balance_and_writes_history():
    payments = [t for t in tpcc.transactions.sequence(1, 100, 7) if t.name == "payment"]
    assert payments
    for transaction in payments:
        assert any(
            statement.sql.startswith("update tpcc.customer") for statement in transaction.statements
        )
        assert any(
            statement.sql.startswith("insert into tpcc.history")
            for statement in transaction.statements
        )


def test_every_statement_targets_the_tpcc_schema():
    for transaction in tpcc.transactions.sequence(1, 100, 7):
        for statement in transaction.statements:
            assert "tpcc." in statement.sql or statement.sql.lstrip().startswith(("select", "with"))
