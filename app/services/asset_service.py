"""素材服务：上传检测、列表、内容读取（权限）、删除。

对应《实施计划》4.9 与接口说明 7.x：
  - kind 由后端检测，不由前端可信指定；检测 MIME/扩展名组合，图片实际解码取宽高；
  - 校验用途、大小、像素上限；其它业务接口不接受本机路径，只用 storage_key；
  - 读取内容需登录+归属校验；产品级视频/音频的 ffprobe 时长检测在后补，demo 以图片为主。
"""

import io
from dataclasses import dataclass
from typing import Any

from PIL import Image, UnidentifiedImageError
from sqlmodel import select

from app.core.config import settings
from app.core.errors import (
    ASSET_CONTENT_INVALID,
    ASSET_IN_USE,
    ASSET_TOO_LARGE,
    ASSET_TYPE_UNSUPPORTED,
    AppError,
)
from app.core.ids import new_id
from app.core.time import now
from app.db.models.asset import Asset
from app.db.models.conversation import Conversation
from app.db.models.video_job import VideoJobAsset
from app.repositories.assets import AssetRepository
from app.schemas.asset import AssetView
from app.storage import LocalStorage, StorageError

# 可上传用途 -> 应检测到的 kind（用于限制与伪装检测）
_UPLOAD_KIND_BY_PURPOSE = {
    "first_frame": "image",
    "last_frame": "image",
    "reference": "image",
    "source_video": "video",
    "audio": "audio",
}

_MAX_BYTES_BY_KIND = {
    "image": settings.image_max_bytes,
    "video": settings.video_max_bytes,
    "audio": settings.audio_max_bytes,
}


@dataclass(frozen=True)
class InspectedFile:
    kind: str
    mime: str
    width: int | None
    height: int | None
    duration_ms: int | None
    ext: str


def _detect_kind_mime(data: bytes) -> tuple[str, str | None]:
    """用文件魔数粗判类型：image/video/audio；返回 (kind, mime) 或 (None, None)。"""
    if data.startswith(b"\xff\xd8\xff"):
        return "image", "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image", "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image", "image/webp"
    if data[:4] == b"GIF8":
        return "image", "image/gif"
    if data[4:8] == b"ftyp":  # MP4 / QuickTime 常见
        return "video", "video/mp4"
    if data[4:8] == b"moov" or data[4:8] == b"mdat":
        return "video", "video/mp4"
    return "unknown", None


def _inspect(data: bytes, suggested_kind: str) -> InspectedFile:
    detected_kind, mime = _detect_kind_mime(data)
    if detected_kind == "unknown":
        raise AppError(ASSET_CONTENT_INVALID, "无法识别文件类型或文件已损坏")

    if detected_kind != suggested_kind and not (suggested_kind == "video" and detected_kind == "image"):
        # 用途声明为图片却传了视频等，属伪装；source_video 也拒绝图片
        raise AppError(ASSET_CONTENT_INVALID, "文件内容与用途不一致")

    if suggested_kind == "image":
        try:
            with Image.open(io.BytesIO(data)) as im:
                im.verify()
            with Image.open(io.BytesIO(data)) as im:
                width, height = im.size
        except UnidentifiedImageError as exc:
            raise AppError(ASSET_CONTENT_INVALID, "图片无法解码") from exc
        if width * height > settings.image_max_pixels:
            raise AppError(ASSET_CONTENT_INVALID, "图片分辨率超过上限")
        return InspectedFile(kind="image", mime=mime or "image/jpeg", width=width, height=height, duration_ms=None, ext="img")
    if data.startswith(b"\xff\xd8\xff"):
        ext = "jpg"
    else:
        ext = "mp4" if suggested_kind == "video" else "audio"
    return InspectedFile(kind=detected_kind, mime=mime or "application/octet-stream", width=None, height=None, duration_ms=None, ext=ext)


def _content_url(asset_id: str) -> str:
    """本站受控读取地址（不是厂商签名地址）。"""
    return f"{settings.app_base_url}/api/v1/assets/{asset_id}/content"


