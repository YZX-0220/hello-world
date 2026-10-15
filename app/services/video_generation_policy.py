"""One source of truth for target identity, legal candidates and wire parameters.

Rules are code/data, never an LLM verdict. Preparation may propose a candidate;
submission only validates the already reviewed candidate and never repairs it.
"""

import hashlib
import itertools
import json
import re
from dataclasses import asdict, dataclass
from typing import Any

from app.core.config import settings
from app.core.errors import VIDEO_CONFIG_INVALID, VIDEO_OPTION_UNSUPPORTED, AppError
from app.repositories.video_api_configs import (
    VideoApiConfigRepository,
    VideoApiConfigRevisionRepository,
)
from app.schemas.agent import VideoBrief
from app.services.video_registry_service import profile_to_view
from app.video_registry import get_preset, get_profile, get_template, list_profiles
from app.video_registry.models import ModeConstraint, ModelProfile, ParameterRule

MODE_LABELS = {
    "text_to_video": "文生视频",
    "first_frame_to_video": "首帧图生视频",
    "first_last_frame_to_video": "首尾帧生视频",
    "reference_image_to_video": "参考图生视频",
    "video_to_video": "视频重绘",
    "video_extend": "视频延长",
    "audio_or_performance_to_video": "音频驱动",
}
PARAM_LABELS = {
    "duration_seconds": "时长",
    "resolution": "清晰度",
    "aspect_ratio": "画幅",
    "generate_audio": "生成声音",
}
POLICY_VERSION = 1


def digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True,
                   default=lambda v: sorted(v) if isinstance(v, (set, frozenset)) else str(v)).encode()
    ).hexdigest()


@dataclass
class GenerationTarget:
    identity: dict
    label: str
    profile: ModelProfile | None
    revision: Any = None
    error: str = ""

    @property
    def fingerprint(self) -> str:
        return digest(self.identity)

    def snapshot(self) -> dict:
        return {**self.identity, "fingerprint": self.fingerprint, "label": self.label}

    def view(self) -> dict:
        return {
            **self.snapshot(),
            "profile": profile_to_view(self.profile).model_dump() if self.profile else None,
            "error": self.error,
        }


async def resolve_target(session, user_id: str, config_id: str) -> GenerationTarget:
    revision = None
    if config_id == "platform":
        protocol = settings.video_platform_protocol
        model = settings.video_platform_model
        profile_code = settings.video_platform_profile_code
        label = "平台体验通道"
        identity = {
            "api_config_id": "platform",
            "revision_id": None,
            "revision": 0,
            "protocol_code": protocol,
            "remote_model_id": model,
            "base_url": settings.video_platform_base_url,
        }
    else:
        config = await VideoApiConfigRepository(session).get_for_user(config_id, user_id)
        if config is None or config.status != "active":
            raise AppError(VIDEO_CONFIG_INVALID, "视频通道已停用、删除或无权使用，请选择有效通道。")
        revision = await VideoApiConfigRevisionRepository(session).get(
            config.id, config.current_revision
        )
        if revision is None or revision.verification_status == "invalid":
            raise AppError(VIDEO_CONFIG_INVALID, "视频通道配置无效，请修正配置或切换通道。")
        protocol, model, profile_code = (
            revision.protocol_code,
            revision.remote_model_id,
            revision.capability_profile_code or "",
        )
        label = config.display_name
        identity = {
            "api_config_id": config.id,
            "revision_id": revision.id,
            "revision": config.current_revision,
            "protocol_code": protocol,
            "remote_model_id": model,
            "base_url": revision.base_url,
        }
    preset = get_preset(protocol)
    template = get_template(protocol, revision.template_code) if revision and revision.template_code else None
    profile = get_profile(protocol, profile_code) if profile_code else None
    # Exact registered IDs are safe to resolve; prefix guesses may match another model.
    if profile is None:
        profile = next((p for p in list_profiles(protocol) if p.remote_model_id == model), None)
    error = ""
    if preset is None or not preset.enabled:
        error = "此通道协议未实现或已停用，请切换通道。"
    elif not model:
        error = "此通道尚未配置视频模型，请配置模型后重新审理。"
    elif profile is None or not profile.enabled:
        error = "此模型尚未登记能力规则，请在 API 配置中绑定已登记的模型能力，或切换已登记通道。"
        profile = None
    elif (
        profile.remote_model_id
        and profile.remote_model_id != model
        and not (protocol == "generic_async_json_v1" or model.startswith("ep-"))
    ):
        # Opaque deployment endpoint IDs require an explicit profile binding.
        error = "模型编号与绑定的能力规则不一致，请修正 API 配置后重新审理。"
    identity.update(
        profile_code=profile.code if profile else profile_code,
        profile_version=profile.version if profile else None,
        template_code=revision.template_code if revision else None,
        template_version=template.version if template else None,
        adapter_version=POLICY_VERSION,
        rules_hash=digest(
            {"policy": POLICY_VERSION, "profile": asdict(profile) if profile else None,
             "protocol": asdict(preset) if preset else None, "template": asdict(template) if template else None}
        ),
    )
    return GenerationTarget(identity, label, profile, revision, error)


