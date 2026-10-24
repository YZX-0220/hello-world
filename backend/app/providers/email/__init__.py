"""邮件 Provider 工厂。根据 EMAIL_PROVIDER 配置返回 Fake 或 SMTP 实现。"""

from app.core.config import settings
from app.providers.email.base import EmailProvider
from app.providers.email.fake import fake_instance
from app.providers.email.smtp import SmtpEmailProvider


def get_email_provider() -> EmailProvider:
    """返回配置的邮件 Provider。可在测试中 override。"""
    if settings.email_provider == "smtp":
        return SmtpEmailProvider()
    return fake_instance


__all__ = ["EmailProvider", "get_email_provider"]
