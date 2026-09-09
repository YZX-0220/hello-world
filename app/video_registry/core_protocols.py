"""内置视频协议数据：generic_async_json_v1（通用异步 JSON 中转协议）与
ark_seedance_v1（火山方舟 Seedance 官方原生协议，无模板）。

generic 含模板 v1_videos_json_v1 与示例模型 Profile；ark 为原生协议，只注册
preset 与多个模型 Profile，由 Adapter（app/providers/video/ark_seedance_v1.py）原生调用。
dashscope_async_v1 / fal_queue_v1 待阶段 10/11 真实化后再按相同结构注册（届时需联网核验）。

协议语义（内置约定，用户只需提供 base_url + key + remote_model_id）：
  - 提交：POST {base}/tasks   请求体为模板化 JSON；响应 data.task_id 为远端任务 ID。
  - 轮询：GET  {base}/tasks/{task_id}；响应 data.status 为远端状态。
  - 结果：GET  {base}/tasks/{task_id}/result，响应 data.url 为厂商直链（可选中转下载）。
"""

from app.core.enums import ApiSourceType, VideoMode
from app.video_registry.models import (
    DynamicField,
    EndpointSpec,
    ModelProfile,
    ProtocolPreset,
    ProtocolTemplate,
)

# ---- 协议预设：动态表单 / 鉴权字段 ----
GENERIC_PRESET = ProtocolPreset(
    code="generic_async_json_v1",
    name="通用异步 JSON 视频接口",
    version=1,
    source_types=(ApiSourceType.OFFICIAL.value, ApiSourceType.RELAY.value),
    allows_custom_base_url=True,
    official_base_url=None,
    auth_fields=(
        DynamicField(
            name="api_key",
            label="API 密钥",
            required=True,
            is_secret=True,
            source="header",
            placeholder="Bearer <token>",
        ),
    ),
    option_fields=(
        DynamicField(name="region", label="地域（可选）", required=False, source="body"),
        DynamicField(name="workspace", label="Workspace（可选）", required=False, source="body"),
    ),
    adapter_code="generic_async_json_v1",
    enabled=True,
)

# ---- 协议模板：路径 / 方法 / 状态映射 ----
V1_VIDEOS_TEMPLATE = ProtocolTemplate(
    template_code="v1_videos_json_v1",
    protocol_code="generic_async_json_v1",
    name="异步 JSON 视频模板",
    version=1,
    submit=EndpointSpec(
        method="POST",
        path="/tasks",
        success_statuses=frozenset({200, 201, 202}),
        id_json_path="data.task_id",
        status_json_path="",
        result_url_json_path="",
        request_template_json={
            "model": "{remote_model_id}",
            "mode": "{mode}",
            "prompt": "{prompt}",
            "durations_seconds": "{duration_seconds}",
            "aspect_ratio": "{aspect_ratio}",
            "resolution": "{resolution}",
            "first_frame_url": "{first_frame_url}",
            "last_frame_url": "{last_frame_url}",
            "reference_image_urls": ["{reference_image_urls}"],
            "options": "{options}",
        },
    ),
    poll=EndpointSpec(
        method="GET",
        path="/tasks/{task_id}",
        success_statuses=frozenset({200}),
        id_json_path="",
        status_json_path="data.status",
        result_url_json_path="",
    ),
    result=EndpointSpec(
        method="GET",
        path="/tasks/{task_id}/result",
        success_statuses=frozenset({200}),
        id_json_path="",
        status_json_path="",
        result_url_json_path="data.url",
    ),
    remote_status_map={
        "queued": "queued",
        "pending": "queued",
        "processing": "running",
        "running": "running",
        "succeeded": "succeeded",
        "completed": "succeeded",
        "failed": "failed",
        "cancelled": "cancelled",
        "canceled": "cancelled",
    },
    allowed_http_methods=("GET", "POST"),
)

# ---- 模型 Profile：允许的模式 / 时长 / 比例 / 分辨率 ----
GENERIC_PROFILES: tuple[ModelProfile, ...] = (
    ModelProfile(
        code="text_reference_media",
        display_name="通用文本/首尾帧视频",
        protocol_code="generic_async_json_v1",
        template_code="v1_videos_json_v1",
        remote_model_id="videos-mini",
        capability_profile_code="text_reference_media",
        modes=(VideoMode.TEXT_TO_VIDEO.value, VideoMode.FIRST_LAST_FRAME_TO_VIDEO.value),
        durations_seconds=(5, 10, 15),
        aspect_ratios=("16:9", "9:16"),
        resolutions=("480p", "720p"),
        generation_options={"generate_audio": False},
        max_reference_images=1,
        max_source_videos=0,
        # 双轨：允许结果降级为厂商直链（下载失败/服务器不支持时）
        allows_provider_direct_url=True,
        provider_direct_url_ttl=3600,
        enabled=True,
    ),
)

