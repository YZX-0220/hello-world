"""3D 视角与空间构图节点 (perspective) 后端持久化、素材上传、多图生图与 Agent 协作测试。"""

from json import dumps as json_dumps
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

from app.core.config import settings
from app.providers.text.base import TextResult
from httpx import AsyncClient
from pytest import mark
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession

from test_canvas import create_project, preparation
from test_canvas_vision import collaborate, encoded, picture, urls


def _perspective_node(asset_id: str | None = None, url: str = "") -> dict:
    return {
        "id": "perspective-1",
        "type": "perspective",
        "title": "3D视角构图",
        "x": 260,
        "y": 140,
        "content": (
            "【机位与透视】9:16 画幅，低机位仰拍视角。\n"
            "【镜头运动】从起始机位平滑推进至特写。\n"
            "【画面空间排布】前景右侧石碑遮挡部分视野，中景中央红衣剑客持剑立于篝火旁。"
        ),
        "url": url,
        "asset_id": asset_id,
        "perspective_data": {
            "aspectRatio": "9:16",
            "groundColor": "#3b4252",
            "objects": [
                {
                    "id": "obj-1",
                    "shape": "box",
                    "color": "#ef4444",
                    "colorName": "红色立方体",
                    "alias": "红衣剑客",
                    "position": [0, 1, -2],
                    "scale": [1, 2, 1],
                }
            ],
            "startCamera": {"position": [0, 1.5, 6], "target": [0, 1, 0]},
            "endCamera": {"position": [0, 1.4, 3], "target": [0, 1, -1]},
            "endFrameUrl": "data:image/png;base64,ZmFrZQ==",
        },
    }


async def test_perspective_node_canvas_roundtrip_and_data_url_save(client: AsyncClient):
    cid, headers, document = await create_project(client)
    node = _perspective_node(url="data:image/png;base64,iVBORw0KGgo=")
    document["nodes"].append(node)

    saved = await client.put(
        f"/api/v1/conversations/{cid}/canvas",
        json={"canvas_data": document, "expected_canvas_version": 1},
        headers=headers,
    )
    assert saved.status_code == 200, saved.text
    body = saved.json()
    persisted = next(n for n in body["canvas_data"]["nodes"] if n["id"] == "perspective-1")
    assert persisted["type"] == "perspective"
    assert persisted["perspective_data"]["aspectRatio"] == "9:16"
    assert persisted["perspective_data"]["objects"][0]["alias"] == "红衣剑客"

    fetched = await client.get(f"/api/v1/conversations/{cid}/project", headers=headers)
    assert fetched.status_code == 200, fetched.text
    got = next(n for n in fetched.json()["canvas_data"]["nodes"] if n["id"] == "perspective-1")
    assert got["perspective_data"] == node["perspective_data"]
    assert got["url"] == node["url"]


@mark.parametrize("purpose", ["reference", "perspective_capture"])
async def test_perspective_screenshot_upload_purposes(client: AsyncClient, purpose: str):
    cid, headers, _document = await create_project(client)
    raw = picture("gray", fmt="PNG", size=(160, 90))
    resp = await client.post(
        "/api/v1/assets",
        headers=headers,
        files={"file": ("perspective.png", raw, "image/png")},
        data={"purpose": purpose, "conversation_id": cid},
    )
    assert resp.status_code == 201, resp.text
    asset = resp.json()
    assert asset["kind"] == "image"
    assert asset["content_url"] == f"/api/v1/assets/{asset['id']}/content"


