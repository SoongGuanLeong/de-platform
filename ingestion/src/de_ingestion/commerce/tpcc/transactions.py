"""The five TPC-C transactions and the specified mix.

The mix is the specification's own: New-Order 45%, Payment 43%, Order-Status 4%,
Delivery 4%, Stock-Level 4% (section 1.3). It is selected from a seeded deck of
one hundred slots, so the proportions are exact over every full deck and the
sequence replays. Parameters are drawn from a second seeded stream, and the
statements that matter to CDC (the ORDER_LINE and STOCK updates, the NEW_ORDER
delete, the NULL-to-value carrier update) are the specification's own.

The sequence is the unit of determinism: sequence() is pure and returns the
statements it would run, and apply() runs exactly that sequence. A second run
with the same (warehouses, count, seed) renders an identical log.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from de_ingestion.commerce.tpcc import counts

MIX = (
    ("new_order", 45),
    ("payment", 43),
    ("order_status", 4),
    ("delivery", 4),
    ("stock_level", 4),
)

_INITIAL_NEXT_O_ID = 3001
_FIRST_NEW_ORDER_ID = 2101
_ORDER_LINE_LOW = 5
_ORDER_LINE_HIGH = 15
_BASE_TIME = datetime(2026, 1, 1, 0, 0, 0)


@dataclass(frozen=True)
class Statement:
    """One SQL statement and its parameters."""

    sql: str
    params: tuple = ()


@dataclass(frozen=True)
class Transaction:
    """One TPC-C transaction, a named group of statements run as one unit."""

    name: str
    statements: tuple[Statement, ...]

    def render(self) -> str:
        body = " | ".join(
            statement.sql + " " + repr(statement.params) for statement in self.statements
        )
        return self.name + ": " + body


class _State:
    """The driver's own key counters, so a sequence is generated without reads.

    Both counters start where the initial population left them (D_NEXT_O_ID is
    3001 and the oldest undelivered NEW_ORDER is 2101) and advance in the same
    order the statements do, so the predicted keys match the database's.
    """

    def __init__(self, warehouses: int) -> None:
        self.warehouses = warehouses
        self._next_o_id: dict[tuple[int, int], int] = {}
        self._delivery_o_id: dict[tuple[int, int], int] = {}

    def take_o_id(self, warehouse: int, district: int) -> int:
        key = (warehouse, district)
        value = self._next_o_id.get(key, _INITIAL_NEXT_O_ID)
        self._next_o_id[key] = value + 1
        return value

    def take_delivery_o_id(self, warehouse: int, district: int) -> int:
        key = (warehouse, district)
        value = self._delivery_o_id.get(key, _FIRST_NEW_ORDER_ID)
        self._delivery_o_id[key] = value + 1
        return value


def _money(rng: random.Random, low: float, high: float) -> Decimal:
    return Decimal(str(round(rng.uniform(low, high), 2)))


def _remote_supply(rng: random.Random, state: _State, warehouse: int) -> tuple[int, int]:
    if state.warehouses > 1 and rng.random() >= 0.99:
        candidates = [w for w in range(1, state.warehouses + 1) if w != warehouse]
        return rng.choice(candidates), 1
    return warehouse, 0


def _new_order(rng: random.Random, state: _State, warehouse: int, district: int) -> Transaction:
    c_id = rng.randint(1, counts.CUSTOMERS_PER_DISTRICT)
    o_id = state.take_o_id(warehouse, district)
    ol_cnt = rng.randint(_ORDER_LINE_LOW, _ORDER_LINE_HIGH)
    entry = _BASE_TIME + timedelta(seconds=rng.randrange(0, 86400))
    statements = [
        Statement(
            "insert into tpcc.orders (o_id, o_d_id, o_w_id, o_c_id, o_entry_d,"
            " o_carrier_id, o_ol_cnt, o_all_local) values (%s, %s, %s, %s, %s, %s, %s, %s)",
            (o_id, district, warehouse, c_id, entry, None, ol_cnt, 1),
        ),
        Statement(
            "insert into tpcc.new_order (no_o_id, no_d_id, no_w_id) values (%s, %s, %s)",
            (o_id, district, warehouse),
        ),
    ]
    for ol_number in range(1, ol_cnt + 1):
        i_id = rng.randint(1, counts.ITEM_ROWS)
        supply_w_id, remote = _remote_supply(rng, state, warehouse)
        quantity = 5
        statements.append(
            Statement(
                "update tpcc.stock set s_quantity = case when s_quantity >= %s"
                " then s_quantity - %s else s_quantity - %s + 91 end,"
                " s_ytd = s_ytd + %s, s_order_cnt = s_order_cnt + 1,"
                " s_remote_cnt = s_remote_cnt + %s where s_w_id = %s and s_i_id = %s",
                (quantity, quantity, quantity, quantity, remote, supply_w_id, i_id),
            )
        )
        statements.append(
            Statement(
                "insert into tpcc.order_line (ol_o_id, ol_d_id, ol_w_id, ol_number, ol_i_id,"
                " ol_supply_w_id, ol_delivery_d, ol_quantity, ol_amount, ol_dist_info)"
                " values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    o_id,
                    district,
                    warehouse,
                    ol_number,
                    i_id,
                    supply_w_id,
                    None,
                    quantity,
                    Decimal("0.00"),
                    "dist",
                ),
            )
        )
    statements.append(
        Statement(
            "update tpcc.district set d_next_o_id = d_next_o_id + 1"
            " where d_w_id = %s and d_id = %s",
            (warehouse, district),
        )
    )
    return Transaction("new_order", tuple(statements))


def _payment(rng: random.Random, state: _State, warehouse: int, district: int) -> Transaction:
    c_id = rng.randint(1, counts.CUSTOMERS_PER_DISTRICT)
    amount = _money(rng, 1.0, 5000.0)
    statements = [
        Statement(
            "update tpcc.warehouse set w_ytd = w_ytd + %s where w_id = %s",
            (amount, warehouse),
        ),
        Statement(
            "update tpcc.district set d_ytd = d_ytd + %s where d_w_id = %s and d_id = %s",
            (amount, warehouse, district),
        ),
        Statement(
            "update tpcc.customer set c_balance = c_balance - %s,"
            " c_ytd_payment = c_ytd_payment + %s, c_payment_cnt = c_payment_cnt + 1"
            " where c_w_id = %s and c_d_id = %s and c_id = %s",
            (amount, amount, warehouse, district, c_id),
        ),
        Statement(
            "insert into tpcc.history (h_c_id, h_c_d_id, h_c_w_id, h_d_id, h_w_id,"
            " h_date, h_amount, h_data) values (%s, %s, %s, %s, %s, %s, %s, %s)",
            (c_id, district, warehouse, district, warehouse, _BASE_TIME, amount, "payment"),
        ),
    ]
    return Transaction("payment", tuple(statements))


def _order_status(rng: random.Random, state: _State, warehouse: int, district: int) -> Transaction:
    c_id = rng.randint(1, counts.CUSTOMERS_PER_DISTRICT)
    statements = [
        Statement(
            "select c_balance, c_first, c_middle, c_last from tpcc.customer"
            " where c_w_id = %s and c_d_id = %s and c_id = %s",
            (warehouse, district, c_id),
        ),
        Statement(
            "select o_id, o_entry_d, o_carrier_id from tpcc.orders"
            " where o_w_id = %s and o_d_id = %s and o_c_id = %s order by o_id desc limit 1",
            (warehouse, district, c_id),
        ),
    ]
    return Transaction("order_status", tuple(statements))


def _delivery(rng: random.Random, state: _State, warehouse: int, district: int) -> Transaction:
    o_id = state.take_delivery_o_id(warehouse, district)
    carrier = rng.randint(1, 10)
    amount = _money(rng, 1.0, 1000.0)
    delivery_time = _BASE_TIME + timedelta(seconds=rng.randrange(0, 86400))
    statements = [
        Statement(
            "delete from tpcc.new_order where no_w_id = %s and no_d_id = %s and no_o_id = %s",
            (warehouse, district, o_id),
        ),
        Statement(
            "update tpcc.orders set o_carrier_id = %s"
            " where o_w_id = %s and o_d_id = %s and o_id = %s",
            (carrier, warehouse, district, o_id),
        ),
        Statement(
            "update tpcc.order_line set ol_delivery_d = %s"
            " where ol_w_id = %s and ol_d_id = %s and ol_o_id = %s",
            (delivery_time, warehouse, district, o_id),
        ),
        Statement(
            "update tpcc.customer set c_balance = c_balance + %s,"
            " c_delivery_cnt = c_delivery_cnt + 1 where c_w_id = %s and c_d_id = %s"
            " and c_id = (select o_c_id from tpcc.orders"
            " where o_w_id = %s and o_d_id = %s and o_id = %s)",
            (amount, warehouse, district, warehouse, district, o_id),
        ),
    ]
    return Transaction("delivery", tuple(statements))


def _stock_level(rng: random.Random, state: _State, warehouse: int, district: int) -> Transaction:
    threshold = rng.randint(10, 20)
    statements = [
        Statement(
            "select count(distinct s_i_id) from tpcc.order_line"
            " join tpcc.stock on s_w_id = ol_w_id and s_i_id = ol_i_id"
            " where ol_w_id = %s and ol_d_id = %s and ol_o_id >= %s and s_quantity < %s",
            (warehouse, district, 3000, threshold),
        ),
    ]
    return Transaction("stock_level", tuple(statements))


_BUILDERS = {
    "new_order": _new_order,
    "payment": _payment,
    "order_status": _order_status,
    "delivery": _delivery,
    "stock_level": _stock_level,
}


def _deck(rng: random.Random) -> list[str]:
    deck = [name for name, slots in MIX for _ in range(slots)]
    rng.shuffle(deck)
    return deck


def sequence(warehouses: int, count: int, seed: int) -> tuple[Transaction, ...]:
    """The transaction sequence for a fixture, generated without touching a database."""
    deck_rng = random.Random(str(seed) + ":tpcc:mix")
    param_rng = random.Random(str(seed) + ":tpcc:params")
    state = _State(warehouses)
    result = []
    deck: list[str] = []
    for index in range(count):
        if index % 100 == 0:
            deck = _deck(deck_rng)
        warehouse = param_rng.randint(1, warehouses)
        district = param_rng.randint(1, counts.DISTRICTS_PER_WAREHOUSE)
        result.append(_BUILDERS[deck[index % 100]](param_rng, state, warehouse, district))
    return tuple(result)


def render(transactions: tuple[Transaction, ...]) -> str:
    """The canonical sequence log a replay compares, one transaction per line."""
    return "\n".join(transaction.render() for transaction in transactions)


def apply(conn, transactions: tuple[Transaction, ...]) -> int:
    """Run a sequence, one database transaction per TPC-C transaction."""
    for transaction in transactions:
        with conn.cursor() as cursor:
            for statement in transaction.statements:
                cursor.execute(statement.sql, statement.params)
        conn.commit()
    return len(transactions)
