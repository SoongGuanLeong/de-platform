"""The RIPE Atlas collector's declared configuration.

The subscription set, the publisher's connection cap and the topic both the
live subscription and the REST backfill produce to are declared in
`ripe-collector.yaml` beside this module, and read through the repository's one
strict YAML entry point (de_governance.yaml_loader), so a duplicated key is a
load error rather than a silently shadowed value.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from de_governance.yaml_loader import load_mapping

DEFAULT_CONFIG_PATH = Path(__file__).with_name("ripe-collector.yaml")

# The publisher's documented cap on concurrent WebSockets per client IP
# (docs/research/01b-datasets-event-streaming.md section 1). A config that
# declares more is rejected rather than trusted.
RIPE_MAX_WEBSOCKET_CONNECTIONS_PER_IP = 16


class ConfigError(ValueError):
    """A declared collector configuration that cannot be run as written."""


@dataclass(frozen=True)
class Subscription:
    """One `atlas_subscribe` entry: a stream type plus its filters."""

    stream_type: str
    filters: Mapping[str, object] = field(default_factory=dict)

    def message(self) -> list:
        """The documented frame: `["atlas_subscribe", {"streamType": ..., ...}]`."""
        payload: dict = {"streamType": self.stream_type}
        payload.update(self.filters)
        return ["atlas_subscribe", payload]


@dataclass(frozen=True)
class RipeCollectorConfig:
    topic: str
    websocket_url: str
    client_id: str
    max_connections_per_ip: int
    connections: int
    max_subscriptions_per_connection: int
    rest_base_url: str
    rest_min_interval_seconds: float
    rest_chunk_seconds: int
    backfill_window_seconds: int
    subscriptions: tuple[Subscription, ...]

    def subscription_plan(self) -> tuple[tuple[Subscription, ...], ...]:
        """The declared set, multiplexed onto the declared connections.

        Raises ConfigError when the plan would exceed the publisher's
        connection cap, or when the set does not fit the declared sockets.
        """
        if self.connections < 1:
            raise ConfigError("connections must be at least 1, got " + repr(self.connections))
        if self.connections > self.max_connections_per_ip:
            raise ConfigError(
                "the plan opens "
                + str(self.connections)
                + " connections, above the publisher's documented cap of "
                + str(self.max_connections_per_ip)
            )
        if self.max_subscriptions_per_connection < 1:
            raise ConfigError("max_subscriptions_per_connection must be at least 1")
        per = self.max_subscriptions_per_connection
        chunks = tuple(
            tuple(self.subscriptions[i : i + per]) for i in range(0, len(self.subscriptions), per)
        )
        if len(chunks) > self.connections:
            raise ConfigError(
                "the declared set needs "
                + str(len(chunks))
                + " connections, above the declared "
                + str(self.connections)
                + "; raise connections or max_subscriptions_per_connection"
            )
        return chunks


def _required(mapping: Mapping, key: str, where: str):
    if key not in mapping:
        raise ConfigError(where + " is missing " + repr(key))
    return mapping[key]


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> RipeCollectorConfig:
    """Read and validate the declared collector configuration."""
    with open(path, encoding="utf-8") as handle:
        document = load_mapping(handle)
    if not isinstance(document, dict):
        raise ConfigError(str(path) + " is not a mapping")

    websocket = _required(document, "websocket", str(path))
    rest = _required(document, "rest", str(path))
    raw_subscriptions = _required(document, "subscriptions", str(path))
    if not isinstance(raw_subscriptions, list) or not raw_subscriptions:
        raise ConfigError(str(path) + ": subscriptions must be a non-empty list")

    subscriptions = []
    for index, entry in enumerate(raw_subscriptions):
        where = str(path) + ": subscriptions[" + str(index) + "]"
        if not isinstance(entry, dict):
            raise ConfigError(where + " is not a mapping")
        stream_type = _required(entry, "stream_type", where)
        filters = {key: value for key, value in entry.items() if key != "stream_type"}
        subscriptions.append(Subscription(stream_type=str(stream_type), filters=filters))

    config = RipeCollectorConfig(
        topic=str(_required(document, "topic", str(path))),
        websocket_url=str(_required(websocket, "url", str(path) + ": websocket")),
        client_id=str(_required(websocket, "client_id", str(path) + ": websocket")),
        max_connections_per_ip=int(
            _required(websocket, "max_connections_per_ip", str(path) + ": websocket")
        ),
        connections=int(_required(websocket, "connections", str(path) + ": websocket")),
        max_subscriptions_per_connection=int(
            _required(websocket, "max_subscriptions_per_connection", str(path) + ": websocket")
        ),
        rest_base_url=str(_required(rest, "base_url", str(path) + ": rest")),
        rest_min_interval_seconds=float(
            _required(rest, "min_interval_seconds", str(path) + ": rest")
        ),
        rest_chunk_seconds=int(_required(rest, "chunk_seconds", str(path) + ": rest")),
        backfill_window_seconds=int(
            _required(rest, "backfill_window_seconds", str(path) + ": rest")
        ),
        subscriptions=tuple(subscriptions),
    )
    if config.max_connections_per_ip > RIPE_MAX_WEBSOCKET_CONNECTIONS_PER_IP:
        raise ConfigError(
            "max_connections_per_ip "
            + str(config.max_connections_per_ip)
            + " exceeds the publisher's documented cap of "
            + str(RIPE_MAX_WEBSOCKET_CONNECTIONS_PER_IP)
        )
    config.subscription_plan()
    return config
