"""The REST backfill, a producer into the same topic as the live feed.

The live RIPE stream is at-most-once and drops results under backpressure, so
the REST results endpoint is the correctness path: it is replayed into the same
Kafka topic through the same Producer, and the collector's job writes the table.
This module therefore imports no table writer, and its only sink is the
Producer it is given (ADR-0014, docs/streaming-jobs.md section 8).
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .cursor import CursorStore
from .producer import Producer, result_key, result_value
from .ratelimit import Backoff, RateLimiter

# 416 (a stale range) and 429 (rate limited) are the publisher's documented
# back-pressure signals, alongside a 5xx; all are retried with backoff.
RETRYABLE_STATUS = frozenset({416, 429}) | frozenset(range(500, 600))


class RipeRestError(RuntimeError):
    """The results endpoint refused a request the backfill cannot retry."""


class RipeRestClient:
    """Fetches measurement results, respecting the declared request rate."""

    def __init__(
        self,
        base_url: str,
        *,
        limiter: RateLimiter,
        backoff: Backoff,
        transport: Callable[[str], tuple[int, object]] | None = None,
        sleep: Callable[[float], None] = time.sleep,
        max_retries: int = 3,
        user_agent: str = "de-platform-ripe-collector/0.0",
    ) -> None:
        self._base = base_url.rstrip("/")
        self._limiter = limiter
        self._backoff = backoff
        self._transport = transport or self._http_get
        self._sleep = sleep
        self._max_retries = max_retries
        self._user_agent = user_agent

    def _http_get(self, url: str) -> tuple[int, object]:
        request = Request(url, headers={"User-Agent": self._user_agent})
        try:
            with urlopen(request, timeout=30) as response:
                return response.status, json.load(response)
        except HTTPError as error:
            return error.code, []
        except URLError as error:
            raise RipeRestError("request failed: " + str(error)) from error

    def fetch_results(self, msm_id: int, *, start: int, stop: int) -> list[dict]:
        """Every result in the inclusive range `[start, stop]`.

        The endpoint ignores `limit` for a ranged request and returns the whole
        range (verified 2026-10-03), so the range itself is the bound and the
        caller chunks it by time. `stop` also excludes a probe whose clock runs
        ahead of the server's, which the endpoint would otherwise reject as a
        future start on the next request.
        """
        url = (
            self._base
            + "/measurements/"
            + str(msm_id)
            + "/results/?start="
            + str(start)
            + "&stop="
            + str(stop)
        )
        attempts = 0
        while True:
            self._limiter.wait()
            status, body = self._transport(url)
            if status == 200:
                self._backoff.reset()
                return list(body)
            if status in RETRYABLE_STATUS and attempts < self._max_retries:
                self._sleep(self._backoff.next())
                attempts += 1
                continue
            raise RipeRestError(url + " returned " + str(status))


class BackfillProducer:
    """Replays REST history into the topic, resuming from the persisted cursor."""

    def __init__(
        self,
        client: RipeRestClient,
        producer: Producer,
        cursor_store: CursorStore,
        *,
        topic: str,
        window_seconds: int,
        chunk_seconds: int,
    ) -> None:
        self._client = client
        self._producer = producer
        self._cursor_store = cursor_store
        self._topic = topic
        self._window = window_seconds
        self._chunk = chunk_seconds

    @property
    def topic(self) -> str:
        return self._topic

    @property
    def producer(self) -> Producer:
        return self._producer

    def run(self, msm_ids, *, now: int) -> int:
        """Produce `[cursor, now]` for each measurement, in time chunks.

        Each request is bounded by `stop`, so the response is a bounded slice
        rather than the whole history, and the cursor is persisted after each
        chunk, so a restart resumes from the last produced result.
        """
        cursor = self._cursor_store.read()
        produced = 0
        for msm_id in msm_ids:
            start = cursor.resume_start(msm_id, now=now, window=self._window)
            while start <= now:
                stop = min(start + self._chunk - 1, now)
                records = self._client.fetch_results(msm_id, start=start, stop=stop)
                for record in records:
                    self._producer.produce(self._topic, result_key(record), result_value(record))
                    cursor.advance(int(record["msm_id"]), int(record["timestamp"]))
                    produced += 1
                self._cursor_store.write(cursor)
                start = stop + 1
        self._cursor_store.write(cursor)
        return produced
