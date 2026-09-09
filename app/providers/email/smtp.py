"""SMTP 邮件 Provider（基于 aiosmtplib）。

支持 SSL(465) / STARTTLS(587) / 明文 三种；登录账号为完整邮箱地址，密码为授权码（如 QQ 邮箱）。
"""

from email.message import EmailMessage

import aiosmtplib

from app.core.config import settings
from app.core.enums import EmailCodePurpose
from app.providers.email.base import EmailProvider

# 各用途的邮件主题（前端/用户可见文案，避免暴露内部信息）
_SUBJECTS = {
    EmailCodePurpose.REGISTER.value: "Hello World 注册验证码",
    EmailCodePurpose.LOGIN.value: "Hello World 登录验证码",
    EmailCodePurpose.RESET_PASSWORD.value: "Hello World 重置密码验证码",
}


class SmtpEmailProvider(EmailProvider):
    """通过 SMTP 服务器发送验证码邮件。"""

    async def send_code(self, to_email: str, code: str, purpose: EmailCodePurpose) -> None:
        tls = settings.smtp_tls.upper()
        subject = _SUBJECTS.get(purpose.value, "Hello World 验证码")
        body = (
            # 验证码后加句号再换行：部分邮件客户端不渲染换行，避免六位验证码与"5 分钟"粘连成 7 位
            f"你的验证码是：{code}。\n"
            f"5 分钟内有效。如果这不是你本人的操作，请忽略此邮件。"
        )

        message = EmailMessage()
        message["From"] = settings.smtp_from
        message["To"] = to_email
        message["Subject"] = subject
        message.set_content(body)

        smtp = aiosmtplib.SMTP(
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_username or None,
            password=settings.smtp_password or None,
            use_tls=(tls == "SSL"),
            start_tls=(tls == "STARTTLS"),
            validate_certs=True,
            timeout=settings.smtp_connect_timeout,
        )
        async with smtp:
            await smtp.send_message(message, sender=settings.smtp_from, recipients=[to_email])
