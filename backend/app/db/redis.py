"""Redis 客户端。

开发/测试使用 fakeredis（内存模拟）避免依赖真实 Redis；生产用 REDIS_URL 的真实实例。
decode_responses=True 使读回的验证码/限流值直接为字符串，便于处理。
"""

from collections.abc import AsyncGenerator

import redis.asyncio as aioredis

from app.core.config import settings


def build_redis_client() -> aioredis.Redis:
    """根据配置构建 Redis 客户端（懒连接）。"""
    return aioredis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_connect_timeout=3,
        socket_timeout=3,
    )


async def get_redis() -> AsyncGenerator[aioredis.Redis, None]:
    """FastAPI 依赖：为每个请求提供一个 Redis 客户端，请求结束关闭。"""
    client = build_redis_client()
    try:
        yield client
    finally:
        await client.close()
