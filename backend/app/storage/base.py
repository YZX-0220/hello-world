"""存储抽象层。

对应《实施计划》4.9：本地文件只使用相对 Storage Root 的 storage_key；
业务接口不接受本机路径；读取时再次解析并验证最终路径仍位于 Storage Root 内。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


class StorageError(RuntimeError):
    """存储层错误（路径越界 / 文件不存在 / 写入失败等），message 为可展示中文说明。"""


@dataclass(frozen=True)
class StoredFile:
    """一次写入成功的结果：实际字节数与 SHA-256（供 Asset 元数据落库）。"""

    size_bytes: int
    sha256: str


class Storage(ABC):
    """本地文件存储抽象。所有方法只接受 relative storage_key，绝不接受绝对路径。"""

    @abstractmethod
    def write_stream(self, data: bytes, key: str, *, final_key: str) -> StoredFile:
        """把一次性读入的字节写入临时路径，边写边算 size/sha256，完成后原子移动到 final_key。

        返回最终 size 与 sha256。抛 StorageError 表示写入失败。
        """

    @abstractmethod
    def open_read_path(self, key: str) -> Path:
        """返回可用于 FileResponse 的最终路径；先做越界校验与存在性检查。"""

    @abstractmethod
    def exists(self, key: str) -> bool:
        """判定 storage_key 是否已存在（需通过越界校验）。"""

    @abstractmethod
    def delete(self, key: str) -> None:
        """安全删除一个 storage_key 对应的文件（越界则拒绝）。"""


__all__ = ["Storage", "StorageError", "StoredFile"]
