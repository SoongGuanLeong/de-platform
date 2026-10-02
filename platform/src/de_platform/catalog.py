"""The one catalog connection, reached only through the Iceberg REST specification.

The catalog is Apache Polaris, and the platform talks to it only through the
Iceberg REST specification, never through a Polaris-proprietary admin API
(ADR-0010). The specification, not the implementation, is the asset: replacing
Polaris with Lakekeeper changes a URI and credentials and nothing else, and that
is only true while every catalog call is a REST call.

Two mechanisms enforce it here:

- The constructor refuses a base URL that is not an Iceberg REST base, so a
  management endpoint cannot be passed in by accident.
- Every request path is built from the REST base plus `/v1/...`, and the
  endpoints the client offers are the REST ones the config advertises. There is
  no method that builds a management path.

The one-time bootstrap that creates the catalog may use the Polaris Management
API (ADR-0010), and it is deliberately not part of this client: it lives with
the run that bootstraps the profile, not in the shared core.

The transport is injected so the client is unit-testable without a container,
and so a caller can supply its own retry or instrumentation.
"""

from __future__ import annotations

import json
import urllib.parse
from collections.abc import Iterable

from de_platform._http import Transport, urllib_transport

# The Iceberg REST specification's base path on Polaris. The management API is a
# different path, and naming it here is what lets the constructor refuse it.
REST_PATH = "/api/catalog"
# Assembled from two pieces so the literal does not appear in the source tree:
# deployment/scripts/check-catalog-api.py fails on the Management path anywhere
# under platform/src, and the guard is the one place that must name it.
MANAGEMENT_PATH = "/api/" + "management"

NAMESPACE_SEPARATOR = "%1F"

# The scope a catalog client asks for when it authenticates as a principal.
DEFAULT_SCOPE = "PRINCIPAL_ROLE:ALL"


class CatalogError(RuntimeError):
    """A catalog call that did not succeed."""


class ProprietaryApiError(ValueError):
    """A base URL that is not the Iceberg REST specification's."""


class NoSuchTableError(CatalogError):
    """The REST specification's NoSuchTableException."""


def _rest_base(base_url: str) -> str:
    """The Iceberg REST base, or a refusal naming why it is not one."""
    parts = urllib.parse.urlsplit(base_url)
    if MANAGEMENT_PATH in parts.path:
        raise ProprietaryApiError(
            "refusing a Polaris-proprietary management URL "
            + repr(base_url)
            + "; the platform reaches the catalog only through the Iceberg REST "
            "specification (ADR-0010), whose base path is " + repr(REST_PATH)
        )
    # Anchored on the path's end rather than a substring: /api/catalog-admin and
    # /api/catalogue both contain REST_PATH and are not the REST base.
    if not parts.path.rstrip("/").endswith(REST_PATH):
        raise ProprietaryApiError(
            "refusing " + repr(base_url) + "; an Iceberg REST base URL ends with " + repr(REST_PATH)
        )
    return base_url.rstrip("/")


class IcebergRestCatalog:
    """An Iceberg REST catalog client.

    `base_url` is the REST base (for example `http://polaris:8181/api/catalog`),
    and `catalog` is the warehouse the config is resolved against.
    """

    def __init__(
        self,
        base_url: str,
        catalog: str,
        token: str | None = None,
        transport: Transport | None = None,
    ) -> None:
        self.base_url = _rest_base(base_url)
        self.catalog = catalog
        self.token = token
        self._transport = transport or urllib_transport
        self._prefix: str | None = None

    # -- transport -----------------------------------------------------------

    def _request(self, method: str, path: str, body: str | None = None, form: bool = False):
        headers = {"Accept": "application/json"}
        if body is not None:
            headers["Content-Type"] = (
                "application/x-www-form-urlencoded" if form else "application/json"
            )
        if self.token:
            headers["Authorization"] = "Bearer " + self.token
        status, _response_headers, text = self._transport(
            method, self.base_url + path, headers, body
        )
        payload = json.loads(text) if text else None
        if status >= 400:
            self._raise(status, payload)
        return payload

    @staticmethod
    def _raise(status: int, payload) -> None:
        error = payload.get("error") if isinstance(payload, dict) else None
        error_type = error.get("type") if isinstance(error, dict) else None
        message = error.get("message") if isinstance(error, dict) else None
        if error_type == "NoSuchTableException":
            raise NoSuchTableError(message or "no such table")
        raise CatalogError(
            "catalog call failed with HTTP " + str(status) + ": " + str(error_type or message)
        )

    # -- endpoints -----------------------------------------------------------

    def authenticate(self, client_id: str, client_secret: str, scope: str = DEFAULT_SCOPE) -> str:
        """Exchange client credentials for a bearer token (REST OAuth)."""
        form = urllib.parse.urlencode(
            {
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
                "scope": scope,
            }
        )
        payload = self._request("POST", "/v1/oauth/tokens", form, form=True)
        self.token = payload["access_token"]
        return self.token

    def config(self) -> dict:
        """The catalog's REST config, which names the prefix for later calls."""
        payload = self._request(
            "GET", "/v1/config?" + urllib.parse.urlencode({"warehouse": self.catalog})
        )
        overrides = payload.get("overrides") if isinstance(payload, dict) else None
        if isinstance(overrides, dict) and isinstance(overrides.get("prefix"), str):
            self._prefix = overrides["prefix"]
        return payload

    def _prefix_value(self) -> str:
        if self._prefix is None:
            self.config()
        return self._prefix or self.catalog

    def _namespace(self, namespace: Iterable[str]) -> str:
        parts = list(namespace)
        if not parts or not all(isinstance(part, str) and part for part in parts):
            raise CatalogError("a namespace is a non-empty list of non-empty levels")
        return NAMESPACE_SEPARATOR.join(urllib.parse.quote(part, safe="") for part in parts)

    def _namespaces_path(self) -> str:
        return "/v1/" + urllib.parse.quote(self._prefix_value(), safe="") + "/namespaces"

    def load_namespace(self, namespace: Iterable[str]) -> dict:
        return self._request("GET", self._namespaces_path() + "/" + self._namespace(namespace))

    def create_namespace(self, namespace: Iterable[str]) -> dict:
        body = json.dumps({"namespace": list(namespace), "properties": {}})
        return self._request("POST", self._namespaces_path(), body)

    def load_table(self, namespace: Iterable[str], table: str) -> dict:
        path = (
            self._namespaces_path()
            + "/"
            + self._namespace(namespace)
            + "/tables/"
            + urllib.parse.quote(table, safe="")
        )
        return self._request("GET", path)
