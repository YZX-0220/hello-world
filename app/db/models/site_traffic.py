"""Anonymous visits, durable event deduplication and the public cumulative total."""

from datetime import datetime

from sqlalchemy import CheckConstraint, Index
from sqlmodel import Field, SQLModel

from app.core.ids import new_id
from app.core.time import now


class SiteVisit(SQLModel, table=True):
    __tablename__ = "site_visits"

    id: str = Field(default_factory=new_id, primary_key=True)
    visitor_hash: str = Field(max_length=64)
    user_id: str | None = Field(default=None, foreign_key="users.id", ondelete="SET NULL")
    started_at: datetime = Field(default_factory=now)
    last_seen_at: datetime = Field(default_factory=now)
    entry_path: str = Field(max_length=64)
    ip_hash: str | None = Field(default=None, max_length=64)
    ip_address: str | None = Field(default=None, max_length=45, index=True)
    ip_version: int | None = Field(default=None)
    ip_is_public: bool | None = Field(default=None)
    ip_source: str | None = Field(default=None, max_length=24)
    device_type: str = Field(default="unknown", max_length=20)
    browser: str = Field(default="unknown", max_length=40)
    operating_system: str = Field(default="unknown", max_length=40)
    referrer_host: str | None = Field(default=None, max_length=253)

    __table_args__ = (Index("ix_site_visits_visitor_seen", "visitor_hash", "last_seen_at"),)


class SiteVisitEvent(SQLModel, table=True):
    __tablename__ = "site_visit_events"

    id: str = Field(primary_key=True, max_length=36)
    visitor_hash: str = Field(max_length=64)
    visit_id: str = Field(foreign_key="site_visits.id", ondelete="CASCADE")
    path: str = Field(max_length=64)
    ip_address: str | None = Field(default=None, max_length=45, index=True)
    ip_version: int | None = Field(default=None)
    ip_is_public: bool | None = Field(default=None)
    ip_source: str | None = Field(default=None, max_length=24)
    created_at: datetime = Field(default_factory=now, index=True)


class SiteTrafficTotal(SQLModel, table=True):
    __tablename__ = "site_traffic_totals"

    id: int = Field(default=1, primary_key=True)
    total_visits: int = Field(default=0)
    started_at: datetime | None = Field(default=None)
    updated_at: datetime = Field(default_factory=now)

    __table_args__ = (
        CheckConstraint("id = 1", name="ck_site_traffic_singleton"),
        CheckConstraint("total_visits >= 0", name="ck_site_traffic_nonnegative"),
    )
