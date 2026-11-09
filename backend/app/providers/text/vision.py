"""Explicit visual model routing; never silently substitute a text-only model."""

from app.core.config import settings
from app.providers.text.base import TextProviderError
from app.providers.text.openai_compatible import OpenAICompatibleTextProvider


def _configuration():
    dedicated = (
        settings.vision_base_url.strip(),
        settings.vision_api_key.strip(),
        settings.vision_model.strip(),
    )
    if any(dedicated):
        return (*dedicated, settings.vision_timeout) if all(dedicated) else None
    text = (
        settings.text_base_url.strip(),
        settings.text_api_key.strip(),
        settings.text_model.strip(),
    )
    if (
        settings.text_supports_vision
        and settings.text_provider == "openai_compatible"
        and all(text)
    ):
        return (*text, settings.text_timeout)
    return None


def vision_available():
    return _configuration() is not None


def get_vision_provider():
    config = _configuration()
    if config is None:
        raise TextProviderError(
            "VISION_NOT_CONFIGURED", "尚未配置支持看图的文字模型。", retryable=False
        )
    base_url, api_key, model, timeout = config
    return OpenAICompatibleTextProvider(
        base_url=base_url, api_key=api_key, model=model, timeout=timeout, supports_vision=True
    )
