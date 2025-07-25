import redis.asyncio as redis
from functools import lru_cache
from app.core.config import get_settings

@lru_cache
def get_redis() -> redis.Redis:
    settings = get_settings()
    return redis.from_url(settings.redis_url, encoding="utf-8", decode_responses=True)
