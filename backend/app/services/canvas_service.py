"""Persist node-scoped AI results independently of the lifetime of a browser tab."""

import json

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.core.errors import (
    CANVAS_NODE_INVALID,
    CANVAS_VERSION_CONFLICT,
    CONVERSATION_BUSY,
    AppError,
)
from app.core.time import now, parse_iso8601
from app.repositories.projects import ProjectRepository
from app.schemas.agent import VideoBrief
from app.schemas.canvas import CanvasCollaboration


class CanvasService:
    def __init__(self, session: AsyncSession) -> None:
        self._repo = ProjectRepository(session)

    async def recover_expired(self, user_id: str, conversation_id: str) -> None:
        """A crashed server must not leave a canvas busy permanently."""
        lease_seconds = max(
            600,
            settings.text_timeout * 3 + settings.search_timeout * settings.search_max_calls + 60,
        )
        for _ in range(5):
            project = await self._repo.get_by_conversation(user_id, conversation_id)
            if project is None:
                return
            data = json.loads(project.canvas_data_json or "{}")
            changed = False
            for node in data.get("nodes", []):
                if not node.get("ai_running"):
                    continue
                try:
                    started = parse_iso8601(node.get("ai_started_at", ""))
                    expired = (now() - started).total_seconds() > lease_seconds
                except (ValueError, TypeError):
                    expired = True
                if expired:
                    node.update(
                        ai_running=False, ai_error="AI 协作已超时，原文已保留，可以重新发送"
                    )
                    changed = True
            if not changed:
                return
            try:
                await self._repo.save_canvas(
                    project, json.dumps(data, ensure_ascii=False), project.canvas_version
                )
                return
            except AppError as exc:
                if exc.code != CANVAS_VERSION_CONFLICT:
                    raise
        raise AppError(CANVAS_VERSION_CONFLICT)

    async def begin(
        self,
        user_id: str,
        conversation_id: str,
        request_id: str,
        collaboration: CanvasCollaboration,
    ) -> tuple[str, str, dict]:
        """Capture the target/reference content at request time and persist a running marker."""
        await self.recover_expired(user_id, conversation_id)
        for _ in range(5):
            project = await self._repo.get_by_conversation(user_id, conversation_id)
            if project is None:
                raise AppError(CANVAS_NODE_INVALID)
            data = json.loads(project.canvas_data_json or "{}")
            nodes = data.get("nodes", [])
            target = next(
                (node for node in nodes if node.get("id") == collaboration.target_node_id), None
            )
            if target is None or target.get("type") != "text":
                raise AppError(CANVAS_NODE_INVALID)
            if any(node.get("ai_running") for node in nodes):
                raise AppError(CONVERSATION_BUSY, "这个项目正在执行 AI 协作，请等回复完成后再发送")
            original = target.get("content") or ""
            parts = [f"协作目标【{target.get('title', '文本节点')}】：\n{original[:12000]}"]
            candidate = target.get("pending_ai") or {}
            if candidate.get("source_model") == "local-preview":
                candidate = {}
            accepted = target.get("last_ai") or {}
            if candidate.get("content"):
                parts.append(
                    f"上次讨论的待确认方案（尚未写入小框）：\n{candidate['content'][:12000]}"
                )
            history = target.get("ai_history") or []
            if history:
                recent = [
                    f"{m.get('role')}: {str(m.get('content') or '')[:1500]}" for m in history[-4:]
                ]
                parts.append("该小框最近的讨论（仅作上下文）：\n" + "\n".join(recent))
            base = (
                candidate.get("brief")
                or (accepted.get("brief") if accepted.get("after") == original else {})
                or {}
            )
            for node in nodes:
                if node.get("id") in collaboration.reference_node_ids and node is not target:
                    parts.append(
                        f"参考节点【{node.get('title', '')}】（{node.get('type')}）：\n{str(node.get('content') or '')[:4000]}"
                    )
            target.update(
                ai_running=True, ai_request_id=request_id, ai_started_at=now().isoformat()
            )
            target.pop("ai_error", None)
            try:
                await self._repo.save_canvas(
                    project, json.dumps(data, ensure_ascii=False), project.canvas_version
                )
                return original, "\n\n".join(parts)[:30000], base
            except AppError as exc:
                if exc.code != CANVAS_VERSION_CONFLICT:
                    raise
        raise AppError(CANVAS_VERSION_CONFLICT)

    async def complete(
        self,
        user_id: str,
        conversation_id: str,
        request_id: str,
        collaboration: CanvasCollaboration,
        original: str,
        reply: str | None,
        message_id: str,
        brief: dict,
        suggested_prompt: str | None,
        *,
        user_content: str = "",
        discussion_reply: str = "",
    ) -> None:
        for _ in range(5):
            project = await self._repo.get_by_conversation(user_id, conversation_id)
            if project is None:
                return
            data = json.loads(project.canvas_data_json or "{}")
            target = next(
                (
                    node
                    for node in data.get("nodes", [])
                    if node.get("id") == collaboration.target_node_id
                ),
                None,
            )
            # Deleting a node while AI runs must not resurrect it or write into a different node.
            if (
                target is None
                or target.get("ai_request_id") != request_id
                or not target.get("ai_running")
            ):
                return
            target["ai_running"] = False
            target.pop("ai_error", None)
            # Discussion never changes the editable box, even when it was empty.
            if reply and reply.strip():
                target["pending_ai"] = {
                    "content": reply,
                    "message_id": message_id,
                    "apply_mode": collaboration.apply_mode,
                    "original": original,
                    "brief": brief,
                    "suggested_prompt": suggested_prompt,
                }
            if user_content:
                target["ai_history"] = [
                    *(target.get("ai_history") or []),
                    {"role": "user", "content": user_content[:4000]},
                    {"role": "assistant", "content": discussion_reply[:4000]},
                ][-12:]
            try:
                await self._repo.save_canvas(
                    project, json.dumps(data, ensure_ascii=False), project.canvas_version
                )
                return
            except AppError as exc:
                if exc.code != CANVAS_VERSION_CONFLICT:
                    raise
        raise AppError(CANVAS_VERSION_CONFLICT)

    async def confirm(
        self,
        user_id: str,
        conversation_id: str,
        target_id: str,
        message_id: str,
        expected_version: int,
    ) -> None:
        project = await self._repo.get_by_conversation(user_id, conversation_id)
        if project is None:
            raise AppError(CANVAS_NODE_INVALID)
        data = json.loads(project.canvas_data_json or "{}")
        target = next((n for n in data.get("nodes", []) if n.get("id") == target_id), None)
        if target is None or target.get("type") != "text" or target.get("ai_running"):
            raise AppError(CANVAS_NODE_INVALID, "目标小框不存在或 AI 仍在回复")
        pending = target.get("pending_ai") or {}
        if pending.get("source_model") == "local-preview":
            raise AppError(CANVAS_NODE_INVALID, "这是历史模拟内容，请发送消息让真实 AI 重新创作")
        if pending.get("message_id") != message_id or not pending.get("content", "").strip():
            raise AppError(CANVAS_VERSION_CONFLICT, "待确认的 AI 方案已变化，请查看最新回复")
        before = target.get("content") or ""
        after = (
            f"{before}\n\n{pending['content']}"
            if pending.get("apply_mode") == "append" and before
            else pending["content"]
        )
        # Validate structured metadata; it remains scoped to this node until video preparation.
        brief = VideoBrief.model_validate(pending.get("brief") or {}).model_dump(mode="json")
        target["content"] = after
        target["last_ai"] = {
            "before": before,
            "after": after,
            "message_id": message_id,
            "brief": brief,
            "suggested_prompt": pending.get("suggested_prompt"),
        }
        target.pop("pending_ai", None)
        await self._repo.save_canvas(
            project, json.dumps(data, ensure_ascii=False), expected_version
        )

    async def fail(
        self, user_id: str, conversation_id: str, request_id: str, target_id: str
    ) -> None:
        for _ in range(5):
            project = await self._repo.get_by_conversation(user_id, conversation_id)
            if project is None:
                return
            data = json.loads(project.canvas_data_json or "{}")
            target = next(
                (node for node in data.get("nodes", []) if node.get("id") == target_id), None
            )
            if (
                target is None
                or target.get("ai_request_id") != request_id
                or not target.get("ai_running")
            ):
                return
            target.update(ai_running=False, ai_error="AI 协作未完成，原文已保留，可以重新发送")
            try:
                await self._repo.save_canvas(
                    project, json.dumps(data, ensure_ascii=False), project.canvas_version
                )
                return
            except AppError as exc:
                if exc.code != CANVAS_VERSION_CONFLICT:
                    raise
