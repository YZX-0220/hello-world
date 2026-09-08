"""Alembic 迁移环境。

迁移使用【同步】 SQLite 引擎（与业务运行的异步引擎解耦），读取与业务相同的 models。
SQLModel.metadata 作为 target_metadata，autogenerate 据此对比生成迁移。
"""

import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import create_engine

# 把 backend 根加入 sys.path，保证 `app` 包可导入
_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

import app.db.models  # noqa: F401  注册全部表到 metadata
from app.core.config import settings
from sqlmodel import SQLModel

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = SQLModel.metadata


def _sync_url() -> str:
    """把异步 URL 转成 Alembic 可用的同步 URL（去掉 aiosqlite 驱动前缀）。"""
    url = settings.database_url
    if url.startswith("sqlite"):
        return url.replace("+aiosqlite", "")
    return url


def run_migrations_offline() -> None:
    """离线模式：仅生成 SQL，不连接数据库。"""
    context.configure(
        url=_sync_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """在线模式：建立连接并执行迁移。SQLite 迁移是删除重建受影响表格。"""
    engine = create_engine(_sync_url())
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
