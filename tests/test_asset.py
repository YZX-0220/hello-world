"""阶段 7 测试：素材上传检测 / 权限下载 / 列表 / 删除 / 厂商签名素材 URL。"""

import io
import uuid

import httpx
import pytest_asyncio
from app.core.config import settings
from app.db.models.video_job import VideoJobAsset
from app.providers.email.fake import fake_instance
from app.services.provider_asset_url import sign_provider_asset
from PIL import Image
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession

ORIGIN = "http://127.0.0.1:5173"
PASSWORD = "password123"


def _png(w: int = 4, h: int = 4) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (255, 0, 0)).save(buf, format="PNG")
    return buf.getvalue()


async def _register(client: httpx.AsyncClient, tag: str) -> None:
    email = f"asset-{tag}-{uuid.uuid4().hex[:8]}@test.com"
    await client.post("/api/v1/auth/email-codes", json={"email": email, "purpose": "register"})
    code = fake_instance.sent[-1]["code"]
    resp = await client.post("/api/v1/auth/register", json={"email": email, "code": code, "password": PASSWORD})
    assert resp.status_code == 201, resp.text


def _csrf(client: httpx.AsyncClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies.get("hw_csrf", ""), "Origin": ORIGIN}


@pytest_asyncio.fixture
async def db_session(db_engine):
    sf = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with sf() as s:
        yield s


async def test_upload_png_and_read_content(client: httpx.AsyncClient) -> None:
    await _register(client, "u1")
    headers = _csrf(client)
    data = _png()
    resp = await client.post(
        "/api/v1/assets",
        files={"file": ("a.png", data, "image/png")},
        data={"purpose": "reference"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["kind"] == "image"
    assert body["width"] == 4 and body["height"] == 4
    assert body["status"] == "ready"
    assert body["content_url"].endswith(f"/api/v1/assets/{body['id']}/content")

    content = await client.get(f"/api/v1/assets/{body['id']}/content")
    assert content.status_code == 200
    assert content.content == data  # 读取回传的就是原始文件字节


async def test_reject_mismatched_content(client: httpx.AsyncClient) -> None:
    await _register(client, "u2")
    headers = _csrf(client)
    # 声明 reference（图片）却传入非图片字节
    resp = await client.post(
        "/api/v1/assets",
        files={"file": ("named.jpg", b"clearly-not-an-image", "image/jpeg")},
        data={"purpose": "reference"},
        headers=headers,
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "ASSET_CONTENT_INVALID"


async def test_asset_inaccessible_to_other_user(client: httpx.AsyncClient) -> None:
    await _register(client, "owner")
    headers = _csrf(client)
    created = (
        await client.post(
            "/api/v1/assets",
            files={"file": ("own.png", _png(), "image/png")},
            data={"purpose": "reference"},
            headers=headers,
        )
    ).json()
    # 换一个用户访问
    await _register(client, "intruder")
    other_headers = _csrf(client)
    resp = await client.get(f"/api/v1/assets/{created['id']}", headers=other_headers)
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "ASSET_CONTENT_INVALID"


async def test_list_and_delete(client: httpx.AsyncClient) -> None:
    await _register(client, "u3")
    headers = _csrf(client)
    for i in range(2):
        r = await client.post(
            "/api/v1/assets",
            files={"file": (f"p{i}.png", _png(), "image/png")},
            data={"purpose": "reference"},
            headers=headers,
        )
        assert r.status_code == 201

    listed = await client.get("/api/v1/assets", params={"purpose": "reference"})
    assert listed.status_code == 200
    assert len(listed.json()["items"]) == 2

    aid = listed.json()["items"][0]["id"]
    deleted = await client.delete(f"/api/v1/assets/{aid}", headers=headers)
    assert deleted.status_code == 204
    remaining = (await client.get("/api/v1/assets", params={"purpose": "reference"})).json()
    assert all(item["id"] != aid for item in remaining["items"])


async def test_provider_asset_token_flow(client: httpx.AsyncClient, db_session) -> None:
    """厂商签名 URL：绑定 asset+job → 单次可读；篡改 / 重放 → 404。"""
    await _register(client, "u4")
    headers = _csrf(client)
    data = _png()
    up = (
        await client.post(
            "/api/v1/assets",
            files={"file": ("frame.png", data, "image/png")},
            data={"purpose": "first_frame"},
            headers=headers,
        )
    ).json()
    aid = up["id"]
    job_id = "job-fixed-0001"

    # 记录任务对该素材的引用（签名只返回被任务引用且 ready 的素材）
    db_session.add(VideoJobAsset(video_job_id=job_id, asset_id=aid, role="first_frame"))
    await db_session.commit()

    token, _ = sign_provider_asset(aid, job_id, "first_frame", settings.app_secret, 600)

    got = await client.get(f"/api/v1/provider-assets/{token}")
    assert got.status_code == 200
    assert got.content == data

    # 篡改 signature -> 404
    bad = token[:-6] + "xxxxxx"
    assert (await client.get(f"/api/v1/provider-assets/{bad}")).status_code == 404
    # 单次访问，重放 -> 404
    assert (await client.get(f"/api/v1/provider-assets/{token}")).status_code == 404
