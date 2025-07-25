from fastapi import FastAPI
from app.core.config import get_settings
from app.core.observability import metrics_middleware
from app.api.v1.routers import health, users, auth

settings = get_settings()

app = FastAPI(
    title="FastAPI Enterprise Clean",
    version="0.1.0",
)

# Observability middleware
app.middleware("http")(metrics_middleware)

# Routers
app.include_router(auth.router, prefix=f"{settings.api_version_prefix}/auth", tags=["Authentication"])
app.include_router(health.router, prefix=f"{settings.api_version_prefix}", tags=["health"])
app.include_router(users.router, prefix=f"{settings.api_version_prefix}/users", tags=["users"])
app.include_router(users.router, prefix=f"{settings.api_version_prefix}/admin_dashboard", tags=["admin-dashboard"])

@app.get("/", tags=["root"])
async def root():
    return {"status": "ok", "env": settings.environment}
