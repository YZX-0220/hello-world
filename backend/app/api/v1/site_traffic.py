"""Public anonymous tracking and a count-only summary, independent of login."""

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, Request, Response
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import db_session
from app.db.redis import get_redis
from app.schemas.site_traffic import SiteTrafficSummary, TrackSiteVisit, TrackSiteVisitResult
from app.services.site_traffic_service import (
    VISITOR_COOKIE,
    SiteTrafficService,
    ensure_visitor_cookie,
    limit_traffic,
    validate_traffic_origin,
    visitor_identity,
)

router = APIRouter(prefix="/site-traffic", tags=["访问统计"])


@router.get("/summary", response_model=SiteTrafficSummary)
async def get_traffic_summary(
    request: Request,
    response: Response,
    session: AsyncSession = Depends(db_session),
):
    response.headers["Cache-Control"] = "no-store"
    ensure_visitor_cookie(request, response)
    return await SiteTrafficService(session).summary()


@router.post("/visits", response_model=TrackSiteVisitResult)
async def track_site_visit(
    payload: TrackSiteVisit,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(db_session),
    redis: aioredis.Redis = Depends(get_redis),
):
    response.headers["Cache-Control"] = "no-store"
    validate_traffic_origin(request)
    identity = visitor_identity(request.cookies.get(VISITOR_COOKIE))
    if identity:
        await limit_traffic(redis, request, identity)
    return await SiteTrafficService(session).track(request, payload)
