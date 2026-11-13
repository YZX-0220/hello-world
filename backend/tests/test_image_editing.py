"""Image editing regressions; every provider is mocked and external HTTP is forbidden."""

from base64 import b64encode
from hashlib import sha256
from io import BytesIO
from json import dumps as json_dumps
from json import loads as json_loads
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

from alembic import command
from alembic.config import Config
from app.core.config import settings
from app.core.time import now
from app.db.models.asset import Asset
from app.db.models.image_generation import ImageJob
from app.providers.text.base import TextProviderError, TextResult
from httpx import AsyncClient, MockTransport, Response
from PIL import Image
from pytest import fixture as pytest_fixture
from pytest import mark
from sqlalchemy import MetaData, Table, create_engine, select
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession

from test_image_generation import (
    API,
    SECRET,
    config,
    conversation,
    create_job,
    headers,
    mock_real,
    original_png,
    register,
    row_for,
    run_job,
)


@pytest_fixture(autouse=True)
def isolated_editing_settings(monkeypatch):
    monkeypatch.setattr(settings, "image_provider", "fake")
    monkeypatch.setattr(settings, "image_worker_enabled", False)
    monkeypatch.setattr(settings, "image_platform_api_key", "")
    monkeypatch.setattr(settings, "image_platform_model", "doubao-seedream-5.0-pro")
    monkeypatch.setattr(settings, "app_env", "dev")
    monkeypatch.setattr(settings, "image_max_pending_per_user", 20)
    monkeypatch.setattr(settings, "image_platform_daily_limit", 30)
    original_send = AsyncClient.send

    async def local_only(self, request, *args, **kwargs):
        assert request.url.host == "testserver" or isinstance(self._transport, MockTransport), (
            "Editing tests must never call external services"
        )
        return await original_send(self, request, *args, **kwargs)

    monkeypatch.setattr(AsyncClient, "send", local_only)


async def upload(client, cid, data=None, name="reference.png", mime="image/png"):
    return await client.post(
        f"{API}/image-reference-uploads",
        data={"conversation_id": cid},
        files={"file": (name, original_png((64, 48)) if data is None else data, mime)},
        headers=headers(client),
    )


async def reference(client, cid, **kwargs):
    response = await upload(client, cid, **kwargs)
    assert response.status_code == 201, response.text
    return response.json()


async def post_job(client, cid, **changes):
    return await client.post(
        f"{API}/image-jobs",
        json={
            "conversation_id": cid,
            "prompt": "保持虚构成年人物面貌，把外套改成蓝色",
            **changes,
        },
        headers=headers(client, str(uuid4())),
    )


async def update_row(db_engine, model, ident, **values):
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        row = await session.get(model, ident)
        for key, value in values.items():
            setattr(row, key, value)
        session.add(row)
        await session.commit()


def data_url(raw, mime="image/png"):
    return f"data:{mime};base64,{b64encode(raw).decode()}"


@mark.parametrize(
    "image_format,mime,name",
    [("PNG", "image/png", "原图.png"), ("JPEG", "image/jpeg", "portrait.jpg")],
)
async def test_reference_upload_preserves_original_bytes_and_owner_access(
    client, db_engine, image_format, mime, name
):
    await register(client)
    cid = await conversation(client)
    stream = BytesIO()
    Image.new("RGB", (73, 51), "orange").save(stream, image_format)
    raw = stream.getvalue()
    uploaded = await reference(client, cid, data=raw, name=name, mime=mime)
    assert uploaded["original_name"] == name
    assert (uploaded["width"], uploaded["height"]) == (73, 51)
    asset = await row_for(db_engine, Asset, uploaded["id"])
    assert asset.status == "ready"
    assert asset.conversation_id == cid
    assert asset.sha256 == sha256(raw).hexdigest()
    assert asset.storage_provider == "local"
    assert Path(settings.storage_root, asset.storage_key).read_bytes() == raw
    response = await client.get(uploaded["content_url"])
    assert response.status_code == 200, response.text
    assert response.content == raw
    await register(client)
    forbidden = await client.get(uploaded["content_url"])
    assert forbidden.status_code in (403, 404, 422), forbidden.text
    assert forbidden.json()["error"]["code"] in ("ASSET_NOT_FOUND", "ASSET_CONTENT_INVALID")


