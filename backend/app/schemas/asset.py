"""素材视图模型（接口说明 3.13）。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AssetView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    conversation_id: str | None
    kind: str  # image/video/audio
    purpose: str  # 首帧/尾帧/参考/源视频/音频/结果
    original_name: str
    mime_type: str
    size_bytes: int
    width: int | None
    height: int | None
    duration_ms: int | None
    status: str  # uploading/ready/quarantined/deleted
    content_url: str | None  # ready 时返回本站受控读取地址或直读重定向
    direct_url: str | None = None  # OBS 预签名直读/播放链接
    created_at: datetime


class AssetUploadIntentRequest(BaseModel):
    filename: str
    purpose: str
    kind: str | None = None  # 可选 image/video/audio
    byte_size: int
    content_type: str
    file_hash: str | None = None  # 客户端计算的 MD5/SHA256（用于秒传）
    conversation_id: str | None = None


class AssetUploadIntentResponse(BaseModel):
    asset_id: str
    upload_url: str | None = None  # 直传 PUT 预签名地址（秒传时为 None）
    object_key: str
    is_duplicate: bool = False  # 是否命中秒传
    content_type: str
    asset: AssetView | None = None  # 秒传成功时直接带上 Asset 详情


class AssetUploadCompleteRequest(BaseModel):
    file_hash: str | None = None
