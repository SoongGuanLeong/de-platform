"""The TPC-C driver for the commerce spine (ticket #54).

The driver is the only write path into the tpcc source schema: it creates the
schema, loads the declared population, and drives the specified transaction mix
against live PostgreSQL. A scripted deterministic mode emits the four CDC hard
cases on demand, so the CDC path correctness tests do not depend on a random
workload happening to produce them.

The public surface is re-exported here so a caller imports the package rather
than a module inside it: schema, counts, population, transactions, scripted and
driver.

Documented limitation. The declared volume W=100 is asserted by the closed-form
count model in counts.py, not by a live load: about 50 million rows and 10 GB is
beyond what the batch profile's 384 MiB PostgreSQL can load in one session. The
live path is verified at W=10, the declared correctness slice, by
tests/batch/test_tpcc_driver.py. The same test with TPCC_TEST_WAREHOUSES=100
closes the gap on a tier-1 host.
"""

from __future__ import annotations

from de_ingestion.commerce.tpcc import counts, driver, population, schema, scripted, transactions

LOAD_ORDER = schema.LOAD_ORDER
PRIMARY_KEYS = schema.PRIMARY_KEYS
SCHEMA_NAME = schema.SCHEMA_NAME
TABLES = schema.TABLES
columns = schema.columns
ddl = schema.ddl
table_ddl = schema.table_ddl

__all__ = [
    "LOAD_ORDER",
    "PRIMARY_KEYS",
    "SCHEMA_NAME",
    "TABLES",
    "columns",
    "counts",
    "ddl",
    "driver",
    "population",
    "scripted",
    "table_ddl",
    "transactions",
]