async def test_reference_upload_uses_local_when_obs_is_not_configured(
    client, db_engine, monkeypatch
):
    await register(client)
    cid = await conversation(client)
    monkeypatch.setattr(settings, "huawei_cloud_obs_bucket", "")
    uploaded = await reference(client, cid)
    asset = await row_for(db_engine, Asset, uploaded["id"])
    assert asset.storage_provider == "local"
    assert Path(settings.storage_root, asset.storage_key).is_file()


async def test_reference_upload_requires_login_and_csrf(client):
    response = await upload(client, str(uuid4()))
    assert response.status_code in (401, 403)
    await register(client)
    cid = await conversation(client)
    response = await client.post(
        f"{API}/image-reference-uploads",
        data={"conversation_id": cid},
        files={"file": ("reference.png", original_png((32, 32)), "image/png")},
    )
    assert response.status_code == 403, response.text


async def test_reference_upload_rejects_another_users_conversation(client):
    await register(client)
    foreign_cid = await conversation(client)
    await register(client)
    response = await upload(client, foreign_cid)
    assert response.status_code in (403, 404), response.text


@mark.parametrize(
    "raw,name,mime",
    [
        (b"not an image", "fake.png", "image/png"),
        (b"<svg xmlns='http://www.w3.org/2000/svg'/>", "image.svg", "image/svg+xml"),
        (b"", "empty.jpg", "image/jpeg"),
    ],
)
async def test_reference_upload_rejects_malformed_and_unsupported_images(client, raw, name, mime):
    await register(client)
    cid = await conversation(client)
    response = await upload(client, cid, data=raw, name=name, mime=mime)
    assert response.status_code in (413, 415, 422), response.text


async def test_reference_upload_rejects_unsupported_decodable_format(client):
    await register(client)
    cid = await conversation(client)
    stream = BytesIO()
    Image.new("RGB", (32, 32), "red").save(stream, "GIF")
    response = await upload(
        client, cid, data=stream.getvalue(), name="renamed.png", mime="image/png"
    )
    assert response.status_code in (415, 422), response.text


async def test_reference_upload_enforces_byte_and_decoded_pixel_limits(client, monkeypatch):
    await register(client)
    cid = await conversation(client)
    monkeypatch.setattr(settings, "image_max_bytes", 128)
    response = await upload(client, cid, data=original_png((128, 128)))
    assert response.status_code in (413, 422), response.text
    monkeypatch.setattr(settings, "image_max_bytes", 10 * 1024 * 1024)
    monkeypatch.setattr(settings, "image_max_pixels", 1000)
    response = await upload(client, cid, data=original_png((32, 32)))
    assert response.status_code in (413, 422), response.text


async def test_reference_reuse_across_own_conversations_but_not_accounts(client):
    await register(client)
    cid = await conversation(client)
    uploaded = await reference(client, cid)
    other_cid = await conversation(client)
    response = await post_job(client, other_cid, reference_asset_ids=[uploaded["id"]])
    assert response.status_code == 201, response.text
    assert response.json()["reference_images"][0]["asset_id"] == uploaded["id"]
    await register(client)
    response = await post_job(
        client, await conversation(client), reference_asset_ids=[uploaded["id"]]
    )
    assert response.status_code in (403, 404, 422), response.text


async def test_parent_must_belong_to_same_user_and_conversation(client, db_engine):
    await register(client)
    cid = await conversation(client)
    parent = await create_job(client, cid)
    await run_job(db_engine, parent["id"])
    response = await post_job(client, await conversation(client), parent_job_id=parent["id"])
    assert response.status_code in (404, 422), response.text
    await register(client)
    response = await post_job(client, await conversation(client), parent_job_id=parent["id"])
    assert response.status_code in (403, 404, 422), response.text


