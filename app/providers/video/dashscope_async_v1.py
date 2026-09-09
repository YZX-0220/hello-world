"""dashscope_async_v1 阿里云百炼 DashScope / 通义 Wan 文生视频 Adapter（原生协议，无模板）。

依据 DashScope 异步任务语义调用：
  - 提交 POST {base}/api/v1/services/aigc/video-generation/video-synthesis，必须带
    X-DashScope-Async: enable 头（缺失会报 "does not support synchronous calls"）；
    响应优先取 output.task_id，回退顶层 task_id；
  - 轮询 GET {base}/api/v1/tasks/{task_id}，顶层 task_status 为远端状态；
  - 结果 GET 同上，output.video_url 为厂商直链（24h 有效，双轨降级可用）；
  - 取消：DashScope 无取消接口，cancel 返回 False（由 service 层返回 409）。

安全：单独实例化的 httpx 客户端 trust_env=False（防误继承代理）、禁止自动跳转；
  base 与下载直链在请求前都做 SSRF 校验（check_base_url）。
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

_SUBMIT_PATH = "/api/v1/services/aigc/video-generation/video-synthesis"
_TASK_PATH = "/api/v1/tasks/{task_id}"

# 远端状态 -> 本站统一状态（DashScope 原生语义；未列出的如 UNKNOWN 原样透传）
_STATUS_MAP = {
    "PENDING": "queued",
    "RUNNING": "running",
    "SUCCEEDED": "succeeded",
    "FAILED": "failed",
}

# 分辨率 -> DashScope size 参数（宽*高；不在映射内则忽略该参数）
_RESOLUTION_SIZE_MAP = {
    "480p": "832*480",
    "720p": "1280*720",
    "1080p": "1920*1080",
}


def _extract(obj: Any, dotpath: str) -> Any:
    """按点分字段路径取值（如 output.task_id）；结构不支持则返回 None。"""
    if not dotpath:
        return None
    cur: Any = obj
    for part in dotpath.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur


class DashScopeAsyncV1Provider(VideoProvider):
    code = "dashscope_async_v1"

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

    def _task_url(self, ctx: AdapterContext, task_id: str) -> str:
        return (ctx.base_url.rstrip("/") + _TASK_PATH).replace("{task_id}", task_id)

    async def submit(self, request: dict[str, Any], ctx: AdapterContext) -> VideoSubmitResult:
        await self._require_public(ctx.base_url)
        url = ctx.base_url.rstrip("/") + _SUBMIT_PATH
        parameters: dict[str, Any] = {}
        resolution = request.get("resolution")
        if resolution in _RESOLUTION_SIZE_MAP:
            parameters["size"] = _RESOLUTION_SIZE_MAP[resolution]
        if request.get("duration_seconds"):
            parameters["duration"] = request["duration_seconds"]
        payload: dict[str, Any] = {
            "model": request["remote_model_id"],
            "input": {"prompt": request.get("prompt", "")},
            "parameters": parameters,
        }
        headers = self._headers(ctx)
        headers["X-DashScope-Async"] = "enable"
        headers["Content-Type"] = "application/json"
        try:
            async with self._client() as c:
                resp = await c.post(url, json=payload, headers=headers)
        except httpx.HTTPError as exc:
            raise VideoProviderError("VIDEO_SUBMISSION_FAILED", "提交厂商请求失败") from exc
        if not (200 <= resp.status_code < 300):
            raise VideoProviderError("VIDEO_SUBMISSION_FAILED", f"厂商拒绝任务（HTTP {resp.status_code}）", retryable=False)
        data = resp.json() or {}
        task_id = _extract(data, "output.task_id") or (data.get("task_id") or "")
        if not task_id:
            raise VideoProviderError("VIDEO_SUBMISSION_FAILED", "厂商响应缺少任务 ID", retryable=False)
        return VideoSubmitResult(provider_task_id=str(task_id))

    async def poll(self, task_id: str, ctx: AdapterContext) -> VideoTaskStatus:
        await self._require_public(ctx.base_url)
        url = self._task_url(ctx, task_id)
        try:
            async with self._client() as c:
                resp = await c.get(url, headers=self._headers(ctx))
        except httpx.HTTPError as exc:
            raise VideoProviderError("VIDEO_POLL_FAILED", "查询厂商状态失败") from exc
        if resp.status_code >= 400:
            raise VideoProviderError("VIDEO_POLL_FAILED", f"厂商查询返回 HTTP {resp.status_code}")
        data = resp.json() or {}
        raw = data.get("task_status") or ""
        mapped = _STATUS_MAP.get(raw, raw)
        return VideoTaskStatus(raw_status=str(mapped), extra={"remote_status": str(raw)})

    async def fetch_result_url(self, task_id: str, ctx: AdapterContext) -> str | None:
        await self._require_public(ctx.base_url)
        url = self._task_url(ctx, task_id)
        try:
            async with self._client() as c:
                resp = await c.get(url, headers=self._headers(ctx))
        except httpx.HTTPError:
            return None
        if resp.status_code >= 400:
            return None
        data = resp.json() or {}
        return _extract(data, "output.video_url")

    async def download_result(self, task_id: str, ctx: AdapterContext) -> bytes | None:
        url = await self.fetch_result_url(task_id, ctx)
        if not url:
            return None
        try:
            check_base_url(url)
        except UnsafeUrlError:
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
        # DashScope 无取消接口，按不支持处理（由 service 层返回 409 VIDEO_CANCEL_UNSUPPORTED）。
        return False
