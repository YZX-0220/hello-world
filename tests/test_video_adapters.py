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
from app.providers.video.generic_async_json_v1 import GenericAsyncJsonV1Provider
from app.services.video_job_service import VideoJobService, _build_custom_template
from app.video_registry.models import EndpointSpec, ProtocolTemplate
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


@pytest.fixture(autouse=True)
def _no_dns_generic(monkeypatch: pytest.MonkeyPatch) -> None:
    """同 _no_dns，但针对 generic_async_json_v1 模块（避开真实 DNS/外网）。"""

    def _fake(url: str, resolver: object = None) -> CheckedBaseUrl:
        return CheckedBaseUrl(
            normalized=url,
            host="example.com",
            port=443,
            resolved_ip="1.1.1.1",
            path_prefix="",
        )

    monkeypatch.setattr("app.providers.video.generic_async_json_v1.check_base_url", _fake)


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


# ---------------------------------------------------------------- generic 自定义模板
# 内置 v1_videos_json_v1 模板走 /tasks、/tasks/{task_id}、/tasks/{task_id}/result；
# 自定义模板由用户指定 submit/poll/status/result 字段路径，由 Adapter 按用户模板调用。

CUSTOM_BASE = "https://custom.example.com"
BUILTIN_BASE = "https://builtin.example.com"
VIDEO_URL = "https://cdn.example.com/out/custom.mp4"


def _custom_template() -> ProtocolTemplate:
    """用户自定义模板（接近任务示例：POST {base}/submit、GET {base}/job/{task_id}）。"""
    return ProtocolTemplate(
        template_code="custom",
        protocol_code="generic_async_json_v1",
        name="用户自定义模板",
        version=1,
        submit=EndpointSpec(
            method="POST",
            path="/submit",
            success_statuses=frozenset({200}),
            id_json_path="job_id",
            request_template_json={"model": "{model}", "prompt": "{prompt}"},
        ),
        poll=EndpointSpec(
            method="GET",
            path="/job/{task_id}",
            success_statuses=frozenset({200}),
            status_json_path="state",
        ),
        result=EndpointSpec(
            method="GET",
            path="/job/{task_id}",
            success_statuses=frozenset({200}),
            result_url_json_path="video",
        ),
        remote_status_map={"pending": "queued", "finished": "succeeded"},
    )


def _custom_ctx(template: ProtocolTemplate) -> AdapterContext:
    return AdapterContext(
        base_url=CUSTOM_BASE,
        auth={"api_key": "custom-key"},
        options={},
        remote_model_id="custom-model",
        template=template,
    )


def test_build_custom_template_from_json() -> None:
    """落库的 custom_template_json → ProtocolTemplate 的字段正确映射。"""
    tpl = _build_custom_template(
        json.dumps(
            {
                "submit_method": "POST",
                "submit_path": "/submit",
                "request_template_json": {"model": "{model}", "prompt": "{prompt}"},
                "task_id_path": "job_id",
                "poll_method": "GET",
                "poll_path": "/job/{task_id}",
                "status_path": "state",
                "status_map": {"pending": "queued", "finished": "succeeded"},
                "result_url_path": "video",
            }
        )
    )
    assert tpl is not None
    assert tpl.submit.method == "POST"
    assert tpl.submit.path == "/submit"
    assert tpl.submit.id_json_path == "job_id"
    assert tpl.submit.request_template_json["model"] == "{model}"
    assert tpl.poll.method == "GET"
    assert tpl.poll.path == "/job/{task_id}"
    assert tpl.poll.status_json_path == "state"
    assert tpl.result.path == "/job/{task_id}"  # 自定义模板 poll/result 共用查询路径
    assert tpl.result.result_url_json_path == "video"
    assert tpl.remote_status_map == {"pending": "queued", "finished": "succeeded"}


def test_build_custom_template_none_when_absent() -> None:
    assert _build_custom_template(None) is None
    assert _build_custom_template("") is None


