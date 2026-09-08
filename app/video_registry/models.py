"""视频协议的只读、版本化对象定义。

对应《实施计划》4.7：三个只读对象 —— ProtocolPreset（动态表单/鉴权字段/官方地址）、
ProtocolTemplate（通用引擎的路径/方法/字段/状态映射）、ModelProfile（某模型允许的模式/
时长/比例/分辨率/素材限制）。

这些对象在代码中固定声明（内置数据），不来自数据库；「是否启用」由 Adapter 实现、
Profile 核验、Contract Test 通过共同决定（见 registry）。
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class DynamicField:
    """协议配置表单里的一个字段（对应接口说明 3.8 DynamicFieldView）。"""

    name: str  # 字段名，如 api_key / region
    label: str  # 中文展示
    required: bool = False
    is_secret: bool = False  # 是否为密钥类（响应只返回掩码、加密存储）
    source: str = "body"  # 取值位置：header / query / body
    placeholder: str = ""


@dataclass(frozen=True)
class ProtocolPreset:
    """一个视频协议的预设（对应接口说明 3.9 ProtocolPresetView）。"""

    code: str  # 协议代码，如 generic_async_json_v1
    name: str
    version: int = 1
    source_types: tuple[str, ...] = ("official", "relay")  # official / relay
    allows_custom_base_url: bool = True  # 中转站是否允许用户自定义地址
    official_base_url: str | None = None  # 官方地址（自建协议时由后端确定）
    auth_fields: tuple[DynamicField, ...] = ()
    option_fields: tuple[DynamicField, ...] = ()  # 公开附加选项（如地域/Workspace）
    adapter_code: str = ""  # 指向具体 Adapter 实现
    enabled: bool = False


@dataclass(frozen=True)
class EndpointSpec:
    """模板里一个 HTTP 端点：白名单方法 + 固定相对路径。"""

    method: str  # 仅允许 GET / POST（其后可能加 PUT/DELETE）
    path: str  # 相对路径，已校验不含用户可控参数
    success_statuses: frozenset[int] = frozenset({200, 201, 202})
    id_json_path: str = ""  # 提取远端任务 ID 的字段路径（如 data.task_id）
    status_json_path: str = ""  # 轮询时读取远端状态的字段路径（如 data.status）
    result_url_json_path: str = ""  # 结果下载地址的字段路径
    request_template_json: dict[str, Any] = field(default_factory=dict)  # 提交请求体模板


@dataclass(frozen=True)
class ProtocolTemplate:
    """一个协议下的审核模板（对应接口说明 3.10 ProtocolTemplateView）。"""

    template_code: str  # 如 v1_videos_json_v1
    protocol_code: str
    name: str
    version: int = 1
    submit: EndpointSpec | None = None
    poll: EndpointSpec | None = None
    result: EndpointSpec | None = None
    # 远端状态 -> 本站统一状态 的映射（远端未识别时保留原状态，不盲目置失败）
    remote_status_map: dict[str, str] = field(default_factory=dict)
    # 模板固定白名单字段名，禁止任意 Jinja / 绝对 URL / JSONPath
    allowed_http_methods: tuple[str, ...] = ("GET", "POST")


@dataclass(frozen=True)
class ModelProfile:
    """一个具体模型的能力（对应接口说明 3.11 ModelProfileView）。

    双轨：allows_provider_direct_url 让「下载失败/服务器不支持」时可回退厂商直链；
    否则一律下载到本站转交。
    """

    code: str  # profile code
    display_name: str
    protocol_code: str
    template_code: str | None = None
    remote_model_id: str = ""  # 默认该 profile 绑定的远端模型
    capability_profile_code: str = ""  # 如 text_reference_media
    modes: tuple[str, ...] = ()  # VideoMode.value 集合
    durations_seconds: tuple[int, ...] = ()
    aspect_ratios: tuple[str, ...] = ()
    resolutions: tuple[str, ...] = ()
    generation_options: dict[str, Any] = field(default_factory=dict)  # 公开生成选项白名单
    max_reference_images: int = 0
    max_source_videos: int = 0
    allows_provider_direct_url: bool = False  # 是否允许结果降级为厂商直链
    provider_direct_url_ttl: int = 3600  # 直链有效期提示（秒）
    enabled: bool = False


__all__ = [
    "DynamicField",
    "EndpointSpec",
    "ModelProfile",
    "ProtocolPreset",
    "ProtocolTemplate",
]
