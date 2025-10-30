from __future__ import annotations

from typing import Callable
from uuid import uuid4

from fastapi import FastAPI, Request, Response

CORRELATION_HEADER = "X-Correlation-Id"


def install_audit_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def ensure_correlation_id(request: Request, call_next: Callable[[Request], Response]):
        correlation_id = request.headers.get(CORRELATION_HEADER) or str(uuid4())
        request.state.correlation_id = correlation_id

        response = await call_next(request)
        if CORRELATION_HEADER not in response.headers:
            response.headers[CORRELATION_HEADER] = correlation_id
        return response
