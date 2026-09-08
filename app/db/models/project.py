"""视频项目与不可变方案版本表。字段以《实施计划》5.11/5.12 为准。

video_projects.current_spec_json 是当前方案唯一事实来源；
conversation_contexts 只保存长对话摘要，不重复保存项目状态。
"""

from datetime import datetime

from sqlalchemy import CheckConstraint, UniqueConstraint
from sqlmodel import Field, SQLModel

from app.core.enums import VersionSource
from app.core.ids import new_id
from app.core.time import now


class VideoProject(SQLModel, table=True):
    __tablename__ = "video_projects"

    id: str = Field(default_factory=new_id, primary_key=True)
    conversation_id: str = Field(foreign_key="conversations.id", unique=True, ondelete="CASCADE")
    user_id: str = Field(foreign_key="users.id", index=True, ondelete="CASCADE")
    current_spec_json: str = Field(default="{}")  # 完整 VideoBrief（规范化 TEXT）
    current_spec_version: int = Field(default=0)
    confirmed_spec_version: int | None = Field(default=None)
    confirmed_at: datetime | None = Field(default=None)
    created_at: datetime = Field(default_factory=now)
    updated_at: datetime = Field(default_factory=now)

    __table_args__ = (
        # 确认版本不得大于当前版本
        CheckConstraint(
            "confirmed_spec_version IS NULL OR confirmed_spec_version <= current_spec_version",
            name="ck_projects_confirmed_le_current",
        ),
    )


class VideoProjectVersion(SQLModel, table=True):
    __tablename__ = "video_project_versions"

    id: str = Field(default_factory=new_id, primary_key=True)
    project_id: str = Field(foreign_key="video_projects.id", index=True, ondelete="CASCADE")
    version: int = Field()  # 初始空方案为 0，后续单调递增
    spec_json: str = Field(default="{}")  # 不可变完整快照
    suggested_prompt: str | None = Field(default=None, max_length=20000)
    source_type: str = Field(default=VersionSource.SYSTEM.value, max_length=20)
    source_message_id: str | None = Field(default=None, foreign_key="messages.id")
    created_at: datetime = Field(default_factory=now)

    __table_args__ = (
        UniqueConstraint("project_id", "version", name="uq_project_versions_project_version"),
    )
