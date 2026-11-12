"""国家/地区负面提示词 Schema。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CulturalGuidanceItem(BaseModel):
    id: int
    code: str
    name: str
    negative_prompt: str
    taboo: str | None = None
    sort_order: int = 0
    is_enabled: bool = True
    created_at: datetime
    updated_at: datetime


class CulturalGuidanceListResponse(BaseModel):
    items: list[CulturalGuidanceItem]


class CreateCulturalGuidanceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=16)
    name: str = Field(min_length=1, max_length=64)
    negative_prompt: str = Field(min_length=1)
    taboo: str | None = Field(default=None, max_length=2000)
    sort_order: int = Field(default=0)
    is_enabled: bool = True


class UpdateCulturalGuidanceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=64)
    negative_prompt: str | None = Field(default=None, min_length=1)
    taboo: str | None = Field(default=None, max_length=2000)
    sort_order: int | None = None
    is_enabled: bool | None = None
