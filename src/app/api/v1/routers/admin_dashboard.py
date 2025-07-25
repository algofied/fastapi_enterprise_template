from fastapi import APIRouter, Depends
from app.auth.dependencies import require_roles
from app.core.rbac import Role  # Your enum or constant class for roles

router = APIRouter()

@router.get("/admin/dashboard")
async def admin_dashboard(user=Depends(require_roles([Role.ADMIN]))):
    return {"message": f"Welcome {user.username}, to the admin dashboard"}
