"""阶段 8 测试：视频任务创建（幂等/状态机/事件）、列表、失败路径。"""

import uuid

import httpx
from app.providers.email.fake import fake_instance
from app.providers.video.base import VideoProvider, VideoProviderError

ORIGIN = "http://127.0.0.1:5173"
PASSWORD = "password123"


async def _register(client: httpx.AsyncClient) -> None:
    email = f"vjob-{uuid.uuid4().hex[:8]}@test.com"
    await client.post("/api/v1/auth/email-codes", json={"email": email, "purpose": "register"})
    code = fake_instance.sent[-1]["code"]
    assert (await client.post("/api/v1/auth/register", json={"email": email, "code": code, "password": PASSWORD})).status_code == 201


def _csrf(client: httpx.AsyncClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies.get("hw_csrf", ""), "Origin": ORIGIN}


async def _make_deliverable(client: httpx.AsyncClient) -> tuple[str, dict]:
    """注册 → 建对话 → 发消息（Fake 生成方案）→ 确认版本 → 建视频接口配置。"""
    await _register(client)
    headers = _csrf(client)
    conv = await client.post("/api/v1/conversations", json={"title": "出片测试"}, headers=headers)
    cid = conv.json()["conversation"]["id"]

    await client.post(
        f"/api/v1/conversations/{cid}/messages",
        json={"content": "主体是一辆穿越草原的越野车", "client_request_id": str(uuid.uuid4())},
        headers=headers,
    )
    project = (await client.get(f"/api/v1/conversations/{cid}/project")).json()
    version = project["current_spec_version"]
    confirmed = await client.post(
        f"/api/v1/conversations/{cid}/project/confirm",
        json={"spec_version": version},
        headers=headers,
    )
    assert confirmed.json()["is_current_version_confirmed"] is True

    cfg = await client.post(
        "/api/v1/video-api-configs",
        json={
            "display_name": "中转出片",
            "source_type": "relay",
            "protocol_code": "generic_async_json_v1",
            "template_code": "v1_videos_json_v1",
            "base_url": "https://api.example-video.com",
            "remote_model_id": "videos-mini",
            "auth": {"api_key": "sk-abcdef123456"},
            "options": {},
            "capability_profile_code": "text_reference_media",
            "relay_risk_accepted": True,
        },
        headers=headers,
    )
    assert cfg.status_code == 201, cfg.text

    project_info = {"conversation_id": cid, "project_id": project["id"], "spec_version": version, "api_config_id": cfg.json()["id"]}
    return cid, project_info


async def _make_confirmed_project(client: httpx.AsyncClient) -> dict:
    """注册 → 建对话 → 发消息（Fake 生成方案）→ 确认版本。不创建视频接口配置。

    平台自有通道（api_config_id="platform"）不需要用户配置，只需项目已确认。
    """
    await _register(client)
    headers = _csrf(client)
    conv = await client.post("/api/v1/conversations", json={"title": "出片测试"}, headers=headers)
    cid = conv.json()["conversation"]["id"]

    await client.post(
        f"/api/v1/conversations/{cid}/messages",
        json={"content": "主体是一辆穿越草原的越野车", "client_request_id": str(uuid.uuid4())},
        headers=headers,
    )
    project = (await client.get(f"/api/v1/conversations/{cid}/project")).json()
    version = project["current_spec_version"]
    confirmed = await client.post(
        f"/api/v1/conversations/{cid}/project/confirm",
        json={"spec_version": version},
        headers=headers,
    )
    assert confirmed.json()["is_current_version_confirmed"] is True
    return {"conversation_id": cid, "project_id": project["id"], "spec_version": version}


def _platform_cmd(info: dict, **overrides) -> dict:
    """构造平台自有通道命令（保留字 api_config_id="platform"）。"""
    cmd = {
        "conversation_id": info["conversation_id"],
        "project_id": info["project_id"],
        "spec_version": info["spec_version"],
        "api_config_id": "platform",
        "mode": "text_to_video",
        "generation_options": {},
    }
    cmd.update(overrides)
    return cmd


