"""视频协议注册表。

只读对象：ProtocolPreset / ProtocolTemplate / ModelProfile（见 models 与 core_protocols）；
「启用」判定与查询见 registry。
"""

from app.video_registry.models import (
    DynamicField,
    EndpointSpec,
    ModelProfile,
    ProtocolPreset,
    ProtocolTemplate,
)
from app.video_registry.registry import (
    get_preset,
    get_profile,
    get_template,
    list_enabled_presets,
    list_profiles,
    list_templates,
)

__all__ = [
    "DynamicField",
    "EndpointSpec",
    "ModelProfile",
    "ProtocolPreset",
    "ProtocolTemplate",
    "get_preset",
    "get_profile",
    "get_template",
    "list_enabled_presets",
    "list_profiles",
    "list_templates",
]
