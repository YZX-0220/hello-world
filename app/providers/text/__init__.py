"""文本 Provider 工厂。根据 TEXT_PROVIDER 配置返回 Fake 或 OpenAI 兼容实现。"""

from app.core.config import settings
from app.providers.text.base import TextProvider
from app.providers.text.fake import fake_text_instance
from app.providers.text.openai_compatible import OpenAICompatibleTextProvider


def get_text_provider() -> TextProvider:
    """返回配置的文本 Provider。可在测试中 override。"""
    if settings.text_provider == "openai_compatible":
        return OpenAICompatibleTextProvider()
    return fake_text_instance


__all__ = ["TextProvider", "get_text_provider"]
