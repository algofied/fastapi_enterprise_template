# src/app/security/jwt.py

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from jose import jwt, JWTError
from fastapi import HTTPException, status

from app.core.config import get_settings

settings = get_settings()

def _get_signing_key() -> str:
    # HS* algs expect a raw shared secret string/bytes, not SecretStr
    key = settings.secret_key.get_secret_value()
    if not key or not isinstance(key, str):
        raise RuntimeError("SECRET_KEY is missing or invalid")
    return key

def create_token(data: dict) -> str:
    """
    Create a JWT whose expiration is calculated in the configured timezone.
    """
    tz = ZoneInfo(settings.timezone)       # e.g. Asia/Kolkata
    now = datetime.now(tz)
    expire = now + timedelta(minutes=settings.token_expiry_minutes)

    to_encode = data.copy()
    to_encode["exp"] = int(expire.timestamp())
    return jwt.encode(
        to_encode,
        _get_signing_key(),
        algorithm=settings.jwt_algorithm
    )

def decode_token(token: str) -> dict:
    """
    Decode & validate the JWT. Raises 401 on failure.
    """
    try:
        return jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.jwt_algorithm],
            options={"verify_aud": False},
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
