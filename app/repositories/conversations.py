"""对话/消息仓储：创建、分页、幂等、所有权过滤。

所有查询同时带用户条件（跨用户访问返回不存在）。
"""

from sqlalchemy import and_, or_
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.constants import CONVERSATION_TITLE_DEFAULT
from app.core.cursor import decode_cursor_pair, parse_ts
from app.core.enums import ConversationStatus, MessageRole, VersionSource
from app.core.time import now
from app.db.models.agent import MessageCitation
from app.db.models.conversation import Conversation, ConversationContext, Message
from app.db.models.project import VideoProject, VideoProjectVersion


class ConversationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, user_id: str, title: str | None) -> Conversation:
        """创建对话，并同时创建空项目、上下文与 0 版空方案快照。"""
        conversation = Conversation(
            user_id=user_id,
            title=(title or CONVERSATION_TITLE_DEFAULT)[:100],
        )
        self._session.add(conversation)
        await self._session.commit()
        await self._session.refresh(conversation)

        project = VideoProject(
            conversation_id=conversation.id,
            user_id=user_id,
            current_spec_json="{}",
            current_spec_version=0,
        )
        ctx = ConversationContext(conversation_id=conversation.id)
        seed_version = VideoProjectVersion(
            project_id=project.id,
            version=0,
            spec_json="{}",
            source_type=VersionSource.SYSTEM.value,
        )
        self._session.add_all([project, ctx, seed_version])
        await self._session.commit()
        return conversation

    async def get(self, user_id: str, conversation_id: str) -> Conversation | None:
        stmt = select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id,
        )
        result = await self._session.exec(stmt)
        return result.first()

    async def list_conversations(self, user_id: str, status: str | None, limit: int, cursor: str | None) -> list[Conversation]:
        """按 (updated_at desc, id desc) 游标分页。

        返回不超过 limit+1 条：多出的 1 条用于判定是否还有下一页。
        游标为上一页最后一条的 (updated_at, id) 编码；无游标返回第一页。
        """
        stmt = select(Conversation).where(Conversation.user_id == user_id)
        if status:
            stmt = stmt.where(Conversation.status == status)
        else:
            stmt = stmt.where(Conversation.status != ConversationStatus.DELETED.value)
        if cursor is not None:
            t, cid = decode_cursor_pair(cursor)
            ts = parse_ts(t)
            stmt = stmt.where(
                or_(
                    Conversation.updated_at < ts,  # type: ignore[arg-type]
                    and_(Conversation.updated_at == ts, Conversation.id < cid),  # type: ignore[arg-type]
                )
            )
        stmt = stmt.order_by(Conversation.updated_at.desc(), Conversation.id.desc()).limit(limit + 1)  # type: ignore[attr-defined]
        result = await self._session.exec(stmt)
        return list(result.all())

    async def patch(self, user_id: str, conversation_id: str, title: str | None, status: str | None) -> Conversation | None:
        conversation = await self.get(user_id, conversation_id)
        if conversation is None:
            return None
        if title is not None:
            conversation.title = title[:100]
        if status is not None:
            conversation.status = status
        conversation.updated_at = now()
        await self._session.commit()
        await self._session.refresh(conversation)
        return conversation

    async def soft_delete(self, user_id: str, conversation_id: str) -> Conversation | None:
        conversation = await self.get(user_id, conversation_id)
        if conversation is None:
            return None
        conversation.status = ConversationStatus.DELETED.value
        conversation.deleted_at = now()
        conversation.updated_at = now()
        await self._session.commit()
        return conversation

    # ---- 消息 ----
    async def add_message(self, conversation_id, role: MessageRole, content: str, **kwargs) -> Message:
        """创建消息。role 用字符串值，kwargs 可传 client_request_id 等。"""
        message = Message(
            conversation_id=conversation_id,
            role=role.value if isinstance(role, MessageRole) else role,
            content=content,
            **kwargs,
        )
        self._session.add(message)
        await self._session.commit()
        await self._session.refresh(message)
        return message

    async def get_message_by_client_request_id(self, conversation_id: str, client_request_id: str) -> Message | None:
        stmt = select(Message).where(
            Message.conversation_id == conversation_id,
            Message.client_request_id == client_request_id,
        )
        result = await self._session.exec(stmt)
        return result.first()

    async def list_messages(self, conversation_id: str, limit: int, cursor: str | None) -> list[Message]:
        """按 (created_at asc, id asc) 游标分页。游标为上一页最后一条的 (created_at, id)。"""
        stmt = select(Message).where(Message.conversation_id == conversation_id)
        if cursor is not None:
            t, cid = decode_cursor_pair(cursor)
            ts = parse_ts(t)
            stmt = stmt.where(
                or_(
                    Message.created_at > ts,  # type: ignore[arg-type]
                    and_(Message.created_at == ts, Message.id > cid),  # type: ignore[arg-type]
                )
            )
        stmt = (
            stmt.order_by(Message.created_at.asc(), Message.id.asc())  # type: ignore[attr-defined]
            .limit(limit + 1)
        )
        result = await self._session.exec(stmt)
        return list(result.all())

    async def list_citations(self, message_id: str) -> list[MessageCitation]:
        stmt = (
            select(MessageCitation)
            .where(MessageCitation.message_id == message_id)
            .order_by(MessageCitation.position.asc())  # type: ignore[attr-defined]
        )
        result = await self._session.exec(stmt)
        return list(result.all())

    async def update_message(self, message: Message) -> Message:
        self._session.add(message)
        await self._session.commit()
        await self._session.refresh(message)
        return message

    async def touch_last_message_at(self, conversation_id: str) -> None:
        conversation = await self._session.get(Conversation, conversation_id)
        if conversation is not None:
            conversation.last_message_at = now()
            conversation.updated_at = now()
            await self._session.commit()
