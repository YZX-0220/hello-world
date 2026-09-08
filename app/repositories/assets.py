"""素材仓储。"""

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.db.models.asset import Asset


class AssetRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_for_user(self, asset_id: str, user_id: str) -> Asset | None:
        stmt = select(Asset).where(Asset.id == asset_id, Asset.user_id == user_id, Asset.status != "deleted")
        result = await self._session.exec(stmt)
        return result.first()

    async def get(self, asset_id: str) -> Asset | None:
        stmt = select(Asset).where(Asset.id == asset_id)
        result = await self._session.exec(stmt)
        return result.first()

    async def list_for_user(
        self,
        user_id: str,
        conversation_id: str | None = None,
        kind: str | None = None,
        purpose: str | None = None,
        status: str | None = None,
    ) -> list[Asset]:
        stmt = select(Asset).where(Asset.user_id == user_id, Asset.status != "deleted")
        if conversation_id is not None:
            stmt = stmt.where(Asset.conversation_id == conversation_id)
        if kind is not None:
            stmt = stmt.where(Asset.kind == kind)
        if purpose is not None:
            stmt = stmt.where(Asset.purpose == purpose)
        if status is not None and status != "deleted":
            stmt = stmt.where(Asset.status == status)
        result = await self._session.exec(stmt)
        return list(result.all())

    async def add(self, row: Asset) -> Asset:
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return row

    async def save(self, row: Asset) -> Asset:
        await self._session.commit()
        await self._session.refresh(row)
        return row