@mark.parametrize("status", ["queued", "generating", "failed", "unknown", "cancelled"])
async def test_parent_must_have_successful_saved_output(client, db_engine, status):
    await register(client)
    cid = await conversation(client)
    parent = await create_job(client, cid)
    await update_row(db_engine, ImageJob, parent["id"], status=status)
    response = await post_job(client, cid, parent_job_id=parent["id"])
    assert response.status_code in (409, 422), response.text


async def test_successful_parent_without_asset_is_rejected(client, db_engine):
    await register(client)
    cid = await conversation(client)
    parent = await create_job(client, cid)
    await update_row(db_engine, ImageJob, parent["id"], status="succeeded", asset_id=None)
    response = await post_job(client, cid, parent_job_id=parent["id"])
    assert response.status_code in (409, 422), response.text


async def test_parent_is_first_reference_and_is_deduplicated(client, db_engine):
    await register(client)
    cid = await conversation(client)
    uploaded = await reference(client, cid)
    parent = await create_job(client, cid)
    await run_job(db_engine, parent["id"])
    parent_row = await row_for(db_engine, ImageJob, parent["id"])
    child = await create_job(
        client,
        cid,
        parent_job_id=parent["id"],
        reference_asset_ids=[uploaded["id"], parent_row.asset_id, uploaded["id"]],
    )
    assert child["parent_job_id"] == parent["id"]
    assert child["watermark"] is False
    assert [item["asset_id"] for item in child["reference_images"]] == [
        parent_row.asset_id,
        uploaded["id"],
    ]
    for item in child["reference_images"]:
        assert item["content_url"] and item["original_name"]
        assert "storage_key" not in item and "sha256" not in item
    stored = await row_for(db_engine, ImageJob, child["id"])
    snapshot = json_loads(stored.reference_images_json)
    assert len(snapshot) == 2
    assert sha256(original_png((64, 48))).hexdigest() in stored.reference_images_json


async def test_parent_plus_references_cannot_exceed_four_images(client, db_engine):
    await register(client)
    cid = await conversation(client)
    refs = [await reference(client, cid, data=original_png((40 + i, 40))) for i in range(5)]
    response = await post_job(client, cid, reference_asset_ids=[ref["id"] for ref in refs])
    assert response.status_code == 422, response.text
    parent = await create_job(client, cid)
    await run_job(db_engine, parent["id"])
    response = await post_job(
        client, cid, parent_job_id=parent["id"], reference_asset_ids=[ref["id"] for ref in refs[:4]]
    )
    assert response.status_code == 422, response.text


async def test_two_edit_rounds_send_previous_original_image_and_prior_text(
    client, db_engine, monkeypatch
):
    await register(client)
    cid = await conversation(client)
    first_bytes = original_png((90, 120))
    generate = mock_real(monkeypatch, data=first_bytes)
    parent = await create_job(client, cid, prompt="虚构成年男子，白色衬衫，背景为绿色花园")
    await run_job(db_engine, parent["id"])
    assert generate.call_args.kwargs["watermark"] is False
    second_bytes = original_png((100, 140))
    generate.return_value.data = second_bytes
    child = await create_job(
        client, cid, parent_job_id=parent["id"], prompt="保持其他细节，把衬衫改为蓝色"
    )
    await run_job(db_engine, child["id"])
    assert generate.call_args.kwargs["images"] == [data_url(first_bytes)]
    assert "白色衬衫" in generate.call_args.kwargs["prompt"]
    assert "蓝色" in generate.call_args.kwargs["prompt"]
    final = await create_job(
        client, cid, parent_job_id=child["id"], prompt="背景改成海边", watermark=True
    )
    await run_job(db_engine, final["id"])
    kwargs = generate.call_args.kwargs
    assert kwargs["images"][0] == data_url(second_bytes)
    assert kwargs["watermark"] is True
    assert "蓝色" in kwargs["prompt"] and "海边" in kwargs["prompt"]
    assert generate.await_count == 3
    stored = await row_for(db_engine, ImageJob, final["id"])
    assert stored.status == "succeeded"
    assert stored.compiled_prompt == kwargs["prompt"]
    assert json_loads(stored.edit_context_json)


