"""把视频协议注册表的只读对象路由到前端视图，并提供创建/检测配置前的校验。

校验规则（《实施计划》4.7/4.8 + 接口说明 6.2/6.3）：
  - 协议必须是「已启用」的；
  - generic 通用协议必须携带其模板；原生官方协议不允许携带模板; 模板必须存在；
  - 模型 Profile：已登记（能匹配 registry 里的 Profile）视为「已核验」，否则按用户声明
    （capability_source=user_declared）处理；是否有效由任务创建时再判。
"""

from dataclasses import asdict

from app.core.errors import VIDEO_PROTOCOL_UNSUPPORTED, VIDEO_TEMPLATE_UNSUPPORTED, AppError
from app.schemas.video_api_config import (
    DynamicFieldView,
    ModelProfileView,
    ProtocolPresetView,
    ProtocolTemplateView,
)
from app.video_registry import (
    get_preset,
    get_profile,
    get_template,
    list_enabled_presets,
    list_profiles,
    list_templates,
)
from app.video_registry.models import DynamicField, ModelProfile, ProtocolPreset, ProtocolTemplate


def _dynamic_to_view(field: DynamicField) -> DynamicFieldView:
    return DynamicFieldView(**asdict(field))


def preset_to_view(preset: ProtocolPreset) -> ProtocolPresetView:
    return ProtocolPresetView(
        code=preset.code,
        name=preset.name,
        version=preset.version,
        source_types=list(preset.source_types),
        allows_custom_base_url=preset.allows_custom_base_url,
        official_base_url=preset.official_base_url,
        auth_fields=[_dynamic_to_view(f) for f in preset.auth_fields],
        option_fields=[_dynamic_to_view(f) for f in preset.option_fields],
    )


def template_to_view(template: ProtocolTemplate) -> ProtocolTemplateView:
    return ProtocolTemplateView(
        template_code=template.template_code,
        protocol_code=template.protocol_code,
        name=template.name,
        version=template.version,
        allowed_http_methods=list(template.allowed_http_methods),
    )


def profile_to_view(profile: ModelProfile) -> ModelProfileView:
    return ModelProfileView(
        code=profile.code,
        display_name=profile.display_name,
        protocol_code=profile.protocol_code,
        template_code=profile.template_code,
        modes=list(profile.modes),
        durations_seconds=list(profile.durations_seconds),
        aspect_ratios=list(profile.aspect_ratios),
        resolutions=list(profile.resolutions),
        generation_options=profile.generation_options,
        max_reference_images=profile.max_reference_images,
        max_source_videos=profile.max_source_videos,
        allows_provider_direct_url=profile.allows_provider_direct_url,
    )


def list_enabled_preset_views() -> list[ProtocolPresetView]:
    return [preset_to_view(p) for p in list_enabled_presets()]


def get_template_view(protocol_code: str, template_code: str) -> ProtocolTemplateView | None:
    template = get_template(protocol_code, template_code)
    return template_to_view(template) if template is not None else None


def list_profile_views(protocol_code: str, template_code: str | None = None) -> list[ModelProfileView]:
    return [profile_to_view(p) for p in list_profiles(protocol_code, template_code)]


def list_template_views(protocol_code: str) -> list[ProtocolTemplateView]:
    return [template_to_view(t) for t in list_templates(protocol_code)]


class ProtocolReferences:
    """一次校验通过的协议引用，供创建/检测配置与任务创建使用。"""

    def __init__(self, preset: ProtocolPreset, template: ProtocolTemplate | None, profile: ModelProfile | None) -> None:
        self.preset = preset
        self.template = template
        self.profile = profile
        self.capability_source = "user_declared" if profile is None else "registry"


def validate_payload_refs(protocol_code: str, template_code: str | None, capability_profile_code: str | None) -> ProtocolReferences:
    """校验协议/模板/能力引用是否合法，返回可直接落库的引用对象。

    抛出：VIDEO_PROTOCOL_UNSUPPORTED / VIDEO_TEMPLATE_UNSUPPORTED。
    """
    preset = get_preset(protocol_code)
    if preset is None or not preset.enabled:
        raise AppError(VIDEO_PROTOCOL_UNSUPPORTED)

    template: ProtocolTemplate | None = None
    if preset.allows_custom_base_url:
        # 通用第三方协议必须携带模板
        if not template_code:
            raise AppError(VIDEO_TEMPLATE_UNSUPPORTED)
        template = get_template(protocol_code, template_code)
        if template is None:
            raise AppError(VIDEO_TEMPLATE_UNSUPPORTED)
    else:
        # 官方原生协议不允许携带模板
        if template_code:
            raise AppError(VIDEO_TEMPLATE_UNSUPPORTED)

    profile = get_profile(protocol_code, capability_profile_code) if capability_profile_code else None
    return ProtocolReferences(preset=preset, template=template, profile=profile)


__all__ = [
    "ProtocolReferences",
    "get_template_view",
    "list_enabled_preset_views",
    "list_profile_views",
    "list_template_views",
    "validate_payload_refs",
]