async def test_create_video_job_and_poll(client: httpx.AsyncClient) -> None:
    _cid, info = await _make_deliverable(client)
    headers = _csrf(client)
    cmd = {
        "conversation_id": info["conversation_id"],
        "project_id": info["project_id"],
        "spec_version": info["spec_version"],
        "api_config_id": info["api_config_id"],
        "mode": "text_to_video",
        "generation_options": {},
    }
    idem = str(uuid.uuid4())
    resp = await client.post(
        "/api/v1/video-jobs", json=cmd, headers={**headers, "Idempotency-Key": idem}
    )
    assert resp.status_code == 202, resp.text
    job = resp.json()
    assert job["protocol_code"] == "generic_async_json_v1"
    assert job["status"] in ("queued", "running")  # fake 提交后 queued
    assert job["api_config_revision"] == 1
    jid = job["id"]

    # 轮询推进状态机，直到 succeeded
    final = None
    for _ in range(6):
        got = (await client.get(f"/api/v1/video-jobs/{jid}")).json()
        if got["status"] == "succeeded":
            final = got
            break
    assert final is not None, "轮询未走到 succeeded"
    assert final["status"] == "succeeded"
    assert final["completed_at"] is not None

    # 事件时间线存在（submit + 若干 status_change）
    events = (await client.get(f"/api/v1/video-jobs/{jid}/events")).json()
    assert len(events["items"]) >= 1
    types = {e["event_type"] for e in events["items"]}
    assert "submit" in types and "status_change" in types


async def test_video_job_idempotency(client: httpx.AsyncClient) -> None:
    _cid, info = await _make_deliverable(client)
    headers = _csrf(client)
    idem = str(uuid.uuid4())
    base = {
        "conversation_id": info["conversation_id"],
        "project_id": info["project_id"],
        "spec_version": info["spec_version"],
        "api_config_id": info["api_config_id"],
        "mode": "text_to_video",
        "generation_options": {},
    }
    r1 = await client.post("/api/v1/video-jobs", json=base, headers={**headers, "Idempotency-Key": idem})
    assert r1.status_code == 202
    job1 = r1.json()

    # 同 key 同请求 → 幂等返回原任务（仍 202）
    r2 = await client.post("/api/v1/video-jobs", json=base, headers={**headers, "Idempotency-Key": idem})
    assert r2.status_code == 202
    assert r2.json()["id"] == job1["id"]

    # 同 key 不同请求 → 409
    base["mode"] = "first_frame_to_video"
    r3 = await client.post("/api/v1/video-jobs", json=base, headers={**headers, "Idempotency-Key": idem})
    assert r3.status_code == 409
    assert r3.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"


async def test_video_job_list(client: httpx.AsyncClient) -> None:
    _cid, info = await _make_deliverable(client)
    headers = _csrf(client)
    r = await client.post(
        "/api/v1/video-jobs",
        json={
            "conversation_id": info["conversation_id"],
            "project_id": info["project_id"],
            "spec_version": info["spec_version"],
            "api_config_id": info["api_config_id"],
            "mode": "text_to_video",
            "generation_options": {},
        },
        headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
    )
    assert r.status_code == 202
    listed = await client.get("/api/v1/video-jobs", params={"conversation_id": info["conversation_id"]})
    assert listed.status_code == 200
    assert len(listed.json()["items"]) >= 1
    assert listed.json()["items"][0]["mode"] == "text_to_video"


