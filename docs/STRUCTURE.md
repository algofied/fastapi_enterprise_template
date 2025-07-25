# Project structure (enterprise-clean scaffold)

See README for quickstart. This document summarizes each folder.

| Path | Role | Description |
|------|------|-------------|
| src/app/core/config.py | Core | Pydantic Settings with @lru_cache |
| src/app/core/logging_config.py | Core | YAML-driven JSON logging |
| src/app/core/observability.py | Core | Prometheus metrics middleware |
| src/app/api/v1/routers | Transport | REST endpoints, thin controllers |
| src/app/domain | Domain | Entities, repository interfaces, use cases |
| src/app/infrastructure | Infra | DB/LDAP/Redis/Celery/gRPC adapters |
| src/app/tasks | Task | Celery tasks |
| monitoring/ | Observability | Grafana + Prometheus + Loki stack |
| infra/ | Ops | Dockerfiles, compose files, K8s manifests |
