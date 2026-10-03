"""The TPC-H source catalogue: the eight tables, their columns and their bronze names.

The catalogue is the one place the eight source tables, their dbgen flat-file
names and their column lists are written, so the generator, the loader and the
row-count assertion cannot drift apart. The bronze name is derived through the
platform core's naming convention rather than spelled out here.
"""

from __future__ import annotations

from de_batch.commerce.tpch import spec


def test_the_eight_source_tables_in_spec_order() -> None:
    assert spec.source_table_names() == (
        "region",
        "nation",
        "part",
        "supplier",
        "partsupp",
        "customer",
        "orders",
        "lineitem",
    )


def test_lineitem_has_the_sixteen_spec_columns_in_order() -> None:
    lineitem = spec.source_table("lineitem")
    assert [column.name for column in lineitem.columns] == [
        "l_orderkey",
        "l_partkey",
        "l_suppkey",
        "l_linenumber",
        "l_quantity",
        "l_extendedprice",
        "l_discount",
        "l_tax",
        "l_returnflag",
        "l_linestatus",
        "l_shipdate",
        "l_commitdate",
        "l_receiptdate",
        "l_shipinstruct",
        "l_shipmode",
        "l_comment",
    ]


def test_a_flat_file_is_named_after_its_table() -> None:
    assert spec.source_table("orders").flat_file == "orders.tbl"


def test_the_bronze_name_uses_the_platform_naming_convention() -> None:
    assert spec.bronze_identifier("lineitem") == "commerce.bronze.lineitem"


def test_an_unknown_table_is_refused() -> None:
    try:
        spec.source_table("partsuppx")
    except KeyError:
        return
    raise AssertionError("an unknown table must be refused")
