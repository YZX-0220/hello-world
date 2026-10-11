"""项目/方案版本仓储：读取当前方案，写入新方案并提供不可变快照。"""

from sqlalchemy import update
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import VersionSource
from app.core.errors import CANVAS_VERSION_CONFLICT, PROJECT_VERSION_CONFLICT, AppError
from app.core.time import now
from app.db.models.project import VideoProject, VideoProjectVersion


class ProjectRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_conversation(self, user_id: str, conversation_id: str) -> VideoProject | None:
        stmt = select(VideoProject).where(
            VideoProject.conversation_id == conversation_id,
            VideoProject.user_id == user_id,
        )
        stmt = stmt.execution_options(populate_existing=True)
        result = await self._session.exec(stmt)
        return result.first()

    async def get_latest_suggested_prompt(self, project_id: str) -> str | None:
        """读取最新版本快照里的 suggested_prompt（AI 给用户看的自由提示词）。"""
        stmt = (
            select(VideoProjectVersion)
            .where(VideoProjectVersion.project_id == project_id)
            .order_by(VideoProjectVersion.version.desc())  # type: ignore[attr-defined]
            .limit(1)
        )
        result = await self._session.exec(stmt)
        row = result.first()
        return row.suggested_prompt if row is not None else None

    async def confirm(self, project: VideoProject, spec_version: int) -> VideoProject:
        """确认某个方案版本。非当前版本则抛版本冲突（方案变化后旧确认自动失效）。"""
        if spec_version != project.current_spec_version or spec_version < 0:
            raise AppError(PROJECT_VERSION_CONFLICT)
        project.confirmed_spec_version = spec_version
        project.confirmed_at = now()
        project.updated_at = now()
        await self._session.commit()
        await self._session.refresh(project)
        return project

    async def commit_spec(
        self,
        project: VideoProject,
        spec_json: str,
        source_type: str = VersionSource.AGENT.value,
        source_message_id: str | None = None,
        suggested_prompt: str | None = None,
    ) -> VideoProject:
        """写入新方案：递增版本并生成不可变快照，再更新当前方案。已在同一事务内。"""
        next_version = project.current_spec_version + 1
        snapshot = VideoProjectVersion(
            project_id=project.id,
            version=next_version,
            spec_json=spec_json,
            source_type=source_type,
            source_message_id=source_message_id,
            suggested_prompt=suggested_prompt,
        )
        self._session.add(snapshot)
        project.current_spec_json = spec_json
        project.current_spec_version = next_version
        project.updated_at = now()
        await self._session.commit()
        await self._session.refresh(project)
        return project

    async def save_canvas(
        self, project: VideoProject, canvas_json: str, expected_version: int | None = None
    ) -> VideoProject:
        """Compare-and-swap only canvas fields; never overwrite a concurrent canvas."""
        version = project.canvas_version if expected_version is None else expected_version
        stmt = (
            update(VideoProject)
            .where(col(VideoProject.id) == project.id, col(VideoProject.canvas_version) == version)
            .values(canvas_data_json=canvas_json, canvas_version=version + 1, updated_at=now())
            .execution_options(synchronize_session=False)
            .returning(col(VideoProject.id))
        )
        result = await self._session.execute(stmt)
        if result.first() is None:
            await self._session.rollback()
            raise AppError(CANVAS_VERSION_CONFLICT)
        await self._session.commit()
        await self._session.refresh(project)
        return project

    async def commit_canvas_spec(
        self, project: VideoProject, canvas_json: str, canvas_version: int,
        spec_version: int, spec_json: str, suggested_prompt: str | None,
    ) -> VideoProject:
        """Publish the prepared brief and its sources atomically; reject edits during AI work."""
        stmt = (
            update(VideoProject)
            .where(
                col(VideoProject.id) == project.id,
                col(VideoProject.canvas_version) == canvas_version,
                col(VideoProject.current_spec_version) == spec_version,
            )
            .values(
                current_spec_json=spec_json, current_spec_version=spec_version + 1,
                canvas_data_json=canvas_json, canvas_version=canvas_version + 1,
                confirmed_spec_version=None, confirmed_at=None, updated_at=now(),
            )
            .execution_options(synchronize_session=False)
            .returning(col(VideoProject.id))
        )
        if (await self._session.execute(stmt)).first() is None:
            await self._session.rollback()
            raise AppError(CANVAS_VERSION_CONFLICT, "整理期间画布已变化，请用最新内容重新整理")
        self._session.add(VideoProjectVersion(
            project_id=project.id, version=spec_version + 1, spec_json=spec_json,
            source_type=VersionSource.AGENT.value, suggested_prompt=suggested_prompt,
        ))
        await self._session.commit()
        await self._session.refresh(project)
        return project
