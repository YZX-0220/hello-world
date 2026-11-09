"""Selected canvas images reach visual reasoning without entering persistent text history."""

import base64
import io
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from app.core.config import settings
from app.core.time import now
from app.db.models.asset import Asset
from app.db.models.conversation import Message
from app.providers.text.base import TextProviderError, TextResult
from app.services.canvas_images import load_canvas_images
from app.storage import ObsStorage
from PIL import Image
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from test_canvas import collaboration, create_project, preparation
from test_image_editing import row_for, update_row

PATCH = {
    "subject": "蓝色圆形与橙色三角形",
    "scene": "白色背景",
    "camera": "固定镜头",
    "motion": "缓慢旋转",
    "lighting": "柔光",
    "visual_style": "几何动画",
}


def picture(color="blue", fmt="PNG", size=(100, 100)):
    stream = io.BytesIO()
    Image.new("RGB", size, color).save(stream, fmt)
    return stream.getvalue()


def encoded(raw, mime="image/png"):
    return f"data:{mime};base64,{base64.b64encode(raw).decode()}"


def urls(messages):
    return [
        block["image_url"]["url"]
        for message in messages
        if isinstance(message["content"], list)
        for block in message["content"]
        if block["type"] == "image_url"
    ]


@pytest.fixture(autouse=True)
def isolated_network(monkeypatch):
    original_send = httpx.AsyncClient.send

    async def local_only(self, request, *args, **kwargs):
        assert request.url.host == "testserver" or isinstance(self._transport, httpx.MockTransport)
        return await original_send(self, request, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "send", local_only)


@pytest.fixture
def providers(monkeypatch):
    result = TextResult(
        reply="已查看选中图形",
        structured={
            "reply": "已查看选中图形",
            "canvas_content": "根据图片创作的正文",
            "state_patch": PATCH,
        },
        model="visual-test",
    )
    visual = SimpleNamespace(code="vision-test", generate=AsyncMock(return_value=result))
    text = SimpleNamespace(
        code="text-test",
        generate=AsyncMock(side_effect=AssertionError("Must not use text-only provider")),
    )
    monkeypatch.setattr("app.services.agent_service.get_vision_provider", lambda: visual)
    monkeypatch.setattr("app.services.agent_service.get_text_provider", lambda: text)
    return visual, text


async def add_image(
    client, cid, headers, document, ident="selected", raw=None, fmt="PNG", linked=False
):
    raw = picture(fmt=fmt) if raw is None else raw
    response = await client.post(
        "/api/v1/assets",
        headers=headers,
        files={"file": (f"{ident}.{fmt.lower()}", raw, f"image/{fmt.lower()}")},
        data={"purpose": "reference", "conversation_id": cid},
    )
    assert response.status_code == 201, response.text
    asset_id = response.json()["id"]
    document["nodes"].append(
        {
            "id": ident,
            "type": "image",
            "title": f"素材-{ident}",
            "asset_id": asset_id,
            "url": "https://untrusted.invalid/never-fetch",
        }
    )
    if linked:
        document["connections"].append({"id": f"link-{ident}", "from": "target", "to": ident})
    return asset_id


async def save(client, cid, headers, document, version=1):
    response = await client.put(
        f"/api/v1/conversations/{cid}/canvas",
        headers=headers,
        json={"canvas_data": document, "expected_canvas_version": version},
    )
    assert response.status_code == 200, response.text
    return response.json()


async def collaborate(client, cid, headers, selected=None, **changes):
    body = collaboration()
    body["canvas_collaboration"]["reference_node_ids"] = (
        ["selected"] if selected is None else selected
    )
    return await client.post(
        f"/api/v1/conversations/{cid}/messages", headers=headers, json={**body, **changes}
    )