async def test_perspective_screenshot_combines_with_reference_image_for_generation(
    client: AsyncClient, db_engine, monkeypatch
):
    from app.providers.image.ark_plan import ImageResult
    from app.services.image_generation_service import ImageGenerationService

    captured: dict = {}

    async def fake_generate_image(**kwargs):
        captured.update(kwargs)
        return ImageResult(
            image_bytes=picture("green", fmt="PNG", size=(128, 128)),
            mime_type="image/png",
            ext="png",
            width=128,
            height=128,
            request_id="req-perspective-1",
            usage={"output_tokens": 100, "total_tokens": 100},
        )

    monkeypatch.setattr(settings, "image_provider", "ark")
    monkeypatch.setattr(settings, "image_worker_enabled", False)
    monkeypatch.setattr(settings, "image_platform_api_key", "test-ark-image-key")
    monkeypatch.setattr(settings, "image_platform_model", "doubao-seedream-5.0-pro")
    monkeypatch.setattr("app.services.image_generation_service.generate_image", fake_generate_image)

    cid, headers, _document = await create_project(client)
    shot_bytes = picture("gray", fmt="PNG", size=(160, 90))
    char_bytes = picture("red", fmt="PNG", size=(120, 120))

    shot_resp = await client.post(
        "/api/v1/assets",
        headers=headers,
        files={"file": ("perspective_start.png", shot_bytes, "image/png")},
        data={"purpose": "perspective_capture", "conversation_id": cid},
    )
    char_resp = await client.post(
        "/api/v1/assets",
        headers=headers,
        files={"file": ("character.png", char_bytes, "image/png")},
        data={"purpose": "reference", "conversation_id": cid},
    )
    assert shot_resp.status_code == 201 and char_resp.status_code == 201
    shot_id = shot_resp.json()["id"]
    char_id = char_resp.json()["id"]

    job_resp = await client.post(
        "/api/v1/image-jobs",
        headers={**headers, "Idempotency-Key": str(uuid4())},
        json={
            "conversation_id": cid,
            "api_config_id": "platform",
            "prompt": "按图1空间透视将图2红衣剑客渲染进实景竹林中",
            "aspect_ratio": "16:9",
            "reference_asset_ids": [shot_id, char_id],
        },
    )
    assert job_resp.status_code == 201, job_resp.text
    job_id = job_resp.json()["id"]

    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        await ImageGenerationService(session).run(job_id)

    assert captured["images"] == [
        encoded(shot_bytes, "image/png"),
        encoded(char_bytes, "image/png"),
    ]
    assert "空间透视" in captured["prompt"]


async def test_perspective_node_collaboration_injects_instruction_and_optional_screenshot(
    client: AsyncClient, monkeypatch
):
    cid, headers, document = await create_project(client)

    # 1) Text-only perspective node (no asset_id yet) must work with text provider without 422.
    document["nodes"].append(_perspective_node(asset_id=None, url=""))
    save_text_only = await client.put(
        f"/api/v1/conversations/{cid}/canvas",
        json={"canvas_data": document, "expected_canvas_version": 1},
        headers=headers,
    )
    assert save_text_only.status_code == 200, save_text_only.text

    text_result = TextResult(
        reply="已按 3D 机位更新脚本",
        structured={
            "reply": "已按 3D 机位更新脚本",
            "canvas_content": "低机位仰拍，前景石碑左侧后方篝火旁红衣剑客持剑而立。",
            "state_patch": {"camera": "低机位仰拍"},
        },
        model="text-test",
    )
    text_provider = SimpleNamespace(code="text-test", generate=AsyncMock(return_value=text_result))
    monkeypatch.setattr("app.services.agent_service.get_text_provider", lambda: text_provider)

    resp_text_only = await collaborate(client, cid, headers, selected=["perspective-1"])
    assert resp_text_only.status_code == 201, resp_text_only.text
    sent_messages = text_provider.generate.call_args.args[0]
    dumped_text = json_dumps(sent_messages, ensure_ascii=False)
    assert "3D 视角与空间构图节点处理规则" in dumped_text
    assert "红衣剑客" in dumped_text

    # 2) Once screenshot asset_id is uploaded, visual provider receives both 6D text and PNG bytes.
    raw = picture("slategray", fmt="PNG", size=(160, 90))
    up = await client.post(
        "/api/v1/assets",
        headers=headers,
        files={"file": ("shot.png", raw, "image/png")},
        data={"purpose": "reference", "conversation_id": cid},
    )
    assert up.status_code == 201
    asset = up.json()

    latest = await client.get(f"/api/v1/conversations/{cid}/project", headers=headers)
    doc2 = latest.json()["canvas_data"]
    for n in doc2["nodes"]:
        if n["id"] == "perspective-1":
            n["asset_id"] = asset["id"]
            n["url"] = asset["content_url"]
    save_with_img = await client.put(
        f"/api/v1/conversations/{cid}/canvas",
        json={"canvas_data": doc2, "expected_canvas_version": latest.json()["canvas_version"]},
        headers=headers,
    )
    assert save_with_img.status_code == 200

    vision_provider = SimpleNamespace(
        code="vision-test",
        generate=AsyncMock(
            return_value=TextResult(
                reply="已结合 3D 视口截图优化分镜",
                structured={
                    "reply": "已结合 3D 视口截图优化分镜",
                    "canvas_content": "优化后分镜",
                    "state_patch": {"camera": "低机位仰拍缓缓推进"},
                },
                model="vision-test",
            )
        ),
    )
    monkeypatch.setattr("app.services.agent_service.get_vision_provider", lambda: vision_provider)

    resp_visual = await collaborate(client, cid, headers, selected=["perspective-1"])
    assert resp_visual.status_code == 201, resp_visual.text
    vision_msgs = vision_provider.generate.call_args.args[0]
    assert urls(vision_msgs) == [encoded(raw)]
    assert "3D视角构图" in json_dumps(vision_msgs, ensure_ascii=False)


