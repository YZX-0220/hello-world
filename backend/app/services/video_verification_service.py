"""视频接口配置的安全约束校验与「三态检测」。

对应《实施计划》4.8、接口说明 6.4：
  - 校验协议/模板/能力引用、中转风险确认、Base URL 安全（SSRF）；
  - 检测状态为 verified / invalid / unverified，检测不得创建收费视频；
  - unverified 表示没有安全、免费的检测手段，不代表配置一定无效 —— 允许用户在明确
    点击生成后再做首次真实调用；invalid / disabled 配置禁止创建任务。

阶段 6 的检测策略：
  - 在 video_provider=fake（开发/演示）时，无真实连通检测手段，返回 verified 供联调，
    但 message 明确说明「未做真实连通性检测」；
  - 真实 generic_async_json_v1 无免费探测端点时返回 unverified（保守），留待任务创建时首调。
"""

from typing import Any

from app.core.config import settings
from app.core.errors import RELAY_RISK_NOT_ACCEPTED, UNSAFE_BASE_URL, VIDEO_CONFIG_INVALID, AppError
from app.core.ssrf import UnsafeUrlError, check_base_url, normalize_base_url
from app.core.time import now
from app.schemas.video_api_config import (
    TestVideoApiConfigResult,
    VideoApiConfigBase,
)
from app.services.video_registry_service import ProtocolReferences, validate_payload_refs


def _validate_constraints(payload: VideoApiConfigBase, resolver: Any = None) -> ProtocolReferences:
    """创建/保存/检测前必做的约束校验，失败抛 AppError。

    resolver 供测试注入（如 mock DNS）；生产默认结构校验（不发起 DNS），
    真正的解析安全判定在任务提交前再做一次。
    """
    refs = validate_payload_refs(payload.protocol_code, payload.template_code, payload.capability_profile_code)

    if payload.source_type == "relay":
        if not payload.relay_risk_accepted:
            raise AppError(RELAY_RISK_NOT_ACCEPTED)
        if not payload.base_url:
            raise AppError(VIDEO_CONFIG_INVALID, "中转配置必须提供基础地址")
        try:
            normalize_base_url(payload.base_url)
            if resolver is not None:
                check_base_url(payload.base_url, resolver)
        except UnsafeUrlError as exc:
            raise AppError(UNSAFE_BASE_URL, str(exc), {"base_url": payload.base_url}) from exc
    return refs


def _build_detection(payload: VideoApiConfigBase, resolver: Any = None) -> TestVideoApiConfigResult:
    """对（未保存或已保存的）配置做约束校验与检测，返回三态结果。"""
    refs = _validate_constraints(payload, resolver)
    model_visible = refs.profile is not None

    if settings.video_provider == "fake":
        return TestVideoApiConfigResult(
            verification_status="verified",
            message="语法与安全约束通过（开发模式，未进行真实连通性检测）",
            checked_at=now(),
            safe_details={"model_visible": model_visible},
        )
    return TestVideoApiConfigResult(
        verification_status="unverified",
        message="暂无免费连通性检测手段，创建后在生成时将进行首次真实调用",
        checked_at=now(),
        safe_details={"model_visible": model_visible},
    )


__all__ = ["_build_detection", "_validate_constraints"]
