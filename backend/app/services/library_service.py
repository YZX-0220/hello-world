"""用户资料库与存储配额服务。"""

from contextlib import suppress
from typing import Any

from sqlalchemy import func
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.db.models.asset import Asset
from app.db.redis import build_redis_client
from app.schemas.clip import StorageQuotaView
from app.storage import get_storage

_USER_QUOTA_KEY_PREFIX = "user_quota:"
_QUOTA_CACHE_TTL_SECONDS = 3600  # 1 hour


class LibraryService:
    def __init__(self, session: AsyncSession, redis: Any = None) -> None:
        self._session = session
        self._storage = get_storage()
        self._redis = redis

    async def _get_redis(self) -> Any:
        if self._redis is not None:
            return self._redis
        return build_redis_client()

    async def get_storage_used_bytes(self, user_id: str) -> tuple[int, int]:
        """获取用户当前已用存储字节数及资产数量。优先从 Redis 缓存读取。"""
        redis = await self._get_redis()
        cache_key = f"{_USER_QUOTA_KEY_PREFIX}{user_id}:used"
        with suppress(Exception):
            cached = await redis.get(cache_key)
            if cached is not None:
                parts = cached.split(":")
                used_bytes = int(parts[0])
                count = int(parts[1]) if len(parts) > 1 else 0
                return used_bytes, count

        # 未命中缓存，从数据库聚合有效资产（排除公共 TV 示例库占用的资产）
        from app.db.models.material_library import MaterialLibraryItem

        tv_videos_subquery = select(MaterialLibraryItem.video_asset_id).where(
            MaterialLibraryItem.status != "deleted"
        )
        tv_covers_subquery = select(MaterialLibraryItem.cover_asset_id).where(
            MaterialLibraryItem.status != "deleted",
            col(MaterialLibraryItem.cover_asset_id).is_not(None),
        )

        stmt = select(
            func.coalesce(func.sum(Asset.size_bytes), 0),
            func.count(col(Asset.id)),
        ).where(
            Asset.user_id == user_id,
            Asset.status != "deleted",
            col(Asset.deleted_at).is_(None),
            col(Asset.purpose).notin_(["material_library_video", "material_library_cover"]),
            col(Asset.id).notin_(tv_videos_subquery),
            col(Asset.id).notin_(tv_covers_subquery),
        )
        res = (await self._session.exec(stmt)).one()
        used_bytes, count = int(res[0]), int(res[1])

        # 写入 Redis 缓存
        with suppress(Exception):
            await redis.setex(cache_key, _QUOTA_CACHE_TTL_SECONDS, f"{used_bytes}:{count}")
        return used_bytes, count

    async def invalidate_quota_cache(self, user_id: str) -> None:
        """失效用户的配额缓存。"""
        with suppress(Exception):
            redis = await self._get_redis()
            cache_key = f"{_USER_QUOTA_KEY_PREFIX}{user_id}:used"
            await redis.delete(cache_key)

    async def get_storage_quota(self, user_id: str) -> StorageQuotaView:
        """获取用户完整的存储配额视图。"""
        quota_gb = settings.default_user_storage_quota_gb
        quota_bytes = int(quota_gb * 1024 * 1024 * 1024)
        used_bytes, count = await self.get_storage_used_bytes(user_id)

        available_bytes = max(0, quota_bytes - used_bytes)
        usage_percent = round((used_bytes / quota_bytes) * 100.0, 1) if quota_bytes > 0 else 100.0

        return StorageQuotaView(
            quota_bytes=quota_bytes,
            used_bytes=used_bytes,
            available_bytes=available_bytes,
            quota_gb=quota_gb,
            usage_percent=usage_percent,
            asset_count=count,
        )

    def resolve_asset_url(self, asset: Asset) -> str:
        """为资产生成适合前端/WebCodecs解码读取的直链或受控路径。"""
        if asset.storage_provider == "obs" and hasattr(
            self._storage, "generate_presigned_download_url"
        ):
            try:
                # 预签名直链，有效期使用系统配置
                generator: Any = self._storage.generate_presigned_download_url
                return generator(
                    asset.storage_key,
                    expires_in=settings.signed_url_ttl_seconds,
                    filename=asset.original_name or None,
                )
            except Exception:
                pass
        return f"/api/v1/assets/{asset.id}/content"
