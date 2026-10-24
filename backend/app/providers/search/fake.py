"""开发/测试用的 Fake 搜索 Provider。返回固定占位结果，便于走通链路。"""


from app.core.time import now
from app.providers.search.base import SearchProvider, SearchResult


class FakeSearchProvider(SearchProvider):
    code = "fake"

    async def search(self, query: str, limit: int = 5) -> list[SearchResult]:
        return [
            SearchResult(
                title=f"关于「{query}」的参考资料（Fake 数据）",
                url="https://example.com/reference/1",
                snippet=f"与「{query}」相关的摘要内容。外网资料仅作参考，请以实际为准。（Fake 搜索数据）",
                retrieved_at=now(),
            )
        ]


fake_search_instance = FakeSearchProvider()
