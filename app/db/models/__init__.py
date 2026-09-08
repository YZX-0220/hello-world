"""所有数据表模型在此集中导入，确保 SQLModel.metadata 发现全部表（Alembic autogenerate 依赖）。"""

from app.db.models.agent import AgentRun, MessageCitation, ToolExecution
from app.db.models.asset import Asset
from app.db.models.audit import AuditEvent
from app.db.models.conversation import Conversation, ConversationContext, Message
from app.db.models.project import VideoProject, VideoProjectVersion
from app.db.models.user import User, UserSession
from app.db.models.video_api_config import VideoApiConfig, VideoApiConfigRevision
from app.db.models.video_job import VideoJob, VideoJobAsset, VideoJobEvent

__all__ = [
    "AgentRun",
    "Asset",
    "AuditEvent",
    "Conversation",
    "ConversationContext",
    "Message",
    "MessageCitation",
    "ToolExecution",
    "User",
    "UserSession",
    "VideoApiConfig",
    "VideoApiConfigRevision",
    "VideoJob",
    "VideoJobAsset",
    "VideoJobEvent",
    "VideoProject",
    "VideoProjectVersion",
]
