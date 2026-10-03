"""The TPC-C source schema, as PostgreSQL DDL.

The nine tables and their keys are TPC-C v5.11.0 section 1.4 (the database
definition), and the dataset selection records the same nine tables at
docs/dataset-selection.md section 4.1. The DDL is idempotent so a reset run can
re-create the schema without a drop, and the driver owns it because the driver
is the only write path into the schema.

Column types are the specification's own types mapped onto PostgreSQL. The
specification's generic fixed-length character columns are declared varchar
except for the two-character codes (state, credit and middle name) and the
nine-character zip, which stay char to keep their padding explicit.
"""

from __future__ import annotations

SCHEMA_NAME = "tpcc"

TABLES = (
    "warehouse",
    "district",
    "customer",
    "history",
    "new_order",
    "orders",
    "order_line",
    "item",
    "stock",
)

# The load order is the foreign-key dependency order, so a foreign key is always
# satisfied by the time the row that references it is inserted. It is the
# salvage-list pattern 15 ("an FK-ordered load") applied to this schema.
LOAD_ORDER = (
    "warehouse",
    "item",
    "district",
    "customer",
    "stock",
    "orders",
    "new_order",
    "history",
    "order_line",
)

PRIMARY_KEYS: dict[str, tuple[str, ...]] = {
    "warehouse": ("w_id",),
    "district": ("d_w_id", "d_id"),
    "customer": ("c_w_id", "c_d_id", "c_id"),
    "new_order": ("no_w_id", "no_d_id", "no_o_id"),
    "orders": ("o_w_id", "o_d_id", "o_id"),
    "order_line": ("ol_w_id", "ol_d_id", "ol_o_id", "ol_number"),
    "item": ("i_id",),
    "stock": ("s_w_id", "s_i_id"),
}

# One tuple per column: (name, type, nullable). HISTORY has no primary key: it is
# append-only by specification, so no key identifies a row.
_COLUMNS: dict[str, tuple[tuple[str, str, bool], ...]] = {
    "warehouse": (
        ("w_id", "integer", False),
        ("w_ytd", "numeric(12, 2)", False),
        ("w_tax", "numeric(4, 4)", False),
        ("w_name", "varchar(10)", False),
        ("w_street_1", "varchar(20)", False),
        ("w_street_2", "varchar(20)", False),
        ("w_city", "varchar(20)", False),
        ("w_state", "char(2)", False),
        ("w_zip", "char(9)", False),
    ),
    "district": (
        ("d_id", "integer", False),
        ("d_w_id", "integer", False),
        ("d_ytd", "numeric(12, 2)", False),
        ("d_tax", "numeric(4, 4)", False),
        ("d_next_o_id", "integer", False),
        ("d_name", "varchar(10)", False),
        ("d_street_1", "varchar(20)", False),
        ("d_street_2", "varchar(20)", False),
        ("d_city", "varchar(20)", False),
        ("d_state", "char(2)", False),
        ("d_zip", "char(9)", False),
    ),
    "customer": (
        ("c_id", "integer", False),
        ("c_d_id", "integer", False),
        ("c_w_id", "integer", False),
        ("c_first", "varchar(16)", False),
        ("c_middle", "char(2)", False),
        ("c_last", "varchar(16)", False),
        ("c_street_1", "varchar(20)", False),
        ("c_street_2", "varchar(20)", False),
        ("c_city", "varchar(20)", False),
        ("c_state", "char(2)", False),
        ("c_zip", "char(9)", False),
        ("c_phone", "char(16)", False),
        ("c_since", "timestamp", False),
        ("c_credit", "char(2)", False),
        ("c_credit_lim", "numeric(12, 2)", False),
        ("c_discount", "numeric(4, 4)", False),
        ("c_balance", "numeric(12, 2)", False),
        ("c_ytd_payment", "numeric(12, 2)", False),
        ("c_payment_cnt", "integer", False),
        ("c_delivery_cnt", "integer", False),
        ("c_data", "varchar(500)", False),
    ),
    "history": (
        ("h_c_id", "integer", False),
        ("h_c_d_id", "integer", False),
        ("h_c_w_id", "integer", False),
        ("h_d_id", "integer", False),
        ("h_w_id", "integer", False),
        ("h_date", "timestamp", False),
        ("h_amount", "numeric(12, 2)", False),
        ("h_data", "varchar(24)", False),
    ),
    "new_order": (
        ("no_o_id", "integer", False),
        ("no_d_id", "integer", False),
        ("no_w_id", "integer", False),
    ),
    "orders": (
        ("o_id", "integer", False),
        ("o_d_id", "integer", False),
        ("o_w_id", "integer", False),
        ("o_c_id", "integer", False),
        ("o_entry_d", "timestamp", False),
        ("o_carrier_id", "integer", True),
        ("o_ol_cnt", "integer", False),
        ("o_all_local", "integer", False),
    ),
    "order_line": (
        ("ol_o_id", "integer", False),
        ("ol_d_id", "integer", False),
        ("ol_w_id", "integer", False),
        ("ol_number", "integer", False),
        ("ol_i_id", "integer", False),
        ("ol_supply_w_id", "integer", False),
        ("ol_delivery_d", "timestamp", True),
        ("ol_quantity", "integer", False),
        ("ol_amount", "numeric(12, 2)", False),
        ("ol_dist_info", "char(24)", False),
    ),
    "item": (
        ("i_id", "integer", False),
        ("i_im_id", "integer", False),
        ("i_name", "varchar(24)", False),
        ("i_price", "numeric(12, 2)", False),
        ("i_data", "varchar(50)", False),
    ),
    "stock": (
        ("s_i_id", "integer", False),
        ("s_w_id", "integer", False),
        ("s_quantity", "integer", False),
        ("s_dist_01", "char(24)", False),
        ("s_dist_02", "char(24)", False),
        ("s_dist_03", "char(24)", False),
        ("s_dist_04", "char(24)", False),
        ("s_dist_05", "char(24)", False),
        ("s_dist_06", "char(24)", False),
        ("s_dist_07", "char(24)", False),
        ("s_dist_08", "char(24)", False),
        ("s_dist_09", "char(24)", False),
        ("s_dist_10", "char(24)", False),
        ("s_ytd", "integer", False),
        ("s_order_cnt", "integer", False),
        ("s_remote_cnt", "integer", False),
        ("s_data", "varchar(50)", False),
    ),
}

