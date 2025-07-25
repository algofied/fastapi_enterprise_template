from fastapi import APIRouter, HTTPException, Depends
        from pydantic import BaseModel
        from sqlalchemy.ext.asyncio import AsyncSession
        from app.auth.ldap_client import ldap_bind
        from app.auth.token import create_access_token
        from app.infrastructure.db.base import get_db_session
        from app.infrastructure.db.repositories.user_repo import UserRepository

        router = APIRouter()

        class LoginRequest(BaseModel):
            username: str
            password: str

        @router.post("/login")
        async def login(data: LoginRequest, db: AsyncSession = Depends(get_db_session)):
            """
            Authenticates user via LDAP and returns JWT with DB roles.
            """
            if not ldap_bind(data.username, data.password):
                raise HTTPException(401, detail="Invalid credentials")

            roles = await UserRepository(db).get_user_roles(data.username)
            token = create_access_token({"sub": data.username, "roles": roles})
            return {"access_token": token, "token_type": "bearer"}