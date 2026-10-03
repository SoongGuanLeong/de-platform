"""The deterministic TPC-C population generator and the COPY loader.

The population model is TPC-C v5.11.0 section 4.3. Every random draw comes from
a per-table random.Random seeded from the fixture seed, so the same
(warehouses, seed) pair produces byte-identical rows on every run and a replay
can be asserted rather than hoped for. The seed is pinned in counts.py and named
by tests/fixtures.yaml.

The loader streams rows into PostgreSQL with COPY, which is the only bulk path
fast enough to make a large warehouse count possible. It returns the tallied row
count per table so the driver can assert the live count against it.
"""

from __future__ import annotations

import random
from collections.abc import Iterable, Iterator
from datetime import datetime, timedelta
from decimal import Decimal

from de_ingestion.commerce.tpcc import counts, schema

# A pinned base instant: every generated timestamp is this plus a seeded offset,
# so a replay produces the same timestamps and never depends on the wall clock.
_BASE_TIME = datetime(2026, 1, 1, 0, 0, 0)

# The TPC-C alphanumeric alphabet. The specification leaves the exact set to the
# implementation; a fixed uppercase-and-digit set keeps a replay exact. The
# translation table maps every byte onto a character, so a string is one
# randbytes call and one C-level translate rather than a Python loop per
# character, which matters when the declared volume generates tens of millions.
_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
_ALPHABET_TABLE = bytes(ord(_ALPHABET[index % len(_ALPHABET)]) for index in range(256))

_ORDER_LINE_LOW = 5
_ORDER_LINE_HIGH = 15
_DELIVERED_ORDERS_PER_DISTRICT = 2_100
_SURNAME_COUNT = 1_000
_DETERMINISTIC_SURNAME = "BARBARBAR"


def _rng(seed: int, table: str) -> random.Random:
    """A per-table stream, so one table's rows do not depend on another's draws."""
    return random.Random(str(seed) + ":" + table)


def _string(rng: random.Random, low: int, high: int) -> str:
    length = rng.randint(low, high)
    return rng.randbytes(length).translate(_ALPHABET_TABLE).decode("ascii")


def _digits(rng: random.Random, length: int) -> str:
    return "".join(str(rng.randint(0, 9)) for _ in range(length))


def _zip(rng: random.Random) -> str:
    return _digits(rng, 4) + "11111"


def _decimal(rng: random.Random, low: float, high: float, places: int) -> Decimal:
    return Decimal(str(round(rng.uniform(low, high), places)))


def _timestamp(rng: random.Random, span: timedelta) -> datetime:
    return _BASE_TIME + timedelta(seconds=rng.randrange(0, int(span.total_seconds())))


def _nurand(rng: random.Random, a: int, x: int, y: int, c: int) -> int:
    return (((rng.randint(0, a) | rng.randint(x, y)) + c) % (y - x + 1)) + x


def _surnames(rng: random.Random) -> list[str]:
    # The 1000th surname is the deterministic one the specification assigns to
    # every customer past the first 1000 (section 4.3.2.3).
    return [_string(rng, 8, 12) for _ in range(_SURNAME_COUNT - 1)] + [_DETERMINISTIC_SURNAME]


def _warehouse_rows(warehouses: int, seed: int) -> Iterator[tuple]:
    rng = _rng(seed, "warehouse")
    for w_id in range(1, warehouses + 1):
        yield (
            w_id,
            Decimal("300000.00"),
            _decimal(rng, 0.0, 0.2, 4),
            _string(rng, 6, 10),
            _string(rng, 10, 20),
            _string(rng, 10, 20),
            _string(rng, 10, 20),
            _string(rng, 2, 2),
            _zip(rng),
        )