async def test_video_job_submission_failed(client: httpx.AsyncClient, monkeypatch) -> None:
    _cid, info = await _make_deliverable(client)
    headers = _csrf(client)

    class RejectProvider(VideoProvider):
        code = "reject"

        async def submit(self, request, ctx):
            raise VideoProviderError("VIDEO_SUBMISSION_FAILED", "厂商拒绝了任务", retryable=False)

        async def poll(self, task_id, ctx):
            raise NotImplementedError

        async def fetch_result_url(self, task_id, ctx):
            raise NotImplementedError

        async def download_result(self, task_id, ctx):
            return None

        async def cancel(self, task_id, ctx):
            return False

    import app.services.video_job_service as vjs

    monkeypatch.setattr(vjs, "get_video_provider", lambda: RejectProvider())

    r = await client.post(
        "/api/v1/video-jobs",
        json={
            "conversation_id": info["conversation_id"],
            "project_id": info["project_id"],
            "spec_version": info["spec_version"],
            "api_config_id": info["api_config_id"],
            "mode": "text_to_video",
            "generation_options": {},
        },
        headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
    )
    assert r.status_code == 202
    body = r.json()
    assert body["status"] == "failed"
    assert body["error"]["code"] == "VIDEO_SUBMISSION_FAILED"


def _cmd(info: dict, **overrides) -> dict:
    cmd = {
        "conversation_id": info["conversation_id"],
        "project_id": info["project_id"],
        "spec_version": info["spec_version"],
        "api_config_id": info["api_config_id"],
        "mode": "text_to_video",
        "generation_options": {},
    }
    cmd.update(overrides)
    return cmd


async def _poll_to_succeeded(client: httpx.AsyncClient, jid: str) -> dict | None:
    for _ in range(8):
        body = (await client.get(f"/api/v1/video-jobs/{jid}")).json()
        if body["status"] == "succeeded":
            return body
    return None


async def test_download_stores_result_asset(client: httpx.AsyncClient) -> None:
    """中转下载：结果字节落成本站 result Asset，可走 content 接口读回。"""
    _cid, info = await _make_deliverable(client)
    headers = _csrf(client)
    created = await client.post(
        "/api/v1/video-jobs", json=_cmd(info), headers={**headers, "Idempotency-Key": str(uuid.uuid4())}
    )
    body = await _poll_to_succeeded(client, created.json()["id"])
    assert body is not None
    assert body["status"] == "succeeded"
    assert body["download_status"] == "stored"
    assert body["result_asset_id"] is not None
    content = await client.get(f"/api/v1/assets/{body['result_asset_id']}/content")
    assert content.status_code == 200
    assert content.content == b"FAKE_VIDEO_BYTES"


async def test_direct_fallback(client: httpx.AsyncClient, monkeypatch) -> None:
    """下载失败且只给直链 + 模型允许直链 -> download_status=direct，返回临时直链与过期时间。"""
    from app.providers.video.base import VideoTaskStatus
    from app.services import video_download_service as vds

    class DirectOnlyProvider(VideoProvider):
        code = "direct"

        async def submit(self, request, ctx):
            raise NotImplementedError

        async def poll(self, task_id, ctx):
            return VideoTaskStatus("succeeded")

        async def fetch_result_url(self, task_id, ctx):
            return "https://cdn.example.com/out/v1.mp4"

        async def download_result(self, task_id, ctx):
            return None

        async def cancel(self, task_id, ctx):
            return False

    monkeypatch.setattr(vds, "get_video_provider", lambda: DirectOnlyProvider())

    _cid, info = await _make_deliverable(client)
    headers = _csrf(client)
    created = await client.post(
        "/api/v1/video-jobs", json=_cmd(info), headers={**headers, "Idempotency-Key": str(uuid.uuid4())}
    )
    body = await _poll_to_succeeded(client, created.json()["id"])
    assert body is not None
    assert body["status"] == "succeeded"
    assert body["download_status"] == "direct"
    assert body["result_asset_id"] is None
    assert body["result_direct_url"] == "https://cdn.example.com/out/v1.mp4"
    assert body["result_expires_at"] is not None


async def test_cancel_and_idempotent(client: httpx.AsyncClient) -> None:
    _cid, info = await _make_deliverable(client)
    headers = _csrf(client)
    created = (await client.post(
        "/api/v1/video-jobs", json=_cmd(info), headers={**headers, "Idempotency-Key": str(uuid.uuid4())}
    )).json()
    cancelled = await client.post(f"/api/v1/video-jobs/{created['id']}/cancel", headers=headers)
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    again = await client.post(f"/api/v1/video-jobs/{created['id']}/cancel", headers=headers)
    assert again.json()["status"] == "cancelled"


