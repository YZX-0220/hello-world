"""视频任务：创建并提交（校验/幂等/无密钥 request_json/状态机）、查询。

对应《实施计划》4.11 与接口说明 8.1~8.3。阶段 8 先做到「创建提交 → 轮询状态机」；
阶段 9 再补 next_poll_at 锁、结果下载与双轨降级。
"""

import hashlib
import json
from contextlib import suppress
from datetime import datetime, timedelta
from typing import Any

from sqlmodel import select

from app.core.config import settings
from app.core.cursor import encode_cursor
from app.core.enums import DownloadStatus, JobEventType, VideoJobStatus
from app.core.errors import (
    ASSET_NOT_FOUND,
    IDEMPOTENCY_KEY_REUSED,
    PROJECT_NOT_CONFIRMED,
    VIDEO_CANCEL_UNSUPPORTED,
    VIDEO_CONFIG_INVALID,
    VIDEO_DOWNLOAD_FAILED,
    VIDEO_INPUT_INVALID,
    VIDEO_MODE_UNSUPPORTED,
    VIDEO_OPTION_UNSUPPORTED,
    VIDEO_POLL_FAILED,
    VIDEO_PROTOCOL_UNSUPPORTED,
    VIDEO_SUBMISSION_FAILED,
    AppError,
)
from app.core.ids import new_id
from app.core.security import decrypt_secret
from app.core.time import now
from app.db.models.project import VideoProject, VideoProjectVersion
from app.db.models.video_api_config import VideoApiConfigRevision
from app.db.models.video_job import VideoJob, VideoJobAsset, VideoJobEvent
from app.providers.video import get_video_provider
from app.providers.video.base import AdapterContext, VideoProviderError
from app.repositories.assets import AssetRepository
from app.repositories.video_api_configs import (
    VideoApiConfigRepository,
    VideoApiConfigRevisionRepository,
)
from app.repositories.video_jobs import (
    VideoJobAssetRepository,
    VideoJobEventRepository,
    VideoJobRepository,
)
from app.schemas.agent import VideoBrief
from app.schemas.video_job import CreateVideoCommand, ErrorInfo, VideoJobEventView, VideoJobView
from app.services.provider_asset_url import sign_provider_asset
from app.services.video_download_service import VideoDownloadService
from app.video_registry import get_template
from app.video_registry.models import EndpointSpec, ProtocolTemplate

_ERROR_MAP = {
    "VIDEO_SUBMISSION_FAILED": VIDEO_SUBMISSION_FAILED,
    "VIDEO_POLL_FAILED": VIDEO_POLL_FAILED,
    "VIDEO_MODE_UNSUPPORTED": VIDEO_MODE_UNSUPPORTED,
    "VIDEO_PROTOCOL_UNSUPPORTED": VIDEO_PROTOCOL_UNSUPPORTED,
    "UNSAFE_BASE_URL": VIDEO_PROTOCOL_UNSUPPORTED,
}


def _provider_error(exc: VideoProviderError) -> AppError:
    return AppError(_ERROR_MAP.get(exc.code, VIDEO_SUBMISSION_FAILED), exc.message)


def _build_custom_template(custom_template_json: str | None) -> ProtocolTemplate | None:
    """把落库的自定义模板 JSON 反序列化成 ProtocolTemplate（供 Adapter 使用）。

    template_mode=="custom"（custom_template_json 非空）时返回用户模板；
    否则返回 None（Adapter 将按内置 V1_VIDEOS_TEMPLATE 行事）。

    自定义模板只有一份查询路径（poll_path）同时承载状态与成品地址，因此
    poll/result 两个 EndpointSpec 共用该路径，status/result_url 分别取
    status_path / result_url_path。
    """
    if not custom_template_json:
        return None
    data = json.loads(custom_template_json)
    poll_path = data.get("poll_path", "/tasks/{task_id}")
    return ProtocolTemplate(
        template_code="custom",
        protocol_code="generic_async_json_v1",
        name="用户自定义模板",
        version=1,
        submit=EndpointSpec(
            method=data.get("submit_method", "POST"),
            path=data.get("submit_path", "/tasks"),
            success_statuses=frozenset({200, 201, 202}),
            id_json_path=data.get("task_id_path", "data.task_id"),
            request_template_json=data.get("request_template_json") or {},
        ),
        poll=EndpointSpec(
            method=data.get("poll_method", "GET"),
            path=poll_path,
            success_statuses=frozenset({200}),
            status_json_path=data.get("status_path", "data.status"),
        ),
        result=EndpointSpec(
            method="GET",
            path=poll_path,
            success_statuses=frozenset({200}),
            result_url_json_path=data.get("result_url_path", "data.url"),
        ),
        remote_status_map=data.get("status_map") or {},
    )