def mode_rule(profile: ModelProfile, mode: str) -> ModeConstraint:
    return next((r for r in profile.mode_constraints if r.mode == mode), ModeConstraint(mode))


def input_issues(profile: ModelProfile, spec: VideoBrief) -> list[str]:
    mode = str(spec.mode or "")
    issues = []
    if mode not in profile.modes:
        supported = "、".join(MODE_LABELS.get(m, m) for m in profile.modes)
        return [
            f"当前模型不支持{MODE_LABELS.get(mode, mode)}。请切换通道，或将生成模式改为：{supported}。"
        ]
    first, last, refs = (
        spec.first_frame_asset_id,
        spec.last_frame_asset_id,
        spec.reference_asset_ids,
    )
    images = ([first] if first else []) + ([last] if last else []) + refs
    identical_frames = profile.allows_identical_frames and mode == "first_last_frame_to_video" and not refs
    if len(set(images)) != len(images) and not identical_frames:
        issues.append("同一张图片不能同时充当多个素材角色，请重新指定首帧、尾帧或参考图。")
    if mode == "text_to_video" and images:
        issues.append("文生视频模式不使用图片，请取消所选或关联的图片，或选择图生视频模式。")
    elif mode == "first_frame_to_video" and (not first or last or refs):
        issues.append("首帧模式需要且只使用一张首帧图片，请调整所选图片。")
    elif mode == "first_last_frame_to_video" and (not first or not last or refs):
        issues.append("首尾帧模式需要指定首帧和尾帧。")
    elif mode == "reference_image_to_video" and (not refs or first or last):
        issues.append("参考图模式需要参考图片，请调整素材角色。")
    elif mode not in (
        "text_to_video",
        "first_frame_to_video",
        "first_last_frame_to_video",
        "reference_image_to_video",
    ):
        issues.append("当前画布尚未提供该模式所需的素材角色入口，请切换文生或图生模式。")
    if len(refs) > profile.max_reference_images:
        issues.append(
            f"此模型最多支持 {profile.max_reference_images} 张参考图，当前为 {len(refs)} 张。请减少参考图或切换模型。"
        )
    if spec.source_video_asset_id or spec.audio_asset_id:
        issues.append("当前模式不接受额外的视频或音频素材，请调整素材。")
    return issues


def _matches(rule: ParameterRule, candidate: dict) -> bool:
    return all(
        candidate.get(key) in value
        if isinstance(value, (tuple, list))
        else candidate.get(key) == value
        for key, value in rule.when.items()
    )


def _violations(profile: ModelProfile, constraint: ModeConstraint, candidate: dict) -> list[str]:
    errors = []
    for rule in (*profile.rules, *constraint.rules):
        if rule.field not in PARAM_LABELS or any(k not in PARAM_LABELS for k in rule.when):
            return ["模型规则含有未实现的参数，请管理员完善规则后重试。"]
        if not _matches(rule, candidate):
            continue
        value = candidate.get(rule.field)
        invalid = rule.allowed_values is not None and value not in rule.allowed_values
        if rule.minimum is not None:
            invalid = invalid or not isinstance(value, (int, float)) or value < rule.minimum
        if rule.maximum is not None:
            invalid = invalid or not isinstance(value, (int, float)) or value > rule.maximum
        if invalid:
            errors.append(rule.note or f"{PARAM_LABELS[rule.field]}不符合此模式的参数组合限制。")
    return errors


