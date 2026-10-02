"""The naming conventions, applied from one place (issue #33).

The expected values are the literals docs/data-architecture.md section 3 fixes:
Iceberg tables are `<spine>.<layer>.<table>` in a spine-then-layer namespace,
ClickHouse mirrors the serving domains, and the CDC topic carries the Confluent
subject `<topic>-value` (docs/data-contracts.md section 4).
"""

from __future__ import annotations

import pytest
from de_platform import naming


def test_iceberg_namespace_is_spine_then_layer():
    assert naming.iceberg_namespace("commerce", "gold") == "commerce.gold"
    assert naming.iceberg_namespace("network", "bronze") == "network.bronze"


def test_control_namespace_has_no_layer():
    assert naming.iceberg_namespace("platform") == "platform"


def test_iceberg_table_is_spine_layer_table():
    assert (
        naming.iceberg_table("commerce", "gold", "fact_lineitem") == "commerce.gold.fact_lineitem"
    )


def test_parse_table_round_trips():
    assert naming.parse_table("commerce.gold.fact_lineitem") == (
        "commerce",
        "gold",
        "fact_lineitem",
    )


def test_unknown_spine_or_layer_is_refused():
    with pytest.raises(naming.NamingError):
        naming.iceberg_namespace("finance", "gold")
    with pytest.raises(naming.NamingError):
        naming.iceberg_table("commerce", "platinum", "x")


def test_parse_table_refuses_a_name_that_is_not_three_parts():
    with pytest.raises(naming.NamingError):
        naming.parse_table("commerce.gold")


def test_clickhouse_mirrors_the_serving_domains():
    assert naming.clickhouse_database("commerce") == "commerce"
    assert naming.clickhouse_database("network") == "network"
    assert naming.CLICKHOUSE_DATABASES == ("commerce", "network", "governance", "lakehouse")


def test_cdc_topic_and_subject():
    topic = naming.cdc_topic("tpc-c", "public", "order_line")
    assert topic == "tpc-c.public.order_line"
    assert naming.cdc_subject(topic) == "tpc-c.public.order_line-value"
