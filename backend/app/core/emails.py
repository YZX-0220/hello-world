"""邮箱规范化工具。"""

from email_validator import EmailNotValidError, validate_email


def normalize_email(email: str) -> str:
    """去掉首尾空格并转为小写，返回规范化邮箱。

    若格式非法则抛出 ValueError，由调用方（schema/service）转成 422 或统一错误。
    """
    raw = email.strip().lower()
    try:
        validated = validate_email(raw, check_deliverability=False)
        return validated.normalized
    except EmailNotValidError as exc:
        raise ValueError(f"邮箱格式不正确：{exc}") from exc

