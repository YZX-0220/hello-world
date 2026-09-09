"""Contract Test：ark_seedance_v1 Adapter（respx mock httpx，无需真实 key/网络）。

覆盖：
  a) submit 构建的 Ark body 正确（model/content/text/first_frame 等 role）且解析出任务 ID；
  b) poll 从顶层 status 映射到本站状态（succeeded / expired→failed）；
  c) fetch_result_url 从 content.video_url 解析；
  d) download_result 能取回 bytes；
  e) cancel DELETE 成功返回 True；
  f) 非 2xx submit 抛 VideoProviderError。
另含 video_registry 断言：get_preset("ark_seedance_v1") 存在、list_profiles("ark_seedance_v1")
返回的 7 个 profile code 集合正确。
"""

import json

import httpx
import pytest
import respx
from app.core.ssrf import CheckedBaseUrl
from app.providers.video.ark_seedance_v1 import ArkSeedanceProvider
from app.providers.video.base import AdapterContext, VideoProviderError
from app.providers.video.dashscope_async_v1 import DashScopeAsyncV1Provider
from app.providers.video.fal_queue_v1 import FalQueueV1Provider
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
    assert {p.code for p in profiles} == {
        "doubao-seedance-1-5-pro",
        "doubao-seedance-2-0",
        "doubao-seedance-1-0-pro-fast",
        "doubao-seedance-2-0-fast",
        "doubao-seedance-1-0-pro",
        "doubao-seedance-1-0-lite-t2v",
        "doubao-seedance-1-0-lite-i2v",
    }


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


# ---------------------------------------------------------------- dashscope_async_v1
# 阿里云百炼 DashScope / 通义 Wan：异步提交需 X-DashScope-Async: enable；任务查询顶层 task_status。

DS_BASE = "https://dashscope.aliyuncs.com"
DS_SUBMIT_URL = f"{DS_BASE}/api/v1/services/aigc/video-generation/video-synthesis"
DS_TASK_URL = f"{DS_BASE}/api/v1/tasks/tsk-1"
DS_VIDEO_URL = "https://cdn.example.com/v.mp4"


@pytest.fixture(autouse=True)
def _no_dns_dashscope(monkeypatch: pytest.MonkeyPatch) -> None:
    """同 _no_dns，但针对 dashscope_async_v1 模块（避开真实 DNS/外网）。"""

    def _fake(url: str, resolver: object = None) -> CheckedBaseUrl:
        return CheckedBaseUrl(
            normalized=url,
            host="dashscope.aliyuncs.com",
            port=443,
            resolved_ip="1.1.1.1",
            path_prefix="",
        )

    monkeypatch.setattr("app.providers.video.dashscope_async_v1.check_base_url", _fake)


def _dash_ctx(model: str = "wan2.5-t2v-preview") -> AdapterContext:
    return AdapterContext(
        base_url=DS_BASE,
        auth={"api_key": "sk-dash-test-key"},
        options={},
        remote_model_id=model,
        template=None,
    )


def _dash_request(**overrides: object) -> dict:
    req: dict = {
        "remote_model_id": "wan2.5-t2v-preview",
        "prompt": "一只猫在草地上奔跑",
        "mode": "text_to_video",
        "duration_seconds": 10,
        "resolution": "720p",
        "generation_options": {},
    }
    req.update(overrides)
    return req


@respx.mock
async def test_dashscope_submit_builds_correct_body_and_resolves_task_id() -> None:
    route = respx.post(DS_SUBMIT_URL)
    route.mock(return_value=httpx.Response(200, json={"output": {"task_id": "tsk-1"}}))
    provider = DashScopeAsyncV1Provider()

    result = await provider.submit(_dash_request(), _dash_ctx())

    assert result.provider_task_id == "tsk-1"

    request = route.calls.last.request
    assert request.headers.get("authorization") == "Bearer sk-dash-test-key"
    assert request.headers.get("x-dashscope-async") == "enable"
    assert json.loads(request.content) == {
        "model": "wan2.5-t2v-preview",
        "input": {"prompt": "一只猫在草地上奔跑"},
        "parameters": {"size": "1280*720", "duration": 10},
    }


