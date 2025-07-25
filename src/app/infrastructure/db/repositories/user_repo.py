# src/app/infrastructure/db/repositories/user_repo.py
from typing import List, Optional
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.infrastructure.db.models.role import Role
from app.infrastructure.db.models.user import User


class UserRepository:
    """
    Concrete repository for User entity—uses SQLAlchemy AsyncSession.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_username(self, username: str) -> Optional[User]:
        """
        Fetch a user by username, eagerly loading roles relationship.
        """
        stmt = select(User).options(selectinload(User.roles)).where(User.username == username)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_user_roles(self, username: str) -> list[str]:
        """
        Fetch just the role‐names (strings) for a given username.
        """
        # simple approach: load the User, then extract role.name
        user = await self.get_by_username(username)
        if not user or not user.roles:
            return []
        return [role.name for role in user.roles]

    async def get_all_users(self) -> List[User]:
        """
        Return all users from the DB.
        """
        result = await self.session.execute(select(User))
        return result.scalars().all()

    async def get_by_id(self, user_id: int) -> Optional[User]:
        """
        Fetch a user by their primary key ID.
        """
        print(f"Fetching user by ID: {user_id}")
        stmt = select(User).where(User.id == int(user_id))
        print(f"Executing statement: {stmt}")
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_user(
        self,
        username: str,
        full_name: Optional[str],
        email: Optional[str],
        role_names: List[str],
    ) -> User:
        # 1) Create the User without roles
        user = User(username=username, full_name=full_name, email=email)

        # 2) For each requested role name, fetch the Role instance and append it
        for name in role_names:
            result = await self.session.execute(select(Role).where(Role.name == name))
            role = result.scalars().first()
            if not role:
                raise HTTPException(status_code=400, detail=f"Role '{name}' not found")
            user.roles.append(role)

        self.session.add(user)

        # 3) Commit & refresh, catching duplicates
        try:
            await self.session.commit()
            await self.session.refresh(user)
        except IntegrityError:
            await self.session.rollback()
            raise HTTPException(status_code=400, detail="Username already exists")

        return user