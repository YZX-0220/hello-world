"""Only aggregate counts are public; browser identity and visit metadata stay private."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

TrafficPath = Literal["/", "/login", "/workspace", "/tv", "/settings/api"]


class TrackSiteVisit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: UUID
    path: TrafficPath
    referrer_origin: str | None = Field(default=None, max_length=512)


class DailyTokens(BaseModel):
    date: str
    tokens: int = Field(default=0, ge=0)


class CreationsBreakdown(BaseModel):
    videos: int = Field(default=0, ge=0)
    images: int = Field(default=0, ge=0)


class SiteTrafficSummary(BaseModel):
    total_visits: int = Field(ge=0)
    started_at: datetime | None = None
    session_timeout_minutes: int = 30
    # 平台全站公开统计指标
    total_tokens: int = Field(default=0, ge=0)
    total_creations: int = Field(default=0, ge=0)
    creations_breakdown: CreationsBreakdown = Field(default_factory=CreationsBreakdown)
    total_users: int = Field(default=0, ge=0)
    published_works: int = Field(default=0, ge=0)
    daily_tokens_14d: list[DailyTokens] = Field(default_factory=list)
    total_assets: int = Field(default=0, ge=0)
    models_and_templates_count: int = Field(default=0, ge=0)


class TrackSiteVisitResult(SiteTrafficSummary):
    counted: bool
