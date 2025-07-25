from celery import Celery
from app.core.config import get_settings

settings = get_settings()

celery = Celery(
    "app",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

@celery.task
def add(x, y):
    return x + y
