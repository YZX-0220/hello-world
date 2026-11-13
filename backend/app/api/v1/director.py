"""全片 AI 统筹规划（AI 导演向导）路由。"""

from fastapi import APIRouter, Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import db_session, get_current_user, require_csrf
from app.db.models.user import User
from app.schemas.director import (
    DirectorBreakdownRequest,
    DirectorBreakdownResponse,
    DirectorOutlineRequest,
    DirectorOutlineResponse,
)
from app.services.director_agent_service import DirectorAgentService

router = APIRouter(tags=["全片AI统筹导演向导"])


@router.post(
    "/conversations/{conversation_id}/director/outline",
    response_model=DirectorOutlineResponse,
)
async def generate_director_outline(
    conversation_id: str,
    payload: DirectorOutlineRequest,
    user: User = Depends(get_current_user),
    _csrf: None = Depends(require_csrf),
    session: AsyncSession = Depends(db_session),
) -> DirectorOutlineResponse:
    """Step 1：生成或迭代全片剧本大纲。"""
    svc = DirectorAgentService(session)
    return await svc.generate_outline(user.id, conversation_id, payload)


@router.post(
    "/conversations/{conversation_id}/director/breakdown",
    response_model=DirectorBreakdownResponse,
)
async def generate_director_breakdown(
    conversation_id: str,
    payload: DirectorBreakdownRequest,
    user: User = Depends(get_current_user),
    _csrf: None = Depends(require_csrf),
    session: AsyncSession = Depends(db_session),
) -> DirectorBreakdownResponse:
    """Step 2 -> Step 3：结合国别禁忌与视觉风格，按时间轴拆解分镜脚本与全局提示词节点。"""
    svc = DirectorAgentService(session)
    return await svc.generate_breakdown(user.id, conversation_id, payload)
