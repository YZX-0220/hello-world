"""素材本地存储层。"""

from app.storage.base import Storage, StorageError, StoredFile
from app.storage.local import LocalStorage

__all__ = ["LocalStorage", "Storage", "StorageError", "StoredFile"]
