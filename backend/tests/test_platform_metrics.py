"""测试平台首页统计大盘指标端到端正确性。"""

from datetime import datetime, timedelta

from app.core.enums import AgentRunStatus, UserStatus
from app.db.models.agent import AgentRun
from app.db.models.asset import Asset
from app.db.models.image_generation import ImageJob
from app.db.models.material_library import MaterialLibraryItem
from app.db.models.site_traffic import SiteTrafficTotal
from app.db.models.user import User
from app.db.models.video_job import VideoJob
from pytest import mark
from sqlmodel.ext.asyncio.session import AsyncSession

SUMMARY_URL = "/api/v1/site-traffic/summary"


@mark.asyncio
async def test_platform_metrics_aggregation(client, db_engine):
    # 1. 准备测试数据
    now_dt = datetime.now()
    async with AsyncSession(db_engine) as session:
        # 写入访问量
        total = SiteTrafficTotal(
            id=1, total_visits=128, started_at=now_dt - timedelta(days=20), updated_at=now_dt
        )
        session.add(total)

        # 写入正常用户
        u1 = User(
            id="usr_01",
            email="test1@example.com",
            password_hash="hash1",
            status=UserStatus.ACTIVE.value,
        )
        u2 = User(
            id="usr_02",
            email="test2@example.com",
            password_hash="hash2",
            status=UserStatus.ACTIVE.value,
        )
        u3 = User(
            id="usr_03",
            email="deleted@example.com",
            password_hash="hash3",
            status=UserStatus.DISABLED.value,
        )
        session.add_all([u1, u2, u3])
        await session.flush()

        # 写入 AgentRuns（产生 Token 消耗及 14 天趋势）
        run1 = AgentRun(
            user_id=u1.id,
            conversation_id="conv_01",
            user_message_id="msg_01",
            status=AgentRunStatus.SUCCEEDED.value,
            input_tokens=150,
            output_tokens=350,
            created_at=now_dt - timedelta(days=2),
        )
        run2 = AgentRun(
            user_id=u2.id,
            conversation_id="conv_02",
            user_message_id="msg_02",
            status=AgentRunStatus.SUCCEEDED.value,
            input_tokens=200,
            output_tokens=800,
            created_at=now_dt - timedelta(days=1),
        )
        run_old = AgentRun(
            user_id=u1.id,
            conversation_id="conv_03",
            user_message_id="msg_03",
            status=AgentRunStatus.SUCCEEDED.value,
            input_tokens=500,
            output_tokens=500,
            created_at=now_dt - timedelta(days=30),  # 超过 14 天
        )
        session.add_all([run1, run2, run_old])

        # 写入创作任务
        v1 = VideoJob(
            id="vjob_01",
            user_id=u1.id,
            conversation_id="conv_01",
            project_id="proj_01",
            project_version_id="pver_01",
            project_version=1,
            api_config_id="cfg_01",
            api_config_revision_id="crev_01",
            idempotency_key="v_idem_01",
            request_fingerprint="v_fp_01",
            protocol_code="generic_async_json_v1",
            remote_model_id="test-model",
            mode="text_to_video",
            prompt="test prompt",
            status="succeeded",
        )
        img1 = ImageJob(
            id="ijob_01",
            user_id=u1.id,
            conversation_id="conv_01",
            api_config_id="cfg_01",
            config_revision=1,
            channel_label="default",
            model="doubao-seededit",
            prompt="test img",
            aspect_ratio="1:1",
            size="1024x1024",
            idempotency_key="idem_01",
            request_fingerprint="fp_01",
            encrypted_api_key="enc_key",
            status="succeeded",
        )
        session.add_all([v1, img1])

        # 写入资产
        asset1 = Asset(
            id="ast_01",
            user_id=u1.id,
            kind="video",
            purpose="source_video",
            mime_type="video/mp4",
            storage_provider="local",
            storage_key="videos/v1.mp4",
            size_bytes=1024,
            sha256="hash_01",
            status="ready",
        )
        asset2 = Asset(
            id="ast_02",
            user_id=u1.id,
            kind="video",
            purpose="source_video",
            mime_type="video/mp4",
            storage_provider="local",
            storage_key="videos/v2.mp4",
            size_bytes=2048,
            sha256="hash_02",
            status="ready",
        )
        session.add_all([asset1, asset2])

        # 写入发布作品
        mat1 = MaterialLibraryItem(
            id="mat_01",
            title="TV Sample 1",
            description="desc",
            model_name="wan2.2",
            video_asset_id="ast_01",
            status="published",
        )
        mat2 = MaterialLibraryItem(
            id="mat_02",
            title="Draft Sample",
            description="desc",
            model_name="wan2.2",
            video_asset_id="ast_02",
            status="draft",
        )
        session.add_all([mat1, mat2])

        await session.commit()

    # 2. 调用公开 summary 接口验证统计结果
    response = await client.get(SUMMARY_URL)
    assert response.status_code == 200
    data = response.json()

    # 累计访问量
    assert data["total_visits"] == 128
    # 累计 Token 消耗 (150+350 + 200+800 + 500+500 = 2500)
    assert data["total_tokens"] == 2500
    # 总创作次数 (1 video + 1 image = 2)
    assert data["total_creations"] == 2
    assert data["creations_breakdown"]["videos"] == 1
    assert data["creations_breakdown"]["images"] == 1
    # 正常用户总量 (u1, u2 两个 active)
    assert data["total_users"] == 2
    # 发布作品量 (只有 1 个 published)
    assert data["published_works"] == 1
    # 素材资产数 (2 个 ready)
    assert data["total_assets"] == 2
    # 模型及模板数 (>= 1)
    assert data["models_and_templates_count"] >= 1

    # 14 天序列检验
    daily = data["daily_tokens_14d"]
    assert len(daily) == 14
    total_14d_tokens = sum(item["tokens"] for item in daily)
    # 14 天内有 run1 (500) + run2 (1000) = 1500，30 天前的 run_old (1000) 不在 14 天内
    assert total_14d_tokens == 1500
