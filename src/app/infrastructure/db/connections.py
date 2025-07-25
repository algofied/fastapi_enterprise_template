from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.core.config import get_settings

settings = get_settings()

# Engines
engine_main = create_async_engine(settings.db_url_test_main, echo=False)
engine_logs = create_async_engine(settings.db_url_test_logs, echo=False)

# SessionMakers
SessionMain = sessionmaker(engine_main, class_=AsyncSession, expire_on_commit=False)
SessionLogs = sessionmaker(engine_logs, class_=AsyncSession, expire_on_commit=False)
