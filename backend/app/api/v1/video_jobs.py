"""视频任务路由（/api/v1/video-jobs...，需登录；创建需 CSRF + Idempotency-Key）。

阶段 9 补充：取消 / 重试下载；GET 单任务会按 next_poll_at + Redis 锁安全触发轮询。
"""

from typing import Any

from fastapi import APIRouter, Depends, Header, Query
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import db_session, get_current_user, require_csrf
from app.db.models.user import User
from app.db.redis import get_redis
from app.schemas.conversation import Page
from app.schemas.video_job import CreateVideoCommand, VideoJobView
from app.services.video_job_service import VideoJobService

router = APIRouter()


def _service(session: AsyncSession, redis: Any) -> VideoJobService:
    return VideoJobService(session, redis)


@router.post("/video-jobs", response_model=VideoJobView, status_code=202)
async def create_video_job(
    payload: CreateVideoCommand,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    user: User = Depends(get_current_user),
    _csrf: None = Depends(require_csrf),
    session: AsyncSession = Depends(db_session),
    redis: Any = Depends(get_redis),
):
    svc = _service(session, redis)
    job, _already = await svc.create(user.id, payload, idempotency_key)
    return await svc.to_view(job)


@router.get("/video-jobs", response_model=Page)
async def list_video_jobs(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(db_session),
    redis: Any = Depends(get_redis),
    limit: int = Query(default=20, ge=1, le=100),
    conversation_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    download_status: str | None = Query(default=None),
    cursor: str | None = Query(default=None),
):
    svc = _service(session, redis)
    rows, next_cursor = await svc.list_jobs(user.id, conversation_id, status, download_status, limit, cursor)
    items = [await svc.to_view(j) for j in rows]
    return Page(items=items, next_cursor=next_cursor)


@router.get("/video-jobs/{job_id}", response_model=VideoJobView)
async def get_video_job(
    job_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(db_session),
    redis: Any = Depends(get_redis),
):
    svc = _service(session, redis)
    job = await svc.get(user.id, job_id)
    return await svc.to_view(job)


@router.post("/video-jobs/{job_id}/cancel", response_model=VideoJobView)
async def cancel_video_job(
    job_id: str,
    user: User = Depends(get_current_user),
    _csrf: None = Depends(require_csrf),
    session: AsyncSession = Depends(db_session),
    redis: Any = Depends(get_redis),
):
    svc = _service(session, redis)
    job = await svc.cancel(user.id, job_id)
    return await svc.to_view(job)


@router.post("/video-jobs/{job_id}/download/retry", response_model=VideoJobView, status_code=202)
async def retry_video_job_download(
    job_id: str,
    user: User = Depends(get_current_user),
    _csrf: None = Depends(require_csrf),
    session: AsyncSession = Depends(db_session),
    redis: Any = Depends(get_redis),
):
    svc = _service(session, redis)
    job = await svc.retry_download(user.id, job_id)
    return await svc.to_view(job)


@router.get("/video-jobs/{job_id}/events", response_model=Page)
async def list_video_job_events(
    job_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(db_session),
    redis: Any = Depends(get_redis),
):
    svc = _service(session, redis)
    events = await svc.events(user.id, job_id)
    return Page(items=[svc.to_event_view(e) for e in events], next_cursor=None)
