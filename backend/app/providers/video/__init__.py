"""视频 Provider 工厂。按 VIDEO_PROVIDER 配置返回 Fake / generic_async_json_v1 / ark_seedance_v1 实现。"""

from app.core.config import settings
from app.providers.video.base import VideoProvider
from app.providers.video.fake import fake_video_instance

__all__ = ["VideoProvider"]


def get_video_provider(protocol_code: str | None = None) -> VideoProvider:
    if settings.video_provider == "fake":
        return fake_video_instance
    protocol = protocol_code or settings.video_provider
    if protocol in ("generic_v1", "generic_async_json_v1"):
        from app.providers.video.generic_async_json_v1 import GenericAsyncJsonV1Provider

        return GenericAsyncJsonV1Provider()
    if protocol == "ark_seedance_v1":
        from app.providers.video.ark_seedance_v1 import ArkSeedanceProvider

        return ArkSeedanceProvider()
    if protocol == "dashscope_async_v1":
        from app.providers.video.dashscope_async_v1 import DashScopeAsyncV1Provider

        return DashScopeAsyncV1Provider()
    if protocol == "fal_queue_v1":
        from app.providers.video.fal_queue_v1 import FalQueueV1Provider

        return FalQueueV1Provider()
    from app.providers.video.base import VideoProviderError

    raise VideoProviderError(
        "VIDEO_PROTOCOL_UNSUPPORTED", "视频通道协议没有可用适配器。", retryable=False
    )
