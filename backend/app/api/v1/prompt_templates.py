"""提示词模板与版本控制路由。"""

from json import loads as json_loads

from fastapi import APIRouter, Depends, Query, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import db_session, get_current_user
from app.core.errors import PROMPT_TEMPLATE_NOT_FOUND, PROMPT_TEMPLATE_VERSION_NOT_FOUND, AppError
from app.db.models.cultural_guidance import PromptTemplate, PromptTemplateVersion
from app.db.models.user import User
from app.repositories.prompt_templates import PromptTemplateRepository
from app.schemas.prompt_template import (
    CreatePromptTemplateRequest,
    PromptTemplateListResponse,
    PromptTemplateVersionView,
    PromptTemplateView,
    RollbackPromptTemplateRequest,
    UpdatePromptTemplateRequest,
)

router = APIRouter(prefix="/prompt-templates", tags=["提示词模板与版本管理"])


def _to_view(item: PromptTemplate) -> PromptTemplateView:
    try:
        vars_list = json_loads(item.variables_json)
    except Exception:
        vars_list = []
    return PromptTemplateView(
        id=item.id,
        user_id=item.user_id,
        code=item.code,
        scope=item.scope,
        category=item.category,
        name=item.name,
        description=item.description,
        content=item.content,
        negative_prompt=item.negative_prompt,
        variables=vars_list,
        current_version=item.current_version,
        status=item.status,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def _to_version_view(v: PromptTemplateVersion) -> PromptTemplateVersionView:
    try:
        vars_list = json_loads(v.variables_json)
    except Exception:
        vars_list = []
    return PromptTemplateVersionView(
        id=v.id,
        template_id=v.template_id,
        version=v.version,
        name=v.name,
        content=v.content,
        negative_prompt=v.negative_prompt,
        variables=vars_list,
        source_type=v.source_type,
        change_note=v.change_note,
        created_by=v.created_by,
        created_at=v.created_at,
    )


@router.get("", response_model=PromptTemplateListResponse)
async def list_prompt_templates(
    category: str | None = Query(default=None, max_length=32),
    scope: str | None = Query(default=None, max_length=16),
    q: str | None = Query(default=None, max_length=100),
    session: AsyncSession = Depends(db_session),
) -> PromptTemplateListResponse:
    """获取提示词模板列表（返回系统预置模板及模板库）。"""
    repo = PromptTemplateRepository(session)
    items = await repo.list_templates(category=category, scope=scope, q=q)
    return PromptTemplateListResponse(items=[_to_view(item) for item in items])


@router.post("", response_model=PromptTemplateView, status_code=status.HTTP_201_CREATED)
async def create_prompt_template(
    payload: CreatePromptTemplateRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(db_session),
) -> PromptTemplateView:
    """新建提示词模板（自动创建 v1 初始版本）。"""
    repo = PromptTemplateRepository(session)
    template, _ = await repo.create(
        name=payload.name,
        content=payload.content,
        category=payload.category,
        negative_prompt=payload.negative_prompt,
        description=payload.description,
        code=payload.code,
        scope="user",
        user_id=user.id,
        change_note=payload.change_note or "创建初始版本",
    )
    return _to_view(template)


@router.get("/{template_id}", response_model=PromptTemplateView)
async def get_prompt_template(
    template_id: str,
    session: AsyncSession = Depends(db_session),
) -> PromptTemplateView:
    """获取单个提示词模板详情。"""
    repo = PromptTemplateRepository(session)
    template = await repo.get_by_id(template_id)
    if not template:
        raise AppError(PROMPT_TEMPLATE_NOT_FOUND, "提示词模板不存在")
    return _to_view(template)


@router.put("/{template_id}", response_model=PromptTemplateView)
async def update_prompt_template(
    template_id: str,
    payload: UpdatePromptTemplateRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(db_session),
) -> PromptTemplateView:
    """修改提示词模板（内容变更时自动递增版本号并留存快照）。"""
    repo = PromptTemplateRepository(session)
    template, _ = await repo.update(
        template_id,
        user.id,
        name=payload.name,
        category=payload.category,
        content=payload.content,
        negative_prompt=payload.negative_prompt,
        description=payload.description,
        change_note=payload.change_note,
    )
    return _to_view(template)


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_prompt_template(
    template_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(db_session),
) -> None:
    """删除自定义提示词模板（软删除）。"""
    repo = PromptTemplateRepository(session)
    await repo.delete(template_id, user.id)


@router.get("/{template_id}/versions", response_model=list[PromptTemplateVersionView])
async def list_template_versions(
    template_id: str,
    session: AsyncSession = Depends(db_session),
) -> list[PromptTemplateVersionView]:
    """查看模板全部历史版本演进列表（版本倒序）。"""
    repo = PromptTemplateRepository(session)
    versions = await repo.list_versions(template_id)
    return [_to_version_view(v) for v in versions]


@router.get("/{template_id}/versions/{version_num}", response_model=PromptTemplateVersionView)
async def get_template_version(
    template_id: str,
    version_num: int,
    session: AsyncSession = Depends(db_session),
) -> PromptTemplateVersionView:
    """获取某个历史版本的详细快照。"""
    repo = PromptTemplateRepository(session)
    v = await repo.get_version(template_id, version_num)
    if not v:
        raise AppError(PROMPT_TEMPLATE_VERSION_NOT_FOUND, f"版本 v{version_num} 不存在")
    return _to_version_view(v)


@router.post("/{template_id}/rollback", response_model=PromptTemplateView)
async def rollback_template_version(
    template_id: str,
    payload: RollbackPromptTemplateRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(db_session),
) -> PromptTemplateView:
    """将提示词模板回滚到指定历史版本，并生成新的回滚版本记录。"""
    repo = PromptTemplateRepository(session)
    template, _ = await repo.rollback(
        template_id,
        user.id,
        target_version_num=payload.target_version,
        change_note=payload.change_note,
    )
    return _to_view(template)
