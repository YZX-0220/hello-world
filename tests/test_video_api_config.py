"""阶段 6 测试：视频协议只读接口 + 用户 API 配置 CRUD（密钥掩码 / revision / 乐观锁 / SSRF）。"""

import uuid

import httpx
from app.providers.email.fake import fake_instance

ORIGIN = "http://127.0.0.1:5173"
PASSWORD = "password123"


async def _register(client: httpx.AsyncClient) -> None:
    email = f"vapi-{uuid.uuid4().hex[:8]}@test.com"
    await client.post("/api/v1/auth/email-codes", json={"email": email, "purpose": "register"})
    code = fake_instance.sent[-1]["code"]
    resp = await client.post("/api/v1/auth/register", json={"email": email, "code": code, "password": PASSWORD})
    assert resp.status_code == 201, resp.text


def _headers(client: httpx.AsyncClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies.get("hw_csrf", ""), "Origin": ORIGIN}


def _create_payload() -> dict:
    return {
        "display_name": "我的第三方视频接口",
        "source_type": "relay",
        "protocol_code": "generic_async_json_v1",
        "template_code": "v1_videos_json_v1",
        "base_url": "https://api.example-video.com",
        "remote_model_id": "videos-mini",
        "auth": {"api_key": "sk-secret-123456"},
        "options": {},
        "capability_profile_code": "text_reference_media",
        "relay_risk_accepted": True,
    }


async def test_video_protocols_readonly(client: httpx.AsyncClient) -> None:
    await _register(client)

    presets = await client.get("/api/v1/video-api-presets")
    assert presets.status_code == 200
    items = presets.json()["items"]
    assert any(p["code"] == "generic_async_json_v1" for p in items)
    generic = next(p for p in items if p["code"] == "generic_async_json_v1")
    # 鉴权字段必须含密钥字段且标记 is_secret（前端据此构造表单）
    assert generic["auth_fields"][0]["name"] == "api_key"
    assert generic["auth_fields"][0]["secret"] is True

    templates = await client.get("/api/v1/video-api-templates", params={"protocol_code": "generic_async_json_v1"})
    assert templates.status_code == 200
    assert any(t["code"] == "v1_videos_json_v1" for t in templates.json()["items"])

    profiles = await client.get("/api/v1/video-model-profiles", params={"protocol_code": "generic_async_json_v1"})
    assert profiles.status_code == 200
    assert any(p["code"] == "text_reference_media" for p in profiles.json()["items"])


async def test_reject_unsafe_base_url(client: httpx.AsyncClient) -> None:
    await _register(client)
    headers = _headers(client)
    payload = _create_payload()
    payload.pop("display_name")  # /test 请求不含 display_name（extra=forbid）
    payload["base_url"] = "http://api.example.com"  # 非 HTTPS -> SSRF 拒绝
    resp = await client.post("/api/v1/video-api-configs/test", json=payload, headers=headers)
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "UNSAFE_BASE_URL"


async def test_create_config_and_key_mask(client: httpx.AsyncClient) -> None:
    await _register(client)
    headers = _headers(client)

    resp = await client.post("/api/v1/video-api-configs", json=_create_payload(), headers=headers)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["current_revision"] == 1
    assert body["protocol_code"] == "generic_async_json_v1"
    # 只返回掩码，绝不返回明文密钥
    assert body["key_hint_json"]["api_key"] == "****3456"
    assert "sk-secret" not in str(body)


async def test_duplicate_display_name_conflict(client: httpx.AsyncClient) -> None:
    await _register(client)
    headers = _headers(client)
    await client.post("/api/v1/video-api-configs", json=_create_payload(), headers=headers)
    resp = await client.post("/api/v1/video-api-configs", json=_create_payload(), headers=headers)
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "VIDEO_CONFIG_NAME_EXISTS"


async def test_patch_identity_no_new_revision(client: httpx.AsyncClient) -> None:
    await _register(client)
    headers = _headers(client)
    created = (await client.post("/api/v1/video-api-configs", json=_create_payload(), headers=headers)).json()

    resp = await client.patch(
        f"/api/v1/video-api-configs/{created['id']}",
        json={"expected_version": created["version"], "display_name": "改名后的接口"},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["display_name"] == "改名后的接口"
    assert body["version"] == created["version"] + 1  # 身份变更仅版本 +1
    assert body["current_revision"] == 1  # 不新建连接 revision


async def test_patch_connection_creates_revision(client: httpx.AsyncClient) -> None:
    await _register(client)
    headers = _headers(client)
    created = (await client.post("/api/v1/video-api-configs", json=_create_payload(), headers=headers)).json()

    resp = await client.patch(
        f"/api/v1/video-api-configs/{created['id']}",
        json={"expected_version": created["version"], "remote_model_id": "videos-standard"},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["remote_model_id"] == "videos-standard"
    assert body["current_revision"] == 2  # 连接项变更新增修订版本
    assert body["verification_status"] == "unverified"  # 变更后需重新检测


async def test_delete_then_not_found(client: httpx.AsyncClient) -> None:
    await _register(client)
    headers = _headers(client)
    created = (await client.post("/api/v1/video-api-configs", json=_create_payload(), headers=headers)).json()
    cid = created["id"]

    resp = await client.delete(f"/api/v1/video-api-configs/{cid}", headers=headers)
    assert resp.status_code == 204
    listed = await client.get("/api/v1/video-api-configs")
    assert all(item["id"] != cid for item in listed.json()["items"])
    fetched = await client.get(f"/api/v1/video-api-configs/{cid}")
    assert fetched.status_code == 404
    assert fetched.json()["error"]["code"] == "VIDEO_API_CONFIG_NOT_FOUND"


async def test_retest_persisted_config(client: httpx.AsyncClient) -> None:
    await _register(client)
    headers = _headers(client)
    created = (await client.post("/api/v1/video-api-configs", json=_create_payload(), headers=headers)).json()

    resp = await client.post(f"/api/v1/video-api-configs/{created['id']}/test", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["verification_status"] == "verified"
