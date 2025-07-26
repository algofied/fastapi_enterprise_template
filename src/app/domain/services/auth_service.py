# src/app/domain/services/auth_service.py
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.ldap_client import ldap_bind
from app.security.jwt import create_token
from app.infrastructure.db.repositories.user_repo import UserRepository
from app.schemas.auth import TokenResponse
from app.utils.hp_py_logger import update_request_context

class AuthService:
    """
    Domain service for authentication logic.
    """

    def __init__(self, session: AsyncSession):
        self.repo = UserRepository(session)

    async def login(self, username: str, password: str) -> TokenResponse:
        """
        Bind to LDAP, fetch user roles, and return a signed JWT.
        """
        # 1️⃣ LDAP authentication
        if not ldap_bind(username, password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )
        print(f"LDAP bind successful for user: {(username)}")
        # 2️⃣ Fetch user record (and roles) from DB
        user = await self.repo.get_by_id(username)
        
        print(f"User fetched from DB: {user}")  # Debugging line

        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        print(f":::::::::::::::::::-------User found: {user.username}----{getattr(user, "username", None)}" )
        update_request_context(user=username)
        
        # 3️⃣ Map Role objects → List[str]
        #    user.roles is List[Role], so extract .name
        role_names = [role.name for role in user.roles]

        # 4  Issue JWT with subject and roles
        token = create_token({
            "sub": user.username,
            "roles": role_names  # comma-separated or list, per your implementation
        })
        return TokenResponse(access_token=token, token_type="bearer")
