import asyncio
import io
import uuid
from dataclasses import replace

import pytest
from app.providers.video.ark_seedance_v1 import _build_body
from app.providers.video.fake import FakeVideoProvider
from app.video_registry import registry
from PIL import Image

from test_canvas import ControlledProvider, create_project, preparation, reviewed_options


async def save(client, cid, headers, project, document):
    result = await client.put(
        f"/api/v1/conversations/{cid}/canvas",
        json={"canvas_data": document, "expected_canvas_version": project["canvas_version"]},
        headers=headers,
    )
    assert result.status_code == 200, result.text
    return result.json()


async def prepare(client, cid, headers, project, **kwargs):
    result = await client.post(
        f"/api/v1/conversations/{cid}/canvas/prepare-video",
        json={**preparation(["target"], project["canvas_version"]), **kwargs},
        headers=headers,
    )
    assert result.status_code == 200, result.text
    return result.json()


async def confirm(client, cid, headers, project):
    return await client.post(
        f"/api/v1/conversations/{cid}/project/confirm",
        json={"spec_version": project["current_spec_version"]},
        headers=headers,
    )


async def submit(client, cid, headers, project, **kwargs):
    return await client.post(
        "/api/v1/video-jobs",
        headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
        json={
            "conversation_id": cid,
            "project_id": project["id"],
            "spec_version": project["current_spec_version"],
            "api_config_id": project["canvas_data"]["selected_api_config_id"],
            "mode": project["current_spec"]["mode"],
            "generation_options": reviewed_options(project),
            **kwargs,
        },
    )


async def config(client, headers, model="doubao-seedance-2-5", protocol="ark_seedance_v1"):
    profile = registry.get_profile(protocol, model)
    result = await client.post(
        "/api/v1/video-api-configs",
        headers=headers,
        json={
            "display_name": "自配模型",
            "source_type": "official",
            "protocol_code": protocol,
            "remote_model_id": profile.remote_model_id,
            "capability_profile_code": profile.code,
            "auth": {"api_key": "test-key"},
        },
    )
    assert result.status_code == 201, result.text
    assert result.json()["capability_profile_code"] == model
    return result.json()


@pytest.mark.parametrize("mode", ["first_frame_to_video", "first_last_frame_to_video"])
async def test_image_review_persists_adaptive_plan_and_real_ark_body_has_no_ratio(
    client, monkeypatch, mode
):
    cid, headers, document = await create_project(client)
    data = io.BytesIO()
    Image.new("RGB", (16, 9), "blue").save(data, format="PNG")
    count = 1 if mode == "first_frame_to_video" else 2
    for i in range(count):
        uploaded = await client.post(
            "/api/v1/assets",
            headers=headers,
            files={"file": (f"image{i}.png", data.getvalue(), "image/png")},
            data={"purpose": "reference"},
        )
        assert uploaded.status_code == 201, uploaded.text
        document["nodes"].append(
            {
                "id": f"image{i}",
                "type": "image",
                "title": f"图{i}",
                "x": 0,
                "y": 0,
                "asset_id": uploaded.json()["id"],
            }
        )
        document["connections"].append({"id": f"link{i}", "from": "target", "to": f"image{i}"})
    document["nodes"][0]["content"] = "16:9，一艘小船经过石桥。"
    project = (await client.get(f"/api/v1/conversations/{cid}/project")).json()
    project = await save(client, cid, headers, project, document)
    provider = ControlledProvider()
    monkeypatch.setattr("app.services.agent_service.get_text_provider", lambda: provider)
    project = await prepare(client, cid, headers, project, mode=mode, duration_seconds=7)
    canvas = project["canvas_data"]
    assert canvas["generation_review"]["status"] == "ready"
    assert canvas["video_duration_seconds"] == 7
    assert canvas["generation_settings"]["duration_seconds"] == 7
    assert project["current_spec"]["aspect_ratio"] == "adaptive"
    assert "16:9" not in project["compiled_prompt"]
    assert "随素材自适应" in canvas["generation_review"]["content"]
    assert "等比放大" in canvas["generation_review"]["content"]
    assert canvas["nodes"] == document["nodes"]
    reopened = (await client.get(f"/api/v1/conversations/{cid}/project")).json()
    assert reopened["canvas_data"]["generation_review"] == canvas["generation_review"]
    assert (await confirm(client, cid, headers, project)).status_code == 200
    requests = []

    class Capture(FakeVideoProvider):
        async def submit(self, request, ctx):
            requests.append(request)
            return await super().submit(request, ctx)

    monkeypatch.setattr(
        "app.services.video_job_service.get_video_provider", lambda *args: Capture()
    )
    result = await submit(client, cid, headers, project)
    assert result.status_code == 202, result.text
    assert requests[0]["prompt"] == project["compiled_prompt"]
    body = _build_body(requests[0])
    assert "ratio" not in body
    assert body["duration"] == 7 and body["resolution"] == "1080p"
    assert len(body["content"]) == count + 1


