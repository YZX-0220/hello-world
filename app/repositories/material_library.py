"""素材库查询与原子版本更新。列表始终按创建时间和 ID 稳定排序。"""

from typing import Any

from sqlalchemy import and_, or_, update
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.cursor import decode_cursor_pair, parse_ts
from app.core.errors import LIBRARY_QUERY_INVALID, LIBRARY_VERSION_CONFLICT, AppError
from app.db.models.material_library import MaterialLibraryItem


class MaterialLibraryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, item_id: str, *, admin: bool = False) -> MaterialLibraryItem | None:
        stmt = select(MaterialLibraryItem).where(MaterialLibraryItem.id == item_id)
        stmt = stmt.where(
            MaterialLibraryItem.status != "deleted"
            if admin
            else MaterialLibraryItem.status == "published"
        )
        return (await self._session.exec(stmt)).first()

    async def list(
        self,
        *,
        admin: bool,
        status: str | None,
        q: str | None,
        model_name: str | None,
        limit: int,
        cursor: str | None,
    ) -> list[MaterialLibraryItem]:
        m = MaterialLibraryItem
        stmt = select(m).where(m.status != "deleted" if admin else m.status == "published")
        if admin and status is not None:
            stmt = stmt.where(m.status == status)
        if q and q.strip():
            # contains(autoescape=True) 将 % 和 _ 作为文字而非通配符。
            stmt = stmt.where(
                or_(
                    col(m.title).contains(q.strip(), autoescape=True),
                    col(m.description).contains(q.strip(), autoescape=True),
                )
            )
        if model_name is not None:
            stmt = stmt.where(m.model_name == model_name.strip())
        if cursor is not None:
            try:
                time_value, last_id = decode_cursor_pair(cursor)
                timestamp = parse_ts(time_value)
                if timestamp.tzinfo is not None or not last_id or len(last_id) > 64:
                    raise ValueError("无效的游标")
            except (ValueError, OverflowError) as exc:
                raise AppError(LIBRARY_QUERY_INVALID) from exc
            stmt = stmt.where(
                or_(
                    col(m.created_at) < timestamp,
                    and_(col(m.created_at) == timestamp, col(m.id) < last_id),
                )
            )
        stmt = stmt.order_by(col(m.created_at).desc(), col(m.id).desc()).limit(limit + 1)
        return list((await self._session.exec(stmt)).all())

    async def add(self, item: MaterialLibraryItem) -> MaterialLibraryItem:
        self._session.add(item)
        await self._session.commit()
        await self._session.refresh(item)
        return item

    async def update(
        self, item: MaterialLibraryItem, expected_version: int, values: dict[str, Any]
    ) -> MaterialLibraryItem:
        stmt = (
            update(MaterialLibraryItem)
            .where(
                col(MaterialLibraryItem.id) == item.id,
                col(MaterialLibraryItem.version) == expected_version,
                col(MaterialLibraryItem.status) != "deleted",
            )
            .values(**values, version=expected_version + 1)
            .execution_options(synchronize_session=False)
        )
        result = await self._session.execute(stmt)
        if result.rowcount != 1:  # type: ignore[attr-defined]
            await self._session.rollback()
            raise AppError(LIBRARY_VERSION_CONFLICT)
        await self._session.commit()
        await self._session.refresh(item)
        return item
