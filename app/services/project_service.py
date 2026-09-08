"""项目服务：读取当前方案、合并 PATCH、提交新版本快照。"""

import json

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import VersionSource
from app.core.errors import PROJECT_VERSION_CONFLICT, AppError
from app.repositories.projects import ProjectRepository


class ProjectService:
    def __init__(self, session: AsyncSession) -> None:
        self._repo = ProjectRepository(session)

    async def get_current_brief(self, user_id: str, conversation_id: str) -> dict:
        """返回当前方案（JSON dict），无项目时返回空。"""
        project = await self._repo.get_by_conversation(user_id, conversation_id)
        if project is None:
            return {}
        return json.loads(project.current_spec_json or "{}")

    async def _current_project(self, user_id: str, conversation_id: str):
        project = await self._repo.get_by_conversation(user_id, conversation_id)
        if project is None:
            raise ValueError("项目不存在")  # 调用方转 404
        return project

    @staticmethod
    def merge_patch(current: dict, patch: dict) -> dict:
        """把 PATCH 合并进当前方案。

        规则：缺失不修改；显式 null 清空对应字段；空列表代表清空列表；其余覆盖。
        """
        merged = dict(current)
        for key, value in patch.items():
            if value is None:
                merged.pop(key, None)
            elif isinstance(value, list) and len(value) == 0:
                merged[key] = []
            else:
                merged[key] = value
        return merged

    async def apply_patch(
        self,
        user_id: str,
        conversation_id: str,
        patch: dict,
        source: str = VersionSource.MANUAL.value,
        source_message_id: str | None = None,
        suggested_prompt: str | None = None,
    ) -> dict:
        """合并并提交新方案版本。返回合并后的完整方案。"""
        project = await self._current_project(user_id, conversation_id)
        current = json.loads(project.current_spec_json or "{}")
        merged = self.merge_patch(current, patch)
        spec_json = json.dumps(merged, ensure_ascii=False)
        await self._repo.commit_spec(project, spec_json, source, source_message_id, suggested_prompt)
        return merged

    async def patch_manual(self, user_id: str, conversation_id: str, expected_version: int, patch: dict) -> None:
        """用户手动修改方案（带乐观锁）。版本不符抛 PROJECT_VERSION_CONFLICT。"""
        project = await self._current_project(user_id, conversation_id)
        if expected_version != project.current_spec_version:
            raise AppError(PROJECT_VERSION_CONFLICT)
        current = json.loads(project.current_spec_json or "{}")
        merged = self.merge_patch(current, patch)
        spec_json = json.dumps(merged, ensure_ascii=False)
        await self._repo.commit_spec(project, spec_json, VersionSource.MANUAL.value, None, None)
