"""Image generation regressions. All providers are fake or mocked; network is forbidden."""

import asyncio
import hashlib
import io
import json
import uuid
from datetime import timedelta
from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import pytest
from app.core.config import Settings, settings
from app.core.security import decrypt_secret
from app.core.time import now
from app.db.models.asset import Asset
from app.db.models.image_generation import ImageApiConfig, ImageJob
from app.db.models.project import VideoProject, VideoProjectVersion
from app.db.models.video_job import VideoJob, VideoJobAsset
from app.providers.email.fake import fake_instance
from PIL import Image, PngImagePlugin
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

API = "/api/v1"
ORIGIN = "http://127.0.0.1:5173"
SECRET = "test-image-only-credential-123456"


@pytest.fixture(autouse=True)
def isolated_image_settings(monkeypatch):
    monkeypatch.setattr(settings, "image_provider", "fake")
    monkeypatch.setattr(settings, "image_worker_enabled", False)
    monkeypatch.setattr(settings, "image_platform_api_key", "")
    monkeypatch.setattr(settings, "image_platform_model", "doubao-seedream-5.0-pro")
    monkeypatch.setattr(settings, "app_env", "dev")
    monkeypatch.setattr(settings, "image_max_pending_per_user", 10)
    monkeypatch.setattr(settings, "image_platform_daily_limit", 20)
    original_send = httpx.AsyncClient.send

    async def local_only(self, request, *args, **kwargs):
        assert request.url.host == "testserver" or isinstance(
            self._transport, httpx.MockTransport
        ), "Tests must never call an external service"
        return await original_send(self, request, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "send", local_only)


def headers(client, key=None):
    result = {"X-CSRF-Token": client.cookies.get("hw_csrf", ""), "Origin": ORIGIN}
    if key is not None:
        result["Idempotency-Key"] = key
    return result


async def register(client):
    email = f"image-{uuid.uuid4().hex}@test.com"
    sent = await client.post(
        f"{API}/auth/email-codes", json={"email": email, "purpose": "register"}
    )
    assert sent.status_code == 202, sent.text
    response = await client.post(
        f"{API}/auth/register",
        json={"email": email, "code": fake_instance.sent[-1]["code"], "password": "password123"},
    )
    assert response.status_code == 201, response.text


async def conversation(client):
    response = await client.post(
        f"{API}/conversations", json={"title": "Image tests"}, headers=headers(client)
    )
    assert response.status_code == 201, response.text
    return response.json()["conversation"]["id"]


async def config(client, **changes):
    response = await client.post(
        f"{API}/image-api-configs",
        json={
            "display_name": "My image channel",
            "api_key": SECRET,
            "account_label": "Claimed account",
            **changes,
        },
        headers=headers(client),
    )
    assert response.status_code == 201, response.text
    return response.json()


async def create_job(client, cid, key=None, **changes):
    response = await client.post(
        f"{API}/image-jobs",
        json={
            "conversation_id": cid,
            "api_config_id": "platform",
            "prompt": "虚构成年人物，半身肖像",
            "aspect_ratio": "9:16",
            **changes,
        },
        headers=headers(client, key or str(uuid.uuid4())),
    )
    assert response.status_code == 201, response.text
    return response.json()


async def run_job(db_engine, jid):
    from app.services.image_generation_service import ImageGenerationService

    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        await ImageGenerationService(session).run(jid)


async def row_for(db_engine, model, ident):
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        return await session.get(model, ident)


def original_png(size=(864, 1536)):
    data = io.BytesIO()
    metadata = PngImagePlugin.PngInfo()
    metadata.add_text("source", "Keep this metadata and the exact original bytes")
    Image.new("RGB", size, "purple").save(data, format="PNG", pnginfo=metadata)
    return data.getvalue()


def mock_real(monkeypatch, **result):
    from app.providers.image.ark_plan import ImageResult

    monkeypatch.setattr(settings, "image_provider", "ark_plan")
    monkeypatch.setattr(settings, "image_platform_api_key", SECRET)
    generate = AsyncMock(return_value=ImageResult(**result))
    monkeypatch.setattr("app.services.image_generation_service.generate_image", generate)
    return generate


async def test_options_and_prompt_suggestions_do_not_create_jobs(client, db_engine):
    await register(client)
    cid = await conversation(client)
    options = await client.get(f"{API}/image-generation/options")
    assert options.status_code == 200, options.text
    assert "doubao-seedream-5.0-pro" in options.text
    response = await client.post(
        f"{API}/image-prompt-suggestions",
        json={"conversation_id": cid, "prompt": "写实成年虚构人物", "aspect_ratio": "9:16"},
        headers=headers(client),
    )
    assert response.status_code == 200, response.text
    factory = async_sessionmaker(db_engine, class_=AsyncSession)
    async with factory() as session:
        assert not (await session.exec(select(ImageJob))).all()


