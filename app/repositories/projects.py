"""项目/方案版本仓储：读取当前方案，写入新方案并提供不可变快照。"""

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import VersionSource
from app.core.errors import PROJECT_VERSION_CONFLICT, AppError
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
