"""平台统一示例库。文件存放在 assets，作品资料与发布状态单独保存。"""

from datetime import datetime

from sqlalchemy import CheckConstraint, Index, Text
from sqlmodel import Field, SQLModel

from app.core.ids import new_id
from app.core.time import now


class MaterialLibraryItem(SQLModel, table=True):
    __tablename__ = "material_library_items"

    id: str = Field(default_factory=new_id, primary_key=True)
    title: str = Field(max_length=200)
    description: str = Field(sa_type=Text)  # 原始 Markdown；前端渲染时需清理 HTML
    model_name: str = Field(max_length=200, index=True)
    video_asset_id: str = Field(foreign_key="assets.id", ondelete="RESTRICT", index=True)
    cover_asset_id: str | None = Field(
        default=None, foreign_key="assets.id", ondelete="RESTRICT", index=True
    )
    status: str = Field(default="draft", max_length=20)
    version: int = Field(default=1)
    created_by: str | None = Field(default=None, foreign_key="users.id", ondelete="SET NULL")
    created_at: datetime = Field(default_factory=now)
    updated_at: datetime = Field(default_factory=now)
    deleted_at: datetime | None = Field(default=None)

    __table_args__ = (
        CheckConstraint("status IN ('draft', 'published', 'deleted')", name="ck_library_status"),
        CheckConstraint("version >= 1", name="ck_library_version"),
        Index("ix_library_status_created", "status", "created_at", "id"),
    )
