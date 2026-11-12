"""剪辑工程路由 (/api/v1/clip-projects)。"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import db_session, get_current_user
from app.db.models.user import User
from app.repositories.clip_projects import ClipProjectRepository
from app.schemas.clip import (
    ClipProjectView,
    CreateClipProjectRequest,
    UpdateClipProjectRequest,
)

router = APIRouter(prefix="/clip-projects", tags=["clip-projects"])


@router.get("", response_model=list[ClipProjectView])
async def list_projects(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(db_session),
) -> list[ClipProjectView]:
    repo = ClipProjectRepository(session)
    projects = await repo.list_for_user(user.id)
    return [ClipProjectView.model_validate(p) for p in projects]


@router.post("", response_model=ClipProjectView, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: CreateClipProjectRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(db_session),
) -> ClipProjectView:
    repo = ClipProjectRepository(session)
    project = await repo.create(
        user_id=user.id,
        title=payload.title,
        width=payload.width,
        height=payload.height,
        fps=payload.fps,
    )
    return ClipProjectView.model_validate(project)


@router.get("/{project_id}", response_model=ClipProjectView)
async def get_project(
    project_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(db_session),
) -> ClipProjectView:
    repo = ClipProjectRepository(session)
    project = await repo.get_for_user(project_id, user.id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="剪辑工程不存在或无权访问"
        )
    return ClipProjectView.model_validate(project)


@router.put("/{project_id}", response_model=ClipProjectView)
async def update_project(
    project_id: str,
    payload: UpdateClipProjectRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(db_session),
) -> ClipProjectView:
    repo = ClipProjectRepository(session)
    project = await repo.get_for_user(project_id, user.id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="剪辑工程不存在或无权访问"
        )

    updated = await repo.update(
        project=project,
        title=payload.title,
        timeline_json=payload.timeline_json,
        duration_ms=payload.duration_ms,
        expected_version=payload.expected_version,
    )
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="草稿在其他端被修改，版本冲突，请刷新以同步最新版本",
        )
    return ClipProjectView.model_validate(updated)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(db_session),
) -> None:
    repo = ClipProjectRepository(session)
    project = await repo.get_for_user(project_id, user.id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="剪辑工程不存在或无权访问"
        )
    await repo.delete(project)
