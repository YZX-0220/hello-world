"""开发用 Fake 邮件 Provider。

不真正发信，把验证码打印到标准输出（开发联调用，便于手动输入验证码走通注册/登录），
同时记录到内存列表供测试断言。生产环境应配置 EMAIL_PROVIDER=smtp，不使用本实现。
"""

from app.core.enums import EmailCodePurpose
from app.providers.email.base import EmailProvider


class FakeEmailProvider(EmailProvider):
    """把验证码输出到 stdout 并记录最近发送记录。"""

    def __init__(self) -> None:
        self.sent: list[dict[str, str]] = []

    async def send_code(self, to_email: str, code: str, purpose: EmailCodePurpose) -> None:
        record = {"to": to_email, "code": code, "purpose": purpose.value}
        self.sent.append(record)
        print(f"[DEV EMAIL] to={to_email} code={code} purpose={purpose.value}")


# 模块级唯一实例，便于测试通过 providers_patch 获取已发送验证码
fake_instance = FakeEmailProvider()
