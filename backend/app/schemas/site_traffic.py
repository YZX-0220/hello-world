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


class SiteTrafficSummary(BaseModel):
    total_visits: int = Field(ge=0)
    started_at: datetime | None
    session_timeout_minutes: int = 30


class TrackSiteVisitResult(SiteTrafficSummary):
    counted: bool
