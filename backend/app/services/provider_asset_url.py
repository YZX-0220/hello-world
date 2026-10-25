"""视频厂商短时读取素材的签名入口（实施计划 4.9 / 接口说明 7.6）。

- Token 绑定 asset_id、job_id、用途、过期时间与随机 nonce；
- 默认有效期 settings.signed_url_ttl_seconds（10 分钟）；
- 有效期内允许厂商重复 GET/HEAD/Range，nonce 只登记；
- 只返回被当前任务引用且 status=ready 的文件；日志不记录完整签名。
"""

import base64
import hashlib
import hmac
import json
import os
import time
from datetime import timedelta
from typing import Any

from sqlmodel import select

from app.core.time import now
from app.db.models.asset import Asset
from app.db.models.video_job import VideoJob, VideoJobAsset


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def sign_provider_asset(
    asset_id: str, job_id: str, purpose: str, secret: str, ttl_seconds: int
) -> tuple[str, "Any"]:
    """生成签名 Token 与过期时间（纯 HMAC，无 DB/Redis 依赖）。"""
    expires_at = now() + timedelta(seconds=ttl_seconds)
    payload = json.dumps(
        {
            "aid": asset_id,
            "jid": job_id,
            "purpose": purpose,
            "exp": int(expires_at.timestamp()),
            "n": os.urandom(8).hex(),
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    body = _b64(payload)
    sig = hmac.new(secret.encode("utf-8"), body.encode("ascii"), hashlib.sha256).hexdigest()
    return f"{body}.{sig}", expires_at


class ProviderAssetUrlService:
    def __init__(self, session: Any, redis: Any, secret: str) -> None:
        self._session = session
        self._redis = redis
        self._secret = secret

    async def verify_subject(self, token: str) -> dict | None:
        """校验签名、过期、任务与用途；再确认素材 ready。

        校验通过返回 payload（含 aid/jid/purpose），否则返回 None（调用方 404/410）。
        """
        try:
            body, sig = token.split(".", 1)
        except ValueError:
            return None
        expected = hmac.new(
            self._secret.encode("utf-8"), body.encode("ascii"), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(expected, sig):
            return None
        try:
            payload = json.loads(_unb64(body))
        except (ValueError, json.JSONDecodeError):
            return None

        now_ts = int(time.time())
        exp = int(payload.get("exp", 0))
        if exp < now_ts:
            return None  # 过期 -> 410
        job = (
            await self._session.exec(select(VideoJob).where(VideoJob.id == payload.get("jid", "")))
        ).first()
        if job is None or job.status not in ("created", "submitting", "queued", "running"):
            return None

        # 厂商会对同一素材发起多次读取（首次命中、后续重试 / 多路读取），
        # 故这里只校验签名、过期与归属，不再做"单次消费"拦截；nonce 仅登记不阻断。
        nonce_key = f"provider-asset-nonce:{payload.get('n', '')}"
        await self._redis.set(nonce_key, "1", ex=max(exp - now_ts, 1))

        # 素材必须属于该任务且为 ready
        asset = (
            await self._session.exec(select(Asset).where(Asset.id == payload.get("aid", "")))
        ).first()
        if asset is None or asset.status != "ready" or asset.user_id != job.user_id:
            return None
        job_ref = (
            await self._session.exec(
                select(VideoJobAsset).where(
                    VideoJobAsset.asset_id == payload.get("aid", ""),
                    VideoJobAsset.video_job_id == payload.get("jid", ""),
                    VideoJobAsset.role == payload.get("purpose", ""),
                )
            )
        ).first()
        if job_ref is None:
            return None

        return payload
