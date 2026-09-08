"""用户视频 API 配置：创建 / 读取 / 列表 / 修改（revision 快照）/ 软删除 / 重新检测。

对应《实施计划》4.8 与接口说明 6.5~6.10：
  - 密钥(auth)用 Fernet 加密落库，API 只回 key_hint 掩码，绝不返回密文或明文；
  - 修改配置身份（名称/启停）不新建 revision；修改连接项（协议/地址/模型/凭据/能力）新建 revision；
  - 任务固定引用创建时的 revision，用户后续修改不破坏运行中旧任务；
  - 修改用乐观锁 expected_version，不匹配即冲突。
"""

import json
from datetime import datetime
from typing import Any

from app.core.config import settings
from app.core.cursor import encode_cursor
from app.core.errors import (
    VIDEO_API_CONFIG_NOT_FOUND,
    VIDEO_CONFIG_INVALID,
    VIDEO_CONFIG_NAME_EXISTS,
    AppError,
)
from app.core.security import decrypt_secret, encrypt_secret
from app.core.ssrf import normalize_base_url
from app.core.time import now
from app.db.models.video_api_config import VideoApiConfig, VideoApiConfigRevision
from app.repositories.video_api_configs import (
    VideoApiConfigRepository,
    VideoApiConfigRevisionRepository,
)
from app.schemas.video_api_config import (
    TestVideoApiConfigRequest,
    TestVideoApiConfigResult,
    VideoApiConfigCreateRequest,
    VideoApiConfigPatchRequest,
    VideoApiConfigView,
)
from app.services.video_registry_service import ProtocolReferences
from app.services.video_verification_service import _build_detection, _validate_constraints

# 类内定义了名为 list 的方法，会遮蔽 builtin list；这里在模块级固化类型别名，避免注解里
# `list[...]` 被解析成 `VideoApiConfigService.list[...]`。
_ConfigViews = list[VideoApiConfigView]


def build_key_hint(auth: dict[str, str]) -> dict[str, str]:
    """生成密钥掩码（每项只留末四位），供展示与校验，绝不回传全文。"""
    hints: dict[str, str] = {}
    for name, value in auth.items():
        tail = value[-4:] if len(value) >= 4 else "****"
        hints[name] = f"****{tail}" if value else "****"
    return hints


def _filter_options(options: dict[str, Any], refs: ProtocolReferences) -> str:
    """保留协议白名单内的公开选项（避免把秘密字段塞进 options）。"""
    allowed = {f.name for f in refs.preset.option_fields}
    filtered = {k: v for k, v in options.items() if k in allowed}
    return json.dumps(filtered, ensure_ascii=False)


def _stored_base_url(payload_base_url: str | None, refs: ProtocolReferences) -> str | None:
    """确定落库的 Base URL：用户给则规范化，否则用协议官方地址。"""
    if payload_base_url:
        return normalize_base_url(payload_base_url)
    return refs.preset.official_base_url


