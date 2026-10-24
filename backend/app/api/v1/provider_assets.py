"""视频厂商短时读取素材的签名入口（/api/v1/provider-assets/{token}）。

该接口由视频厂商调用，不使用用户 Cookie；签名错误/过期/任务不匹配返回 404。
支持 HEAD 与 Range（由 FileResponse 处理）。
"""

from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import db_session
from app.core.config import settings
from app.core.errors import ASSET_NOT_FOUND, AppError
from app.db.models.asset import Asset
from app.db.redis import get_redis
from app.services.provider_asset_url import ProviderAssetUrlService
from app.storage import LocalStorage

router = APIRouter()


@router.api_route("/provider-assets/{token}", methods=["GET", "HEAD"])
async def provider_asset(
    token: str,
    session: AsyncSession = Depends(db_session),
    redis: Any = Depends(get_redis),
):
    svc = ProviderAssetUrlService(session, redis, settings.app_secret)
    payload = await svc.verify_subject(token)
    if payload is None:
        raise AppError(ASSET_NOT_FOUND, "素材签名无效或已过期")

    row = (await session.exec(select(Asset).where(Asset.id == payload["aid"]))).first()
    if row is None:
        raise AppError(ASSET_NOT_FOUND)
    path = LocalStorage(settings.storage_root).open_read_path(row.storage_key)
    return FileResponse(path, media_type=row.mime_type, filename=row.original_name or None)
