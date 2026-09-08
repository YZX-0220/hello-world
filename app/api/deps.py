"""API 共享依赖：数据库/Redis 会话、覆盖当前用户鉴权与 CSRF 校验。"""

from collections.abc import AsyncGenerator

import redis.asyncio as aioredis
from fastapi import Depends, Request
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.core.errors import AUTH_REQUIRED, CSRF_INVALID, AppError
from app.db.models.user import User
from app.db.redis import get_redis
from app.db.session import get_session
from app.services.auth_service import AuthService, verify_csrf_token


async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 依赖：为每个请求提供一个数据库会话。"""
    async for session in get_session():
        yield session


async def get_auth_service(
    session: AsyncSession = Depends(db_session),
    redis: aioredis.Redis = Depends(get_redis),
) -> AuthService:
    """构造认证服务，供认证路由使用。"""
    return AuthService(session, redis)


def _read_session_token(request: Request) -> str | None:
    """从 Cookie 读取 Session Token。"""
    return request.cookies.get(settings.session_cookie_name)


async def get_current_user(
    request: Request,
    session: AsyncSession = Depends(db_session),
    redis: aioredis.Redis = Depends(get_redis),
) -> User:
    """根据 Cookie 中的 Session Token 解析当前用户；无效则抛 AUTH_REQUIRED。"""
    token = _read_session_token(request)
    if not token:
        raise AppError(AUTH_REQUIRED)
    service = AuthService(session, redis)
    return await service.get_authenticated_user(token)


async def require_csrf(request: Request) -> None:
    """对会修改数据的登录后请求校验 CSRF 与 Origin。

    GET/HEAD/OPTIONS 不需要；登录后的 POST/PATCH/PUT/DELETE 需要：
    - X-CSRF-Token 必须与当前会话绑定；
    - Origin（若携带）必须在前端白名单内。
    """
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return
    token = _read_session_token(request)
    if not token:
        raise AppError(AUTH_REQUIRED)
    provided = request.headers.get("X-CSRF-Token", "")
    if not provided or not verify_csrf_token(token, provided):
        raise AppError(CSRF_INVALID)
    origin = request.headers.get("Origin")
    if origin:
        allowed = [o.strip() for o in settings.frontend_origin.split(",") if o.strip()]
        if origin not in allowed:
            raise AppError(CSRF_INVALID)
