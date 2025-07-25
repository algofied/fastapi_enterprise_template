# src/app/infrastructure/db/models/user_roles.py

from sqlalchemy import Table, Column, Integer, ForeignKey
from app.infrastructure.db.base_class import Base

# Join table for many‑to‑many User ↔ Role
user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id"), primary_key=True),
    Column("role_id", Integer, ForeignKey("roles.id"), primary_key=True),
)
