"""提示词模板与版本控制 Schema。"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

TemplateCategory = Literal["positive", "negative", "cultural", "storyboard"]
TemplateScope = Literal["system", "user"]


class PromptTemplateVersionView(BaseModel):
    id: str
    template_id: str
    version: int
    name: str
    content: str
    negative_prompt: str | None = None
    variables: list[str] = Field(default_factory=list)
    source_type: str
    change_note: str | None = None
    created_by: str | None = None
    created_at: datetime


class PromptTemplateView(BaseModel):
    id: str
    user_id: str | None = None
    code: str | None = None
    scope: str
    category: str
    name: str
    description: str | None = None
    content: str
    negative_prompt: str | None = None
    variables: list[str] = Field(default_factory=list)
    current_version: int
    status: str
    created_at: datetime
    updated_at: datetime


class PromptTemplateListResponse(BaseModel):
    items: list[PromptTemplateView]


class CreatePromptTemplateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    category: TemplateCategory = "positive"
    content: str = Field(min_length=1)
    negative_prompt: str | None = None
    description: str | None = Field(default=None, max_length=500)
    code: str | None = Field(default=None, max_length=64)
    change_note: str | None = Field(default="创建初始版本", max_length=500)


class UpdatePromptTemplateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=100)
    category: TemplateCategory | None = None
    content: str | None = Field(default=None, min_length=1)
    negative_prompt: str | None = None
    description: str | None = Field(default=None, max_length=500)
    change_note: str | None = Field(default=None, max_length=500)


class RollbackPromptTemplateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_version: int = Field(ge=1)
    change_note: str | None = Field(default=None, max_length=500)
