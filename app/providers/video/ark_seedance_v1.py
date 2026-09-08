"""ark_seedance_v1 火山方舟 Seedance 视频生成协议 Adapter（原生协议，无模板）。

依据火山方舟 Contents API 语义调用：
  - 提交 POST {base}/api/v3/contents/generations/tasks，响应顶层 id 为远端任务 ID；
  - 轮询 GET  {base}/api/v3/contents/generations/tasks/{task_id}，顶层 status 为远端状态；
  - 结果 GET  同上，响应 content.video_url 为厂商直链（24h 有效，双轨降级可用）；
  - 取消 DELETE {base}/api/v3/contents/generations/tasks/{task_id}（仅 queued 可取消）。

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

_SUBMIT_PATH = "/api/v3/contents/generations/tasks"
_TASK_PATH = "/api/v3/contents/generations/tasks/{task_id}"

# 远端状态 -> 本站统一状态（Ark 原生语义；expired 归为 failed）
_STATUS_MAP = {
    "queued": "queued",
    "running": "running",
    "succeeded": "succeeded",
    "failed": "failed",
    "cancelled": "cancelled",
    "expired": "failed",
}


def _build_content(request: dict[str, Any]) -> list[dict[str, Any]]:
    """按 request 里各素材 URL 是否为空，填充 Ark content 数组。

    规则：text 永远放第一项（纯文生视频时只有它）；随后依次是
    first_frame / last_frame / 各 reference_image / source_video / audio。
    """
    content: list[dict[str, Any]] = []
    if request.get("prompt"):
        content.append({"type": "text", "text": str(request["prompt"])})
    if request.get("first_frame_url"):
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": request["first_frame_url"]},
                "role": "first_frame",
            }
        )
    if request.get("last_frame_url"):
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": request["last_frame_url"]},
                "role": "last_frame",
            }
        )
    for url in request.get("reference_image_urls") or []:
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": url},
                "role": "reference_image",
            }
        )
    if request.get("source_video_url"):
        content.append(
            {
                "type": "video_url",
                "video_url": {"url": request["source_video_url"]},
            }
        )
    if request.get("audio_url"):
        content.append(
            {
                "type": "audio_url",
                "audio_url": {"url": request["audio_url"]},
            }
        )
    return content


def _build_body(request: dict[str, Any]) -> dict[str, Any]:
    """把本站 request dict 转成 Ark 提交请求体。

    值缺失的字段不放入 body（Ark 用默认值）；generate_audio 取 request，缺省为 True。
    """
    body: dict[str, Any] = {
        "model": request["remote_model_id"],
        "content": _build_content(request),
    }
    if request.get("duration_seconds"):
        body["duration"] = request["duration_seconds"]
    if request.get("resolution"):
        body["resolution"] = request["resolution"]
    if request.get("aspect_ratio"):
        body["ratio"] = request["aspect_ratio"]
    body["generate_audio"] = request.get("generate_audio", True)
    body["watermark"] = False
    body["return_last_frame"] = True
    body["camera_fixed"] = False
    return body


class ArkSeedanceProvider(VideoProvider):
    code = "ark_seedance_v1"

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
        payload = _build_body(request)
        try:
            async with self._client() as c:
                resp = await c.post(url, json=payload, headers=self._headers(ctx))
        except httpx.HTTPError as exc:
            raise VideoProviderError("VIDEO_SUBMISSION_FAILED", "提交厂商请求失败") from exc
        if not (200 <= resp.status_code < 300):
            raise VideoProviderError("VIDEO_SUBMISSION_FAILED", f"厂商拒绝任务（HTTP {resp.status_code}）", retryable=False)
        task_id = (resp.json() or {}).get("id")
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
        raw = data.get("status") or ""
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
        content = data.get("content") or {}
        return content.get("video_url")

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
        url = self._task_url(ctx, task_id)
        try:
            async with self._client() as c:
                resp = await c.delete(url, headers=self._headers(ctx))
        except httpx.HTTPError:
            return False
        return resp.status_code in (200, 202)
