# src/app/domain/services/user_service.py

from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.repositories.user_repo import UserRepository
from app.schemas.user import UserRead, UserCreate
from app.infrastructure.db.models.user import User


class UserService:
    """
    Domain service for user-related business logic.
    """

    def __init__(self, session: AsyncSession, current_user: User):
        self.repo = UserRepository(session)
        self.current_user = current_user

    async def list_users(self) -> List[UserRead]:
        """
        Return all users in the system.
        """
        users = await self.repo.get_all_users()
        output: List[UserRead] = []
        for u in users:
            output.append(
                UserRead(
                    id=u.id,
                    username=u.username,
                    full_name=u.full_name,
                    email=u.email,
                    roles=[role.name for role in u.roles] if u.roles else []
                )
            )
        return output

    async def get_current_user(self) -> UserRead:
        """
        Return the logged-in user's profile.
        Always returns roles as List[str], even if current_user.roles is already a List[str].
        """
        u = self.current_user

        # normalize roles to a list of strings
        role_names: List[str] = []
        for r in (u.roles or []):
            if hasattr(r, "name"):
                role_names.append(r.name)  # Role object
            else:
                role_names.append(r)       # already a str

        return UserRead(
            id=u.id,
            username=u.username,
            full_name=u.full_name,
            email=u.email,
            roles=role_names,
        )

    async def get_user_by_id(self, user_id: int) -> Optional[UserRead]:
        """
        Return a specific user by ID.
        """
        u = await self.repo.get_by_id(user_id)
        if not u:
            return None

        return UserRead(
            id=u.id,
            username=u.username,
            full_name=u.full_name,
            email=u.email,
            roles=[role.name for role in u.roles] if u.roles else []
        )

    async def create_user(self, payload: UserCreate) -> UserRead:
        """
        Create a new user. Only admin can invoke.
        """
        # pass the roles list directly
        user = await self.repo.create_user(
            username=payload.username,
            full_name=payload.full_name,
            email=payload.email,
            role_names=payload.roles,      # <-- list[str]
        )
        return UserRead.from_orm(user)