@respx.mock
async def test_generic_custom_submit_uses_user_template() -> None:
    """自定义模板：提交 POST {base}/submit，请求体按 request_template 构造，解析 job_id。"""
    route = respx.post(f"{CUSTOM_BASE}/submit")
    route.mock(return_value=httpx.Response(200, json={"job_id": "abc-123"}))
    provider = GenericAsyncJsonV1Provider()

    req = {
        "remote_model_id": "custom-model",
        "prompt": "一只猫",
        "mode": "text_to_video",
        "duration_seconds": 5,
        "aspect_ratio": "16:9",
        "resolution": "720p",
        "reference_image_urls": [],
        "generation_options": {},
    }
    result = await provider.submit(req, _custom_ctx(_custom_template()))

    assert result.provider_task_id == "abc-123"
    body = json.loads(route.calls.last.request.content)
    # {model} 通过别名解析到 remote_model_id；prompt 普通解析
    assert body == {"model": "custom-model", "prompt": "一只猫"}


@respx.mock
async def test_generic_custom_poll_uses_user_template() -> None:
    """自定义模板：轮询 GET {base}/job/{task_id}，按 status_path 读取远端状态。"""
    respx.get(f"{CUSTOM_BASE}/job/abc-123").mock(
        return_value=httpx.Response(200, json={"state": "finished", "video": VIDEO_URL})
    )
    provider = GenericAsyncJsonV1Provider()

    status = await provider.poll("abc-123", _custom_ctx(_custom_template()))

    assert status.raw_status == "finished"


@respx.mock
async def test_generic_custom_fetch_result_url() -> None:
    """自定义模板：结果地址从查询响应 result_url_path 取（复用 poll 路径）。"""
    respx.get(f"{CUSTOM_BASE}/job/abc-123").mock(
        return_value=httpx.Response(200, json={"state": "finished", "video": VIDEO_URL})
    )
    provider = GenericAsyncJsonV1Provider()

    url = await provider.fetch_result_url("abc-123", _custom_ctx(_custom_template()))

    assert url == VIDEO_URL


def test_generic_custom_status_map_and_passthrough() -> None:
    """自定义 status_map 生效；未列出的远端值原样透传。"""
    service = VideoJobService(session=None)
    tpl = _build_custom_template(
        json.dumps(
            {
                "submit_path": "/submit",
                "task_id_path": "job_id",
                "poll_path": "/job/{task_id}",
                "status_path": "state",
                "status_map": {"pending": "queued", "finished": "succeeded"},
                "result_url_path": "video",
            }
        )
    )
    assert service._map_status("finished", tpl) == "succeeded"
    assert service._map_status("pending", tpl) == "queued"
    assert service._map_status("weird_state", tpl) == "weird_state"


@respx.mock
async def test_generic_builtin_template_unchanged() -> None:
    """内置模板（template=None）行为完全不变：/tasks、/tasks/{id}、/tasks/{id}/result。"""
    respx.post(f"{BUILTIN_BASE}/tasks").mock(return_value=httpx.Response(200, json={"data": {"task_id": "t1"}}))
    respx.get(f"{BUILTIN_BASE}/tasks/t1").mock(
        return_value=httpx.Response(200, json={"data": {"status": "succeeded", "url": VIDEO_URL}})
    )
    respx.get(f"{BUILTIN_BASE}/tasks/t1/result").mock(
        return_value=httpx.Response(200, json={"data": {"url": VIDEO_URL}})
    )
    provider = GenericAsyncJsonV1Provider()
    ctx = AdapterContext(
        base_url=BUILTIN_BASE,
        auth={},
        options={},
        remote_model_id="videos-mini",
        template=None,
    )

    res = await provider.submit({}, ctx)
    assert res.provider_task_id == "t1"
    status = await provider.poll("t1", ctx)
    assert status.raw_status == "succeeded"
    url = await provider.fetch_result_url("t1", ctx)
    assert url == VIDEO_URL