class AssetService:
    def __init__(self, session: Any, storage: LocalStorage | None = None) -> None:
        self._session = session
        self._repo = AssetRepository(session)
        self._storage = storage or LocalStorage(settings.storage_root)

    async def upload(
        self,
        user_id: str,
        data: bytes,
        original_name: str,
        purpose: str,
        conversation_id: str | None,
    ) -> AssetView:
        suggested = _UPLOAD_KIND_BY_PURPOSE.get(purpose)
        if suggested is None:
            raise AppError(ASSET_TYPE_UNSUPPORTED, "素材用途不受支持")
        max_bytes = _MAX_BYTES_BY_KIND[suggested]
        if len(data) > max_bytes:
            raise AppError(ASSET_TOO_LARGE)

        inspected = _inspect(data, suggested)
        asset_id = new_id()
        if conversation_id is not None:
            conv = await self._session.exec(
                select(Conversation).where(Conversation.id == conversation_id, Conversation.user_id == user_id)
            )
            if conv.first() is None:
                raise AppError(ASSET_CONTENT_INVALID, "所属对话不存在或无权访问")
        storage_key = f"{user_id}/{asset_id}.{inspected.ext}"
        try:
            stored = self._storage.write_stream(data, storage_key, final_key=storage_key)
        except StorageError as exc:
            raise AppError(ASSET_CONTENT_INVALID, str(exc)) from exc

        asset = Asset(
            id=asset_id,
            user_id=user_id,
            conversation_id=conversation_id,
            kind=inspected.kind,
            purpose=purpose,
            original_name=original_name[:500],
            storage_key=storage_key,
            mime_type=inspected.mime,
            size_bytes=stored.size_bytes,
            sha256=stored.sha256,
            width=inspected.width,
            height=inspected.height,
            duration_ms=inspected.duration_ms,
            status="ready",
            retention_until=None,
        )
        row = await self._repo.add(asset)
        return self._to_view(row)

    async def list(self, user_id: str, conversation_id: str | None, kind: str | None, purpose: str | None) -> list[AssetView]:
        rows = await self._repo.list_for_user(user_id, conversation_id, kind, purpose)
        return [self._to_view(r) for r in rows]

    async def get(self, user_id: str, asset_id: str) -> AssetView:
        asset = await self._repo.get_for_user(asset_id, user_id)
        if asset is None:
            raise AppError(ASSET_CONTENT_INVALID, "素材不存在或无权访问")
        return self._to_view(asset)

    async def open_content(self, user_id: str, asset_id: str) -> tuple[Asset, str]:
        asset = await self._repo.get_for_user(asset_id, user_id)
        if asset is None:
            raise AppError(ASSET_CONTENT_INVALID, "素材不存在或无权访问")
        return asset, asset.storage_key

    async def delete(self, user_id: str, asset_id: str) -> None:
        asset = await self._repo.get_for_user(asset_id, user_id)
        if asset is None:
            raise AppError(ASSET_CONTENT_INVALID, "素材不存在或无权访问")
        # 已被任务的素材引用则拒绝删除（保证 running 任务的输入可用）
        used = await self._session.exec(
            select(VideoJobAsset).where(VideoJobAsset.asset_id == asset_id)
        )
        if used.first() is not None:
            raise AppError(ASSET_IN_USE)
        asset.status = "deleted"
        asset.deleted_at = now()
        await self._session.commit()

    def _to_view(self, asset: Asset) -> AssetView:
        return AssetView(
            id=asset.id,
            conversation_id=asset.conversation_id,
            kind=asset.kind,
            purpose=asset.purpose,
            original_name=asset.original_name,
            mime_type=asset.mime_type,
            size_bytes=asset.size_bytes,
            width=asset.width,
            height=asset.height,
            duration_ms=asset.duration_ms,
            status=asset.status,
            content_url=_content_url(asset.id) if asset.status == "ready" else None,
            created_at=asset.created_at,
        )
