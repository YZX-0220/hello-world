"""视频任务三张表。字段以《实施计划》5.16/5.17/5.18 为准。

video_jobs 固定引用创建时的方案版本、配置 revision、模板与模型能力版本；
request_json 是无密钥的标准化命令；download_status 与生成 status 相互独立。
"""

from datetime import datetime

from sqlalchemy import Index, UniqueConstraint, text
from sqlmodel import Field, SQLModel

from app.core.enums import DownloadStatus, JobEventType, VideoJobStatus
from app.core.ids import new_id
from app.core.time import now


class VideoJob(SQLModel, table=True):
    __tablename__ = "video_jobs"

    id: str = Field(default_factory=new_id, primary_key=True)
    user_id: str = Field(foreign_key="users.id", index=True, ondelete="CASCADE")
    conversation_id: str = Field(foreign_key="conversations.id", index=True, ondelete="CASCADE")
    project_id: str = Field(foreign_key="video_projects.id", index=True, ondelete="CASCADE")
    project_version_id: str = Field(foreign_key="video_project_versions.id", ondelete="RESTRICT")
    project_version: int = Field()  # 固定版本
    # 平台自有通道（请求 api_config_id="platform"）不引用用户配置：api_config_id 存 NULL、
    # revision 也为 None；用户自配通道则存真实 config.id / revision.id（非空）。
    api_config_id: str | None = Field(default=None, foreign_key="video_api_configs.id", ondelete="RESTRICT")
    api_config_revision_id: str | None = Field(default=None, foreign_key="video_api_config_revisions.id", ondelete="RESTRICT")
    previous_job_id: str | None = Field(default=None, foreign_key="video_jobs.id")
    idempotency_key: str = Field(max_length=64)  # 请求头值
    request_fingerprint: str = Field(max_length=128)  # 规范化请求摘要
    protocol_code: str = Field(max_length=64)  # 创建时快照
    adapter_version: str | None = Field(default=None, max_length=64)
    template_code: str | None = Field(default=None, max_length=64)
    template_version: str | None = Field(default=None, max_length=64)
    model_profile_code: str | None = Field(default=None, max_length=64)
    model_profile_version: str | None = Field(default=None, max_length=64)
    remote_model_id: str = Field(max_length=160)
    mode: str = Field(max_length=50)  # VideoMode.value
    status: str = Field(default=VideoJobStatus.CREATED.value, max_length=20)
    request_json: str = Field(default="{}")  # 无密钥标准化命令
    provider_task_id: str | None = Field(default=None, max_length=200)
    provider_context_id: str | None = Field(default=None, max_length=200)
    progress: int | None = Field(default=None)
    encrypted_result_ref_json: str | None = Field(default=None)  # 远端结果定位信息（加密）
    download_status: str = Field(default=DownloadStatus.NOT_STARTED.value, max_length=20)
    download_attempts: int = Field(default=0)
    local_asset_id: str | None = Field(default=None, foreign_key="assets.id")
    error_code: str | None = Field(default=None, max_length=64)
    error_message: str | None = Field(default=None, max_length=2000)  # 脱敏、截断
    next_poll_at: datetime | None = Field(default=None)
    poll_count: int = Field(default=0)
    submitted_at: datetime | None = Field(default=None)
    completed_at: datetime | None = Field(default=None)
    created_at: datetime = Field(default_factory=now)
    updated_at: datetime = Field(default_factory=now)

    __table_args__ = (
        UniqueConstraint("user_id", "idempotency_key", name="uq_video_jobs_user_idempotency"),
        # 远端 ID 非空时唯一，防止同一厂商任务被重复登记
        Index(
            "uq_video_jobs_revision_providertask",
            "api_config_revision_id",
            "provider_task_id",
            unique=True,
            sqlite_where=text("provider_task_id IS NOT NULL"),
        ),
        Index("ix_video_jobs_user_created", "user_id", "created_at"),
        Index("ix_video_jobs_status_nextpoll", "status", "next_poll_at"),
        Index("ix_video_jobs_download_completed", "download_status", "completed_at"),
    )


class VideoJobAsset(SQLModel, table=True):
    __tablename__ = "video_job_assets"

    id: str = Field(default_factory=new_id, primary_key=True)
    video_job_id: str = Field(foreign_key="video_jobs.id", index=True, ondelete="CASCADE")
    asset_id: str = Field(foreign_key="assets.id", index=True)
    role: str = Field(max_length=30)  # first_frame/last_frame/reference/source_video/audio
    position: int = Field(default=0)  # 同一角色内的顺序
    created_at: datetime = Field(default_factory=now)

    __table_args__ = (
        UniqueConstraint("video_job_id", "role", "position", name="uq_video_job_assets_role_position"),
    )


class VideoJobEvent(SQLModel, table=True):
    __tablename__ = "video_job_events"

    id: str = Field(default_factory=new_id, primary_key=True)
    video_job_id: str = Field(foreign_key="video_jobs.id", index=True, ondelete="CASCADE")
    event_type: str = Field(default=JobEventType.POLL.value, max_length=20)
    from_status: str | None = Field(default=None, max_length=20)
    to_status: str | None = Field(default=None, max_length=20)
    safe_payload_json: str = Field(default="{}")  # 无密钥、截断
    created_at: datetime = Field(default_factory=now)
