"""The catalog connection speaks only the Iceberg REST specification (issue #33).

A table is resolved through the Iceberg REST specification and never through a
Polaris-proprietary admin API, so the client refuses a management base URL at
construction and every request it builds is under the REST path. The transport
is injected, so these are unit tests: no container and no network.

The endpoint shapes are the ones Polaris 1.7.0 served when probed live on
2026-10-02: `POST /api/catalog/v1/oauth/tokens`, `GET /api/catalog/v1/config`,
and the `prefix` the config returns, with `%1F` as the namespace separator.
"""

from __future__ import annotations

import pytest
from de_platform import catalog

REST = "http://polaris:8181/api/catalog"


class Recorder:
    """A transport that records each request and replays a scripted response."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, method, url, headers, body):
        self.calls.append((method, url, dict(headers), body))
        return self.responses.pop(0)


def test_a_polaris_management_url_is_refused():
    with pytest.raises(catalog.ProprietaryApiError):
        catalog.IcebergRestCatalog("http://polaris:8181/api/management/v1", catalog="de_platform")


def test_a_rest_base_url_is_accepted():
    client = catalog.IcebergRestCatalog(REST, catalog="de_platform")
    assert client.base_url == REST


def test_a_custom_rest_base_path_is_accepted():
    # A catalog swap (ADR-0010) changes the URI, so the REST base path is not
    # pinned to Polaris's /api/catalog; only the Management API is refused.
    client = catalog.IcebergRestCatalog("http://lakekeeper:8181/catalog", catalog="de_platform")
    assert client.base_url == "http://lakekeeper:8181/catalog"


def test_authenticate_posts_the_client_credentials_grant():
    recorder = Recorder([(200, {}, '{"access_token": "t0ken", "token_type": "bearer"}')])
    client = catalog.IcebergRestCatalog(REST, catalog="de_platform", transport=recorder)
    client.authenticate("root", "s3cr3t")
    method, url, _headers, body = recorder.calls[0]
    assert (method, url) == ("POST", REST + "/v1/oauth/tokens")
    assert "grant_type=client_credentials" in body
    assert "client_id=root" in body
    assert "client_secret=s3cr3t" in body
    assert client.token == "t0ken"


def test_config_asks_for_the_warehouse():
    recorder = Recorder([(200, {}, '{"overrides": {"prefix": "de_platform"}}')])
    client = catalog.IcebergRestCatalog(REST, catalog="de_platform", transport=recorder)
    assert client.config()["overrides"]["prefix"] == "de_platform"
    assert recorder.calls[0][1] == REST + "/v1/config?warehouse=de_platform"


def test_the_defaults_prefix_is_used_when_overrides_names_none():
    recorder = Recorder(
        [
            (200, {}, '{"defaults": {"prefix": "de_platform"}}'),
            (200, {}, '{"namespace": ["commerce", "gold"], "properties": {}}'),
        ]
    )
    client = catalog.IcebergRestCatalog(REST, catalog="de_platform", transport=recorder)
    client.load_namespace(("commerce", "gold"))
    assert recorder.calls[1][1] == REST + "/v1/de_platform/namespaces/commerce%1Fgold"


def test_the_overrides_prefix_wins_over_defaults():
    recorder = Recorder(
        [
            (200, {}, '{"defaults": {"prefix": "a"}, "overrides": {"prefix": "b"}}'),
            (200, {}, '{"namespace": ["commerce", "gold"], "properties": {}}'),
        ]
    )
    client = catalog.IcebergRestCatalog(REST, catalog="de_platform", transport=recorder)
    client.load_namespace(("commerce", "gold"))
    assert recorder.calls[1][1] == REST + "/v1/b/namespaces/commerce%1Fgold"


def test_a_catalog_with_no_prefix_serves_namespaces_at_the_root():
    recorder = Recorder(
        [
            (200, {}, "{}"),
            (200, {}, '{"namespace": ["commerce", "gold"], "properties": {}}'),
        ]
    )
    client = catalog.IcebergRestCatalog(REST, catalog="de_platform", transport=recorder)
    client.load_namespace(("commerce", "gold"))
    assert recorder.calls[1][1] == REST + "/v1/namespaces/commerce%1Fgold"


def test_load_namespace_uses_the_unit_separator():
    recorder = Recorder(
        [
            (200, {}, '{"overrides": {"prefix": "de_platform"}}'),
            (200, {}, '{"namespace": ["commerce", "gold"], "properties": {}}'),
        ]
    )
    client = catalog.IcebergRestCatalog(REST, catalog="de_platform", transport=recorder)
    namespace = client.load_namespace(("commerce", "gold"))
    assert namespace["namespace"] == ["commerce", "gold"]
    assert recorder.calls[1][1] == REST + "/v1/de_platform/namespaces/commerce%1Fgold"


def test_create_namespace_posts_the_namespace():
    recorder = Recorder(
        [
            (200, {}, '{"overrides": {"prefix": "de_platform"}}'),
            (200, {}, '{"namespace": ["commerce", "gold"], "properties": {}}'),
        ]
    )
    client = catalog.IcebergRestCatalog(REST, catalog="de_platform", transport=recorder)
    client.create_namespace(("commerce", "gold"))
    method, url, _headers, body = recorder.calls[1]
    assert (method, url) == ("POST", REST + "/v1/de_platform/namespaces")
    assert body == '{"namespace": ["commerce", "gold"], "properties": {}}'


def test_load_table_addresses_the_rest_table_endpoint():
    recorder = Recorder(
        [
            (200, {}, '{"overrides": {"prefix": "de_platform"}}'),
            (200, {}, '{"metadata-location": "s3://warehouse/x/metadata/00000.json"}'),
        ]
    )
    client = catalog.IcebergRestCatalog(REST, catalog="de_platform", transport=recorder)
    table = client.load_table(("commerce", "gold"), "fact_order_line")
    assert table["metadata-location"].endswith("00000.json")
    assert recorder.calls[1][1] == (
        REST + "/v1/de_platform/namespaces/commerce%1Fgold/tables/fact_order_line"
    )


def test_a_missing_table_is_the_rest_no_such_table_error():
    recorder = Recorder(
        [
            (200, {}, '{"overrides": {"prefix": "de_platform"}}'),
            (404, {}, '{"error": {"message": "x", "type": "NoSuchTableException", "code": 404}}'),
        ]
    )
    client = catalog.IcebergRestCatalog(REST, catalog="de_platform", transport=recorder)
    with pytest.raises(catalog.NoSuchTableError):
        client.load_table(("commerce", "gold"), "absent")


def test_the_token_is_sent_as_a_bearer_header():
    recorder = Recorder([(200, {}, '{"overrides": {"prefix": "de_platform"}}')])
    client = catalog.IcebergRestCatalog(REST, catalog="de_platform", transport=recorder)
    client.token = "t0ken"
    client.config()
    assert recorder.calls[0][2]["Authorization"] == "Bearer t0ken"
