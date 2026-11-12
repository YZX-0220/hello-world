"""国家/地区负面提示词路由。"""

from fastapi import APIRouter, Depends, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import db_session, get_current_user
from app.db.models.user import User
from app.repositories.cultural_guidances import CulturalGuidanceRepository
from app.schemas.cultural_guidance import (
    CreateCulturalGuidanceRequest,
    CulturalGuidanceItem,
    CulturalGuidanceListResponse,
    UpdateCulturalGuidanceRequest,
)

router = APIRouter(prefix="/cultural-guidances", tags=["国际传播国家负面提示词"])


@router.get("", response_model=CulturalGuidanceListResponse)
async def list_cultural_guidances(
    session: AsyncSession = Depends(db_session),
) -> CulturalGuidanceListResponse:
    """获取所有启用的国家/地区负面提示词及禁忌配置（公开/登录均可读取）。"""
    repo = CulturalGuidanceRepository(session)
    items = await repo.list_enabled()
    return CulturalGuidanceListResponse(
        items=[
            CulturalGuidanceItem(
                id=item.id or 0,
                code=item.code,
                name=item.name,
                negative_prompt=item.negative_prompt,
                taboo=item.taboo,
                sort_order=item.sort_order,
                is_enabled=item.is_enabled,
                created_at=item.created_at,
                updated_at=item.updated_at,
            )
            for item in items
        ]
    )


@router.post("", response_model=CulturalGuidanceItem, status_code=status.HTTP_201_CREATED)
async def create_cultural_guidance(
    payload: CreateCulturalGuidanceRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(db_session),
) -> CulturalGuidanceItem:
    """新增国家负面提示词与禁忌配置。"""
    repo = CulturalGuidanceRepository(session)
    item = await repo.create(
        code=payload.code,
        name=payload.name,
        negative_prompt=payload.negative_prompt,
        taboo=payload.taboo,
        sort_order=payload.sort_order,
        is_enabled=payload.is_enabled,
    )
    return CulturalGuidanceItem(
        id=item.id or 0,
        code=item.code,
        name=item.name,
        negative_prompt=item.negative_prompt,
        taboo=item.taboo,
        sort_order=item.sort_order,
        is_enabled=item.is_enabled,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


@router.put("/{code}", response_model=CulturalGuidanceItem)
async def update_cultural_guidance(
    code: str,
    payload: UpdateCulturalGuidanceRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(db_session),
) -> CulturalGuidanceItem:
    """更新指定国家的负面提示词、禁忌描述或排序权重。"""
    repo = CulturalGuidanceRepository(session)
    item = await repo.update_by_code(
        code,
        name=payload.name,
        negative_prompt=payload.negative_prompt,
        taboo=payload.taboo,
        sort_order=payload.sort_order,
        is_enabled=payload.is_enabled,
    )
    return CulturalGuidanceItem(
        id=item.id or 0,
        code=item.code,
        name=item.name,
        negative_prompt=item.negative_prompt,
        taboo=item.taboo,
        sort_order=item.sort_order,
        is_enabled=item.is_enabled,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )
