"""结构化日志与敏感字段脱敏。

安全要求：API Key、Session Token、验证码、密码、临时签名等绝不进入日志。
logging_filter 拦截日志记录的 dict 参数与 message，将敏感键替换为掩码。
"""

from logging import INFO, Filter, Formatter, LogRecord, StreamHandler, getLevelName, getLogger
from re import IGNORECASE
from re import compile as regex_compile
from re import sub as regex_sub

from app.core.config import settings

# 需要被脱敏的敏感键名（含常见变体）
_SENSITIVE_KEYS = {
    "password",
    "api_key",
    "apikey",
    "token",
    "access_token",
    "refresh_token",
    "secret",
    "secret_key",
    "code",
    "auth",
    "authorization",
    "session",
    "credential",
    "signature",
    "signed_token",
}

_SENSITIVE_KEY_RE = regex_compile(
    r"(_password|api[_-]?key|token|secret|code|auth|signature|credential)", IGNORECASE
)


def _mask(key: str) -> str:
    """把敏感键的值替换为掩码。"""
    if _SENSITIVE_KEY_RE.search(key):
        return "***REDACTED***"
    return key


class SensitiveFilter(Filter):
    """过滤日志记录中的敏感字段。"""

    def filter(self, record: LogRecord) -> bool:
        # Third-party loggers (e.g. httpx during real AI requests) have no request context.
        if not hasattr(record, "request_id"):
            record.request_id = "-"
        # Render positional/mapping args first: httpx logs signed URLs via %s.
        # Clear args after rendering so handlers cannot reinsert the original secrets.
        message = record.getMessage()
        record.msg = regex_sub(
            r"((?:password|api_key|apikey|token|secret|code|auth|signature|credential)[^:=&]*[:=]\s*)[^\s,}&\"']+",
            r"\1***REDACTED***",
            message,
            flags=IGNORECASE,
        )
        record.args = ()
        return True


def setup_logging() -> None:
    """配置根日志器：级别、统一格式、敏感过滤。"""
    resolved = getLevelName(settings.log_level.upper())
    level = resolved if isinstance(resolved, int) else INFO
    handler = StreamHandler()
    handler.setFormatter(
        Formatter(
            fmt="%(asctime)s %(levelname)s %(name)s [%(request_id)s] %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
    )
    handler.addFilter(SensitiveFilter())
    root = getLogger()
    root.handlers = [handler]
    root.setLevel(level)
    root.addFilter(SensitiveFilter())