@respx.mock
async def test_dashscope_submit_top_level_task_id_fallback() -> None:
    """顶层 task_id 回退：无 output.task_id 时取顶层 task_id。"""
    route = respx.post(DS_SUBMIT_URL)
    route.mock(return_value=httpx.Response(200, json={"task_id": "tsk-top"}))
    provider = DashScopeAsyncV1Provider()

    result = await provider.submit(_dash_request(), _dash_ctx())

    assert result.provider_task_id == "tsk-top"


@respx.mock
async def test_dashscope_poll_maps_succeeded() -> None:
    respx.get(DS_TASK_URL).mock(
        return_value=httpx.Response(200, json={"task_status": "SUCCEEDED", "output": {"video_url": DS_VIDEO_URL}})
    )
    provider = DashScopeAsyncV1Provider()

    status = await provider.poll("tsk-1", _dash_ctx())

    assert status.raw_status == "succeeded"
    assert status.extra["remote_status"] == "SUCCEEDED"


@respx.mock
async def test_dashscope_poll_maps_pending_to_queued() -> None:
    respx.get(DS_TASK_URL).mock(return_value=httpx.Response(200, json={"task_status": "PENDING"}))
    provider = DashScopeAsyncV1Provider()

    status = await provider.poll("tsk-1", _dash_ctx())

    assert status.raw_status == "queued"


@respx.mock
async def test_dashscope_poll_maps_failed() -> None:
    respx.get(DS_TASK_URL).mock(return_value=httpx.Response(200, json={"task_status": "FAILED"}))
    provider = DashScopeAsyncV1Provider()

    status = await provider.poll("tsk-1", _dash_ctx())

    assert status.raw_status == "failed"
    assert status.extra["remote_status"] == "FAILED"


@respx.mock
async def test_dashscope_poll_raises_on_http_error() -> None:
    respx.get(DS_TASK_URL).mock(return_value=httpx.Response(500, json={}))
    provider = DashScopeAsyncV1Provider()

    with pytest.raises(VideoProviderError) as exc_info:
        await provider.poll("tsk-1", _dash_ctx())
    assert exc_info.value.code == "VIDEO_POLL_FAILED"


@respx.mock
async def test_dashscope_fetch_result_url() -> None:
    respx.get(DS_TASK_URL).mock(
        return_value=httpx.Response(200, json={"task_status": "SUCCEEDED", "output": {"video_url": DS_VIDEO_URL}})
    )
    provider = DashScopeAsyncV1Provider()

    url = await provider.fetch_result_url("tsk-1", _dash_ctx())

    assert url == DS_VIDEO_URL


@respx.mock
async def test_dashscope_fetch_result_url_returns_none_on_http_error() -> None:
    respx.get(DS_TASK_URL).mock(return_value=httpx.Response(404, json={}))
    provider = DashScopeAsyncV1Provider()

    assert await provider.fetch_result_url("tsk-1", _dash_ctx()) is None


@respx.mock
async def test_dashscope_download_result_returns_bytes() -> None:
    respx.get(DS_TASK_URL).mock(
        return_value=httpx.Response(200, json={"task_status": "SUCCEEDED", "output": {"video_url": DS_VIDEO_URL}})
    )
    respx.get(DS_VIDEO_URL).mock(return_value=httpx.Response(200, content=b"VIDEO_BYTES"))
    provider = DashScopeAsyncV1Provider()

    data = await provider.download_result("tsk-1", _dash_ctx())

    assert data == b"VIDEO_BYTES"


@respx.mock
async def test_dashscope_cancel_returns_false() -> None:
    provider = DashScopeAsyncV1Provider()

    assert await provider.cancel("tsk-1", _dash_ctx()) is False


