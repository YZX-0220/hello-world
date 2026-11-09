"""Real storage/routing code with an in-memory OBS SDK; never contact external services."""

import asyncio
import base64
import hashlib
import io
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from urllib.parse import urlsplit

import pytest
from app.core.config import settings
from app.db.models.asset import Asset
from app.db.models.image_generation import ImageJob
from app.services.canvas_images import load_canvas_images
from app.services.image_inputs import read_reference
from app.storage import ObsStorage, StorageError
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession

import test_image_generation as generation
import test_video_images as video
from test_canvas import ControlledProvider, preparation
from test_image_editing import data_url, reference
from test_model_bound_review import confirm, prepare, save, submit


@pytest.fixture
def obs_memory(monkeypatch):
    objects, streams = {}, []
    sdk = Mock()
    for name, value in {
        "huawei_cloud_obs_endpoint": "https://obs.example.invalid",
        "huawei_cloud_obs_bucket": "test-images",
        "huawei_cloud_obs_access_key": "test-ak",
        "huawei_cloud_obs_secret_key": "test-sk",
        "image_provider": "fake",
        "image_worker_enabled": False,
        "image_platform_api_key": "",
        "app_env": "dev",
    }.items():
        monkeypatch.setattr(settings, name, value)

    def put(bucket, key, data):
        objects[key] = bytes(data)
        return SimpleNamespace(status=200)

    def get(bucket, key, **kwargs):
        if key not in objects:
            return SimpleNamespace(status=404, body=None)
        stream = io.BytesIO(objects[key])
        streams.append(stream)
        return SimpleNamespace(status=200, body=SimpleNamespace(response=stream))

    def delete(bucket, key):
        objects.pop(key, None)
        return SimpleNamespace(status=204)

    sdk.putContent.side_effect = put
    sdk.getObject.side_effect = get
    sdk.deleteObject.side_effect = delete
    sdk.getObjectMetadata.side_effect = lambda bucket, key: SimpleNamespace(
        status=200 if key in objects else 404
    )
    sdk.createSignedUrl.side_effect = lambda **kwargs: SimpleNamespace(
        signedUrl="https://obs.example.invalid/" + kwargs["objectKey"]
    )
    monkeypatch.setattr("app.storage.obs.ObsClient", lambda **kwargs: sdk)
    monkeypatch.setattr(
        "app.services.agent_service.get_vision_provider", lambda: ControlledProvider()
    )
    return SimpleNamespace(objects=objects, streams=streams, sdk=sdk)


async def test_obs_reference_generation_editing_and_visual_context(
    client, db_engine, monkeypatch, obs_memory
):
    await generation.register(client)
    cid = await generation.conversation(client)
    raw = generation.original_png((400, 400))
    uploaded = await reference(client, cid, data=raw)
    asset = await generation.row_for(db_engine, Asset, uploaded["id"])
    assert asset.storage_provider == "obs"
    assert obs_memory.objects[asset.storage_key] == raw
    assert not Path(settings.storage_root, asset.storage_key).exists()
    assert read_reference(asset)[0] == raw
    response = await client.get(uploaded["content_url"])
    assert response.status_code == 302
    assert response.headers["location"].endswith(asset.storage_key)
    assert "x-image-process" not in (
        obs_memory.sdk.createSignedUrl.call_args.kwargs["queryParams"] or {}
    )
    downloaded = await client.get(f"/api/v1/assets/{asset.id}/content?download=true")
    assert downloaded.status_code == 302
    query = obs_memory.sdk.createSignedUrl.call_args.kwargs["queryParams"]
    assert query["response-content-disposition"].startswith("attachment;")
    assert "x-image-process" not in query

    generated = generation.original_png((420, 420))
    provider = generation.mock_real(monkeypatch, data=generated)
    job = await generation.create_job(client, cid, reference_asset_ids=[asset.id])
    await generation.run_job(db_engine, job["id"])
    assert provider.call_args.kwargs["images"] == [data_url(raw)]
    result = await generation.row_for(db_engine, Asset, job["id"])
    assert result.storage_provider == "obs"
    assert obs_memory.objects[result.storage_key] == generated
    assert result.sha256 == hashlib.sha256(generated).hexdigest()
    assert not Path(settings.storage_root, result.storage_key).exists()

    child = await generation.create_job(client, cid, parent_job_id=job["id"], prompt="蓝色背景")
    await generation.run_job(db_engine, child["id"])
    assert provider.call_args.kwargs["images"] == [data_url(generated)]
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        images = await load_canvas_images(
            session, asset.user_id, [{"id": "image", "type": "image", "asset_id": result.id}]
        )
    assert base64.b64decode(images[0]["data_url"].split(",", 1)[1]) == generated
    assert all(stream.closed for stream in obs_memory.streams)


