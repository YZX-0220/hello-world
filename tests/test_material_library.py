"""素材库回归：发布权限、共享读取、范围请求、分页、文件归属和版本冲突。"""

import io
import uuid
from pathlib import Path

import httpx
import pytest
import pytest_asyncio
from app.core.config import settings
from app.db.models.material_library import MaterialLibraryItem
from app.main import app
from app.providers.email.fake import fake_instance
from PIL import Image
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession

LIBRARY = "/api/v1/material-library"
ADMIN = "/api/v1/admin/material-library"
# HTTP 内容测试用容器字节；不作为可播放视频或解码有效性的测试。
MP4 = b"\x00\x00\x00\x18ftypisom\x00\x00\x00\x00isommp42" + b"\x00\x00\x00\x0cmdatdemo"


def _headers(client: httpx.AsyncClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies.get("hw_csrf", ""), "Origin": "http://127.0.0.1:5173"}


async def _register(client: httpx.AsyncClient) -> str:
    email = f"library-{uuid.uuid4().hex[:8]}@test.com"
    await client.post("/api/v1/auth/email-codes", json={"email": email, "purpose": "register"})
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "code": fake_instance.sent[-1]["code"], "password": "password123"},
    )
    assert response.status_code == 201, response.text
    return email


@pytest_asyncio.fixture
async def admin(client, monkeypatch):
    email = await _register(client)
    # 邮箱匹配忽略大小写和两侧空格，不默认授予所有登录用户权限。
    monkeypatch.setattr(settings, "material_library_admin_emails", f"  {email.upper()} , ")
    return client