def _district_rows(warehouses: int, seed: int) -> Iterator[tuple]:
    rng = _rng(seed, "district")
    for w_id in range(1, warehouses + 1):
        for d_id in range(1, counts.DISTRICTS_PER_WAREHOUSE + 1):
            yield (
                d_id,
                w_id,
                Decimal("30000.00"),
                _decimal(rng, 0.0, 0.2, 4),
                3001,
                _string(rng, 6, 10),
                _string(rng, 10, 20),
                _string(rng, 10, 20),
                _string(rng, 10, 20),
                _string(rng, 2, 2),
                _zip(rng),
            )


def _customer_rows(warehouses: int, seed: int) -> Iterator[tuple]:
    rng = _rng(seed, "customer")
    surnames = _surnames(rng)
    constant = rng.randint(0, 255)
    for w_id in range(1, warehouses + 1):
        for d_id in range(1, counts.DISTRICTS_PER_WAREHOUSE + 1):
            for c_id in range(1, counts.CUSTOMERS_PER_DISTRICT + 1):
                if c_id <= 1000:
                    last = surnames[_nurand(rng, 255, 0, 999, constant)]
                else:
                    last = surnames[_SURNAME_COUNT - 1]
                yield (
                    c_id,
                    d_id,
                    w_id,
                    _string(rng, 8, 16),
                    "OE",
                    last,
                    _string(rng, 10, 20),
                    _string(rng, 10, 20),
                    _string(rng, 10, 20),
                    _string(rng, 2, 2),
                    _zip(rng),
                    _digits(rng, 16),
                    _timestamp(rng, timedelta(days=365)),
                    "BC" if rng.random() < 0.10 else "GC",
                    Decimal("50000.00"),
                    _decimal(rng, 0.0, 0.5, 4),
                    Decimal("-10.00"),
                    Decimal("10.00"),
                    1,
                    0,
                    _string(rng, 300, 500),
                )


def _history_rows(warehouses: int, seed: int) -> Iterator[tuple]:
    rng = _rng(seed, "history")
    # HISTORY is one row per customer, so the customer stream is replayed to
    # reuse each customer's C_SINCE rather than drawing a second, uncorrelated
    # timestamp.
    since_index = schema.columns("customer").index("c_since")
    for customer in _customer_rows(warehouses, seed):
        h_c_id, h_c_d_id, h_c_w_id = customer[0], customer[1], customer[2]
        yield (
            h_c_id,
            h_c_d_id,
            h_c_w_id,
            h_c_d_id,
            h_c_w_id,
            customer[since_index],
            Decimal("10.00"),
            _string(rng, 12, 24),
        )


def _order_rows(warehouses: int, seed: int) -> Iterator[tuple]:
    rng = _rng(seed, "orders")
    for w_id in range(1, warehouses + 1):
        for d_id in range(1, counts.DISTRICTS_PER_WAREHOUSE + 1):
            customer_ids = list(range(1, counts.CUSTOMERS_PER_DISTRICT + 1))
            rng.shuffle(customer_ids)
            for index, c_id in enumerate(customer_ids):
                o_id = index + 1
                delivered = o_id <= _DELIVERED_ORDERS_PER_DISTRICT
                yield (
                    o_id,
                    d_id,
                    w_id,
                    c_id,
                    _timestamp(rng, timedelta(days=30)),
                    rng.randint(1, 10) if delivered else None,
                    rng.randint(_ORDER_LINE_LOW, _ORDER_LINE_HIGH),
                    1,
                )


def _new_order_rows(warehouses: int, seed: int) -> Iterator[tuple]:
    for w_id in range(1, warehouses + 1):
        for d_id in range(1, counts.DISTRICTS_PER_WAREHOUSE + 1):
            for o_id in range(_DELIVERED_ORDERS_PER_DISTRICT + 1, counts.ORDERS_PER_DISTRICT + 1):
                yield (o_id, d_id, w_id)