async def test_uploaded_jpeg_and_png_reach_worker_as_original_data_urls(
    client, db_engine, monkeypatch
):
    await register(client)
    cid = await conversation(client)
    jpeg_buffer = BytesIO()
    Image.new("RGB", (48, 64), "gold").save(jpeg_buffer, "JPEG")
    jpeg = jpeg_buffer.getvalue()
    png = original_png((64, 48))
    uploaded_jpeg = await reference(client, cid, data=jpeg, name="original.jpg", mime="image/jpeg")
    uploaded_png = await reference(client, cid, data=png)
    generate = mock_real(monkeypatch, data=original_png())
    job = await create_job(
        client,
        cid,
        reference_asset_ids=[uploaded_jpeg["id"], uploaded_png["id"]],
        watermark=True,
    )
    await run_job(db_engine, job["id"])
    generate.assert_awaited_once()
    assert generate.call_args.kwargs["images"] == [data_url(jpeg, "image/jpeg"), data_url(png)]
    assert generate.call_args.kwargs["watermark"] is True


@mark.parametrize(
    "damage",
    [
        "changed_bytes",
        "changed_bytes_and_hash",
        "missing_file",
        "deleted",
        "not_ready",
        "changed_owner",
    ],
)
async def test_reference_integrity_failures_stop_before_provider(
    client, db_engine, monkeypatch, damage
):
    await register(client)
    cid = await conversation(client)
    uploaded = await reference(client, cid)
    generate = mock_real(monkeypatch, data=original_png())
    job = await create_job(client, cid, reference_asset_ids=[uploaded["id"]])
    asset = await row_for(db_engine, Asset, uploaded["id"])
    path = Path(settings.storage_root, asset.storage_key)
    if damage in ("changed_bytes", "changed_bytes_and_hash"):
        replacement = original_png((41, 43))
        path.write_bytes(replacement)
        if damage == "changed_bytes_and_hash":
            await update_row(
                db_engine,
                Asset,
                asset.id,
                sha256=sha256(replacement).hexdigest(),
                size_bytes=len(replacement),
                width=41,
                height=43,
            )
    elif damage == "missing_file":
        path.unlink()
    elif damage == "deleted":
        await update_row(db_engine, Asset, asset.id, deleted_at=now())
    elif damage == "not_ready":
        await update_row(db_engine, Asset, asset.id, status="uploading")
    else:
        await register(client)
        other = await reference(client, await conversation(client))
        other_asset = await row_for(db_engine, Asset, other["id"])
        await update_row(db_engine, Asset, asset.id, user_id=other_asset.user_id)
    await run_job(db_engine, job["id"])
    stored = await row_for(db_engine, ImageJob, job["id"])
    assert stored.status == "failed", stored.error_message
    assert stored.error_message
    generate.assert_not_awaited()


@mark.parametrize("field", ["reference_asset_ids", "parent_job_id", "watermark"])
async def test_idempotency_includes_edit_inputs(client, db_engine, field):
    await register(client)
    cid = await conversation(client)
    ref = await reference(client, cid)
    parent = await create_job(client, cid)
    await run_job(db_engine, parent["id"])
    key = str(uuid4())
    first = await create_job(client, cid, key)
    same = await create_job(client, cid, key)
    assert same["id"] == first["id"]
    values = {"reference_asset_ids": [ref["id"]], "parent_job_id": parent["id"], "watermark": True}
    response = await client.post(
        f"{API}/image-jobs",
        json={
            "conversation_id": cid,
            "api_config_id": "platform",
            "prompt": "虚构成年人物，半身肖像",
            "aspect_ratio": "9:16",
            field: values[field],
        },
        headers=headers(client, key),
    )
    assert response.status_code == 409, response.text