def test_dashscope_preset_and_profiles_registered() -> None:
    preset = get_preset("dashscope_async_v1")
    assert preset is not None
    assert preset.enabled is True
    assert preset.allows_custom_base_url is False
    assert preset.official_base_url == DS_BASE

    profiles = list_profiles("dashscope_async_v1")
    assert {p.code for p in profiles} == {"wan2.5-t2v-preview", "wan2.2-t2v-plus"}


# ---------------------------------------------------------------- fal_queue_v1
# fal.ai Queue：提交 POST {base}/{model endpoint}（端点含多段路径，直接拼 base 后），鉴权头为 `Key <key>`；
# 任务 ID（request_id）用于拼接 status / response / cancel 三类 URL（均在 {base}/fal-ai/requests/ 之下）。

FAL_BASE = "https://queue.fal.run"
FAL_SUBMIT_URL = f"{FAL_BASE}/fal-ai/wan/v2.2-a14b/text-to-video/turbo"
FAL_REQ_URL = f"{FAL_BASE}/fal-ai/requests/req_1"
FAL_VIDEO_URL = "https://cdn.example.com/v.mp4"


@pytest.fixture(autouse=True)
def _no_dns_fal(monkeypatch: pytest.MonkeyPatch) -> None:
    """同 _no_dns，但针对 fal_queue_v1 模块（避开真实 DNS/外网）。"""

    def _fake(url: str, resolver: object = None) -> CheckedBaseUrl:
        return CheckedBaseUrl(
            normalized=url,
            host="queue.fal.run",
            port=443,
            resolved_ip="1.1.1.1",
            path_prefix="",
        )

    monkeypatch.setattr("app.providers.video.fal_queue_v1.check_base_url", _fake)


def _fal_ctx(model: str = "fal-ai/wan/v2.2-a14b/text-to-video/turbo") -> AdapterContext:
    return AdapterContext(
        base_url=FAL_BASE,
        auth={"api_key": "sk-fal-test"},
        options={},
        remote_model_id=model,
        template=None,
    )


def _fal_request(**overrides: object) -> dict:
    req: dict = {
        "remote_model_id": "fal-ai/wan/v2.2-a14b/text-to-video/turbo",
        "prompt": "一只猫在草地上奔跑",
        "mode": "text_to_video",
        "duration_seconds": 10,
        "resolution": "720p",
        "aspect_ratio": "16:9",
        "generation_options": {},
    }
    req.update(overrides)
    return req


@respx.mock
async def test_fal_submit_builds_correct_body_and_resolves_task_id() -> None:
    route = respx.post(FAL_SUBMIT_URL)
    route.mock(return_value=httpx.Response(200, json={"status": "IN_QUEUE", "request_id": "req_1"}))
    provider = FalQueueV1Provider()

    result = await provider.submit(_fal_request(), _fal_ctx())

    assert result.provider_task_id == "req_1"

    request = route.calls.last.request
    # fal 鉴权头是 `Key <key>` 前缀（而非 Bearer）
    assert request.headers.get("authorization") == "Key sk-fal-test"
    assert json.loads(request.content) == {
        "prompt": "一只猫在草地上奔跑",
        "resolution": "720p",
        "aspect_ratio": "16:9",
        "duration": 10,
    }


@respx.mock
async def test_fal_submit_non_2xx_raises() -> None:
    respx.post(FAL_SUBMIT_URL).mock(return_value=httpx.Response(401, json={"error": "unauthorized"}))
    provider = FalQueueV1Provider()

    with pytest.raises(VideoProviderError) as exc_info:
        await provider.submit(_fal_request(), _fal_ctx())
    assert exc_info.value.code == "VIDEO_SUBMISSION_FAILED"


@respx.mock
async def test_fal_poll_maps_completed_to_succeeded() -> None:
    respx.get(f"{FAL_REQ_URL}/status").mock(return_value=httpx.Response(200, json={"status": "COMPLETED"}))
    provider = FalQueueV1Provider()

    status = await provider.poll("req_1", _fal_ctx())

    assert status.raw_status == "succeeded"
    assert status.extra["remote_status"] == "COMPLETED"


