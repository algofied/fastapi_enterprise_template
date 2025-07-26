# # src/app/core/request_context.py
# import uuid
# import contextvars
# from typing import Optional
# from starlette.middleware.base import BaseHTTPMiddleware
# from starlette.types import ASGIApp
# from starlette.requests import Request
# from app.utils.hp_py_logger import set_request_context, clear_request_context, update_request_context

# class RequestContextMiddleware(BaseHTTPMiddleware):
#     """
#     Sets per-request correlation context so all logs include request_id, user, path, method, ip.
#     Clears context after the request completes.
#     """

#     def __init__(self, app: ASGIApp):
#         super().__init__(app)

#     async def dispatch(self, request: Request, call_next):
#         rid = request.headers.get("x-request-id") or str(uuid.uuid4())
#         ip = request.client.host if request.client else None
#         set_request_context(
#             request_id=rid,
#             user=None,                     # auth dependency can update later
#             method=request.method,
#             path=request.url.path,
#             ip=ip,
#         )
#         try:
#             response = await call_next(request)
#             response.headers["x-request-id"] = rid
#             return response
#         finally:
#             clear_request_context()

# # Optional: call this from your auth dependency once user is known
# def set_user_in_request_context(username: Optional[str]):
#     update_request_context(user=username)
