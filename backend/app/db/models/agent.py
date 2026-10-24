"""Agent 执行、工具调用与引用表。字段以《实施计划》5.8/5.9/5.10 为准。"""

from datetime import datetime

from sqlalchemy import Index, UniqueConstraint, text
from sqlmodel import Field, SQLModel

from app.core.enums import AgentRunStatus, ToolExecutionStatus
from app.core.ids import new_id
from app.core.time import now


class AgentRun(SQLModel, table=True):
    __tablename__ = "agent_runs"

    id: str = Field(default_factory=new_id, primary_key=True)
    user_id: str = Field(foreign_key="users.id", index=True, ondelete="CASCADE")
    conversation_id: str = Field(foreign_key="conversations.id", index=True, ondelete="CASCADE")
    user_message_id: str = Field(foreign_key="messages.id", unique=True, ondelete="CASCADE")
    assistant_message_id: str | None = Field(default=None, foreign_key="messages.id")
    base_spec_version: int = Field(default=0)  # 调用开始时的方案版本
    status: str = Field(default=AgentRunStatus.PENDING.value, max_length=20)
    provider_code: str | None = Field(default=None, max_length=64)
    model_name: str | None = Field(default=None, max_length=200)
    prompt_version: str | None = Field(default=None, max_length=64)
    attempt_count: int = Field(default=0)
    tool_call_count: int = Field(default=0)  # 本轮工具调用次数，上限由服务层控制
    provider_request_id: str | None = Field(default=None, max_length=200)
    input_tokens: int | None = Field(default=None)
    output_tokens: int | None = Field(default=None)
    error_code: str | None = Field(default=None, max_length=64)
    error_message: str | None = Field(default=None, max_length=2000)  # 脱敏并截断
    started_at: datetime | None = Field(default=None)
    completed_at: datetime | None = Field(default=None)
    created_at: datetime = Field(default_factory=now)

    __table_args__ = (
        # 同一对话同一时间只允许 1 个 pending/running Run（SQLite 部分唯一索引）
        Index(
            "uq_agent_runs_one_active_per_conversation",
            "conversation_id",
            unique=True,
            sqlite_where=text("status IN ('pending', 'running')"),
        ),
    )


class ToolExecution(SQLModel, table=True):
    __tablename__ = "tool_executions"

    id: str = Field(default_factory=new_id, primary_key=True)
    agent_run_id: str = Field(foreign_key="agent_runs.id", index=True, ondelete="CASCADE")
    sequence: int = Field()  # 本轮顺序
    tool_name: str = Field(max_length=64)  # 首期仅 web_search
    input_json: str = Field(default="{}")  # 已校验输入
    result_json: str | None = Field(default=None)  # 截断后的安全结果
    status: str = Field(default=ToolExecutionStatus.REQUESTED.value, max_length=20)
    error_code: str | None = Field(default=None, max_length=64)
    started_at: datetime | None = Field(default=None)
    completed_at: datetime | None = Field(default=None)

    __table_args__ = (
        UniqueConstraint("agent_run_id", "sequence", name="uq_tool_executions_run_sequence"),
    )


class MessageCitation(SQLModel, table=True):
    __tablename__ = "message_citations"

    id: str = Field(default_factory=new_id, primary_key=True)
    message_id: str = Field(foreign_key="messages.id", index=True, ondelete="CASCADE")
    tool_execution_id: str | None = Field(default=None, foreign_key="tool_executions.id")
    position: int = Field()  # 展示顺序
    title: str = Field(default="", max_length=500)  # 截断
    url: str = Field(max_length=1000)  # HTTP(S)
    snippet: str = Field(default="", max_length=2000)  # 截断
    published_at: datetime | None = Field(default=None)
    retrieved_at: datetime = Field(default_factory=now)
