"""剪辑工程 (ClipProject) 数据库持久化仓储。"""

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.time import now
from app.db.models.clip_project import ClipProject


class ClipProjectRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_user(self, user_id: str) -> list[ClipProject]:
        stmt = (
            select(ClipProject)
            .where(ClipProject.user_id == user_id)
            .order_by(col(ClipProject.updated_at).desc())
        )
        return list((await self._session.exec(stmt)).all())

    async def get_for_user(self, project_id: str, user_id: str) -> ClipProject | None:
        stmt = select(ClipProject).where(
            ClipProject.id == project_id, ClipProject.user_id == user_id
        )
        return (await self._session.exec(stmt)).first()

    async def create(
        self,
        user_id: str,
        title: str,
        width: int,
        height: int,
        fps: int,
    ) -> ClipProject:
        project = ClipProject(
            user_id=user_id,
            title=title,
            width=width,
            height=height,
            fps=fps,
            timeline_json='{"tracks":[],"duration_ms":0}',
            version=1,
            created_at=now(),
            updated_at=now(),
        )
        self._session.add(project)
        await self._session.commit()
        await self._session.refresh(project)
        return project

    async def update(
        self,
        project: ClipProject,
        title: str,
        timeline_json: str,
        duration_ms: int,
        expected_version: int,
    ) -> ClipProject | None:
        """带乐观锁版本校验的更新。版本不匹配返回 None。"""
        if project.version != expected_version:
            return None

        project.title = title
        project.timeline_json = timeline_json
        project.duration_ms = duration_ms
        project.version = project.version + 1
        project.updated_at = now()

        self._session.add(project)
        await self._session.commit()
        await self._session.refresh(project)
        return project

    async def delete(self, project: ClipProject) -> None:
        await self._session.delete(project)
        await self._session.commit()
