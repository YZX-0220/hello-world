"""文本 Agent 服务：构造上下文→调用文本 Provider→解析结构化输出→交付结果。

MVP 采用【非流式、同步阻塞】处理（请求期间等待模型返回）。异步流水线与 worker 在
后续批次实现；当前实现保证"能基本对话 + 逐轮更新方案"的可靠链路。
"""

from typing import ClassVar

from pydantic import ValidationError
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import AgentRunStatus
from app.core.errors import (
    TEXT_PROVIDER_TIMEOUT,
    TEXT_PROVIDER_UNAVAILABLE,
    AppError,
)
from app.core.time import now
from app.db.models.agent import AgentRun
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

    async def run_turn(
        self,
        user_id: str,
        conversation_id: str,
        user_message_id: str,
        user_content: str,
        history: list[dict[str, str]],
    ) -> AgentOutput:
        """执行一轮对话，返回结构与用户回复，并把本轮 AgentRun 落库。

        生命周期：创建 AgentRun(running，记录调用开始时的方案版本) → 调用文本 Provider →
        成功记为 succeeded（带模型名/Token 用量/结束时间），失败记为 failed（带错误码与脱敏错误），
        并把 agent_run_id 挂到 AgentOutput 上，供上层关联工具调用与引用。
        """
        brief_dict = await self._projects.get_current_brief(user_id, conversation_id)
        brief = VideoBrief.model_validate(brief_dict) if brief_dict else VideoBrief()
        context = build_context(brief, history, user_content)

        base_spec_version = await self._projects.get_current_spec_version(user_id, conversation_id)
        agent_run = AgentRun(
            user_id=user_id,
            conversation_id=conversation_id,
            user_message_id=user_message_id,
            base_spec_version=base_spec_version,
            status=AgentRunStatus.RUNNING.value,
            provider_code=self._provider.code,
            started_at=now(),
        )
        self._session.add(agent_run)
        await self._session.commit()
        await self._session.refresh(agent_run)

        try:
            result = await self._provider.generate(context, structured=True)
        except TextProviderError as exc:
            agent_run.status = AgentRunStatus.FAILED.value
            agent_run.error_code = exc.code
            agent_run.error_message = exc.message[:2000]
            agent_run.completed_at = now()
            await self._session.commit()
            if exc.code == "TEXT_PROVIDER_TIMEOUT":
                raise AppError(TEXT_PROVIDER_TIMEOUT, exc.message) from exc
            raise AppError(TEXT_PROVIDER_UNAVAILABLE, exc.message) from exc

        output = self._parse_output(result.structured, result.reply)
        agent_run.status = AgentRunStatus.SUCCEEDED.value
        agent_run.model_name = result.model or None
        agent_run.provider_request_id = result.request_id
        agent_run.input_tokens = result.prompt_tokens
        agent_run.output_tokens = result.completion_tokens
        agent_run.completed_at = now()
        await self._session.commit()

        output.agent_run_id = agent_run.id
        return output

    async def refine_with_search(
        self,
        user_id: str,
        conversation_id: str,
        history: list[dict[str, str]],
        user_content: str,
        search_results_text: str,
    ) -> str | None:
        """第二阶段：把检索结果回流给模型，让它基于检索结果重写最终回复。

        背景：第一阶段模型若通过 search_requests 请求了联网搜索，后端执行搜索后不能把结果
        简单"附"在回复末尾（旧实现），而要真正喂给模型重新生成，这是 function-calling 的
        落地形态之一。

        消息结构与第一阶段复用 build_context（system + 历史 + 当前用户消息），再追加：
          - 一条用户侧提示："请依据以下检索结果给出最终回复，并指出引用的来源。"
          - 一条检索结果注入消息：默认用 role="assistant" 承载（多数 OpenAI 兼容 API 的
            role="tool" 需要 tool_call_id，直接传会被拒绝），这里在注释中明确这是"检索结果注入"，
            避免被误读为真实历史。

        用相同 provider 以 structured=False 再调一次。任何异常或空回复都返回 None，由调用方
        保留初版 reply，保证不丢消息、不报错。
        """
        if not search_results_text.strip():
            return None
        brief_dict = await self._projects.get_current_brief(user_id, conversation_id)
        brief = VideoBrief.model_validate(brief_dict) if brief_dict else VideoBrief()
        context = build_context(brief, history, user_content)
        messages: list[dict[str, str]] = [
            *context,
            {"role": "user", "content": "请依据以下检索结果给出最终回复，并指出引用的来源。"},
            # 检索结果注入（role="assistant" 承载，见方法注释）
            {"role": "assistant", "content": f"【检索结果】\n{search_results_text}"},
        ]
        try:
            result = await self._provider.generate(messages, structured=False)
        except TextProviderError:
            return None
        reply = (result.reply or "").strip()
        return reply or None

    async def bind_assistant_message(self, agent_run_id: str, assistant_message_id: str) -> None:
        """把本轮生成的 assistant 消息 id 写回 AgentRun（在其创建完成后调用）。"""
        agent_run = await self._session.get(AgentRun, agent_run_id)
        if agent_run is None:
            return
        agent_run.assistant_message_id = assistant_message_id
        await self._session.commit()

    async def set_tool_call_count(self, agent_run_id: str, count: int) -> None:
        """写入本轮实际执行的工具调用次数（如联网搜索），供 AgentRun.tool_call_count。"""
        agent_run = await self._session.get(AgentRun, agent_run_id)
        if agent_run is None:
            return
        agent_run.tool_call_count = count
        await self._session.commit()
