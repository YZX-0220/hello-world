"""业务常量与限制。集中定义，避免在服务层散落魔法数字。"""

from enum import IntEnum


class Limits(IntEnum):
    """分页、长度、次数等数值型限制。"""

    DEFAULT_PAGE_SIZE = 20  # 列表默认每页
    MAX_PAGE_SIZE = 100  # 列表每页上限
    CONVERSATION_TITLE_MIN = 1
    CONVERSATION_TITLE_MAX = 100
    MESSAGE_MAX_LENGTH = 20000  # 用户消息正文长度上限
    DISPLAY_NAME_MIN = 1
    DISPLAY_NAME_MAX = 40  # 视频 API 配置显示名
    EMAIL_CODE_LENGTH = 6
    EMAIL_CODE_TTL_SECONDS = 300  # 验证码有效期
    EMAIL_CODE_MAX_ATTEMPTS = 5  # 验证码最大尝试次数
    PASSWORD_MIN_LENGTH = 8
    PASSWORD_MAX_LENGTH = 128
    SEARCH_QUERY_MAX_LENGTH = 200
    SEARCH_RESULT_LIMIT = 5  # 每次搜索最多结果条数
    SEARCH_MAX_CALLS = 3  # 每轮最多搜索次数
    MAX_TOOL_CALLS = 3  # 每轮工具调用循环次数上限
    REMOTE_MODEL_ID_MAX_LENGTH = 160
    BASE_URL_MAX_LENGTH = 500


# 对话标题、版本来源等字符串常量
CONVERSATION_TITLE_DEFAULT = "新对话"

# 方案版本来源
VERSION_SOURCE_AGENT = "agent"
VERSION_SOURCE_MANUAL = "manual"
VERSION_SOURCE_SYSTEM = "system"
