"""The producer, the REST client and the backfill producer.

The backfill is a producer into the same topic the live subscription writes,
not a second writer: its only sink is the injected Producer, and the cursor it
persists is the same cursor the live path advances (ADR-0014).
"""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
from de_ingestion.network.ripe.backfill import BackfillProducer, RipeRestClient, RipeRestError
from de_ingestion.network.ripe.cursor import CursorStore, TimepointCursor
from de_ingestion.network.ripe.producer import KafkaProducer, result_key, result_value
from de_ingestion.network.ripe.ratelimit import Backoff, RateLimiter

TOPIC = "network.ripe.results"


class RecordingProducer:
    def __init__(self) -> None:
        self.records: list[tuple[str, bytes | None, bytes]] = []

    def produce(self, topic: str, key: bytes | None, value: bytes) -> None:
        self.records.append((topic, key, value))


class FakeKafkaClient:
    def __init__(self) -> None:
        self.sent: list[tuple] = []
        self.flushed = 0
        self.closed = 0

    def send(self, topic, key=None, value=None):
        self.sent.append((topic, key, value))

    def flush(self):
        self.flushed += 1

    def close(self):
        self.closed += 1


class FakeTransport:
    """A stand-in for the RIPE results endpoint.

    Returns every record at or after `start`, in timestamp order, and records
    the start each call used so a test can assert resume behaviour.
    """

    def __init__(self, records: list[dict], *, scripted: list[tuple[int, object]] | None = None):
        self.records = records
        self.scripted = list(scripted or [])
        self.calls: list[tuple[int, int]] = []

    def __call__(self, url: str):
        query = parse_qs(urlparse(url).query)
        msm_id = int(urlparse(url).path.rstrip("/").split("/")[-2])
        start = int(query["start"][0])
        stop = int(query["stop"][0])
        self.calls.append((msm_id, start))
        if self.scripted:
            return self.scripted.pop(0)
        page = [r for r in self.records if start <= r["timestamp"] <= stop]
        return 200, page


def no_wait_limiter() -> RateLimiter:
    return RateLimiter(0.0)


def test_result_key_is_the_measurement_so_one_measurement_stays_ordered() -> None:
    assert result_key({"msm_id": 1001, "prb_id": 9}) == b"1001"


def test_result_value_is_one_line_of_json() -> None:
    value = result_value({"msm_id": 1001, "result": [{"rtt": 1.0}], "lts": -1})
    assert b"\n" not in value
    assert json.loads(value) == {"msm_id": 1001, "result": [{"rtt": 1.0}], "lts": -1}


def test_kafka_producer_sends_the_encoded_record_and_flushes() -> None:
    client = FakeKafkaClient()
    producer = KafkaProducer("localhost:9092", client=client)
    producer.produce(TOPIC, b"1001", b"{}")
    producer.close()
    assert client.sent == [(TOPIC, b"1001", b"{}")]
    assert client.flushed == 1
    assert client.closed == 1


def test_the_backfill_produces_every_rest_result_to_the_shared_topic(tmp_path: Path) -> None:
    records = [
        {"msm_id": 1001, "prb_id": 1, "timestamp": 100},
        {"msm_id": 1001, "prb_id": 2, "timestamp": 101},
    ]
    transport = FakeTransport(records)
    client = RipeRestClient(
        "https://example/api/v2",
        limiter=no_wait_limiter(),
        backoff=Backoff(base=0.0, factor=1.0, max_delay=0.0),
        transport=transport,
    )
    producer = RecordingProducer()
    store = CursorStore(tmp_path / "cursor.json")
    backfill = BackfillProducer(
        client, producer, store, topic=TOPIC, window_seconds=900, chunk_seconds=300
    )

    produced = backfill.run([1001], now=1000)

    assert produced == 2
    assert {topic for topic, _, _ in producer.records} == {TOPIC}
    assert [json.loads(value)["prb_id"] for _, _, value in producer.records] == [1, 2]
    assert store.read().get(1001) == 101


def test_a_restart_resumes_from_the_persisted_cursor_not_the_whole_window(
    tmp_path: Path,
) -> None:
    path = tmp_path / "cursor.json"
    store = CursorStore(path)
    cursor = TimepointCursor()
    cursor.advance(1001, 500)
    store.write(cursor)
    transport = FakeTransport([{"msm_id": 1001, "prb_id": 1, "timestamp": 500}])
    client = RipeRestClient(
        "https://example/api/v2",
        limiter=no_wait_limiter(),
        backoff=Backoff(base=0.0, factor=1.0, max_delay=0.0),
        transport=transport,
    )
    backfill = BackfillProducer(
        client, RecordingProducer(), store, topic=TOPIC, window_seconds=900, chunk_seconds=300
    )

    backfill.run([1001], now=1000)

    assert transport.calls[0] == (1001, 500)


def test_the_rest_client_backs_off_and_retries_on_a_rate_limit() -> None:
    scripted = [
        (429, []),
        (200, [{"msm_id": 1001, "prb_id": 1, "timestamp": 7}]),
    ]
    transport = FakeTransport([], scripted=scripted)
    sleeps: list[float] = []

    def sleep(seconds: float) -> None:
        sleeps.append(seconds)

    client = RipeRestClient(
        "https://example/api/v2",
        limiter=RateLimiter(0.0),
        backoff=Backoff(base=2.0, factor=2.0, max_delay=60.0),
        transport=transport,
        sleep=sleep,
    )

    assert client.fetch_results(1001, start=0, stop=1000) == [
        {"msm_id": 1001, "prb_id": 1, "timestamp": 7}
    ]
    assert sleeps == [2.0]


def test_the_rest_client_raises_after_the_retry_budget_is_spent() -> None:
    transport = FakeTransport([], scripted=[(503, [])] * 4)
    client = RipeRestClient(
        "https://example/api/v2",
        limiter=RateLimiter(0.0),
        backoff=Backoff(base=0.0, factor=1.0, max_delay=0.0),
        transport=transport,
        max_retries=3,
    )
    with pytest.raises(RipeRestError, match="503"):
        client.fetch_results(1001, start=0, stop=1000)
