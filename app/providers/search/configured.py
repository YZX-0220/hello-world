"""真实搜索 Provider（占位实现）。

对接一个可配置的 JSON 搜索接口：POST {SEARCH_BASE_URL}/search，请求 {"query":...,"limit":...}，
响应 {"results":[{"title","url","snippet","published_at"}]}。未确定具体搜索服务商前，此实现按
该假设契约编写，实际接入时按对应服务调整请求/响应解析。搜索失败抛 SearchProviderError。
"""

import httpx
from pydantic import ValidationError

from app.core.config import settings
from app.core.time import now
from app.providers.search.base import SearchProvider, SearchProviderError, SearchResult


class ConfiguredSearchProvider(SearchProvider):
    code = "configured"

    async def search(self, query: str, limit: int = 5) -> list[SearchResult]:
        if not settings.search_base_url:
            raise SearchProviderError("SEARCH_UNAVAILABLE", "搜索接口未配置", retryable=False)
        url = f"{settings.search_base_url.rstrip('/')}/search"
        payload = {"query": query, "limit": limit, "pretty": False}
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
                        snippet=str(item.get("snippet", "")),
                        published_at=None,
                        retrieved_at=now(),
                    )
                )
            except ValidationError:
                continue
        return results
