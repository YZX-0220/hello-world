"""Explicit vision routing and multimodal transport; all HTTP is intercepted locally."""

import copy
import json

import httpx
import pytest
from app.core.config import settings
from app.providers.text import get_text_provider
from app.providers.text.base import TextProviderError
from app.providers.text.vision import get_vision_provider, vision_available

TEXT_KEY = "unit-test-text-secret-123"
VISION_KEY = "unit-test-vision-secret-456"
IMAGE_ONE = "data:image/png;base64,aW1hZ2Utb25l"
IMAGE_TWO = "data:image/jpeg;base64,aW1hZ2UtdHdv"


@pytest.fixture(autouse=True)
def isolated_vision_configuration(monkeypatch):
    values = {
        "text_provider": "openai_compatible",
        "text_base_url": "https://text.invalid/v1",
        "text_api_key": TEXT_KEY,
        "text_model": "text-only-test-model",
        "text_timeout": 31,
        "text_supports_vision": False,
        "vision_base_url": "",
        "vision_api_key": "",
        "vision_model": "",
        "vision_timeout": 47,
    }
    for key, value in values.items():
        monkeypatch.setattr(settings, key, value)
    original_send = httpx.AsyncClient.send

    async def mocked_only(self, request, *args, **kwargs):
        assert isinstance(self._transport, httpx.MockTransport), "No external HTTP in vision tests"
        return await original_send(self, request, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "send", mocked_only)


def configure_dedicated(monkeypatch):
    monkeypatch.setattr(settings, "vision_base_url", "https://vision.invalid/v1/")
    monkeypatch.setattr(settings, "vision_api_key", VISION_KEY)
    monkeypatch.setattr(settings, "vision_model", "dedicated-vision-test-model")


def mock_http(monkeypatch, replies):
    requests = []
    original_init = httpx.AsyncClient.__init__

    async def handle(request):
        index = len(requests)
        requests.append(request)
        content = replies[index]
        return httpx.Response(
            200,
            json={
                "model": json.loads(request.content)["model"],
                "choices": [{"message": {"content": content}, "finish_reason": "stop"}],
            },
        )

    def init_with_transport(self, *args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handle)
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", init_with_transport)
    return requests


def image_messages():
    return [
        {"role": "system", "content": "Inspect the attached references and return JSON."},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Keep the person, change the coat to blue."},
                {"type": "image_url", "image_url": {"url": IMAGE_ONE}},
                {"type": "image_url", "image_url": {"url": IMAGE_TWO}},
            ],
        },
    ]


def test_missing_vision_configuration_never_uses_unmarked_text_model():
    assert not vision_available()
    with pytest.raises(TextProviderError) as raised:
        get_vision_provider()
    assert raised.value.code == "VISION_NOT_CONFIGURED"
    assert raised.value.retryable is False
    assert TEXT_KEY not in str(raised.value)


@pytest.mark.parametrize("configured_field", ["vision_base_url", "vision_api_key", "vision_model"])
def test_partial_dedicated_configuration_blocks_text_fallback(monkeypatch, configured_field):
    monkeypatch.setattr(settings, "text_supports_vision", True)
    value = {
        "vision_base_url": "https://vision.invalid/v1",
        "vision_api_key": VISION_KEY,
        "vision_model": "vision-test",
    }[configured_field]
    monkeypatch.setattr(settings, configured_field, value)
    assert not vision_available()
    with pytest.raises(TextProviderError, match="看图") as raised:
        get_vision_provider()
    assert raised.value.code == "VISION_NOT_CONFIGURED"


