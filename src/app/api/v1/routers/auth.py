# src/app/api/v1/routers/auth.py

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.auth import TokenResponse     # updated import
from app.domain.services.auth_service import AuthService
from app.infrastructure.db.dependencies import get_main_session
from app.utils.hp_py_logger import update_request_context

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: AsyncSession = Depends(get_main_session),
):
    """
    Authenticate via LDAP and return a JWT.
    """
    update_request_context(user=form_data.username)
    service = AuthService(session)
    return await service.login(form_data.username, form_data.password)


@router.post("/logout")
async def logout():
    """
    Stateless JWT logout (client discards token).
    """
    return {"message": "Logout successful – discard your JWT on the client."}
