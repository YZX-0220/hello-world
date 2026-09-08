"""对话、消息与视频项目路由（/api/v1/conversations...）。

写接口要求登录 + CSRF；读接口要求登录。
"""

import json

from fastapi import APIRouter, Depends, Query
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import db_session, get_current_user, require_csrf
from app.core.errors import CONVERSATION_NOT_FOUND, AppError
from app.db.models.project import VideoProject
from app.db.models.user import User
from app.repositories.projects import ProjectRepository
from app.schemas.agent import VideoBrief
from app.schemas.conversation import (
    ConfirmProjectRequest,
    ConversationView,
    CreateConversationRequest,
    Page,
    PatchProjectRequest,
    ProjectSummary,
    SendMessageRequest,
    VideoProjectView,
)
from app.services.conversation_service import ConversationService
from app.services.project_service import ProjectService

router = APIRouter()

_LIMIT_DEFAULT = 20
_LIMIT_MAX = 100


def _project_view(project: VideoProject, suggested_prompt: str | None = None) -> VideoProjectView:
    spec = json.loads(project.current_spec_json or "{}")
    confirmed = project.confirmed_spec_version
    return VideoProjectView(
        id=project.id,
        conversation_id=project.conversation_id,
        current_spec=VideoBrief.model_validate(spec) if spec else VideoBrief(),
        current_spec_version=project.current_spec_version,
        suggested_prompt=suggested_prompt,
        confirmed_spec_version=confirmed,
        confirmed_at=project.confirmed_at,
        is_current_version_confirmed=(confirmed is not None and confirmed == project.current_spec_version),
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


@router.post("/conversations", status_code=201)
async def create_conversation(
    payload: CreateConversationRequest,
    user: User = Depends(get_current_user),
    _csrf: None = Depends(require_csrf),
    session: AsyncSession = Depends(db_session),
):
    svc = ConversationService(session)
    conversation = await svc.create_conversation(user.id, payload.title)
    project = await ProjectRepository(session).get_by_conversation(user.id, conversation.id)
    sp = await ProjectRepository(session).get_latest_suggested_prompt(project.id) if project else None
    return {
        "conversation": ConversationView.model_validate(conversation),
        "project": _project_view(project, sp) if project else None,
    }


@router.get("/conversations", response_model=Page)
async def list_conversations(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(db_session),
    limit: int = Query(default=_LIMIT_DEFAULT, ge=1, le=_LIMIT_MAX),
    status: str | None = Query(default=None),
    cursor: str | None = Query(default=None),
):
    svc = ConversationService(session)
    rows, next_cursor = await svc.list_conversations(user.id, status, limit, cursor)
    return Page(items=[ConversationView.model_validate(r) for r in rows], next_cursor=next_cursor)


@router.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(db_session),
):
    svc = ConversationService(session)
    conversation = await svc.get_or_404(user.id, conversation_id)
    project = await ProjectRepository(session).get_by_conversation(user.id, conversation_id)
    summary = None
    if project is not None:
        confirmed = project.confirmed_spec_version
        summary = ProjectSummary(
            project_id=project.id,
            current_spec_version=project.current_spec_version,
            confirmed_spec_version=confirmed,
            is_current_version_confirmed=(confirmed is not None and confirmed == project.current_spec_version),
        )
    return {"conversation": ConversationView.model_validate(conversation), "project_summary": summary}


@router.get("/conversations/{conversation_id}/messages", response_model=Page)
async def list_messages(
    conversation_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(db_session),
    limit: int = Query(default=_LIMIT_DEFAULT, ge=1, le=_LIMIT_MAX),
    cursor: str | None = Query(default=None),
):
    svc = ConversationService(session)
    rows, next_cursor = await svc.list_messages(user.id, conversation_id, limit, cursor)
    return Page(items=[await svc.message_view(r) for r in rows], next_cursor=next_cursor)


@router.post("/conversations/{conversation_id}/messages", status_code=201)
async def send_message(
    conversation_id: str,
    payload: SendMessageRequest,
    user: User = Depends(get_current_user),
    _csrf: None = Depends(require_csrf),
    session: AsyncSession = Depends(db_session),
):
    svc = ConversationService(session)
    user_message, assistant_message, _ = await svc.send_message(
        user.id, conversation_id, payload.content, payload.client_request_id, payload.web_search_enabled
    )
    project = await ProjectRepository(session).get_by_conversation(user.id, conversation_id)
    sp = await ProjectRepository(session).get_latest_suggested_prompt(project.id) if project else None
    return {
        "run_id": user_message.id,
        "run_status": "succeeded" if assistant_message is not None else "pending",
        "user_message": await svc.message_view(user_message) if user_message else None,
        "assistant_message": await svc.message_view(assistant_message) if assistant_message else None,
        "project": _project_view(project, sp) if project else None,
    }


@router.get("/conversations/{conversation_id}/project")
async def get_project(
    conversation_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(db_session),
) -> VideoProjectView:
    project = await ProjectRepository(session).get_by_conversation(user.id, conversation_id)
    if project is None:
        raise AppError(CONVERSATION_NOT_FOUND)
    sp = await ProjectRepository(session).get_latest_suggested_prompt(project.id)
    return _project_view(project, sp)


@router.post("/conversations/{conversation_id}/project/confirm")
async def confirm_project(
    conversation_id: str,
    payload: ConfirmProjectRequest,
    user: User = Depends(get_current_user),
    _csrf: None = Depends(require_csrf),
    session: AsyncSession = Depends(db_session),
) -> VideoProjectView:
    """确认某个方案版本。非当前版本则 409（方案已变化，需重新确认）。"""
    repo = ProjectRepository(session)
    project = await repo.get_by_conversation(user.id, conversation_id)
    if project is None:
        raise AppError(CONVERSATION_NOT_FOUND)
    project = await repo.confirm(project, payload.spec_version)
    sp = await repo.get_latest_suggested_prompt(project.id)
    return _project_view(project, sp)


@router.patch("/conversations/{conversation_id}/project")
async def patch_project(
    conversation_id: str,
    payload: PatchProjectRequest,
    user: User = Depends(get_current_user),
    _csrf: None = Depends(require_csrf),
    session: AsyncSession = Depends(db_session),
) -> VideoProjectView:
    """用户手动修改方案字段（带期望版本乐观锁；版本不符 409）。"""
    repo = ProjectRepository(session)
    if await repo.get_by_conversation(user.id, conversation_id) is None:
        raise AppError(CONVERSATION_NOT_FOUND)
    svc = ProjectService(session)
    await svc.patch_manual(user.id, conversation_id, payload.expected_spec_version, payload.patch.model_dump(exclude_unset=True))
    project = await repo.get_by_conversation(user.id, conversation_id)
    if project is None:
        raise AppError(CONVERSATION_NOT_FOUND)
    sp = await repo.get_latest_suggested_prompt(project.id)
    return _project_view(project, sp)