@pytest.mark.parametrize("source_storage", ["obs", "local"])
async def test_video_review_checks_and_serves_obs_derived_image(
    client, db_engine, monkeypatch, obs_memory, source_storage
):
    if source_storage == "local":
        monkeypatch.setattr(settings, "huawei_cloud_obs_bucket", "")
    cid, headers, project, originals = await video.image_project(client)
    monkeypatch.setattr(settings, "huawei_cloud_obs_bucket", "test-images")
    reviewed = await prepare(client, cid, headers, project, mode="first_frame_to_video")
    assert reviewed["canvas_data"]["generation_review"]["status"] == "ready"
    aid = reviewed["current_spec"]["first_frame_asset_id"]
    assert aid != originals[0]
    derived = await generation.row_for(db_engine, Asset, aid)
    assert derived.storage_provider == "obs"
    assert not Path(settings.storage_root, derived.storage_key).exists()
    with io.BytesIO(obs_memory.objects[derived.storage_key]) as stream:
        from PIL import Image

        with Image.open(stream) as image:
            assert image.size == (1000, 400)
    assert (await confirm(client, cid, headers, reviewed)).status_code == 200
    requests = []

    class Capture(video.FakeVideoProvider):
        async def submit(self, request, ctx):
            requests.append(request)
            return await super().submit(request, ctx)

    monkeypatch.setattr(
        "app.services.video_job_service.get_video_provider", lambda *args: Capture()
    )
    response = await submit(client, cid, headers, reviewed)
    assert response.status_code == 202, response.text
    served = await client.get(urlsplit(requests[0]["first_frame_url"]).path)
    assert served.status_code == 302
    assert served.headers["location"].endswith(derived.storage_key)
    # Provider receives the original object, never an OBS thumbnail transformation.
    assert "x-image-process" not in (
        obs_memory.sdk.createSignedUrl.call_args.kwargs["queryParams"] or {}
    )
    obs_memory.objects[derived.storage_key] = b"tampered image"
    assert (await confirm(client, cid, headers, reviewed)).status_code == 409


async def test_stale_review_cleans_only_new_obs_derivatives(client, monkeypatch, obs_memory):
    cid, headers, project, _ = await video.image_project(client)
    originals = set(obs_memory.objects)
    provider = ControlledProvider(blocked=True)
    monkeypatch.setattr("app.services.agent_service.get_vision_provider", lambda: provider)
    work = asyncio.create_task(
        client.post(
            f"/api/v1/conversations/{cid}/canvas/prepare-video",
            headers=headers,
            json={
                **preparation(["target"], project["canvas_version"]),
                "mode": "first_frame_to_video",
            },
        )
    )
    try:
        await asyncio.wait_for(provider.started.wait(), 5)
        assert set(obs_memory.objects) > originals
        document = project["canvas_data"]
        document["nodes"][0]["content"] = "changed during review"
        await save(client, cid, headers, project, document)
        provider.release.set()
        assert (await asyncio.wait_for(work, 5)).status_code == 409
        assert set(obs_memory.objects) == originals
    finally:
        provider.release.set()
        if not work.done():
            work.cancel()
            await asyncio.gather(work, return_exceptions=True)


async def test_obs_upload_failure_does_not_silently_write_local(client, obs_memory):
    await generation.register(client)
    cid = await generation.conversation(client)
    obs_memory.sdk.putContent.side_effect = RuntimeError("unavailable")
    response = await client.post(
        "/api/v1/image-reference-uploads",
        headers=generation.headers(client),
        data={"conversation_id": cid},
        files={"file": ("image.png", generation.original_png(), "image/png")},
    )
    assert response.status_code == 422
    assert not obs_memory.objects
    assert not [p for p in Path(settings.storage_root).rglob("*") if p.is_file()]


async def test_obs_result_failure_retries_storage_without_generating_again(
    client, db_engine, monkeypatch, obs_memory
):
    await generation.register(client)
    cid = await generation.conversation(client)
    raw = generation.original_png()
    remote = "https://images.example.invalid/original.png"
    provider = generation.mock_real(monkeypatch, url=remote)
    from unittest.mock import AsyncMock

    monkeypatch.setattr(
        "app.services.image_generation_service.download_image", AsyncMock(return_value=raw)
    )
    put = obs_memory.sdk.putContent.side_effect
    obs_memory.sdk.putContent.side_effect = RuntimeError("unavailable")
    job = await generation.create_job(client, cid)
    await generation.run_job(db_engine, job["id"])
    row = await generation.row_for(db_engine, ImageJob, job["id"])
    assert row.status == "storage_failed"
    obs_memory.sdk.putContent.side_effect = put
    response = await client.post(
        f"/api/v1/image-jobs/{job['id']}/retry-storage", headers=generation.headers(client)
    )
    assert response.status_code == 200, response.text
    await generation.run_job(db_engine, job["id"])
    row = await generation.row_for(db_engine, ImageJob, job["id"])
    assert row.status == "succeeded"
    provider.assert_awaited_once()
    asset = await generation.row_for(db_engine, Asset, job["id"])
    assert asset.storage_provider == "obs" and obs_memory.objects[asset.storage_key] == raw


