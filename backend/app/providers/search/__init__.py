"""搜索 Provider 工厂。根据 SEARCH_PROVIDER 配置返回 Fake 或真实实现。"""

from app.core.config import settings
from app.providers.search.base import SearchProvider, SearchResult
from app.providers.search.configured import ConfiguredSearchProvider
from app.providers.search.fake import fake_search_instance


def get_search_provider() -> SearchProvider:
    """返回配置的搜索 Provider。可在测试中 override。"""
    if settings.search_provider == "configured" and settings.search_base_url:
        return ConfiguredSearchProvider()
    return fake_search_instance


__all__ = ["SearchProvider", "SearchResult", "get_search_provider"]