@mark.parametrize("watermark", [False, True])
async def test_image_adapter_serializes_original_references_and_watermark(monkeypatch, watermark):
    from app.providers.image.ark_plan import ENDPOINT, generate_image

    raw = original_png((44, 60))
    refs = [data_url(raw)]
    bodies = []

    async def handle(request):
        assert str(request.url) == ENDPOINT
        assert request.headers["Authorization"] == f"Bearer {SECRET}"
        bodies.append(json_loads(request.content))
        return Response(200, json={"data": [{"b64_json": b64encode(raw).decode()}]})

    original_init = AsyncClient.__init__

    def init_with_transport(self, *args, **kwargs):
        kwargs["transport"] = MockTransport(handle)
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(AsyncClient, "__init__", init_with_transport)
    result = await generate_image(
        api_key=SECRET,
        model="doubao-seedream-5.0-flash",
        prompt="蓝色外套",
        size="1536x1536",
        images=refs,
        watermark=watermark,
    )
    assert result.data == raw
    assert len(bodies) == 1
    assert bodies[0]["image"] == refs
    assert bodies[0]["watermark"] is watermark
    assert bodies[0]["model"] == "doubao-seedream-5.0-flash"
    assert bodies[0]["size"] == "1536x1536"


async def test_text_only_jobs_keep_compatible_defaults(client, db_engine, monkeypatch):
    await register(client)
    cid = await conversation(client)
    generate = mock_real(monkeypatch, data=original_png())
    job = await create_job(client, cid)
    assert job["reference_images"] == []
    assert job["parent_job_id"] is None
    assert job["watermark"] is False
    await run_job(db_engine, job["id"])
    assert not generate.call_args.kwargs.get("images")
    assert generate.call_args.kwargs["watermark"] is False
    response = await client.get(f"{API}/image-jobs/{job['id']}")
    assert response.status_code == 200
    assert response.json()["status"] == "succeeded"


