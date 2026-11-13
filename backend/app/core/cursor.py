"""游标分页的游标编码/解码工具。

游标统一用 base64 编码的 JSON 数组来表示「排序键 + 稳定 tiebreak 主键」，
例如按 (created_at, id) 排序时，游标为 base64(json(["2026-09-08T..", "<uuid>"]))。

各列表分页模块复用，避免重复实现。编码只依赖值的字符串形式（datetime 用 isoformat
的字符串、id 用字符串），解码后由各仓储按自身排序方向构造 WHERE 条件。
"""

from base64 import urlsafe_b64decode, urlsafe_b64encode
from datetime import datetime
from json import dumps as json_dumps
from json import loads as json_loads


def encode_cursor(*values: object) -> str:
    """把有序键（时间 + id 等）编码为不透明字符串。"""
    payload = json_dumps([str(v) for v in values], ensure_ascii=False)
    return urlsafe_b64encode(payload.encode("utf-8")).decode("ascii")


def decode_cursor(cursor: str) -> list[str]:
    """解码游标为原始字符串数组；游标非法时抛 ValueError。"""
    try:
        raw = urlsafe_b64decode(cursor.encode("ascii")).decode("utf-8")
        parts = json_loads(raw)
    except Exception as exc:  # base64 坏数据 / JSON 解析失败都归类为非法游标
        raise ValueError("无效的游标") from exc
    if not isinstance(parts, list):
        raise ValueError("无效的游标")
    return [str(p) for p in parts]


def decode_cursor_pair(cursor: str) -> tuple[str, str]:
    """解码两段式游标（时间 + id），字段数不符视为非法。"""
    parts = decode_cursor(cursor)
    if len(parts) != 2:
        raise ValueError("无效的游标")
    return parts[0], parts[1]


def parse_ts(value: str) -> datetime:
    """把游标里的时间字符串解析为本地 naive datetime（与库内时间语义一致）。"""
    return datetime.fromisoformat(value)
