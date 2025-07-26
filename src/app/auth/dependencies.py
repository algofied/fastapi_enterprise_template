# src/app/auth/dependencies.py

from typing import Callable, List
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.infrastructure.db.dependencies import get_main_session
from app.infrastructure.db.repositories.user_repo import UserRepository
from app.schemas.user import UserRead
from app.utils.hp_py_logger import set_request_context, update_request_context
from app.security.jwt import decode_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")
settings = get_settings()

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_main_session),
) -> UserRead:
    """
    Validate JWT, look up the user, and return a UserRead DTO
    (so that `.roles` is List[str], never ORM objects).
    """
    payload = decode_token(token)
    username = payload.get("sub")
    if not username:
        raise HTTPException(status_code=400, detail="Invalid token payload")

    repo = UserRepository(session)
    user = await repo.get_by_username(username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # 👇 Add the username (or id/email) to the per-request logging context
    #     so every log line can include the user identity.
    print(f":::::::::::::::::::-------User found: {user.username}----{getattr(user, "username", None)}" )
    set_request_context(user=getattr(user, "username", None))
    
    # pull just the names of the roles
    role_names = await repo.get_user_roles(username)

    return UserRead(
        id=user.id,
        username=user.username,
        full_name=user.full_name,
        email=user.email,
        roles=role_names,
    )


def require_roles(allowed: List[str]) -> Callable:
    """
    Ensure that the current user (as a UserRead) has at least one
    of the allowed roles.
    """
    async def role_checker(user: UserRead = Depends(get_current_user)):
        if not any(r in allowed for r in user.roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access forbidden: insufficient role",
            )
        return user

    return role_checker
