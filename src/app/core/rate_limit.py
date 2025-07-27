from __future__ import annotations

import os
from typing import Callable

from fastapi import Request, Response
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

# Prefer Redis for multi-process / multi-replica, fallback to memory
# e.g. REDIS_URL=redis://localhost:6379/0
REDIS_URL = os.getenv("REDIS_URL")
STORAGE_URI = REDIS_URL if REDIS_URL else "memory://"

def key_ip(request: Request) -> str:
    """
    Robust IP extractor for proxies: use leftmost X-Forwarded-For, else client.host.
    Adjust to your trust boundaries (e.g., only trust your ingress).
    """
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return get_remote_address(request)

def key_user_or_ip(request: Request) -> str:
    """
    User key when JWT middleware populates request.state.user; fallback to IP.
    """
    user = getattr(request.state, "user", None)
    return f"user:{user}" if user else f"ip:{key_ip(request)}"

# Create one Limiter instance and reuse it app-wide
limiter = Limiter(
    key_func=key_ip,              # default key (IP)
    storage_uri=STORAGE_URI,      # Redis or memory
    headers_enabled=True,         # send standard rate-limit headers
)

# Exception handler for 429
def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> Response:
    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=429,
        content={"detail": "Too many requests, slow down."},
        headers=getattr(exc, "headers", None) or {},
    )

# Convenience decorators you can import in routers
def limit_login(rule: str) -> Callable:
    """
    Use IP-only for login to avoid async body parsing inside key_func.
    Example: @limit_login("5/minute")
    """
    return limiter.limit(rule, key_func=key_ip)

def limit_user(rule: str) -> Callable:
    """
    Use user (from JWT middleware) if present, else IP.
    Example: @limit_user("100/minute")
    """
    return limiter.limit(rule, key_func=key_user_or_ip)
