"""平台素材库：用户阅读已发布示例，管理员维护并预览草稿。"""

from typing import Literal

from fastapi import APIRouter, Depends, File, Form, Header, Query, Request, Response, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import db_session, get_material_library_admin, require_csrf
from app.core.errors import ErrorResponse
from app.db.models.asset import Asset
from app.db.models.user import User
from app.schemas.asset import AssetView
from app.schemas.material_library import (
    CreateLibraryItem,
    LibraryItemView,
    LibraryPage,
    LibraryStatus,
    PatchLibraryItem,
)
from app.services.material_library_service import MaterialLibraryService
from app.storage import ObsStorage, get_storage


def _serve_asset_response(
    asset: Asset, storage_key: str, *, image_process: str | None = None
) -> Response:
    storage = get_storage()
    if isinstance(storage, ObsStorage) and asset.storage_provider == "obs":
        # 仅对图片格式且指定缩略图规则时生效
        process_rule = image_process if (asset.kind == "image" and image_process) else None
        direct_url = storage.generate_presigned_download_url(
            storage_key, filename=asset.original_name, image_process=process_rule
        )
        return RedirectResponse(
            url=direct_url,
            status_code=302,
            headers={"Cache-Control": "private, max-age=600"},
        )

    path = storage.open_read_path(storage_key)
    return FileResponse(
        path,
        media_type=asset.mime_type,
        filename=asset.original_name or None,
        content_disposition_type="inline",
        headers={"Cache-Control": "private, no-store"},
    )


async def _library_csrf(
    request: Request,
    _token: str | None = Header(
        default=None,
        alias="X-CSRF-Token",
        description="写请求必需，填当前 hw_csrf Cookie 的值；GET/HEAD 不需要",
    ),
) -> None:
    # Header 参数用于 OpenAPI 描述；实际会话绑定和 Origin 检查复用共享依赖。
    await require_csrf(request)


router = APIRouter(
    tags=["素材库"], responses={status: {"model": ErrorResponse} for status in (401, 404, 422)}
)
admin_router = APIRouter(
    prefix="/admin",
    tags=["素材库管理"],
    dependencies=[Depends(get_material_library_admin), Depends(_library_csrf)],
    responses={status: {"model": ErrorResponse} for status in (401, 403, 404, 409, 413, 415, 422)},
)


@router.get("/material-library", response_model=LibraryPage)
async def list_library(
    session: AsyncSession = Depends(db_session),
    q: str | None = Query(default=None, max_length=200),
    model_name: str | None = Query(default=None, min_length=1, max_length=200),
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = Query(default=None, max_length=1000),
):
    return await MaterialLibraryService(session).list_items(
        q=q, model_name=model_name, limit=limit, cursor=cursor
    )


@router.get("/material-library/{item_id}", response_model=LibraryItemView)
async def get_library_item(
    item_id: str,
    session: AsyncSession = Depends(db_session),
):
    return await MaterialLibraryService(session).get(item_id)


@router.get("/material-library/{item_id}/{role}")
@router.head("/material-library/{item_id}/{role}")
async def read_library_media(
    item_id: str,
    role: Literal["video", "cover"],
    thumbnail: Literal["small", "medium", "raw"] = Query(
        default="small",
        description="封面缩略图规格（仅对 cover 有效）：small(320px WebP)、medium(800px WebP)、raw(原图)",
    ),
    session: AsyncSession = Depends(db_session),
):
    asset, storage_key = await MaterialLibraryService(session).open_content(item_id, role)
    process_rule = thumbnail if (role == "cover" and thumbnail in ("small", "medium")) else None
    return _serve_asset_response(asset, storage_key, image_process=process_rule)


@admin_router.post("/material-library/uploads", response_model=AssetView, status_code=201)
async def upload_library_file(
    file: UploadFile = File(...),
    kind: Literal["video", "image"] = Form(...),
    user: User = Depends(get_material_library_admin),
    session: AsyncSession = Depends(db_session),
):
    return await MaterialLibraryService(session).upload(user.id, file, kind)


@admin_router.post("/material-library", response_model=LibraryItemView, status_code=201)
async def create_library_item(
    request: CreateLibraryItem,
    user: User = Depends(get_material_library_admin),
    session: AsyncSession = Depends(db_session),
):
    return await MaterialLibraryService(session).create(user.id, request)


@admin_router.get("/material-library", response_model=LibraryPage)
async def list_admin_library(
    session: AsyncSession = Depends(db_session),
    status: LibraryStatus | None = Query(default=None),
    q: str | None = Query(default=None, max_length=200),
    model_name: str | None = Query(default=None, min_length=1, max_length=200),
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = Query(default=None, max_length=1000),
):
    return await MaterialLibraryService(session).list_items(
        admin=True, status=status, q=q, model_name=model_name, limit=limit, cursor=cursor
    )


@admin_router.get("/material-library/{item_id}", response_model=LibraryItemView)
async def get_admin_library_item(item_id: str, session: AsyncSession = Depends(db_session)):
    return await MaterialLibraryService(session).get(item_id, admin=True)


@admin_router.patch("/material-library/{item_id}", response_model=LibraryItemView)
async def patch_library_item(
    item_id: str,
    request: PatchLibraryItem,
    user: User = Depends(get_material_library_admin),
    session: AsyncSession = Depends(db_session),
):
    return await MaterialLibraryService(session).patch(user.id, item_id, request)


@admin_router.delete("/material-library/{item_id}", status_code=204)
async def delete_library_item(
    item_id: str, expected_version: int = Query(ge=1), session: AsyncSession = Depends(db_session)
):
    await MaterialLibraryService(session).delete(item_id, expected_version)


@admin_router.get("/material-library/{item_id}/{role}")
@admin_router.head("/material-library/{item_id}/{role}")
async def read_admin_library_media(
    item_id: str,
    role: Literal["video", "cover"],
    thumbnail: Literal["small", "medium", "raw"] = Query(
        default="small",
        description="封面缩略图规格（仅对 cover 有效）：small(320px WebP)、medium(800px WebP)、raw(原图)",
    ),
    session: AsyncSession = Depends(db_session),
):
    asset, storage_key = await MaterialLibraryService(session).open_content(
        item_id, role, admin=True
    )
    process_rule = thumbnail if (role == "cover" and thumbnail in ("small", "medium")) else None
    return _serve_asset_response(asset, storage_key, image_process=process_rule)
