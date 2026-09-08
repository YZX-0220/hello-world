"""对话、消息与视图输出模型（接口说明 3.2/3.3/3.4）。"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.agent import VideoBrief, VideoBriefPatch


class ConversationView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    status: str
    last_message_at: datetime | None
    version: int
    created_at: datetime
    updated_at: datetime


class CitationView(BaseModel):
    title: str
    url: str
    snippet: str
    published_at: datetime | None
    retrieved_at: datetime


class MessageView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    conversation_id: str
    role: str
    content: str
    status: str
    reply_to_message_id: str | None
    client_request_id: str | None
    model_name: str | None
    citations: list[CitationView] = Field(default_factory=list)
    error_code: str | None
    created_at: datetime


class CreateConversationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=100)


class SendMessageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: str = Field(min_length=1, max_length=20000)
    client_request_id: str = Field(min_length=1, max_length=64)
    web_search_enabled: bool = False


class ProjectSummary(BaseModel):
    project_id: str
    current_spec_version: int
    confirmed_spec_version: int | None
    is_current_version_confirmed: bool


class VideoProjectView(BaseModel):
    id: str
    conversation_id: str
    current_spec: VideoBrief
    current_spec_version: int
    suggested_prompt: str | None
    confirmed_spec_version: int | None
    confirmed_at: datetime | None
    is_current_version_confirmed: bool
    created_at: datetime
    updated_at: datetime


class Page(BaseModel):
    items: list[Any]
    next_cursor: str | None


class ConfirmProjectRequest(BaseModel):
    """确认方案版本请求。必须等于当前方案版本。"""

    model_config = ConfigDict(extra="forbid")

    spec_version: int


class PatchProjectRequest(BaseModel):
    """用户手动修改方案请求。patch 只允许 VideoBrief 部分字段。"""

    model_config = ConfigDict(extra="forbid")

    expected_spec_version: int
    patch: VideoBriefPatch
