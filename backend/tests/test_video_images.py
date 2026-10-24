import asyncio
import io
import time
from dataclasses import replace
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from app.core.config import settings
from app.db.models.asset import Asset
from app.db.models.project import VideoProjectVersion
from app.providers.video.base import VideoTaskStatus
from app.providers.video.fake import FakeVideoProvider
from app.services.provider_asset_url import _unb64
from app.services.video_image_service import adapt_image, image_issues
from app.storage import LocalStorage
from app.video_registry import get_profile
from PIL import Image
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from test_canvas import ControlledProvider, create_project, preparation
from test_model_bound_review import confirm, prepare, save, submit

RULES = get_profile("ark_seedance_v1", "doubao-seedance-2-5").image_constraints


def picture(size, fmt="PNG", **kwargs):
    out = io.BytesIO()
    Image.new("RGB", size, (220, 30, 10)).save(out, format=fmt, **kwargs)
    return out.getvalue()


@pytest.mark.parametrize("size", [
    (1, 1), (16, 9), (200, 500), (300, 300), (300, 750), (750, 300),
    (300, 751), (751, 300), (1000, 10), (10, 1000), (1, 100000), (100000, 1),
    (6001, 100), (100, 6001), (4000, 3000),
])
def test_normalization_satisfies_dimensions_ratio_and_bytes_together(size):
    original = picture(size)
    data, meta, actions = adapt_image(original, RULES)
    assert not image_issues(meta, RULES)
    assert meta["width"] * meta["height"] <= settings.image_max_pixels
    with Image.open(io.BytesIO(data)) as output:
        assert output.size == (meta["width"], meta["height"])
        cx, cy = output.width // 2, output.height // 2
        assert max(output.getpixel((cx + dx, cy + dy))[0] for dx in (-1, 0, 1) for dy in (-1, 0, 1)) > 100
    if size == (300, 300):
        assert data == original and not actions
    if size == (200, 500):
        assert any("放大" in a for a in actions)  # Area >=90k alone is insufficient.
    if size in ((300, 751), (751, 300)):
        assert any("补边" in a for a in actions)


def test_orientation_animation_and_format_conversion_are_disclosed():
    exif = Image.Exif()
    exif[274] = 6
    _data, meta, actions = adapt_image(picture((800, 400), "JPEG", exif=exif), RULES)
    assert (meta["width"], meta["height"]) == (400, 800)
    assert any("纠正" in a for a in actions)
    for fmt in ("BMP", "TIFF", "GIF"):
        _, meta, actions = adapt_image(picture((400, 400), fmt), RULES)
        assert meta["mime_type"] == "image/jpeg"
        assert any("JPEG" in a for a in actions)
    out = io.BytesIO()
    Image.new("RGB", (400, 400), "red").save(
        out, format="GIF", save_all=True, append_images=[Image.new("RGB", (400, 400), "blue")], duration=100,
    )
    _, _, actions = adapt_image(out.getvalue(), RULES)
    assert any("第一帧" in a for a in actions)
    with pytest.raises((ValueError, OSError)):
        adapt_image(b"invalid image", RULES)


def test_byte_limit_is_checked_after_encoding():
    with pytest.raises(ValueError):
        adapt_image(picture((300, 300)), replace(RULES, max_bytes_exclusive=10))


async def image_project(client, count=1):
    cid, headers, document = await create_project(client)
    originals = []
    for i in range(count):
        uploaded = await client.post("/api/v1/assets", headers=headers,
            files={"file": (f"image{i}.png", picture((1000, 10)), "image/png")},
            data={"purpose": "reference"})
        assert uploaded.status_code == 201, uploaded.text
        originals.append(uploaded.json()["id"])
        document["nodes"].append({
            "id": f"image{i}", "type": "image", "title": f"参考{i}", "x": 0, "y": 0,
            "asset_id": originals[-1],
        })
        document["connections"].append({"id": f"link{i}", "from": "target", "to": f"image{i}"})
    project = (await client.get(f"/api/v1/conversations/{cid}/project")).json()
    return cid, headers, await save(client, cid, headers, project, document), originals


