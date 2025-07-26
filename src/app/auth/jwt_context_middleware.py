from __future__ import annotations

from typing import Callable, Optional

from fastapi import Request
from jose import jwt, JWTError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.core.config import get_settings
from app.utils.hp_py_logger import update_request_context

class JWTContextMiddleware(BaseHTTPMiddleware):
    """
    Best-effort: if an Authorization: Bearer <token> header exists, decode it and
    inject 'user' (from 'sub') into the request logging context. Never raises.
    """
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable):
        try:
            auth = request.headers.get("authorization")
            if auth and auth.lower().startswith("bearer "):
                token = auth.split(" ", 1)[1].strip()
                settings = get_settings()
                payload = jwt.decode(
                    token,
                    settings.secret_key.get_secret_value() if hasattr(settings.secret_key, "get_secret_value") else settings.secret_key,
                    algorithms=[settings.jwt_algorithm],
                )
                sub = payload.get("sub")
                if sub:
                    # Inject user into logging context for the current request
                    update_request_context(user=sub)
        except JWTError:
            # invalid/expired token? ignore here (this middleware is non-enforcing)
            pass
        except Exception:
            # Never break the request pipeline due to logging enrichment
            pass

        return await call_next(request)
