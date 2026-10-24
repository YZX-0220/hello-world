"""Canvas durability, optimistic concurrency, and node-scoped collaboration regressions."""

import asyncio
import copy
import uuid

import httpx
import pytest
from app.providers.email.fake import fake_instance
from app.providers.text.base import TextProviderError, TextResult
from app.providers.text.fake import FakeTextProvider


async def create_project(client: httpx.AsyncClient):
    email = "canvas-tests@example.com"
    await client.post("/api/v1/auth/email-codes", json={"email": email, "purpose": "register"})
    registered = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "code": fake_instance.sent[-1]["code"],
            "password": "CanvasTest123!",
        },
    )
    assert registered.status_code == 201
    headers = {"X-CSRF-Token": client.cookies.get("hw_csrf", ""), "Origin": "http://127.0.0.1:5173"}
    created = await client.post(
        "/api/v1/conversations", json={"title": "画布回归"}, headers=headers
    )
    cid = created.json()["conversation"]["id"]
    document = {
        "schema_version": 1,
        "nodes": [
            {
                "id": "target",
                "type": "text",
                "title": "脚本",
                "x": -120,
                "y": 240,
                "content": "原有脚本",
            },
            {
                "id": "other",
                "type": "text",
                "title": "参考",
                "x": 500,
                "y": 200,
                "content": "参考素材",
            },
        ],
        "connections": [{"id": "connection", "from": "other", "to": "target"}],
        "pan": {"x": -40, "y": 220},
        "zoom": 1.5,
        "agent_draft": "未发送的输入",
        "ai_target_node_id": "target",
        "referenced_node_ids": ["other"],
        "selected_api_config_id": "platform",
        "dismissed_job_ids": [],
        "generation_node_id": "",
    }
    saved = await client.put(
        f"/api/v1/conversations/{cid}/canvas",
        json={"canvas_data": document, "expected_canvas_version": 0},
        headers=headers,
    )
    assert saved.status_code == 200
    return cid, headers, saved.json()["canvas_data"]


def collaboration(target="target", request_id=None, apply_mode="replace"):
    return {
        "content": "改写为专业镜头脚本",
        "client_request_id": request_id or str(uuid.uuid4()),
        "canvas_collaboration": {
            "target_node_id": target,
            "reference_node_ids": ["other"],
            "apply_mode": apply_mode,
        },
    }


def preparation(node_ids, version=1, duration=8, resolution="1080p"):
    return {"node_ids": node_ids, "expected_canvas_version": version,
            "duration_seconds": duration, "resolution": resolution}


def reviewed_options(project, ids=None):
    data = project["canvas_data"]
    return {**data["generation_settings"], "review_fingerprint": data["generation_review"]["fingerprint"],
            "canvas_source_node_ids": ids or data["generation_source_ids"]}


class ControlledProvider(FakeTextProvider):
    def __init__(self, blocked=False, failing=False):
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.blocked = blocked
        self.failing = failing
        self.calls = []

    async def generate(self, messages, *, structured=False):
        self.calls.append(messages)
        self.started.set()
        if self.blocked:
            await self.release.wait()
        if self.failing:
            raise TextProviderError("TEXT_PROVIDER_TIMEOUT", "模拟超时", retryable=True)
        return TextResult(
            reply="AI 完整回复",
            structured={"reply": "AI 完整回复", "canvas_content": "AI 完整回复", "state_patch": {
                "subject": "小船", "scene": "古镇石桥", "camera": "镜头缓慢推进",
                "motion": "小船前进", "lighting": "暖色侧光", "visual_style": "写实",
            }, "suggested_prompt": "小船经过古镇石桥，镜头缓慢推进。"},
            model="test",
        )


