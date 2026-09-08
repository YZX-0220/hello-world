"""公共枚举。对应《接口说明(初版)》第 2 节。

全部继承 str 与 Enum，便于直接作为数据库字符字段值（存字符串）。
枚举类之间保持独立，避免跨模块循环导入。
"""

from enum import Enum


class _StrEnum(str, Enum):
    """带中文说明的字符串枚举基类。value 为落库/传输值。"""

    def __str__(self) -> str:  # 便于日志与展示
        return self.value


class EmailCodePurpose(_StrEnum):
    REGISTER = "register"  # 注册账号
    LOGIN = "login"  # 邮箱验证码登录
    RESET_PASSWORD = "reset_password"  # 重置密码


class UserStatus(_StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"


class ConversationStatus(_StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"


class MessageRole(_StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"
    SYSTEM = "system"


class MessageStatus(_StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


class AgentRunStatus(_StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class VideoMode(_StrEnum):
    TEXT_TO_VIDEO = "text_to_video"
    FIRST_FRAME_TO_VIDEO = "first_frame_to_video"
    FIRST_LAST_FRAME_TO_VIDEO = "first_last_frame_to_video"
    REFERENCE_IMAGE_TO_VIDEO = "reference_image_to_video"
    VIDEO_TO_VIDEO = "video_to_video"
    VIDEO_EXTEND = "video_extend"
    AUDIO_OR_PERFORMANCE_TO_VIDEO = "audio_or_performance_to_video"


class ApiSourceType(_StrEnum):
    OFFICIAL = "official"
    RELAY = "relay"


class CapabilitySource(_StrEnum):
    REGISTRY = "registry"  # 后端已登记并核验
    USER_DECLARED = "user_declared"  # 用户自行声明，尚未证明
    RUNTIME_CONFIRMED = "runtime_confirmed"  # 已通过真实运行确认


class VerificationStatus(_StrEnum):
    UNVERIFIED = "unverified"  # 没有可靠的免费检测方式
    VERIFIED = "verified"
    INVALID = "invalid"


class AssetKind(_StrEnum):
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"


class AssetPurpose(_StrEnum):
    FIRST_FRAME = "first_frame"
    LAST_FRAME = "last_frame"
    REFERENCE = "reference"
    SOURCE_VIDEO = "source_video"
    AUDIO = "audio"
    RESULT = "result"


class AssetStatus(_StrEnum):
    UPLOADING = "uploading"
    READY = "ready"
    QUARANTINED = "quarantined"
    DELETED = "deleted"


class VideoJobStatus(_StrEnum):
    CREATED = "created"
    SUBMITTING = "submitting"
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DownloadStatus(_StrEnum):
    NOT_STARTED = "not_started"
    PENDING = "pending"
    DOWNLOADING = "downloading"
    STORED = "stored"
    DIRECT = "direct"  # 双轨：下载失败/服务器不支持，回退为厂商直链交付
    FAILED = "failed"


class VersionSource(_StrEnum):
    AGENT = "agent"  # 文本 AI 修改
    MANUAL = "manual"  # 用户手动修改
    SYSTEM = "system"  # 系统创建


class ApiConfigStatus(_StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"
    DELETED = "deleted"


class JobEventType(_StrEnum):
    SUBMIT = "submit"
    POLL = "poll"
    STATUS_CHANGE = "status_change"
    DOWNLOAD = "download"
    CANCEL = "cancel"


class ToolExecutionStatus(_StrEnum):
    REQUESTED = "requested"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REJECTED = "rejected"