_FOREIGN_KEYS: dict[str, tuple[tuple[tuple[str, ...], str, tuple[str, ...]], ...]] = {
    "district": ((("d_w_id",), "warehouse", ("w_id",)),),
    "customer": ((("c_w_id", "c_d_id"), "district", ("d_w_id", "d_id")),),
    "history": (
        (("h_c_w_id", "h_c_d_id", "h_c_id"), "customer", ("c_w_id", "c_d_id", "c_id")),
        (("h_w_id", "h_d_id"), "district", ("d_w_id", "d_id")),
    ),
    "new_order": ((("no_w_id", "no_d_id", "no_o_id"), "orders", ("o_w_id", "o_d_id", "o_id")),),
    "orders": ((("o_w_id", "o_d_id", "o_c_id"), "customer", ("c_w_id", "c_d_id", "c_id")),),
    "order_line": (
        (("ol_w_id", "ol_d_id", "ol_o_id"), "orders", ("o_w_id", "o_d_id", "o_id")),
        (("ol_supply_w_id", "ol_i_id"), "stock", ("s_w_id", "s_i_id")),
    ),
    "stock": (
        (("s_w_id",), "warehouse", ("w_id",)),
        (("s_i_id",), "item", ("i_id",)),
    ),
}


def columns(table: str) -> tuple[str, ...]:
    """The column names of one table, in the order the DDL declares them."""
    return tuple(name for name, _sql_type, _nullable in _COLUMNS[table])


def table_ddl(table: str) -> str:
    """The CREATE TABLE statement for one table, idempotent and schema-qualified."""
    definitions = []
    for name, sql_type, nullable in _COLUMNS[table]:
        definition = "  " + name + " " + sql_type
        if not nullable:
            definition += " not null"
        definitions.append(definition)
    key = PRIMARY_KEYS.get(table)
    if key is not None:
        definitions.append("  primary key (" + ", ".join(key) + ")")
    for columns, target, target_columns in _FOREIGN_KEYS.get(table, ()):
        definitions.append(
            "  foreign key ("
            + ", ".join(columns)
            + ") references "
            + SCHEMA_NAME
            + "."
            + target
            + " ("
            + ", ".join(target_columns)
            + ")"
        )
    return (
        "create table if not exists "
        + SCHEMA_NAME
        + "."
        + table
        + " (\n"
        + ",\n".join(definitions)
        + "\n)"
    )


def ddl() -> list[str]:
    """The schema and every table, in foreign-key dependency order."""
    return [
        "create schema if not exists " + SCHEMA_NAME,
        *(table_ddl(table) for table in LOAD_ORDER),
    ]
