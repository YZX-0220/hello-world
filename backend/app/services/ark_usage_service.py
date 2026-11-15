"""火山方舟用量查询（GetInferenceUsage）与历史视频任务 Token 回填服务。

1. `fetch_ark_inference_usage`: 调用火山方舟管控面 `Action=GetInferenceUsage&Version=2024-01-01`
   （需配置 `ARK_ACCESS_KEY` / `ARK_SECRET_KEY`，使用 Volcengine V4 HMAC-SHA256 签名）。
2. `backfill_ark_video_usage`: 遍历库内已成功但尚未记账的 `ark_seedance_v1` 视频任务，
   通过任务查询接口补齐 `LLMUsageRecord`（按 `provider_task_id` 自动去重）。
"""

from datetime import UTC, datetime
from hashlib import sha256
from hmac import new as hmac_new
from json import dumps as json_dumps
from logging import getLogger
from typing import Any

from httpx import AsyncClient
from sqlalchemy import and_
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.core.enums import VideoJobStatus
from app.db.models.site_traffic import LLMUsageRecord
from app.db.models.video_api_config import VideoApiConfigRevision
from app.db.models.video_job import VideoJob
from app.providers.video import get_video_provider
from app.services.llm_usage_service import record_token_usage
from app.services.video_job_service import VideoJobService

logger = getLogger(__name__)


def _hmac_sha256(key: bytes, msg: str) -> bytes:
    return hmac_new(key, msg.encode("utf-8"), sha256).digest()


def build_volcengine_v4_headers(
    *,
    access_key: str,
    secret_key: str,
    region: str,
    service: str,
    host: str,
    method: str,
    path: str,
    query: str,
    body: bytes,
    now_utc: datetime | None = None,
) -> dict[str, str]:
    """构造火山引擎 OpenAPI Signature V4 请求头。"""
    dt = (now_utc or datetime.now(UTC)).astimezone(UTC)
    x_date = dt.strftime("%Y%m%dT%H%M%SZ")
    short_date = dt.strftime("%Y%m%d")
    body_hash = sha256(body).hexdigest()

    canonical_headers = (
        f"content-type:application/json; charset=utf-8\n"
        f"host:{host}\n"
        f"x-content-sha256:{body_hash}\n"
        f"x-date:{x_date}\n"
    )
    signed_headers = "content-type;host;x-content-sha256;x-date"
    canonical_request = "\n".join(
        [
            method.upper(),
            path,
            query,
            canonical_headers,
            signed_headers,
            body_hash,
        ]
    )
    credential_scope = f"{short_date}/{region}/{service}/request"
    string_to_sign = "\n".join(
        [
            "HMAC-SHA256",
            x_date,
            credential_scope,
            sha256(canonical_request.encode("utf-8")).hexdigest(),
        ]
    )

    k_date = _hmac_sha256(secret_key.encode("utf-8"), short_date)
    k_region = _hmac_sha256(k_date, region)
    k_service = _hmac_sha256(k_region, service)
    k_signing = _hmac_sha256(k_service, "request")
    signature = hmac_new(k_signing, string_to_sign.encode("utf-8"), sha256).hexdigest()

    authorization = (
        f"HMAC-SHA256 Credential={access_key}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )
    return {
        "Content-Type": "application/json; charset=utf-8",
        "Host": host,
        "X-Date": x_date,
        "X-Content-Sha256": body_hash,
        "Authorization": authorization,
    }


async def fetch_ark_inference_usage(
    *,
    start_time: str,
    end_time: str,
    query_interval: str = "Day",
    filters: list[dict[str, Any]] | None = None,
    show_window_detail: bool = False,
    access_key: str | None = None,
    secret_key: str | None = None,
    region: str | None = None,
) -> dict[str, Any]:
    """调用火山方舟 `GetInferenceUsage` 查询推理用量（需要 AK/SK）。"""
    ak = (access_key or settings.ark_access_key).strip()
    sk = (secret_key or settings.ark_secret_key).strip()
    if not ak or not sk:
        raise ValueError("未配置火山方舟 AK/SK（ARK_ACCESS_KEY / ARK_SECRET_KEY）")

    reg = (region or settings.ark_region or "cn-beijing").strip()
    host = f"ark.{reg}.volcengineapi.com"
    query = "Action=GetInferenceUsage&Version=2024-01-01"
    url = f"https://{host}/?{query}"

    payload: dict[str, Any] = {
        "QueryInterval": query_interval,
        "StartTime": start_time,
        "EndTime": end_time,
        "ShowWindowDetail": show_window_detail,
    }
    if filters:
        payload["Filters"] = filters
    body = json_dumps(payload, separators=(",", ":")).encode("utf-8")

    headers = build_volcengine_v4_headers(
        access_key=ak,
        secret_key=sk,
        region=reg,
        service="ark",
        host=host,
        method="POST",
        path="/",
        query=query,
        body=body,
    )
    async with AsyncClient(timeout=settings.video_provider_timeout, trust_env=False) as client:
        resp = await client.post(url, content=body, headers=headers)
        resp.raise_for_status()
        return resp.json()


async def backfill_ark_video_usage(session: AsyncSession) -> dict[str, int]:
    """为历史已成功的 `ark_seedance_v1` 视频任务补齐 Token 消耗记录。"""
    jobs = (
        await session.exec(
            select(VideoJob)
            .outerjoin(
                LLMUsageRecord,
                and_(
                    col(LLMUsageRecord.operation) == "video_generation",
                    col(LLMUsageRecord.provider_request_id) == col(VideoJob.provider_task_id),
                ),
            )
            .where(
                col(VideoJob.status) == VideoJobStatus.SUCCEEDED.value,
                col(VideoJob.protocol_code) == "ark_seedance_v1",
                col(VideoJob.provider_task_id).is_not(None),
                col(LLMUsageRecord.id).is_(None),
            )
        )
    ).all()

    service = VideoJobService(session)
    provider = get_video_provider("ark_seedance_v1")
    recorded = 0
    skipped = 0
    failed = 0

    for job in jobs:
        if not job.provider_task_id:
            skipped += 1
            continue
        try:
            if job.api_config_id is None:
                if not settings.video_platform_api_key:
                    skipped += 1
                    continue
                ctx = service._platform_ctx(job)
            else:
                revision = (
                    await session.exec(
                        select(VideoApiConfigRevision).where(
                            VideoApiConfigRevision.id == job.api_config_revision_id
                        )
                    )
                ).first()
                if revision is None:
                    skipped += 1
                    continue
                ctx = service._ctx(revision)

            task_status = await provider.poll(job.provider_task_id, ctx)
            if task_status.input_tokens is None and task_status.output_tokens is None:
                skipped += 1
                continue
            item = await record_token_usage(
                session,
                operation="video_generation",
                input_tokens=task_status.input_tokens,
                output_tokens=task_status.output_tokens,
                user_id=job.user_id,
                conversation_id=job.conversation_id,
                provider_code=job.protocol_code,
                model_name=job.remote_model_id,
                provider_request_id=job.provider_task_id,
                created_at=job.completed_at or job.created_at,
                dedupe_by_request_id=True,
            )
            if item is not None:
                recorded += 1
            else:
                skipped += 1
        except Exception as exc:
            logger.warning("回填视频任务 %s Token 失败: %s", job.id, type(exc).__name__)
            failed += 1

    return {"total": len(jobs), "recorded": recorded, "skipped": skipped, "failed": failed}
