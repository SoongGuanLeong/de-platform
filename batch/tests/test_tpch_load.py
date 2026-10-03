"""The bronze load plan and the row-count assertion.

The plan is one target per TPC-H source table, and each target carries the count
read independently from the flat file. The assertion compares the table's count
with that independent count, and the idempotence check is that a second run
leaves every count unchanged.
"""

from __future__ import annotations

from de_batch.commerce.tpch import load


def _populate(tmp_path) -> None:
    for index, name in enumerate(
        ("region", "nation", "part", "supplier", "partsupp", "customer", "orders", "lineitem")
    ):
        (tmp_path / (name + ".tbl")).write_text("x\n" * (index + 1), encoding="utf-8")


def test_the_plan_has_one_target_per_source_table(tmp_path) -> None:
    _populate(tmp_path)
    targets = load.plan(str(tmp_path))
    assert [target.table for target in targets] == [
        "commerce.bronze.region",
        "commerce.bronze.nation",
        "commerce.bronze.part",
        "commerce.bronze.supplier",
        "commerce.bronze.partsupp",
        "commerce.bronze.customer",
        "commerce.bronze.orders",
        "commerce.bronze.lineitem",
    ]


def test_each_target_carries_the_independent_count(tmp_path) -> None:
    _populate(tmp_path)
    targets = {target.table: target.expected_rows for target in load.plan(str(tmp_path))}
    assert targets["commerce.bronze.region"] == 1
    assert targets["commerce.bronze.lineitem"] == 8


def test_a_matching_count_passes(tmp_path) -> None:
    _populate(tmp_path)
    expected = {target.table: target.expected_rows for target in load.plan(str(tmp_path))}
    load.verify(expected, dict(expected))


def test_a_mismatch_names_the_table_and_both_counts() -> None:
    expected = {"commerce.bronze.region": 5}
    actual = {"commerce.bronze.region": 4}
    try:
        load.verify(expected, actual)
    except load.CountMismatch as error:
        text = str(error)
        assert "commerce.bronze.region" in text
        assert "5" in text
        assert "4" in text
        return
    raise AssertionError("a count mismatch must be raised")


def test_a_missing_table_is_a_mismatch_too() -> None:
    try:
        load.verify({"commerce.bronze.region": 5}, {})
    except load.CountMismatch:
        return
    raise AssertionError("a missing table must be a mismatch")


def test_idempotence_is_equal_counts_before_and_after() -> None:
    assert load.same_counts({"a": 1, "b": 2}, {"a": 1, "b": 2}) is True
    assert load.same_counts({"a": 1, "b": 2}, {"a": 1, "b": 3}) is False
