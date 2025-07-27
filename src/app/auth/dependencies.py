# src/app/auth/dependencies.py
from __future__ import annotations

from typing import Callable, Iterable, List, Literal, Sequence, Set

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.infrastructure.db.dependencies import get_main_session
from app.infrastructure.db.repositories.user_repo import UserRepository
from app.schemas.user import UserRead
from app.security.jwt import decode_token
from app.utils.hp_py_logger import hp_log, set_request_context, update_request_context

# OAuth2 bearer setup (kept simple; scopes are optional if you add them later)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")
settings = get_settings()


# ---- helpers -----------------------------------------------------------------
from typing import Iterable, Set, Union, Sequence

def _flatten_roles(roles: Iterable[Union[str, Sequence[str]]]) -> Iterable[str]:
    for r in roles:
        if isinstance(r, (list, tuple, set)):
            for x in r:
                if isinstance(x, str):
                    yield x
        elif isinstance(r, str):
            yield r

def _norm(roles: Iterable[Union[str, Sequence[str]]]) -> Set[str]:
    """Normalize role names for case-insensitive comparison; accepts varargs or nested lists/tuples."""
    return {s.strip().lower() for s in _flatten_roles(roles) if s and s.strip()}


# ---- core user dependency ----------------------------------------------------
async def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_main_session),
) -> UserRead:
    """
    1) Validate JWT
    2) Resolve user from DB
    3) Load role names (List[str])
    4) Set request logging context
    5) Return a UserRead DTO (never ORM objects)
    """
    payload = decode_token(token)  # raises 401 on failure
    username = payload.get("sub")
    if not username:
        raise HTTPException(status_code=400, detail="Invalid token payload: missing 'sub'")

    repo = UserRepository(session)

    # Fetch user & roles
    user = await repo.get_by_username(username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    role_names: List[str] = await repo.get_user_roles(username)

    # Put identity into the structured-logging context
    # (RequestContextMiddleware already injected request_id/method/path/ip)
    set_request_context(user=user.id)
    # Optional: also record roles (comma separated), helpful for audits
    update_request_context(roles=",".join(role_names))

    hp_log.debug(
        "Auth resolved current user",
        extra={"user": user.username}
    )

    return UserRead(
        id=user.id,
        username=user.username,
        full_name=user.full_name,
        email=user.email,
        roles=role_names,
    )


# ---- role-guard factories ----------------------------------------------------
def require_roles(
    *required_roles: str,
    logic: Literal["any", "all"] = "any",
) -> Callable:
    """
    Factory that returns a dependency ensuring the current user satisfies role requirements.

    Usage:
        - ANY of the roles:
          @router.get("/admin", dependencies=[Depends(require_roles("admin", "ops"))])
        - ALL of the roles:
          @router.post(..., dependencies=[Depends(require_roles("admin", "editor", logic="all"))])

        In handlers where you want the user object:
          async def endpoint(user: UserRead = Depends(require_roles("admin"))): ...

    Notes:
      * Role matching is case-insensitive.
      * Returns the same UserRead as get_current_user so you can use the object.
    """
    if not required_roles:
        raise ValueError("require_roles() must be called with at least one role")

    required_norm = _norm(required_roles)

    async def _checker(user: UserRead = Depends(get_current_user)) -> UserRead:
        have = _norm(user.roles)

        allowed = False
        if logic == "any":
            allowed = bool(have.intersection(required_norm))
        elif logic == "all":
            allowed = required_norm.issubset(have)
        else:
            # Defensive: should never happen with the Literal type
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Invalid role guard logic",
            )

        if not allowed:
            hp_log.warning(
                "Access forbidden: insufficient role",
                extra={
                    "user": user.username,
                    "required_roles": ",".join(sorted(required_norm)),
                    "user_roles": ",".join(sorted(have)),
                },
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access forbidden: insufficient role",
            )
        return user

    return _checker


def require_any_role(*roles: str) -> Callable:
    """Allow if user has ANY of the given roles."""
    return require_roles(*roles, logic="any")


def require_all_roles(*roles: str) -> Callable:
    """Allow only if user has ALL of the given roles."""
    return require_roles(*roles, logic="all")
