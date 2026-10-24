"""素材路由（/api/v1/assets...，需登录；写接口需 CSRF）。

内容读取支持 Range/HEAD（由 FileResponse 处理），只返回本站文件流。
"""

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import FileResponse
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import db_session, get_current_user, require_csrf
from app.core.config import settings
from app.db.models.user import User
from app.schemas.asset import AssetView
from app.schemas.conversation import Page
from app.services.asset_service import AssetService
from app.storage import LocalStorage

router = APIRouter()


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
    views, next_cursor = await AssetService(session).list(user.id, conversation_id, kind, purpose, status, limit, cursor)
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
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(db_session),
):
    asset, storage_key = await AssetService(session).open_content(user.id, asset_id)
    path = LocalStorage(settings.storage_root).open_read_path(storage_key)
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
