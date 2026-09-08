"""Contract Test：ark_seedance_v1 Adapter（respx mock httpx，无需真实 key/网络）。

覆盖：
  a) submit 构建的 Ark body 正确（model/content/text/first_frame 等 role）且解析出任务 ID；
  b) poll 从顶层 status 映射到本站状态（succeeded / expired→failed）；
  c) fetch_result_url 从 content.video_url 解析；
  d) download_result 能取回 bytes；
  e) cancel DELETE 成功返回 True；
  f) 非 2xx submit 抛 VideoProviderError。
另含 video_registry 断言：get_preset("ark_seedance_v1") 存在、list_profiles 返回 2 个 profile。
"""

import json

import httpx
import pytest
import respx
from app.core.ssrf import CheckedBaseUrl
from app.providers.video.ark_seedance_v1 import ArkSeedanceProvider
from app.providers.video.base import AdapterContext, VideoProviderError
from app.video_registry.registry import get_preset, list_profiles

BASE = "https://ark.cn-beijing.volces.com"
SUBMIT_URL = f"{BASE}/api/v3/contents/generations/tasks"
TASK_URL = f"{BASE}/api/v3/contents/generations/tasks/cgt-1"
VIDEO_URL = "https://cdn.example.com/result.mp4"


@pytest.fixture(autouse=True)
def _no_dns(monkeypatch: pytest.MonkeyPatch) -> None:
    """把 check_base_url 打桩成固定返回，避免 Contract Test 触发真实 DNS/外网。

    本批测试只验证「请求/响应映射」，SSRF 结构校验已在别处覆盖。
    """

    def _fake(url: str, resolver: object = None) -> CheckedBaseUrl:
        return CheckedBaseUrl(
            normalized=url,
            host="ark.cn-beijing.volces.com",
            port=443,
            resolved_ip="1.1.1.1",
            path_prefix="",
        )

    monkeypatch.setattr("app.providers.video.ark_seedance_v1.check_base_url", _fake)


def _ctx(model: str = "doubao-seedance-1-5-pro-251215") -> AdapterContext:
    return AdapterContext(
        base_url=BASE,
        auth={"api_key": "ark-test-key"},
        options={},
        remote_model_id=model,
        template=None,
    )


def _request(**overrides: object) -> dict:
    req: dict = {
        "remote_model_id": "doubao-seedance-1-5-pro-251215",
        "prompt": "一只猫在草地上奔跑",
        "mode": "first_last_frame_to_video",
        "duration_seconds": 10,
        "aspect_ratio": "16:9",
        "resolution": "720p",
        "generate_audio": True,
        "first_frame_url": "https://cdn.example.com/first.png",
        "last_frame_url": "https://cdn.example.com/last.png",
        "reference_image_urls": ["https://cdn.example.com/ref1.png"],
        "source_video_url": None,
        "audio_url": None,
        "generation_options": {},
    }
    req.update(overrides)
    return req


def _ok_task(body: dict) -> httpx.Response:
    payload = {"id": "cgt-1", "status": "succeeded", "content": {"video_url": VIDEO_URL}, **body}
    return httpx.Response(200, json=payload)


@respx.mock
async def test_submit_builds_correct_body_and_resolves_task_id() -> None:
    route = respx.post(SUBMIT_URL)
    route.mock(return_value=httpx.Response(201, json={"id": "cgt-123"}))
    provider = ArkSeedanceProvider()

    result = await provider.submit(_request(), _ctx())

    assert result.provider_task_id == "cgt-123"

    body = json.loads(route.calls.last.request.content)
    assert body["model"] == "doubao-seedance-1-5-pro-251215"
    assert body["content"] == [
        {"type": "text", "text": "一只猫在草地上奔跑"},
        {
            "type": "image_url",
            "image_url": {"url": "https://cdn.example.com/first.png"},
            "role": "first_frame",
        },
        {
            "type": "image_url",
            "image_url": {"url": "https://cdn.example.com/last.png"},
            "role": "last_frame",
        },
        {
            "type": "image_url",
            "image_url": {"url": "https://cdn.example.com/ref1.png"},
            "role": "reference_image",
        },
    ]
    assert body["duration"] == 10
    assert body["resolution"] == "720p"
    assert body["ratio"] == "16:9"
    assert body["generate_audio"] is True
    assert body["watermark"] is False
    assert body["return_last_frame"] is True
    assert body["camera_fixed"] is False


