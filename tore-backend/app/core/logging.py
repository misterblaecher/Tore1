"""Request correlation helpers independent from the legacy runtime."""

from __future__ import annotations

from typing import Optional

from fastapi import Request


def _request_id_from_request(request: Request) -> Optional[str]:
    return (
        request.headers.get("x-request-id")
        or request.headers.get("x-render-request-id")
        or request.headers.get("x-correlation-id")
    )


__all__ = ["_request_id_from_request"]
