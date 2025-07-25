# src/app/infrastructure/db/models/user.py
from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from app.infrastructure.db.base_class import Base
from app.infrastructure.db.models.user_roles import user_roles

class User(Base):
    __tablename__ = "users"

    id        = Column(Integer, primary_key=True, index=True)
    username  = Column(String, unique=True, index=True, nullable=False)
    full_name = Column(String, nullable=True)
    email     = Column(String, nullable=True)

    # Refer to Role by string, not by importing Role
    roles = relationship(
        "Role",
        secondary=user_roles,
        back_populates="users",
        lazy="selectin",
    )
