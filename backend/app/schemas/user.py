"""用户视图输出模型。绝不返回密码哈希、Session 摘要或安全密钥。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UserView(BaseModel):
    """用户视图（接口说明 3.1）。"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    email_verified_at: datetime
    status: str
    created_at: datetime
