# src/app/schemas/user.py

from typing import List, Optional, Any
from pydantic import BaseModel, field_validator

class UserRead(BaseModel):
    id: int
    username: str
    full_name: Optional[str]
    email: Optional[str]
    roles: List[str]

    # enable .from_orm()
    model_config = {
        "from_attributes": True,
    }

    @field_validator("roles", mode="before")
    @classmethod
    def _unpack_roles(cls, v: Any) -> List[str]:
        """
        If we got a list of Role objects, return [r.name for r in v].
        Otherwise (already List[str]) just return it.
        """
        if isinstance(v, list):
            unpacked = []
            for item in v:
                # SQLAlchemy relationship gives Role instances
                if hasattr(item, "name"):
                    unpacked.append(item.name)
                else:
                    unpacked.append(item)
            return unpacked
        return v  # let pydantic handle other cases

class UserCreate(BaseModel):
    username: str
    full_name: Optional[str]
    email: Optional[str]
    roles: List[str]

    model_config = {
        "from_attributes": True,
    }
