import asyncio
from app.infrastructure.db.base import Base
from app.infrastructure.db.connections import engine_main, engine_logs

async def init():
    async with engine_main.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with engine_logs.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

if __name__ == "__main__":
    asyncio.run(init())
