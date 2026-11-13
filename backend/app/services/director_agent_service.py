"""全片 AI 统筹规划（AI 导演向导）编排服务。"""

import math
from typing import Any

from pydantic import ValidationError
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.core.errors import (
    AGENT_OUTPUT_INVALID,
    TEXT_PROVIDER_TIMEOUT,
    TEXT_PROVIDER_UNAVAILABLE,
    AppError,
)
from app.prompts.director import (
    allocate_segment_durations,
    build_breakdown_messages,
    build_outline_messages,
    to_cn_index,
)
from app.providers.text import get_text_provider
from app.providers.text.base import TextProvider, TextProviderError
from app.repositories.cultural_guidances import CulturalGuidanceRepository
from app.repositories.prompt_templates import PromptTemplateRepository
from app.schemas.director import (
    DirectorBreakdownRequest,
    DirectorBreakdownResponse,
    DirectorOutlineRequest,
    DirectorOutlineResponse,
)
from app.services.conversation_service import ConversationService


class DirectorAgentService:
    def __init__(self, session: AsyncSession, provider: TextProvider | None = None) -> None:
        self._session = session
        self._convs = ConversationService(session)
        self._cultural_repo = CulturalGuidanceRepository(session)
        self._template_repo = PromptTemplateRepository(session)
        self._provider: TextProvider = provider or get_text_provider()

    @staticmethod
    def _map_provider_error(exc: TextProviderError) -> AppError:
        if exc.code == "TEXT_PROVIDER_TIMEOUT":
            return AppError(TEXT_PROVIDER_TIMEOUT, exc.message)
        if exc.code == "AGENT_OUTPUT_INVALID":
            return AppError(AGENT_OUTPUT_INVALID, exc.message)
        return AppError(TEXT_PROVIDER_UNAVAILABLE, exc.message)

    async def generate_outline(
        self, user_id: str, conversation_id: str, req: DirectorOutlineRequest
    ) -> DirectorOutlineResponse:
        """Step 1：首次生成或根据用户手改草稿 + 修改意见迭代全片剧本大纲。"""
        await self._convs.get_or_404(user_id, conversation_id)
        recommended_segments = max(1, math.ceil(req.total_duration / 15))

        messages = build_outline_messages(
            total_duration=req.total_duration,
            recommended_segments=recommended_segments,
            user_idea=req.user_idea,
            current_draft=req.current_draft,
            revision_instruction=req.revision_instruction,
        )

        try:
            result = await self._provider.generate(
                messages,
                structured=False,
                temperature=settings.director_outline_temperature,
                max_tokens=settings.director_outline_max_tokens,
                timeout=settings.director_timeout,
            )
        except TextProviderError as exc:
            raise self._map_provider_error(exc) from exc

        draft = (result.reply or "").strip()
        if not draft:
            raise AppError(AGENT_OUTPUT_INVALID, "模型未能生成有效剧本大纲，请重试")

        return DirectorOutlineResponse(
            script_draft=draft,
            recommended_segments=recommended_segments,
        )

    @staticmethod
    def _normalize_breakdown(
        raw: dict[str, Any] | None,
        *,
        segment_count: int,
        seg_durations: list[int],
        country_names: str,
        db_negative_prompts: str,
    ) -> DirectorBreakdownResponse:
        if not isinstance(raw, dict):
            raise AppError(AGENT_OUTPUT_INVALID, "AI 分镜拆解输出格式异常，请重试")

        raw_segments = raw.get("segments")
        if not isinstance(raw_segments, list) or len(raw_segments) < segment_count:
            raise AppError(
                AGENT_OUTPUT_INVALID,
                f"AI 返回的分镜片段数量不足（期望 {segment_count} 个），请重试",
            )

        # 若模型多吐出了片段，截断到精确长度并强制规范 index / title / duration
        trimmed_segments: list[dict[str, Any]] = []
        for idx, seg in enumerate(raw_segments[:segment_count], start=1):
            if not isinstance(seg, dict):
                raise AppError(AGENT_OUTPUT_INVALID, "AI 分镜片段条目格式非法，请重试")
            timeline_prompt = str(seg.get("timeline_prompt") or "").strip()
            if not timeline_prompt:
                raise AppError(
                    AGENT_OUTPUT_INVALID, f"片段{to_cn_index(idx)}缺少时间轴提示词，请重试"
                )
            trimmed_segments.append(
                {
                    "index": idx,
                    "title": f"片段{to_cn_index(idx)}",
                    "duration": seg_durations[idx - 1],
                    "timeline_prompt": timeline_prompt,
                }
            )

        style_content = str(raw.get("style_node_content") or "").strip()
        cultural_content = str(raw.get("cultural_node_content") or "").strip()
        image_prompts = str(raw.get("image_asset_prompts") or "").strip()

        if not style_content:
            style_content = "【整体视觉风格】4K电影级写实质感，自然光线，平稳运镜，色调统一。"
        if not cultural_content:
            cultural_content = f"【目标地区】{country_names}"
        # 兜底确保数据库查询到的国别负面词一定留在节点内容中，供后续单点审理读取
        if db_negative_prompts and db_negative_prompts not in cultural_content:
            cultural_content = (
                f"{cultural_content}\n【合并负面提示词 (Negative Prompt)】{db_negative_prompts}"
            ).strip()
        if not image_prompts:
            image_prompts = "【核心图片素材】请根据分镜剧本主体与场景描述生成首帧参考图。"

        normalized = {
            "style_node_content": style_content,
            "cultural_node_content": cultural_content,
            "image_asset_prompts": image_prompts,
            "segments": trimmed_segments,
        }
        try:
            return DirectorBreakdownResponse.model_validate(normalized)
        except ValidationError as exc:
            raise AppError(AGENT_OUTPUT_INVALID, "AI 分镜拆解结果校验失败，请重试") from exc

    async def generate_breakdown(
        self, user_id: str, conversation_id: str, req: DirectorBreakdownRequest
    ) -> DirectorBreakdownResponse:
        """Step 2 -> Step 3：结合国别禁忌、负面词与风格模板，将剧本按秒级时间轴拆解为多节点结构。"""
        await self._convs.get_or_404(user_id, conversation_id)

        # 1. 查询国别文化库（带空列表防护）
        guidances = await self._cultural_repo.list_by_codes(req.country_codes)
        country_names = "、".join(g.name for g in guidances) or "全球通用受众"
        cultural_taboos = (
            "；".join(f"{g.name}: {g.taboo}" for g in guidances if g.taboo) or "无特殊文化禁忌"
        )
        neg_parts = [
            g.negative_prompt.strip()
            for g in guidances
            if g.negative_prompt and g.negative_prompt.strip()
        ]

        # 2. 查询提示词模板库（支持 id 或 code，且做权限校验）
        custom_desc = (req.custom_style_desc or "").strip()
        style_parts: list[str] = []
        if req.style_template_id:
            tpl = await self._template_repo.get_accessible_template(req.style_template_id, user_id)
            if tpl is not None:
                style_parts.append(f"模板名称：{tpl.name}\n模板参考内容：{tpl.content}")
                if tpl.negative_prompt and tpl.negative_prompt.strip():
                    neg_parts.append(tpl.negative_prompt.strip())
        if custom_desc:
            style_parts.append(f"用户自定义风格补充：{custom_desc}")
        style_template_content = (
            "\n".join(style_parts) or "电影级高清写实风格，自然光效，平稳运镜，色调协调统一"
        )
        db_negative_prompts = "、".join(dict.fromkeys(neg_parts))

        # 3. 分配各片段时长（对齐 5/10/15s 档位且满足 1~15s 模型限制）
        seg_durations = allocate_segment_durations(req.total_duration, req.segment_count)

        # 4. 构造 Prompt 并调用结构化输出模型
        messages = build_breakdown_messages(
            segment_count=req.segment_count,
            seg_durations=seg_durations,
            script_draft=req.script_draft,
            country_names=country_names,
            cultural_taboos=cultural_taboos,
            db_negative_prompts=db_negative_prompts or "低画质、画面闪烁、肢体畸变",
            style_template_content=style_template_content,
        )

        try:
            result = await self._provider.generate(
                messages,
                structured=True,
                temperature=settings.director_breakdown_temperature,
                max_tokens=settings.director_breakdown_max_tokens,
                timeout=settings.director_timeout,
            )
        except TextProviderError as exc:
            raise self._map_provider_error(exc) from exc

        return self._normalize_breakdown(
            result.structured,
            segment_count=req.segment_count,
            seg_durations=seg_durations,
            country_names=country_names,
            db_negative_prompts=db_negative_prompts,
        )
