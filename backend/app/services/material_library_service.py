"""统一示例库：已发布内容共享读取，新增文件只能引用管理者自己的素材。"""

from pathlib import Path
from typing import Literal, cast

from fastapi import UploadFile
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.core.cursor import encode_cursor
from app.core.errors import (
    ASSET_CONTENT_INVALID,
    ASSET_TOO_LARGE,
    LIBRARY_ASSET_INVALID,
    LIBRARY_ITEM_NOT_FOUND,
    LIBRARY_MEDIA_UNAVAILABLE,
    LIBRARY_VERSION_CONFLICT,
    AppError,
)
from app.core.time import now
from app.db.models.asset import Asset
from app.db.models.material_library import MaterialLibraryItem
from app.repositories.material_library import MaterialLibraryRepository
from app.schemas.asset import AssetView
from app.schemas.material_library import (
    CreateLibraryItem,
    LibraryFileView,
    LibraryItemView,
    LibraryPage,
    LibraryStatus,
    PatchLibraryItem,
)
from app.services.asset_service import AssetService, _detect_kind_mime
from app.storage import Storage, StorageError, get_storage


class MaterialLibraryService:
    def __init__(self, session: AsyncSession, storage: Storage | None = None) -> None:
        self._session = session
        self._repo = MaterialLibraryRepository(session)
        self._storage = storage or get_storage()

    async def upload(
        self, user_id: str, file: UploadFile, kind: Literal["video", "image"]
    ) -> AssetView:
        """分块读取并限制字节数，复用 assets 的落盘与哈希机制。"""
        limit = settings.video_max_bytes if kind == "video" else settings.image_max_bytes
        data = bytearray()
        while chunk := await file.read(min(1024 * 1024, max(1, limit + 1 - len(data)))):
            data.extend(chunk)
            if len(data) > limit:
                raise AppError(ASSET_TOO_LARGE)
        raw = bytes(data)
        detected_kind, _ = _detect_kind_mime(raw)
        if detected_kind != kind:
            raise AppError(ASSET_CONTENT_INVALID, "上传的视频或封面内容与类型不符")
        if kind == "video":
            # 暂只接收 MP4。魔数不能把 HEIC/AVIF 的 ISO 容器误认成视频。
            brands = {
                b"isom",
                b"iso2",
                b"iso3",
                b"iso4",
                b"iso5",
                b"iso6",
                b"mp41",
                b"mp42",
                b"avc1",
                b"dash",
                b"MSNV",
            }
            if (
                len(raw) < 24
                or raw[4:8] != b"ftyp"
                or raw[8:12] not in brands
                or Path(file.filename or "").suffix.lower() != ".mp4"
            ):
                raise AppError(ASSET_CONTENT_INVALID, "示例视频需要 MP4 文件")
        purpose = "source_video" if kind == "video" else "reference"
        return await AssetService(self._session).upload(
            user_id, raw, file.filename or "", purpose, None
        )

    async def _item(self, item_id: str, *, admin: bool) -> MaterialLibraryItem:
        item = await self._repo.get(item_id, admin=admin)
        if item is None:
            raise AppError(LIBRARY_ITEM_NOT_FOUND)
        return item

    async def _asset(self, asset_id: str, kind: str, *, owner_id: str | None = None) -> Asset:
        asset = await self._session.get(Asset, asset_id)
        if (
            asset is None
            or asset.kind != kind
            or asset.status != "ready"
            or (owner_id is not None and asset.user_id != owner_id)
        ):
            raise AppError(LIBRARY_ASSET_INVALID)
        if getattr(asset, "storage_provider", None) == "obs":
            if not self._storage.exists(asset.storage_key):
                raise AppError(LIBRARY_ASSET_INVALID, "示例文件尚未完整存储或已丢失")
        else:
            try:
                self._storage.open_read_path(asset.storage_key)
            except StorageError as exc:
                raise AppError(LIBRARY_ASSET_INVALID, "示例文件尚未完整存储或已丢失") from exc
        return asset

    async def create(self, user_id: str, request: CreateLibraryItem) -> LibraryItemView:
        await self._asset(request.video_asset_id, "video", owner_id=user_id)
        if request.cover_asset_id is not None:
            await self._asset(request.cover_asset_id, "image", owner_id=user_id)
        item = MaterialLibraryItem(**request.model_dump(), created_by=user_id)
        await self._repo.add(item)
        return (await self._views([item], admin=True))[0]

    async def patch(self, user_id: str, item_id: str, request: PatchLibraryItem) -> LibraryItemView:
        item = await self._item(item_id, admin=True)
        if item.version != request.expected_version:
            raise AppError(LIBRARY_VERSION_CONFLICT)
        changes = request.model_dump(exclude_unset=True, exclude={"expected_version"})
        video_id = changes.get("video_asset_id", item.video_asset_id)
        cover_id = changes.get("cover_asset_id", item.cover_asset_id)
        await self._asset(
            video_id, "video", owner_id=user_id if video_id != item.video_asset_id else None
        )
        if cover_id is not None:
            await self._asset(
                cover_id, "image", owner_id=user_id if cover_id != item.cover_asset_id else None
            )
        changes["updated_at"] = now()
        await self._repo.update(item, request.expected_version, changes)
        return (await self._views([item], admin=True))[0]

    async def delete(self, item_id: str, expected_version: int) -> None:
        item = await self._item(item_id, admin=True)
        await self._repo.update(
            item, expected_version, {"status": "deleted", "updated_at": now(), "deleted_at": now()}
        )

    async def get(self, item_id: str, *, admin: bool = False) -> LibraryItemView:
        return (await self._views([await self._item(item_id, admin=admin)], admin=admin))[0]

    async def list_items(
        self,
        *,
        admin: bool = False,
        status: str | None = None,
        q: str | None = None,
        model_name: str | None = None,
        limit: int = 20,
        cursor: str | None = None,
    ) -> LibraryPage:
        rows = await self._repo.list(
            admin=admin, status=status, q=q, model_name=model_name, limit=limit, cursor=cursor
        )
        page = rows[:limit]
        next_cursor = encode_cursor(page[-1].created_at, page[-1].id) if len(rows) > limit else None
        return LibraryPage(items=await self._views(page, admin=admin), next_cursor=next_cursor)

    async def _views(
        self, items: list[MaterialLibraryItem], *, admin: bool
    ) -> list[LibraryItemView]:
        ids = {
            asset_id
            for item in items
            for asset_id in (item.video_asset_id, item.cover_asset_id)
            if asset_id
        }
        if not ids:
            return []
        assets = {
            asset.id: asset
            for asset in (
                await self._session.exec(select(Asset).where(col(Asset.id).in_(ids)))
            ).all()
        }
        prefix = "/api/v1/admin/material-library" if admin else "/api/v1/material-library"

        def file_view(asset_id: str, role: str, item_id: str) -> LibraryFileView:
            asset = assets.get(asset_id)
            if asset is None or asset.status != "ready":
                raise AppError(LIBRARY_MEDIA_UNAVAILABLE)
            return LibraryFileView(
                asset_id=asset.id,
                mime_type=asset.mime_type,
                size_bytes=asset.size_bytes,
                width=asset.width,
                height=asset.height,
                duration_ms=asset.duration_ms,
                content_url=f"{settings.app_base_url.rstrip('/')}{prefix}/{item_id}/{role}",
            )

        result = []
        for item in items:
            result.append(
                LibraryItemView(
                    id=item.id,
                    title=item.title,
                    description=item.description,
                    model_name=item.model_name,
                    status=cast(LibraryStatus, item.status),
                    version=item.version,
                    video=file_view(item.video_asset_id, "video", item.id),
                    cover=file_view(item.cover_asset_id, "cover", item.id)
                    if item.cover_asset_id
                    else None,
                    created_at=item.created_at,
                    updated_at=item.updated_at,
                )
            )
        return result

    async def open_content(
        self, item_id: str, role: Literal["video", "cover"], *, admin: bool = False
    ) -> tuple[Asset, str]:
        item = await self._item(item_id, admin=admin)
        asset_id = item.video_asset_id if role == "video" else item.cover_asset_id
        if asset_id is None:
            raise AppError(LIBRARY_MEDIA_UNAVAILABLE)
        try:
            asset = await self._asset(asset_id, "video" if role == "video" else "image")
            return asset, asset.storage_key
        except (AppError, StorageError) as exc:
            raise AppError(LIBRARY_MEDIA_UNAVAILABLE) from exc
