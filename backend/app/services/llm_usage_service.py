"""通用大模型与多模态生成 Token 消耗记账服务。

用于集中记录非对话类/后台独立调用（如分镜拆解、大纲生成、整板AI审理、图片提示词建议、
历史压缩、视频生成、图片生成）的实际 input_tokens 与 output_tokens，确保平台全量指标不遗漏。
"""

from datetime import datetime
from typing import Any

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.time import now
from app.db.models.site_traffic import LLMUsageRecord
from app.providers.text.base import TextResult


def _coerce_non_negative_int(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return max(int(value), 0)
    if isinstance(value, str):
        try:
            return max(int(float(value.strip())), 0)
        except ValueError:
            return None
    return None


def parse_token_usage(usage: Any) -> tuple[int | None, int | None, int | None]:
    """解析厂商响应中的 usage 字典，返回 (input_tokens, output_tokens, total_tokens)。"""
    if not isinstance(usage, dict):
        return None, None, None
    input_tokens = _coerce_non_negative_int(
        usage.get("prompt_tokens") if "prompt_tokens" in usage else usage.get("input_tokens")
    )
    output_tokens = _coerce_non_negative_int(
        usage.get("completion_tokens")
        if "completion_tokens" in usage
        else usage.get("output_tokens")
    )
    total_tokens = _coerce_non_negative_int(usage.get("total_tokens"))
    if total_tokens is not None:
        if input_tokens is None and output_tokens is None:
            input_tokens = 0
            output_tokens = total_tokens
        elif input_tokens is None and output_tokens is not None:
            input_tokens = max(total_tokens - output_tokens, 0)
        elif output_tokens is None and input_tokens is not None:
            output_tokens = max(total_tokens - input_tokens, 0)
    return input_tokens, output_tokens, total_tokens


async def record_token_usage(
    session: AsyncSession,
    *,
    operation: str,
    input_tokens: int | None,
    output_tokens: int | None,
    user_id: str | None = None,
    conversation_id: str | None = None,
    provider_code: str | None = None,
    model_name: str | None = None,
    provider_request_id: str | None = None,
    status: str = "succeeded",
    created_at: datetime | None = None,
    dedupe_by_request_id: bool = True,
) -> LLMUsageRecord | None:
    """写入一条 Token 消耗记录并提交事务；支持按 (operation, provider_request_id) 去重。"""
    if input_tokens is None and output_tokens is None:
        return None
    try:
        if dedupe_by_request_id and provider_request_id:
            existing = (
                await session.exec(
                    select(LLMUsageRecord.id).where(
                        col(LLMUsageRecord.operation) == operation,
                        col(LLMUsageRecord.provider_request_id) == provider_request_id,
                    )
                )
            ).first()
            if existing is not None:
                return None
        record = LLMUsageRecord(
            user_id=user_id,
            conversation_id=conversation_id,
            operation=operation,
            provider_code=provider_code,
            model_name=model_name or None,
            provider_request_id=provider_request_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            status=status,
            created_at=created_at or now(),
        )
        session.add(record)
        await session.commit()
        return record
    except Exception:
        # 记账属于观测指标，绝不阻断生成或拆解主链路
        return None


async def record_llm_usage(
    session: AsyncSession,
    *,
    operation: str,
    result: TextResult,
    user_id: str | None = None,
    conversation_id: str | None = None,
    provider_code: str | None = None,
    status: str = "succeeded",
) -> LLMUsageRecord | None:
    """写入一条 LLM Token 消耗记录并提交事务。若未产生有效 token 或记录失败则静默容错，不阻断主业务。"""
    return await record_token_usage(
        session,
        operation=operation,
        input_tokens=result.prompt_tokens,
        output_tokens=result.completion_tokens,
        user_id=user_id,
        conversation_id=conversation_id,
        provider_code=provider_code,
        model_name=result.model or None,
        provider_request_id=result.request_id,
        status=status,
        dedupe_by_request_id=False,
    )
