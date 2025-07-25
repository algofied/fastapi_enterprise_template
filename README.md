# FastAPI Enterprise Clean Scaffold

- Clean Architecture / SOLID
- PEP‑compliant (black, ruff, mypy)
- Observability: Prometheus, Grafana, Loki
- Background tasks: Celery + Redis
- Production stack: Gunicorn -> Uvicorn workers
- Settings cached with @lru_cache

## Quick start (dev)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
uvicorn app.main:app --reload
```

## Monitoring

```
docker compose -f monitoring/docker-compose.yml up -d
```

## Celery

```
celery -A app.infrastructure.mq.celery_app.celery worker -l info
```
