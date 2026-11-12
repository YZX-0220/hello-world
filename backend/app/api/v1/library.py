"""用户资料库与存储配额路由 (/api/v1/library)。"""

from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import db_session, get_current_user
from app.db.models.asset import Asset
from app.db.models.material_library import MaterialLibraryItem
from app.db.models.user import User
from app.schemas.clip import LibraryAssetView, StorageQuotaView
from app.services.library_service import LibraryService

router = APIRouter(prefix="/library", tags=["library"])


@router.get("/quota", response_model=StorageQuotaView)
async def get_storage_quota(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(db_session),
) -> StorageQuotaView:
    svc = LibraryService(session)
    return await svc.get_storage_quota(user.id)


@router.get("/assets")
async def list_library_assets(
    kind: Literal["video", "image", "audio"] | None = Query(default=None),
    purpose: Literal["all", "source_video", "ai_generated", "clip_export"] | None = Query(
        default=None
    ),
    q: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = Query(default=None),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(db_session),
) -> dict:
    svc = LibraryService(session)

    # 无论查询什么 purpose，公共示例库中引用的素材都不应作为个人剪辑素材出现
    tv_videos_subquery = select(MaterialLibraryItem.video_asset_id).where(
        MaterialLibraryItem.status != "deleted"
    )
    tv_covers_subquery = select(MaterialLibraryItem.cover_asset_id).where(
        MaterialLibraryItem.status != "deleted",
        col(MaterialLibraryItem.cover_asset_id).is_not(None),
    )

    stmt = select(Asset).where(
        Asset.user_id == user.id,
        Asset.status == "ready",
        col(Asset.deleted_at).is_(None),
        col(Asset.purpose).notin_(["material_library_video", "material_library_cover"]),
        col(Asset.id).notin_(tv_videos_subquery),
        col(Asset.id).notin_(tv_covers_subquery),
    )

    if kind:
        stmt = stmt.where(Asset.kind == kind)

    if purpose and purpose != "all":
        if purpose == "ai_generated":
            # AI 任务生成回流素材（包含 result 等目的）
            stmt = stmt.where(col(Asset.purpose).in_(["result", "ai_generated"]))
        else:
            stmt = stmt.where(Asset.purpose == purpose)

    if q:
        stmt = stmt.where(col(Asset.original_name).contains(q))

    stmt = stmt.order_by(col(Asset.created_at).desc()).limit(limit)

    assets = (await session.exec(stmt)).all()

    items = []
    for a in assets:
        url = svc.resolve_asset_url(a)
        items.append(
            LibraryAssetView(
                id=a.id,
                file_name=a.original_name or f"{a.kind}_{a.id}",
                size_bytes=a.size_bytes,
                mime_type=a.mime_type,
                kind=a.kind,  # type: ignore
                purpose=a.purpose,
                sha256=a.sha256,
                duration_ms=a.duration_ms,
                width=a.width,
                height=a.height,
                url=url,
                created_at=a.created_at,
            )
        )

    return {"items": items, "next_cursor": None}
