"""视频任务相关模型（接口说明 3.14/3.15、8.1）。"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CreateVideoCommand(BaseModel):
    """创建并提交视频任务（接口说明 8.1）。"""

    model_config = ConfigDict(extra="forbid")

    conversation_id: str
    project_id: str
    spec_version: int = Field(ge=0)
    api_config_id: str
    mode: str = Field(min_length=1, max_length=50)
    generation_options: dict[str, Any] = Field(default_factory=dict)
    previous_job_id: str | None = Field(default=None)


class ErrorInfo(BaseModel):
    code: str
    message: str
    retryable: bool


class VideoJobView(BaseModel):
    id: str
    conversation_id: str
    project_id: str
    project_version: int
    api_config_id: str
    api_config_revision: int
    previous_job_id: str | None = None
    protocol_code: str
    remote_model_id: str
    mode: str
    status: str
    progress: int | None = None
    generation_options: dict[str, Any] = Field(default_factory=dict)
    download_status: str
    result_asset_id: str | None = None
    # 双轨：下载失败/服务器不支持时可能回退厂商直链（标注临时直链 + 过期时间）
    result_direct_url: str | None = None
    result_expires_at: datetime | None = None
    error: ErrorInfo | None = None
    poll_after_seconds: int | None = None
    submitted_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class VideoJobEventView(BaseModel):
    id: str
    event_type: str
    from_status: str | None = None
    to_status: str | None = None
    message: str
    created_at: datetime
