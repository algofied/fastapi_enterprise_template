from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.params import Depends

from app.auth.jwt_context_middleware import JWTContextMiddleware
from app.core.config import get_settings
from app.core.observability import metrics_middleware
from app.utils.hp_py_logger import init_logging, hp_log
from app.utils.request_context_middleware import RequestContextMiddleware

# Routers
from app.api.v1.routers import health, users, auth, admin_dashboard

# Load settings first
settings = get_settings()

# 1) Initialize logging BEFORE app creation (so every logger uses the same pipeline)
init_logging(settings=settings)

# 2) Optional: enable SQLAlchemy “wire” logs based on env flags
if settings.log_wire_sqlalchemy:
    level = getattr(logging, settings.log_sqlalchemy_level.upper(), logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(level)
    logging.getLogger("sqlalchemy.pool").setLevel(level)
    logging.getLogger("sqlalchemy.orm").setLevel(level)

# 3) Lifespan handlers replace on_event
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup phase
    hp_log.info("Application startup")
    try:
        yield
    finally:
        # Shutdown phase
        hp_log.info("Application shutdown")

# 4) Create the app with lifespan
app = FastAPI(
    title=settings.project_name,
    version="0.1.0",
    debug=settings.debug,
    lifespan=lifespan,
)

# 5) Middleware order: request context first, then metrics, then routers
app.add_middleware(RequestContextMiddleware)     # adds request_id/user/method/path/ip to logs
app.add_middleware(JWTContextMiddleware) 
app.middleware("http")(metrics_middleware)      # your existing Prometheus middleware

# 6) Routers
prefix = settings.api_version_prefix
app.include_router(auth.router, prefix=f"{prefix}/auth", tags=["Authentication"])
app.include_router(health.router, prefix=prefix, tags=["health"])
app.include_router(users.router, prefix=f"{prefix}/users", tags=["users"])
# app.include_router(admin_dashboard.router, prefix=f"{prefix}/admin_dashboard", tags=["admin-dashboard"])

# 7) Root
@app.get("/", tags=["root"])
async def root():
    hp_log.info("Root endpoint accessed")
    hp_log.debug("Root endpoint debug info", extra={"env": settings.environment})
    hp_log.warning("Root endpoint warning message")
    hp_log.error("Root endpoint error message")
    hp_log.critical("Root endpoint critical message")

    return {"status": "ok", "env": settings.environment}
