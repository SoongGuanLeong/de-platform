"""The OpenLineage configuration and the one-event emitter (issue #33).

The platform emits OpenLineage, the portable asset, rather than a backend API
(ADR-0010's reasoning applied to lineage; docs/technology-selection.md).
The event is built to the spec and POSTed to the configured endpoint.

The dataset namespace names the platform rather than the catalog, so a catalog
swap (ADR-0010) does not fork lineage identity. The read-back that proves an
event is visible in Marquez needs Marquez, which lands with the lineage work in
Phase 7, so it is gated; these are unit tests and the smoke run uses a local
receiver. The transport is injected.
"""

from __future__ import annotations

import json

from de_platform import lineage

CONFIG = lineage.LineageConfig(
    namespace="de-platform", endpoint="http://marquez:5000/api/v1/lineage"
)


class Recorder:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, method, url, headers, body):
        self.calls.append((method, url, dict(headers), body))
        return self.responses.pop(0)


def test_the_event_names_the_run_job_and_datasets():
    event = lineage.build_run_event(
        CONFIG,
        job_name="commerce.gold.fact_order_line",
        run_id="5c9d1f2e-0000-4000-8000-000000000000",
        event_time="2026-10-02T00:00:00Z",
        inputs=["tpc-c.public.order_line"],
        outputs=["commerce.gold.fact_order_line"],
    )
    assert event["eventType"] == "COMPLETE"
    assert event["job"] == {"namespace": "de-platform", "name": "commerce.gold.fact_order_line"}
    assert event["inputs"] == [{"namespace": "de-platform", "name": "tpc-c.public.order_line"}]
    assert event["outputs"] == [
        {"namespace": "de-platform", "name": "commerce.gold.fact_order_line"}
    ]
    assert event["run"]["runId"] == "5c9d1f2e-0000-4000-8000-000000000000"
    assert event["producer"] == lineage.PRODUCER
    assert event["schemaURL"].startswith("https://openlineage.io/spec/")


def test_a_run_id_is_generated_when_none_is_given():
    event = lineage.build_run_event(
        CONFIG, job_name="j", run_id=None, event_time="2026-10-02T00:00:00Z"
    )
    assert event["run"]["runId"]


def test_emit_posts_the_event_to_the_configured_endpoint():
    event = lineage.build_run_event(
        CONFIG, job_name="j", run_id="abc", event_time="2026-10-02T00:00:00Z"
    )
    recorder = Recorder([(201, {}, "")])
    emitter = lineage.OpenLineageEmitter(CONFIG, transport=recorder)
    run_id = emitter.emit(event)
    method, url, headers, body = recorder.calls[0]
    assert run_id == "abc"
    assert (method, url) == ("POST", "http://marquez:5000/api/v1/lineage")
    assert headers["Content-Type"] == "application/json"
    assert json.loads(body)["job"]["name"] == "j"
