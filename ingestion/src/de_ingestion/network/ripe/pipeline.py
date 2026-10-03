"""The collector and the backfill wired to one producer and one topic.

The pipeline is the single composition point: the live subscription and the REST
backfill are handed the same Producer and the same topic, which is what makes
the backfill a producer into the same topic rather than a second writer
(ADR-0014). It backfills the gap from the persisted cursor first, then streams.
"""

from __future__ import annotations

import time
from collections.abc import Callable

from .backfill import BackfillProducer, RipeRestClient
from .collector import Collector, ConnectionFactory, websocket_connection
from .config import RipeCollectorConfig
from .cursor import CursorStore
from .producer import Producer
from .ratelimit import Backoff, RateLimiter


class RipePipeline:
    def __init__(
        self,
        config: RipeCollectorConfig,
        producer: Producer,
        cursor_store: CursorStore,
        *,
        connection_factory: ConnectionFactory | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.config = config
        self.producer = producer
        self.cursor_store = cursor_store
        client = RipeRestClient(
            config.rest_base_url,
            limiter=RateLimiter(config.rest_min_interval_seconds),
            backoff=Backoff(base=1.0, factor=2.0, max_delay=60.0),
        )
        self.backfill = BackfillProducer(
            client,
            producer,
            cursor_store,
            topic=config.topic,
            window_seconds=config.backfill_window_seconds,
            chunk_seconds=config.rest_chunk_seconds,
        )
        self.collector = Collector(
            config,
            producer,
            cursor_store,
            connection_factory=connection_factory or websocket_connection,
            sleep=sleep,
        )

    def backfill_measurements(self) -> list[int]:
        return [
            int(subscription.filters["msm"])
            for subscription in self.config.subscriptions
            if "msm" in subscription.filters
        ]

    def run(self, *, now: int, limit: int | None = None, backfill: bool = True) -> int:
        if backfill:
            self.backfill.run(self.backfill_measurements(), now=now)
        return self.collector.run(limit=limit)
