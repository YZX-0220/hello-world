"""ID 工具。主键统一采用 UUID4 字符串（实施计划 5.2 节）。"""

from uuid import uuid4


def new_id() -> str:
    """生成一个新的 UUID4 字符串主键。"""
    return str(uuid4())
