"""文本 Agent 服务：构造上下文→调用文本 Provider→解析结构化输出→交付结果。

MVP 采用【非流式、同步阻塞】处理（请求期间等待模型返回）。异步流水线与 worker 在
后续批次实现；当前实现保证"能基本对话 + 逐轮更新方案"的可靠链路。
"""

from typing import ClassVar

from pydantic import ValidationError
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.errors import (
    TEXT_PROVIDER_TIMEOUT,
    TEXT_PROVIDER_UNAVAILABLE,
    AppError,
)
from app.providers.text import get_text_provider
from app.providers.text.base import TextProvider, TextProviderError
from app.schemas.agent import AgentOutput, VideoBrief, VideoBriefPatch
from app.services.context_builder import build_context
from app.services.project_service import ProjectService


class AgentService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._provider: TextProvider = get_text_provider()
        self._projects = ProjectService(session)

    # 常见模型字段别名 → VideoBrief 标准字段；不在标准集合内的视为多余并丢弃
    _PATCH_ALIASES: ClassVar[dict[str, str]] = {
        "duration": "duration_seconds",
        "style": "visual_style",
        "scenes": "scene",
        "shot": "camera",
        "prompt": "suggested_prompt",
    }

    @classmethod
    def _normalize_patch(cls, raw: dict) -> dict:
        """把模型返回的 state_patch 归一化为 VideoBriefPatch 能接受的字段集合。

        - 字段名按别名映射到标准字段；不在标准集合内的丢弃；
        - 字符串值去首尾空格；空字符串视为省略；
        - 列表字段：仅 reference_asset_ids 保留列表，其余合并为字符串。
        """
        fields = set(VideoBriefPatch.model_fields)
        out: dict = {}
        for key, value in raw.items():
            canonical = cls._PATCH_ALIASES.get(key, key)
            if canonical not in fields:
                continue
            if isinstance(value, list):
                if canonical == "reference_asset_ids":
                    out[canonical] = value
                else:
                    joined = "；".join(str(x) for x in value)
                    if joined:
                        out[canonical] = joined
                continue
            if isinstance(value, str):
                stripped = value.strip()
                if stripped:
                    out[canonical] = stripped
                continue
            out[canonical] = value
        return out

    def _best_effort_patch(self, value: object) -> VideoBriefPatch:
        """逐字段容错解析 state_patch：单个字段值非法时跳过该字段，而非整体失败。"""
        if not isinstance(value, dict):
            return VideoBriefPatch()
        clean = self._normalize_patch(value)
        patch_dict: dict = {}
        for key, val in clean.items():
            try:
                VideoBriefPatch.model_validate({**patch_dict, key: val})
            except ValidationError:
                continue
            patch_dict[key] = val
        return VideoBriefPatch.model_validate(patch_dict) if patch_dict else VideoBriefPatch()

    def _parse_output(self, structured: dict | None, fallback_reply: str) -> AgentOutput:
        """把模型返回的结构化内容解析为 AgentOutput。

        兼容两种形态：
        - 完整 AgentOutput 形状（含 reply / state_patch 字段）：回复始终取 reply 自然语言，
          state_patch 逐字段容错解析；
        - 直接把 JSON 当作 state_patch：回复用 fallback_reply 兜底。
        """
        if structured is None:
            return AgentOutput(reply=fallback_reply)
        if "reply" in structured or "state_patch" in structured:
            reply = str(structured.get("reply") or fallback_reply)
            patch = self._best_effort_patch(structured.get("state_patch"))
            missing = [str(x) for x in (structured.get("missing_fields") or [])]
            return AgentOutput(
                reply=reply,
                state_patch=patch,
                missing_fields=missing,
                ready_for_generation=bool(structured.get("ready_for_generation", False)),
                suggested_prompt=structured.get("suggested_prompt"),
                search_requests=[str(x) for x in (structured.get("search_requests") or [])],
            )
        patch = self._best_effort_patch(structured)
        return AgentOutput(reply=fallback_reply, state_patch=patch)

    async def run_turn(self, user_id: str, conversation_id: str, user_content: str, history: list[dict[str, str]]) -> AgentOutput:
        """执行一轮对话，返回结构与用户回复。"""
        brief_dict = await self._projects.get_current_brief(user_id, conversation_id)
        brief = VideoBrief.model_validate(brief_dict) if brief_dict else VideoBrief()
        context = build_context(brief, history, user_content)

        try:
            result = await self._provider.generate(context, structured=True)
        except TextProviderError as exc:
            if exc.code == "TEXT_PROVIDER_TIMEOUT":
                raise AppError(TEXT_PROVIDER_TIMEOUT, exc.message) from exc
            raise AppError(TEXT_PROVIDER_UNAVAILABLE, exc.message) from exc

        return self._parse_output(result.structured, result.reply)
