"""测试视频/图片生成 Token 消耗解析、落库去重、历史回填与方舟 GetInferenceUsage 签名请求。"""

from datetime import UTC, datetime

import httpx
import respx
from app.core.enums import UserStatus, VideoJobStatus
from app.db.models.site_traffic import LLMUsageRecord
from app.db.models.user import User
from app.db.models.video_job import VideoJob
from app.providers.image.ark_plan import generate_image
from app.providers.video.ark_seedance_v1 import ArkSeedanceProvider
from app.providers.video.base import AdapterContext
from app.services.ark_usage_service import (
    backfill_ark_video_usage,
    build_volcengine_v4_headers,
    fetch_ark_inference_usage,
    sync_ark_inference_usage_to_records,
)
from app.services.video_job_service import VideoJobService
from pytest import mark
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

ARK_BASE = "https://ark.cn-beijing.volces.com"


@mark.asyncio
async def test_ark_seedance_poll_parses_usage(monkeypatch):
    monkeypatch.setattr("app.providers.video.base.check_base_url", lambda url: None)
    provider = ArkSeedanceProvider()
    ctx = AdapterContext(
        base_url=ARK_BASE,
        auth={"api_key": "test-key"},
        options={},
        remote_model_id="doubao-seedance-1-0-pro-250528",
    )
    with respx.mock(assert_all_called=True) as mock:
        mock.get(f"{ARK_BASE}/api/v3/contents/generations/tasks/cgt-123").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "cgt-123",
                    "status": "succeeded",
                    "content": {"video_url": "https://cdn.example.com/out.mp4"},
                    "usage": {"completion_tokens": 35800, "total_tokens": 35800},
                },
            )
        )
        status = await provider.poll("cgt-123", ctx)

    assert status.raw_status == "succeeded"
    assert status.input_tokens == 0
    assert status.output_tokens == 35800
    assert status.total_tokens == 35800


@mark.asyncio
async def test_video_job_refresh_records_and_dedupes_tokens_in_summary(
    client, db_engine, monkeypatch
):
    monkeypatch.setattr("app.providers.video.base.check_base_url", lambda url: None)
    monkeypatch.setattr("app.core.config.settings.video_provider", "ark_seedance_v1")
    monkeypatch.setattr("app.core.config.settings.video_platform_api_key", "test-platform-key")
    monkeypatch.setattr("app.core.config.settings.video_platform_base_url", ARK_BASE)

    async def _noop_download(self, job):
        return None

    monkeypatch.setattr(VideoJobService, "_trigger_download", _noop_download)

    async with AsyncSession(db_engine) as session:
        user = User(
            id="usr_vid_1",
            email="vid@example.com",
            password_hash="hash",
            status=UserStatus.ACTIVE.value,
        )
        job = VideoJob(
            id="vjob_usage_1",
            user_id=user.id,
            conversation_id="conv_vid_1",
            project_id="proj_vid_1",
            project_version_id="pver_vid_1",
            project_version=1,
            api_config_id=None,
            api_config_revision_id=None,
            idempotency_key="idem_vid_1",
            request_fingerprint="fp_vid_1",
            protocol_code="ark_seedance_v1",
            remote_model_id="doubao-seedance-1-0-pro-250528",
            mode="text_to_video",
            status=VideoJobStatus.RUNNING.value,
            provider_task_id="cgt-usage-1",
        )
        session.add_all([user, job])
        await session.commit()
        await session.refresh(job)

        service = VideoJobService(session)
        with respx.mock(assert_all_called=True) as mock:
            route = mock.get(f"{ARK_BASE}/api/v3/contents/generations/tasks/cgt-usage-1").mock(
                return_value=httpx.Response(
                    200,
                    json={
                        "id": "cgt-usage-1",
                        "status": "succeeded",
                        "usage": {"completion_tokens": 125000, "total_tokens": 125000},
                    },
                )
            )
            await service._refresh(job)
            # 再次刷新同一个任务，不应重复记账
            await service._refresh(job)
            assert route.call_count == 2

        rows = (
            await session.exec(
                select(LLMUsageRecord).where(
                    col(LLMUsageRecord.provider_request_id) == "cgt-usage-1"
                )
            )
        ).all()
        assert len(rows) == 1
        assert rows[0].operation == "video_generation"
        assert rows[0].input_tokens == 0
        assert rows[0].output_tokens == 125000

    resp = await client.get("/api/v1/site-traffic/summary")
    assert resp.status_code == 200
    assert resp.json()["total_tokens"] == 125000


@mark.asyncio
async def test_ark_image_parses_usage():
    with respx.mock(assert_all_called=True) as mock:
        mock.post("https://ark.cn-beijing.volces.com/api/v3/images/generations").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": [{"url": "https://cdn.example.com/img.png"}],
                    "usage": {"output_tokens": 4096, "total_tokens": 4096},
                },
                headers={"x-request-id": "req-img-1"},
            )
        )
        res = await generate_image(
            api_key="test-key",
            model="doubao-seedream-5-0-pro-260628",
            prompt="a cat",
            size="1536x1536",
        )
    assert res.request_id == "req-img-1"
    assert res.input_tokens == 0
    assert res.output_tokens == 4096
    assert res.total_tokens == 4096


