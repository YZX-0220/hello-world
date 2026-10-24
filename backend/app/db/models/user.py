"""用户与会话表。字段以《实施计划》5.3/5.4 为准，时间采用服务器本地时间。"""

from datetime import datetime

from sqlmodel import Field, SQLModel

from app.core.enums import UserStatus
from app.core.ids import new_id
from app.core.time import now


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: str = Field(default_factory=new_id, primary_key=True)  # UUID4 字符串
    email: str = Field(max_length=320, unique=True, index=True)  # 规范化后小写
    email_verified_at: datetime = Field(default_factory=now)  # 注册成功时间
    password_hash: str = Field(max_length=255)  # Argon2
    status: str = Field(default=UserStatus.ACTIVE.value, max_length=20)
    created_at: datetime = Field(default_factory=now)
    updated_at: datetime = Field(default_factory=now)


class UserSession(SQLModel, table=True):
    __tablename__ = "user_sessions"

    id: str = Field(default_factory=new_id, primary_key=True)
    user_id: str = Field(foreign_key="users.id", index=True, ondelete="CASCADE")
    token_hash: str = Field(max_length=64, unique=True, index=True)  # SHA-256 摘要
    expires_at: datetime = Field(default_factory=now)
    revoked_at: datetime | None = Field(default=None)
    last_seen_at: datetime | None = Field(default=None)
    ip_address: str | None = Field(default=None, max_length=64)
    user_agent: str | None = Field(default=None, max_length=500)
    created_at: datetime = Field(default_factory=now)
