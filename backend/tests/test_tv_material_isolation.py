from uuid import uuid4

from app.providers.email.fake import fake_instance
from httpx import AsyncClient
from pytest import MonkeyPatch, mark

PASSWORD = "Password123!"
ORIGIN = "http://127.0.0.1:5173"


async def _register(client: AsyncClient, tag: str) -> None:
    email = f"tv-admin-{tag}-{uuid4().hex[:8]}@test.com"
    await client.post("/api/v1/auth/email-codes", json={"email": email, "purpose": "register"})
    code = fake_instance.sent[-1]["code"]
    resp = await client.post(
        "/api/v1/auth/register", json={"email": email, "code": code, "password": PASSWORD}
    )
    assert resp.status_code == 201, resp.text


def _csrf(client: AsyncClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies.get("hw_csrf", ""), "Origin": ORIGIN}


def _mp4_bytes() -> bytes:
    # 构造极简有效 MP4 头结构
    ftyp = b"ftypisom"
    length = 24
    header = length.to_bytes(4, "big") + ftyp + b"\x00\x00\x02\x00isomiso2mp41"
    return header + b"\x00" * 32


@mark.asyncio
async def test_tv_materials_not_in_user_clip_library(
    client: AsyncClient, monkeypatch: MonkeyPatch
) -> None:
    # 1. 注册一个账号并配置为管理员
    from app.core.config import settings

    email = f"tv-admin-{uuid4().hex[:8]}@test.com"
    await client.post("/api/v1/auth/email-codes", json={"email": email, "purpose": "register"})
    code = fake_instance.sent[-1]["code"]
    resp = await client.post(
        "/api/v1/auth/register", json={"email": email, "code": code, "password": PASSWORD}
    )
    assert resp.status_code == 201, resp.text
    monkeypatch.setattr(settings, "material_library_admin_emails", email)

    headers = _csrf(client)

    # 2. 上传一个 TV 频道视频
    mp4_data = _mp4_bytes()
    upload_res = await client.post(
        "/api/v1/admin/material-library/uploads",
        files={"file": ("showcase.mp4", mp4_data, "video/mp4")},
        data={"kind": "video"},
        headers=headers,
    )
    assert upload_res.status_code == 201
    asset_id = upload_res.json()["id"]

    # 3. 录入为 TV 示例作品
    item_res = await client.post(
        "/api/v1/admin/material-library",
        json={
            "title": "官方TV宣传片",
            "model_name": "Seedance",
            "description": "测试描述",
            "video_asset_id": asset_id,
            "cover_asset_id": None,
            "status": "published",
        },
        headers=headers,
    )
    assert item_res.status_code == 201

    # 4. 检查该用户的剪辑素材区列表 (GET /api/v1/library/assets)
    # 无论筛选 purpose=all 还是 purpose=source_video，都不应该包含刚才上传的 TV 视频！
    lib_res_all = await client.get("/api/v1/library/assets?purpose=all")
    assert lib_res_all.status_code == 200
    all_items = lib_res_all.json()["items"]
    assert not any(item["id"] == asset_id for item in all_items)

    lib_res_source = await client.get("/api/v1/library/assets?purpose=source_video")
    assert lib_res_source.status_code == 200
    source_items = lib_res_source.json()["items"]
    assert not any(item["id"] == asset_id for item in source_items)
