"""对话服务：创建对话、发送消息并运行 Agent、幂等处理。

MVP 采用同步处理（发消息请求内等待模型返回并落库）。
"""

import hashlib

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.core.enums import MessageRole, VersionSource
from app.core.errors import CONVERSATION_NOT_FOUND, IDEMPOTENCY_KEY_REUSED, AppError
from app.db.models.agent import MessageCitation
from app.db.models.conversation import Conversation, Message
from app.providers.search import get_search_provider
from app.providers.search.base import SearchProviderError
from app.repositories.conversations import ConversationRepository
from app.schemas.conversation import CitationView, MessageView
from app.services.agent_service import AgentService
from app.services.project_service import ProjectService


class ConversationService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._convs = ConversationRepository(session)
        self._projects = ProjectService(session)
        self._agent = AgentService(session)

    @staticmethod
    def _fingerprint(content: str) -> str:
        """请求指纹：防止同一幂等 ID 被不同正文复用。"""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    async def create_conversation(self, user_id: str, title: str | None) -> Conversation:
        return await self._convs.create(user_id, title)

    async def get_or_404(self, user_id: str, conversation_id: str) -> Conversation:
        conversation = await self._convs.get(user_id, conversation_id)
        if conversation is None:
            raise AppError(CONVERSATION_NOT_FOUND)
        return conversation

    async def send_message(
        self, user_id: str, conversation_id: str, content: str, client_request_id: str, web_search_enabled: bool = False
    ):
        """保存用户消息并运行 Agent，返回 (user_message, assistant_message, project)。"""
        await self.get_or_404(user_id, conversation_id)
        fingerprint = self._fingerprint(content)

        # 幂等：同一对话同一 client_request_id
        existing = await self._convs.get_message_by_client_request_id(conversation_id, client_request_id)
        if existing is not None:
            if existing.request_fingerprint != fingerprint:
                raise AppError(IDEMPOTENCY_KEY_REUSED)
            # 幂等命中：返回既有用户消息、对应助手消息（若有）与当前方案
            assistant = await self._find_reply(existing)
            return existing, assistant

        user_message = await self._convs.add_message(
            conversation_id,
            MessageRole.USER,
            content,
            client_request_id=client_request_id,
            request_fingerprint=fingerprint,
            status="completed",
        )

        # 构造历史（本轮之前的所有 user/assistant 消息）
        history = await self._history(conversation_id)

        output = await self._agent.run_turn(user_id, conversation_id, content, history)

        assistant_message = await self._convs.add_message(
            conversation_id,
            MessageRole.ASSISTANT,
            output.reply,
            reply_to_message_id=user_message.id,
            status="completed",
        )

        # 若本轮修改了方案字段，则提交新版本
        patch = output.state_patch.model_dump(exclude_unset=True)
        if patch:
            await self._projects.apply_patch(
                user_id,
                conversation_id,
                patch,
                source=VersionSource.AGENT.value,
                source_message_id=assistant_message.id,
                suggested_prompt=output.suggested_prompt,
            )

        # 联网搜索：模型请求过、且用户开启联网 → 执行搜索、保存引用并把来源附到回复
        if web_search_enabled and output.search_requests:
            await self._run_search(assistant_message, output.search_requests)

        await self._convs.touch_last_message_at(conversation_id)
        project = await self._projects.get_current_brief(user_id, conversation_id)
        return user_message, assistant_message, project

    async def _run_search(self, assistant_message: Message, queries: list[str]) -> None:
        """执行搜索并保存来源引用。单条搜索失败不阻断回复，仅跳过。"""
        provider = get_search_provider()
        citations: list[MessageCitation] = []
        position = 0
        for query in queries[: settings.search_max_calls]:
            try:
                results = await provider.search(query, limit=5)
            except SearchProviderError:
                continue
            for result in results:
                citations.append(
                    MessageCitation(
                        message_id=assistant_message.id,
                        position=position,
                        title=result.title[:500],
                        url=result.url[:1000],
                        snippet=result.snippet[:2000],
                        retrieved_at=result.retrieved_at,
                    )
                )
                position += 1
        if not citations:
            return
        self._session.add_all(citations)
        await self._session.commit()
        lines = [f"{i}. {c.title}：{c.url}" for i, c in enumerate(citations, 1)]
        assistant_message.content += "\n\n【检索到的参考资料】\n" + "\n".join(lines)
        await self._session.commit()

    async def _find_reply(self, user_message: Message) -> Message | None:
        """找到某条用户消息对应的助手回复。"""
        rows = await self._convs.list_messages(user_message.conversation_id, 1000, 0)
        for row in rows:
            if row.role == MessageRole.ASSISTANT.value and row.reply_to_message_id == user_message.id:
                return row
        return None

    async def _history(self, conversation_id: str) -> list[dict[str, str]]:
        """构造发送给模型的历史消息（本轮之前的 user/assistant，按时间顺序）。"""
        rows = await self._convs.list_messages(conversation_id, 1000, 0)
        out: list[dict[str, str]] = []
        for row in rows:
            if row.role not in (MessageRole.USER.value, MessageRole.ASSISTANT.value):
                continue
            if row.content == "" or row.status not in ("completed", "failed"):
                continue
            out.append({"role": row.role, "content": row.content})
        return out

    async def list_conversations(self, user_id: str, status: str | None, limit: int, skip: int):
        return await self._convs.list_conversations(user_id, status, limit, skip)

    async def list_messages(self, user_id: str, conversation_id: str, limit: int, skip: int):
        await self.get_or_404(user_id, conversation_id)
        return await self._convs.list_messages(conversation_id, limit, skip)

    async def message_view(self, message: Message) -> MessageView:
        """组装消息视图，并填充真实结构化引用列表（来自 message_citations 表）。"""
        citations = await self._convs.list_citations(message.id)
        view = MessageView.model_validate(message)
        return view.model_copy(
            update={
                "citations": [
                    CitationView(
                        title=c.title,
                        url=c.url,
                        snippet=c.snippet,
                        published_at=c.published_at,
                        retrieved_at=c.retrieved_at,
                    )
                    for c in citations
                ]
            }
        )
