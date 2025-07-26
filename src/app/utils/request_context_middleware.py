# src/app/utils/request_context_middleware.py
from __future__ import annotations

import uuid
from typing import Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send

from app.utils.hp_py_logger import set_request_context, clear_request_context

class RequestContextMiddleware(BaseHTTPMiddleware):
    """
    Adds per-request context:
      request_id, method, path, ip
    and clears the context after response.
    """
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable):
        try:
            req_id = request.headers.get("x-request-id") or str(uuid.uuid4())
            client_host = request.client.host if request.client else None

            set_request_context(
                request_id=req_id,
                method=request.method,
                path=request.url.path,
                ip=client_host,
            )

            response = await call_next(request)
            # propagate request id to response too (handy for tracing)
            response.headers["X-Request-ID"] = req_id
            print(f"^^^^^^^------^^^^response headers: {response.headers}")  # Debugging line
            return response
        finally:
            # always clear context to avoid leakage across requests
            clear_request_context()
