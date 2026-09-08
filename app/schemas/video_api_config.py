"""视频协议 / 用户 API 配置的输入输出模型（接口说明 3.8~3.12、6.x）。"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# ---- 协议只读对象视图（供前端构造动态表单）----
class DynamicFieldView(BaseModel):
    name: str
    label: str
    required: bool = False
    is_secret: bool = False
    source: str = "body"
    placeholder: str = ""


class ProtocolPresetView(BaseModel):
    code: str
    name: str
    version: int
    source_types: list[str]
    allows_custom_base_url: bool
    official_base_url: str | None = None
    auth_fields: list[DynamicFieldView] = Field(default_factory=list)
    option_fields: list[DynamicFieldView] = Field(default_factory=list)


class ProtocolTemplateView(BaseModel):
    template_code: str
    protocol_code: str
    name: str
    version: int
    allowed_http_methods: list[str]


class ModelProfileView(BaseModel):
    code: str
    display_name: str
    protocol_code: str
    template_code: str | None = None
    modes: list[str]
    durations_seconds: list[int]
    aspect_ratios: list[str]
    resolutions: list[str]
    generation_options: dict[str, Any] = Field(default_factory=dict)
    max_reference_images: int = 0
    max_source_videos: int = 0
    # 双轨降级能力声明：模型是否允许结果在下载失败时回退为厂商直链（供前端提示）
    allows_provider_direct_url: bool = False


# ---- 请求对象（检测 / 创建 / 修改）----
class VideoApiConfigBase(BaseModel):
    """检测与创建共用的字段（接口说明 6.4 / 6.5）。"""

    source_type: str = Field(min_length=1, max_length=20)  # official / relay
    protocol_code: str = Field(min_length=1, max_length=64)
    template_code: str | None = Field(default=None, max_length=64)
    base_url: str | None = Field(default=None, max_length=500)
    remote_model_id: str = Field(min_length=1, max_length=160)
    auth: dict[str, str] = Field(default_factory=dict)
    options: dict[str, Any] = Field(default_factory=dict)
    capability_profile_code: str | None = Field(default=None, max_length=64)
    relay_risk_accepted: bool = False


class TestVideoApiConfigRequest(VideoApiConfigBase):
    """临时检测配置（不保存凭据，不创建收费视频）。"""

    model_config = ConfigDict(extra="forbid")


class VideoApiConfigCreateRequest(VideoApiConfigBase):
    """创建用户视频接口配置。"""

    model_config = ConfigDict(extra="forbid")

    display_name: str = Field(min_length=1, max_length=40)


class VideoApiConfigPatchRequest(BaseModel):
    """修改配置（接口说明 6.8）。身份项改变不建 revision；连接项改变会新建。"""

    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(ge=0)
    display_name: str | None = Field(default=None, min_length=1, max_length=40)
    source_type: str | None = Field(default=None, min_length=1, max_length=20)
    protocol_code: str | None = Field(default=None, min_length=1, max_length=64)
    template_code: str | None = Field(default=None, max_length=64)
    base_url: str | None = Field(default=None, max_length=500)
    remote_model_id: str | None = Field(default=None, min_length=1, max_length=160)
    auth: dict[str, str] | None = Field(default=None)
    options: dict[str, Any] | None = Field(default=None)
    capability_profile_code: str | None = Field(default=None, max_length=64)
    relay_risk_accepted: bool | None = Field(default=None)
    status: str | None = Field(default=None, min_length=1, max_length=20)  # active / disabled


# ---- 响应对象 ----
class TestVideoApiConfigResult(BaseModel):
    verification_status: str  # verified / invalid / unverified
    message: str
    checked_at: datetime
    safe_details: dict[str, Any] = Field(default_factory=dict)


class VideoApiConfigView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    display_name: str
    status: str
    current_revision: int
    version: int
    source_type: str
    protocol_code: str
    template_code: str | None = None
    base_url: str | None = None
    remote_model_id: str
    key_hint_json: dict[str, Any] = Field(default_factory=dict)
    verification_status: str
    capability_source: str
    relay_risk_accepted_at: datetime | None = None
    last_error_code: str | None = None
    created_at: datetime
    updated_at: datetime
