"""本地文件系统存储实现。

安全性要点：
  - 只接受相对 Storage Root 的 key，读取/删除前对最终路径做二次 resolve 与越界校验；
  - 写入先落随机临时文件，边写边算 size/sha256，完成后 os.replace 原子移动到最终位置，
    避免中途失败留下半成品或用户可见的中间文件。
"""

import hashlib
import os
from pathlib import Path

from app.storage.base import Storage, StorageError, StoredFile


class LocalStorage(Storage):
    """把文件存到磁盘上的某个根目录。"""

    def __init__(self, root: str | Path) -> None:
        self._root = Path(root).resolve()

    def _resolve(self, key: str) -> Path:
        """把 storage_key 解析为落在 Storage Root 内的绝对路径；越界抛 StorageError。"""
        if not key or key.startswith(("/", "\\")) or ".." in Path(key).parts:
            raise StorageError("非法存储路径")
        path = (self._root / key).resolve()
        if path != self._root and self._root not in path.parents:
            raise StorageError("存储路径越界")
        return path

    def _temp_key(self, key: str) -> str:
        """同目录下的随机临时路径（与最终文件同目录，保证同文件系统可原子重命名）。"""
        path = self._resolve(key)
        tmp = path.with_name(f".tmp-{os.urandom(8).hex()}-{path.name}")
        return str(tmp.relative_to(self._root))

    def write_stream(self, data: bytes, key: str, *, final_key: str) -> StoredFile:
        tmp_key = self._temp_key(key if final_key == key else final_key)
        tmp_path = self._resolve(tmp_key)
        tmp_path.parent.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256()
        try:
            tmp_path.write_bytes(b"")  # 创建文件
            with tmp_path.open("wb") as fh:
                fh.write(data)
                digest.update(data)
        except OSError as exc:
            raise StorageError("素材写入磁盘失败") from exc

        final_path = self._resolve(final_key)
        final_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.replace(tmp_path, final_path)  # 原子移动
        except OSError as exc:
            tmp_path.unlink(missing_ok=True)
            raise StorageError("素材落盘失败") from exc
        return StoredFile(size_bytes=len(data), sha256=digest.hexdigest())

    def open_read_path(self, key: str) -> Path:
        path = self._resolve(key)
        if not path.is_file():
            raise StorageError("素材文件不存在")
        return path

    def exists(self, key: str) -> bool:
        return self._resolve(key).is_file()

    def delete(self, key: str) -> None:
        try:
            self._resolve(key).unlink(missing_ok=True)
        except StorageError:
            raise
        except OSError as exc:
            raise StorageError("素材删除失败") from exc


__all__ = ["LocalStorage"]