@pytest.mark.parametrize("change", ["channel", "mode", "roles", "rules", "options"])
async def test_changed_binding_cannot_submit_the_old_review(client, monkeypatch, change):
    cid, headers, _ = await create_project(client)
    monkeypatch.setattr(
        "app.services.agent_service.get_text_provider", lambda: ControlledProvider()
    )
    current = (await client.get(f"/api/v1/conversations/{cid}/project")).json()
    project = await prepare(client, cid, headers, current)
    assert (await confirm(client, cid, headers, project)).status_code == 200
    if change == "rules":
        key = ("ark_seedance_v1", "doubao-seedance-2-5")
        monkeypatch.setitem(
            registry._PROFILES,
            key,
            replace(registry._PROFILES[key], version=registry._PROFILES[key].version + 1),
        )
    elif change == "options":
        options = reviewed_options(project)
        options["aspect_ratio"] = "9:16"
        result = await submit(client, cid, headers, project, generation_options=options)
        assert result.status_code == 422, result.text
        return
    else:
        canvas = project["canvas_data"]
        if change == "channel":
            canvas["selected_api_config_id"] = "unreviewed-channel"
        elif change == "mode":
            canvas["video_mode"] = "first_frame_to_video"
        else:
            canvas["video_input_roles"] = {"first_frame_node_id": "different"}
        project = await save(client, cid, headers, project, canvas)
    result = await submit(client, cid, headers, project)
    assert result.status_code == 409, result.text
    assert result.json()["error"]["code"] == "PROJECT_NOT_CONFIRMED"


async def test_client_canvas_cannot_replace_review_content_or_parameters(client, monkeypatch):
    cid, headers, _ = await create_project(client)
    monkeypatch.setattr(
        "app.services.agent_service.get_text_provider", lambda: ControlledProvider()
    )
    project = await prepare(
        client, cid, headers, (await client.get(f"/api/v1/conversations/{cid}/project")).json()
    )
    content = project["canvas_data"]["generation_review"]["content"]
    canvas = project["canvas_data"]
    canvas["generation_review"]["content"] = "伪造的最终方案"
    canvas["generation_settings"]["duration_seconds"] = 15
    saved = await save(client, cid, headers, project, canvas)
    assert saved["canvas_data"]["generation_review"]["content"] == content
    assert saved["canvas_data"]["generation_settings"]["duration_seconds"] == 8


@pytest.mark.parametrize("kind", ["missing_image", "unknown_model", "unsupported_mode"])
async def test_unresolvable_review_is_persisted_without_calling_ai_or_claiming_ready(
    client, monkeypatch, kind
):
    from app.core.config import settings

    cid, headers, _ = await create_project(client)
    provider = ControlledProvider()
    monkeypatch.setattr("app.services.agent_service.get_text_provider", lambda: provider)
    if kind == "unknown_model":
        monkeypatch.setattr(settings, "video_platform_model", "unregistered-model")
        monkeypatch.setattr(settings, "video_platform_profile_code", "")
    mode = (
        "first_frame_to_video"
        if kind == "missing_image"
        else "video_extend"
        if kind == "unsupported_mode"
        else "auto"
    )
    project = await prepare(
        client,
        cid,
        headers,
        (await client.get(f"/api/v1/conversations/{cid}/project")).json(),
        mode=mode,
    )
    assert project["canvas_data"]["generation_review"]["status"] == "blocked"
    assert "如果不再修改" not in project["canvas_data"]["generation_review"]["content"]
    assert provider.calls == []
    assert (await confirm(client, cid, headers, project)).status_code == 409
    assert (await submit(client, cid, headers, project)).status_code == 409


async def test_config_revision_change_during_llm_call_does_not_publish_stale_review(
    client, monkeypatch
):
    cid, headers, _ = await create_project(client)
    cfg = await config(client, headers)
    provider = ControlledProvider(blocked=True)
    monkeypatch.setattr("app.services.agent_service.get_text_provider", lambda: provider)
    work = asyncio.create_task(
        client.post(
            f"/api/v1/conversations/{cid}/canvas/prepare-video",
            json={**preparation(["target"]), "api_config_id": cfg["id"]},
            headers=headers,
        )
    )
    await asyncio.wait_for(provider.started.wait(), 5)
    changed = await client.patch(
        f"/api/v1/video-api-configs/{cfg['id']}",
        headers=headers,
        json={"expected_version": cfg["version"], "auth": {"api_key": "rotated-test-key"}},
    )
    assert changed.status_code == 200, changed.text
    provider.release.set()
    result = await asyncio.wait_for(work, 5)
    assert result.status_code == 409, result.text
    assert (await client.get(f"/api/v1/conversations/{cid}/project")).json()[
        "current_spec_version"
    ] == 0


