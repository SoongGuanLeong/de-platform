"""The TPC-H source catalogue.

The eight tables, their columns and their dbgen flat-file names, in the order
dbgen writes them and the TPC-H specification defines them (TPC-H v3.0.1, and
the dss.ddl shipped with dbgen). The bronze name is derived through the platform
core's naming convention rather than spelled out here, so the spine and layer
are not re-decided in this distribution.
"""

from __future__ import annotations

from dataclasses import dataclass

from de_platform import naming

SPINE = "commerce"
LAYER = "bronze"


@dataclass(frozen=True)
class Column:
    """A TPC-H column: its name, and the specification's SQL type.

    The type is the specification's, kept for the silver work that casts these
    columns; bronze lands every column as a string.
    """

    name: str
    sql_type: str


@dataclass(frozen=True)
class SourceTable:
    """One TPC-H source table and the flat file dbgen writes for it."""

    name: str
    flat_file: str
    columns: tuple[Column, ...]

    def bronze_identifier(self) -> str:
        return naming.iceberg_table(SPINE, LAYER, self.name)


def _columns(*pairs: tuple[str, str]) -> tuple[Column, ...]:
    return tuple(Column(name, sql_type) for name, sql_type in pairs)


_CATALOGUE: tuple[SourceTable, ...] = (
    SourceTable(
        "region",
        "region.tbl",
        _columns(
            ("r_regionkey", "INTEGER"),
            ("r_name", "CHAR(25)"),
            ("r_comment", "VARCHAR(152)"),
        ),
    ),
    SourceTable(
        "nation",
        "nation.tbl",
        _columns(
            ("n_nationkey", "INTEGER"),
            ("n_name", "CHAR(25)"),
            ("n_regionkey", "INTEGER"),
            ("n_comment", "VARCHAR(152)"),
        ),
    ),
    SourceTable(
        "part",
        "part.tbl",
        _columns(
            ("p_partkey", "INTEGER"),
            ("p_name", "VARCHAR(55)"),
            ("p_mfgr", "CHAR(25)"),
            ("p_brand", "CHAR(10)"),
            ("p_type", "VARCHAR(25)"),
            ("p_size", "INTEGER"),
            ("p_container", "CHAR(10)"),
            ("p_retailprice", "DECIMAL(15,2)"),
            ("p_comment", "VARCHAR(23)"),
        ),
    ),
    SourceTable(
        "supplier",
        "supplier.tbl",
        _columns(
            ("s_suppkey", "INTEGER"),
            ("s_name", "CHAR(25)"),
            ("s_address", "VARCHAR(40)"),
            ("s_nationkey", "INTEGER"),
            ("s_phone", "CHAR(15)"),
            ("s_acctbal", "DECIMAL(15,2)"),
            ("s_comment", "VARCHAR(101)"),
        ),
    ),
    SourceTable(
        "partsupp",
        "partsupp.tbl",
        _columns(
            ("ps_partkey", "INTEGER"),
            ("ps_suppkey", "INTEGER"),
            ("ps_availqty", "INTEGER"),
            ("ps_supplycost", "DECIMAL(15,2)"),
            ("ps_comment", "VARCHAR(199)"),
        ),
    ),
    SourceTable(
        "customer",
        "customer.tbl",
        _columns(
            ("c_custkey", "INTEGER"),
            ("c_name", "VARCHAR(25)"),
            ("c_address", "VARCHAR(40)"),
            ("c_nationkey", "INTEGER"),
            ("c_phone", "CHAR(15)"),
            ("c_acctbal", "DECIMAL(15,2)"),
            ("c_mktsegment", "CHAR(10)"),
            ("c_comment", "VARCHAR(117)"),
        ),
    ),
    SourceTable(
        "orders",
        "orders.tbl",
        _columns(
            ("o_orderkey", "INTEGER"),
            ("o_custkey", "INTEGER"),
            ("o_orderstatus", "CHAR(1)"),
            ("o_totalprice", "DECIMAL(15,2)"),
            ("o_orderdate", "DATE"),
            ("o_orderpriority", "CHAR(15)"),
            ("o_clerk", "CHAR(15)"),
            ("o_shippriority", "INTEGER"),
            ("o_comment", "VARCHAR(79)"),
        ),
    ),
    SourceTable(
        "lineitem",
        "lineitem.tbl",
        _columns(
            ("l_orderkey", "INTEGER"),
            ("l_partkey", "INTEGER"),
            ("l_suppkey", "INTEGER"),
            ("l_linenumber", "INTEGER"),
            ("l_quantity", "DECIMAL(15,2)"),
            ("l_extendedprice", "DECIMAL(15,2)"),
            ("l_discount", "DECIMAL(15,2)"),
            ("l_tax", "DECIMAL(15,2)"),
            ("l_returnflag", "CHAR(1)"),
            ("l_linestatus", "CHAR(1)"),
            ("l_shipdate", "DATE"),
            ("l_commitdate", "DATE"),
            ("l_receiptdate", "DATE"),
            ("l_shipinstruct", "CHAR(25)"),
            ("l_shipmode", "CHAR(10)"),
            ("l_comment", "VARCHAR(44)"),
        ),
    ),
)

_BY_NAME = {table.name: table for table in _CATALOGUE}


def source_tables() -> tuple[SourceTable, ...]:
    """The eight TPC-H source tables, in specification order."""
    return _CATALOGUE


def source_table_names() -> tuple[str, ...]:
    return tuple(table.name for table in _CATALOGUE)


def source_table(name: str) -> SourceTable:
    """One source table by name. An unknown name is a KeyError."""
    return _BY_NAME[name]


def bronze_identifier(name: str) -> str:
    """The fully-qualified Iceberg bronze table for a source table."""
    return source_table(name).bronze_identifier()
