# src/app/api/v1/routers/users.py
from fastapi import APIRouter, Depends, HTTPException
from typing import List

from app.schemas.user import UserRead, UserCreate
from app.domain.services.user_service import UserService
from app.infrastructure.db.dependencies import get_main_session
from app.auth.dependencies import get_current_user, require_roles
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


def get_user_service(
    session: AsyncSession = Depends(get_main_session),
    current_user=Depends(get_current_user),
) -> UserService:
    """
    Dependency to build UserService with DB session and current user.
    """
    return UserService(session, current_user)


@router.get(
    "/",
    response_model=List[UserRead],
    summary="List all users (admin only)",
    dependencies=[Depends(require_roles("admin"))]
)
async def list_users(svc: UserService = Depends(get_user_service)):
    """
    Return all users. Only 'admin' role allowed.
    """
    return await svc.list_users()


@router.get("/me", response_model=UserRead, summary="Get current user profile")
async def get_me(svc: UserService = Depends(get_user_service)):
    """
    Return profile of the authenticated user.
    """
    return await svc.get_current_user()


@router.get(
    "/{user_id}",
    response_model=UserRead,
    summary="Get a user by ID (admin only)",
    dependencies=[Depends(require_roles(["admin"]))]
)
async def get_user(
    user_id: int,
    svc: UserService = Depends(get_user_service)
):
    """
    Fetch a specific user by their ID. Admin only.
    """
    user = await svc.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.post(
    "/",
    response_model=UserRead,
    summary="Create a new user (admin only)",
    dependencies=[Depends(require_roles("admin"))]
)
async def create_user(
    payload: UserCreate,
    svc: UserService = Depends(get_user_service)
):
    """
    Create a new user with specified roles. Admin only.
    """
    return await svc.create_user(payload)
