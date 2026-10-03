"""The producer both the live subscription and the REST backfill write through.

There is one Producer interface and one topic. The live collector and the REST
backfill are both handed the same instance, so the backfill is a producer into
the same topic rather than a second writer to the table (ADR-0014). The Kafka
adapter is the only place the kafka client is imported, so the rest of the
package is importable and testable without a broker.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Protocol, runtime_checkable


@runtime_checkable
class Producer(Protocol):
    """A sink that accepts a topic, a key and a value."""

    def produce(self, topic: str, key: bytes | None, value: bytes) -> None: ...


def result_key(record: Mapping) -> bytes:
    """Key a result by its measurement, so one measurement stays ordered."""
    return str(record["msm_id"]).encode("utf-8")


def result_value(record: Mapping) -> bytes:
    """One line of compact JSON, the shape the topic carries."""
    return json.dumps(record, separators=(",", ":"), sort_keys=True).encode("utf-8")


class KafkaProducer:
    """A thin adapter over kafka-python's producer."""

    def __init__(
        self,
        bootstrap_servers: str,
        *,
        client_id: str = "de-platform-ripe-collector",
        client=None,
    ) -> None:
        self._client = client if client is not None else self._build(bootstrap_servers, client_id)

    @staticmethod
    def _build(bootstrap_servers: str, client_id: str):
        from kafka import KafkaProducer as _KafkaProducer

        return _KafkaProducer(
            bootstrap_servers=bootstrap_servers,
            client_id=client_id,
            acks="all",
            retries=5,
            linger_ms=50,
        )

    def produce(self, topic: str, key: bytes | None, value: bytes) -> None:
        self._client.send(topic, key=key, value=value)

    def close(self) -> None:
        self._client.flush()
        self._client.close()
