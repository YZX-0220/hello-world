"""搜索 Provider 抽象与结果/错误定义。"""

from abc import ABC, abstractmethod
from datetime import datetime

from pydantic import BaseModel


class SearchResult(BaseModel):
    """一条搜索结果（本站统一类型）。"""

    title: str
    url: str
    snippet: str
    published_at: datetime | None = None
    retrieved_at: datetime


class SearchProviderError(Exception):
    """搜索 Provider 错误，带是否可重试标记。"""

    def __init__(self, code: str, message: str, retryable: bool = True) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable


class SearchProvider(ABC):
    @property
    @abstractmethod
    def code(self) -> str:
        raise NotImplementedError

    @abstractmethod
    async def search(self, query: str, limit: int = 5) -> list[SearchResult]:
        raise NotImplementedError
