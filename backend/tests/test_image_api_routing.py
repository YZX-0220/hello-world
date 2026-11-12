"""Explicit image billing routes; all upstream requests use MockTransport."""

import base64
import json

import httpx
import pytest
from app.core.config import settings
from app.db.models.image_generation import ImageApiConfig, ImageJob
from app.providers.image import ark_plan

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
from test_image_generation import (
    isolated_image_settings as isolated_image_settings,
)

STANDARD_MODELS = [
    "doubao-seedream-5-0-pro-260628",
    "doubao-seedream-5-0-flash-260915",
]
SUBSCRIPTION_MODELS = ["doubao-seedream-5.0-pro", "doubao-seedream-5.0-flash"]
STANDARD_URL = "https://ark.cn-beijing.volces.com/api/v3/images/generations"
SUBSCRIPTION_URL = "https://ark.cn-beijing.volces.com/api/plan/v3/images/generations"


def install_transport(monkeypatch, handler):
    original_init = httpx.AsyncClient.__init__

    def mocked_init(self, *args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", mocked_init)


async def test_b64_response_format_requests_inline_png_and_preserves_original_bytes(monkeypatch):
    monkeypatch.setattr(settings, "image_response_format", "b64_json")
    raw = original_png((73, 51))
    calls = []

    async def handle(request):
        calls.append(request)
        assert request.method == "POST"
        assert str(request.url) == STANDARD_URL
        assert json.loads(request.content)["response_format"] == "b64_json"
        return httpx.Response(
            200,
            json={"data": [{"b64_json": base64.b64encode(raw).decode()}]},
            headers={"x-request-id": "inline-png-request"},
        )

    install_transport(monkeypatch, handle)
    result = await ark_plan.generate_image(
        api_key=SECRET, model=STANDARD_MODELS[0], prompt="Portrait", size="1536x1536"
    )
    assert len(calls) == 1
    assert result.data == raw
    assert result.url is None
    assert result.request_id == "inline-png-request"


@pytest.mark.parametrize("model", STANDARD_MODELS + SUBSCRIPTION_MODELS)
@pytest.mark.parametrize("editing", [False, True])
async def test_models_send_exact_payload_to_their_fixed_route(monkeypatch, model, editing):
    calls = []
    raw = original_png((32, 32))
    images = ["data:image/png;base64," + base64.b64encode(raw).decode()] if editing else None

    async def handle(request):
        calls.append(request)
        return httpx.Response(200, json={"data": [{"b64_json": base64.b64encode(raw).decode()}]})

    install_transport(monkeypatch, handle)
    result = await ark_plan.generate_image(
        api_key=SECRET,
        model=model,
        prompt="Blue coat",
        size="1536x1536",
        images=images,
        watermark=editing,
    )
    assert result.data == raw
    assert len(calls) == 1
    assert str(calls[0].url) == (STANDARD_URL if model in STANDARD_MODELS else SUBSCRIPTION_URL)
    assert calls[0].headers["Authorization"] == f"Bearer {SECRET}"
    assert json.loads(calls[0].content) == {
        "model": model,
        "prompt": "Blue coat",
        "size": "1536x1536",
        "response_format": "url",
        "output_format": "png",
        "watermark": editing,
        **({"image": images} if editing else {}),
    }


@pytest.mark.parametrize("model", STANDARD_MODELS + SUBSCRIPTION_MODELS)
@pytest.mark.parametrize("status", [401, 403, 404, 429])
async def test_rejections_never_retry_switch_routes_or_expose_upstream_body(
    monkeypatch, caplog, model, status
):
    calls = []
    upstream_body = f"private-vendor-diagnostic {SECRET}"

    async def handle(request):
        calls.append(str(request.url))
        return httpx.Response(status, json={"error": upstream_body})

    install_transport(monkeypatch, handle)
    with pytest.raises(ark_plan.ImageProviderError) as raised:
        await ark_plan.generate_image(
            api_key=SECRET, model=model, prompt="Portrait", size="1536x1536"
        )
    assert calls == [STANDARD_URL if model in STANDARD_MODELS else SUBSCRIPTION_URL]
    assert raised.value.uncertain is False
    assert SECRET not in str(raised.value) + caplog.text
    assert "private-vendor-diagnostic" not in str(raised.value) + caplog.text


@pytest.mark.parametrize("model", ["unknown-model", "doubao-seedream-5-0-pro", STANDARD_URL])
async def test_unknown_model_fails_before_constructing_http_client(monkeypatch, model):
    def forbidden_client(*args, **kwargs):
        pytest.fail("Unknown models must fail before opening an HTTP client")

    monkeypatch.setattr(httpx, "AsyncClient", forbidden_client)
    with pytest.raises(ark_plan.ImageProviderError) as raised:
        await ark_plan.generate_image(
            api_key=SECRET, model=model, prompt="Portrait", size="1536x1536"
        )
    assert raised.value.uncertain is False
    assert SECRET not in str(raised.value)


@pytest.mark.parametrize("model", STANDARD_MODELS)
async def test_standard_config_persists_and_queued_execution_uses_frozen_model(
    client, db_engine, monkeypatch, model
):
    await register(client)
    cid = await conversation(client)
    generate = mock_real(monkeypatch, data=original_png())
    created = await config(client, model=model)
    stored = await row_for(db_engine, ImageApiConfig, created["id"])
    assert created["model"] == stored.model == model
    job = await create_job(client, cid, api_config_id=created["id"])
    frozen = await row_for(db_engine, ImageJob, job["id"])
    assert frozen.status == "queued" and frozen.model == model
    patched = await client.patch(
        f"{API}/image-api-configs/{created['id']}",
        json={"expected_revision": created["revision"], "model": SUBSCRIPTION_MODELS[0]},
        headers=headers(client),
    )
    assert patched.status_code == 200, patched.text
    monkeypatch.setattr(settings, "image_platform_model", SUBSCRIPTION_MODELS[1])
    await run_job(db_engine, job["id"])
    generate.assert_awaited_once()
    assert generate.call_args.kwargs["model"] == model
    completed = await row_for(db_engine, ImageJob, job["id"])
    assert completed.status == "succeeded"
    assert completed.model == model and completed.config_revision == created["revision"]
