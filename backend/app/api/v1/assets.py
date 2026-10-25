"""素材路由（/api/v1/assets...，需登录；写接口需 CSRF）。

内容读取支持 Range/HEAD（由 FileResponse 处理），只返回本站文件流。
"""

from typing import Literal

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import db_session, get_current_user, require_csrf
from app.db.models.user import User
from app.schemas.asset import (
    AssetUploadCompleteRequest,
    AssetUploadIntentRequest,
    AssetUploadIntentResponse,
    AssetView,
)
from app.schemas.conversation import Page
from app.services.asset_service import AssetService
from app.storage import ObsStorage, get_storage

router = APIRouter()


# ============ 新增 OBS 两阶段直传接口 ============


@router.post("/assets/upload-intent", response_model=AssetUploadIntentResponse, status_code=200)
async def create_upload_intent(
    req: AssetUploadIntentRequest,
    user: User = Depends(get_current_user),
    _csrf: None = Depends(require_csrf),
    session: AsyncSession = Depends(db_session),
):
    """阶段一：获取 OBS 预签名直传凭证（支持 Hash 秒传判重）。"""
    svc = AssetService(session)
    return await svc.create_upload_intent(user.id, req)


@router.post("/assets/{asset_id}/complete", response_model=AssetView, status_code=200)
async def complete_upload(
    asset_id: str,
    req: AssetUploadCompleteRequest,
    user: User = Depends(get_current_user),
    _csrf: None = Depends(require_csrf),
    session: AsyncSession = Depends(db_session),
):
    """阶段二：前端通知直传完成，后端核验 OBS ETag/大小并激活素材。"""
    svc = AssetService(session)
    return await svc.complete_upload(user.id, asset_id, req)


@router.get("/assets/{asset_id}/direct-url")
async def get_asset_direct_url(
    asset_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(db_session),
):
    """获取素材在 OBS 的预签名直接访问/拉流 URL（绕过 3M 业务服务器）。"""
    svc = AssetService(session)
    url = await svc.get_direct_url(user.id, asset_id)
    return {"direct_url": url}


# ============ 存量接口平滑过渡（保留接口，底层透明入桶与直链重定向） ============


@router.post("/assets", response_model=AssetView, status_code=201)
async def upload_asset(
    file: UploadFile = File(...),
    purpose: str = Form(..., min_length=1, max_length=30),
    conversation_id: str | None = Form(default=None),
    user: User = Depends(get_current_user),
    _csrf: None = Depends(require_csrf),
    session: AsyncSession = Depends(db_session),
):
    data = await file.read()
    svc = AssetService(session)
    return await svc.upload(user.id, data, file.filename or "", purpose, conversation_id)


@router.get("/assets", response_model=Page)
async def list_assets(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(db_session),
    limit: int = Query(default=20, ge=1, le=100),
    conversation_id: str | None = Query(default=None),
    kind: str | None = Query(default=None, max_length=20),
    purpose: str | None = Query(default=None, max_length=30),
    status: str | None = Query(default=None, max_length=20),
    cursor: str | None = Query(default=None),
):
    views, next_cursor = await AssetService(session).list(
        user.id, conversation_id, kind, purpose, status, limit, cursor
    )
    return Page(items=views, next_cursor=next_cursor)


@router.get("/assets/{asset_id}", response_model=AssetView)
async def get_asset(
    asset_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(db_session),
):
    return await AssetService(session).get(user.id, asset_id)


@router.api_route("/assets/{asset_id}/content", methods=["GET", "HEAD"])
async def read_asset_content(
    asset_id: str,
    thumbnail: Literal["small", "medium", "raw"] = Query(
        default="small", description="缩略图规格：small(320px WebP，默认)、medium(800px WebP)、raw(原图)"
    ),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(db_session),
):
    """读取素材：若为 OBS 存储直接 302 重定向到预签名直链，完全不耗服务器下行带宽。"""
    asset, storage_key = await AssetService(session).open_content(user.id, asset_id)
    storage = get_storage()
    if isinstance(storage, ObsStorage):
        # 仅对图片格式且指定缩略图规则时生效（非图片格式自动忽略该参数走原流）
        process_rule = (
            thumbnail if (asset.kind == "image" and thumbnail in ("small", "medium")) else None
        )
        direct_url = storage.generate_presigned_download_url(
            storage_key, filename=asset.original_name, image_process=process_rule
        )
        return RedirectResponse(
            url=direct_url,
            status_code=302,
            headers={"Cache-Control": "private, max-age=600"},
        )

    path = storage.open_read_path(storage_key)
    return FileResponse(path, media_type=asset.mime_type, filename=asset.original_name or None)


@router.delete("/assets/{asset_id}", status_code=204)
async def delete_asset(
    asset_id: str,
    user: User = Depends(get_current_user),
    _csrf: None = Depends(require_csrf),
    session: AsyncSession = Depends(db_session),
):
    await AssetService(session).delete(user.id, asset_id)
    return None
