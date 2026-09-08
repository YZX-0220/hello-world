"""结构化日志与敏感字段脱敏。

安全要求：API Key、Session Token、验证码、密码、临时签名等绝不进入日志。
logging_filter 拦截日志记录的 dict 参数与 message，将敏感键替换为掩码。
"""

import contextlib
import logging
import re

from app.core.config import settings

# 需要被脱敏的敏感键名（含常见变体）
_SENSITIVE_KEYS = {
    "password", "api_key", "apikey", "token", "access_token", "refresh_token",
    "secret", "secret_key", "code", "auth", "authorization", "session",
    "credential", "signature", "signed_token",
}

_SENSITIVE_KEY_RE = re.compile(r"(_password|api[_-]?key|token|secret|code|auth|signature|credential)", re.IGNORECASE)


def _mask(key: str) -> str:
    """把敏感键的值替换为掩码。"""
    if _SENSITIVE_KEY_RE.search(key):
        return "***REDACTED***"
    return key


class SensitiveFilter(logging.Filter):
    """过滤日志记录中的敏感字段。"""

    def filter(self, record: logging.LogRecord) -> bool:
        # message 里的敏感键名值替换
        if isinstance(record.msg, str):
            with contextlib.suppress(re.error):
                record.msg = re.sub(
                    r"((?:password|api_key|apikey|token|secret|code|auth|signature|credential)[^:=]*[:=]\s*)[^\s,}]+",
                    r"\1***REDACTED***",
                    record.msg,
                    flags=re.IGNORECASE,
                )
        return True


def setup_logging() -> None:
    """配置根日志器：级别、统一格式、敏感过滤。"""
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s %(levelname)s %(name)s [%(request_id)s] %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
    )
    handler.addFilter(SensitiveFilter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
    root.addFilter(SensitiveFilter())
