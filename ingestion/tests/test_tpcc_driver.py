"""The driver's pure orchestration helpers.

The live path (schema, COPY, transaction execution) is an integration test under
the batch profile. These tests cover the parts that decide whether a live run
passes: the count comparison and the declared-count report.
"""

from __future__ import annotations

from de_ingestion.commerce import tpcc


def test_count_mismatches_reports_only_the_disagreeing_tables():
    assert tpcc.driver.count_mismatches({"a": 1, "b": 2}, {"a": 1, "b": 3}) == {"b": (2, 3)}


def test_count_mismatches_treats_a_missing_table_as_a_mismatch():
    assert tpcc.driver.count_mismatches({"a": 1}, {}) == {"a": (1, None)}


def test_a_matching_set_has_no_mismatches():
    assert tpcc.driver.count_mismatches({"a": 1}, {"a": 1, "b": 9}) == {}


def test_declared_counts_is_the_closed_form():
    assert tpcc.driver.declared_counts(1) == tpcc.counts.fixed_counts(1)
