"""华为云 OBS 对象存储实现。

实现与 LocalStorage 一致的基础能力（exists/delete），并扩展对象存储核心特权：
- 预签名上传 URL（PUT Direct Upload）
- 预签名读取 URL（GET Direct Read）
- 元数据与 ETag 核验
- 外部 URL 异步拉取转存（asyncFetchObject，零服务器流量）
"""

from pathlib import Path
from typing import Any

from obs import ObsClient

from app.core.config import settings
from app.storage.base import Storage, StorageError, StoredFile


class ObsStorage(Storage):
    """华为云 OBS 存储驱动。"""

    def __init__(
        self,
        endpoint: str | None = None,
        bucket: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
    ) -> None:
        self._endpoint = endpoint or settings.huawei_cloud_obs_endpoint
        self._bucket = bucket or settings.huawei_cloud_obs_bucket
        self._ak = access_key or settings.huawei_cloud_obs_access_key
        self._sk = secret_key or settings.huawei_cloud_obs_secret_key

        if not (self._endpoint and self._bucket and self._ak and self._sk):
            raise StorageError("华为云 OBS 存储配置不完整")

        if ObsClient is None:
            raise StorageError("未安装 esdk-obs-python 依赖")

        # 规范化 server 地址
        server = self._endpoint
        if not server.startswith(("http://", "https://")):
            server = f"https://{server}"

        self._client = ObsClient(
            access_key_id=self._ak,
            secret_access_key=self._sk,
            server=server,
            timeout=300,  # 针对服务器 3M 较慢上行大文件增加超时（秒）
        )

    def write_stream(self, data: bytes, key: str, *, final_key: str) -> StoredFile:
        """把内存数据直接上传至 OBS，不落本地磁盘。"""
        import hashlib

        object_key = final_key.lstrip("/")
        digest = hashlib.sha256(data).hexdigest()
        try:
            resp = self._client.putContent(self._bucket, object_key, data)
            if resp.status >= 300:
                raise StorageError(f"OBS 写入失败: {resp.errorCode} {resp.errorMessage}")
        except Exception as exc:
            if isinstance(exc, StorageError):
                raise
            raise StorageError(f"OBS 写入异常: {exc}") from exc

        return StoredFile(size_bytes=len(data), sha256=digest)

    def open_read_path(self, key: str) -> Path:
        """OBS 对象为云端文件，不支持本地文件系统直接 open_read_path。"""
        raise StorageError("OBS 对象不支持本地路径访问，请使用预签名读取链接")

    def exists(self, key: str) -> bool:
        object_key = key.lstrip("/")
        try:
            resp = self._client.getObjectMetadata(self._bucket, object_key)
            return resp.status < 300
        except Exception:
            return False

    def delete(self, key: str) -> None:
        object_key = key.lstrip("/")
        try:
            resp = self._client.deleteObject(self._bucket, object_key)
            if resp.status >= 300 and resp.status != 404:
                raise StorageError(f"OBS 删除失败: {resp.errorCode}")
        except Exception as exc:
            if isinstance(exc, StorageError):
                raise
            raise StorageError(f"OBS 删除异常: {exc}") from exc

    # ============ OBS 专属能力 ============

    def generate_presigned_upload_url(
        self, object_key: str, content_type: str | None = None, expires: int = 1800
    ) -> str:
        """生成供浏览器 PUT 直传的预签名 URL。"""
        clean_key = object_key.lstrip("/")
        headers = {"Content-Type": content_type} if content_type else None
        res = self._client.createSignedUrl(
            method="PUT",
            bucketName=self._bucket,
            objectKey=clean_key,
            expires=expires,
            headers=headers,
        )
        return str(res.signedUrl)

    def generate_presigned_download_url(
        self, object_key: str, expires: int = 3600, filename: str | None = None
    ) -> str:
        """生成供浏览器直接播放/查看/下载的预签名 GET URL。"""
        clean_key = object_key.lstrip("/")
        queryParams: dict[str, Any] = {}
        if filename:
            from urllib.parse import quote

            encoded = quote(filename)
            queryParams["response-content-disposition"] = f"inline; filename*=utf-8''{encoded}"

        res = self._client.createSignedUrl(
            method="GET",
            bucketName=self._bucket,
            objectKey=clean_key,
            expires=expires,
            queryParams=queryParams if queryParams else None,
        )
        return str(res.signedUrl)

    def get_object_metadata(self, object_key: str) -> dict[str, Any]:
        """获取对象元数据（ETag, content-length, content-type）。"""
        clean_key = object_key.lstrip("/")
        resp = self._client.getObjectMetadata(self._bucket, clean_key)
        if resp.status >= 300:
            raise StorageError(f"对象不存在或读取失败: {resp.errorCode}")

        headers_dict = dict(resp.header or [])
        etag = headers_dict.get("etag", "").strip('"')
        content_length = int(headers_dict.get("content-length", 0))
        content_type = headers_dict.get("content-type", "")

        return {
            "etag": etag,
            "size_bytes": content_length,
            "content_type": content_type,
        }

    def async_fetch_object(self, remote_url: str, object_key: str) -> str:
        """异步拉取外部 URL 转存入桶（方式 A：零服务器流量）。

        华为云 OBS Python SDK 对应方法为 setBucketFetchJob。
        返回 OBS 异步任务 ID 或转存后的目标 key。
        """
        clean_key = object_key.lstrip("/")
        try:
            if hasattr(self._client, "setBucketFetchJob"):
                resp = self._client.setBucketFetchJob(
                    bucketName=self._bucket,
                    job={"url": remote_url, "object": clean_key},
                )
                if resp.status < 300:
                    body = resp.body
                    return str(getattr(body, "id", "") or clean_key)
        except Exception:
            pass

        # 若当前区域不支持 setBucketFetchJob 或权限受限，平滑回退至流式转储（Pipe）
        import httpx

        with httpx.stream("GET", remote_url, timeout=120) as stream_resp:
            stream_resp.raise_for_status()
            content = stream_resp.read()
            self.write_stream(content, clean_key, final_key=clean_key)
        return clean_key

    def close(self) -> None:
        if hasattr(self, "_client") and self._client:
            self._client.close()


__all__ = ["ObsStorage"]
