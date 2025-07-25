from app.infrastructure.db.connections import SessionMain, SessionLogs
from sqlalchemy.ext.asyncio import AsyncSession

async def get_main_session() -> AsyncSession:
    async with SessionMain() as session:
        yield session

async def get_logs_session() -> AsyncSession:
    async with SessionLogs() as session:
        yield session
