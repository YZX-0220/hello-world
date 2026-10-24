"""视频 Provider 抽象与统一结果定义。

Provider 返回本站定义的类型（VideoSubmitResult / VideoTaskStatus），不向上泄露厂商原始对象。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


class VideoProviderError(Exception):
    """视频 Provider 错误，带分类（是否可重试）与稳定错误码。"""

    def __init__(self, code: str, message: str, retryable: bool = True) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable


@dataclass(frozen=True)
class VideoTaskStatus:
    """厂商任务状态（raw 远端状态，未做本站映射；由 service 层按模板映射）。"""

    raw_status: str
    progress: int | None = None
    result_url: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class VideoSubmitResult:
    """提交厂商成功后的结果。"""

    provider_task_id: str
    provider_context_id: str | None = None


@dataclass(frozen=True)
class AdapterContext:
    """一次厂商调用所需的连接与模板上下文（base_url/auth/options/template）。"""

    base_url: str
    auth: dict[str, str]
    options: dict[str, Any]
    remote_model_id: str
    template: Any | None = None  # ProtocolTemplate 或 None


class VideoProvider(ABC):
    """视频厂商统一接口。所有实现都返回本站定义的类型。"""

    @property
    @abstractmethod
    def code(self) -> str:
        raise NotImplementedError

    @abstractmethod
    async def submit(self, request: dict[str, Any], ctx: AdapterContext) -> VideoSubmitResult:
        """提交任务，返回远端任务 ID。"""
        raise NotImplementedError

    @abstractmethod
    async def poll(self, task_id: str, ctx: AdapterContext) -> VideoTaskStatus:
        """查询远端任务状态。"""
        raise NotImplementedError

    @abstractmethod
    async def fetch_result_url(self, task_id: str, ctx: AdapterContext) -> str | None:
        """取结果下载直链；无直链时返回 None（用于双轨降级）。"""
        raise NotImplementedError

    @abstractmethod
    async def download_result(self, task_id: str, ctx: AdapterContext) -> bytes | None:
        """把生成结果字节拉回本站；无法拉回（只支持直链）时返回 None（由 service 降级直链）。"""
        raise NotImplementedError

    @abstractmethod
    async def cancel(self, task_id: str, ctx: AdapterContext) -> bool:
        """尝试远端取消；返回是否成功取消。不支持则返回 False。"""
        raise NotImplementedError


__all__ = ["AdapterContext", "VideoProvider", "VideoProviderError", "VideoSubmitResult", "VideoTaskStatus"]