def propose_settings(target: GenerationTarget, spec: VideoBrief, requested: dict) -> dict:
    """Find a minimally changed legal combination, preserving inputs and creative intent."""
    if target.error or target.profile is None:
        return {
            "issues": [target.error or "模型规则不可用。"],
            "settings": requested,
            "wire": {},
            "changes": [],
        }
    profile = target.profile
    issues = input_issues(profile, spec)
    rule = mode_rule(profile, str(spec.mode))
    if rule.ratio_transport not in ("omit", "adaptive"):
        issues.append("此模式的画幅传输规则不可用，请管理员完善配置。")
    if rule.ratio not in ("model", "adaptive_only", "omit") or rule.duration not in (
        "model",
        "omit",
        "fixed:-1",
    ):
        issues.append("此模式的参数规则尚未实现，请管理员补全规则或选择其他模式。")
    if rule.duration == "fixed:-1":
        issues.append(
            "此模式由输入素材决定时长，无法保证用户确认的 1–15 秒。请选择支持指定时长的模式。"
        )
    durations = [v for v in profile.durations_seconds if 1 <= v <= 15]
    if profile.image_constraints and requested["duration_seconds"] not in durations:
        issues.append(f"请手动选择当前模型支持的时长：{'、'.join(map(str, durations))} 秒。")
    if rule.duration == "omit":
        durations = [requested["duration_seconds"]]
    ratios = (
        ["adaptive"] if rule.ratio in ("adaptive_only", "omit") else list(profile.aspect_ratios)
    )
    resolutions = list(profile.resolutions)
    audios = [False, True] if profile.generation_options.get("generate_audio") else [False]
    if not durations or not ratios or not resolutions:
        issues.append("此模式缺少可用的时长、清晰度或画幅规则，请管理员补全规则。")
    if issues:
        return {"issues": issues, "settings": requested, "wire": {}, "changes": []}
    preferred = {
        **requested,
        "aspect_ratio": requested.get("aspect_ratio")
        or ("16:9" if "16:9" in ratios else ratios[0]),
        "generate_audio": requested.get("generate_audio", True),
    }
    candidates = [
        dict(
            zip(
                ("duration_seconds", "resolution", "aspect_ratio", "generate_audio"),
                values,
                strict=True,
            )
        )
        for values in itertools.product(durations, resolutions, ratios, audios)
    ]
    candidates = [c for c in candidates if not _violations(profile, rule, c)]
    if not candidates:
        return {
            "issues": ["此模型的参数组合没有合法方案，请调整生成设置或切换模型。"],
            "settings": requested,
            "wire": {},
            "changes": [],
        }

    def score(c):
        return (
            sum(c[k] != preferred.get(k) for k in ("duration_seconds", "resolution")),
            abs(c["duration_seconds"] - preferred["duration_seconds"]),
            abs(int(c["resolution"].rstrip("p")) - int(preferred["resolution"].rstrip("p"))),
            c["aspect_ratio"] != preferred["aspect_ratio"],
            c["generate_audio"] != preferred["generate_audio"],
            c["duration_seconds"],
        )

    effective = min(candidates, key=score)
    changes = []
    for key, label in PARAM_LABELS.items():
        before = preferred[key]
        if before != effective[key]:
            reason = (
                rule.note
                if key == "aspect_ratio" and rule.note
                else "按当前模型和模式的合法参数组合做最小调整。"
            )
            if key == "duration_seconds" and before not in durations:
                reason = f"此模式支持的时长为 {'、'.join(map(str, durations))} 秒，原时长不在支持范围内。"
            elif key == "resolution" and before not in resolutions:
                reason = f"此模式支持的清晰度为 {'、'.join(resolutions)}，原清晰度不受支持。"
            elif key == "generate_audio" and not profile.generation_options.get("generate_audio"):
                reason = "当前模型不支持生成声音，采用无声视频方案。"
            elif key == "aspect_ratio" and rule.ratio == "model":
                reason = f"此模式支持的画幅为 {'、'.join(ratios)}，原画幅不受支持。"
            violated = _violations(profile, rule, preferred)
            if violated:
                reason = " ".join(violated)
            changes.append(
                {
                    "field": key,
                    "label": label,
                    "before": before,
                    "after": effective[key],
                    "reason": reason,
                }
            )
    if not requested.get("aspect_ratio") and effective["aspect_ratio"] == "adaptive":
        changes.append(
            {
                "field": "aspect_ratio",
                "label": "画幅",
                "before": "未指定",
                "after": "adaptive",
                "reason": rule.note or "此模式画幅由输入素材决定，不发送固定比例。",
            }
        )
    wire = dict(effective)
    if profile.task_timeout_seconds:
        wire["execution_expires_after"] = profile.task_timeout_seconds
    if rule.ratio in ("adaptive_only", "omit"):
        if rule.ratio == "adaptive_only" and rule.ratio_transport == "adaptive":
            wire["aspect_ratio"] = "adaptive"
        else:
            wire.pop("aspect_ratio", None)
    if rule.duration == "omit":
        wire.pop("duration_seconds", None)
        changes.append(
            {
                "field": "duration_transport",
                "label": "时长提交方式",
                "before": "API 参数",
                "after": "提示词描述",
                "reason": "此模式不接受时长参数；目标时长写入画面描述。",
            }
        )
    if not profile.generation_options.get("generate_audio"):
        wire.pop("generate_audio", None)
    if target.revision is not None and target.revision.custom_template_json:
        body = json.loads(target.revision.custom_template_json).get("request_template_json", {})
        mapped = set(re.findall(r"\{([a-z_]+)\}", json.dumps(body)))
        required = set(wire)
        if spec.first_frame_asset_id:
            required.add("first_frame_url")
        if spec.last_frame_asset_id:
            required.add("last_frame_url")
        if spec.reference_asset_ids:
            required.add("reference_image_urls")
        missing = required - mapped
        if missing:
            return {"issues": ["自定义视频模板未映射这些审理参数或素材：" + "、".join(sorted(missing))
                               + "。请补全模板占位符，或切换已配置的通道。"],
                    "settings": effective, "wire": wire, "changes": changes}
    return {"issues": [], "settings": effective, "wire": wire, "changes": changes}


def validate_settings(
    target: GenerationTarget, spec: VideoBrief, effective: dict, wire: dict
) -> None:
    result = propose_settings(target, spec, effective)
    if result["issues"] or result["settings"] != effective or result["wire"] != wire:
        raise AppError(
            VIDEO_OPTION_UNSUPPORTED,
            "已审理参数不再符合当前模型规则，请重新审理。",
            {"reasons": result["issues"]},
        )
