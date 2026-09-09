"""视频 Provider 工厂。按 VIDEO_PROVIDER 配置返回 Fake / generic_async_json_v1 / ark_seedance_v1 实现。"""

from app.core.config import settings
from app.providers.video.base import VideoProvider
from app.providers.video.fake import fake_video_instance

__all__ = ["VideoProvider"]


def get_video_provider() -> VideoProvider:
    if settings.video_provider == "generic_v1":
        from app.providers.video.generic_async_json_v1 import GenericAsyncJsonV1Provider

        return GenericAsyncJsonV1Provider()
    if settings.video_provider == "ark_seedance_v1":
        from app.providers.video.ark_seedance_v1 import ArkSeedanceProvider

        return ArkSeedanceProvider()
    if settings.video_provider == "dashscope_async_v1":
        from app.providers.video.dashscope_async_v1 import DashScopeAsyncV1Provider

        return DashScopeAsyncV1Provider()
    return fake_video_instance
