"""通用大模型 Token 消耗记账服务。

用于集中记录非对话类/后台独立大模型调用（如分镜拆解、大纲生成、整板AI审理、图片提示词建议、历史压缩）的
实际 input_tokens 与 output_tokens，确保平台全量大模型调用指标不遗漏。
"""

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.time import now
from app.db.models.site_traffic import LLMUsageRecord
from app.providers.text.base import TextResult


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
    try:
        record = LLMUsageRecord(
            user_id=user_id,
            conversation_id=conversation_id,
            operation=operation,
            provider_code=provider_code,
            model_name=result.model or None,
            provider_request_id=result.request_id,
            input_tokens=result.prompt_tokens,
            output_tokens=result.completion_tokens,
            status=status,
            created_at=now(),
        )
        session.add(record)
        await session.commit()
        return record
    except Exception:
        # 记账属于观测指标，绝不阻断生成或拆解主链路
        return None
