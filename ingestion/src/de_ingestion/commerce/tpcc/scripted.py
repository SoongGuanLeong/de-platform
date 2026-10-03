"""The scripted deterministic mode: the four CDC hard cases, on demand.

The four cases are NULL-to-value UPDATE, composite-PK UPDATE, DELETE, and
out-of-order arrival (docs/testing-strategy.md section 4.1). Each is a fixed,
replayable transaction sequence targeting the initial population's keys, so the
CDC path's correctness tests do not depend on a random workload producing the
case. This is not a TPC-C workload and is labelled as such wherever it runs.

The out-of-order case is two updates to one key with distinct values. The driver
commits them in order; a consumer that delivers them in the other order must
still converge on the later value, which is the LSN ordering rule's job. The
driver's obligation is only that both writes exist and are distinguishable.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from de_ingestion.commerce.tpcc.transactions import Statement, Transaction

_TARGET_WAREHOUSE = 1
_TARGET_DISTRICT = 1
# Order 2101 is the first undelivered order in the initial population, so its
# carrier and its order lines' delivery timestamps are NULL before this runs.
_TARGET_ORDER = 2101
_DELIVERY_TIME = datetime(2026, 1, 2, 12, 0, 0)


class Case(StrEnum):
    """One named CDC hard case, or all four."""

    NULL_TO_VALUE_UPDATE = "null_to_value_update"
    COMPOSITE_PK_UPDATE = "composite_pk_update"
    DELETE = "delete"
    OUT_OF_ORDER = "out_of_order"
    ALL = "all"


_ORDERED_CASES = (
    Case.NULL_TO_VALUE_UPDATE,
    Case.COMPOSITE_PK_UPDATE,
    Case.DELETE,
    Case.OUT_OF_ORDER,
)


def _null_to_value_update() -> Transaction:
    return Transaction(
        "null_to_value_update",
        (
            Statement(
                "update tpcc.orders set o_carrier_id = %s"
                " where o_w_id = %s and o_d_id = %s and o_id = %s",
                (7, _TARGET_WAREHOUSE, _TARGET_DISTRICT, _TARGET_ORDER),
            ),
            Statement(
                "update tpcc.order_line set ol_delivery_d = %s"
                " where ol_w_id = %s and ol_d_id = %s and ol_o_id = %s",
                (_DELIVERY_TIME, _TARGET_WAREHOUSE, _TARGET_DISTRICT, _TARGET_ORDER),
            ),
        ),
    )


def _composite_pk_update() -> Transaction:
    return Transaction(
        "composite_pk_update",
        (
            Statement(
                "update tpcc.customer set c_balance = c_balance - %s"
                " where c_w_id = %s and c_d_id = %s and c_id = %s",
                (Decimal("25.00"), _TARGET_WAREHOUSE, _TARGET_DISTRICT, 1),
            ),
        ),
    )


def _delete() -> Transaction:
    return Transaction(
        "delete",
        (
            Statement(
                "delete from tpcc.new_order where no_w_id = %s and no_d_id = %s and no_o_id = %s",
                (_TARGET_WAREHOUSE, _TARGET_DISTRICT, _TARGET_ORDER),
            ),
        ),
    )


def _out_of_order() -> Transaction:
    return Transaction(
        "out_of_order",
        (
            Statement(
                "update tpcc.customer set c_balance = %s"
                " where c_w_id = %s and c_d_id = %s and c_id = %s",
                (Decimal("-1.00"), _TARGET_WAREHOUSE, _TARGET_DISTRICT, 2),
            ),
            Statement(
                "update tpcc.customer set c_balance = %s"
                " where c_w_id = %s and c_d_id = %s and c_id = %s",
                (Decimal("-2.00"), _TARGET_WAREHOUSE, _TARGET_DISTRICT, 2),
            ),
        ),
    )


_BUILDERS = {
    Case.NULL_TO_VALUE_UPDATE: _null_to_value_update,
    Case.COMPOSITE_PK_UPDATE: _composite_pk_update,
    Case.DELETE: _delete,
    Case.OUT_OF_ORDER: _out_of_order,
}


def sequence(warehouses: int, seed: int, case: Case) -> tuple[Transaction, ...]:
    """The scripted sequence for one case, or all four in the declared order.

    The warehouse count and the seed are accepted so a caller drives the
    scripted mode through the same interface as the TPC-C mix. The scripted keys
    are fixed on purpose: the case must be reproducible regardless of the seed.
    """
    if case is Case.ALL:
        return tuple(_BUILDERS[name]() for name in _ORDERED_CASES)
    return (_BUILDERS[case](),)


def render(sequence: tuple[Transaction, ...]) -> str:
    """The canonical sequence log a replay compares, one transaction per line."""
    return "\n".join(transaction.render() for transaction in sequence)
