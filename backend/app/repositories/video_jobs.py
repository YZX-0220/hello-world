"""视频任务三张表仓储。"""

from sqlalchemy import and_, or_
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.cursor import decode_cursor_pair, parse_ts
from app.db.models.video_job import VideoJob, VideoJobAsset, VideoJobEvent


class VideoJobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_for_user(self, job_id: str, user_id: str) -> VideoJob | None:
        stmt = select(VideoJob).where(VideoJob.id == job_id, VideoJob.user_id == user_id)
        result = await self._session.exec(stmt)
        return result.first()

    async def get_by_idempotency(self, user_id: str, idempotency_key: str) -> VideoJob | None:
        stmt = select(VideoJob).where(VideoJob.user_id == user_id, VideoJob.idempotency_key == idempotency_key)
        result = await self._session.exec(stmt)
        return result.first()

    async def list_for_user(
        self,
        user_id: str,
        conversation_id: str | None = None,
        status: str | None = None,
        download_status: str | None = None,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> list[VideoJob]:
        """按 (created_at desc, id desc) 游标分页；返回不超过 limit+1 条。"""
        stmt = select(VideoJob).where(VideoJob.user_id == user_id)
        if conversation_id is not None:
            stmt = stmt.where(VideoJob.conversation_id == conversation_id)
        if status is not None:
            stmt = stmt.where(VideoJob.status == status)
        if download_status is not None:
            stmt = stmt.where(VideoJob.download_status == download_status)
        if cursor is not None:
            t, cid = decode_cursor_pair(cursor)
            ts = parse_ts(t)
            stmt = stmt.where(
                or_(
                    VideoJob.created_at < ts,  # type: ignore[arg-type]
                    and_(VideoJob.created_at == ts, VideoJob.id < cid),  # type: ignore[arg-type]
                )
            )
        stmt = stmt.order_by(VideoJob.created_at.desc(), VideoJob.id.desc())  # type: ignore[attr-defined]
        if limit is not None:
            stmt = stmt.limit(limit + 1)
        result = await self._session.exec(stmt)
        return list(result.all())

    async def add(self, row: VideoJob) -> VideoJob:
        self._session.add(row)
        await self._session.flush()
        return row

    async def save(self, row: VideoJob) -> VideoJob:
        await self._session.commit()
        await self._session.refresh(row)
        return row


class VideoJobEventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_job(self, job_id: str) -> list[VideoJobEvent]:
        stmt = (
            select(VideoJobEvent)
            .where(VideoJobEvent.video_job_id == job_id)
            .order_by(VideoJobEvent.created_at.asc())  # type: ignore[attr-defined]
        )
        result = await self._session.exec(stmt)
        return list(result.all())

    async def add(self, row: VideoJobEvent) -> VideoJobEvent:
        self._session.add(row)
        await self._session.flush()
        return row


class VideoJobAssetRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_job(self, job_id: str) -> list[VideoJobAsset]:
        stmt = select(VideoJobAsset).where(VideoJobAsset.video_job_id == job_id)
        result = await self._session.exec(stmt)
        return list(result.all())

    async def any_for_asset(self, asset_id: str) -> bool:
        stmt = select(VideoJobAsset.id).where(VideoJobAsset.asset_id == asset_id).limit(1)
        result = await self._session.exec(stmt)
        return result.first() is not None

    async def add(self, row: VideoJobAsset) -> VideoJobAsset:
        self._session.add(row)
        await self._session.flush()
        return row
