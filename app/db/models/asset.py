"""素材表。字段以《实施计划》5.15 为准。

本地文件只使用相对 Storage Root 的 storage_key；业务接口不接受本机路径。
"""

from datetime import datetime

from sqlalchemy import CheckConstraint, Index
from sqlmodel import Field, SQLModel

from app.core.enums import AssetStatus
from app.core.ids import new_id
from app.core.time import now


class Asset(SQLModel, table=True):
    __tablename__ = "assets"

    id: str = Field(default_factory=new_id, primary_key=True)
    user_id: str = Field(foreign_key="users.id", index=True, ondelete="CASCADE")
    conversation_id: str | None = Field(default=None, foreign_key="conversations.id", ondelete="SET NULL")
    kind: str = Field(max_length=20)  # image/video/audio
    purpose: str = Field(max_length=30)  # 首帧、尾帧、参考等
    original_name: str = Field(default="", max_length=500)  # 仅展示
    storage_key: str = Field(unique=True, max_length=1000)  # Storage Root 下相对路径
    mime_type: str = Field(max_length=200)  # 服务端检测值
    size_bytes: int = Field()
    sha256: str = Field(max_length=64)  # 64 位十六进制
    width: int | None = Field(default=None)
    height: int | None = Field(default=None)
    duration_ms: int | None = Field(default=None)
    status: str = Field(default=AssetStatus.UPLOADING.value, max_length=20)
    retention_until: datetime | None = Field(default=None)
    created_at: datetime = Field(default_factory=now)
    deleted_at: datetime | None = Field(default=None)

    __table_args__ = (
        CheckConstraint("size_bytes > 0", name="ck_assets_size_positive"),
        Index("ix_assets_user_created", "user_id", "created_at"),
        # 可选：用于提示重复上传，但不能跨用户推断文件存在
        Index("ix_assets_user_sha256", "user_id", "sha256"),
    )
