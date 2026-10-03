"""The RIPE Atlas collector's declared configuration and rate limits.

The behaviour under test is the collector's own: what it declares it will
subscribe to, and that the declared set fits inside the publisher's documented
connection cap (16 concurrent WebSockets per client IP, research 01b section 1).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from de_ingestion.network.ripe.config import (
    ConfigError,
    RipeCollectorConfig,
    Subscription,
    load_config,
)


def test_declared_config_loads_the_measurement_set_and_topic() -> None:
    config = load_config()
    assert config.topic == "network.ripe.results"
    assert config.websocket_url == "wss://atlas-stream.ripe.net/stream/"
    assert config.client_id == "de-platform-portfolio"
    assert [s.filters["msm"] for s in config.subscriptions] == [1001, 38813297]
    assert all(s.stream_type == "result" for s in config.subscriptions)


def test_subscription_message_is_the_documented_atlas_subscribe_frame() -> None:
    sub = Subscription(stream_type="result", filters={"msm": 1001})
    assert sub.message() == ["atlas_subscribe", {"streamType": "result", "msm": 1001}]


def test_the_plan_multiplexes_the_set_onto_the_declared_connection_count() -> None:
    config = RipeCollectorConfig(
        topic="t",
        websocket_url="wss://example/stream/",
        client_id="c",
        max_connections_per_ip=16,
        connections=2,
        max_subscriptions_per_connection=2,
        rest_base_url="https://example/api/v2",
        rest_min_interval_seconds=1.0,
        rest_chunk_seconds=100,
        backfill_window_seconds=900,
        subscriptions=(
            Subscription("result", {"msm": 1}),
            Subscription("result", {"msm": 2}),
            Subscription("result", {"msm": 3}),
        ),
    )
    plan = config.subscription_plan()
    assert len(plan) == 2
    assert [s.filters["msm"] for s in plan[0]] == [1, 2]
    assert [s.filters["msm"] for s in plan[1]] == [3]


def test_a_plan_beyond_the_publisher_connection_cap_is_rejected() -> None:
    config = RipeCollectorConfig(
        topic="t",
        websocket_url="wss://example/stream/",
        client_id="c",
        max_connections_per_ip=16,
        connections=17,
        max_subscriptions_per_connection=1,
        rest_base_url="https://example/api/v2",
        rest_min_interval_seconds=1.0,
        rest_chunk_seconds=100,
        backfill_window_seconds=900,
        subscriptions=(Subscription("result", {"msm": 1}),),
    )
    with pytest.raises(ConfigError, match="connection"):
        config.subscription_plan()


def test_a_set_too_large_for_the_declared_connections_is_rejected() -> None:
    config = RipeCollectorConfig(
        topic="t",
        websocket_url="wss://example/stream/",
        client_id="c",
        max_connections_per_ip=16,
        connections=1,
        max_subscriptions_per_connection=1,
        rest_base_url="https://example/api/v2",
        rest_min_interval_seconds=1.0,
        rest_chunk_seconds=100,
        backfill_window_seconds=900,
        subscriptions=(Subscription("result", {"msm": 1}), Subscription("result", {"msm": 2})),
    )
    with pytest.raises(ConfigError, match="subscription"):
        config.subscription_plan()


def test_a_declared_config_that_breaks_the_cap_fails_to_load(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "topic: t\n"
        "websocket:\n"
        "  url: wss://example/stream/\n"
        "  client_id: c\n"
        "  max_connections_per_ip: 16\n"
        "  connections: 32\n"
        "  max_subscriptions_per_connection: 1\n"
        "rest:\n"
        "  base_url: https://example/api/v2\n"
        "  min_interval_seconds: 1.0\n"
        "  chunk_seconds: 100\n"
        "  backfill_window_seconds: 900\n"
        "subscriptions:\n"
        "  - stream_type: result\n"
        "    msm: 1\n",
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="connection"):
        load_config(bad)
