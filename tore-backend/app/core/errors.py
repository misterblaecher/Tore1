"""Application exception handlers independent from the legacy runtime."""

from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from app.core.logging import _request_id_from_request
from app.services.rate_limit_service import RateLimitExceeded, standard_rate_limit_http_exception


async def _http_exception_handler(request: Request, exc: HTTPException):
    detail = exc.detail
    payload_detail: Any
    if isinstance(detail, dict):
        payload_detail = dict(detail)
    else:
        payload_detail = str(detail)

    if exc.status_code == 429 and isinstance(payload_detail, dict):
        retry_after_raw = None
        if exc.headers:
            retry_after_raw = exc.headers.get("Retry-After") or exc.headers.get("retry-after")
        if retry_after_raw is None:
            retry_after_raw = request.headers.get("retry-after")
        retry_after_seconds = (
            int(retry_after_raw)
            if retry_after_raw and retry_after_raw.isdigit()
            else None
        )
        body_retry = payload_detail.get("retry_after_seconds")
        if retry_after_seconds is None and isinstance(body_retry, int):
            retry_after_seconds = body_retry
        if retry_after_seconds is not None:
            payload_detail["retry_after_seconds"] = retry_after_seconds

    if (
        isinstance(payload_detail, dict)
        and "code" not in payload_detail
        and isinstance(payload_detail.get("reason"), str)
    ):
        payload_detail["code"] = payload_detail["reason"]

    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": payload_detail},
        headers=exc.headers,
    )


async def _rate_limit_exception_handler(request: Request, exc: RateLimitExceeded):
    http_exc = standard_rate_limit_http_exception(
        scope=exc.scope,
        retry_after_seconds=exc.retry_after_seconds,
    )
    return await _http_exception_handler(request, http_exc)


async def _unhandled_exception_handler(request: Request, exc: Exception):
    request_id = _request_id_from_request(request)
    logging.exception(
        "Unhandled exception on %s %s",
        request.method,
        request.url.path,
        exc_info=exc,
    )
    payload: Dict[str, Any] = {
        "detail": "Internal Server Error",
        "code": "internal_error",
        "request_id": request_id,
    }
    return JSONResponse(status_code=500, content=payload)


def install_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(HTTPException, _http_exception_handler)
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exception_handler)
    app.add_exception_handler(Exception, _unhandled_exception_handler)


__all__ = [
    "_http_exception_handler",
    "_rate_limit_exception_handler",
    "_unhandled_exception_handler",
    "install_exception_handlers",
]
