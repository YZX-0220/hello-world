"""ID 工具。主键统一采用 UUID4 字符串（实施计划 5.2 节）。"""

from uuid import uuid4


def new_id() -> str:
    """生成一个新的 UUID4 字符串主键。"""
    return str(uuid4())


def is_uuid4(value: str) -> bool:
    """判断字符串是否为合法 UUID4（十六进制、连字符分隔）。"""
    try:
        from uuid import UUID

        UUID(value, version=4)
        return True
    except (TypeError, ValueError):
        return False