async def _upload(client: httpx.AsyncClient, *, image: bool = False) -> dict:
    if image:
        buffer = io.BytesIO()
        Image.new("RGB", (8, 4), (0, 100, 200)).save(buffer, format="PNG")
        file = ("cover.png", buffer.getvalue(), "image/png")
    else:
        file = ("example.mp4", MP4, "video/mp4")
    response = await client.post(
        f"{ADMIN}/uploads",
        files={"file": file},
        data={"kind": "image" if image else "video"},
        headers=_headers(client),
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _create(client: httpx.AsyncClient, **changes) -> dict:
    video = await _upload(client)
    payload = {
        "title": "晨雾宫殿",
        "description": "## 作品介绍\n冬日建筑与雾气。",
        "model_name": "演示视频模型",
        "video_asset_id": video["id"],
        **changes,
    }
    response = await client.post(ADMIN, json=payload, headers=_headers(client))
    assert response.status_code == 201, response.text
    return response.json()


async def test_draft_publish_shared_video_and_unpublish(admin):
    cover = await _upload(admin, image=True)
    item = await _create(admin, cover_asset_id=cover["id"])
    item_id = item["id"]
    assert item["status"] == "draft" and item["version"] == 1
    assert item["cover"]["width"] == 8
    assert item["video"]["content_url"].endswith(f"{ADMIN}/{item_id}/video")
    assert (await admin.get(LIBRARY)).json()["items"] == []
    for endpoint in (
        f"{LIBRARY}/{item_id}",
        f"{LIBRARY}/{item_id}/video",
        f"{LIBRARY}/{item_id}/cover",
    ):
        assert (await admin.get(endpoint)).status_code == 404
    assert (await admin.get(f"{ADMIN}/{item_id}/video")).content == MP4
    published = await admin.patch(
        f"{ADMIN}/{item_id}",
        json={"expected_version": 1, "status": "published"},
        headers=_headers(admin),
    )
    assert published.status_code == 200, published.text
    assert published.json()["version"] == 2
    # 草稿下架后可再次发布；共享访问不会开放普通私有素材接口。
    await _register(admin)
    shared = await admin.get(f"{LIBRARY}/{item_id}")
    assert shared.status_code == 200 and shared.json()["description"].startswith("##")
    assert shared.json()["video"]["content_url"].endswith(f"{LIBRARY}/{item_id}/video")
    response = await admin.get(f"{LIBRARY}/{item_id}/video")
    assert response.status_code == 200 and response.content == MP4
    assert response.headers["content-disposition"].startswith("inline")
    assert response.headers["cache-control"] == "private, no-store"
    assert (
        (await admin.get(f"{LIBRARY}/{item_id}/cover"))
        .headers["content-type"]
        .startswith("image/png")
    )
    assert (
        await admin.get(f"/api/v1/assets/{item['video']['asset_id']}/content")
    ).status_code == 422
    assert (await admin.get(f"{ADMIN}/{item_id}")).status_code == 403
    # 临时指定第二个管理员执行下架，原文件仍可被管理员预览。
    email = await _register(admin)
    settings.material_library_admin_emails += f",{email}"
    hidden = await admin.patch(
        f"{ADMIN}/{item_id}",
        json={"expected_version": 2, "status": "draft"},
        headers=_headers(admin),
    )
    assert hidden.status_code == 200, hidden.text
    assert (await admin.get(f"{LIBRARY}/{item_id}/video")).status_code == 404
    assert (await admin.get(f"{ADMIN}/{item_id}/video")).status_code == 200


async def test_range_and_head_requests(admin):
    item = await _create(admin, status="published")
    url = f"{LIBRARY}/{item['id']}/video"
    response = await admin.get(url, headers={"Range": "bytes=0-11"})
    assert response.status_code == 206
    assert response.content == MP4[:12]
    assert response.headers["content-range"] == f"bytes 0-11/{len(MP4)}"
    head = await admin.head(url)
    assert head.status_code == 200 and not head.content
    assert int(head.headers["content-length"]) == len(MP4)
    assert (await admin.get(url, headers={"Range": "bytes=999-1000"})).status_code == 416
    assert (await admin.get(f"{LIBRARY}/{item['id']}/cover")).status_code == 404


async def test_search_filter_pagination_and_invalid_cursor(admin):
    ids = []
    for i in range(3):
        ids.append(
            (await _create(admin, title=f"晨雾{i}", status="published", model_name="模型A"))["id"]
        )
    await _create(admin, title="100%_示例", status="published", model_name="模型B")
    await _create(admin, title="未公开")
    response = await admin.get(LIBRARY, params={"q": "晨雾", "model_name": "模型A", "limit": 2})
    first = response.json()
    assert len(first["items"]) == 2 and first["next_cursor"]
    second = (
        await admin.get(
            LIBRARY,
            params={"q": "晨雾", "model_name": "模型A", "limit": 2, "cursor": first["next_cursor"]},
        )
    ).json()
    assert len(second["items"]) == 1 and second["next_cursor"] is None
    assert {item["id"] for item in first["items"] + second["items"]} == set(ids)
    assert len((await admin.get(LIBRARY, params={"q": "%_"})).json()["items"]) == 1
    assert len((await admin.get(ADMIN, params={"status": "draft"})).json()["items"]) == 1
    invalid = await admin.get(LIBRARY, params={"cursor": "not-a-cursor"})
    assert invalid.status_code == 422 and invalid.json()["error"]["code"] == "LIBRARY_QUERY_INVALID"


async def test_edit_conflicts_soft_delete_and_asset_protection(admin, db_engine):
    item = await _create(admin, status="published")
    url = f"{ADMIN}/{item['id']}"
    aid = item["video"]["asset_id"]
    protected = await admin.delete(f"/api/v1/assets/{aid}", headers=_headers(admin))
    assert protected.status_code == 409 and protected.json()["error"]["code"] == "ASSET_IN_USE"
    edited = await admin.patch(
        url,
        json={"expected_version": 1, "title": "新的标题", "description": "新介绍"},
        headers=_headers(admin),
    )
    assert edited.status_code == 200 and edited.json()["version"] == 2
    stale = await admin.patch(
        url, json={"expected_version": 1, "title": "旧修改"}, headers=_headers(admin)
    )
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "LIBRARY_VERSION_CONFLICT"
    assert (
        await admin.delete(url, params={"expected_version": 1}, headers=_headers(admin))
    ).status_code == 409
    assert (
        await admin.delete(url, params={"expected_version": 2}, headers=_headers(admin))
    ).status_code == 204
    assert (await admin.get(f"{LIBRARY}/{item['id']}")).status_code == 404
    assert (await admin.get(f"{LIBRARY}/{item['id']}/video")).status_code == 404
    assert (await admin.get(url)).status_code == 404
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        stored = await session.get(MaterialLibraryItem, item["id"])
        assert stored and stored.status == "deleted" and stored.deleted_at is not None
    assert (await admin.delete(f"/api/v1/assets/{aid}", headers=_headers(admin))).status_code == 204


async def test_replace_video_remove_cover_and_version_update(admin):
    cover = await _upload(admin, image=True)
    item = await _create(admin, status="published", cover_asset_id=cover["id"])
    new_video = await _upload(admin)
    response = await admin.patch(
        f"{ADMIN}/{item['id']}",
        json={"expected_version": 1, "video_asset_id": new_video["id"], "cover_asset_id": None},
        headers=_headers(admin),
    )
    assert response.status_code == 200, response.text
    assert (
        response.json()["video"]["asset_id"] == new_video["id"] and response.json()["cover"] is None
    )
    assert (
        await admin.delete(f"/api/v1/assets/{item['video']['asset_id']}", headers=_headers(admin))
    ).status_code == 204


@pytest.mark.parametrize(
    "patch",
    [
        {"title": " "},
        {"description": None},
        {"video_asset_id": None},
        {"status": "deleted"},
        {"unknown": 1},
        {},
    ],
)
async def test_reject_invalid_patch_without_mutating(admin, patch):
    item = await _create(admin)
    response = await admin.patch(
        f"{ADMIN}/{item['id']}", json={"expected_version": 1, **patch}, headers=_headers(admin)
    )
    assert response.status_code == 422, response.text
    unchanged = (await admin.get(f"{ADMIN}/{item['id']}")).json()
    assert unchanged["version"] == 1 and unchanged["title"] == item["title"]


async def test_reject_unowned_deleted_wrong_kind_and_missing_file(admin, monkeypatch):
    own_video = await _upload(admin)
    image = await _upload(admin, image=True)
    payload = {
        "title": "示例",
        "description": "介绍",
        "model_name": "模型",
        "video_asset_id": own_video["id"],
    }
    for wrong_types in ({"video_asset_id": image["id"]}, {"cover_asset_id": own_video["id"]}):
        wrong = await admin.post(ADMIN, json={**payload, **wrong_types}, headers=_headers(admin))
        assert wrong.status_code == 422 and wrong.json()["error"]["code"] == "LIBRARY_ASSET_INVALID"
    foreign_email = await _register(admin)
    monkeypatch.setattr(settings, "material_library_admin_emails", foreign_email)
    for invalid_id in (own_video["id"], image["id"], "missing"):
        response = await admin.post(
            ADMIN, json={**payload, "video_asset_id": invalid_id}, headers=_headers(admin)
        )
        assert (
            response.status_code == 422
            and response.json()["error"]["code"] == "LIBRARY_ASSET_INVALID"
        )
    own = await _upload(admin)
    assert (
        await admin.delete(f"/api/v1/assets/{own['id']}", headers=_headers(admin))
    ).status_code == 204
    response = await admin.post(
        ADMIN, json={**payload, "video_asset_id": own["id"]}, headers=_headers(admin)
    )
    assert response.status_code == 422
    lost = await _upload(admin)
    # 删除测试临时文件，模拟文件系统损失；不触碰用户的真实素材。
    # 上传接口不暴露 storage_key，根据测试目录查找这个 ID 对应的文件。
    for path in Path(settings.storage_root).rglob(f"{lost['id']}.*"):
        path.unlink()
    assert (
        await admin.post(
            ADMIN, json={**payload, "video_asset_id": lost["id"]}, headers=_headers(admin)
        )
    ).status_code == 422


async def test_published_file_loss_returns_controlled_error(admin):
    item = await _create(admin, status="published")
    for path in Path(settings.storage_root).rglob(f"{item['video']['asset_id']}.*"):
        path.unlink()
    response = await admin.get(f"{LIBRARY}/{item['id']}/video")
    assert (
        response.status_code == 404
        and response.json()["error"]["code"] == "LIBRARY_MEDIA_UNAVAILABLE"
    )


async def test_admin_permissions_and_csrf(client, monkeypatch):
    monkeypatch.setattr(settings, "material_library_admin_emails", "")
    assert (await client.get(LIBRARY)).status_code == 401
    await _register(client)
    assert (await client.get(LIBRARY)).status_code == 200
    assert (await client.get(ADMIN)).status_code == 403
    assert (
        await client.post(
            f"{ADMIN}/uploads",
            files={"file": ("v.mp4", MP4)},
            data={"kind": "video"},
            headers=_headers(client),
        )
    ).status_code == 403
    email = await _register(client)
    monkeypatch.setattr(settings, "material_library_admin_emails", email)
    assert (await client.get(ADMIN)).status_code == 200
    no_csrf = await client.post(
        f"{ADMIN}/uploads", files={"file": ("v.mp4", MP4)}, data={"kind": "video"}
    )
    assert no_csrf.status_code == 403 and no_csrf.json()["error"]["code"] == "CSRF_INVALID"


@pytest.mark.parametrize(
    "name,content",
    [("v.mp4", b"not-a-video"), ("v.mp4", b"\x00\x00\x00\x18ftypheic" + b"0" * 24), ("v.txt", MP4)],
)
async def test_upload_rejects_disguised_video(admin, name, content):
    response = await admin.post(
        f"{ADMIN}/uploads",
        files={"file": (name, content, "video/mp4")},
        data={"kind": "video"},
        headers=_headers(admin),
    )
    assert (
        response.status_code == 422 and response.json()["error"]["code"] == "ASSET_CONTENT_INVALID"
    )
    assert (await admin.get("/api/v1/assets")).json()["items"] == []


async def test_upload_rejects_oversize_before_asset_creation(admin, monkeypatch):
    monkeypatch.setattr(settings, "video_max_bytes", 16)
    response = await admin.post(
        f"{ADMIN}/uploads",
        files={"file": ("v.mp4", MP4)},
        data={"kind": "video"},
        headers=_headers(admin),
    )
    assert response.status_code == 413 and response.json()["error"]["code"] == "ASSET_TOO_LARGE"
    assert (await admin.get("/api/v1/assets")).json()["items"] == []


def test_openapi_has_unique_operations_and_actual_error_contract():
    schema = app.openapi()
    operations = [
        operation
        for path, methods in schema["paths"].items()
        if "/material-library" in path
        for operation in methods.values()
    ]
    ids = [operation["operationId"] for operation in operations]
    assert len(ids) == len(set(ids))
    for operation in operations:
        error_schema = operation["responses"]["422"]["content"]["application/json"]["schema"]
        assert error_schema["$ref"] == "#/components/schemas/ErrorResponse"
    headers = schema["paths"][ADMIN]["post"]["parameters"]
    assert any(
        parameter["name"] == "X-CSRF-Token" and parameter["in"] == "header" for parameter in headers
    )
