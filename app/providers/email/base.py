"""邮件 Provider 抽象。所有邮件发送走统一接口，业务代码不关心底层是 SMTP 还是 Fake。"""

from abc import ABC, abstractmethod

from app.core.enums import EmailCodePurpose


class EmailProvider(ABC):
    """验证码邮件发送接口。"""

    @abstractmethod
    async def send_code(self, to_email: str, code: str, purpose: EmailCodePurpose) -> None:
        """向 to_email 发送验证码邮件，purpose 用于区分注册/登录/重置场景。"""
        raise NotImplementedError
