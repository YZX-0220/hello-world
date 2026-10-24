"""时间工具。

关键约定（用户特别指定）：后端所有时间一律采用【服务器本地时间】，
以 naive datetime 保存与输出，不做 UTC 转换。禁止使用
`datetime.now(timezone.utc)` 或 `astimezone(utc)`。

API 输出统一走 iso8601，得到不带时区后缀的本地时间字符串。
"""

from datetime import datetime


def now() -> datetime:
    """当前服务器本地时间（naive）。所有时间字段默认值统一用它。"""
    return datetime.now()


def iso8601(dt: datetime) -> str:
    """把 naive 本地时间格式化为 ISO 8601 字符串（不带时区后缀）。"""
    return dt.isoformat()


def parse_iso8601(value: str) -> datetime:
    """把 ISO 8601 字符串解析为 naive 本地时间。

    若字符串带时区偏移（如 '...Z' 或 '+08:00'），会先转换为服务器本地时间再去掉时区，
    以保证与库内 naive 时间语义一致。
    """
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is not None:
        # 转本地时区（不含 UTC 转换问题，时间语义仍以机器本地为准）
        parsed = parsed.astimezone().replace(tzinfo=None)
    return parsed
