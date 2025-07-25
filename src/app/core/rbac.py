from typing import Callable, Set
from fastapi import Depends, HTTPException, status

class RBAC:
    def __init__(self, role_permissions: dict[str, Set[str]]):
        self.role_permissions = role_permissions

    def require(self, permission: str) -> Callable:
        def dep(user = Depends(lambda: {"role": "user"})):  # placeholder dependency
            role = user.get("role")
            if role not in self.role_permissions or permission not in self.role_permissions[role]:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
            return user
        return dep

rbac = RBAC(role_permissions={
    "admin": {"user:read", "user:write"},
    "user": {"user:read"},
})
