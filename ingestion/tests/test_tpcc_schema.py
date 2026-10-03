"""The TPC-C source schema: the nine tables, their keys, and the idempotent DDL.

The schema is the contract the driver writes and Debezium reads, so these tests
assert the shape a reviewer can check against TPC-C v5.11.0 section 1.4 (the
database definition) rather than anything about the driver's internals.
"""

from __future__ import annotations

from de_ingestion.commerce import tpcc


def test_the_schema_is_the_nine_tpcc_tables():
    assert set(tpcc.TABLES) == {
        "warehouse",
        "district",
        "customer",
        "history",
        "new_order",
        "orders",
        "order_line",
        "item",
        "stock",
    }


def test_ddl_creates_the_schema_and_every_table_idempotently():
    text = "\n".join(tpcc.ddl()).lower()
    assert "create schema if not exists tpcc" in text
    for table in tpcc.TABLES:
        assert "create table if not exists tpcc." + table in text


def test_primary_keys_are_the_specified_composite_keys():
    assert tpcc.PRIMARY_KEYS == {
        "warehouse": ("w_id",),
        "district": ("d_w_id", "d_id"),
        "customer": ("c_w_id", "c_d_id", "c_id"),
        "new_order": ("no_w_id", "no_d_id", "no_o_id"),
        "orders": ("o_w_id", "o_d_id", "o_id"),
        "order_line": ("ol_w_id", "ol_d_id", "ol_o_id", "ol_number"),
        "item": ("i_id",),
        "stock": ("s_w_id", "s_i_id"),
    }


def test_history_is_append_only_and_has_no_primary_key():
    assert "history" not in tpcc.PRIMARY_KEYS
    assert "primary key" not in tpcc.table_ddl("history").lower()


def test_the_schema_qualifies_every_table_with_the_tpcc_schema():
    assert tpcc.SCHEMA_NAME == "tpcc"
