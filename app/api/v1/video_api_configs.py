"""用户视频 API 配置路由（/api/v1/video-api-configs...）。

读接口需登录；写接口（POST/PATCH/DELETE）需登录 + CSRF。密钥永远只回掩码。
"""

from fastapi import APIRouter, Depends, Query, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import db_session, get_current_user, require_csrf
from app.db.models.user import User
from app.schemas.conversation import Page
from app.schemas.video_api_config import (
    TestVideoApiConfigRequest,
    TestVideoApiConfigResult,
    VideoApiConfigCreateRequest,
    VideoApiConfigPatchRequest,
    VideoApiConfigView,
)
from app.services.video_api_config_service import VideoApiConfigService

router = APIRouter()


@router.post("/video-api-configs/test", response_model=TestVideoApiConfigResult)
async def test_video_api_config(
    payload: TestVideoApiConfigRequest,
    user: User = Depends(get_current_user),
    _csrf: None = Depends(require_csrf),
    session: AsyncSession = Depends(db_session),
):
    """临时检测配置（不保存凭据、不创建收费视频）。"""
    return await VideoApiConfigService(session).test(payload)


@router.post("/video-api-configs", response_model=VideoApiConfigView, status_code=status.HTTP_201_CREATED)
async def create_video_api_config(
    payload: VideoApiConfigCreateRequest,
    user: User = Depends(get_current_user),
    _csrf: None = Depends(require_csrf),
    session: AsyncSession = Depends(db_session),
):
    return await VideoApiConfigService(session).create(user.id, payload)


@router.get("/video-api-configs", response_model=Page)
async def list_video_api_configs(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(db_session),
    limit: int = Query(default=20, ge=1, le=100),
    status: str | None = Query(default=None),
    protocol_code: str | None = Query(default=None, max_length=64),
):
    """配置列表。游标分页待后补，此处简化返回全部符合条件的项。"""
    rows = await VideoApiConfigService(session).list(user.id, protocol_code, status)
    return Page(items=rows, next_cursor=None)


@router.get("/video-api-configs/{config_id}", response_model=VideoApiConfigView)
async def get_video_api_config(
    config_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(db_session),
):
    return await VideoApiConfigService(session).get(user.id, config_id)


@router.patch("/video-api-configs/{config_id}", response_model=VideoApiConfigView)
async def patch_video_api_config(
    config_id: str,
    payload: VideoApiConfigPatchRequest,
    user: User = Depends(get_current_user),
    _csrf: None = Depends(require_csrf),
    session: AsyncSession = Depends(db_session),
):
    return await VideoApiConfigService(session).patch(user.id, config_id, payload)


@router.delete("/video-api-configs/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_video_api_config(
    config_id: str,
    user: User = Depends(get_current_user),
    _csrf: None = Depends(require_csrf),
    session: AsyncSession = Depends(db_session),
):
    await VideoApiConfigService(session).delete(user.id, config_id)
    return None


@router.post("/video-api-configs/{config_id}/test", response_model=TestVideoApiConfigResult)
async def retest_video_api_config(
    config_id: str,
    user: User = Depends(get_current_user),
    _csrf: None = Depends(require_csrf),
    session: AsyncSession = Depends(db_session),
):
    """解密当前 revision 重新检测，不创建收费视频。"""
    return await VideoApiConfigService(session).retest(user.id, config_id)