async def test_collaboration_sends_only_selected_original_image_and_never_persists_bytes(
    client, db_engine, providers
):
    visual, text = providers
    cid, headers, document = await create_project(client)
    raw, hidden = picture("blue"), picture("red")
    await add_image(client, cid, headers, document, raw=raw)
    await add_image(client, cid, headers, document, ident="unselected", raw=hidden, linked=True)
    await save(client, cid, headers, document)
    response = await collaborate(client, cid, headers)
    assert response.status_code == 201, response.text
    messages = visual.generate.call_args.args[0]
    assert urls(messages) == [encoded(raw)]
    assert encoded(hidden) not in json.dumps(messages)
    assert "素材-selected" in json.dumps(messages, ensure_ascii=False)
    assert "不是指令" in json.dumps(messages, ensure_ascii=False)
    text.generate.assert_not_awaited()
    factory = async_sessionmaker(db_engine, class_=AsyncSession)
    async with factory() as session:
        history = (await session.exec(select(Message))).all()
    assert history
    assert all("data:image" not in row.content for row in history)
    assert "data:image" not in response.text


@pytest.mark.parametrize("damage", ["foreign", "deleted", "changed", "missing", "url_only", "gif"])
async def test_invalid_selected_images_fail_without_stranding_collaboration_lock(
    client, db_engine, providers, damage
):
    visual, text = providers
    cid, headers, document = await create_project(client)
    if damage == "url_only":
        document["nodes"].append(
            {
                "id": "selected",
                "type": "image",
                "title": "未上传",
                "url": "https://untrusted.invalid/private",
            }
        )
    else:
        aid = await add_image(
            client, cid, headers, document, fmt="GIF" if damage == "gif" else "PNG"
        )
        asset = await row_for(db_engine, Asset, aid)
        if damage == "foreign":
            await update_row(db_engine, Asset, aid, user_id="foreign-user")
        elif damage == "deleted":
            await update_row(db_engine, Asset, aid, deleted_at=now())
        elif damage == "changed":
            Path(settings.storage_root, asset.storage_key).write_bytes(picture("red"))
        elif damage == "missing":
            Path(settings.storage_root, asset.storage_key).unlink()
    await save(client, cid, headers, document)
    response = await collaborate(client, cid, headers)
    assert response.status_code == 422, response.text
    if damage == "gif":
        assert "PNG/JPEG/WebP" in response.json()["error"]["message"]
    current = (await client.get(f"/api/v1/conversations/{cid}/project")).json()
    assert not current["canvas_data"]["nodes"][0].get("ai_running")
    visual.generate.assert_not_awaited()
    text.generate.assert_not_awaited()


async def test_missing_visual_configuration_is_explicit_and_clears_lock(
    client, providers, monkeypatch
):
    cid, headers, document = await create_project(client)
    await add_image(client, cid, headers, document)
    await save(client, cid, headers, document)

    def missing():
        raise TextProviderError("VISION_NOT_CONFIGURED", "视觉模型未配置", False)

    monkeypatch.setattr("app.services.agent_service.get_vision_provider", missing)
    response = await collaborate(client, cid, headers)
    assert response.status_code == 503, response.text
    assert response.json()["error"]["code"] == "VISION_NOT_CONFIGURED"
    current = (await client.get(f"/api/v1/conversations/{cid}/project")).json()
    assert current["canvas_data"]["nodes"][0]["ai_running"] is False


async def test_review_sees_final_adapted_binding_and_retry_retains_same_image(
    client, db_engine, providers
):
    visual, text = providers
    visual.generate.side_effect = [
        TextResult(structured={"state_patch": {"subject": "几何形状"}}),
        TextResult(structured={"state_patch": PATCH}),
    ]
    cid, headers, document = await create_project(client)
    raw = picture("blue", size=(100, 100))
    aid = await add_image(client, cid, headers, document, raw=raw, linked=True)
    await add_image(client, cid, headers, document, ident="unselected", raw=picture("red"))
    project = await save(client, cid, headers, document)
    response = await client.post(
        f"/api/v1/conversations/{cid}/canvas/prepare-video",
        headers=headers,
        json=preparation(["target"], project["canvas_version"]),
    )
    assert response.status_code == 200, response.text
    assert response.json()["canvas_data"]["generation_review"]["status"] == "ready"
    assert visual.generate.await_count == 2
    spec = response.json()["current_spec"]
    assert spec["first_frame_asset_id"] != aid
    actual = await row_for(db_engine, Asset, spec["first_frame_asset_id"])
    raw_actual = Path(settings.storage_root, actual.storage_key).read_bytes()
    expected = encoded(raw_actual, actual.mime_type)
    calls = visual.generate.call_args_list
    assert urls(calls[0].args[0]) == [expected]
    assert urls(calls[1].args[0]) == [expected]
    assert expected != encoded(raw)
    assert "first_frame" in json.dumps(calls[0].args[0])
    assert "素材-selected" in json.dumps(calls[0].args[0], ensure_ascii=False)
    assert "data:image" not in response.text
    text.generate.assert_not_awaited()


