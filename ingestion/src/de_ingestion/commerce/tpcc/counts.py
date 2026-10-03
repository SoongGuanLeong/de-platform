"""The independent row-count model for the TPC-C population.

The eight fixed tables have a closed form from the TPC-C population model
(section 4.3), and the driver asserts a live load against it. ORDER_LINE is the
exception: O_OL_CNT is random within [5, 15] per order, so its count is the sum
of the generated values rather than a formula, and it is asserted against the
generator's own tally (population.py) rather than here.

The declared volume is W=100 from docs/dataset-selection.md section 7. The seed
is part of the fixture per docs/testing-strategy.md section 4.1: the driver is
authored here, so its seed is pinned rather than left to a default.
"""

from __future__ import annotations

# W=100, the declared volume of docs/dataset-selection.md section 7.
DECLARED_WAREHOUSES = 100

# The pinned fixture seed. A run that does not name this seed is not the
# declared fixture, so it cannot be cited as one.
DECLARED_SEED = 20261003

DISTRICTS_PER_WAREHOUSE = 10
CUSTOMERS_PER_DISTRICT = 3_000
ORDERS_PER_DISTRICT = 3_000
NEW_ORDERS_PER_DISTRICT = 900
STOCK_PER_WAREHOUSE = 100_000
ITEM_ROWS = 100_000


def fixed_counts(warehouses: int) -> dict[str, int]:
    """The row count of every table whose count is a closed form of W."""
    districts = DISTRICTS_PER_WAREHOUSE * warehouses
    return {
        "warehouse": warehouses,
        "district": districts,
        "customer": CUSTOMERS_PER_DISTRICT * districts,
        "history": CUSTOMERS_PER_DISTRICT * districts,
        "orders": ORDERS_PER_DISTRICT * districts,
        "new_order": NEW_ORDERS_PER_DISTRICT * districts,
        "item": ITEM_ROWS,
        "stock": STOCK_PER_WAREHOUSE * warehouses,
    }


def order_line_bounds(warehouses: int) -> tuple[int, int]:
    """The inclusive bounds on ORDER_LINE, from O_OL_CNT in [5, 15]."""
    orders = ORDERS_PER_DISTRICT * DISTRICTS_PER_WAREHOUSE * warehouses
    return (5 * orders, 15 * orders)