def _order_line_rows(warehouses: int, seed: int) -> Iterator[tuple]:
    rng = _rng(seed, "order_line")
    for order in _order_rows(warehouses, seed):
        o_id, d_id, w_id, _c_id, o_entry_d, carrier, o_ol_cnt, _all_local = order
        delivered = carrier is not None
        for ol_number in range(1, o_ol_cnt + 1):
            supply_w_id = w_id
            if warehouses > 1 and rng.random() >= 0.99:
                supply_w_id = rng.choice([w for w in range(1, warehouses + 1) if w != w_id])
            yield (
                o_id,
                d_id,
                w_id,
                ol_number,
                rng.randint(1, counts.ITEM_ROWS),
                supply_w_id,
                o_entry_d if delivered else None,
                5,
                Decimal("0.00") if delivered else _decimal(rng, 0.01, 9999.99, 2),
                _string(rng, 24, 24),
            )


def _item_rows(_warehouses: int, seed: int) -> Iterator[tuple]:
    rng = _rng(seed, "item")
    for i_id in range(1, counts.ITEM_ROWS + 1):
        data = _string(rng, 26, 50)
        if rng.random() < 0.10:
            # Overwrite the first eight characters rather than prefixing, so the
            # value stays within the declared 50 characters.
            data = "ORIGINAL" + data[8:]
        yield (
            i_id,
            rng.randint(1, 10000),
            _string(rng, 14, 24),
            _decimal(rng, 1.0, 100.0, 2),
            data,
        )


def _stock_rows(warehouses: int, seed: int) -> Iterator[tuple]:
    rng = _rng(seed, "stock")
    for w_id in range(1, warehouses + 1):
        for i_id in range(1, counts.STOCK_PER_WAREHOUSE + 1):
            data = _string(rng, 26, 50)
            if rng.random() < 0.10:
                data = "ORIGINAL" + data[8:]
            yield (
                i_id,
                w_id,
                rng.randint(10, 100),
                *(_string(rng, 24, 24) for _ in range(10)),
                0,
                0,
                0,
                data,
            )


_GENERATORS = {
    "warehouse": _warehouse_rows,
    "district": _district_rows,
    "customer": _customer_rows,
    "history": _history_rows,
    "new_order": _new_order_rows,
    "orders": _order_rows,
    "order_line": _order_line_rows,
    "item": _item_rows,
    "stock": _stock_rows,
}


def iter_rows(table: str, warehouses: int, seed: int) -> Iterator[tuple]:
    """The rows of one table for a (warehouses, seed) fixture, in key order."""
    return _GENERATORS[table](warehouses, seed)


def encode_copy_row(row: Iterable) -> str:
    """One COPY text-format line: tab-separated, escaped, with a NULL marker."""
    fields = []
    for value in row:
        if value is None:
            fields.append("\\N")
        elif isinstance(value, datetime):
            fields.append(value.isoformat(sep=" "))
        else:
            text = str(value)
            text = text.replace("\\", "\\\\")
            text = text.replace("\t", "\\t").replace("\n", "\\n").replace("\r", "\\r")
            fields.append(text)
    return "\t".join(fields)


def load(conn, warehouses: int, seed: int, batch: int = 10_000) -> dict[str, int]:
    """Load the population through COPY, in foreign-key order.

    Returns the row count the loader emitted per table. The driver asserts a live
    SELECT count(*) against it, so a load that silently dropped rows fails rather
    than passing on a number the loader produced.
    """
    loaded: dict[str, int] = {}
    for table in schema.LOAD_ORDER:
        statement = (
            "copy "
            + schema.SCHEMA_NAME
            + "."
            + table
            + " ("
            + ", ".join(schema.columns(table))
            + ") from stdin"
        )
        total = 0
        with conn.cursor() as cursor:
            with cursor.copy(statement) as copy:
                buffer: list[str] = []
                for row in iter_rows(table, warehouses, seed):
                    buffer.append(encode_copy_row(row))
                    total += 1
                    if len(buffer) >= batch:
                        copy.write("\n".join(buffer) + "\n")
                        buffer.clear()
                if buffer:
                    copy.write("\n".join(buffer) + "\n")
        loaded[table] = total
    return loaded
