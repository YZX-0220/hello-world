"""视频协议 / 用户 API 配置的输入输出模型（接口说明 3.8~3.12、6.x）。"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


# ---- 协议只读对象视图（字段名与接口说明 3.8~3.11 保持一致）----
class ChoiceView(BaseModel):
    value: Any
    label: str


class DynamicFieldView(BaseModel):
    name: str
    label: str
    input_type: str = "text"  # text / password / select / boolean
    required: bool = False
    secret: bool = False
    required_for_sources: list[str] = Field(default_factory=list)
    choices: list[ChoiceView] = Field(default_factory=list)
    placeholder: str | None = None
    help_text: str | None = None


class ProtocolPresetView(BaseModel):
    code: str
    label: str
    description: str = ""
    source_types: list[str]
    supports_custom_base_url: bool
    official_base_url: str | None = None
    template_required: bool = False
    auth_fields: list[DynamicFieldView] = Field(default_factory=list)
    option_fields: list[DynamicFieldView] = Field(default_factory=list)


class ProtocolTemplateView(BaseModel):
    code: str
    label: str
    version: int
    protocol_code: str
    description: str = ""
    modes: list[str] = Field(default_factory=list)


class DurationRange(BaseModel):
    min_seconds: int | None = None
    max_seconds: int | None = None
    allowed_values: list[int] = Field(default_factory=list)


class ModelProfileView(BaseModel):
    code: str
    label: str
    version: int
    protocol_code: str
    remote_model_id: str
    modes: list[str]
    duration: DurationRange
    aspect_ratios: list[str]
    resolutions: list[str]
    max_reference_images: int = 0
    max_reference_videos: int = 0
    max_reference_audios: int = 0
    supports_audio: bool = False
    supports_negative_prompt: bool = False
    generation_option_fields: list[DynamicFieldView] = Field(default_factory=list)


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
    # ---- 用户自定义模板（template_mode="custom" 时必填，builtin 时忽略）----
    template_mode: Literal["builtin", "custom"] = "builtin"
    submit_method: str | None = Field(default=None, max_length=10)
    submit_path: str | None = Field(default=None, max_length=500)
    request_template_json: dict[str, Any] | None = None
    task_id_path: str | None = Field(default=None, max_length=200)
    poll_method: str | None = Field(default=None, max_length=10)
    poll_path: str | None = Field(default=None, max_length=500)
    status_path: str | None = Field(default=None, max_length=200)
    status_map: dict[str, str] | None = None
    result_url_path: str | None = Field(default=None, max_length=200)


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
    # ---- 用户自定义模板（template_mode 显式提供时才参与连接变更）----
    template_mode: Literal["builtin", "custom"] | None = None
    submit_method: str | None = Field(default=None, max_length=10)
    submit_path: str | None = Field(default=None, max_length=500)
    request_template_json: dict[str, Any] | None = None
    task_id_path: str | None = Field(default=None, max_length=200)
    poll_method: str | None = Field(default=None, max_length=10)
    poll_path: str | None = Field(default=None, max_length=500)
    status_path: str | None = Field(default=None, max_length=200)
    status_map: dict[str, str] | None = None
    result_url_path: str | None = Field(default=None, max_length=200)


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
    template_mode: str = "builtin"
    custom_template_json: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime
