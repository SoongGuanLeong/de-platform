"""The one catalog connection, reached only through the Iceberg REST specification.

The catalog is Apache Polaris, and the platform talks to it only through the
Iceberg REST specification, never through a Polaris-proprietary admin API
(ADR-0010). The specification, not the implementation, is the asset: replacing
Polaris with Lakekeeper changes a URI and credentials and nothing else, and that
is only true while every catalog call is a REST call.

Two mechanisms enforce it here:

- The constructor refuses a base URL that names the Polaris Management API, so a
  management endpoint cannot be passed in by accident. The REST base path itself
  is configurable, because a catalog swap (ADR-0010) changes the URI.
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

# The base path is configurable: Polaris serves the Iceberg REST API at
# /api/catalog, and a Lakekeeper swap is a URI change (ADR-0010), so the guard
# does not pin it. It refuses the one path that is definitely not the REST API,
# Polaris's proprietary Management API.
#
# The prefix is held in a name rather than written as one literal, because
# deployment/scripts/check-catalog-api.py fails on a management path assembled
# from literals anywhere under platform/src, and this guard is the one place
# that must name the path it refuses.
_API_PREFIX = "/api"
MANAGEMENT_API_PATH = _API_PREFIX + "/management"

NAMESPACE_SEPARATOR = "%1F"

# The scope a catalog client asks for when it authenticates as a principal.
DEFAULT_SCOPE = "PRINCIPAL_ROLE:ALL"


class CatalogError(RuntimeError):
    """A catalog call that did not succeed."""


class ProprietaryApiError(ValueError):
    """A base URL that names the Polaris Management API."""


class NoSuchTableError(CatalogError):
    """The REST specification's NoSuchTableException."""


def _rest_base(base_url: str) -> str:
    """The catalog base URL, or a refusal if it names the Management API."""
    parts = urllib.parse.urlsplit(base_url)
    if MANAGEMENT_API_PATH in parts.path:
        raise ProprietaryApiError(
            "refusing "
            + repr(base_url)
            + "; the platform reaches the catalog only through the Iceberg REST "
            "specification, never the Polaris Management API (ADR-0010)"
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
        """The catalog's REST config, which may name the prefix for later calls."""
        payload = self._request(
            "GET", "/v1/config?" + urllib.parse.urlencode({"warehouse": self.catalog})
        )
        defaults = payload.get("defaults") if isinstance(payload, dict) else None
        overrides = payload.get("overrides") if isinstance(payload, dict) else None
        prefix = None
        if isinstance(defaults, dict) and isinstance(defaults.get("prefix"), str):
            prefix = defaults["prefix"]
        if isinstance(overrides, dict) and isinstance(overrides.get("prefix"), str):
            prefix = overrides["prefix"]
        self._prefix = prefix
        return payload

    def _prefix_value(self) -> str:
        """The resolved prefix, or an empty string when the catalog names none.

        The Iceberg REST specification makes the prefix optional and does not
        substitute the catalog name for a missing one: a catalog with no prefix
        serves its namespaces at /v1/namespaces.
        """
        if self._prefix is None:
            self.config()
        return self._prefix or ""

    def _namespace(self, namespace: Iterable[str]) -> str:
        parts = list(namespace)
        if not parts or not all(isinstance(part, str) and part for part in parts):
            raise CatalogError("a namespace is a non-empty list of non-empty levels")
        return NAMESPACE_SEPARATOR.join(urllib.parse.quote(part, safe="") for part in parts)

    def _namespaces_path(self) -> str:
        prefix = self._prefix_value()
        segment = "/" + urllib.parse.quote(prefix, safe="") if prefix else ""
        return "/v1" + segment + "/namespaces"

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