@respx.mock
async def test_fal_poll_maps_in_queue_to_queued() -> None:
    respx.get(f"{FAL_REQ_URL}/status").mock(return_value=httpx.Response(200, json={"status": "IN_QUEUE"}))
    provider = FalQueueV1Provider()

    status = await provider.poll("req_1", _fal_ctx())

    assert status.raw_status == "queued"


@respx.mock
async def test_fal_poll_maps_failed() -> None:
    respx.get(f"{FAL_REQ_URL}/status").mock(return_value=httpx.Response(200, json={"status": "FAILED"}))
    provider = FalQueueV1Provider()

    status = await provider.poll("req_1", _fal_ctx())

    assert status.raw_status == "failed"
    assert status.extra["remote_status"] == "FAILED"


@respx.mock
async def test_fal_poll_raises_on_http_error() -> None:
    respx.get(f"{FAL_REQ_URL}/status").mock(return_value=httpx.Response(500, json={}))
    provider = FalQueueV1Provider()

    with pytest.raises(VideoProviderError) as exc_info:
        await provider.poll("req_1", _fal_ctx())
    assert exc_info.value.code == "VIDEO_POLL_FAILED"


@respx.mock
async def test_fal_fetch_result_url() -> None:
    respx.get(FAL_REQ_URL).mock(
        return_value=httpx.Response(200, json={"output": {"video": {"url": FAL_VIDEO_URL}}})
    )
    provider = FalQueueV1Provider()

    url = await provider.fetch_result_url("req_1", _fal_ctx())

    assert url == FAL_VIDEO_URL


@respx.mock
async def test_fal_fetch_result_url_array_takes_first() -> None:
    respx.get(FAL_REQ_URL).mock(
        return_value=httpx.Response(
            200,
            json={"output": {"video": {"url": [FAL_VIDEO_URL, "https://cdn.example.com/v2.mp4"]}}},
        )
    )
    provider = FalQueueV1Provider()

    url = await provider.fetch_result_url("req_1", _fal_ctx())

    assert url == FAL_VIDEO_URL


@respx.mock
async def test_fal_fetch_result_url_string_output() -> None:
    respx.get(FAL_REQ_URL).mock(return_value=httpx.Response(200, json={"output": {"video": FAL_VIDEO_URL}}))
    provider = FalQueueV1Provider()

    url = await provider.fetch_result_url("req_1", _fal_ctx())

    assert url == FAL_VIDEO_URL


@respx.mock
async def test_fal_fetch_result_url_none_on_http_error() -> None:
    respx.get(FAL_REQ_URL).mock(return_value=httpx.Response(404, json={}))
    provider = FalQueueV1Provider()

    assert await provider.fetch_result_url("req_1", _fal_ctx()) is None


@respx.mock
async def test_fal_download_result_returns_bytes() -> None:
    respx.get(FAL_REQ_URL).mock(
        return_value=httpx.Response(200, json={"output": {"video": {"url": FAL_VIDEO_URL}}})
    )
    respx.get(FAL_VIDEO_URL).mock(return_value=httpx.Response(200, content=b"VIDEO_BYTES"))
    provider = FalQueueV1Provider()

    data = await provider.download_result("req_1", _fal_ctx())

    assert data == b"VIDEO_BYTES"


@respx.mock
async def test_fal_cancel_returns_true_on_2xx() -> None:
    respx.delete(f"{FAL_REQ_URL}/cancel").mock(return_value=httpx.Response(202))
    provider = FalQueueV1Provider()

    assert await provider.cancel("req_1", _fal_ctx()) is True


def test_fal_preset_and_profiles_registered() -> None:
    preset = get_preset("fal_queue_v1")
    assert preset is not None
    assert preset.enabled is True
    assert preset.allows_custom_base_url is False
    assert preset.official_base_url == FAL_BASE

    profiles = list_profiles("fal_queue_v1")
    assert {p.code for p in profiles} == {
        "fal-ai/wan/v2.2-a14b/text-to-video/turbo",
        "fal-ai/wan/v2.7/text-to-video",
    }
