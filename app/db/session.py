"""SQLite 异步数据库引擎与会话。

用户决定：数据库用【异步】AsyncSession（对话/任务等 IO 密集场景收益明显）。
Alembic 迁移使用同步引擎（见 alembic/env.py），与业务运行的异步引擎解耦，两者都读同一套 models。

SQLite PRAGMA：WAL、foreign_keys、busy_timeout（并发写锁与外部键约束）。
"""

from collections.abc import AsyncGenerator
from pathlib import Path
from sqlite3 import Connection as SQLiteConnection

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings


def _ensure_sqlite_parent(database_url: str) -> None:
    """确保 SQLite 数据库文件的父目录存在（异步驱动不会自动建父目录）。"""
    if not database_url.startswith("sqlite"):
        return
    # 形如 sqlite+aiosqlite:///./data/app.db，去掉驱动前缀与 '///'
    file_part = database_url.split("///", 1)[-1]
    if file_part in ("", ":memory:"):
        return
    Path(file_part).expanduser().parent.mkdir(parents=True, exist_ok=True)


_ensure_sqlite_parent(settings.database_url)

engine: AsyncEngine = create_async_engine(
    settings.database_url,
    echo=False,
)


@event.listens_for(engine.sync_engine, "connect")
def _configure_sqlite(dbapi_connection: SQLiteConnection, connection_record: object) -> None:
    """每个 SQLite 连接建立时启用 WAL 日志、外键约束与忙等待超时。"""
    del connection_record
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute(f"PRAGMA busy_timeout={int(settings.sqlite_busy_timeout_ms)}")
    finally:
        cursor.close()


SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 依赖：为每个请求提供一个 AsyncSession，请求结束自动关闭。"""
    async with SessionLocal() as session:
        yield session
