"""Image configuration identities and immutable task snapshots; credentials never leave backend."""

from datetime import datetime

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel

from app.core.ids import new_id
from app.core.time import now


class ImageApiConfig(SQLModel, table=True):
    __tablename__ = "image_api_configs"
    id: str = Field(default_factory=new_id, primary_key=True)
    user_id: str = Field(foreign_key="users.id", index=True, ondelete="CASCADE")
    display_name: str = Field(max_length=40)
    model: str = Field(max_length=160)
    encrypted_api_key: str
    key_hint: str = Field(max_length=12)
    account_label: str = Field(default="", max_length=80)
    linked_video_api_config_id: str | None = Field(default=None, max_length=64)
    revision: int = Field(default=1)
    status: str = Field(default="active", max_length=20)
    created_at: datetime = Field(default_factory=now)
    updated_at: datetime = Field(default_factory=now)


class ImageJob(SQLModel, table=True):
    __tablename__ = "image_jobs"
    __table_args__ = (UniqueConstraint("user_id", "idempotency_key", name="uq_image_job_request"),)
    id: str = Field(default_factory=new_id, primary_key=True)
    user_id: str = Field(foreign_key="users.id", index=True, ondelete="CASCADE")
    conversation_id: str = Field(foreign_key="conversations.id", index=True, ondelete="CASCADE")
    api_config_id: str = Field(max_length=64)
    config_revision: int
    channel_label: str = Field(max_length=80)
    account_label: str = Field(default="", max_length=80)
    linked_video_api_config_id: str | None = Field(default=None, max_length=64)
    model: str = Field(max_length=160)
    prompt: str
    aspect_ratio: str = Field(max_length=10)
    size: str = Field(max_length=30)
    source_node_id: str | None = Field(default=None, max_length=128)
    parent_job_id: str | None = Field(default=None, max_length=64, index=True)
    reference_images_json: str = "[]"
    edit_context_json: str = "[]"
    compiled_prompt: str = ""
    watermark: bool = False
    idempotency_key: str = Field(max_length=128)
    request_fingerprint: str = Field(max_length=64)
    encrypted_api_key: str
    status: str = Field(default="queued", index=True, max_length=30)
    simulation: bool = False
    asset_id: str | None = Field(default=None, foreign_key="assets.id", ondelete="SET NULL")
    encrypted_result_url: str | None = None
    provider_request_id: str | None = Field(default=None, max_length=200)
    error_message: str | None = None
    generated_at: datetime | None = None
    lease_until: datetime | None = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=now)
    updated_at: datetime = Field(default_factory=now)
