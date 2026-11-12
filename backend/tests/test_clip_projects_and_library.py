import uuid

import httpx
import pytest
from app.providers.email.fake import fake_instance

PASSWORD = "Password123!"
ORIGIN = "http://localhost:5173"


async def _register(client: httpx.AsyncClient, tag: str) -> None:
    email = f"clip-{tag}-{uuid.uuid4().hex[:8]}@test.com"
    await client.post("/api/v1/auth/email-codes", json={"email": email, "purpose": "register"})
    code = fake_instance.sent[-1]["code"]
    resp = await client.post(
        "/api/v1/auth/register", json={"email": email, "code": code, "password": PASSWORD}
    )
    assert resp.status_code == 201, resp.text


def _csrf(client: httpx.AsyncClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies.get("hw_csrf", ""), "Origin": ORIGIN}


@pytest.mark.asyncio
async def test_clip_project_lifecycle(client: httpx.AsyncClient) -> None:
    await _register(client, "clip1")
    headers = _csrf(client)

    # 1. 创建工程
    create_res = await client.post(
        "/api/v1/clip-projects",
        json={"title": "测试工程1", "width": 1920, "height": 1080, "fps": 30},
        headers=headers,
    )
    assert create_res.status_code == 201
    proj = create_res.json()
    assert proj["title"] == "测试工程1"
    assert proj["version"] == 1
    proj_id = proj["id"]

    # 2. 查询列表
    list_res = await client.get("/api/v1/clip-projects")
    assert list_res.status_code == 200
    items = list_res.json()
    assert any(p["id"] == proj_id for p in items)

    # 3. 获取详情
    get_res = await client.get(f"/api/v1/clip-projects/{proj_id}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == proj_id

    # 4. 正常更新草稿
    new_timeline = '{"tracks":[{"id":"t1","clips":[]}],"duration_ms":5000}'
    update_res = await client.put(
        f"/api/v1/clip-projects/{proj_id}",
        json={
            "title": "已更名工程",
            "timeline_json": new_timeline,
            "duration_ms": 5000,
            "expected_version": 1,
        },
        headers=headers,
    )
    assert update_res.status_code == 200
    updated = update_res.json()
    assert updated["title"] == "已更名工程"
    assert updated["version"] == 2
    assert updated["duration_ms"] == 5000

    # 5. 乐观锁冲突校验 (用旧版本 1 更新应报 409)
    conflict_res = await client.put(
        f"/api/v1/clip-projects/{proj_id}",
        json={
            "title": "冲突提交",
            "timeline_json": new_timeline,
            "duration_ms": 5000,
            "expected_version": 1,
        },
        headers=headers,
    )
    assert conflict_res.status_code == 409

    # 6. 删除工程
    del_res = await client.delete(f"/api/v1/clip-projects/{proj_id}", headers=headers)
    assert del_res.status_code == 204

    # 再次获取 404
    assert (await client.get(f"/api/v1/clip-projects/{proj_id}")).status_code == 404


@pytest.mark.asyncio
async def test_library_quota_and_assets(client: httpx.AsyncClient) -> None:
    await _register(client, "clip2")

    # 1. 查询配额
    quota_res = await client.get("/api/v1/library/quota")
    assert quota_res.status_code == 200
    quota = quota_res.json()
    assert quota["quota_gb"] == 1.0
    assert quota["quota_bytes"] == 1024 * 1024 * 1024
    assert quota["used_bytes"] == 0

    # 2. 查询素材列表
    assets_res = await client.get("/api/v1/library/assets?purpose=all")
    assert assets_res.status_code == 200
    data = assets_res.json()
    assert "items" in data
    assert isinstance(data["items"], list)
