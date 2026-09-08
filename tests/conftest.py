"""测试夹具：独立临时数据库 + fakeredis + 覆盖依赖的 AsyncClient。

重要：本模块在顶层就强制 email/video Provider 为 fake，并注入一把有效的 Fernet 密钥，
确保任何测试都绝不可能通过真实 SMTP 发送邮件，也不会因缺加密密钥而失败。
（不依赖每个 fixture 单独设置 / 事后还原，避免 .env 的 smtp 值在收集阶段泄漏到测试。）
"""

import fakeredis.aioredis as fakeredis_async
import httpx
import pytest_asyncio
from app.api import deps
from app.core.config import settings
from app.core.security import generate_fernet_key
from app.db.redis import get_redis
from app.main import app
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

# ---- 顶层强制测试环境，绝不触碰真实外部凭据 ----
settings.email_provider = "fake"
settings.video_provider = "fake"
settings.credential_encryption_keys = generate_fernet_key()
settings.video_poll_interval_seconds = 0  # 测试内快速推进轮询状态


@pytest_asyncio.fixture
async def db_engine(tmp_path):
    """每次测试一个独立的临时 SQLite 数据库（自动建表）。"""
    url = f"sqlite+aiosqlite:///{tmp_path / 'test.db'}"
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def client(db_engine, tmp_path):
    """覆盖数据库/Redis 依赖后的 AsyncClient。"""
    # 隔离存储目录，避免测试素材写入真实 ./data
    settings.storage_root = str(tmp_path / "media")
    session_factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    fake_redis = fakeredis_async.FakeRedis(decode_responses=True)

    async def override_db_session():
        async with session_factory() as s:
            yield s

    async def override_redis():
        yield fake_redis

    app.dependency_overrides.update(
        {deps.db_session: override_db_session, get_redis: override_redis}
    )

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c

    app.dependency_overrides.clear()
    await fake_redis.aclose()
