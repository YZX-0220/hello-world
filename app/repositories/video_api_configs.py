"""用户视频 API 配置与修订版本仓储。

config 表只存「配置身份」，实际协议/地址/凭据/能力在 revision 表；
视频任务固定引用创建时的 revision，用户后续修改不破坏旧任务。
"""

from sqlalchemy import and_, or_
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.cursor import decode_cursor_pair, parse_ts
from app.db.models.video_api_config import VideoApiConfig, VideoApiConfigRevision


class VideoApiConfigRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_for_user(self, config_id: str, user_id: str) -> VideoApiConfig | None:
        stmt = select(VideoApiConfig).where(
            VideoApiConfig.id == config_id,
            VideoApiConfig.user_id == user_id,
        )
        result = await self._session.exec(stmt)
        return result.first()

    async def list_for_user(
        self,
        user_id: str,
        status: str | None = None,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> list[VideoApiConfig]:
        """按 (created_at desc, id desc) 游标分页，返回不超过 limit 条。

        注意这里用 limit 而非 limit+1：Service 层会先拉取这批配置、再按最新 revision
        的 protocol_code 过滤，所以"是否还有下一页"由 Service 层的 pagination 循环判定。
        protocol_code 过滤由 Service 层按最新 revision 处理。
        """
        stmt = select(VideoApiConfig).where(
            VideoApiConfig.user_id == user_id,
            VideoApiConfig.status != "deleted",
        )
        if status is not None and status != "deleted":
            stmt = stmt.where(VideoApiConfig.status == status)
        if cursor is not None:
            t, cid = decode_cursor_pair(cursor)
            ts = parse_ts(t)
            stmt = stmt.where(
                or_(
                    VideoApiConfig.created_at < ts,  # type: ignore[arg-type]
                    and_(VideoApiConfig.created_at == ts, VideoApiConfig.id < cid),  # type: ignore[arg-type]
                )
            )
        stmt = stmt.order_by(VideoApiConfig.created_at.desc(), VideoApiConfig.id.desc())  # type: ignore[attr-defined]
        if limit is not None:
            stmt = stmt.limit(limit)
        result = await self._session.exec(stmt)
        return list(result.all())

    async def get_by_display_name(self, user_id: str, display_name: str) -> VideoApiConfig | None:
        stmt = select(VideoApiConfig).where(
            VideoApiConfig.user_id == user_id,
            VideoApiConfig.display_name == display_name,
            VideoApiConfig.status != "deleted",
        )
        result = await self._session.exec(stmt)
        return result.first()

    async def add(self, row: VideoApiConfig) -> VideoApiConfig:
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return row

    async def save(self, row: VideoApiConfig) -> VideoApiConfig:
        await self._session.commit()
        await self._session.refresh(row)
        return row


class VideoApiConfigRevisionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, config_id: str, revision: int) -> VideoApiConfigRevision | None:
        stmt = select(VideoApiConfigRevision).where(
            VideoApiConfigRevision.config_id == config_id,
            VideoApiConfigRevision.revision == revision,
        )
        result = await self._session.exec(stmt)
        return result.first()

    async def get_latest(self, config_id: str) -> VideoApiConfigRevision | None:
        stmt = (
            select(VideoApiConfigRevision)
            .where(VideoApiConfigRevision.config_id == config_id)
            .order_by(VideoApiConfigRevision.revision.desc())  # type: ignore[attr-defined]
            .limit(1)
        )
        result = await self._session.exec(stmt)
        return result.first()

    async def max_revision(self, config_id: str) -> int:
        stmt = (
            select(VideoApiConfigRevision.revision)
            .where(VideoApiConfigRevision.config_id == config_id)
            .order_by(VideoApiConfigRevision.revision.desc())  # type: ignore[attr-defined]
            .limit(1)
        )
        result = await self._session.exec(stmt)
        row = result.first()
        return int(row) if row is not None else 0

    async def add(self, row: VideoApiConfigRevision) -> VideoApiConfigRevision:
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return row
