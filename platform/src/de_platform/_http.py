"""The one HTTP transport the shared core injects.

Both the catalog client and the lineage emitter talk to a service over HTTP and
both take their transport as a parameter, so the seam is defined once here
rather than copied into each module. A caller supplies its own transport to
unit-test without a container, or to add retries or instrumentation.
"""

from __future__ import annotations

import urllib.error
import urllib.request
from collections.abc import Callable

# (method, url, headers, body) -> (status, headers, body text).
Transport = Callable[[str, str, dict, str | None], tuple[int, dict, str]]

TIMEOUT_SECONDS = 30


def urllib_transport(method: str, url: str, headers: dict, body: str | None):
    data = body.encode("utf-8") if body is not None else None
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            return response.status, dict(response.headers), response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        return error.code, dict(error.headers), error.read().decode("utf-8")
