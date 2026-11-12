"""剪辑工程表 (ClipProject) 数据库模型。"""

from datetime import datetime

from sqlalchemy import Column, Text
from sqlmodel import Field, SQLModel

from app.core.ids import new_id
from app.core.time import now


class ClipProject(SQLModel, table=True):
    __tablename__ = "clip_projects"

    id: str = Field(default_factory=new_id, primary_key=True)
    user_id: str = Field(foreign_key="users.id", index=True, ondelete="CASCADE")
    title: str = Field(default="未命名工程", max_length=100)
    description: str = Field(default="", max_length=500)

    # WebAV 时间线草稿结构（JSON 字符串），包含 tracks, clips, effects, transitions 等
    timeline_json: str = Field(default="{}", sa_column=Column(Text, nullable=False))

    duration_ms: int = Field(default=0)  # 总时长（毫秒）
    fps: int = Field(default=30)
    width: int = Field(default=1080)
    height: int = Field(default=1920)

    cover_asset_id: str | None = Field(default=None, foreign_key="assets.id", ondelete="SET NULL")
    exported_asset_id: str | None = Field(
        default=None, foreign_key="assets.id", ondelete="SET NULL"
    )

    version: int = Field(default=1)  # 乐观锁版本号
    created_at: datetime = Field(default_factory=now)
    updated_at: datetime = Field(default_factory=now)
