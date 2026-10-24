"""文本 Provider 抽象与通用结果/能力定义。

对应《实施计划》4.4 节：统一接口至少支持普通非流式生成、JSON 结构化输出能力标记、
工具调用能力标记、原生搜索能力标记、模型名/请求 ID/Token 用量/结束原因，以及分类后的
可重试与不可重试错误。首期先保证非流式链路可靠。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from pydantic import BaseModel


class TextProviderError(Exception):
    """文本 Provider 错误，带分类（是否可重试）。"""

    def __init__(self, code: str, message: str, retryable: bool = True) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable


class TextResult(BaseModel):
    """非流式生成结果（本站统一类型，不向上泄露厂商原始对象）。"""

    reply: str = ""
    structured: dict | None = None  # 若请求结构输出，解析后的 JSON
    model: str = ""
    request_id: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    finish_reason: str | None = None


@dataclass
class TextCapabilities:
    """一个 Provider 的能力标记（用于前端展示与能力判断）。"""

    supports_structured_output: bool = False
    supports_tool_call: bool = False
    supports_native_search: bool = False
    output_token_limit: int = 8192


class TextProvider(ABC):
    """文本 Provider 统一接口。"""

    @property
    @abstractmethod
    def code(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def capabilities(self) -> TextCapabilities:
        raise NotImplementedError

    @abstractmethod
    async def generate(self, messages: list[dict[str, str]], *, structured: bool = False) -> TextResult:
        """给定对话消息，返回非流式生成结果。structured=True 时请求结构化输出。

        messages 形如 [{"role": "system"|"user"|"assistant", "content": "..."}]。
        """
        raise NotImplementedError