async def test_legacy_draft_fingerprint_replays_original_watermarked_job(
    client, db_engine, monkeypatch
):
    await register(client)
    cid = await conversation(client)
    generate = mock_real(monkeypatch, data=original_png())
    key = str(uuid4())
    job = await create_job(client, cid, key)
    legacy_request = {
        "conversation_id": cid,
        "api_config_id": "platform",
        "prompt": "虚构成年人物，半身肖像",
        "aspect_ratio": "9:16",
        "source_node_id": None,
    }
    fingerprint = sha256(
        json_dumps(legacy_request, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()
    await update_row(
        db_engine,
        ImageJob,
        job["id"],
        request_fingerprint=fingerprint,
        watermark=True,
        compiled_prompt="",
    )
    replayed = await create_job(client, cid, key)
    assert replayed["id"] == job["id"]
    assert replayed["watermark"] is True
    stored = await row_for(db_engine, ImageJob, job["id"])
    assert stored.request_fingerprint == fingerprint
    assert stored.watermark is True
    changed = await client.post(
        f"{API}/image-jobs",
        json={**legacy_request, "watermark": True},
        headers=headers(client, key),
    )
    assert changed.status_code == 409, changed.text
    await run_job(db_engine, replayed["id"])
    generate.assert_awaited_once()
    assert generate.call_args.kwargs["watermark"] is True
    assert generate.call_args.kwargs["prompt"] == legacy_request["prompt"]


def test_migration_preserves_watermark_for_existing_jobs(tmp_path, monkeypatch):
    """The legacy adapter always requested a watermark; migration must keep that fact."""
    database_url = f"sqlite:///{tmp_path / 'legacy-images.db'}"
    monkeypatch.setattr(settings, "database_url", database_url)
    cfg = Config("alembic.ini")
    command.upgrade(cfg, "d5e6f7a8b9c0")
    engine = create_engine(database_url)
    old_jobs = Table("image_jobs", MetaData(), autoload_with=engine)
    with engine.begin() as connection:
        connection.execute(
            old_jobs.insert().values(
                id="legacy-image-job",
                user_id="legacy-user",
                conversation_id="legacy-conversation",
                api_config_id="platform",
                config_revision=1,
                channel_label="Legacy",
                account_label="",
                model="doubao-seedream-5.0-pro",
                prompt="Historical portrait",
                aspect_ratio="1:1",
                size="1536x1536",
                idempotency_key="legacy-request-key",
                request_fingerprint="a" * 64,
                encrypted_api_key="historical-ciphertext",
                status="succeeded",
                simulation=False,
                created_at=now(),
                updated_at=now(),
            )
        )
    command.upgrade(cfg, "head")
    migrated = Table("image_jobs", MetaData(), autoload_with=engine)
    with engine.connect() as connection:
        row = connection.execute(select(migrated)).mappings().one()
    engine.dispose()
    assert row["id"] == "legacy-image-job"
    assert row["prompt"] == "Historical portrait"
    assert row["watermark"] is True
    assert row["parent_job_id"] is None
    assert json_loads(row["reference_images_json"]) == []
    assert row["compiled_prompt"] in (None, "", "Historical portrait")


async def test_reference_suggestions_use_vision_with_image_and_selected_settings(
    client, db_engine, monkeypatch
):
    await register(client)
    cid = await conversation(client)
    raw = original_png((64, 48))
    uploaded = await reference(client, cid, data=raw)
    selected = await config(client, model="doubao-seedream-5.0-flash")
    generate = AsyncMock(
        return_value=TextResult(
            structured={
                "suggested_prompt": "保留人物特征，将背景替换为安静的海边，柔和自然光。",
                "explanation": "保留参考图人物，修改背景。",
            }
        )
    )
    monkeypatch.setattr("app.services.image_generation_service.vision_available", lambda: True)
    monkeypatch.setattr(
        "app.services.image_generation_service.get_vision_provider",
        lambda: SimpleNamespace(generate=generate),
    )
    text_provider = Mock(
        side_effect=AssertionError("Image suggestions must use the vision provider")
    )
    monkeypatch.setattr("app.services.image_generation_service.get_text_provider", text_provider)
    response = await client.post(
        f"{API}/image-prompt-suggestions",
        json={
            "conversation_id": cid,
            "api_config_id": selected["id"],
            "prompt": "背景换成海边",
            "aspect_ratio": "16:9",
            "watermark": True,
            "reference_asset_ids": [uploaded["id"]],
        },
        headers=headers(client),
    )
    assert response.status_code == 200, response.text
    assert response.json()["suggested_prompt"].startswith("保留人物特征")
    generate.assert_awaited_once()
    messages = generate.call_args.args[0]
    assert any(isinstance(message["content"], list) for message in messages)
    serialized = json_dumps(messages, ensure_ascii=False)
    assert data_url(raw) in serialized
    assert "doubao-seedream-5.0-flash" in serialized
    assert "16:9" in serialized and "2048x1152" in serialized
    assert "水印" in serialized or "watermark" in serialized
    assert "true" in serialized.lower() or "开启" in serialized or "启用" in serialized
    text_provider.assert_not_called()
    from sqlmodel import select as sqlmodel_select

    factory = async_sessionmaker(db_engine, class_=AsyncSession)
    async with factory() as session:
        assert not (await session.exec(sqlmodel_select(ImageJob))).all()


async def test_reference_suggestion_without_vision_configuration_is_explicitly_unavailable(
    client, monkeypatch
):
    await register(client)
    cid = await conversation(client)
    uploaded = await reference(client, cid)
    monkeypatch.setattr("app.services.image_generation_service.vision_available", lambda: False)
    monkeypatch.setattr(
        "app.services.image_generation_service.get_vision_provider",
        Mock(side_effect=TextProviderError("VISION_NOT_CONFIGURED", "视觉模型尚未配置", False)),
    )
    text_provider = Mock(side_effect=AssertionError("Never downgrade image requests to text-only"))
    monkeypatch.setattr("app.services.image_generation_service.get_text_provider", text_provider)
    response = await client.post(
        f"{API}/image-prompt-suggestions",
        json={
            "conversation_id": cid,
            "prompt": "请根据图片建议",
            "reference_asset_ids": [uploaded["id"]],
        },
        headers=headers(client),
    )
    assert response.status_code == 503, response.text
    assert "VISION" in response.text or "视觉" in response.text
    text_provider.assert_not_called()
