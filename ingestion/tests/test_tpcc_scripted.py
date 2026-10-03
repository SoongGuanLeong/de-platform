"""The scripted deterministic mode: the four CDC hard cases on demand.

The four cases are NULL-to-value UPDATE, composite-PK UPDATE, DELETE, and
out-of-order arrival (docs/testing-strategy.md section 4.1). They must not depend
on a random workload happening to produce them, so the mode emits each one as a
fixed, replayable transaction sequence that targets the initial population's
keys. The mode is labelled as not a TPC-C workload.
"""

from __future__ import annotations

from de_ingestion.commerce import tpcc

Case = tpcc.scripted.Case


def _statements(case):
    return [
        statement
        for transaction in tpcc.scripted.sequence(1, 7, case)
        for statement in transaction.statements
    ]


def test_null_to_value_update_sets_a_null_column_to_a_value():
    statements = _statements(Case.NULL_TO_VALUE_UPDATE)
    assert any("o_carrier_id" in statement.sql for statement in statements)
    assert any("ol_delivery_d" in statement.sql for statement in statements)
    for statement in statements:
        assert not statement.sql.startswith("select")


def test_composite_pk_update_targets_a_row_with_a_composite_key():
    statements = _statements(Case.COMPOSITE_PK_UPDATE)
    updates = [
        statement for statement in statements if statement.sql.startswith("update tpcc.customer")
    ]
    assert updates
    # CUSTOMER's key is (c_w_id, c_d_id, c_id): three parameters identify the row.
    assert len(updates[0].params) == 4


def test_delete_removes_a_new_order_row():
    statements = _statements(Case.DELETE)
    assert any(statement.sql.startswith("delete from tpcc.new_order") for statement in statements)


def test_out_of_order_is_two_distinct_updates_to_the_same_key():
    statements = _statements(Case.OUT_OF_ORDER)
    updates = [
        statement for statement in statements if statement.sql.startswith("update tpcc.customer")
    ]
    assert len(updates) == 2
    # The value differs; the key does not, so a consumer that reorders the two
    # converges on the wrong value unless it applies the LSN ordering rule.
    assert updates[0].params[0] != updates[1].params[0]
    assert updates[0].params[1:] == updates[1].params[1:]


def test_the_scripted_sequence_replays_identically():
    for case in (
        Case.NULL_TO_VALUE_UPDATE,
        Case.COMPOSITE_PK_UPDATE,
        Case.DELETE,
        Case.OUT_OF_ORDER,
    ):
        first = tpcc.scripted.render(tpcc.scripted.sequence(2, 7, case))
        second = tpcc.scripted.render(tpcc.scripted.sequence(2, 7, case))
        assert first == second
        assert first


def test_all_is_the_four_cases_in_order():
    names = [transaction.name for transaction in tpcc.scripted.sequence(1, 7, Case.ALL)]
    assert names == [
        "null_to_value_update",
        "composite_pk_update",
        "delete",
        "out_of_order",
    ]
