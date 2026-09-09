"""fal_queue_v1 fal.ai 队列视频生成协议 Adapter（原生协议，无模板）。

依据 fal Queue API 语义调用：
  - 提交 POST {base}/{remote_model_id}：base 为协议官方地址（https://queue.fal.run），
    remote_model_id 是模型端点（形如 fal-ai/wan/.../text-to-video/turbo，含多段路径，直接拼在 base 后）；
    鉴权头为 `Authorization: Key <api_key>`（注意是 Key 前缀而非 Bearer）；
    响应 request_id 作为远端任务 ID（provider_task_id）；
  - 轮询 GET {base}/fal-ai/requests/{task_id}/status（即 status_url），顶层 status 为远端状态；
  - 结果 GET {base}/fal-ai/requests/{task_id}（即 response_url），成功时 output.video.url(数组) /
    output.video(字符串) / output.videos.0.url 为厂商直链；
  - 取消 DELETE {base}/fal-ai/requests/{task_id}/cancel（cancel_url），2xx 视为取消成功。

任务 ID（request_id）统一用于拼接 status / response / cancel 三类 URL（均在
{base}/fal-ai/requests/ 之下），所以 poll/fetch/cancel 都通过 _requests_url 复用。

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

# 远端状态 -> 本站统一状态（fal 原生语义；未列出的原样透传）
_STATUS_MAP = {
    "IN_QUEUE": "queued",
    "IN_PROGRESS": "running",
    "COMPLETED": "succeeded",
    "FAILED": "failed",
    "CANCELED": "cancelled",
}


def _extract(obj: Any, dotpath: str) -> Any:
    """按点分字段路径取值（如 output.video.url）；支持字典与数组下标。结构不支持则返回 None。"""
    if not dotpath:
        return None
    cur: Any = obj
    for part in dotpath.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        elif isinstance(cur, list) and part.isdigit():
            idx = int(part)
            cur = cur[idx] if idx < len(cur) else None
        else:
            return None
        if cur is None:
            return None
    return cur


def _video_url(data: dict[str, Any]) -> str | None:
    """从 fal 结果响应提取视频直链。

    依次尝试：output.video.url(数组，取首项) → output.video(字符串) → output.videos.0.url。
    """
    candidate = _extract(data, "output.video.url")
    if isinstance(candidate, list):
        return str(candidate[0]) if candidate else None
    if isinstance(candidate, str):
        return candidate
    candidate = _extract(data, "output.video")
    if isinstance(candidate, str):
        return candidate
    candidate = _extract(data, "output.videos.0.url")
    if isinstance(candidate, str):
        return candidate
    return None


class FalQueueV1Provider(VideoProvider):
    code = "fal_queue_v1"

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
        return {"Authorization": f"Key {api_key}"} if api_key else {}

    def _requests_url(self, ctx: AdapterContext, task_id: str) -> str:
        """request_id（provider_task_id）对应的一组查询 URL 的基址（{base}/fal-ai/requests/{task_id}）。"""
        return ctx.base_url.rstrip("/") + "/fal-ai/requests/" + task_id

    async def submit(self, request: dict[str, Any], ctx: AdapterContext) -> VideoSubmitResult:
        await self._require_public(ctx.base_url)
        # 模型端点（多段路径）直接拼在官方 base 后：POST {base}/{remote_model_id}
        url = ctx.base_url.rstrip("/") + "/" + ctx.remote_model_id
        payload: dict[str, Any] = {}
        if request.get("prompt") is not None:
            payload["prompt"] = request["prompt"]
        if request.get("resolution") is not None:
            payload["resolution"] = request["resolution"]
        if request.get("aspect_ratio") is not None:
            payload["aspect_ratio"] = request["aspect_ratio"]
        if request.get("duration_seconds") is not None:
            payload["duration"] = request["duration_seconds"]
        headers = self._headers(ctx)
        headers["Content-Type"] = "application/json"
        headers["Accept"] = "application/json"
        try:
            async with self._client() as c:
                resp = await c.post(url, json=payload, headers=headers)
        except httpx.HTTPError as exc:
            raise VideoProviderError("VIDEO_SUBMISSION_FAILED", "提交厂商请求失败") from exc
        if not (200 <= resp.status_code < 300):
            raise VideoProviderError("VIDEO_SUBMISSION_FAILED", f"厂商拒绝任务（HTTP {resp.status_code}）", retryable=False)
        task_id = (resp.json() or {}).get("request_id")
        if not task_id:
            raise VideoProviderError("VIDEO_SUBMISSION_FAILED", "厂商响应缺少任务 ID", retryable=False)
        return VideoSubmitResult(provider_task_id=str(task_id))

    async def poll(self, task_id: str, ctx: AdapterContext) -> VideoTaskStatus:
        await self._require_public(ctx.base_url)
        url = self._requests_url(ctx, task_id) + "/status"
        try:
            async with self._client() as c:
                resp = await c.get(url, headers=self._headers(ctx))
        except httpx.HTTPError as exc:
            raise VideoProviderError("VIDEO_POLL_FAILED", "查询厂商状态失败") from exc
        if resp.status_code >= 400:
            raise VideoProviderError("VIDEO_POLL_FAILED", f"厂商查询返回 HTTP {resp.status_code}")
        data = resp.json() or {}
        raw = data.get("status") or ""
        mapped = _STATUS_MAP.get(raw, raw)
        return VideoTaskStatus(raw_status=str(mapped), extra={"remote_status": str(raw)})

    async def fetch_result_url(self, task_id: str, ctx: AdapterContext) -> str | None:
        await self._require_public(ctx.base_url)
        url = self._requests_url(ctx, task_id)
        try:
            async with self._client() as c:
                resp = await c.get(url, headers=self._headers(ctx))
        except httpx.HTTPError:
            return None
        if resp.status_code >= 400:
            return None
        data = resp.json() or {}
        return _video_url(data)

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
        await self._require_public(ctx.base_url)
        url = self._requests_url(ctx, task_id) + "/cancel"
        try:
            async with self._client() as c:
                resp = await c.delete(url, headers=self._headers(ctx))
        except httpx.HTTPError:
            return False
        return 200 <= resp.status_code < 300
