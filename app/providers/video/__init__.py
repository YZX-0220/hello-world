"""视频 Provider 工厂。按 VIDEO_PROVIDER 配置返回 Fake 或 generic_async_json_v1 实现。"""

from app.core.config import settings
from app.providers.video.base import VideoProvider
from app.providers.video.fake import fake_video_instance

__all__ = ["VideoProvider"]


def get_video_provider() -> VideoProvider:
    if settings.video_provider == "generic_v1":
        from app.providers.video.generic_async_json_v1 import GenericAsyncJsonV1Provider

        return GenericAsyncJsonV1Provider()
    return fake_video_instance
