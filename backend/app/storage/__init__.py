"""素材存储层工厂与统一入口。"""

from app.core.config import settings
from app.storage.base import Storage, StorageError, StoredFile
from app.storage.local import LocalStorage
from app.storage.obs import ObsStorage


def get_storage() -> Storage:
    """根据系统配置获取存储实现实例。配置了 OBS 时优先使用 OBS。"""
    if (
        settings.huawei_cloud_obs_endpoint
        and settings.huawei_cloud_obs_bucket
        and settings.huawei_cloud_obs_access_key
        and settings.huawei_cloud_obs_secret_key
    ):
        return ObsStorage()
    return LocalStorage(settings.storage_root)


def get_asset_storage(asset) -> Storage:
    """Read existing assets from their recorded backend, independently of new-upload policy."""
    if asset.storage_provider == "local":
        return LocalStorage(settings.storage_root)
    return get_storage()


__all__ = [
    "LocalStorage",
    "ObsStorage",
    "Storage",
    "StorageError",
    "StoredFile",
    "get_asset_storage",
    "get_storage",
]