async def test_video_review_includes_perspective_prompt_and_excludes_whitebox_from_first_frame(
    client: AsyncClient, monkeypatch
):
    cid, headers, document = await create_project(client)
    shot = picture("gray", fmt="PNG", size=(160, 90))
    up = await client.post(
        "/api/v1/assets",
        headers=headers,
        files={"file": ("shot.png", shot, "image/png")},
        data={"purpose": "reference", "conversation_id": cid},
    )
    assert up.status_code == 201
    asset = up.json()

    document["nodes"].append(_perspective_node(asset_id=asset["id"], url=asset["content_url"]))
    saved = await client.put(
        f"/api/v1/conversations/{cid}/canvas",
        json={"canvas_data": document, "expected_canvas_version": 1},
        headers=headers,
    )
    assert saved.status_code == 200
    version = saved.json()["canvas_version"]

    review_result = TextResult(
        reply="ok",
        structured={
            "state_patch": {
                "subject": "红衣剑客立于篝火旁",
                "scene": "前景右侧石碑遮挡部分视野，夜色荒原篝火跳动",
                "camera": "低机位仰拍缓缓推进",
                "motion": "剑客微转身望向镜头",
                "lighting": "暖色篝火侧逆光",
                "visual_style": "写实武侠电影质感",
            },
            "assumptions": [],
            "suggestions": [],
            "contains_portrait": False,
        },
        model="review-test",
    )
    review_provider = SimpleNamespace(
        code="review-test", generate=AsyncMock(return_value=review_result)
    )
    monkeypatch.setattr("app.services.agent_service.get_text_provider", lambda: review_provider)
    monkeypatch.setattr("app.services.agent_service.get_vision_provider", lambda: review_provider)

    prep = await client.post(
        f"/api/v1/conversations/{cid}/canvas/prepare-video",
        headers=headers,
        json=preparation(["target", "perspective-1"], version),
    )
    assert prep.status_code == 200, prep.text
    body = prep.json()
    assert body["current_spec"]["mode"] == "text_to_video"
    assert body["current_spec"]["first_frame_asset_id"] is None
    assert body["current_spec"]["aspect_ratio"] == "9:16"

    prompt_msgs = review_provider.generate.call_args.args[0]
    dumped = json_dumps(prompt_msgs, ensure_ascii=False)
    assert "3D 视角与空间构图节点处理规则" in dumped
    assert "3D 视角参考小框【3D视角构图】（type=perspective）" in dumped
    assert "前景右侧石碑遮挡部分视野" in dumped
