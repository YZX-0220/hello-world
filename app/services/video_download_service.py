"""结果下载与双轨降级。

厂商生成成功（status=succeeded）后：
  - 优先把结果字节拉回本站，写成 purpose=result 的 Asset（local_asset_id）→ download_status=stored；
  - 拉不回（仅直链）且 ModelProfile 允许直链时 → download_status=direct，结果直链加密存
    encrypted_result_ref_json，view 解密返回 result_direct_url/result_expires_at 并标注临时直链；
  - 两者都不可行（下载失败且不允许直链）→ download_status=failed（不改变生成的 status）。
"""

import json
from datetime import timedelta
from typing import Any

from sqlmodel import select

from app.core.config import settings
from app.core.enums import DownloadStatus
from app.core.errors import VIDEO_DOWNLOAD_FAILED, AppError
from app.core.ids import new_id
from app.core.security import decrypt_secret, encrypt_secret
from app.core.time import now
from app.db.models.asset import Asset
from app.db.models.video_api_config import VideoApiConfigRevision
from app.db.models.video_job import VideoJob
from app.providers.video import get_video_provider
from app.providers.video.base import AdapterContext
from app.storage import LocalStorage
from app.video_registry import get_profile


class VideoDownloadService:
    def __init__(self, session: Any, storage: LocalStorage | None = None) -> None:
        self._session = session
        self._provider = get_video_provider()
        self._storage = storage or LocalStorage(settings.storage_root)

    async def fetch_result_asset(self, job: VideoJob) -> str:
        """对已成功的任务执行一次下载/降级，返回更新后的 download_status。"""
        if job.status != "succeeded":
            raise AppError(VIDEO_DOWNLOAD_FAILED, "任务尚未生成成功，不能下载结果")
        if job.api_config_id is None:
            # 平台自有通道：无用户 revision，改用平台 ctx（base_url/auth/model）。
            revision = None
            ctx = self._platform_ctx()
        else:
            revision = (
                await self._session.exec(select(VideoApiConfigRevision).where(VideoApiConfigRevision.id == job.api_config_revision_id))
            ).first()
            ctx = self._ctx(revision)
        data = await self._provider.download_result(job.provider_task_id or "", ctx)
        if data:
            return await self._store_result(job, data)
        return await self._fallback_direct(job, revision, ctx)

    async def _store_result(self, job: VideoJob, data: bytes) -> str:
        asset_id = new_id()
        storage_key = f"{job.user_id}/{asset_id}.mp4"
        stored = self._storage.write_stream(data, storage_key, final_key=storage_key)
        asset = Asset(
            id=asset_id,
            user_id=job.user_id,
            conversation_id=job.conversation_id,
            kind="video",
            purpose="result",
            original_name=f"video-{job.id[:8]}.mp4",
            storage_key=storage_key,
            mime_type="video/mp4",
            size_bytes=stored.size_bytes,
            sha256=stored.sha256,
            status="ready",
            retention_until=now() + timedelta(days=settings.result_retention_days),
        )
        self._session.add(asset)
        job.local_asset_id = asset_id
        job.download_status = DownloadStatus.STORED.value
        job.encrypted_result_ref_json = None
        job.completed_at = job.completed_at or now()
        await self._session.commit()
        return DownloadStatus.STORED.value

    async def _fallback_direct(self, job: VideoJob, revision: VideoApiConfigRevision | None, ctx: AdapterContext) -> str:
        url = await self._provider.fetch_result_url(job.provider_task_id or "", ctx)
        profile = None
        if revision is not None and revision.capability_profile_code:
            profile = get_profile(revision.protocol_code, revision.capability_profile_code)
        if profile is not None and url and profile.allows_provider_direct_url:
            expires = now() + timedelta(seconds=profile.provider_direct_url_ttl)
            job.encrypted_result_ref_json = encrypt_secret(
                json.dumps({"direct_url": url, "expires_at": expires.isoformat()}, ensure_ascii=False),
                settings.credential_encryption_keys,
            )
            job.download_status = DownloadStatus.DIRECT.value
        else:
            job.download_status = DownloadStatus.FAILED.value
        job.completed_at = job.completed_at or now()
        await self._session.commit()
        return job.download_status

    @staticmethod
    def _ctx(revision: VideoApiConfigRevision | None) -> AdapterContext:
        if revision is None:
            return AdapterContext(base_url="", auth={}, options={}, remote_model_id="")
        return AdapterContext(
            base_url=revision.base_url or "",
            auth=json.loads(decrypt_secret(revision.encrypted_auth_json, settings.credential_encryption_keys)),
            options=json.loads(revision.public_options_json or "{}"),
            remote_model_id=revision.remote_model_id,
            template=None,
        )

    @staticmethod
    def _platform_ctx() -> AdapterContext:
        """平台自有通道的厂商上下文：直接读 settings.video_platform_*，无 revision。"""
        return AdapterContext(
            base_url=settings.video_platform_base_url,
            auth={"api_key": settings.video_platform_api_key},
            options={},
            remote_model_id=settings.video_platform_model,
            template=None,
        )