async def test_discussion_and_write_content_are_separate_and_scoped(client, monkeypatch):
    cid, headers, _ = await create_project(client)

    class DiscussionProvider(ControlledProvider):
        async def generate(self, messages, *, structured=False):
            self.calls.append(messages)
            return TextResult(reply="解释与建议", structured={
                "reply": "解释与建议：雪地中的红狐狸建议采用固定镜头。",
                "canvas_content": "# 红狐狸\n雪地中一只红狐狸缓慢向前走，固定镜头。" if len(self.calls) == 1 else None,
                "state_patch": {},
            }, model="discussion-test")

    provider = DiscussionProvider()
    monkeypatch.setattr("app.services.agent_service.get_text_provider", lambda: provider)
    first = (await client.post(
        f"/api/v1/conversations/{cid}/messages", json=collaboration(), headers=headers,
    )).json()
    candidate = first["project"]["canvas_data"]["nodes"][0]["pending_ai"]
    assert candidate["content"].startswith("# 红狐狸")
    assert "解释与建议" not in candidate["content"]
    body = collaboration()
    body["content"] = "为什么选择固定镜头？仅讨论，不要改写。"
    second = (await client.post(
        f"/api/v1/conversations/{cid}/messages", json=body, headers=headers,
    )).json()
    assert second["assistant_message"]["model_name"] == "discussion-test"
    node = second["project"]["canvas_data"]["nodes"][0]
    assert node["content"] == "原有脚本"
    assert node["pending_ai"] == candidate
    assert "解释与建议：雪地" in provider.calls[1][-1]["content"]
    confirmed = await client.post(
        f"/api/v1/conversations/{cid}/canvas/confirm",
        json={"target_node_id": "target", "message_id": candidate["message_id"],
              "expected_canvas_version": second["project"]["canvas_version"]}, headers=headers,
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["canvas_data"]["nodes"][0]["content"] == candidate["content"]
    body = collaboration(target="other")
    body["canvas_collaboration"]["reference_node_ids"] = []
    await client.post(f"/api/v1/conversations/{cid}/messages", json=body, headers=headers)
    assert "红狐狸" not in provider.calls[-1][-1]["content"]


async def test_canvas_roundtrip_and_empty_canvas(client):
    cid, headers, document = await create_project(client)
    loaded = (await client.get(f"/api/v1/conversations/{cid}/project")).json()
    assert loaded["canvas_data"] == document
    assert loaded["canvas_version"] == 1
    assert loaded["current_spec_version"] == 0
    document["nodes"] = []
    document["connections"] = []
    result = await client.put(
        f"/api/v1/conversations/{cid}/canvas",
        json={"canvas_data": document, "expected_canvas_version": 1},
        headers=headers,
    )
    assert result.status_code == 200
    assert result.json()["canvas_data"]["nodes"] == []


async def test_concurrent_saves_do_not_silently_overwrite(client):
    cid, headers, document = await create_project(client)
    one = copy.deepcopy(document)
    two = copy.deepcopy(document)
    one["nodes"][0]["content"] = "窗口 A"
    two["nodes"][0]["content"] = "窗口 B"
    results = await asyncio.gather(
        *[
            client.put(
                f"/api/v1/conversations/{cid}/canvas",
                json={"canvas_data": value, "expected_canvas_version": 1},
                headers=headers,
            )
            for value in [one, two]
        ]
    )
    assert sorted(response.status_code for response in results) == [200, 409]
    failed = next(response for response in results if response.status_code == 409)
    assert failed.json()["error"]["code"] == "CANVAS_VERSION_CONFLICT"
    loaded = (await client.get(f"/api/v1/conversations/{cid}/project")).json()
    winner = next(response for response in results if response.status_code == 200).json()
    assert loaded["canvas_data"] == winner["canvas_data"]


async def test_ai_stages_without_overwriting_and_passes_reference_context(client, monkeypatch):
    cid, headers, _ = await create_project(client)
    provider = ControlledProvider()
    monkeypatch.setattr("app.services.agent_service.get_text_provider", lambda: provider)
    response = await client.post(
        f"/api/v1/conversations/{cid}/messages", json=collaboration(), headers=headers
    )
    assert response.status_code == 201
    data = response.json()["project"]["canvas_data"]
    assert data["nodes"][0]["content"] == "原有脚本"
    assert data["nodes"][0]["pending_ai"]["content"] == "AI 完整回复"
    assert data["nodes"][0]["pending_ai"]["brief"]["camera"] == "镜头缓慢推进"
    assert response.json()["project"]["current_spec_version"] == 0
    assert data["nodes"][1]["content"] == "参考素材"
    assert data["nodes"][0]["ai_running"] is False
    prompt = provider.calls[0][-1]["content"]
    assert "原有脚本" in prompt and "参考素材" in prompt
    confirmed = await client.post(
        f"/api/v1/conversations/{cid}/canvas/confirm",
        json={"target_node_id": "target", "message_id": data["nodes"][0]["pending_ai"]["message_id"],
              "expected_canvas_version": response.json()["project"]["canvas_version"]}, headers=headers,
    )
    assert confirmed.status_code == 200, confirmed.text
    result = confirmed.json()["canvas_data"]
    assert result["nodes"][0]["content"] == "AI 完整回复"
    assert result["nodes"][1]["content"] == "参考素材"
    assert "pending_ai" not in result["nodes"][1]


@pytest.mark.parametrize("change", ["edit", "delete", "other"])
async def test_ai_completion_respects_edits_and_deletion_during_generation(
    client, monkeypatch, change
):
    cid, headers, _ = await create_project(client)
    provider = ControlledProvider(blocked=True)
    monkeypatch.setattr("app.services.agent_service.get_text_provider", lambda: provider)
    task = asyncio.create_task(
        client.post(f"/api/v1/conversations/{cid}/messages", json=collaboration(), headers=headers)
    )
    await asyncio.wait_for(provider.started.wait(), 3)
    current = (await client.get(f"/api/v1/conversations/{cid}/project")).json()
    assert current["canvas_data"]["nodes"][0]["ai_running"] is True
    document = current["canvas_data"]
    if change == "delete":
        document["nodes"] = document["nodes"][1:]
        document["connections"] = []
    elif change == "edit":
        document["nodes"][0]["content"] = "等待期间的新手动编辑"
    else:
        document["nodes"][1]["content"] = "另一个小框的新文字"
    saved = await client.put(
        f"/api/v1/conversations/{cid}/canvas",
        json={"canvas_data": document, "expected_canvas_version": current["canvas_version"]},
        headers=headers,
    )
    assert saved.status_code == 200
    provider.release.set()
    response = await asyncio.wait_for(task, 3)
    assert response.status_code == 201
    result = (await client.get(f"/api/v1/conversations/{cid}/project")).json()["canvas_data"]
    if change == "delete":
        assert all(node["id"] != "target" for node in result["nodes"])
    elif change == "edit":
        assert result["nodes"][0]["content"] == "等待期间的新手动编辑"
        assert result["nodes"][0]["pending_ai"]["content"] == "AI 完整回复"
    else:
        assert result["nodes"][0]["content"] == "原有脚本"
        assert result["nodes"][0]["pending_ai"]["content"] == "AI 完整回复"
        assert result["nodes"][1]["content"] == "另一个小框的新文字"


async def test_ai_replay_does_not_reapply_reply_over_later_manual_edits(client, monkeypatch):
    cid, headers, _ = await create_project(client)
    provider = ControlledProvider()
    monkeypatch.setattr("app.services.agent_service.get_text_provider", lambda: provider)
    body = collaboration()
    first = await client.post(f"/api/v1/conversations/{cid}/messages", json=body, headers=headers)
    current = first.json()["project"]
    current["canvas_data"]["nodes"][0]["content"] = "回复后的手动编辑"
    await client.put(
        f"/api/v1/conversations/{cid}/canvas",
        json={
            "canvas_data": current["canvas_data"],
            "expected_canvas_version": current["canvas_version"],
        },
        headers=headers,
    )
    replay = await client.post(f"/api/v1/conversations/{cid}/messages", json=body, headers=headers)
    assert replay.status_code == 201
    assert len(provider.calls) == 1
    assert replay.json()["project"]["canvas_data"]["nodes"][0]["content"] == "回复后的手动编辑"
    changed_target = {**body, "canvas_collaboration": {"target_node_id": "other"}}
    invalid = await client.post(
        f"/api/v1/conversations/{cid}/messages", json=changed_target, headers=headers
    )
    assert invalid.status_code == 409


async def test_ai_failure_preserves_text_and_clears_busy_marker(client, monkeypatch):
    cid, headers, _ = await create_project(client)
    provider = ControlledProvider(failing=True)
    monkeypatch.setattr("app.services.agent_service.get_text_provider", lambda: provider)
    response = await client.post(
        f"/api/v1/conversations/{cid}/messages", json=collaboration(), headers=headers
    )
    assert response.status_code == 504
    data = (await client.get(f"/api/v1/conversations/{cid}/project")).json()["canvas_data"]
    assert data["nodes"][0]["content"] == "原有脚本"
    assert data["nodes"][0]["ai_running"] is False
    assert data["nodes"][0]["ai_error"]
    provider.failing = False
    retry = await client.post(
        f"/api/v1/conversations/{cid}/messages", json=collaboration(), headers=headers
    )
    assert retry.status_code == 201


@pytest.mark.parametrize("initial", ["", "用户写了一部分"])
async def test_confirm_is_the_only_operation_that_writes_ai_into_box(client, monkeypatch, initial):
    cid, headers, document = await create_project(client)
    document["nodes"][0]["content"] = initial
    await client.put(
        f"/api/v1/conversations/{cid}/canvas",
        json={"canvas_data": document, "expected_canvas_version": 1}, headers=headers,
    )
    monkeypatch.setattr("app.services.agent_service.get_text_provider", lambda: ControlledProvider())
    generated = await client.post(
        f"/api/v1/conversations/{cid}/messages", json=collaboration(), headers=headers,
    )
    project = generated.json()["project"]
    node = project["canvas_data"]["nodes"][0]
    assert node["content"] == initial
    assert "last_ai" not in node
    refreshed = (await client.get(f"/api/v1/conversations/{cid}/project")).json()
    assert refreshed["canvas_data"]["nodes"][0]["pending_ai"] == node["pending_ai"]
    confirmed = await client.post(
        f"/api/v1/conversations/{cid}/canvas/confirm",
        json={"target_node_id": "target", "message_id": node["pending_ai"]["message_id"],
              "expected_canvas_version": refreshed["canvas_version"]}, headers=headers,
    )
    assert confirmed.status_code == 200, confirmed.text
    node = confirmed.json()["canvas_data"]["nodes"][0]
    assert node["content"] == "AI 完整回复"
    assert node["last_ai"]["before"] == initial
    assert node["last_ai"]["brief"]["camera"] == "镜头缓慢推进"
    assert "pending_ai" not in node
    assert confirmed.json()["current_spec_version"] == 0


async def test_old_candidate_cannot_replace_latest_discussion(client, monkeypatch):
    cid, headers, _ = await create_project(client)
    provider = ControlledProvider()
    monkeypatch.setattr("app.services.agent_service.get_text_provider", lambda: provider)
    first = (await client.post(
        f"/api/v1/conversations/{cid}/messages", json=collaboration(), headers=headers,
    )).json()["project"]
    second = (await client.post(
        f"/api/v1/conversations/{cid}/messages", json=collaboration(), headers=headers,
    )).json()["project"]
    assert "上次讨论的待确认方案" in provider.calls[1][-1]["content"]
    assert any("镜头缓慢推进" in m["content"] for m in provider.calls[1])
    stale = await client.post(
        f"/api/v1/conversations/{cid}/canvas/confirm",
        json={"target_node_id": "target",
              "message_id": first["canvas_data"]["nodes"][0]["pending_ai"]["message_id"],
              "expected_canvas_version": second["canvas_version"]}, headers=headers,
    )
    assert stale.status_code == 409
    assert (await client.get(f"/api/v1/conversations/{cid}/project")).json()["canvas_data"]["nodes"][0]["content"] == "原有脚本"


async def test_confirmation_rejects_a_concurrent_canvas_edit(client, monkeypatch):
    cid, headers, _ = await create_project(client)
    monkeypatch.setattr("app.services.agent_service.get_text_provider", lambda: ControlledProvider())
    project = (await client.post(
        f"/api/v1/conversations/{cid}/messages", json=collaboration(), headers=headers,
    )).json()["project"]
    node = project["canvas_data"]["nodes"][0]
    node["content"] = "确认前的新编辑"
    await client.put(
        f"/api/v1/conversations/{cid}/canvas",
        json={"canvas_data": project["canvas_data"], "expected_canvas_version": project["canvas_version"]},
        headers=headers,
    )
    rejected = await client.post(
        f"/api/v1/conversations/{cid}/canvas/confirm",
        json={"target_node_id": "target", "message_id": node["pending_ai"]["message_id"],
              "expected_canvas_version": project["canvas_version"]}, headers=headers,
    )
    assert rejected.status_code == 409
    current = (await client.get(f"/api/v1/conversations/{cid}/project")).json()
    assert current["canvas_data"]["nodes"][0]["content"] == "确认前的新编辑"
    accepted = await client.post(
        f"/api/v1/conversations/{cid}/canvas/confirm",
        json={"target_node_id": "target", "message_id": node["pending_ai"]["message_id"],
              "expected_canvas_version": current["canvas_version"]}, headers=headers,
    )
    assert accepted.json()["canvas_data"]["nodes"][0]["last_ai"]["before"] == "确认前的新编辑"


async def test_multiple_manual_boxes_use_structured_agent_and_preview_matches_video_request(client, monkeypatch):
    from app.providers.video.fake import FakeVideoProvider

    cid, headers, document = await create_project(client)
    provider = ControlledProvider()
    monkeypatch.setattr("app.services.agent_service.get_text_provider", lambda: provider)
    response = await client.post(
        f"/api/v1/conversations/{cid}/canvas/prepare-video",
        json=preparation(["target", "other"], 1), headers=headers,
    )
    assert response.status_code == 200, response.text
    project = response.json()
    assert project["canvas_data"]["nodes"] == document["nodes"]
    assert project["canvas_data"]["generation_source_ids"] == ["target", "other"]
    assert not project["is_current_version_confirmed"]
    assert project["current_spec"]["subject"] == "小船"
    assert project["current_spec"]["camera"] == "镜头缓慢推进"
    assert project["current_spec"]["duration_seconds"] == 8
    assert project["current_spec"]["aspect_ratio"] == "16:9"
    assert "原有脚本" in provider.calls[0][-1]["content"] and "参考素材" in provider.calls[0][-1]["content"]
    assert "承上启下" in provider.calls[0][0]["content"]
    for phrase in ["镜头运动", "镜头缓慢推进", "主体动作", "暖色侧光", "古镇石桥"]:
        assert phrase in project["compiled_prompt"]

    class CapturingVideoProvider(FakeVideoProvider):
        request = None

        async def submit(self, request, ctx):
            self.request = request
            return await super().submit(request, ctx)

    video = CapturingVideoProvider()
    monkeypatch.setattr("app.services.video_job_service.get_video_provider", lambda *args: video)
    confirmed = await client.post(
        f"/api/v1/conversations/{cid}/project/confirm",
        json={"spec_version": project["current_spec_version"]}, headers=headers,
    )
    assert confirmed.status_code == 200
    created = await client.post(
        "/api/v1/video-jobs", headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
        json={"conversation_id": cid, "project_id": project["id"], "spec_version": project["current_spec_version"],
              "api_config_id": "platform", "mode": "text_to_video",
              "generation_options": reviewed_options(project)},
    )
    assert created.status_code == 202, created.text
    assert video.request["prompt"] == project["compiled_prompt"]
    assert video.request["duration_seconds"] == 8 and video.request["resolution"] == "1080p"


async def test_review_delivers_a_persisted_plan_and_optional_gaps_do_not_block_generation(client, monkeypatch):
    cid, headers, document = await create_project(client)

    class OptionalGapProvider(ControlledProvider):
        async def generate(self, messages, *, structured=False):
            result = await super().generate(messages, structured=structured)
            result.structured.update({
                "reply": "用途和受众是什么？需要你确认后才能继续。",
                "missing_fields": ["audience", "objective"], "ready_for_generation": False,
                "assumptions": ["采用暖色清晨光线。"],
                "suggestions": ["如需旅游宣传用途，可在小框增加目的地名称。"],
            })
            return result

    provider = OptionalGapProvider()
    monkeypatch.setattr("app.services.agent_service.get_text_provider", lambda: provider)
    response = await client.post(
        f"/api/v1/conversations/{cid}/canvas/prepare-video",
        json=preparation(["target"], 1), headers=headers,
    )
    assert response.status_code == 200, response.text
    project = response.json()
    review = project["canvas_data"]["generation_review"]
    assert review["spec_version"] == project["current_spec_version"]
    assert "### 最终方案" in review["content"]
    assert "**用途**：未填写" in review["content"] and "**受众**：未填写" in review["content"]
    assert "### 本次采用的假设" in review["content"]
    assert "### 可选建议" in review["content"]
    assert "需要你确认" not in review["content"] and "？" not in review["content"]
    assert review["content"].endswith("如果不再修改，那么可以根据我给出的方案进行生成视频。")
    assert project["canvas_data"]["nodes"] == document["nodes"]
    reopened = (await client.get(f"/api/v1/conversations/{cid}/project")).json()
    assert reopened["canvas_data"]["generation_review"] == review
    await client.post(
        f"/api/v1/conversations/{cid}/project/confirm",
        json={"spec_version": project["current_spec_version"]}, headers=headers,
    )
    created = await client.post(
        "/api/v1/video-jobs", headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
        json={"conversation_id": cid, "project_id": project["id"], "spec_version": project["current_spec_version"],
              "api_config_id": "platform", "mode": "text_to_video",
              "generation_options": reviewed_options(project)},
    )
    assert created.status_code == 202, created.text


@pytest.mark.parametrize("content", ["", "# 视频脚本\n主体：待定\n场景：待定\n光线：暖色侧光"])
async def test_review_fills_in_incomplete_or_blank_boxes_instead_of_using_chat_questions(client, monkeypatch, content):
    cid, headers, document = await create_project(client)
    document["nodes"][0]["content"] = content
    saved = await client.put(
        f"/api/v1/conversations/{cid}/canvas",
        json={"canvas_data": document, "expected_canvas_version": 1}, headers=headers,
    )
    provider = ControlledProvider()
    monkeypatch.setattr("app.services.agent_service.get_text_provider", lambda: provider)
    response = await client.post(
        f"/api/v1/conversations/{cid}/canvas/prepare-video",
        json=preparation(["target"], saved.json()["canvas_version"]), headers=headers,
    )
    assert response.status_code == 200, response.text
    system = provider.calls[0][0]["content"]
    assert "本轮是一次性 AI 审理" in system and "不要提问" in system
    assert "先在 reply 里引导用户补充" not in system
    assert response.json()["current_spec"]["subject"] == "小船"
    assert response.json()["canvas_data"]["nodes"][0]["content"] == content


async def test_incomplete_model_review_is_repaired_without_asking_the_user(client, monkeypatch):
    cid, headers, _ = await create_project(client)

    class RepairProvider(ControlledProvider):
        async def generate(self, messages, *, structured=False):
            result = await super().generate(messages, structured=structured)
            if len(self.calls) == 1:
                result.structured["state_patch"] = {"subject": "小船", "duration_seconds": 15, "camera": "固定机位"}
                result.structured["assumptions"] = ["采用水乡场景。"]
            else:
                result.structured["state_patch"].pop("camera")
            return result

    provider = RepairProvider()
    monkeypatch.setattr("app.services.agent_service.get_text_provider", lambda: provider)
    response = await client.post(
        f"/api/v1/conversations/{cid}/canvas/prepare-video",
        json=preparation(["target"], 1, duration=15), headers=headers,
    )
    assert response.status_code == 200, response.text
    assert len(provider.calls) == 2 and "【补齐输出】" in provider.calls[1][-1]["content"]
    assert response.json()["current_spec"]["duration_seconds"] == 15
    assert response.json()["current_spec"]["camera"] == "固定机位"
    assert "采用水乡场景" in response.json()["canvas_data"]["generation_review"]["content"]


@pytest.mark.parametrize("change", ["content", "delete", "selection", "linked_image", "duration", "resolution"])
async def test_video_submission_rejects_changed_sources(client, monkeypatch, change):
    cid, headers, _ = await create_project(client)
    monkeypatch.setattr("app.services.agent_service.get_text_provider", lambda: ControlledProvider())
    project = (await client.post(
        f"/api/v1/conversations/{cid}/canvas/prepare-video",
        json=preparation(["target", "other"], 1), headers=headers,
    )).json()
    await client.post(
        f"/api/v1/conversations/{cid}/project/confirm",
        json={"spec_version": project["current_spec_version"]}, headers=headers,
    )
    document = project["canvas_data"]
    if change == "content":
        document["nodes"][0]["content"] = "用户新修改的内容"
    elif change == "delete":
        document["nodes"] = document["nodes"][1:]
        document["connections"] = []
    elif change == "linked_image":
        document["nodes"].append({"id": "image", "type": "image", "title": "首帧", "asset_id": "new-asset"})
        document["connections"].append({"id": "image-link", "from": "image", "to": "target"})
    elif change == "duration":
        document["video_duration_seconds"] = 12
    elif change == "resolution":
        document["video_resolution"] = "720p"
    if change != "selection":
        await client.put(
            f"/api/v1/conversations/{cid}/canvas",
            json={"canvas_data": document, "expected_canvas_version": project["canvas_version"]}, headers=headers,
        )
    created = await client.post(
        "/api/v1/video-jobs", headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
        json={"conversation_id": cid, "project_id": project["id"], "spec_version": project["current_spec_version"],
              "api_config_id": "platform", "mode": "text_to_video",
              "generation_options": {"canvas_source_node_ids": ["target"] if change == "selection" else ["target", "other"]}},
    )
    assert created.status_code == 409, created.text
    assert created.json()["error"]["code"] == "PROJECT_NOT_CONFIRMED"


@pytest.mark.parametrize("duration", [1, 12, 15])
async def test_video_parameters_are_required_and_the_confirmed_values_reach_the_provider(client, monkeypatch, duration):
    from dataclasses import replace

    from app.providers.video.fake import FakeVideoProvider
    from app.video_registry import registry
    profile_key = ("ark_seedance_v1", "doubao-seedance-2-5")
    monkeypatch.setitem(registry._PROFILES, profile_key, replace(registry._PROFILES[profile_key], durations_seconds=tuple(range(1, 16))))

    cid, headers, _ = await create_project(client)
    provider = ControlledProvider()
    monkeypatch.setattr("app.services.agent_service.get_text_provider", lambda: provider)
    base = {"node_ids": ["target"], "expected_canvas_version": 1}
    for invalid in [{}, {"duration_seconds": 8}, {"resolution": "720p"},
                    {"duration_seconds": 7.5, "resolution": "720p"},
                    {"duration_seconds": 0, "resolution": "720p"},
                    {"duration_seconds": 16, "resolution": "720p"},
                    {"duration_seconds": 120, "resolution": "720p"},
                    {"duration_seconds": True, "resolution": "720p"},
                    {"duration_seconds": 8, "resolution": "invalid"}]:
        result = await client.post(
            f"/api/v1/conversations/{cid}/canvas/prepare-video", json={**base, **invalid}, headers=headers,
        )
        assert result.status_code == 422, result.text
    assert not provider.calls
    response = await client.post(
        f"/api/v1/conversations/{cid}/canvas/prepare-video",
        json=preparation(["target"], duration=duration, resolution="720p"), headers=headers,
    )
    assert response.status_code == 200, response.text
    project = response.json()
    assert project["current_spec"]["duration_seconds"] == duration
    assert project["canvas_data"]["generation_requested_settings"] == {"duration_seconds": duration, "resolution": "720p"}
    assert project["canvas_data"]["generation_settings"]["duration_seconds"] == duration
    assert f"{duration} 秒" in project["canvas_data"]["generation_review"]["content"]
    assert "720p" in project["canvas_data"]["generation_review"]["content"]
    assert f"视频总时长必须为 {duration} 秒" in provider.calls[0][-1]["content"]
    await client.post(
        f"/api/v1/conversations/{cid}/project/confirm",
        json={"spec_version": project["current_spec_version"]}, headers=headers,
    )

    class CapturingVideoProvider(FakeVideoProvider):
        request = None

        async def submit(self, request, ctx):
            self.request = request
            return await super().submit(request, ctx)

    video = CapturingVideoProvider()
    monkeypatch.setattr("app.services.video_job_service.get_video_provider", lambda *args: video)
    command = {"conversation_id": cid, "project_id": project["id"], "spec_version": project["current_spec_version"],
               "api_config_id": "platform", "mode": "text_to_video"}
    for options in [{"canvas_source_node_ids": ["target"]},
                    {"canvas_source_node_ids": ["target"], "duration_seconds": 8, "resolution": "720p"},
                    {"canvas_source_node_ids": ["target"], "duration_seconds": 12, "resolution": "1080p"}]:
        rejected = await client.post(
            "/api/v1/video-jobs", json={**command, "generation_options": options},
            headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
        )
        assert rejected.status_code == 422, rejected.text
    accepted = await client.post(
        "/api/v1/video-jobs", headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
        json={**command, "generation_options": reviewed_options(project)},
    )
    assert accepted.status_code == 202, accepted.text
    assert video.request["duration_seconds"] == duration and video.request["resolution"] == "720p"
    assert video.request["prompt"] == project["compiled_prompt"]


async def test_edit_during_video_preparation_preserves_edit_and_rejects_stale_plan(client, monkeypatch):
    cid, headers, document = await create_project(client)
    provider = ControlledProvider(blocked=True)
    monkeypatch.setattr("app.services.agent_service.get_text_provider", lambda: provider)
    task = asyncio.create_task(client.post(
        f"/api/v1/conversations/{cid}/canvas/prepare-video",
        json=preparation(["target"], 1), headers=headers,
    ))
    await asyncio.wait_for(provider.started.wait(), 3)
    document["nodes"][0]["content"] = "整理期间修改"
    await client.put(
        f"/api/v1/conversations/{cid}/canvas",
        json={"canvas_data": document, "expected_canvas_version": 1}, headers=headers,
    )
    provider.release.set()
    result = await asyncio.wait_for(task, 3)
    assert result.status_code == 409
    current = (await client.get(f"/api/v1/conversations/{cid}/project")).json()
    assert current["current_spec_version"] == 0
    assert current["canvas_data"]["nodes"][0]["content"] == "整理期间修改"
    assert not current["canvas_data"].get("generation_source_ids")


async def test_unconfirmed_candidate_is_excluded_from_video_preparation(client, monkeypatch):
    cid, headers, _ = await create_project(client)
    provider = ControlledProvider()
    monkeypatch.setattr("app.services.agent_service.get_text_provider", lambda: provider)
    generated = (await client.post(
        f"/api/v1/conversations/{cid}/messages", json=collaboration(), headers=headers,
    )).json()["project"]
    prepared = await client.post(
        f"/api/v1/conversations/{cid}/canvas/prepare-video",
        json=preparation(["target"], generated["canvas_version"]), headers=headers,
    )
    assert prepared.status_code == 200, prepared.text
    assert "原有脚本" in provider.calls[-1][-1]["content"]
    assert "AI 完整回复" not in provider.calls[-1][-1]["content"]
    assert prepared.json()["canvas_data"]["nodes"][0]["pending_ai"]["content"] == "AI 完整回复"


async def test_confirmed_structured_details_are_used_when_preparing_video(client, monkeypatch):
    cid, headers, _ = await create_project(client)
    provider = ControlledProvider()
    monkeypatch.setattr("app.services.agent_service.get_text_provider", lambda: provider)
    generated = (await client.post(
        f"/api/v1/conversations/{cid}/messages", json=collaboration(), headers=headers,
    )).json()["project"]
    confirmed = (await client.post(
        f"/api/v1/conversations/{cid}/canvas/confirm",
        json={"target_node_id": "target",
              "message_id": generated["canvas_data"]["nodes"][0]["pending_ai"]["message_id"],
              "expected_canvas_version": generated["canvas_version"]}, headers=headers,
    )).json()
    prepared = await client.post(
        f"/api/v1/conversations/{cid}/canvas/prepare-video",
        json=preparation(["target"], confirmed["canvas_version"]),
        headers=headers,
    )
    assert prepared.status_code == 200, prepared.text
    prompt = provider.calls[-1][-1]["content"]
    assert "该小框已确认的结构化方案" in prompt
    assert "小船经过古镇石桥" in prompt and "镜头缓慢推进" in prompt
    assert prepared.json()["canvas_data"]["generation_snapshot"][0]["confirmed_brief"]["lighting"] == "暖色侧光"


async def test_canvas_write_requires_csrf_and_rejects_invalid_structure(client):
    cid, headers, document = await create_project(client)
    rejected = await client.put(
        f"/api/v1/conversations/{cid}/canvas", json={"canvas_data": document}
    )
    assert rejected.status_code == 403
    document["nodes"][1]["id"] = "target"
    invalid = await client.put(
        f"/api/v1/conversations/{cid}/canvas", json={"canvas_data": document}, headers=headers
    )
    assert invalid.status_code == 422
    target = await client.post(
        f"/api/v1/conversations/{cid}/messages", json=collaboration("missing"), headers=headers
    )
    assert target.status_code == 422


async def test_failure_after_model_reply_clears_canvas_running_marker(client, monkeypatch):
    from app.core.errors import CANVAS_NODE_INVALID, AppError

    cid, headers, _ = await create_project(client)
    monkeypatch.setattr(
        "app.services.agent_service.get_text_provider", lambda: ControlledProvider()
    )

    async def fail_binding(*args):
        raise AppError(CANVAS_NODE_INVALID)

    monkeypatch.setattr(
        "app.services.agent_service.AgentService.bind_assistant_message", fail_binding
    )
    response = await client.post(
        f"/api/v1/conversations/{cid}/messages", json=collaboration(), headers=headers
    )
    assert response.status_code == 422
    document = (await client.get(f"/api/v1/conversations/{cid}/project")).json()["canvas_data"]
    assert document["nodes"][0]["ai_running"] is False
    assert document["nodes"][0]["content"] == "原有脚本"
    assert document["nodes"][0]["ai_error"]


async def test_canvas_write_cannot_modify_deleted_project(client):
    cid, headers, document = await create_project(client)
    await client.delete(f"/api/v1/conversations/{cid}", headers=headers)
    response = await client.put(
        f"/api/v1/conversations/{cid}/canvas",
        json={"canvas_data": document, "expected_canvas_version": 1},
        headers=headers,
    )
    assert response.status_code == 404


async def test_expired_ai_marker_recovers_after_server_restart(client, monkeypatch):
    from datetime import timedelta

    from app.core.time import now

    cid, headers, document = await create_project(client)
    document["nodes"][0].update(
        ai_running=True,
        ai_request_id="abandoned",
        ai_started_at=(now() - timedelta(hours=1)).isoformat(),
    )
    await client.put(
        f"/api/v1/conversations/{cid}/canvas",
        json={"canvas_data": document, "expected_canvas_version": 1},
        headers=headers,
    )
    current = (await client.get(f"/api/v1/conversations/{cid}/project")).json()
    assert current["canvas_data"]["nodes"][0]["ai_running"] is False
    assert current["canvas_data"]["nodes"][0]["content"] == "原有脚本"
    assert current["canvas_data"]["nodes"][0]["ai_error"]
    monkeypatch.setattr(
        "app.services.agent_service.get_text_provider", lambda: ControlledProvider()
    )
    retry = await client.post(
        f"/api/v1/conversations/{cid}/messages", json=collaboration(), headers=headers
    )
    assert retry.status_code == 201
