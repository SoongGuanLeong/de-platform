"""The live RIPE Atlas collector.

It opens one long-lived WebSocket, multiplexes the declared subscription set
onto it (the publisher's documented advice, research 01b section 1), produces
each result to the configured topic through the shared Producer, advances the
persisted timepoint cursor, and backs off before reconnecting after a drop. The
transport is injected, so the loop is exercised without the live stream.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from typing import Protocol, runtime_checkable
from urllib.parse import quote

from .config import RipeCollectorConfig
from .cursor import CursorStore, TimepointCursor
from .producer import Producer, result_key, result_value
from .ratelimit import Backoff


class ConnectionClosed(Exception):
    """The WebSocket dropped; the collector backs off and reconnects."""


class RipeStreamError(RuntimeError):
    """The stream reported an error frame the collector cannot ignore."""


@runtime_checkable
class Connection(Protocol):
    def send(self, message: str) -> None: ...

    def recv(self, timeout: float | None = None) -> str: ...


ConnectionFactory = Callable[[str, str], Connection]


class _WebsocketConnection:
    """Adapts a websockets client to the Connection protocol."""

    def __init__(self, websocket, closed_exception) -> None:
        self._websocket = websocket
        self._closed_exception = closed_exception

    def send(self, message: str) -> None:
        self._websocket.send(message)

    def recv(self, timeout: float | None = None) -> str:
        try:
            return self._websocket.recv(timeout=timeout)
        except self._closed_exception as error:
            raise ConnectionClosed(str(error)) from error


def websocket_connection(url: str, client_id: str) -> Connection:
    """The real connection factory: one WebSocket, identified for RIPE."""
    from websockets.exceptions import ConnectionClosed as WsConnectionClosed
    from websockets.sync.client import connect

    separator = "&" if "?" in url else "?"
    full_url = url + separator + "client=" + quote(client_id)
    websocket = connect(
        full_url,
        open_timeout=10,
        close_timeout=5,
        ping_interval=20,
        ping_timeout=20,
        max_size=None,
    )
    return _WebsocketConnection(websocket, WsConnectionClosed)


class Collector:
    def __init__(
        self,
        config: RipeCollectorConfig,
        producer: Producer,
        cursor_store: CursorStore,
        *,
        connection_factory: ConnectionFactory,
        sleep: Callable[[float], None] = time.sleep,
        backoff: Backoff | None = None,
    ) -> None:
        self._config = config
        self._producer = producer
        self._cursor_store = cursor_store
        self._connection_factory = connection_factory
        self._sleep = sleep
        self._backoff = backoff or Backoff(base=1.0, factor=2.0, max_delay=60.0)

    @property
    def topic(self) -> str:
        return self._config.topic

    @property
    def producer(self) -> Producer:
        return self._producer

    def run(self, limit: int | None = None) -> int:
        """Stream until `limit` results are produced, reconnecting on a drop."""
        produced = 0
        cursor = self._cursor_store.read()
        while True:
            connection = self._connection_factory(
                self._config.websocket_url, self._config.client_id
            )
            try:
                self._subscribe(connection)
                self._backoff.reset()
                while True:
                    kind, payload = self._decode(connection.recv())
                    if kind == "atlas_result":
                        self._produce(cursor, payload)
                        produced += 1
                        if limit is not None and produced >= limit:
                            return produced
                    elif kind == "atlas_error":
                        raise RipeStreamError("the stream reported " + str(payload))
            except ConnectionClosed:
                self._sleep(self._backoff.next())

    def _subscribe(self, connection: Connection) -> None:
        for group in self._config.subscription_plan():
            for subscription in group:
                connection.send(json.dumps(subscription.message()))

    def _produce(self, cursor: TimepointCursor, payload) -> None:
        record = dict(payload)
        self._producer.produce(self._config.topic, result_key(record), result_value(record))
        cursor.advance(int(record["msm_id"]), int(record["timestamp"]))
        self._cursor_store.write(cursor)

    @staticmethod
    def _decode(raw: str) -> tuple[str, object]:
        frame = json.loads(raw)
        if not isinstance(frame, list) or len(frame) != 2:
            raise RipeStreamError("unexpected frame: " + raw[:200])
        return str(frame[0]), frame[1]
