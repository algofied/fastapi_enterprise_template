import time
from prometheus_client import Histogram, Counter
from fastapi import Request

REQUEST_LATENCY = Histogram("app_request_latency_seconds", "Request latency", ["method", "path"])
REQUEST_COUNT = Counter("app_request_total", "Request count", ["method", "path", "status"])

async def metrics_middleware(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    latency = time.perf_counter() - start
    REQUEST_LATENCY.labels(request.method, request.url.path).observe(latency)
    REQUEST_COUNT.labels(request.method, request.url.path, str(response.status_code)).inc()
    return response
