# src/app/main.py
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from ipaddress import ip_network, ip_address

from fastapi import FastAPI, Request, Depends
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.observability import metrics_middleware, metrics_response
from app.utils.hp_py_logger import init_logging, hp_log
from app.utils.request_context_middleware import RequestContextMiddleware
from app.auth.jwt_context_middleware import JWTContextMiddleware

# Rate limiting (SlowAPI)
from slowapi.middleware import SlowAPIMiddleware
from slowapi.errors import RateLimitExceeded
from app.core.rate_limit import limiter, rate_limit_exceeded_handler

# Routers
from app.api.v1.routers import health, users, auth
# from app.api.v1.routers import admin_dashboard

# ---------------------------------------------------------------------
# 1) Settings + logging (before app creation)
# ---------------------------------------------------------------------
settings = get_settings()
init_logging(settings=settings)
prefix = settings.api_version_prefix

# Optional: tune SQLAlchemy wire logs from the env
if settings.log_wire_sqlalchemy:
    level = getattr(logging, settings.log_sqlalchemy_level.upper(), logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(level)
    logging.getLogger("sqlalchemy.pool").setLevel(level)
    logging.getLogger("sqlalchemy.orm").setLevel(level)

# ---------------------------------------------------------------------
# 2) Lifespan (startup/shutdown logs)
# ---------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    hp_log.info("Application startup")
    try:
        yield
    finally:
        hp_log.info("Application shutdown")

# ---------------------------------------------------------------------
# 3) Create the app
# ---------------------------------------------------------------------
app = FastAPI(
    title=settings.project_name,
    version="0.1.0",
    debug=settings.debug,
    lifespan=lifespan,
)

# If you run behind a reverse proxy (Nginx/Ingress), consider:
# from starlette.middleware.proxy_headers import ProxyHeadersMiddleware
# app.add_middleware(ProxyHeadersMiddleware)  # trust X-Forwarded-* for correct client IP

# ---------------------------------------------------------------------
# 4) Middleware order: RequestContext → JWTContext → SlowAPI → metrics
# ---------------------------------------------------------------------
app.add_middleware(RequestContextMiddleware)
app.add_middleware(JWTContextMiddleware)

# SlowAPI middleware + handler
app.add_middleware(SlowAPIMiddleware)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

# Rate limit error -> 429 JSON
# from fastapi.responses import JSONResponse
# @app.exception_handler(RateLimitExceeded)
# async def _rate_limit_exceeded_handler(request, exc):
#     return JSONResponse(status_code=429, content={"detail": "Too many requests, slow down."})


# Prometheus metrics middleware (your existing one)
app.middleware("http")(metrics_middleware)

# ---------------------------------------------------------------------
# 5) Routers
# ---------------------------------------------------------------------
app.include_router(auth.router,   prefix=f"{prefix}/auth",   tags=["Authentication"])
app.include_router(health.router, prefix=prefix,             tags=["health"])
app.include_router(users.router,  prefix=f"{prefix}/users",  tags=["users"])
# app.include_router(admin_dashboard.router, prefix=f"{prefix}/admin_dashboard", tags=["admin-dashboard"])

# ---------------------------------------------------------------------
# 6) Root (public). If a valid JWT is sent, JWTContextMiddleware will add `user` to log context.
# ---------------------------------------------------------------------
@app.get("/", tags=["root"])
async def root():
    hp_log.info("Root endpoint accessed")
    return {"status": "ok", "env": settings.environment}

# ---------------------------------------------------------------------
# 7) /metrics protection (open | role | ip_allow)
# ---------------------------------------------------------------------
def _ip_allowed(ip: str, allowed: list[str]) -> bool:
    for item in allowed:
        item = item.strip()
        if not item:
            continue
        try:
            if ip_address(ip) in ip_network(item, strict=False):
                return True
        except ValueError:
            if ip == item:
                return True
    return False

if settings.metrics_enabled:
    if settings.metrics_protect_mode == "open":
        @app.get(settings.metrics_path)
        async def metrics_open():
            return metrics_response()

    elif settings.metrics_protect_mode == "role":
        # Only users with e.g. "ops" role can see metrics
        from app.auth.dependencies import require_roles
        @app.get(settings.metrics_path, dependencies=[Depends(require_roles(["ops"]))])
        async def metrics_role():
            return metrics_response()

    else:  # ip_allow (default)
        @app.get(settings.metrics_path)
        async def metrics_ip_guard(request: Request):
            client_ip = (request.headers.get("x-real-ip")
                         or request.headers.get("x-forwarded-for", "").split(",")[0].strip()
                         or (request.client.host if request.client else "127.0.0.1"))
            if not _ip_allowed(client_ip, settings.metrics_allow_ips):
                return JSONResponse(status_code=403, content={"detail": "Forbidden"})
            return metrics_response()
