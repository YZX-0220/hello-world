"""generic_async_json_v1 通用异步 JSON 协议 Adapter。

依据 v1_videos_json_v1 模板与内置语义调用：
  - 提交 POST {base}/tasks，响应的 data.task_id 为远端任务 ID；
  - 轮询 GET {base}/tasks/{task_id}，响应的 data.status 为远端状态；
  - 结果 GET {base}/tasks/{task_id}/result，响应的 data.url 为厂商直链。

安全：单独实例化的 httpx 客户端 trust_env=False（防误继承代理）、禁止自动跳转、请求前做 SSRF 校验。
"""

from typing import Any

import httpx

from app.core.config import settings
from app.core.ssrf import UnsafeUrlError, check_base_url
from app.providers.video.base import (
    AdapterContext,
    VideoProvider,
    VideoProviderError,
    VideoSubmitResult,
    VideoTaskStatus,
)
from app.video_registry.core_protocols import V1_VIDEOS_TEMPLATE


def _extract(obj: Any, dotpath: str) -> Any:
    """按点分字段路径取值（如 data.task_id）；不支持则返回 None。"""
    if not dotpath:
        return None
    cur: Any = obj
    for part in dotpath.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        elif isinstance(cur, list):
            try:
                cur = cur[int(part)]
            except (ValueError, IndexError):
                return None
        else:
            return None
    return cur


def _fill(template: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    """用 request 的值替换模板里的 {key} 占位符（递归）。"""

    def _sub(v: Any) -> Any:
        if isinstance(v, str):
            return request.get(v.strip("{}"), v)
        if isinstance(v, list):
            return [_sub(x) for x in v]
        if isinstance(v, dict):
            return {k: _sub(x) for k, x in v.items()}
        return v

    return _sub(template)


class GenericAsyncJsonV1Provider(VideoProvider):
    code = "generic_async_json_v1"

    def __init__(self) -> None:
        self._template = V1_VIDEOS_TEMPLATE

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            timeout=settings.video_provider_timeout,
            trust_env=False,
            follow_redirects=False,
        )

    async def _require_public(self, base_url: str) -> None:
        try:
            check_base_url(base_url)
        except UnsafeUrlError as exc:
            raise VideoProviderError("UNSAFE_BASE_URL", str(exc), retryable=False) from exc

    @staticmethod
    def _headers(ctx: AdapterContext) -> dict[str, str]:
        api_key = ctx.auth.get("api_key")
        return {"Authorization": f"Bearer {api_key}"} if api_key else {}

    async def submit(self, request: dict[str, Any], ctx: AdapterContext) -> VideoSubmitResult:
        tpl = ctx.template or self._template
        endpoint = tpl.submit
        if endpoint is None:
            raise VideoProviderError("VIDEO_PROTOCOL_UNSUPPORTED", "模板缺少提交端点", retryable=False)
        await self._require_public(ctx.base_url)
        url = ctx.base_url.rstrip("/") + endpoint.path
        payload = _fill(endpoint.request_template_json, request)
        try:
            async with self._client() as c:
                resp = await c.post(url, json=payload, headers=self._headers(ctx))
        except httpx.HTTPError as exc:
            raise VideoProviderError("VIDEO_SUBMISSION_FAILED", "提交厂商请求失败") from exc
        if resp.status_code not in endpoint.success_statuses:
            raise VideoProviderError("VIDEO_SUBMISSION_FAILED", f"厂商拒绝任务（HTTP {resp.status_code}）", retryable=False)
        task_id = _extract(resp.json(), endpoint.id_json_path)
        if not task_id:
            raise VideoProviderError("VIDEO_SUBMISSION_FAILED", "厂商响应缺少任务 ID", retryable=False)
        return VideoSubmitResult(provider_task_id=str(task_id))

    async def poll(self, task_id: str, ctx: AdapterContext) -> VideoTaskStatus:
        tpl = ctx.template or self._template
        endpoint = tpl.poll
        if endpoint is None:
            raise VideoProviderError("VIDEO_PROTOCOL_UNSUPPORTED", "模板缺少轮询端点", retryable=False)
        await self._require_public(ctx.base_url)
        url = (ctx.base_url.rstrip("/") + endpoint.path).replace("{task_id}", task_id)
        try:
            async with self._client() as c:
                resp = await c.get(url, headers=self._headers(ctx))
        except httpx.HTTPError as exc:
            raise VideoProviderError("VIDEO_POLL_FAILED", "查询厂商状态失败") from exc
        if resp.status_code >= 400:
            raise VideoProviderError("VIDEO_POLL_FAILED", f"厂商查询返回 HTTP {resp.status_code}")
        data = resp.json()
        raw = _extract(data, endpoint.status_json_path) or ""
        return VideoTaskStatus(raw_status=str(raw))

    async def fetch_result_url(self, task_id: str, ctx: AdapterContext) -> str | None:
        tpl = ctx.template or self._template
        endpoint = tpl.result
        if endpoint is None:
            return None
        await self._require_public(ctx.base_url)
        url = (ctx.base_url.rstrip("/") + endpoint.path).replace("{task_id}", task_id)
        try:
            async with self._client() as c:
                resp = await c.get(url, headers=self._headers(ctx))
        except httpx.HTTPError:
            return None
        if resp.status_code >= 400:
            return None
        url_value = _extract(resp.json(), endpoint.result_url_json_path)
        return str(url_value) if url_value else None

    async def download_result(self, task_id: str, ctx: AdapterContext) -> bytes | None:
        url = await self.fetch_result_url(task_id, ctx)
        if not url:
            return None
        try:
            async with self._client() as c:
                resp = await c.get(url, headers=self._headers(ctx))
        except httpx.HTTPError:
            return None
        if resp.status_code >= 400:
            return None
        return resp.content

    async def cancel(self, task_id: str, ctx: AdapterContext) -> bool:
        # 通用 JSON 协议并未定义取消语义，按不支持处理（由 service 返回 409）。
        return False