@mark.asyncio
async def test_backfill_ark_video_usage(db_engine, monkeypatch):
    monkeypatch.setattr("app.providers.video.base.check_base_url", lambda url: None)
    monkeypatch.setattr("app.core.config.settings.video_provider", "ark_seedance_v1")
    monkeypatch.setattr("app.core.config.settings.video_platform_api_key", "test-platform-key")
    monkeypatch.setattr("app.core.config.settings.video_platform_base_url", ARK_BASE)

    async with AsyncSession(db_engine) as session:
        user = User(
            id="usr_bf_1",
            email="bf@example.com",
            password_hash="hash",
            status=UserStatus.ACTIVE.value,
        )
        j1 = VideoJob(
            id="vjob_bf_1",
            user_id=user.id,
            conversation_id="conv_bf_1",
            project_id="proj_bf_1",
            project_version_id="pver_bf_1",
            project_version=1,
            api_config_id=None,
            api_config_revision_id=None,
            idempotency_key="idem_bf_1",
            request_fingerprint="fp_bf_1",
            protocol_code="ark_seedance_v1",
            remote_model_id="doubao-seedance-1-0-pro-250528",
            mode="text_to_video",
            status=VideoJobStatus.SUCCEEDED.value,
            provider_task_id="cgt-bf-1",
        )
        j2 = VideoJob(
            id="vjob_bf_2",
            user_id=user.id,
            conversation_id="conv_bf_1",
            project_id="proj_bf_1",
            project_version_id="pver_bf_1",
            project_version=1,
            api_config_id=None,
            api_config_revision_id=None,
            idempotency_key="idem_bf_2",
            request_fingerprint="fp_bf_2",
            protocol_code="ark_seedance_v1",
            remote_model_id="doubao-seedance-1-0-pro-250528",
            mode="text_to_video",
            status=VideoJobStatus.SUCCEEDED.value,
            provider_task_id="cgt-bf-2",
        )
        existing = LLMUsageRecord(
            user_id=user.id,
            conversation_id="conv_bf_1",
            operation="video_generation",
            provider_code="ark_seedance_v1",
            model_name="doubao-seedance-1-0-pro-250528",
            provider_request_id="cgt-bf-2",
            input_tokens=0,
            output_tokens=50000,
        )
        session.add_all([user, j1, j2, existing])
        await session.commit()

        with respx.mock(assert_all_called=False) as mock:
            route = mock.get(f"{ARK_BASE}/api/v3/contents/generations/tasks/cgt-bf-1").mock(
                return_value=httpx.Response(
                    200,
                    json={
                        "id": "cgt-bf-1",
                        "status": "succeeded",
                        "usage": {"completion_tokens": 88000, "total_tokens": 88000},
                    },
                )
            )
            stats = await backfill_ark_video_usage(session)
            assert stats == {"total": 1, "recorded": 1, "skipped": 0, "failed": 0}
            assert route.called


@mark.asyncio
async def test_get_inference_usage_signing_and_request():
    headers = build_volcengine_v4_headers(
        access_key="ak_test",
        secret_key="sk_test",
        region="cn-beijing",
        service="ark",
        host="ark.cn-beijing.volcengineapi.com",
        method="POST",
        path="/",
        query="Action=GetInferenceUsage&Version=2024-01-01",
        body=b'{"QueryInterval":"Day"}',
        now_utc=datetime(2026, 11, 15, 5, 0, 0, tzinfo=UTC),
    )
    assert headers["X-Date"] == "20261115T050000Z"
    assert headers["Authorization"].startswith(
        "HMAC-SHA256 Credential=ak_test/20261115/cn-beijing/ark/request, "
        "SignedHeaders=content-type;host;x-content-sha256;x-date, Signature="
    )

    with respx.mock(assert_all_called=True) as mock:
        mock.post(
            "https://ark.cn-beijing.volcengineapi.com/?Action=GetInferenceUsage&Version=2024-01-01"
        ).mock(return_value=httpx.Response(200, json={"Result": {"TotalTokens": 2254947}}))
        res = await fetch_ark_inference_usage(
            start_time="2026-11-01",
            end_time="2026-11-15",
            access_key="ak_test",
            secret_key="sk_test",
        )
    assert res["Result"]["TotalTokens"] == 2254947


@mark.asyncio
async def test_sync_ark_inference_usage_to_records(db_engine, monkeypatch):
    monkeypatch.setattr("app.core.config.settings.ark_access_key", "ak_test")
    monkeypatch.setattr("app.core.config.settings.ark_secret_key", "sk_test")

    async with AsyncSession(db_engine) as session:
        # 预先写入一条 2026-11-15 的单任务记账（模拟 backfill 已录入 100000）
        session.add(
            LLMUsageRecord(
                operation="video_generation",
                provider_code="ark_seedance_v1",
                provider_request_id="cgt-existing-1",
                input_tokens=0,
                output_tokens=100000,
                created_at=datetime(2026, 11, 15, 10, 0, 0),
            )
        )
        await session.commit()

        with respx.mock(assert_all_called=True) as mock:
            mock.post(
                "https://ark.cn-beijing.volcengineapi.com/?Action=GetInferenceUsage&Version=2024-01-01"
            ).mock(
                return_value=httpx.Response(
                    200,
                    json={
                        "Result": {
                            "Fields": [
                                {"Name": "Day", "Type": "DATE"},
                                {"Name": "InputTokens", "Type": "BIGINT"},
                                {"Name": "OutputTokens", "Type": "BIGINT"},
                                {"Name": "TotalTokens", "Type": "BIGINT"},
                            ],
                            "Data": [
                                ["2026-11-13", "0", "324900", "324900"],
                                ["2026-11-15", "0", "324900", "324900"],
                            ],
                        }
                    },
                )
            )
            stats = await sync_ark_inference_usage_to_records(
                session, start_time="2026-11-13", end_time="2026-11-15"
            )

        assert stats == {"days": 2, "recorded": 2, "tokens_added": 549800}
