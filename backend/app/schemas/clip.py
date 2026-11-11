"""剪辑工程与资料库 Schemas。"""

from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field


class ClipProjectView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    title: str
    description: str
    timeline_json: str
    duration_ms: int
    fps: int
    width: int
    height: int
    cover_asset_id: str | None = None
    exported_asset_id: str | None = None
    version: int
    created_at: datetime
    updated_at: datetime


class CreateClipProjectRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    title: str = Field(default="未命名剪辑草稿", max_length=100)
    width: int = Field(default=1080, ge=100, le=4096)
    height: int = Field(default=1920, ge=100, le=4096)
    fps: int = Field(default=30, ge=1, le=120)


class UpdateClipProjectRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    title: str = Field(max_length=100)
    timeline_json: str
    duration_ms: int = Field(default=0, ge=0)
    expected_version: int = Field(ge=1)


class StorageQuotaView(BaseModel):
    quota_bytes: int
    used_bytes: int
    available_bytes: int
    quota_gb: float
    usage_percent: float
    asset_count: int


class LibraryAssetView(BaseModel):
    id: str
    file_name: str
    size_bytes: int
    mime_type: str
    kind: Literal["video", "image", "audio"]
    purpose: str
    sha256: str
    duration_ms: int | None = None
    width: int | None = None
    height: int | None = None
    url: str
    created_at: datetime
