"""对话、消息与长对话摘要表。字段以《实施计划》5.5/5.6/5.7 为准。"""

from datetime import datetime

from sqlalchemy import Column, Index, Text, UniqueConstraint
from sqlmodel import Field, SQLModel

from app.core.enums import ConversationStatus, MessageStatus
from app.core.ids import new_id
from app.core.time import now


class Conversation(SQLModel, table=True):
    __tablename__ = "conversations"

    id: str = Field(default_factory=new_id, primary_key=True)
    user_id: str = Field(foreign_key="users.id", index=True, ondelete="CASCADE")
    title: str = Field(default="新对话", max_length=100)
    status: str = Field(default=ConversationStatus.ACTIVE.value, max_length=20)
    last_message_at: datetime | None = Field(default=None)
    version: int = Field(default=0)  # 乐观锁
    created_at: datetime = Field(default_factory=now)
    updated_at: datetime = Field(default_factory=now)
    deleted_at: datetime | None = Field(default=None)

    __table_args__ = (
        Index("ix_conversations_user_status_updated", "user_id", "status", "updated_at", "id"),
    )


class Message(SQLModel, table=True):
    __tablename__ = "messages"

    id: str = Field(default_factory=new_id, primary_key=True)
    conversation_id: str = Field(foreign_key="conversations.id", index=True, ondelete="CASCADE")
    role: str = Field(max_length=20)  # MessageRole.value
    # Pending Assistant 可为空字符串，用户消息与完成消息必须非空（服务层校验）
    content: str = Field(default="", max_length=100000)
    structured_json: str | None = Field(default=None)  # Pydantic 校验后序列化
    reply_to_message_id: str | None = Field(default=None, foreign_key="messages.id")
    client_request_id: str | None = Field(default=None, max_length=64)  # 用户消息幂等 ID
    request_fingerprint: str | None = Field(default=None, max_length=128)  # 防同 ID 被不同正文复用
    status: str = Field(default=MessageStatus.PENDING.value, max_length=20)
    model_name: str | None = Field(default=None, max_length=200)
    input_tokens: int | None = Field(default=None)
    output_tokens: int | None = Field(default=None)
    error_code: str | None = Field(default=None, max_length=64)
    created_at: datetime = Field(default_factory=now)

    __table_args__ = (
        UniqueConstraint("conversation_id", "client_request_id", name="uq_messages_conv_client_request"),
        Index("ix_messages_conv_created", "conversation_id", "created_at", "id"),
    )


class ConversationContext(SQLModel, table=True):
    __tablename__ = "conversation_contexts"

    conversation_id: str = Field(foreign_key="conversations.id", primary_key=True, ondelete="CASCADE")
    summary_text: str = Field(default="")  # 仅摘要，不保存项目状态
    summary_through_message_id: str | None = Field(default=None)
    summary_model: str | None = Field(default=None, max_length=200)
    summary_prompt_version: str | None = Field(default=None, max_length=64)
    # 联网搜索的详细依据累积（只供后续轮次后端上下文，不进入任何前端响应字段，MessageView 不包含它）
    retrieval_notes: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    updated_at: datetime = Field(default_factory=now)