async def test_explicit_text_vision_capability_allows_reuse_but_fake_provider_does_not(monkeypatch):
    monkeypatch.setattr(settings, "text_supports_vision", True)
    assert vision_available()
    requests = mock_http(monkeypatch, ['{"reply":"visual reuse"}'])
    provider = get_vision_provider()
    assert provider.capabilities.supports_vision is True
    await provider.generate(image_messages(), structured=True)
    assert requests[0].url.host == "text.invalid"
    assert requests[0].headers["Authorization"] == f"Bearer {TEXT_KEY}"
    assert json.loads(requests[0].content)["model"] == "text-only-test-model"
    monkeypatch.setattr(settings, "text_provider", "fake")
    assert not vision_available()
    with pytest.raises(TextProviderError) as raised:
        get_vision_provider()
    assert raised.value.code == "VISION_NOT_CONFIGURED"


async def test_dedicated_credentials_and_model_do_not_change_ordinary_text_provider(monkeypatch):
    configure_dedicated(monkeypatch)
    requests = mock_http(monkeypatch, ['{"reply":"visual"}', "ordinary text reply"])
    visual = get_vision_provider()
    text = get_text_provider()
    await visual.generate(image_messages(), structured=True)
    await text.generate([{"role": "user", "content": "Plain text request"}])
    assert [request.url.host for request in requests] == ["vision.invalid", "text.invalid"]
    assert [request.headers["Authorization"] for request in requests] == [
        f"Bearer {VISION_KEY}",
        f"Bearer {TEXT_KEY}",
    ]
    assert [json.loads(request.content)["model"] for request in requests] == [
        "dedicated-vision-test-model",
        "text-only-test-model",
    ]
    assert settings.text_api_key == TEXT_KEY and settings.text_model == "text-only-test-model"
    assert [request.extensions["timeout"]["read"] for request in requests] == [47, 31]
    assert visual.capabilities.supports_vision is True
    assert text.capabilities.supports_vision is False


async def test_vision_http_preserves_image_url_content_lists(monkeypatch):
    configure_dedicated(monkeypatch)
    requests = mock_http(
        monkeypatch, ['{"suggested_prompt":"Blue coat","explanation":"Observed references"}']
    )
    messages = image_messages()
    original = copy.deepcopy(messages)
    result = await get_vision_provider().generate(messages, structured=True)
    assert len(requests) == 1
    assert str(requests[0].url) == "https://vision.invalid/v1/chat/completions"
    body = json.loads(requests[0].content)
    assert body["messages"] == original
    assert body["messages"][1]["content"][1]["image_url"]["url"] == IMAGE_ONE
    assert body["messages"][1]["content"][2]["image_url"]["url"] == IMAGE_TWO
    assert body["response_format"] == {"type": "json_object"}
    assert result.structured["suggested_prompt"] == "Blue coat"
    assert messages == original


async def test_invalid_json_repair_keeps_original_images_in_second_request(monkeypatch):
    configure_dedicated(monkeypatch)
    requests = mock_http(monkeypatch, ["malformed JSON reply", '{"suggested_prompt":"Repaired"}'])
    messages = image_messages()
    original = copy.deepcopy(messages)
    result = await get_vision_provider().generate(messages, structured=True)
    assert result.structured == {"suggested_prompt": "Repaired"}
    assert len(requests) == 2
    first, second = [json.loads(request.content) for request in requests]
    assert first["messages"] == original
    assert second["messages"][: len(original)] == original
    assert second["messages"][-2] == {"role": "assistant", "content": "malformed JSON reply"}
    assert second["messages"][-1]["role"] == "user"
    assert IMAGE_ONE in json.dumps(second) and IMAGE_TWO in json.dumps(second)
    assert messages == original


async def test_invalid_json_repair_is_bounded_and_never_falls_back_to_text(monkeypatch):
    configure_dedicated(monkeypatch)
    requests = mock_http(monkeypatch, ["invalid first reply", "invalid repaired reply"])
    with pytest.raises(TextProviderError) as raised:
        await get_vision_provider().generate(image_messages(), structured=True)
    assert raised.value.code == "AGENT_OUTPUT_INVALID"
    assert len(requests) == 2
    assert all(request.url.host == "vision.invalid" for request in requests)
    assert all(request.headers["Authorization"] == f"Bearer {VISION_KEY}" for request in requests)