async def test_different_protocol_dispatches_submit_poll_and_download_by_job_identity(
    client, monkeypatch
):
    from app.core.config import settings
    from app.providers.video import get_video_provider
    from app.providers.video.dashscope_async_v1 import DashScopeAsyncV1Provider

    cid, headers, _ = await create_project(client)
    cfg = await config(client, headers, "wan2.5-t2v-preview", "dashscope_async_v1")
    monkeypatch.setattr(
        "app.services.agent_service.get_text_provider", lambda: ControlledProvider()
    )
    project = await prepare(
        client,
        cid,
        headers,
        (await client.get(f"/api/v1/conversations/{cid}/project")).json(),
        api_config_id=cfg["id"],
    )
    assert project["canvas_data"]["generation_settings"]["duration_seconds"] == 10
    assert project["canvas_data"]["generation_settings"]["generate_audio"] is False
    seen = []

    class Capture(FakeVideoProvider):
        async def submit(self, request, ctx):
            assert "generate_audio" not in request
            return await super().submit(request, ctx)

    provider = Capture()

    def factory(protocol):
        seen.append(protocol)
        return provider

    monkeypatch.setattr("app.services.video_job_service.get_video_provider", factory)
    monkeypatch.setattr("app.services.video_download_service.get_video_provider", factory)
    assert (await confirm(client, cid, headers, project)).status_code == 200
    created = await submit(client, cid, headers, project)
    assert created.status_code == 202, created.text
    for _ in range(6):
        result = (await client.get(f"/api/v1/video-jobs/{created.json()['id']}")).json()
        if result["download_status"] == "stored":
            break
    assert result["download_status"] == "stored"
    assert len(seen) >= 3 and set(seen) == {"dashscope_async_v1"}
    monkeypatch.setattr(settings, "video_provider", "ark_seedance_v1")
    assert isinstance(get_video_provider("dashscope_async_v1"), DashScopeAsyncV1Provider)


async def test_conflicting_ai_technical_text_cannot_leak_into_the_compiled_prompt(
    client, monkeypatch
):
    cid, headers, _ = await create_project(client)

    class OldPrompt(ControlledProvider):
        async def generate(self, messages, *, structured=False):
            result = await super().generate(messages, structured=structured)
            result.structured["state_patch"]["camera"] = "9:16画幅，清晰度1080p，固定镜头"
            result.structured["state_patch"]["duration_seconds"] = 20
            result.structured["suggested_prompt"] = "9:16，1080p，总时长20秒，完全不同的自由提示词"
            result.structured["suggestions"] = ["你还需要修改吗？"]
            return result

    monkeypatch.setattr("app.services.agent_service.get_text_provider", lambda: OldPrompt())
    project = await prepare(
        client,
        cid,
        headers,
        (await client.get(f"/api/v1/conversations/{cid}/project")).json(),
        resolution="720p",
    )
    prompt = project["compiled_prompt"]
    assert "9:16" not in prompt and "1080p" not in prompt and "20秒" not in prompt
    assert "（秒）：20" not in prompt
    assert "16:9" in prompt and "720p" in prompt
    assert "自由提示词" not in prompt
    assert "？" not in project["canvas_data"]["generation_review"]["content"]


async def test_ai_time_line_beyond_effective_duration_gets_one_internal_repair_then_blocks(
    client, monkeypatch
):
    cid, headers, _ = await create_project(client)

    class TooLong(ControlledProvider):
        async def generate(self, messages, *, structured=False):
            result = await super().generate(messages, structured=structured)
            result.structured["state_patch"]["motion"] = "0-30秒，主体持续奔跑"
            return result

    provider = TooLong()
    monkeypatch.setattr("app.services.agent_service.get_text_provider", lambda: provider)
    project = await prepare(
        client, cid, headers, (await client.get(f"/api/v1/conversations/{cid}/project")).json()
    )
    assert len(provider.calls) == 2
    assert project["canvas_data"]["generation_review"]["status"] == "blocked"
    assert "时间线" in project["canvas_data"]["generation_review"]["content"]
    assert (await confirm(client, cid, headers, project)).status_code == 409
