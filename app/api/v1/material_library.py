"""平台素材库：用户阅读已发布示例，管理员维护并预览草稿。"""

from typing import Literal

from fastapi import APIRouter, Depends, File, Form, Header, Query, Request, UploadFile
from fastapi.responses import FileResponse
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import db_session, get_current_user, get_material_library_admin, require_csrf
from app.core.errors import ErrorResponse
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
    user: User = Depends(get_current_user),
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
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(db_session),
):
    return await MaterialLibraryService(session).get(item_id)


def _file_response(asset, path) -> FileResponse:
    return FileResponse(
        path,
        media_type=asset.mime_type,
        filename=asset.original_name or None,
        content_disposition_type="inline",
        headers={"Cache-Control": "private, no-store"},
    )


@router.get("/material-library/{item_id}/{role}", response_class=FileResponse)
@router.head("/material-library/{item_id}/{role}", response_class=FileResponse)
async def read_library_media(
    item_id: str,
    role: Literal["video", "cover"],
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(db_session),
):
    asset, path = await MaterialLibraryService(session).open_content(item_id, role)
    return _file_response(asset, path)


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


@admin_router.get("/material-library/{item_id}/{role}", response_class=FileResponse)
@admin_router.head("/material-library/{item_id}/{role}", response_class=FileResponse)
async def read_admin_library_media(
    item_id: str, role: Literal["video", "cover"], session: AsyncSession = Depends(db_session)
):
    asset, path = await MaterialLibraryService(session).open_content(item_id, role, admin=True)
    return _file_response(asset, path)
