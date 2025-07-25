# src/app/schemas/auth.py

from pydantic import BaseModel

class TokenResponse(BaseModel):
    """
    Response model for JWT access tokens.
    """
    access_token: str
    token_type: str

    model_config = {
        "from_attributes": True,  # Pydantic v2: replaces `orm_mode`
    }