async def test_retry_requires_failed_download(client: httpx.AsyncClient) -> None:
    """仅当生成成功且下载失败时可重试；已成功落盘时重试应报错。"""
    _cid, info = await _make_deliverable(client)
    headers = _csrf(client)
    created = (await client.post(
        "/api/v1/video-jobs", json=_cmd(info), headers={**headers, "Idempotency-Key": str(uuid.uuid4())}
    )).json()
    body = await _poll_to_succeeded(client, created["id"])
    assert body is not None and body["download_status"] == "stored"
    retry = await client.post(f"/api/v1/video-jobs/{created['id']}/download/retry", headers=headers)
    assert retry.status_code == 502
    assert retry.json()["error"]["code"] == "VIDEO_DOWNLOAD_FAILED"


async def test_platform_channel_create(client: httpx.AsyncClient) -> None:
    """平台自有通道：无需用户视频接口配置，直接建任务成功（202），status 非 created。"""
    info = await _make_confirmed_project(client)
    headers = _csrf(client)
    r = await client.post(
        "/api/v1/video-jobs", json=_platform_cmd(info), headers={**headers, "Idempotency-Key": str(uuid.uuid4())}
    )
    assert r.status_code == 202, r.text
    job = r.json()
    assert job["api_config_id"] is None  # 平台通道不引用用户配置（存 NULL）
    assert job["status"] in ("queued", "running")  # fake 提交后 queued，不会停在 created
    assert job["api_config_revision"] == 0  # 平台通道无 revision


async def test_platform_channel_daily_quota(client: httpx.AsyncClient) -> None:
    """同用户当日再建一个 platform 任务 → 429 PLATFORM_DAILY_QUOTA_EXCEEDED。"""
    info = await _make_confirmed_project(client)
    headers = _csrf(client)
    r1 = await client.post(
        "/api/v1/video-jobs", json=_platform_cmd(info), headers={**headers, "Idempotency-Key": str(uuid.uuid4())}
    )
    assert r1.status_code == 202, r1.text

    r2 = await client.post(
        "/api/v1/video-jobs", json=_platform_cmd(info), headers={**headers, "Idempotency-Key": str(uuid.uuid4())}
    )
    assert r2.status_code == 429, r2.text
    assert r2.json()["error"]["code"] == "PLATFORM_DAILY_QUOTA_EXCEEDED"


async def test_platform_quota_does_not_affect_user_config(client: httpx.AsyncClient) -> None:
    """平台额度用完不影响用户自配 API 创建（仍可建）。"""
    _cid, info = await _make_deliverable(client)
    headers = _csrf(client)

    # 先消费掉平台当日额度
    pr = await client.post(
        "/api/v1/video-jobs", json=_platform_cmd(info), headers={**headers, "Idempotency-Key": str(uuid.uuid4())}
    )
    assert pr.status_code == 202, pr.text

    # 用户自配 API 创建不受平台配额影响
    cr = await client.post(
        "/api/v1/video-jobs", json=_cmd(info), headers={**headers, "Idempotency-Key": str(uuid.uuid4())}
    )
    assert cr.status_code == 202, cr.text
    assert cr.json()["api_config_id"] == info["api_config_id"]
    assert cr.json()["api_config_revision"] == 1


async def test_platform_channel_poll(client: httpx.AsyncClient) -> None:
    """平台任务轮询走通（fake poll 正常，不因无 revision 报错/500），直到 succeeded。"""
    info = await _make_confirmed_project(client)
    headers = _csrf(client)
    created = (
        await client.post(
            "/api/v1/video-jobs", json=_platform_cmd(info), headers={**headers, "Idempotency-Key": str(uuid.uuid4())}
        )
    ).json()
    jid = created["id"]
    final = None
    for _ in range(8):
        got = (await client.get(f"/api/v1/video-jobs/{jid}")).json()
        if got["status"] == "succeeded":
            final = got
            break
    assert final is not None, "平台任务轮询未走到 succeeded"
    assert final["status"] == "succeeded"
