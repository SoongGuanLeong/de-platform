"""The one HTTP transport the shared core injects.

Both the catalog client and the lineage emitter talk to a service over HTTP and
both take their transport as a parameter, so the seam is defined once here
rather than copied into each module. A caller supplies its own transport to
unit-test without a container, or to add retries or instrumentation.
"""

from __future__ import annotations

import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable

# (method, url, headers, body) -> (status, headers, body text).
Transport = Callable[[str, str, dict, str | None], tuple[int, dict, str]]

TIMEOUT_SECONDS = 30


def _origin(url: str) -> tuple[str, str | None, int | None]:
    parts = urllib.parse.urlsplit(url)
    return (parts.scheme, parts.hostname, parts.port)


class _SameOriginRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Follow a redirect only when it stays on the request's origin.

    urllib re-sends the original request headers on a redirect, so an
    authenticated request that followed a cross-origin redirect would hand its
    bearer token to the redirect target. Refusing the cross-origin hop keeps the
    token on the origin it was minted for; a same-origin redirect is still
    followed, because that is the catalog redirecting within itself.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if _origin(newurl) != _origin(req.full_url):
            raise urllib.error.HTTPError(
                req.full_url,
                code,
                "cross-origin redirect refused: " + newurl,
                headers,
                fp,
            )
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_OPENER = urllib.request.build_opener(_SameOriginRedirectHandler())


def urllib_transport(method: str, url: str, headers: dict, body: str | None):
    data = body.encode("utf-8") if body is not None else None
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with _OPENER.open(request, timeout=TIMEOUT_SECONDS) as response:
            return response.status, dict(response.headers), response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        return error.code, dict(error.headers), error.read().decode("utf-8")
