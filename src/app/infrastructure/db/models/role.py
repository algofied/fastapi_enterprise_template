# src/app/infrastructure/db/models/role.py
from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from app.infrastructure.db.base_class import Base
from app.infrastructure.db.models.user_roles import user_roles

class Role(Base):
    __tablename__ = "roles"

    id   = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False, index=True)

    # Refer to User by string
    users = relationship(
        "User",
        secondary=user_roles,
        back_populates="roles",
        lazy="selectin",
    )
