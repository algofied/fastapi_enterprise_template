from __future__ import annotations
import time
from typing import Callable
from fastapi import Request, Response
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
)

REQUEST_LATENCY = Histogram(
    "http_request_latency_seconds",
    "Latency of HTTP requests",
    ["method", "path"]
)

async def metrics_middleware(request: Request, call_next: Callable):
    start = time.perf_counter()
    response: Response = await call_next(request)
    elapsed = time.perf_counter() - start

    # Label cardinality: avoid raw dynamic paths; you can normalize (e.g., /users/{id} -> /users/:id)
    path = request.url.path
    REQUEST_COUNT.labels(request.method, path, str(response.status_code)).inc()
    REQUEST_LATENCY.labels(request.method, path).observe(elapsed)
    return response

# Expose /metrics response
def metrics_response():
    from fastapi import Response
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
