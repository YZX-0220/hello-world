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
    content_url: str | None  # ready 时返回本站受控读取地址
    created_at: datetime