def _fingerprint(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def _asset_ids(spec: VideoBrief) -> list[tuple[str, str, int]]:
    rows: list[tuple[str, str, int]] = []
    if spec.first_frame_asset_id:
        rows.append((spec.first_frame_asset_id, "first_frame", 0))
    if spec.last_frame_asset_id:
        rows.append((spec.last_frame_asset_id, "last_frame", 0))
    for i, aid in enumerate(spec.reference_asset_ids or []):
        rows.append((aid, "reference", i))
    if spec.source_video_asset_id:
        rows.append((spec.source_video_asset_id, "source_video", 0))
    if spec.audio_asset_id:
        rows.append((spec.audio_asset_id, "audio", 0))
    return rows


class VideoJobService:
    def __init__(self, session: Any, redis: Any = None) -> None:
        self._session = session
        self._redis = redis
        self._repo = VideoJobRepository(session)
        self._events = VideoJobEventRepository(session)
        self._job_assets = VideoJobAssetRepository(session)
        self._assets = AssetRepository(session)
        self._configs = VideoApiConfigRepository(session)
        self._revisions = VideoApiConfigRevisionRepository(session)
        self._provider = get_video_provider()
        self._downloader: VideoDownloadService | None = None

    async def create(self, user_id: str, command: CreateVideoCommand, idempotency_key: str) -> tuple[VideoJob, bool]:
        project = await self._load_project(user_id, command)
        self._validate_confirmed(project, command.spec_version)
        config, revision = await self._active_config(user_id, command.api_config_id)

        spec = VideoBrief.model_validate(json.loads(project.current_spec_json or "{}"))
        self._validate_mode(command, spec)
        assets = await self._require_assets(user_id, spec)

        request_json = self._build_request_json(command, spec, revision)
        fingerprint = _fingerprint(
            {"project_version": command.spec_version, "api_config_revision": config.current_revision, "mode": command.mode, "request": request_json}
        )

        existing = await self._repo.get_by_idempotency(user_id, idempotency_key)
        if existing is not None:
            if existing.request_fingerprint != fingerprint:
                raise AppError(IDEMPOTENCY_KEY_REUSED)
            return existing, True

        version_row = (
            await self._session.exec(
                select(VideoProjectVersion).where(
                    VideoProjectVersion.project_id == project.id,
                    VideoProjectVersion.version == command.spec_version,
                )
            )
        ).first()

        job = VideoJob(
            id=new_id(),
            user_id=user_id,
            conversation_id=command.conversation_id,
            project_id=project.id,
            project_version_id=version_row.id if version_row else project.id,
            project_version=command.spec_version,
            api_config_id=config.id,
            api_config_revision_id=revision.id,
            previous_job_id=command.previous_job_id,
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint,
            protocol_code=revision.protocol_code,
            template_code=revision.template_code,
            remote_model_id=revision.remote_model_id,
            mode=command.mode,
            status=VideoJobStatus.CREATED.value,
            request_json=json.dumps(request_json, ensure_ascii=False),
            download_status=DownloadStatus.NOT_STARTED.value,
        )
        await self._repo.add(job)
        for asset_id, role, position in assets:
            await self._job_assets.add(VideoJobAsset(video_job_id=job.id, asset_id=asset_id, role=role, position=position))

        job.status = VideoJobStatus.SUBMITTING.value
        await self._events.add(
            VideoJobEvent(video_job_id=job.id, event_type=JobEventType.SUBMIT.value, to_status=job.status)
        )
        await self._session.commit()
        await self._session.refresh(job)

        try:
            result = await self._provider.submit(self._provider_request(job, assets), self._ctx(revision))
            job.provider_task_id = result.provider_task_id
            job.provider_context_id = result.provider_context_id
            job.status = VideoJobStatus.QUEUED.value
            job.submitted_at = now()
        except VideoProviderError as exc:
            if exc.retryable:
                job.status = VideoJobStatus.SUBMITTING.value
                job.error_code = "PROVIDER_SUBMISSION_UNKNOWN"
                job.error_message = "无法确认厂商是否已接受"
            else:
                job.status = VideoJobStatus.FAILED.value
                job.completed_at = now()
                job.error_code = exc.code
                job.error_message = exc.message[:2000]
        await self._events.add(
            VideoJobEvent(video_job_id=job.id, event_type=JobEventType.STATUS_CHANGE.value, to_status=job.status)
        )
        await self._repo.save(job)
        return job, False

    async def get(self, user_id: str, job_id: str, allow_refresh: bool = True) -> VideoJob:
        job = await self._repo.get_for_user(job_id, user_id)
        if job is None:
            raise AppError(VIDEO_CONFIG_INVALID, "视频任务不存在或无权访问")
        # 双轨：生成成功但还未下载/降级时，在读取时安全触发一次
        if job.status == VideoJobStatus.SUCCEEDED.value and job.download_status == DownloadStatus.NOT_STARTED.value:
            await self._trigger_download(job)
        if allow_refresh and job.status in (VideoJobStatus.QUEUED.value, VideoJobStatus.RUNNING.value) and self._poll_due(job):
            await self._maybe_refresh(job)
        return job

    async def list_jobs(
        self,
        user_id: str,
        conversation_id: str | None = None,
        status: str | None = None,
        download_status: str | None = None,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> tuple[list[VideoJob], str | None]:
        """按 (created_at desc, id desc) 游标分页，返回 (page_rows, next_cursor)。"""
        rows = await self._repo.list_for_user(user_id, conversation_id, status, download_status, limit, cursor)
        has_more = len(rows) > limit if limit else False
        page = rows[:limit] if limit else rows
        next_cursor = encode_cursor(page[-1].created_at, page[-1].id) if page and has_more else None
        return page, next_cursor

    async def cancel(self, user_id: str, job_id: str) -> VideoJob:
        job = await self._repo.get_for_user(job_id, user_id)
        if job is None:
            raise AppError(VIDEO_CONFIG_INVALID, "视频任务不存在或无权访问")
        if job.status in (VideoJobStatus.SUCCEEDED.value, VideoJobStatus.FAILED.value, VideoJobStatus.CANCELLED.value):
            return job  # 幂等返回终态
        revision = (
            await self._session.exec(select(VideoApiConfigRevision).where(VideoApiConfigRevision.id == job.api_config_revision_id))
        ).first()
        supported = await self._provider.cancel(job.provider_task_id or "", self._ctx(revision))
        if not supported:
            raise AppError(VIDEO_CANCEL_UNSUPPORTED)
        old = job.status
        job.status = VideoJobStatus.CANCELLED.value
        job.completed_at = now()
        await self._events.add(
            VideoJobEvent(video_job_id=job.id, event_type=JobEventType.CANCEL.value, from_status=old, to_status=job.status)
        )
        await self._repo.save(job)
        return job

    async def retry_download(self, user_id: str, job_id: str) -> VideoJob:
        job = await self._repo.get_for_user(job_id, user_id)
        if job is None:
            raise AppError(VIDEO_CONFIG_INVALID, "视频任务不存在或无权访问")
        if job.status != VideoJobStatus.SUCCEEDED.value or job.download_status != DownloadStatus.FAILED.value:
            raise AppError(VIDEO_DOWNLOAD_FAILED, "仅当生成成功且下载失败时可重试下载")
        if self._downloader is None:
            self._downloader = VideoDownloadService(self._session)
        await self._downloader.fetch_result_asset(job)
        return await self._repo.get_for_user(job_id, user_id) or job

    async def _maybe_refresh(self, job: VideoJob) -> None:
        if not await self._acquire_poll_lock(job.id):
            return  # 已有人在轮询，避免轰炸厂商
        try:
            await self._refresh(job)
        finally:
            await self._release_poll_lock(job.id)

    async def _trigger_download(self, job: VideoJob) -> None:
        if self._downloader is None:
            self._downloader = VideoDownloadService(self._session)
        try:
            await self._downloader.fetch_result_asset(job)
        except Exception:
            job.download_status = DownloadStatus.FAILED.value
            await self._repo.save(job)

    def _poll_due(self, job: VideoJob) -> bool:
        if not job.provider_task_id:
            return False
        if job.next_poll_at is None:
            return True
        return now() >= job.next_poll_at

    async def _acquire_poll_lock(self, job_id: str) -> bool:
        if self._redis is None:
            return True
        with suppress(Exception):
            return bool(await self._redis.set(f"video-job-poll:{job_id}", "1", ex=4, nx=True))
        return True

    async def _release_poll_lock(self, job_id: str) -> None:
        if self._redis is None:
            return
        with suppress(Exception):
            await self._redis.delete(f"video-job-poll:{job_id}")

    async def events(self, user_id: str, job_id: str) -> list[VideoJobEvent]:
        if await self._repo.get_for_user(job_id, user_id) is None:
            raise AppError(VIDEO_CONFIG_INVALID, "视频任务不存在或无权访问")
        return await self._events.list_for_job(job_id)

    async def _refresh(self, job: VideoJob) -> None:
        if not job.provider_task_id:
            return
        revision = (
            await self._session.exec(select(VideoApiConfigRevision).where(VideoApiConfigRevision.id == job.api_config_revision_id))
        ).first()
        try:
            status = await self._provider.poll(job.provider_task_id, self._ctx(revision))
            template = _build_custom_template(revision.custom_template_json) or get_template(
                "generic_async_json_v1", "v1_videos_json_v1"
            )
            mapped = self._map_status(status.raw_status, template)
        except VideoProviderError as exc:
            job.error_code = exc.code
            job.error_message = exc.message[:2000]
            job.next_poll_at = now() + timedelta(seconds=5)  # 轮询失败指数退避
            await self._repo.save(job)
            return
        old = job.status
        if mapped not in (
            VideoJobStatus.QUEUED.value,
            VideoJobStatus.RUNNING.value,
            VideoJobStatus.SUCCEEDED.value,
            VideoJobStatus.FAILED.value,
        ):
            mapped = old
        job.status = mapped
        job.progress = status.progress
        job.next_poll_at = now() + timedelta(seconds=settings.video_poll_interval_seconds)
        if mapped == VideoJobStatus.SUCCEEDED.value:
            job.completed_at = now()
        if mapped != old:
            await self._events.add(
                VideoJobEvent(video_job_id=job.id, event_type=JobEventType.STATUS_CHANGE.value, from_status=old, to_status=mapped)
            )
        await self._repo.save(job)
        if mapped == VideoJobStatus.SUCCEEDED.value and job.download_status == DownloadStatus.NOT_STARTED.value:
            await self._trigger_download(job)

    def _map_status(self, raw: str, template: ProtocolTemplate | None) -> str:
        if template is not None:
            return template.remote_status_map.get(raw, raw)
        return raw

    def _ctx(self, revision: Any) -> AdapterContext:
        auth = json.loads(decrypt_secret(revision.encrypted_auth_json, settings.credential_encryption_keys))
        options = json.loads(revision.public_options_json or "{}")
        return AdapterContext(
            base_url=revision.base_url or "",
            auth=auth,
            options=options,
            remote_model_id=revision.remote_model_id,
            template=_build_custom_template(revision.custom_template_json),
        )

    def _provider_request(self, job: VideoJob, assets: list[tuple[str, str, int]]) -> dict[str, Any]:
        request = json.loads(job.request_json or "{}")
        for asset_id, role, _pos in assets:
            url, _ = sign_provider_asset(asset_id, job.id, role, settings.app_secret, settings.signed_url_ttl_seconds)
            if role == "first_frame":
                request["first_frame_url"] = url
            elif role == "last_frame":
                request["last_frame_url"] = url
            elif role == "reference":
                request.setdefault("reference_image_urls", []).append(url)
            elif role == "source_video":
                request["source_video_url"] = url
            elif role == "audio":
                request["audio_url"] = url
        return request

    async def _load_project(self, user_id: str, command: CreateVideoCommand) -> VideoProject:
        project = (
            await self._session.exec(
                select(VideoProject).where(
                    VideoProject.id == command.project_id,
                    VideoProject.conversation_id == command.conversation_id,
                    VideoProject.user_id == user_id,
                )
            )
        ).first()
        if project is None:
            raise AppError(VIDEO_INPUT_INVALID, "项目不存在或不属于当前用户")
        return project

    async def _active_config(self, user_id: str, config_id: str) -> tuple[Any, VideoApiConfigRevision]:
        config = await self._configs.get_for_user(config_id, user_id)
        if config is None or config.status in ("deleted", "disabled"):
            raise AppError(VIDEO_CONFIG_INVALID, "视频接口配置不存在、停用或已删除")
        revision = await self._revisions.get(config.id, config.current_revision)
        if revision is None:
            raise AppError(VIDEO_CONFIG_INVALID, "配置缺少修订版本")
        if revision.verification_status == "invalid":
            raise AppError(VIDEO_CONFIG_INVALID, "视频接口配置检测无效，禁止创建任务")
        return config, revision

    def _validate_confirmed(self, project: VideoProject, spec_version: int) -> None:
        if spec_version != project.current_spec_version or spec_version != project.confirmed_spec_version:
            raise AppError(PROJECT_NOT_CONFIRMED)

    def _validate_mode(self, command: CreateVideoCommand, spec: VideoBrief) -> None:
        if spec.mode is not None and spec.mode.value != command.mode:
            raise AppError(VIDEO_MODE_UNSUPPORTED, "生成模式与方案版本不一致")
        if spec.duration_seconds is not None and not (1 <= spec.duration_seconds <= 120):
            raise AppError(VIDEO_OPTION_UNSUPPORTED, "时长不在允许范围")

    async def _require_assets(self, user_id: str, spec: VideoBrief) -> list[tuple[str, str, int]]:
        rows = _asset_ids(spec)
        for asset_id, _role, _pos in rows:
            asset = await self._assets.get_for_user(asset_id, user_id)
            if asset is None:
                raise AppError(ASSET_NOT_FOUND, "任务引用的素材不存在或无权访问")
        return rows

    def _build_request_json(self, command: CreateVideoCommand, spec: VideoBrief, revision: VideoApiConfigRevision) -> dict[str, Any]:
        return {
            "remote_model_id": revision.remote_model_id,
            "mode": command.mode,
            "prompt": spec.objective or spec.subject or spec.scene or "",
            "duration_seconds": spec.duration_seconds,
            "aspect_ratio": spec.aspect_ratio,
            "resolution": command.generation_options.get("resolution"),
            "generate_audio": command.generation_options.get("generate_audio", False),
            "first_frame_asset_id": spec.first_frame_asset_id,
            "last_frame_asset_id": spec.last_frame_asset_id,
            "reference_asset_ids": spec.reference_asset_ids or [],
            "source_video_asset_id": spec.source_video_asset_id,
            "audio_asset_id": spec.audio_asset_id,
            "generation_options": command.generation_options,
        }

    async def to_view(self, job: VideoJob) -> VideoJobView:
        request = json.loads(job.request_json or "{}")
        revision = (
            await self._session.exec(select(VideoApiConfigRevision).where(VideoApiConfigRevision.id == job.api_config_revision_id))
        ).first()
        error = None
        if job.error_code:
            error = ErrorInfo(
                code=job.error_code,
                message=job.error_message or "",
                retryable=job.error_code == "PROVIDER_SUBMISSION_UNKNOWN",
            )
        result_direct_url = None
        result_expires_at = None
        if job.download_status == DownloadStatus.DIRECT.value and job.encrypted_result_ref_json:
            try:
                ref = json.loads(decrypt_secret(job.encrypted_result_ref_json, settings.credential_encryption_keys))
                result_direct_url = ref.get("direct_url")
                result_expires_at = datetime.fromisoformat(ref["expires_at"]) if ref.get("expires_at") else None
            except Exception:
                pass
        return VideoJobView(
            id=job.id,
            conversation_id=job.conversation_id,
            project_id=job.project_id,
            project_version=job.project_version,
            api_config_id=job.api_config_id,
            api_config_revision=revision.revision if revision else 0,
            previous_job_id=job.previous_job_id,
            protocol_code=job.protocol_code,
            remote_model_id=job.remote_model_id,
            mode=job.mode,
            status=job.status,
            progress=job.progress,
            generation_options=request.get("generation_options") or {},
            download_status=job.download_status,
            result_asset_id=job.local_asset_id,
            result_direct_url=result_direct_url,
            result_expires_at=result_expires_at,
            error=error,
            poll_after_seconds=3 if job.status in (VideoJobStatus.QUEUED.value, VideoJobStatus.RUNNING.value, VideoJobStatus.SUBMITTING.value) else None,
            submitted_at=job.submitted_at,
            completed_at=job.completed_at,
            created_at=job.created_at,
            updated_at=job.updated_at,
        )

    def to_event_view(self, event: VideoJobEvent) -> VideoJobEventView:
        return VideoJobEventView(
            id=event.id,
            event_type=event.event_type,
            from_status=event.from_status,
            to_status=event.to_status,
            message="",
            created_at=event.created_at,
        )
