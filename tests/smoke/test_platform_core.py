"""The platform core's smoke run (issue #33).

One run exercises all four things the shared core does, and it is the only path
that does: the catalog resolves a namespace and a table through the Iceberg REST
specification, the contract loader returns a gold contract's schema, the naming
conventions are applied from one place, and one OpenLineage event is emitted.

The catalog is real: postgres and polaris come up, and every call the core makes
is an Iceberg REST call. The one-time bootstrap that creates the catalog uses
the Polaris Management API, which ADR-0010 permits for the bootstrap alone; the
shared core never does, and its client refuses a management URL.

Two things this run does not do, both recorded rather than implied:

- It does not create a table. Polaris writes a new table's metadata to the
  warehouse, which needs the region, the SeaweedFS STS role and the catalog
  grants the credential-vending work sets up in Phase 7. The run resolves the
  table endpoint and asserts the specification's own NoSuchTableException, so
  the table is addressed through REST, and the create-and-load path is gated.
- It does not read the event back from Marquez, which also lands in Phase 7.
  The emitter posts to a local receiver, so the emission is proven and the
  read-back is the registered limitation.
"""

from __future__ import annotations

import json
import os
import threading
import urllib.error
import urllib.request
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from de_governance.yaml_loader import load_mapping
from de_platform import catalog, contracts, lineage, naming

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FIXTURE = os.path.join(ROOT, "tests/smoke/fixtures/contracts/commerce/gold/fact_order_line.yml")
CATALOG = "de_platform"


def _bootstrap_catalog(base_url: str, token: str) -> None:
    """Create the catalog, through the Management API, as the one-time bootstrap.

    Idempotent: a catalog that already exists is left alone.
    """
    endpoint = base_url.replace("/api/catalog", "/api/management") + "/v1/catalogs"
    body = json.dumps(
        {
            "catalog": {
                "name": CATALOG,
                "type": "INTERNAL",
                "properties": {"default-base-location": "s3://warehouse/"},
                "storageConfigInfo": {
                    "storageType": "S3",
                    "allowedLocations": ["s3://warehouse/"],
                    "endpoint": "http://seaweedfs:8333",
                    "pathStyleAccess": True,
                    "region": "us-east-1",
                },
            }
        }
    )
    request = urllib.request.Request(
        endpoint,
        data=body.encode("utf-8"),
        method="POST",
        headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30):
            return
    except urllib.error.HTTPError as error:
        if error.code != 409:
            raise


class _Receiver(BaseHTTPRequestHandler):
    """A one-shot HTTP receiver standing in for Marquez, off the claim's path."""

    def do_POST(self):  # noqa: N802 (http.server's naming)
        length = int(self.headers.get("Content-Length", "0"))
        self.server.received.append(json.loads(self.rfile.read(length)))
        self.send_response(201)
        self.end_headers()

    def log_message(self, *args):  # keep the smoke output clean
        return


def _emit_to_a_local_receiver(event: dict) -> tuple[str, dict]:
    server = HTTPServer(("127.0.0.1", 0), _Receiver)
    server.received = []
    thread = threading.Thread(target=server.handle_request, daemon=True)
    thread.start()
    config = lineage.LineageConfig(
        namespace=lineage.DEFAULT_NAMESPACE,
        endpoint="http://127.0.0.1:" + str(server.server_port) + "/api/v1/lineage",
    )
    run_id = lineage.OpenLineageEmitter(config).emit(event)
    thread.join(timeout=15)
    server.server_close()
    assert server.received, "the emitter posted no event to the receiver"
    return run_id, server.received[0]


def test_platform_core(polaris_rest):
    # 1. The catalog, through the Iceberg REST specification only.
    secret = polaris_rest["secret"]
    _bootstrap_catalog(polaris_rest["base_url"], _management_token(polaris_rest, secret))
    client = catalog.IcebergRestCatalog(polaris_rest["base_url"], catalog=CATALOG)
    client.authenticate("root", secret)
    assert client.config()["overrides"]["prefix"] == CATALOG

    client.create_namespace(("commerce",))
    client.create_namespace(("commerce", "gold"))
    resolved = client.load_namespace(("commerce", "gold"))
    assert resolved["namespace"] == ["commerce", "gold"]

    # The table endpoint answers with the specification's own error type, so the
    # table is addressed through REST. Creating one needs Phase 7's catalog
    # bootstrap; that is gated, not silently skipped.
    with pytest.raises(catalog.NoSuchTableError):
        client.load_table(("commerce", "gold"), "fact_order_line")

    # 2. The contract loader, through the repository's one YAML entry point.
    contract = contracts.load_contract(FIXTURE, load_mapping)
    assert [column.name for column in contract.schema] == [
        "w_id",
        "d_id",
        "o_id",
        "ol_number",
        "ol_quantity",
        "ol_amount",
        "o_entry_d",
    ]

    # 3. The naming conventions, applied from one place.
    assert naming.parse_table(contract.table) == ("commerce", "gold", "fact_order_line")
    assert contract.table == naming.iceberg_table("commerce", "gold", "fact_order_line")
    assert naming.clickhouse_database(contract.spine) == "commerce"
    assert naming.cdc_topic("tpc-c", "public", "order_line") == "tpc-c.public.order_line"
    assert naming.cdc_subject("tpc-c.public.order_line") == "tpc-c.public.order_line-value"

    # 4. One OpenLineage event, emitted.
    config = lineage.LineageConfig(
        namespace=lineage.DEFAULT_NAMESPACE, endpoint="http://127.0.0.1:0/api/v1/lineage"
    )
    event = lineage.build_run_event(
        config,
        job_name=contract.table,
        event_time=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        inputs=["tpc-c.public.order_line"],
        outputs=[contract.table],
    )
    run_id, received = _emit_to_a_local_receiver(event)
    assert received["run"]["runId"] == run_id
    assert received["job"]["name"] == contract.table
    assert received["outputs"] == [{"namespace": "de-platform", "name": contract.table}]


def _management_token(polaris_rest: dict, secret: str) -> str:
    """A token for the bootstrap call only. The shared core authenticates itself."""
    client = catalog.IcebergRestCatalog(polaris_rest["base_url"], catalog=CATALOG)
    return client.authenticate("root", secret)
