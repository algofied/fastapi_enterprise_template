# src/app/infrastructure/db/models/__init__.py

# 1. register the join table
from .user_roles import user_roles

# 2. register Role
from .role      import Role

# 3. register User
from .user      import User