class VideoApiConfigService:
    def __init__(self, session: Any) -> None:
        self._session = session
        self._repo = VideoApiConfigRepository(session)
        self._rev_repo = VideoApiConfigRevisionRepository(session)

    async def test(self, payload: TestVideoApiConfigRequest, resolver: Any = None) -> TestVideoApiConfigResult:
        """临时检测（不保存凭据、不创建收费视频）。"""
        return _build_detection(payload, resolver)

    async def create(self, user_id: str, payload: VideoApiConfigCreateRequest, resolver: Any = None) -> VideoApiConfigView:
        refs = _validate_constraints(payload, resolver)
        detection = _build_detection(payload, resolver)
        if await self._repo.get_by_display_name(user_id, payload.display_name) is not None:
            raise AppError(VIDEO_CONFIG_NAME_EXISTS)

        config = VideoApiConfig(
            user_id=user_id,
            display_name=payload.display_name,
            current_revision=1,
            status="active",
            version=0,
        )
        self._session.add(config)
        await self._session.flush()  # 拿到 config.id

        revision = self._new_revision(
            config_id=config.id,
            number=1,
            source_type=payload.source_type,
            refs=refs,
            base_url=_stored_base_url(payload.base_url, refs),
            remote_model_id=payload.remote_model_id,
            auth=payload.auth,
            options=payload.options,
            capability_profile_code=payload.capability_profile_code,
            verification_status=detection.verification_status,
            last_verified_at=detection.checked_at if detection.verification_status == "verified" else None,
        )
        self._session.add(revision)
        await self._session.commit()
        await self._session.refresh(config)
        await self._session.refresh(revision)
        return self._to_view(config, revision)

    async def get(self, user_id: str, config_id: str) -> VideoApiConfigView:
        config = await self._require_config(user_id, config_id)
        revision = await self._current_revision(config)
        return self._to_view(config, revision)

    async def list(
        self,
        user_id: str,
        protocol_code: str | None = None,
        status: str | None = None,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> tuple[_ConfigViews, str | None]:
        """按 (created_at desc, id desc) 游标分页，并在 Service 层按最新 revision 过滤 protocol_code。

        因为 protocol_code 过滤发生在 Python（依赖每条配置的最新 revision），仓库层无法直接
        用它下推 WHERE，所以这里在仓库分页的基础之上再做一次"凑满 limit 条匹配项"循环：
        每轮拉取 limit 条候选配置，剔除 protocol_code 不匹配的，直到凑满 limit 或候选耗尽。
        limit 为 None 时保持旧行为——返回全部匹配配置（不设 next_cursor）。
        """
        if limit is None:
            configs = await self._repo.list_for_user(user_id, status)
            views: list[VideoApiConfigView] = []
            for config in configs:
                revision = await self._current_revision(config)
                if protocol_code is not None and revision.protocol_code != protocol_code:
                    continue
                views.append(self._to_view(config, revision))
            return views, None

        return await self._matched_views(user_id, protocol_code, status, limit, cursor)

    async def _matched_views(
        self,
        user_id: str,
        protocol_code: str | None,
        status: str | None,
        limit: int,
        cursor: str | None,
    ) -> tuple[_ConfigViews, str | None]:
        """迭代库内分页，凑满 limit 条匹配 protocol_code 的配置视图。

        返回 (views, next_cursor)。next_cursor 只在匹配项取满时才有值；候选耗尽则 None。
        """
        views: list[VideoApiConfigView] = []
        keys: list[tuple[datetime, str]] = []
        page_cursor = cursor
        while len(views) < limit:
            configs = await self._repo.list_for_user(user_id, status, limit=limit, cursor=page_cursor)
            if not configs:
                break
            for config in configs:
                revision = await self._current_revision(config)
                if protocol_code is not None and revision.protocol_code != protocol_code:
                    continue
                views.append(self._to_view(config, revision))
                keys.append((config.created_at, config.id))
                if len(views) == limit:
                    break
            if len(views) >= limit:
                break
            if len(configs) < limit:
                break  # 仓库层候选已耗尽
            page_cursor = encode_cursor(configs[-1].created_at, configs[-1].id)
        if len(views) == limit:
            t, cid = keys[-1]
            return views, encode_cursor(t, cid)
        return views, None

    async def patch(self, user_id: str, config_id: str, payload: VideoApiConfigPatchRequest, resolver: Any = None) -> VideoApiConfigView:
        config = await self._require_config(user_id, config_id)
        if config.version != payload.expected_version:
            raise AppError(VIDEO_CONFIG_INVALID, "配置已发生变化，请刷新后重试")

        identity_changed = payload.display_name is not None or payload.status is not None
        connection_changed = any(
            v is not None
            for v in (
                payload.source_type,
                payload.protocol_code,
                payload.template_code,
                payload.base_url,
                payload.remote_model_id,
                payload.auth,
                payload.options,
                payload.capability_profile_code,
                payload.relay_risk_accepted,
            )
        )

        if identity_changed and payload.display_name is not None:
            dup = await self._repo.get_by_display_name(user_id, payload.display_name)
            if dup is not None and dup.id != config.id:
                raise AppError(VIDEO_CONFIG_NAME_EXISTS)
            config.display_name = payload.display_name
        if identity_changed and payload.status is not None:
            if payload.status not in ("active", "disabled"):
                raise AppError(VIDEO_CONFIG_INVALID, "状态只允许 active 或 disabled")
            config.status = payload.status
        if identity_changed:
            config.version = config.version + 1
            config.updated_at = now()

        if connection_changed:
            base_rev = await self._current_revision(config)
            merged = self._merge_connection_fields(base_rev, payload)
            refs = _validate_constraints(merged, resolver)
            next_rev = await self._rev_repo.max_revision(config.id) + 1
            revision = self._new_revision(
                config_id=config.id,
                number=next_rev,
                source_type=merged.source_type,
                refs=refs,
                base_url=_stored_base_url(merged.base_url, refs),
                remote_model_id=merged.remote_model_id,
                auth=merged.auth,
                options=merged.options,
                capability_profile_code=merged.capability_profile_code,
                verification_status="unverified",
                relay_risk_accepted=merged.relay_risk_accepted,
            )
            self._session.add(revision)
            config.current_revision = next_rev
            config.version = config.version + 1
            config.updated_at = now()

        await self._session.commit()
        await self._session.refresh(config)
        latest = await self._current_revision(config)
        return self._to_view(config, latest)

    async def delete(self, user_id: str, config_id: str) -> None:
        config = await self._require_config(user_id, config_id)
        config.status = "deleted"
        config.deleted_at = now()
        config.updated_at = now()
        await self._session.commit()

    async def retest(self, user_id: str, config_id: str, resolver: Any = None) -> TestVideoApiConfigResult:
        config = await self._require_config(user_id, config_id)
        revision = await self._require_revision(config)
        auth = json.loads(decrypt_secret(revision.encrypted_auth_json, settings.credential_encryption_keys))
        payload = TestVideoApiConfigRequest(
            source_type=revision.source_type,
            protocol_code=revision.protocol_code,
            template_code=revision.template_code,
            base_url=revision.base_url,
            remote_model_id=revision.remote_model_id,
            auth=auth,
            options=json.loads(revision.public_options_json or "{}"),
            capability_profile_code=revision.capability_profile_code,
            relay_risk_accepted=revision.relay_risk_accepted_at is not None,
        )
        result = _build_detection(payload, resolver)
        revision.verification_status = result.verification_status
        revision.last_verified_at = result.checked_at if result.verification_status == "verified" else None
        revision.last_error_code = None
        await self._session.commit()
        return result

    # ---- 内部辅助 ----

    async def _require_config(self, user_id: str, config_id: str) -> VideoApiConfig:
        config = await self._repo.get_for_user(config_id, user_id)
        if config is None or config.status == "deleted":
            raise AppError(VIDEO_API_CONFIG_NOT_FOUND)
        return config

    async def _require_revision(self, config: VideoApiConfig) -> VideoApiConfigRevision:
        revision = await self._rev_repo.get(config.id, config.current_revision)
        if revision is None:
            raise AppError(VIDEO_CONFIG_INVALID, "配置缺少修订版本")
        return revision

    async def _current_revision(self, config: VideoApiConfig) -> VideoApiConfigRevision:
        return await self._require_revision(config)

    def _merge_connection_fields(self, base: VideoApiConfigRevision, payload: VideoApiConfigPatchRequest) -> TestVideoApiConfigRequest:
        """以当前 revision 为基准，用 patch 显式提供的覆盖，构造完整检测 payload。"""
        current_auth = json.loads(decrypt_secret(base.encrypted_auth_json, settings.credential_encryption_keys))
        return TestVideoApiConfigRequest(
            source_type=payload.source_type or base.source_type,
            protocol_code=payload.protocol_code or base.protocol_code,
            template_code=payload.template_code if payload.template_code is not None else base.template_code,
            base_url=payload.base_url if payload.base_url is not None else base.base_url,
            remote_model_id=payload.remote_model_id or base.remote_model_id,
            auth=payload.auth if payload.auth is not None else current_auth,
            options=payload.options or json.loads(base.public_options_json or "{}"),
            capability_profile_code=payload.capability_profile_code if payload.capability_profile_code is not None else base.capability_profile_code,
            relay_risk_accepted=(
                payload.relay_risk_accepted if payload.relay_risk_accepted is not None else base.relay_risk_accepted_at is not None
            ),
        )

    def _new_revision(
        self,
        *,
        config_id: str,
        number: int,
        source_type: str,
        refs: ProtocolReferences,
        base_url: str | None,
        remote_model_id: str,
        auth: dict[str, str],
        options: dict[str, Any],
        capability_profile_code: str | None,
        verification_status: str,
        last_verified_at: Any = None,
        relay_risk_accepted: bool = False,
    ) -> VideoApiConfigRevision:
        return VideoApiConfigRevision(
            config_id=config_id,
            revision=number,
            source_type=source_type,
            protocol_code=refs.preset.code,
            template_code=refs.template.template_code if refs.template else None,
            template_version=refs.template.version if refs.template else None,
            base_url=base_url,
            remote_model_id=remote_model_id,
            encrypted_auth_json=encrypt_secret(json.dumps(auth, ensure_ascii=False), settings.credential_encryption_keys),
            public_options_json=_filter_options(options, refs),
            capability_profile_code=capability_profile_code,
            capabilities_json=json.dumps(list(refs.profile.modes)) if refs.profile else "[]",
            capability_source=refs.capability_source,
            verification_status=verification_status,
            key_hint_json=json.dumps(build_key_hint(auth), ensure_ascii=False),
            relay_risk_accepted_at=now() if source_type == "relay" else None,
            last_verified_at=last_verified_at,
        )

    def _to_view(self, config: VideoApiConfig, revision: VideoApiConfigRevision) -> VideoApiConfigView:
        return VideoApiConfigView(
            id=config.id,
            display_name=config.display_name,
            status=config.status,
            current_revision=config.current_revision,
            version=config.version,
            source_type=revision.source_type,
            protocol_code=revision.protocol_code,
            template_code=revision.template_code,
            base_url=revision.base_url,
            remote_model_id=revision.remote_model_id,
            key_hint_json=json.loads(revision.key_hint_json) if revision.key_hint_json else {},
            verification_status=revision.verification_status,
            capability_source=revision.capability_source,
            relay_risk_accepted_at=revision.relay_risk_accepted_at,
            last_error_code=revision.last_error_code,
            created_at=config.created_at,
            updated_at=config.updated_at,
        )
