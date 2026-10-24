"""安全审计事件表。字段以《实施计划》5.19 为准。

只保存行为类型、用户、资源 ID、请求 ID、IP 摘要与安全元数据；
绝不保存密码、验证码、Token、API Key、Prompt 正文或素材内容。
"""

from datetime import datetime

from sqlalchemy import Index
from sqlmodel import Field, SQLModel

from app.core.ids import new_id
from app.core.time import now


class AuditEvent(SQLModel, table=True):
    __tablename__ = "audit_events"

    id: str = Field(default_factory=new_id, primary_key=True)
    user_id: str | None = Field(default=None, foreign_key="users.id", ondelete="SET NULL")
    event_type: str = Field(max_length=64)  # login_success / login_failure / password_reset / ...
    resource_id: str | None = Field(default=None, max_length=64)
    request_id: str | None = Field(default=None, max_length=64)
    ip_hash: str | None = Field(default=None, max_length=64)  # 不存原始 IP，存摘要
    safe_meta_json: str = Field(default="{}")
    created_at: datetime = Field(default_factory=now)

    __table_args__ = (
        Index("ix_audit_user_created", "user_id", "created_at"),
        Index("ix_audit_event_created", "event_type", "created_at"),
    )
