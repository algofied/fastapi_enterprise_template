# src/app/api/v1/routers/auth.py

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.schemas.auth import TokenResponse     # updated import
from app.domain.services.auth_service import AuthService
from app.infrastructure.db.dependencies import get_main_session
from app.utils.hp_py_logger import update_request_context
from app.core.rate_limit import limit_login

router = APIRouter()

settings = get_settings()

@router.post("/login")
@limit_login("5/minute")        # IP-based throttling for login
async def login(
    request: Request, 
    response: Response, 
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