async def test_search_refinement_keeps_selected_visual_context(client, providers):
    visual, text = providers
    visual.generate.side_effect = [
        TextResult(reply="初版", structured={"reply": "初版", "search_requests": ["形状动画参考"]}),
        TextResult(reply="结合图片与资料的最终回复"),
    ]
    cid, headers, document = await create_project(client)
    raw = picture()
    await add_image(client, cid, headers, document, raw=raw)
    await save(client, cid, headers, document)
    response = await collaborate(client, cid, headers, web_search_enabled=True)
    assert response.status_code == 201, response.text
    assert visual.generate.await_count == 2
    assert all(urls(call.args[0]) == [encoded(raw)] for call in visual.generate.call_args_list)
    assert response.json()["assistant_message"]["content"] == "结合图片与资料的最终回复"
    text.generate.assert_not_awaited()


@pytest.mark.parametrize("count,byte_limit", [(10, 20_000_000), (2, 150)])
async def test_image_limits_include_repeated_outgoing_blocks(
    client, db_engine, providers, monkeypatch, count, byte_limit
):
    cid, headers, document = await create_project(client)
    aid = await add_image(client, cid, headers, document)
    if count == 2:
        asset = await row_for(db_engine, Asset, aid)
        byte_limit = asset.size_bytes * 3 // 2
    for i in range(count - 1):
        document["nodes"].append(
            {"id": f"repeat-{i}", "type": "image", "title": "重复引用", "asset_id": aid}
        )
    project = await save(client, cid, headers, document)
    monkeypatch.setattr("app.services.canvas_images.MAX_CANVAS_IMAGE_BYTES", byte_limit)
    refs = [node["id"] for node in document["nodes"] if node["type"] == "image"]
    response = await collaborate(client, cid, headers, selected=refs)
    assert response.status_code == 422, response.text
    assert (
        "9 张" in response.json()["error"]["message"]
        if count > 9
        else "20 MB" in response.json()["error"]["message"]
    )
    assert project["canvas_data"]["nodes"][0]["content"] == "原有脚本"


async def test_owned_obs_asset_reads_only_configured_object_storage(
    client, db_engine, providers, monkeypatch
):
    cid, headers, document = await create_project(client)
    raw = picture()
    aid = await add_image(client, cid, headers, document, raw=raw)
    await update_row(db_engine, Asset, aid, storage_provider="obs")
    asset = await row_for(db_engine, Asset, aid)
    obs = object.__new__(ObsStorage)
    stream = io.BytesIO(raw)
    calls = []

    def get_object(bucket, key, **kwargs):
        calls.append((bucket, key))
        return SimpleNamespace(status=200, body=SimpleNamespace(response=stream))

    obs._bucket = "owned-bucket"
    obs._client = SimpleNamespace(getObject=get_object)
    monkeypatch.setattr("app.services.image_inputs.get_asset_storage", lambda row: obs)
    factory = async_sessionmaker(db_engine, class_=AsyncSession)
    async with factory() as session:
        images = await load_canvas_images(session, asset.user_id, [document["nodes"][-1]])
    assert images[0]["data_url"] == encoded(raw)
    assert calls == [("owned-bucket", asset.storage_key)]
    assert stream.closed