# ---- 火山方舟 Seedance 官方原生协议（无模板，Adapter 原生调用） ----
ARK_PRESET = ProtocolPreset(
    code="ark_seedance_v1",
    name="火山方舟 Seedance 视频生成",
    version=1,
    source_types=(ApiSourceType.OFFICIAL.value,),
    allows_custom_base_url=False,  # 官方原生协议，固定官方地址，不允许自定义
    official_base_url="https://ark.cn-beijing.volces.com",
    auth_fields=(
        DynamicField(
            name="api_key",
            label="API 密钥",
            required=True,
            is_secret=True,
            source="header",
            placeholder="Bearer <ark-...>",
        ),
    ),
    option_fields=(
        DynamicField(name="region", label="地域（可选）", required=False, source="body"),
    ),
    adapter_code="ark_seedance_v1",
    enabled=True,
)

# ---- Ark 模型 Profile：一个 Adapter 挂多个模型（1.5 Pro / 2.0） ----
ARK_PROFILES: tuple[ModelProfile, ...] = (
    ModelProfile(
        code="doubao-seedance-1-5-pro",
        display_name="Doubao Seedance 1.5 Pro",
        protocol_code="ark_seedance_v1",
        template_code=None,  # 原生协议无模板
        remote_model_id="doubao-seedance-1-5-pro-251215",
        capability_profile_code="text_reference_media",
        modes=(
            VideoMode.TEXT_TO_VIDEO.value,
            VideoMode.FIRST_FRAME_TO_VIDEO.value,
            VideoMode.FIRST_LAST_FRAME_TO_VIDEO.value,
            VideoMode.REFERENCE_IMAGE_TO_VIDEO.value,
        ),
        durations_seconds=(4, 5, 8, 10, 12),
        aspect_ratios=("16:9", "9:16", "4:3", "3:4", "1:1", "21:9"),
        resolutions=("480p", "720p", "1080p"),
        generation_options={"generate_audio": True},
        max_reference_images=1,
        max_source_videos=0,
        # 双轨：Ark 返回 24h 的 video_url 直链，下载失败时回退为直链交付
        allows_provider_direct_url=True,
        provider_direct_url_ttl=86400,
        enabled=True,
    ),
    ModelProfile(
        code="doubao-seedance-2-0",
        display_name="Doubao Seedance 2.0",
        protocol_code="ark_seedance_v1",
        template_code=None,  # 原生协议无模板
        remote_model_id="doubao-seedance-2-0-260128",
        capability_profile_code="text_reference_media",
        modes=(
            VideoMode.TEXT_TO_VIDEO.value,
            VideoMode.FIRST_FRAME_TO_VIDEO.value,
            VideoMode.FIRST_LAST_FRAME_TO_VIDEO.value,
            VideoMode.REFERENCE_IMAGE_TO_VIDEO.value,
        ),
        durations_seconds=(4, 5, 8, 10, 12, 15),
        aspect_ratios=("16:9", "9:16", "4:3", "3:4", "1:1", "21:9"),
        # 2.0 只支持 480p/720p
        resolutions=("480p", "720p"),
        generation_options={"generate_audio": True},
        max_reference_images=1,
        max_source_videos=0,
        allows_provider_direct_url=True,
        provider_direct_url_ttl=86400,
        enabled=True,
    ),
    # ---- Seedance 1.0 Pro Fast（火山方舟接入点绑定；调用时 model=ep-…）----
    ModelProfile(
        code="doubao-seedance-1-0-pro-fast",
        display_name="Doubao Seedance 1.0 Pro Fast",
        protocol_code="ark_seedance_v1",
        template_code=None,
        remote_model_id="ep-20260908233754-lwzxm",
        capability_profile_code="text_reference_media",
        modes=(
            VideoMode.TEXT_TO_VIDEO.value,
            VideoMode.FIRST_FRAME_TO_VIDEO.value,
            VideoMode.FIRST_LAST_FRAME_TO_VIDEO.value,
            VideoMode.REFERENCE_IMAGE_TO_VIDEO.value,
        ),
        durations_seconds=(5, 8, 10, 12),
        aspect_ratios=("16:9", "9:16", "1:1"),
        resolutions=("480p", "720p", "1080p"),
        generation_options={"generate_audio": True},
        max_reference_images=1,
        max_source_videos=0,
        allows_provider_direct_url=True,
        provider_direct_url_ttl=86400,
        enabled=True,
    ),
    # ---- Seedance 2.0 Fast ----
    ModelProfile(
        code="doubao-seedance-2-0-fast",
        display_name="Doubao Seedance 2.0 Fast",
        protocol_code="ark_seedance_v1",
        template_code=None,
        remote_model_id="doubao-seedance-2-0-fast-260128",
        capability_profile_code="text_reference_media",
        modes=(
            VideoMode.TEXT_TO_VIDEO.value,
            VideoMode.FIRST_FRAME_TO_VIDEO.value,
            VideoMode.FIRST_LAST_FRAME_TO_VIDEO.value,
            VideoMode.REFERENCE_IMAGE_TO_VIDEO.value,
        ),
        durations_seconds=(4, 5, 8, 10, 12, 15),
        aspect_ratios=("16:9", "9:16", "4:3", "3:4", "1:1", "21:9"),
        resolutions=("480p", "720p"),
        generation_options={"generate_audio": True},
        max_reference_images=1,
        max_source_videos=0,
        allows_provider_direct_url=True,
        provider_direct_url_ttl=86400,
        enabled=True,
    ),
    # ---- Seedance 1.0 Pro（扣积分不扣火山币的正统版） ----
    ModelProfile(
        code="doubao-seedance-1-0-pro",
        display_name="Doubao Seedance 1.0 Pro",
        protocol_code="ark_seedance_v1",
        template_code=None,
        remote_model_id="doubao-seedance-1-0-pro-250528",
        capability_profile_code="text_reference_media",
        modes=(
            VideoMode.TEXT_TO_VIDEO.value,
            VideoMode.FIRST_FRAME_TO_VIDEO.value,
            VideoMode.FIRST_LAST_FRAME_TO_VIDEO.value,
            VideoMode.REFERENCE_IMAGE_TO_VIDEO.value,
        ),
        durations_seconds=(2, 5, 8, 10, 12),
        aspect_ratios=("16:9", "9:16", "4:3", "3:4", "1:1", "21:9"),
        resolutions=("480p", "720p", "1080p"),
        generation_options={"generate_audio": True},
        max_reference_images=1,
        max_source_videos=0,
        allows_provider_direct_url=True,
        provider_direct_url_ttl=86400,
        enabled=True,
    ),
    # ---- Seedance 1.0 Lite 文生（仅文本 -> 视频） ----
    ModelProfile(
        code="doubao-seedance-1-0-lite-t2v",
        display_name="Doubao Seedance 1.0 Lite（文生）",
        protocol_code="ark_seedance_v1",
        template_code=None,
        remote_model_id="doubao-seedance-1-0-lite-t2v-250428",
        capability_profile_code="text_reference_media",
        modes=(VideoMode.TEXT_TO_VIDEO.value,),
        durations_seconds=(2, 5, 10),
        aspect_ratios=("16:9", "9:16"),
        resolutions=("480p", "720p"),
        generation_options={"generate_audio": True},
        max_reference_images=0,
        max_source_videos=0,
        allows_provider_direct_url=True,
        provider_direct_url_ttl=86400,
        enabled=True,
    ),
    # ---- Seedance 1.0 Lite 图生（首帧 / 参考图 -> 视频） ----
    ModelProfile(
        code="doubao-seedance-1-0-lite-i2v",
        display_name="Doubao Seedance 1.0 Lite（图生）",
        protocol_code="ark_seedance_v1",
        template_code=None,
        remote_model_id="doubao-seedance-1-0-lite-i2v-250428",
        capability_profile_code="text_reference_media",
        modes=(
            VideoMode.FIRST_FRAME_TO_VIDEO.value,
            VideoMode.REFERENCE_IMAGE_TO_VIDEO.value,
        ),
        durations_seconds=(2, 5, 10),
        aspect_ratios=("16:9", "9:16"),
        resolutions=("480p", "720p"),
        generation_options={"generate_audio": True},
        max_reference_images=1,
        max_source_videos=0,
        allows_provider_direct_url=True,
        provider_direct_url_ttl=86400,
        enabled=True,
    ),
)