async def test_config_secret_encrypted_and_old_job_keeps_revision_snapshot(client, db_engine):
    await register(client)
    cid = await conversation(client)
    created = await config(client)
    stored = await row_for(db_engine, ImageApiConfig, created["id"])
    assert SECRET not in str(created)
    assert "encrypted_api_key" not in created and "api_key" not in created
    assert stored.encrypted_api_key != SECRET
    assert decrypt_secret(stored.encrypted_api_key, settings.credential_encryption_keys) == SECRET
    job = await create_job(client, cid, api_config_id=created["id"])
    patched = await client.patch(
        f"{API}/image-api-configs/{created['id']}",
        json={
            "expected_revision": created["revision"],
            "api_key": "replacement-test-key-87654321",
            "model": "doubao-seedream-5.0-flash",
        },
        headers=headers(client),
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["revision"] == created["revision"] + 1
    stale = await client.patch(
        f"{API}/image-api-configs/{created['id']}",
        json={"expected_revision": created["revision"], "display_name": "Stale edit"},
        headers=headers(client),
    )
    assert stale.status_code == 409, stale.text
    snap = await row_for(db_engine, ImageJob, job["id"])
    assert snap.config_revision == created["revision"]
    assert snap.model == "doubao-seedream-5.0-pro"
    assert decrypt_secret(snap.encrypted_api_key, settings.credential_encryption_keys) == SECRET
    assert "encrypted_api_key" not in job and SECRET not in str(job)
    deleted = await client.delete(
        f"{API}/image-api-configs/{created['id']}", headers=headers(client)
    )
    assert deleted.status_code == 204, deleted.text
    assert created["id"] not in (await client.get(f"{API}/image-api-configs")).text
    assert (await client.get(f"{API}/image-jobs/{job['id']}")).status_code == 200


async def test_mutations_require_csrf(client):
    await register(client)
    cid = await conversation(client)
    requests = [
        ("/image-api-configs", {"display_name": "Unsafe", "api_key": SECRET}),
        ("/image-jobs", {"conversation_id": cid, "prompt": "Hello"}),
        ("/image-prompt-suggestions", {"conversation_id": cid, "prompt": "Hello"}),
    ]
    for path, payload in requests:
        response = await client.post(f"{API}{path}", json=payload)
        assert response.status_code == 403, (path, response.text)


async def test_idempotency_replays_same_job_and_rejects_changed_payload(client, db_engine):
    await register(client)
    cid = await conversation(client)
    key = str(uuid.uuid4())
    first = await create_job(client, cid, key)
    same = await create_job(client, cid, key)
    assert same["id"] == first["id"]
    changed = await client.post(
        f"{API}/image-jobs",
        json={
            "conversation_id": cid,
            "api_config_id": "platform",
            "prompt": "Changed prompt",
            "aspect_ratio": "9:16",
        },
        headers=headers(client, key),
    )
    assert changed.status_code == 409, changed.text
    factory = async_sessionmaker(db_engine, class_=AsyncSession)
    async with factory() as session:
        assert len((await session.exec(select(ImageJob))).all()) == 1


async def test_concurrent_idempotent_create_inserts_one_job(client, db_engine):
    await register(client)
    cid = await conversation(client)
    key = str(uuid.uuid4())
    jobs = await asyncio.gather(create_job(client, cid, key), create_job(client, cid, key))
    assert jobs[0]["id"] == jobs[1]["id"]
    factory = async_sessionmaker(db_engine, class_=AsyncSession)
    async with factory() as session:
        assert len((await session.exec(select(ImageJob))).all()) == 1


async def test_owner_isolation_for_jobs_configs_and_conversation_listing(client):
    await register(client)
    cid = await conversation(client)
    owned_config = await config(client)
    job = await create_job(client, cid)
    owner_cookies = httpx.Cookies(client.cookies)
    client.cookies.clear()
    await register(client)
    other_cid = await conversation(client)
    assert (await client.get(f"{API}/image-api-configs")).json()["items"] == []
    denied = [
        await client.get(f"{API}/image-jobs/{job['id']}"),
        await client.get(f"{API}/image-jobs", params={"conversation_id": cid}),
        await client.post(f"{API}/image-jobs/{job['id']}/cancel", headers=headers(client)),
        await client.post(f"{API}/image-jobs/{job['id']}/retry-storage", headers=headers(client)),
        await client.delete(
            f"{API}/image-api-configs/{owned_config['id']}", headers=headers(client)
        ),
        await client.patch(
            f"{API}/image-api-configs/{owned_config['id']}",
            json={"expected_revision": 1, "display_name": "Stolen"},
            headers=headers(client),
        ),
        await client.post(
            f"{API}/image-jobs",
            json={
                "conversation_id": other_cid,
                "api_config_id": owned_config["id"],
                "prompt": "Unauthorized",
            },
            headers=headers(client, str(uuid.uuid4())),
        ),
        await client.post(
            f"{API}/image-prompt-suggestions",
            json={"conversation_id": cid, "prompt": "Unauthorized"},
            headers=headers(client),
        ),
    ]
    for response in denied:
        assert response.status_code == 404, response.text
    client.cookies.clear()
    client.cookies.update(owner_cookies)
    listed = await client.get(f"{API}/image-jobs", params={"conversation_id": cid})
    assert listed.status_code == 200, listed.text
    assert [item["id"] for item in listed.json()["items"]] == [job["id"]]


async def test_queued_cancel_prevents_generation(client, db_engine, monkeypatch):
    generate = mock_real(monkeypatch, data=original_png())
    await register(client)
    jid = (await create_job(client, await conversation(client)))["id"]
    canceled = await client.post(f"{API}/image-jobs/{jid}/cancel", headers=headers(client))
    assert canceled.status_code == 200, canceled.text
    assert canceled.json()["status"] == "cancelled"
    await run_job(db_engine, jid)
    assert generate.await_count == 0


async def test_fake_output_is_visibly_simulated_and_never_claims_trust(client, db_engine):
    await register(client)
    job = await create_job(client, await conversation(client))
    await run_job(db_engine, job["id"])
    final = (await client.get(f"{API}/image-jobs/{job['id']}")).json()
    assert final["status"] == "succeeded", final
    assert final["simulation"] is True
    asset = await row_for(db_engine, Asset, final["asset_id"])
    assert asset.storage_provider == "local"
    raw = Path(settings.storage_root, asset.storage_key).read_bytes()
    with Image.open(io.BytesIO(raw)) as image:
        assert image.format == "PNG"
    assert not final.get("same_account_verified", False)


async def test_historical_local_result_preserves_original_bytes_with_obs_configured(
    client, db_engine, monkeypatch
):
    original = original_png()
    generate = mock_real(monkeypatch, data=original, request_id="mock-provider-request")
    await register(client)
    cid = await conversation(client)
    job = await create_job(client, cid)
    await run_job(db_engine, job["id"])
    # Existing local originals remain readable after new uploads switch to OBS.
    from unittest.mock import Mock

    for key, value in {
        "huawei_cloud_obs_endpoint": "https://obs.invalid",
        "huawei_cloud_obs_bucket": "test-bucket",
        "huawei_cloud_obs_access_key": "test-only",
        "huawei_cloud_obs_secret_key": "test-only",
    }.items():
        monkeypatch.setattr(settings, key, value)
    sdk = Mock()
    monkeypatch.setattr("app.storage.obs.ObsClient", lambda **kwargs: sdk)
    final_response = await client.get(f"{API}/image-jobs/{job['id']}")
    final = final_response.json()
    assert final["status"] == "succeeded", final
    assert final["simulation"] is False
    generate.assert_awaited_once()
    assert generate.call_args.kwargs["size"] == "1152x2048"
    asset = await row_for(db_engine, Asset, final["asset_id"])
    assert asset.storage_provider == "local"
    assert asset.sha256 == hashlib.sha256(original).hexdigest()
    assert Path(settings.storage_root, asset.storage_key).read_bytes() == original
    for path in (
        f"/assets/{asset.id}/content?thumbnail=raw",
        f"/assets/{asset.id}/content?download=true",
    ):
        result = await client.get(f"{API}{path}")
        assert result.status_code == 200, (path, result.text)
        assert result.content == original
        assert "location" not in result.headers
    assert SECRET not in final_response.text
    # A signed video-provider request must also honor the asset's local storage provider.
    from app.services.provider_asset_url import sign_provider_asset

    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        project = (
            await session.exec(select(VideoProject).where(VideoProject.conversation_id == cid))
        ).one()
        version = (
            await session.exec(
                select(VideoProjectVersion).where(VideoProjectVersion.project_id == project.id)
            )
        ).first()
        video = VideoJob(
            user_id=asset.user_id,
            conversation_id=cid,
            project_id=project.id,
            project_version_id=version.id,
            project_version=version.version,
            idempotency_key=str(uuid.uuid4()),
            request_fingerprint="image-route-test",
            protocol_code="ark_seedance_v1",
            remote_model_id="mock-video",
            mode="reference_image_to_video",
            status="queued",
        )
        session.add(video)
        session.add(
            VideoJobAsset(video_job_id=video.id, asset_id=asset.id, role="reference", position=0)
        )
        await session.commit()
        token, _ = sign_provider_asset(asset.id, video.id, "reference", settings.app_secret, 600)
    provider = await client.get(f"{API}/provider-assets/{token}")
    assert provider.status_code == 200, provider.text
    assert provider.content == original and "location" not in provider.headers
    sdk.getObject.assert_not_called()
    sdk.putContent.assert_not_called()
    client.cookies.clear()
    await register(client)
    denied = await client.get(f"{API}/assets/{asset.id}/content")
    # Existing asset API uses ASSET_CONTENT_INVALID (422) for absent/foreign assets.
    assert denied.status_code == 422
    assert denied.json()["error"]["code"] == "ASSET_CONTENT_INVALID"


async def test_atomic_claim_calls_provider_once_for_concurrent_workers(
    client, db_engine, monkeypatch
):
    generate = mock_real(monkeypatch, data=original_png())
    original_result = generate.return_value

    async def delayed(**kwargs):
        await asyncio.sleep(0.03)
        return original_result

    generate.side_effect = delayed
    await register(client)
    job = await create_job(client, await conversation(client))
    await asyncio.gather(run_job(db_engine, job["id"]), run_job(db_engine, job["id"]))
    generate.assert_awaited_once()
    assert (await client.get(f"{API}/image-jobs/{job['id']}")).json()["status"] == "succeeded"


async def test_unknown_generation_timeout_is_not_automatically_retried(
    client, db_engine, monkeypatch
):
    generate = mock_real(monkeypatch)
    generate.side_effect = TimeoutError("Upstream outcome unknown")
    await register(client)
    job = await create_job(client, await conversation(client))
    await run_job(db_engine, job["id"])
    await run_job(db_engine, job["id"])
    generate.assert_awaited_once()
    final = (await client.get(f"{API}/image-jobs/{job['id']}")).json()
    assert final["status"] == "unknown", final
    retry = await client.post(
        f"{API}/image-jobs/{job['id']}/retry-storage", headers=headers(client)
    )
    assert retry.status_code == 409, retry.text
    generate.assert_awaited_once()


async def test_owner_acknowledges_unknown_without_regenerating_and_can_create_next_job(
    client, db_engine, monkeypatch
):
    generate = mock_real(monkeypatch)
    generate.side_effect = TimeoutError("Uncertain upstream outcome")
    monkeypatch.setattr(settings, "image_max_pending_per_user", 1)
    await register(client)
    cid = await conversation(client)
    job = await create_job(client, cid)
    await run_job(db_engine, job["id"])
    unknown = await row_for(db_engine, ImageJob, job["id"])
    assert unknown.status == "unknown"
    response = await client.post(
        f"{API}/image-jobs/{job['id']}/acknowledge-unknown", headers=headers(client)
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "unknown_acknowledged"
    stored = await row_for(db_engine, ImageJob, job["id"])
    assert stored.status == "unknown_acknowledged"
    assert stored.error_message == unknown.error_message
    assert stored.asset_id is None
    await run_job(db_engine, job["id"])
    generate.assert_awaited_once()
    next_job = await create_job(client, cid)
    assert next_job["id"] != job["id"] and next_job["status"] == "queued"
    generate.assert_awaited_once()


async def test_unknown_acknowledgement_requires_owner_and_csrf(client, db_engine, monkeypatch):
    generate = mock_real(monkeypatch)
    generate.side_effect = TimeoutError("Uncertain upstream outcome")
    await register(client)
    job = await create_job(client, await conversation(client))
    await run_job(db_engine, job["id"])
    owner_cookies = httpx.Cookies(client.cookies)
    client.cookies.clear()
    await register(client)
    url = f"{API}/image-jobs/{job['id']}/acknowledge-unknown"
    denied = await client.post(url, headers=headers(client))
    assert denied.status_code == 404, denied.text
    assert (await row_for(db_engine, ImageJob, job["id"])).status == "unknown"
    client.cookies.clear()
    client.cookies.update(owner_cookies)
    no_csrf = await client.post(url)
    assert no_csrf.status_code == 403, no_csrf.text
    assert (await row_for(db_engine, ImageJob, job["id"])).status == "unknown"
    generate.assert_awaited_once()


async def test_acknowledging_unknown_does_not_refund_platform_daily_quota(
    client, db_engine, monkeypatch
):
    generate = mock_real(monkeypatch)
    generate.side_effect = TimeoutError("Upstream may already have generated an image")
    monkeypatch.setattr(settings, "image_platform_daily_limit", 1)
    await register(client)
    cid = await conversation(client)
    job = await create_job(client, cid)
    await run_job(db_engine, job["id"])

    async def submit_next():
        return await client.post(
            f"{API}/image-jobs",
            json={"conversation_id": cid, "prompt": "A separate paid generation"},
            headers=headers(client, str(uuid.uuid4())),
        )

    before = await submit_next()
    assert before.status_code == 429, before.text
    acknowledged = await client.post(
        f"{API}/image-jobs/{job['id']}/acknowledge-unknown", headers=headers(client)
    )
    assert acknowledged.status_code == 200, acknowledged.text
    after = await submit_next()
    assert after.status_code == 429, after.text
    assert after.json()["error"]["code"] == "IMAGE_LIMIT"
    factory = async_sessionmaker(db_engine, class_=AsyncSession)
    async with factory() as session:
        rows = (await session.exec(select(ImageJob))).all()
        assert len(rows) == 1 and rows[0].status == "unknown_acknowledged"
    generate.assert_awaited_once()


@pytest.mark.parametrize("status", ["queued", "generating", "succeeded", "unknown_acknowledged"])
async def test_acknowledgement_rejects_non_unknown_without_state_change(
    client, db_engine, monkeypatch, status
):
    generate = mock_real(monkeypatch)
    await register(client)
    job = await create_job(client, await conversation(client))
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        row = await session.get(ImageJob, job["id"])
        row.status = status
        session.add(row)
        await session.commit()
    response = await client.post(
        f"{API}/image-jobs/{job['id']}/acknowledge-unknown", headers=headers(client)
    )
    assert response.status_code == 409, response.text
    assert response.json()["error"]["code"] == "IMAGE_CONFLICT"
    assert (await row_for(db_engine, ImageJob, job["id"])).status == status
    generate.assert_not_awaited()


@pytest.mark.parametrize("download_failure", ["io", "provider"])
async def test_storage_retry_downloads_existing_result_without_regeneration(
    client, db_engine, monkeypatch, download_failure
):
    from app.providers.image.ark_plan import ImageProviderError

    remote = "https://mock-result.invalid/image.png?secret=never-expose"
    generate = mock_real(monkeypatch, url=remote, request_id="storage-retry-test")
    failure = (
        OSError("Temporary download failure")
        if download_failure == "io"
        else ImageProviderError("Temporary result download failure", uncertain=True)
    )
    download = AsyncMock(side_effect=failure)
    monkeypatch.setattr("app.services.image_generation_service.download_image", download)
    await register(client)
    job = await create_job(client, await conversation(client))
    await run_job(db_engine, job["id"])
    failed_response = await client.get(f"{API}/image-jobs/{job['id']}")
    failed = failed_response.json()
    assert failed["status"] == "storage_failed", failed
    assert remote not in failed_response.text and "never-expose" not in failed_response.text
    snapshot = await row_for(db_engine, ImageJob, job["id"])
    assert snapshot.encrypted_result_url != remote
    assert (
        decrypt_secret(snapshot.encrypted_result_url, settings.credential_encryption_keys) == remote
    )
    original = original_png()
    download.side_effect = None
    download.return_value = original
    retry = await client.post(
        f"{API}/image-jobs/{job['id']}/retry-storage", headers=headers(client)
    )
    assert retry.status_code in {200, 202}, retry.text
    await run_job(db_engine, job["id"])
    final = (await client.get(f"{API}/image-jobs/{job['id']}")).json()
    assert final["status"] == "succeeded", final
    generate.assert_awaited_once()
    assert download.await_count == 2
    asset = await row_for(db_engine, Asset, final["asset_id"])
    assert Path(settings.storage_root, asset.storage_key).read_bytes() == original


async def test_expired_generation_lease_becomes_unknown_without_resubmission(
    client, db_engine, monkeypatch
):
    generate = mock_real(monkeypatch, data=original_png())
    await register(client)
    job = await create_job(client, await conversation(client))
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        row = await session.get(ImageJob, job["id"])
        row.status = "generating"
        row.lease_until = now() - timedelta(seconds=1)
        session.add(row)
        await session.commit()
        from app.services.image_generation_service import ImageGenerationService

        await ImageGenerationService(session).recover_expired()
    await run_job(db_engine, job["id"])
    generate.assert_not_awaited()
    assert (await client.get(f"{API}/image-jobs/{job['id']}")).json()["status"] == "unknown"


@pytest.mark.parametrize("stale_outcome", ["return", "provider_error", "cancel"])
async def test_expired_saving_claim_cannot_overwrite_new_worker_result(
    client, db_engine, monkeypatch, stale_outcome
):
    from app.providers.image.ark_plan import ImageProviderError
    from app.services.image_generation_service import ImageGenerationService

    old_bytes, winner_bytes = original_png(), original_png((800, 1424))
    generate = mock_real(monkeypatch, url="https://mock-result.invalid/lease-test.png")
    started, release = asyncio.Event(), asyncio.Event()
    download_calls = 0

    async def download(url):
        nonlocal download_calls
        download_calls += 1
        if download_calls == 1:
            started.set()
            await release.wait()
            if stale_outcome == "provider_error":
                raise ImageProviderError("Stale download failed", uncertain=True)
            return old_bytes
        return winner_bytes

    monkeypatch.setattr("app.services.image_generation_service.download_image", download)
    original_store = ImageGenerationService._store_original
    stores = []

    def store(row, data):
        stores.append(data)
        return original_store(row, data)

    monkeypatch.setattr(ImageGenerationService, "_store_original", staticmethod(store))
    await register(client)
    job = await create_job(client, await conversation(client))
    old_worker = asyncio.create_task(run_job(db_engine, job["id"]))
    try:
        await asyncio.wait_for(started.wait(), timeout=5)
        factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            row = await session.get(ImageJob, job["id"])
            assert row.status == "saving"
            row.lease_until = now() - timedelta(seconds=1)
            session.add(row)
            await session.commit()
        await run_job(db_engine, job["id"])
        winner = await row_for(db_engine, ImageJob, job["id"])
        assert winner.status == "succeeded"
        if stale_outcome == "cancel":
            old_worker.cancel()
            with pytest.raises(asyncio.CancelledError):
                await old_worker
        else:
            release.set()
            await old_worker
    finally:
        if not old_worker.done():
            old_worker.cancel()
            with pytest.raises(asyncio.CancelledError):
                await old_worker
    final = await row_for(db_engine, ImageJob, job["id"])
    assert final.status == "succeeded" and final.error_message is None
    assert final.asset_id == winner.asset_id and final.lease_until is None
    asset = await row_for(db_engine, Asset, final.asset_id)
    assert asset.sha256 == hashlib.sha256(winner_bytes).hexdigest()
    assert Path(settings.storage_root, asset.storage_key).read_bytes() == winner_bytes
    assert stores == [winner_bytes]
    async with factory() as session:
        assert len((await session.exec(select(Asset))).all()) == 1
    generate.assert_awaited_once()


@pytest.mark.parametrize("acknowledge", [False, True])
async def test_recovered_generation_claim_cannot_checkpoint_late_success(
    client, db_engine, monkeypatch, acknowledge
):
    from app.providers.image.ark_plan import ImageResult
    from app.services.image_generation_service import ImageGenerationService

    generate = mock_real(monkeypatch)
    started, release = asyncio.Event(), asyncio.Event()

    async def late_result(**kwargs):
        started.set()
        await release.wait()
        return ImageResult(data=original_png(), request_id="late-success")

    generate.side_effect = late_result
    await register(client)
    job = await create_job(client, await conversation(client))
    old_worker = asyncio.create_task(run_job(db_engine, job["id"]))
    try:
        await asyncio.wait_for(started.wait(), timeout=5)
        factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            row = await session.get(ImageJob, job["id"])
            row.lease_until = now() - timedelta(seconds=1)
            session.add(row)
            await session.commit()
            await ImageGenerationService(session).recover_expired()
        if acknowledge:
            response = await client.post(
                f"{API}/image-jobs/{job['id']}/acknowledge-unknown", headers=headers(client)
            )
            assert response.status_code == 200, response.text
        release.set()
        await old_worker
    finally:
        if not old_worker.done():
            old_worker.cancel()
            with pytest.raises(asyncio.CancelledError):
                await old_worker
    final = await row_for(db_engine, ImageJob, job["id"])
    assert final.status == ("unknown_acknowledged" if acknowledge else "unknown")
    assert final.asset_id is None and final.generated_at is None
    assert final.provider_request_id is None and final.lease_until is None
    async with factory() as session:
        assert not (await session.exec(select(Asset))).all()
    generate.assert_awaited_once()


@pytest.mark.parametrize("stage", ["generation", "download"])
async def test_worker_shutdown_keeps_generation_uncertainty_and_storage_retry_separate(
    client, db_engine, monkeypatch, stage
):
    generate = mock_real(monkeypatch, url="https://mock-result.invalid/original.png")
    started = asyncio.Event()
    download = AsyncMock(return_value=original_png())
    monkeypatch.setattr("app.services.image_generation_service.download_image", download)

    async def interrupted(**kwargs):
        started.set()
        await asyncio.Event().wait()

    async def interrupted_download(url):
        started.set()
        await asyncio.Event().wait()

    if stage == "generation":
        generate.side_effect = interrupted
    else:
        download.side_effect = interrupted_download
    await register(client)
    job = await create_job(client, await conversation(client))
    worker = asyncio.create_task(run_job(db_engine, job["id"]))
    await asyncio.wait_for(started.wait(), timeout=5)
    worker.cancel()
    with pytest.raises(asyncio.CancelledError):
        await worker
    final = (await client.get(f"{API}/image-jobs/{job['id']}")).json()
    assert final["status"] == ("unknown" if stage == "generation" else "storage_failed"), final
    await run_job(db_engine, job["id"])
    generate.assert_awaited_once()
    if stage == "download":
        download.side_effect = None
        retried = await client.post(
            f"{API}/image-jobs/{job['id']}/retry-storage", headers=headers(client)
        )
        assert retried.status_code == 200, retried.text
        await run_job(db_engine, job["id"])
        assert (await client.get(f"{API}/image-jobs/{job['id']}")).json()["status"] == "succeeded"
        generate.assert_awaited_once()


async def test_user_declared_account_link_never_claims_verified_provenance(client, db_engine):
    await register(client)
    cid = await conversation(client)
    from test_video_api_config import _create_payload

    video = await client.post(
        f"{API}/video-api-configs", json=_create_payload(), headers=headers(client)
    )
    assert video.status_code == 201, video.text
    created = await config(
        client,
        linked_video_api_config_id=video.json()["id"],
        account_label="Arbitrary claim, not proof",
    )
    job = await create_job(client, cid, api_config_id=created["id"])
    await run_job(db_engine, job["id"])
    final = (await client.get(f"{API}/image-jobs/{job['id']}")).json()
    assert final["linked_video_api_config_id"] == video.json()["id"]
    assert final["provenance_notice"] == ""
    assert not any("verified" in key for key in final)
    assert SECRET not in json.dumps(final)


@pytest.mark.parametrize("size,valid", [((864, 1536), True), ((200, 200), False)])
async def test_generated_video_inputs_are_preserved_or_blocked_without_adapting(
    client, db_engine, monkeypatch, size, valid
):
    from app.schemas.agent import VideoBrief
    from app.services.video_image_service import prepare_images
    from app.video_registry import get_profile

    original = original_png(size)
    mock_real(monkeypatch, data=original)
    await register(client)
    job = await create_job(client, await conversation(client))
    await run_job(db_engine, job["id"])
    final = (await client.get(f"{API}/image-jobs/{job['id']}")).json()
    asset = await row_for(db_engine, Asset, final["asset_id"])

    def forbid_adaptation(*args, **kwargs):
        pytest.fail("Generated originals must never pass through image adaptation")

    monkeypatch.setattr("app.services.video_image_service.adapt_image", forbid_adaptation)
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        bindings, notices, issues, pending = await prepare_images(
            session,
            asset.user_id,
            get_profile("ark_seedance_v1", "doubao-seedance-2-5"),
            VideoBrief(mode="reference_image_to_video", reference_asset_ids=[asset.id]),
            {asset.id: "Generated portrait"},
        )
    assert not pending and not notices
    if valid:
        assert not issues
        assert bindings[0]["asset_id"] == asset.id
        assert bindings[0]["sha256"] == hashlib.sha256(original).hexdigest()
        assert bindings[0]["actions"] == []
    else:
        assert issues and not bindings
        assert "不会自动改图" in issues[0]
    assert Path(settings.storage_root, asset.storage_key).read_bytes() == original


async def test_missing_real_platform_key_reports_unavailable_without_fake_fallback(
    client, monkeypatch, db_engine
):
    monkeypatch.setattr(settings, "image_provider", "ark_plan")
    await register(client)
    cid = await conversation(client)
    options = (await client.get(f"{API}/image-generation/options")).json()
    assert options["platform"]["available"] is False and options["simulation"] is False
    response = await client.post(
        f"{API}/image-jobs",
        json={"conversation_id": cid, "prompt": "Portrait"},
        headers=headers(client, str(uuid.uuid4())),
    )
    assert response.status_code == 503, response.text
    factory = async_sessionmaker(db_engine, class_=AsyncSession)
    async with factory() as session:
        assert not (await session.exec(select(ImageJob))).all()


async def test_production_api_rejects_fake_jobs(client, monkeypatch):
    await register(client)
    cid = await conversation(client)
    monkeypatch.setattr(settings, "app_env", "production")
    response = await client.post(
        f"{API}/image-jobs",
        json={"conversation_id": cid, "prompt": "Portrait"},
        headers=headers(client, str(uuid.uuid4())),
    )
    assert response.status_code == 503, response.text


async def test_concurrent_quota_checks_allow_only_one_new_pending_job(
    client, monkeypatch, db_engine
):
    await register(client)
    cid = await conversation(client)
    monkeypatch.setattr(settings, "image_max_pending_per_user", 1)

    async def submit():
        return await client.post(
            f"{API}/image-jobs",
            json={"conversation_id": cid, "prompt": "Portrait"},
            headers=headers(client, str(uuid.uuid4())),
        )

    responses = await asyncio.gather(submit(), submit())
    assert sorted(response.status_code for response in responses) == [201, 429]
    factory = async_sessionmaker(db_engine, class_=AsyncSession)
    async with factory() as session:
        assert len((await session.exec(select(ImageJob))).all()) == 1


def test_production_forbids_fake_image_provider():
    configured = Settings(_env_file=None, app_env="production", image_provider="fake")
    with pytest.raises(RuntimeError, match="模拟生图"):
        configured.ensure_secure()


@pytest.mark.parametrize("result_format", ["url", "b64_json"])
async def test_adapter_uses_only_plan_endpoint_and_parses_both_result_formats(
    monkeypatch, result_format
):
    import base64

    from app.providers.image.ark_plan import ENDPOINT, generate_image

    seen = []
    original = original_png()
    item = (
        {"url": "https://example.tos-cn-beijing.volces.com/original.png"}
        if result_format == "url"
        else {"b64_json": base64.b64encode(original).decode()}
    )

    async def handle(request):
        seen.append(request)
        assert str(request.url) == ENDPOINT
        assert request.headers["Authorization"] == f"Bearer {SECRET}"
        body = json.loads(request.content)
        assert body["model"] == "doubao-seedream-5.0-pro"
        assert body["size"] == "1152x2048"
        assert body["output_format"] == "png"
        assert "ratio" not in body and "n" not in body
        return httpx.Response(200, json={"data": [item]}, headers={"x-request-id": "mock-id"})

    original_init = httpx.AsyncClient.__init__

    def init_with_transport(self, *args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handle)
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", init_with_transport)
    result = await generate_image(
        api_key=SECRET, model="doubao-seedream-5.0-pro", prompt="Portrait", size="1152x2048"
    )
    assert len(seen) == 1
    assert result.request_id == "mock-id"
    if result_format == "url":
        assert result.url == item["url"] and result.data is None
    else:
        assert result.data == original and result.url is None


@pytest.mark.parametrize("failure", ["timeout", "server_error", "invalid_json"])
async def test_adapter_uncertain_failures_never_retry_or_fall_back(monkeypatch, failure):
    from app.providers.image.ark_plan import ENDPOINT, ImageProviderError, generate_image

    calls = []

    async def handle(request):
        calls.append(str(request.url))
        if failure == "timeout":
            raise httpx.ReadTimeout("mock timeout", request=request)
        if failure == "server_error":
            return httpx.Response(503, text="do not expose upstream diagnostics")
        return httpx.Response(200, text="not JSON")

    original_init = httpx.AsyncClient.__init__

    def init_with_transport(self, *args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handle)
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", init_with_transport)
    with pytest.raises(ImageProviderError) as raised:
        await generate_image(
            api_key=SECRET, model="doubao-seedream-5.0-pro", prompt="Portrait", size="1152x2048"
        )
    assert raised.value.uncertain is True
    assert SECRET not in str(raised.value)
    assert calls == [ENDPOINT]


@pytest.mark.parametrize(
    "url",
    [
        "http://example.volces.com/image.png",
        "https://volces.com.attacker.invalid/image.png",
        "https://user:pass@example.volces.com/image.png",
        "https://127.0.0.1/image.png",
        "https://example.volces.com:8443/image.png",
    ],
)
async def test_download_rejects_unsafe_or_non_ark_urls_before_network(url):
    from app.providers.image.ark_plan import download_image

    with pytest.raises(ValueError):
        await download_image(url)
