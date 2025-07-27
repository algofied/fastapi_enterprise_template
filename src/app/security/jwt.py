# src/app/security/jwt.py
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence, Union

from fastapi import HTTPException, status
from jose import jwt

# Import exceptions from the correct module. Fallback to JWTError-only if needed.
try:
    from jose.exceptions import JWTError, ExpiredSignatureError, JWTClaimsError  # type: ignore
except Exception:  # pragma: no cover
    from jose.exceptions import JWTError  # type: ignore
    ExpiredSignatureError = JWTError     # fallback
    JWTClaimsError = JWTError            # fallback

from zoneinfo import ZoneInfo

from app.core.config import get_settings


# ---- Helpers -----------------------------------------------------------------
def _settings():
    # Lazily resolve to avoid import cycles during app start
    return get_settings()


def _get_signing_key() -> str:
    """
    HS* algorithms require a raw shared secret (bytes/str), not a SecretStr object.
    """
    key = _settings().secret_key.get_secret_value()
    if not key or not isinstance(key, str):
        raise RuntimeError("SECRET_KEY is missing or invalid")
    return key


def _get_algorithms() -> List[str]:
    alg = _settings().jwt_algorithm
    return [alg] if isinstance(alg, str) else list(alg)


# ---- Public API ---------------------------------------------------------------
def create_token(
    claims: Dict[str, Any],
    *,
    expires_in_minutes: Optional[int] = None,
    issuer: Optional[str] = None,
    audience: Optional[str] = None,
) -> str:
    """
    Create a signed JWT.

    - `claims` should at least include a subject: e.g. {"sub": "username"}.
    - `exp` is added automatically using configured timezone.
    - Optional `iss` and `aud` can be set here or enforced at decode time.
    """
    settings = _settings()
    tz = ZoneInfo(settings.timezone)  # ex: "Asia/Kolkata"
    now = datetime.now(tz)

    exp_minutes = expires_in_minutes or settings.token_expiry_minutes
    expire = now + timedelta(minutes=exp_minutes)

    to_encode: Dict[str, Any] = {**claims}
    to_encode["iat"] = int(now.timestamp())
    to_encode["exp"] = int(expire.timestamp())
    if issuer:
        to_encode["iss"] = issuer
    if audience:
        to_encode["aud"] = audience

    token = jwt.encode(
        to_encode,
        _get_signing_key(),
        algorithm=_settings().jwt_algorithm,
    )
    return token


def decode_token(
    token: str,
    *,
    verify_exp: bool = True,
    verify_aud: bool = False,
    expected_issuer: Optional[str] = None,
    expected_audience: Optional[str] = None,
    leeway_seconds: int = 10,
) -> Dict[str, Any]:
    """
    Decode & validate a JWT.
    - `verify_exp`: validate expiration (default True)
    - `verify_aud`: validate audience `aud` claim (default False)
    - `expected_issuer`: check `iss` claim if provided
    - `expected_audience`: required if `verify_aud=True`
    - `leeway_seconds`: clock skew allowance
    """
    try:
        options = {
            "verify_exp": verify_exp,
            # We'll pass `audience` parameter below only when verify_aud=True;
            # `python-jose` uses that to trigger aud validation.
            "verify_aud": verify_aud,
            "leeway": leeway_seconds,
        }

        decoded = jwt.decode(
            token,
            _get_signing_key(),
            algorithms=_get_algorithms(),
            options=options,
            audience=expected_audience if verify_aud else None,
            issuer=expected_issuer,
        )
        # Note: If you pass issuer/audience, jose will raise JWTClaimsError on mismatch.

        return decoded

    except ExpiredSignatureError:
        # Token expired
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except JWTClaimsError as exc:
        # Missing / mismatched claims (iss/aud/nbf, etc.)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token claims: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except JWTError:
        # Bad signature, malformed token, wrong key/alg, etc.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )
