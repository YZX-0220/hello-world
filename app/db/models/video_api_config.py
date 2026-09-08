"""用户视频 API 配置与版本化快照表。字段以《实施计划》5.13/5.14 为准。

config 只表示用户看到的"配置身份"，实际协议、地址、模型、凭据与能力保存在 revision。
视频任务引用创建时的 revision，因此用户后续修改配置不破坏运行中的旧任务。
"""

from datetime import datetime

from sqlalchemy import Index, UniqueConstraint, text
from sqlmodel import Field, SQLModel

from app.core.enums import ApiSourceType, CapabilitySource, VerificationStatus
from app.core.ids import new_id
from app.core.time import now


class VideoApiConfig(SQLModel, table=True):
    __tablename__ = "video_api_configs"

    id: str = Field(default_factory=new_id, primary_key=True)
    user_id: str = Field(foreign_key="users.id", index=True, ondelete="CASCADE")
    display_name: str = Field(max_length=40)  # 1~40 字符，同用户未删除配置中唯一
    current_revision: int = Field(default=1)
    status: str = Field(default="active", max_length=20)  # active/disabled/deleted
    version: int = Field(default=0)  # 修改配置身份时乐观锁
    created_at: datetime = Field(default_factory=now)
    updated_at: datetime = Field(default_factory=now)
    deleted_at: datetime | None = Field(default=None)

    __table_args__ = (
        # 同一用户的未删除配置名称唯一
        Index(
            "uq_configs_user_display_name",
            "user_id",
            "display_name",
            unique=True,
            sqlite_where=text("status != 'deleted'"),
        ),
    )


class VideoApiConfigRevision(SQLModel, table=True):
    __tablename__ = "video_api_config_revisions"

    id: str = Field(default_factory=new_id, primary_key=True)
    config_id: str = Field(foreign_key="video_api_configs.id", index=True, ondelete="CASCADE")
    revision: int = Field()  # 单调递增
    source_type: str = Field(default=ApiSourceType.OFFICIAL.value, max_length=20)
    protocol_code: str = Field(max_length=64)  # 已启用协议
    template_code: str | None = Field(default=None, max_length=64)  # 通用引擎必填，原生协议为空
    template_version: str | None = Field(default=None, max_length=64)
    base_url: str | None = Field(default=None, max_length=500)  # 规范化 URL
    remote_model_id: str = Field(max_length=160)
    encrypted_auth_json: str = Field(default="")  # Fernet 密文
    public_options_json: str = Field(default="{}")  # 白名单字段
    capability_profile_code: str | None = Field(default=None, max_length=64)
    capabilities_json: str = Field(default="[]")  # 实际允许能力快照
    capability_source: str = Field(default=CapabilitySource.USER_DECLARED.value, max_length=20)
    verification_status: str = Field(default=VerificationStatus.UNVERIFIED.value, max_length=20)
    key_hint_json: str = Field(default="{}")  # 每项凭据末四位
    relay_risk_accepted_at: datetime | None = Field(default=None)  # 中转配置必填
    last_verified_at: datetime | None = Field(default=None)
    last_error_code: str | None = Field(default=None, max_length=64)
    created_at: datetime = Field(default_factory=now)

    __table_args__ = (
        UniqueConstraint("config_id", "revision", name="uq_config_revisions_config_revision"),
    )
