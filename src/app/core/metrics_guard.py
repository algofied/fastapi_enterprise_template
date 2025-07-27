# src/app/core/metrics_guard.py
from __future__ import annotations

from ipaddress import ip_address, ip_network
from typing import Iterable, Optional
from fastapi import Depends, HTTPException, Request, status

from app.core.config import get_settings
from app.auth.dependencies import get_current_user, UserRead  # adjust import if path differs
from app.utils.hp_py_logger import hp_log

def _ip_in_allowlist(ip: str, patterns: Iterable[str]) -> bool:
    try:
        ipaddr = ip_address(ip)
    except ValueError:
        return False
    for p in patterns:
        try:
            if "/" in p:
                if ipaddr in ip_network(p, strict=False):
                    return True
            else:
                if ipaddr == ip_address(p):
                    return True
        except ValueError:
            continue
    return False

def require_metrics_access():
    """
    Returns a dependency that enforces metrics access policy:
    - dev/local: open
    - prod:
        * METRICS_MODE=allowlist -> IP allow list
        * METRICS_MODE=role      -> require role METRICS_REQUIRED_ROLE
        * METRICS_MODE=open      -> open (not recommended in prod)
    """
    async def guard(request: Request, user: Optional[UserRead] = Depends(get_current_user)):
        settings = get_settings()
        env = settings.environment.lower()
        mode = settings.metrics_mode

        # Always open in dev/local
        if env in {"dev", "local"} or mode == "open":
            return True

        client_ip = request.client.host if request.client else None

        if mode == "allowlist":
            if client_ip and _ip_in_allowlist(client_ip, settings.metrics_allow_ips):
                return True
            hp_log.warning("Metrics access denied (IP)", extra={"ip": client_ip, "path": "/metrics"})
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

        # mode == "role"
        # get_current_user dependency already validated JWT and loaded roles
        required = settings.metrics_required_role.lower().strip()
        roles = {r.lower() for r in (user.roles if user else [])}
        if required in roles:
            return True

        hp_log.warning("Metrics access denied (role)", extra={"user": getattr(user, "username", None)})
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    return guard