@pytest.mark.parametrize("mode,count", [
    ("first_frame_to_video", 1), ("first_last_frame_to_video", 1), ("reference_image_to_video", 2),
])
async def test_review_submits_exact_prepared_bytes_without_image_preview(client, monkeypatch, db_engine, mode, count):
    cid, headers, project, originals = await image_project(client, count)
    monkeypatch.setattr("app.services.agent_service.get_text_provider", lambda: ControlledProvider())
    reviewed = await prepare(client, cid, headers, project, mode=mode, duration_seconds=7)
    review = reviewed["canvas_data"]["generation_review"]
    assert review["status"] == "ready"
    assert "背景补边" in review["content"] and "原图已保留" in review["content"]
    assert "![" not in review["content"] and "<img" not in review["content"]
    assert reviewed["canvas_data"]["nodes"] == project["canvas_data"]["nodes"]
    assert reviewed["current_spec"]["duration_seconds"] == 7
    assert (await confirm(client, cid, headers, reviewed)).status_code == 200
    requests = []

    class Capture(FakeVideoProvider):
        async def submit(self, request, ctx):
            requests.append(request)
            return await super().submit(request, ctx)

    monkeypatch.setattr("app.services.video_job_service.get_video_provider", lambda *args: Capture())
    response = await submit(client, cid, headers, reviewed)
    assert response.status_code == 202, response.text
    request = requests[0]
    urls = request.get("reference_image_urls") or [request["first_frame_url"]]
    for url in urls:
        token = url.rsplit("/", 1)[-1]
        import json
        payload = json.loads(_unb64(token.split(".")[0]))
        assert payload["aid"] not in originals
        assert payload["exp"] - time.time() > 172800
        fetched = await client.get(urlsplit(url).path)
        assert fetched.status_code == 200, fetched.text
        with Image.open(io.BytesIO(fetched.content)) as image:
            assert image.size == (1000, 400)
    if mode == "first_last_frame_to_video":
        assert reviewed["current_spec"]["first_frame_asset_id"] == reviewed["current_spec"]["last_frame_asset_id"]
    # The persisted bindings agree with the actual task input and retain original lineage.
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        version = (await session.exec(select(VideoProjectVersion).where(
            VideoProjectVersion.project_id == reviewed["id"],
            VideoProjectVersion.version == reviewed["current_spec_version"],
        ))).first()
        import json
        bindings = json.loads(version.generation_review_json)["materials"]
        assert {b["source_asset_id"] for b in bindings} == set(originals)
    reopened = (await client.get(f"/api/v1/conversations/{cid}/project")).json()
    assert reopened["canvas_data"]["generation_review"] == review


@pytest.mark.parametrize("change", ["deleted", "tampered", "original_deleted"])
async def test_invalidated_material_cannot_pass_confirm_or_submit(client, monkeypatch, db_engine, change):
    cid, headers, project, originals = await image_project(client)
    monkeypatch.setattr("app.services.agent_service.get_text_provider", lambda: ControlledProvider())
    reviewed = await prepare(client, cid, headers, project, mode="first_frame_to_video")
    assert (await confirm(client, cid, headers, reviewed)).status_code == 200
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        aid = originals[0] if change == "original_deleted" else reviewed["current_spec"]["first_frame_asset_id"]
        asset = (await session.exec(select(Asset).where(Asset.id == aid))).first()
        if change == "tampered":
            LocalStorage(settings.storage_root).open_read_path(asset.storage_key).write_bytes(b"broken image")
        else:
            asset.status = "deleted"
            await session.commit()
    assert (await confirm(client, cid, headers, reviewed)).status_code == 409
    assert (await submit(client, cid, headers, reviewed)).status_code == 409


async def test_image_preparation_does_not_lock_canvas_during_text_ai(client, monkeypatch):
    cid, headers, project, _ = await image_project(client)
    provider = ControlledProvider(blocked=True)
    monkeypatch.setattr("app.services.agent_service.get_text_provider", lambda: provider)
    work = asyncio.create_task(client.post(f"/api/v1/conversations/{cid}/canvas/prepare-video",
        headers=headers, json={**preparation(["target"], project["canvas_version"]), "mode": "first_frame_to_video"}))
    await asyncio.wait_for(provider.started.wait(), 5)
    document = project["canvas_data"]
    document["nodes"][0]["content"] = "审理期间继续编辑"
    await asyncio.wait_for(save(client, cid, headers, project, document), 3)
    provider.release.set()
    assert (await asyncio.wait_for(work, 5)).status_code == 409
    assert not list(Path(settings.storage_root).glob("*/generation-input/*"))


@pytest.mark.parametrize("duration", [1, 2, 3])
async def test_seedance_duration_requires_manual_valid_choice_before_ai(client, monkeypatch, duration):
    cid, headers, _ = await create_project(client)
    provider = ControlledProvider()
    monkeypatch.setattr("app.services.agent_service.get_text_provider", lambda: provider)
    project = (await client.get(f"/api/v1/conversations/{cid}/project")).json()
    reviewed = await prepare(client, cid, headers, project, duration_seconds=duration)
    assert reviewed["canvas_data"]["generation_review"]["status"] == "blocked"
    assert "手动选择" in reviewed["canvas_data"]["generation_review"]["content"]
    assert not provider.calls


async def test_async_vendor_failure_is_returned_to_user(client, monkeypatch):
    cid, headers, _ = await create_project(client)
    monkeypatch.setattr("app.services.agent_service.get_text_provider", lambda: ControlledProvider())
    project = (await client.get(f"/api/v1/conversations/{cid}/project")).json()
    reviewed = await prepare(client, cid, headers, project)
    await confirm(client, cid, headers, reviewed)

    class Failing(FakeVideoProvider):
        async def poll(self, task_id, ctx):
            return VideoTaskStatus(raw_status="failed", error_code="InvalidParameter.TaskTypeConstraint",
                                   error_message="厂商明确的失败原因")

    provider = Failing()
    monkeypatch.setattr("app.services.video_job_service.get_video_provider", lambda *args: provider)
    response = await submit(client, cid, headers, reviewed)
    result = (await client.get(f"/api/v1/video-jobs/{response.json()['id']}")).json()
    assert result["status"] == "failed"
    assert result["error"]["code"] == "InvalidParameter.TaskTypeConstraint"
    assert result["error"]["message"] == "厂商明确的失败原因"
    assert result["completed_at"]
