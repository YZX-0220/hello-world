"""真实搜索 Provider（Tavily）。

对接 Tavily Search API：POST {SEARCH_BASE_URL}/search（默认 https://api.tavily.com）。
认证用 Authorization: Bearer <key>；请求 {"query", "max_results"}；响应
{"results":[{"title","url","content","published_date"...}]}。搜索失败抛 SearchProviderError。

兼容性：snippet 字段优先取响应的 content（Tavily 用 content 而非 snippet）；published_date 尽力解析，
解析失败置 None，不影响结果。
"""

from datetime import datetime

import httpx
from pydantic import ValidationError

from app.core.config import settings
from app.core.time import now
from app.providers.search.base import SearchProvider, SearchProviderError, SearchResult


def _parse_date(value: object):
    """把 published_date（如 '2024-01-15'）解析为 naive datetime；失败返回 None。"""
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


class ConfiguredSearchProvider(SearchProvider):
    code = "configured"

    async def search(self, query: str, limit: int = 5) -> list[SearchResult]:
        if not settings.search_base_url:
            raise SearchProviderError("SEARCH_UNAVAILABLE", "搜索接口未配置", retryable=False)
        url = f"{settings.search_base_url.rstrip('/')}/search"
        payload = {"query": query, "max_results": limit}
        headers = {"Authorization": f"Bearer {settings.search_api_key}", "Content-Type": "application/json"}
        try:
            async with httpx.AsyncClient(timeout=settings.search_timeout) as client:
                resp = await client.post(url, json=payload, headers=headers)
        except httpx.HTTPError as exc:
            raise SearchProviderError("SEARCH_UNAVAILABLE", "搜索服务暂时不可用", retryable=True) from exc
        if resp.status_code >= 400:
            raise SearchProviderError("SEARCH_UNAVAILABLE", f"搜索服务返回 {resp.status_code}", retryable=resp.status_code >= 500)

        data = resp.json()
        raw_results = data.get("results") or []
        results: list[SearchResult] = []
        for item in raw_results[:limit]:
            try:
                results.append(
                    SearchResult(
                        title=str(item.get("title", "")),
                        url=str(item.get("url", "")),
                        snippet=str(item.get("snippet") or item.get("content") or ""),
                        published_at=_parse_date(item.get("published_date")),
                        retrieved_at=now(),
                    )
                )
            except ValidationError:
                continue
        return results
