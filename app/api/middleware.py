"""HTTP 中间件：请求 ID、精确 CORS。

安全要求：
- 每个请求携带请求追踪编号（X-Request-ID），便于错误正文与日志对齐；
- CORS 只允许明确白名单的来源（FRONTEND_ORIGIN），不走通配。
"""

import time
import uuid
from typing import Any

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.core.config import settings


class RequestIDMiddleware(BaseHTTPMiddleware):
    """为每个请求分配/透传 request_id，写入 request.state 并在响应头返回。"""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get(settings.request_id_header) or str(uuid.uuid4())
        request.state.request_id = request_id
        start_time = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers[settings.request_id_header] = request_id
        duration_ms = round((time.perf_counter() - start_time) * 1000, 1)
        response.headers["X-Response-Time-Ms"] = str(duration_ms)
        return response


def cors_config() -> dict[str, Any]:
    """生成 CORSMiddleware 的参数（由 app.add_middleware(CORSMiddleware, **cors_config()) 使用）。

    仅允许前端来源白名单，不使用通配符。
    """
    origins = [origin.strip() for origin in settings.frontend_origin.split(",") if origin.strip()]
    return {
        "allow_origins": origins,
        "allow_credentials": True,
        "allow_methods": ["GET", "POST", "PATCH", "DELETE", "PUT", "OPTIONS", "HEAD"],
        "allow_headers": ["Authorization", "Content-Type", "X-CSRF-Token", "X-Request-ID", "Idempotency-Key", "Range"],
        "expose_headers": ["X-Request-ID", "X-Response-Time-Ms", "Content-Disposition", "Accept-Ranges", "Content-Range"],
        "max_age": 600,
    }
