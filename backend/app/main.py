"""FastAPI 应用入口。

- lifespan：初始化日志、生产密钥校验、数据目录；优雅关闭异步引擎。
- /healthz：只表示进程存活，不访问 DB/Redis。
- /readyz：检查数据库（必需）、Redis 与存储目录（可降级），返回 ready/degraded/unready。
- /api/v1：业务路由（本批次为空，后继批次加入）。
"""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import redis.asyncio as aioredis
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import text
from starlette.middleware.cors import CORSMiddleware

from app.api.middleware import RequestIDMiddleware, cors_config
from app.api.v1.router import register_v1_routes
from app.core.config import settings
from app.core.errors import register_exception_handlers
from app.core.logging import setup_logging
from app.core.time import iso8601, now
from app.db.session import engine

_READYZ_DB_MSG = "数据库不可用"
_READYZ_REDIS_MSG = "验证码和短缓存暂时不可用"


def _ensure_directories() -> None:
    """确保存储目录存在（SQLite/上传/视频/临时）。"""
    for path in (settings.storage_root, settings.upload_dir, settings.video_dir, settings.temp_dir):
        Path(path).mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(_: FastAPI):
    """应用启动初始化，关闭时释放资源。"""
    setup_logging()
    settings.ensure_secure()  # 生产环境密钥校验，不通过则拒绝启动
    _ensure_directories()
    yield
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, version=settings.version, lifespan=lifespan)

    # 统一错误响应
    register_exception_handlers(app)

    # 中间件：先请求 ID，后 CORS（注意顺序）
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(CORSMiddleware, **cors_config())

    # 健康检查（不带 /api/v1 前缀）
    app.add_api_route("/healthz", healthz, methods=["GET"])
    app.add_api_route("/readyz", readyz, methods=["GET"])

    # 业务路由
    register_v1_routes(app)

    return app


async def healthz() -> dict[str, Any]:
    """进程存活检查。不访问数据库与 Redis。"""
    return {
        "status": "ok",
        "service": "hello-world-backend",
        "version": settings.version,
        "time": iso8601(now()),
    }


async def readyz() -> JSONResponse:
    """就绪检查。数据库为必需依赖；Redis/存储降级时仍返回 200（degraded）。"""
    components: dict[str, Any] = {}

    # ---- 数据库（必需） ----
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        components["database"] = {"status": "ok", "latency_ms": 1, "message": None}
    except Exception:
        components["database"] = {"status": "unavailable", "latency_ms": None, "message": _READYZ_DB_MSG}

    # ---- Redis（可降级） ----
    redis_status = "ok"
    try:
        client = aioredis.from_url(settings.redis_url, socket_connect_timeout=2)
        await client.ping()
        await client.close()
        components["redis"] = {"status": "ok", "latency_ms": 1, "message": None}
    except Exception:
        redis_status = "unavailable"
        components["redis"] = {"status": "unavailable", "latency_ms": None, "message": _READYZ_REDIS_MSG}

    # ---- 存储（可降级） ----
    storage_status = "ok"
    try:
        probe = Path(settings.temp_dir) / ".readyz-probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        components["storage"] = {"status": "ok", "latency_ms": 1, "message": None}
    except Exception:
        storage_status = "unavailable"
        components["storage"] = {"status": "unavailable", "latency_ms": None, "message": "存储目录不可用"}

    db_status = components["database"]["status"]
    if db_status == "unavailable":
        overview_status = "unready"  # 必需依赖不可用 → 503
    else:
        overview_status = "ready" if redis_status == "ok" and storage_status == "ok" else "degraded"

    body = {"status": overview_status, "components": components, "time": iso8601(now())}
    status_code = 503 if overview_status == "unready" else 200
    return JSONResponse(status_code=status_code, content=body)


app = create_app()
