"""国家负面提示词（Cultural Guidance）与提示词模板数据表模型。"""

from datetime import datetime

from sqlalchemy import Index, Text, UniqueConstraint
from sqlmodel import Field, SQLModel

from app.core.ids import new_id
from app.core.time import now


class CulturalGuidance(SQLModel, table=True):
    __tablename__ = "cultural_guidances"

    id: int | None = Field(default=None, primary_key=True)
    code: str = Field(max_length=16, unique=True, index=True)  # 国家/地区代码，如 CN, US, GB
    name: str = Field(max_length=64)  # 中文名，如 中国、美国
    negative_prompt: str = Field(sa_type=Text)  # 负面提示词正文
    taboo: str | None = Field(default=None, sa_type=Text)  # 禁忌说明
    sort_order: int = Field(default=0, index=True)  # 排序权重
    is_enabled: bool = Field(default=True, index=True)
    created_at: datetime = Field(default_factory=now)
    updated_at: datetime = Field(default_factory=now)


class PromptTemplate(SQLModel, table=True):
    __tablename__ = "prompt_templates"

    id: str = Field(default_factory=new_id, primary_key=True)
    user_id: str | None = Field(
        default=None, foreign_key="users.id", index=True, ondelete="CASCADE"
    )
    code: str | None = Field(default=None, max_length=64, index=True)  # 预置模板编码
    scope: str = Field(default="user", max_length=16, index=True)  # system | user
    category: str = Field(
        default="positive", max_length=32, index=True
    )  # positive | negative | cultural | storyboard
    name: str = Field(max_length=100)
    description: str | None = Field(default=None, max_length=500)
    content: str = Field(sa_type=Text)  # 提示词正文
    negative_prompt: str | None = Field(default=None, sa_type=Text)  # 配套负面词
    variables_json: str = Field(default="[]", sa_type=Text)  # 变量名列表 JSON
    current_version: int = Field(default=1)  # 当前生效版本
    status: str = Field(default="active", max_length=20, index=True)  # active | archived | deleted
    created_at: datetime = Field(default_factory=now)
    updated_at: datetime = Field(default_factory=now)


class PromptTemplateVersion(SQLModel, table=True):
    __tablename__ = "prompt_template_versions"

    id: str = Field(default_factory=new_id, primary_key=True)
    template_id: str = Field(foreign_key="prompt_templates.id", index=True, ondelete="CASCADE")
    version: int = Field()
    name: str = Field(max_length=100)
    content: str = Field(sa_type=Text)
    negative_prompt: str | None = Field(default=None, sa_type=Text)
    variables_json: str = Field(default="[]", sa_type=Text)
    source_type: str = Field(default="manual", max_length=20)  # init | edit | rollback
    change_note: str | None = Field(default=None, max_length=500)
    created_by: str | None = Field(default=None, foreign_key="users.id", ondelete="SET NULL")
    created_at: datetime = Field(default_factory=now)

    __table_args__ = (
        UniqueConstraint("template_id", "version", name="uq_prompt_template_version"),
        Index("ix_prompt_template_version_query", "template_id", "version"),
    )