@respx.mock
async def test_submit_text_only_has_only_text_content() -> None:
    route = respx.post(SUBMIT_URL)
    route.mock(return_value=httpx.Response(201, json={"id": "cgt-456"}))
    provider = ArkSeedanceProvider()

    req = _request(
        mode="text_to_video",
        first_frame_url=None,
        last_frame_url=None,
        reference_image_urls=[],
    )
    await provider.submit(req, _ctx())

    body = json.loads(route.calls.last.request.content)
    assert body["content"] == [{"type": "text", "text": "一只猫在草地上奔跑"}]


@respx.mock
async def test_poll_maps_succeeded() -> None:
    respx.get(TASK_URL).mock(return_value=_ok_task({}))
    provider = ArkSeedanceProvider()

    status = await provider.poll("cgt-1", _ctx())

    assert status.raw_status == "succeeded"


@respx.mock
async def test_poll_maps_expired_to_failed() -> None:
    respx.get(TASK_URL).mock(return_value=httpx.Response(200, json={"id": "cgt-1", "status": "expired"}))
    provider = ArkSeedanceProvider()

    status = await provider.poll("cgt-1", _ctx())

    assert status.raw_status == "failed"
    assert status.extra["remote_status"] == "expired"


@respx.mock
async def test_poll_raises_on_http_error() -> None:
    respx.get(TASK_URL).mock(return_value=httpx.Response(500, json={}))
    provider = ArkSeedanceProvider()

    with pytest.raises(VideoProviderError) as exc_info:
        await provider.poll("cgt-1", _ctx())
    assert exc_info.value.code == "VIDEO_POLL_FAILED"


@respx.mock
async def test_fetch_result_url() -> None:
    respx.get(TASK_URL).mock(return_value=_ok_task({}))
    provider = ArkSeedanceProvider()

    url = await provider.fetch_result_url("cgt-1", _ctx())

    assert url == VIDEO_URL


@respx.mock
async def test_fetch_result_url_returns_none_on_http_error() -> None:
    respx.get(TASK_URL).mock(return_value=httpx.Response(404, json={}))
    provider = ArkSeedanceProvider()

    assert await provider.fetch_result_url("cgt-1", _ctx()) is None


@respx.mock
async def test_download_result_returns_bytes() -> None:
    respx.get(TASK_URL).mock(return_value=_ok_task({}))
    respx.get(VIDEO_URL).mock(return_value=httpx.Response(200, content=b"VIDEO_BYTES"))
    provider = ArkSeedanceProvider()

    data = await provider.download_result("cgt-1", _ctx())

    assert data == b"VIDEO_BYTES"


@respx.mock
async def test_cancel_returns_true_on_2xx() -> None:
    respx.delete(TASK_URL).mock(return_value=httpx.Response(202))
    provider = ArkSeedanceProvider()

    assert await provider.cancel("cgt-1", _ctx()) is True


@respx.mock
async def test_submit_non_2xx_raises() -> None:
    respx.post(SUBMIT_URL).mock(return_value=httpx.Response(401, json={"error": "unauthorized"}))
    provider = ArkSeedanceProvider()

    with pytest.raises(VideoProviderError) as exc_info:
        await provider.submit(_request(), _ctx())
    assert exc_info.value.code == "VIDEO_SUBMISSION_FAILED"


def test_ark_preset_and_profiles_registered() -> None:
    preset = get_preset("ark_seedance_v1")
    assert preset is not None
    assert preset.enabled is True
    assert preset.allows_custom_base_url is False
    assert preset.official_base_url == BASE

    profiles = list_profiles("ark_seedance_v1")
    assert {p.code for p in profiles} == {"doubao-seedance-1-5-pro", "doubao-seedance-2-0", "doubao-seedance-1-0-pro-fast"}
