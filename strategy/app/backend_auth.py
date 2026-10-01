"""Service authentication for calls from the strategy service to the Go backend.

The backend gates every non-public route. The routes the bots use (real
orders, balances, the shared paper engine, the trade journal) accept the
shared ``AUTH_TOKEN`` as a service credential; see
``backend/internal/adapter/http/route_access.go``.

``backend_event_hooks()`` returns httpx event hooks that attach
``Authorization: Bearer $AUTH_TOKEN`` only to requests whose URL starts with
``BACKEND_API_BASE`` or ``PAPER_API_BASE``. Clients that also call exchanges or
other third parties can use the hooks safely: the token never leaves for any
other origin, and a caller-provided ``Authorization`` header is left alone.
"""

from __future__ import annotations

import os
from collections.abc import Awaitable, Callable

import httpx

_DEFAULT_BACKEND = "http://backend:8080"


def _backend_bases() -> tuple[str, ...]:
    bases = []
    for name in ("BACKEND_API_BASE", "PAPER_API_BASE"):
        value = (os.getenv(name) or _DEFAULT_BACKEND).strip().rstrip("/")
        if value:
            bases.append(value)
    return tuple(dict.fromkeys(bases))


def is_backend_url(url: str | httpx.URL) -> bool:
    """True when ``url`` is under a configured backend base (origin + path)."""
    text = str(url)
    return any(text == base or text.startswith((base + "/", base + "?")) for base in _backend_bases())


def backend_auth_headers(url: str | httpx.URL) -> dict[str, str]:
    """Headers to send to ``url``: the service bearer for backend URLs only."""
    token = (os.getenv("AUTH_TOKEN") or "").strip()
    if not token or not is_backend_url(url):
        return {}
    return {"Authorization": f"Bearer {token}"}


async def _attach_backend_auth(request: httpx.Request) -> None:
    if "Authorization" in request.headers:
        return
    request.headers.update(backend_auth_headers(request.url))


def backend_event_hooks() -> dict[str, list[Callable[[httpx.Request], Awaitable[None]]]]:
    """``event_hooks`` for an ``httpx.AsyncClient`` that may call the backend."""
    return {"request": [_attach_backend_auth]}