def test_obs_bounded_reads_close_stream_and_reject_missing_objects(obs_memory):
    storage = ObsStorage()
    obs_memory.objects["large"] = b"12345"
    with pytest.raises(StorageError):
        storage.read_bytes("large", max_bytes=4)
    assert obs_memory.streams[-1].closed
    with pytest.raises(StorageError):
        storage.read_bytes("missing", max_bytes=4)


async def test_failed_derived_upload_is_not_recorded_as_ready(client, db_engine, obs_memory):
    from sqlmodel import select

    cid, headers, project, _ = await video.image_project(client)
    before = dict(obs_memory.objects)
    obs_memory.sdk.putContent.side_effect = RuntimeError("unavailable")
    reviewed = await prepare(client, cid, headers, project, mode="first_frame_to_video")
    assert reviewed["canvas_data"]["generation_review"]["status"] == "blocked"
    assert obs_memory.objects == before
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        rows = (await session.exec(select(Asset).where(Asset.purpose == "generation_input"))).all()
    assert rows == []


async def test_obs_prompt_suggestions_send_actual_image(client, db_engine, monkeypatch, obs_memory):
    from test_image_editing import (
        test_reference_suggestions_use_vision_with_image_and_selected_settings,
    )

    await test_reference_suggestions_use_vision_with_image_and_selected_settings(
        client, db_engine, monkeypatch
    )
    assert obs_memory.sdk.getObject.called


@pytest.mark.parametrize("size,valid", [((864, 1536), True), ((200, 200), False)])
async def test_generated_obs_original_is_preserved_for_video(
    client, db_engine, monkeypatch, obs_memory, size, valid
):
    from app.schemas.agent import VideoBrief
    from app.services.video_image_service import prepare_images
    from app.video_registry import get_profile

    raw = generation.original_png(size)
    generation.mock_real(monkeypatch, data=raw)
    await generation.register(client)
    job = await generation.create_job(client, await generation.conversation(client))
    await generation.run_job(db_engine, job["id"])
    asset = await generation.row_for(db_engine, Asset, job["id"])
    before = dict(obs_memory.objects)
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        bindings, notices, issues, pending = await prepare_images(
            session,
            asset.user_id,
            get_profile("ark_seedance_v1", "doubao-seedance-2-5"),
            VideoBrief(mode="reference_image_to_video", reference_asset_ids=[asset.id]),
            {},
        )
    assert not pending and not notices
    assert bool(issues) is not valid
    if valid:
        assert bindings[0]["asset_id"] == asset.id
        assert bindings[0]["sha256"] == hashlib.sha256(raw).hexdigest()
        assert not bindings[0]["actions"]
    else:
        assert not bindings
    assert obs_memory.objects == before


async def test_historical_local_images_readable_with_obs_enabled(
    client, db_engine, monkeypatch, obs_memory
):
    from app.api.v1.material_library import _serve_asset_response
    from app.services.material_library_service import MaterialLibraryService

    await generation.register(client)
    cid = await generation.conversation(client)
    monkeypatch.setattr(settings, "huawei_cloud_obs_bucket", "")
    raw = generation.original_png((400, 400))
    uploaded = await reference(client, cid, data=raw)
    asset = await generation.row_for(db_engine, Asset, uploaded["id"])
    monkeypatch.setattr(settings, "huawei_cloud_obs_bucket", "test-images")
    assert read_reference(asset)[0] == raw
    response = await client.get(uploaded["content_url"])
    assert response.status_code == 200 and response.content == raw
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        library_asset = await MaterialLibraryService(session)._asset(asset.id, "image")
    response = _serve_asset_response(library_asset, asset.storage_key)
    assert response.status_code == 200
    assert Path(response.path).read_bytes() == raw
    assert not obs_memory.sdk.getObject.called


async def test_cancel_during_obs_upload_waits_then_cleans_staged_object(
    client, monkeypatch, obs_memory
):
    import threading

    cid, headers, project, _ = await video.image_project(client)
    originals = set(obs_memory.objects)
    started, release = threading.Event(), threading.Event()
    original_put = obs_memory.sdk.putContent.side_effect

    def blocked_put(bucket, key, data):
        started.set()
        assert release.wait(5)
        return original_put(bucket, key, data)

    obs_memory.sdk.putContent.side_effect = blocked_put
    work = asyncio.create_task(
        client.post(
            f"/api/v1/conversations/{cid}/canvas/prepare-video",
            headers=headers,
            json={
                **preparation(["target"], project["canvas_version"]),
                "mode": "first_frame_to_video",
            },
        )
    )
    try:
        assert await asyncio.to_thread(started.wait, 5)
        work.cancel()
        await asyncio.sleep(0)
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await work
        assert set(obs_memory.objects) == originals
    finally:
        release.set()
        if not work.done():
            work.cancel()
            await asyncio.gather(work, return_exceptions=True)
