"""视频协议注册表：按 code 查询 / 枚举已启用对象。

「启用」条件（《实施计划》4.7）：Adapter 已实现 + 至少一个 Model Profile 已核验 +
Contract Test 通过 + enabled=true。阶段 6~9 仅 generic_async_json_v1 满足。
"""

from app.video_registry.core_protocols import (
    ARK_PRESET,
    ARK_PROFILES,
    DASHSCOPE_PRESET,
    DASHSCOPE_PROFILES,
    GENERIC_PRESET,
    GENERIC_PROFILES,
    V1_VIDEOS_TEMPLATE,
)
from app.video_registry.models import ModelProfile, ProtocolPreset, ProtocolTemplate

_PRESETS: dict[str, ProtocolPreset] = {p.code: p for p in (GENERIC_PRESET, ARK_PRESET, DASHSCOPE_PRESET)}
_TEMPLATES: dict[tuple[str, str], ProtocolTemplate] = {
    (t.protocol_code, t.template_code): t for t in (V1_VIDEOS_TEMPLATE,)
}
_PROFILES: dict[tuple[str, str], ModelProfile] = {
    (p.protocol_code, p.code): p for p in (*GENERIC_PROFILES, *ARK_PROFILES, *DASHSCOPE_PROFILES)
}


def list_enabled_presets() -> list[ProtocolPreset]:
    """返回满足启用条件的协议预设（供前端 6.1）。"""
    return [p for p in _PRESETS.values() if p.enabled]


def get_preset(protocol_code: str) -> ProtocolPreset | None:
    return _PRESETS.get(protocol_code)


def get_template(protocol_code: str, template_code: str) -> ProtocolTemplate | None:
    return _TEMPLATES.get((protocol_code, template_code))


def list_profiles(protocol_code: str, template_code: str | None = None) -> list[ModelProfile]:
    """返回某协议（可按模板过滤、且已启用）的模型能力列表（供前端 6.3）。"""
    return [
        p
        for (proto, code), p in _PROFILES.items()
        if proto == protocol_code
        and p.enabled
        and (template_code is None or p.template_code == template_code)
    ]


def get_profile(protocol_code: str, profile_code: str) -> ModelProfile | None:
    return _PROFILES.get((protocol_code, profile_code))


def list_templates(protocol_code: str) -> list[ProtocolTemplate]:
    """返回某协议下的模板列表（原生协议无模板时返回空）。"""
    return [t for (proto, _tc), t in _TEMPLATES.items() if proto == protocol_code]


__all__ = [
    "get_preset",
    "get_profile",
    "get_template",
    "list_enabled_presets",
    "list_profiles",
    "list_templates",
]
