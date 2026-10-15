"""ark_seedance_v1 火山方舟 Seedance 视频生成协议 Adapter（原生协议，无模板）。

依据火山方舟 Contents API 语义调用：
  - 提交 POST {base}/api/v3/contents/generations/tasks，响应顶层 id 为远端任务 ID；
  - 轮询 GET  {base}/api/v3/contents/generations/tasks/{task_id}，顶层 status 为远端状态；
  - 结果 GET  同上，响应 content.video_url 为厂商直链（24h 有效，双轨降级可用）；
  - 取消 DELETE {base}/api/v3/contents/generations/tasks/{task_id}（仅 queued 可取消）。

安全：单独实例化的 httpx 客户端 trust_env=False（防误继承代理）、禁止自动跳转；
  base 与下载直链在请求前都做 SSRF 校验（check_base_url）。
"""

import json
import logging
import re
from typing import Any
from urllib.parse import urlsplit

import httpx

from app.core.config import settings
from app.core.ssrf import UnsafeUrlError, check_base_url, validate_public_host
from app.providers.video.base import (
    AdapterContext,
    VideoProvider,
    VideoProviderError,
    VideoSubmitResult,
    VideoTaskStatus,
)

_SUBMIT_PATH = "/api/v3/contents/generations/tasks"
logger = logging.getLogger("app.providers.video.ark")
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


def _failure(error: Any, fallback="厂商未返回具体原因") -> tuple[str, str]:
    error = error if isinstance(error, dict) else {}
    code = str(error.get("code") or "PROVIDER_TASK_FAILED")[:64]
    detail = str(error.get("message") or fallback)
    detail = re.sub(r"https?://[^\s\"<>]+", "[素材地址]", detail)
    detail = re.sub(r"(?i)Bearer\s+\S+", "Bearer [已隐藏]", detail)[:1200]
    lowered = (code + " " + detail).lower()
    if any(word in lowered for word in ("real person", "real human", "human face", "portrait", "人脸", "真人")):
        hint = "该素材涉及真人人像准入要求；当前普通图片入口尚未接入专用人像通道，请更换素材。"
    elif any(word in lowered for word in ("sensitive", "contentpolicy", "moderation")):
        hint = "内容未通过厂商审核，请调整描述或素材后重新审理。"
    elif any(word in lowered for word in ("authentication", "unauthorized", "accessdenied", "apikey")):
        hint = "请检查视频通道的密钥、模型开通状态和调用权限。"
    elif any(word in lowered for word in ("quota", "balance", "ratelimit", "overdue")):
        hint = "请检查厂商余额、额度或并发限制，稍后再试。"
    elif "tasktype" in lowered:
        hint = "厂商判定的任务类型与本次模式不一致，请调整描述后重新审理。"
    else:
        hint = "请根据厂商原因调整素材或参数后重新审理。"
    return code, f"{hint}\n厂商原因（{code}）：{detail}"


def _response_failure(resp: httpx.Response) -> tuple[str, str]:
    try:
        payload = resp.json()
    except ValueError:
        payload = {}
    error = payload.get("error") if isinstance(payload, dict) else None
    if not isinstance(error, dict):
        error = {"message": error or f"HTTP {resp.status_code}"}
    error.setdefault("code", "VIDEO_SUBMISSION_FAILED")
    return _failure(error, f"HTTP {resp.status_code}")


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
    if "generate_audio" in request:
        body["generate_audio"] = request["generate_audio"]
    if request.get("execution_expires_after"):
        body["execution_expires_after"] = request["execution_expires_after"]
    target = request.get("generation_target") or {}
    if ((request.get("remote_model_id") == "doubao-seedance-2-5-260628"
         or target.get("profile_code") == "doubao-seedance-2-5")
            and request.get("mode") == "reference_image_to_video"):
        body["omni_reference_task_type"] = "reference"
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
        for item in payload["content"]:
            media = item.get(item["type"])
            media_url = str(media.get("url", "")) if isinstance(media, dict) else ""
            if media_url.startswith(("http://", "https://")):
                # 素材是本站受控地址（可为 http，如 http://<APP_BASE_URL 主机>/api/v1/provider-assets/…）。
                # 只校验其主机名解析为公网可达即可；不能套用 check_base_url（那要求 HTTPS，仅适用于用户自配的厂商 base_url）。
                host = urlsplit(media_url).hostname or ""
                try:
                    validate_public_host(host)
                except UnsafeUrlError as exc:
                    raise VideoProviderError(
                        "VIDEO_INPUT_UNREACHABLE",
                        "素材地址不是厂商可访问的公网地址，请检查后端 APP_BASE_URL 和域名解析。",
                        retryable=False,
                    ) from exc
        if len(json.dumps(payload, ensure_ascii=False).encode("utf-8")) > 64_000_000:
            raise VideoProviderError("VIDEO_SUBMISSION_FAILED", "生成请求超过厂商 64 MB 上限，请精简方案。", retryable=False)
        try:
            async with self._client() as c:
                resp = await c.post(url, json=payload, headers=self._headers(ctx))
        except httpx.HTTPError as exc:
            raise VideoProviderError("VIDEO_SUBMISSION_FAILED", "提交厂商请求失败") from exc
        if not (200 <= resp.status_code < 300):
            logger.warning("Ark 提交被拒 HTTP %s: %s", resp.status_code, resp.text[:1500])
            code, message = _response_failure(resp)
            raise VideoProviderError(code, message, retryable=False)
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
            logger.warning("Ark 查询返回 HTTP %s: %s", resp.status_code, resp.text[:1200])
            raise VideoProviderError("VIDEO_POLL_FAILED", f"厂商查询返回 HTTP {resp.status_code}")
        data = resp.json() or {}
        raw = data.get("status") or ""
        mapped = _STATUS_MAP.get(raw, raw)
        code, message = None, None
        if raw == "failed":
            code, message = _failure(data.get("error"))
        elif raw == "expired":
            code, message = "PROVIDER_TASK_EXPIRED", "厂商任务排队或执行超时，请稍后重试。"
        return VideoTaskStatus(raw_status=str(mapped), error_code=code, error_message=message,
                               extra={"remote_status": str(raw)})

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
