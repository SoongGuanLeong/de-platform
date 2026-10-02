"""The OpenLineage emission configuration, defined once.

Lineage is emitted by the pipeline rather than maintained by hand, and the
portable asset is the OpenLineage specification rather than any one backend
(docs/technology-selection.md): the same event can be pointed at Marquez,
DataHub or a file, because all of them consume the spec. This module fixes the
parts of that emission that are shared - the producer, the schema URL, the
dataset namespace and the transport - so every path emits the same shape.

**The namespace names the platform, not the catalog.** A dataset namespace of
`de-platform` keeps lineage identity stable across the catalog swap ADR-0010
exists to make cheap; naming it after Polaris would fork every dataset's
identity the day Lakekeeper is used.

**What this does not do.** It does not read lineage back. The evidence that an
event is *visible in Marquez* needs Marquez, which lands with the lineage work
in Phase 7; until then the smoke run posts to a local receiver, and the
Marquez read-back is a registered limitation rather than an unstated one.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterable
from dataclasses import dataclass

from de_platform._http import Transport, urllib_transport

# The repository that produces the event, per the OpenLineage spec's producer
# field: a URI naming the producer, not the consumer.
PRODUCER = "https://github.com/SoongGuanLeong/de-platform"

# OpenLineage 1.53.0 emits the 2-0-2 schema.
SCHEMA_URL = "https://openlineage.io/spec/2-0-2/OpenLineage.json#/$defs/RunEvent"

# The platform's stable lineage namespace (see the module docstring).
DEFAULT_NAMESPACE = "de-platform"

# Marquez's OpenLineage HTTP endpoint. The default is where Marquez will listen
# once it lands in Phase 7; a run overrides it.
DEFAULT_ENDPOINT = "http://marquez:5000/api/v1/lineage"


class LineageError(RuntimeError):
    """An emission that the endpoint did not accept."""


@dataclass(frozen=True)
class LineageConfig:
    """The emission configuration every path shares."""

    namespace: str = DEFAULT_NAMESPACE
    endpoint: str = DEFAULT_ENDPOINT
    producer: str = PRODUCER


def dataset(config: LineageConfig, name: str) -> dict:
    """An OpenLineage dataset reference in the platform's namespace."""
    return {"namespace": config.namespace, "name": name}


def build_run_event(
    config: LineageConfig,
    job_name: str,
    event_time: str,
    run_id: str | None = None,
    inputs: Iterable[str] = (),
    outputs: Iterable[str] = (),
    event_type: str = "COMPLETE",
) -> dict:
    """Build one OpenLineage run event.

    `event_time` is a required ISO-8601 UTC instant, because the schema the
    event declares requires one: it is passed in rather than read from the clock
    so an event is reproducible, and it has no default that could emit a null.
    """
    event: dict = {
        "eventType": event_type,
        "eventTime": event_time,
        "run": {"runId": run_id or str(uuid.uuid4())},
        "job": {"namespace": config.namespace, "name": job_name},
        "inputs": [dataset(config, name) for name in inputs],
        "outputs": [dataset(config, name) for name in outputs],
        "producer": config.producer,
        "schemaURL": SCHEMA_URL,
    }
    return event


class OpenLineageEmitter:
    """Posts one OpenLineage event to the configured endpoint."""

    def __init__(self, config: LineageConfig, transport: Transport | None = None) -> None:
        self.config = config
        self._transport = transport or urllib_transport

    def emit(self, event: dict) -> str:
        """Emit an event and return its run id."""
        body = json.dumps(event)
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        status, _response_headers, text = self._transport(
            "POST", self.config.endpoint, headers, body
        )
        if status >= 400:
            raise LineageError(
                "the lineage endpoint "
                + self.config.endpoint
                + " returned HTTP "
                + str(status)
                + ": "
                + text
            )
        return event["run"]["runId"]
