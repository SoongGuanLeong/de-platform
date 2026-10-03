"""The live collector and the pipeline that wires it to the backfill.

The WebSocket is a double in the red-green loop (docs/testing-strategy.md
section 5): the claim under test is the collector's own behaviour, the declared
subscription set on one socket, the produce-and-advance path, and the backoff on
a disconnect. The bounded real check runs the same Collector against
atlas-stream.ripe.net separately.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from de_ingestion.network.ripe.collector import (
    Collector,
    ConnectionClosed,
    RipeStreamError,
)
from de_ingestion.network.ripe.config import RipeCollectorConfig, Subscription
from de_ingestion.network.ripe.cursor import CursorStore
from de_ingestion.network.ripe.ratelimit import Backoff

TOPIC = "network.ripe.results"


class RecordingProducer:
    def __init__(self) -> None:
        self.records: list[tuple[str, bytes | None, bytes]] = []

    def produce(self, topic: str, key: bytes | None, value: bytes) -> None:
        self.records.append((topic, key, value))


class FakeConnection:
    def __init__(self, messages: list) -> None:
        self._messages = list(messages)
        self.sent: list[str] = []

    def send(self, message: str) -> None:
        self.sent.append(message)

    def recv(self, timeout=None) -> str:
        if not self._messages:
            raise ConnectionClosed("script exhausted")
        return json.dumps(self._messages.pop(0))


def config(**overrides) -> RipeCollectorConfig:
    values = dict(
        topic=TOPIC,
        websocket_url="wss://example/stream/",
        client_id="c",
        max_connections_per_ip=16,
        connections=1,
        max_subscriptions_per_connection=16,
        rest_base_url="https://example/api/v2",
        rest_min_interval_seconds=1.0,
        rest_chunk_seconds=300,
        backfill_window_seconds=900,
        subscriptions=(
            Subscription("result", {"msm": 1001}),
            Subscription("result", {"msm": 38813297}),
        ),
    )
    values.update(overrides)
    return RipeCollectorConfig(**values)


def result(msm_id: int, prb_id: int, timestamp: int) -> list:
    return ["atlas_result", {"msm_id": msm_id, "prb_id": prb_id, "timestamp": timestamp}]


def subscribed() -> list:
    return ["atlas_subscribed", {"streamType": "result", "msm": 1001}]


def test_the_collector_subscribes_the_declared_set_on_one_socket(tmp_path: Path) -> None:
    connection = FakeConnection([subscribed(), result(1001, 1, 100), result(1001, 2, 101)])
    opened: list[tuple[str, str]] = []

    def factory(url: str, client_id: str):
        opened.append((url, client_id))
        return connection

    producer = RecordingProducer()
    store = CursorStore(tmp_path / "cursor.json")
    collector = Collector(
        config(), producer, store, connection_factory=factory, sleep=lambda _: None
    )

    produced = collector.run(limit=2)

    assert produced == 2
    assert opened == [("wss://example/stream/", "c")]
    assert connection.sent == [
        json.dumps(["atlas_subscribe", {"streamType": "result", "msm": 1001}]),
        json.dumps(["atlas_subscribe", {"streamType": "result", "msm": 38813297}]),
    ]
    assert {topic for topic, _, _ in producer.records} == {TOPIC}
    assert [json.loads(value)["prb_id"] for _, _, value in producer.records] == [1, 2]
    assert store.read().get(1001) == 101


def test_a_disconnect_backs_off_then_reconnects_and_keeps_producing(tmp_path: Path) -> None:
    connections = [
        FakeConnection([subscribed(), result(1001, 1, 100)]),
        FakeConnection([subscribed(), result(1001, 2, 200)]),
    ]
    sleeps: list[float] = []

    def factory(url: str, client_id: str):
        return connections.pop(0)

    collector = Collector(
        config(),
        RecordingProducer(),
        CursorStore(tmp_path / "cursor.json"),
        connection_factory=factory,
        sleep=sleeps.append,
        backoff=Backoff(base=2.0, factor=2.0, max_delay=60.0),
    )

    produced = collector.run(limit=2)

    assert produced == 2
    assert sleeps == [2.0]


def test_an_atlas_error_is_surfaced_rather_than_swallowed(tmp_path: Path) -> None:
    connection = FakeConnection([["atlas_error", {"code": "invalid_message"}]])
    collector = Collector(
        config(),
        RecordingProducer(),
        CursorStore(tmp_path / "cursor.json"),
        connection_factory=lambda url, client_id: connection,
        sleep=lambda _: None,
    )
    with pytest.raises(RipeStreamError, match="invalid_message"):
        collector.run(limit=1)


def test_the_live_and_backfill_paths_share_one_producer_and_topic(tmp_path: Path) -> None:
    from de_ingestion.network.ripe.pipeline import RipePipeline

    producer = RecordingProducer()
    store = CursorStore(tmp_path / "cursor.json")
    pipeline = RipePipeline(
        config(),
        producer,
        store,
        connection_factory=lambda url, client_id: FakeConnection([]),
    )

    assert pipeline.collector.producer is producer
    assert pipeline.backfill.producer is producer
    assert pipeline.collector.topic == pipeline.backfill.topic == TOPIC
