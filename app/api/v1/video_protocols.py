"""视频协议只读路由（/api/v1/video-api-presets 等，需登录）。

对应接口说明 6.1/6.2/6.3：已启用协议、审核模板、模型能力。未实现/未核验协议不返回。
"""

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_current_user
from app.db.models.user import User
from app.services.video_registry_service import (
    list_enabled_preset_views,
    list_profile_views,
    list_template_views,
)

router = APIRouter()


@router.get("/video-api-presets")
async def list_video_api_presets(user: User = Depends(get_current_user)):
    """返回已启用协议（含动态表单字段）。"""
    return {"items": list_enabled_preset_views()}


@router.get("/video-api-templates")
async def list_video_api_templates(
    protocol_code: str = Query(..., min_length=1, max_length=64),
    user: User = Depends(get_current_user),
):
    """返回某协议下允许选择的模板列表（原生协议无模板时为空数组）。"""
    return {"items": list_template_views(protocol_code)}


@router.get("/video-model-profiles")
async def list_video_model_profiles(
    protocol_code: str = Query(..., min_length=1, max_length=64),
    template_code: str | None = Query(default=None, max_length=64),
    user: User = Depends(get_current_user),
):
    """返回某协议（可按模板过滤）的已核验模型能力列表。"""
    return {"items": list_profile_views(protocol_code, template_code)}
