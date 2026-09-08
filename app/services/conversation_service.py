"""对话服务：创建对话、发送消息并运行 Agent、幂等处理。

MVP 采用同步处理（发消息请求内等待模型返回并落库）。
"""

import hashlib
import json

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.core.cursor import encode_cursor
from app.core.enums import MessageRole, ToolExecutionStatus, VersionSource
from app.core.errors import CONVERSATION_NOT_FOUND, IDEMPOTENCY_KEY_REUSED, AppError
from app.core.time import now
from app.db.models.agent import MessageCitation, ToolExecution
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

        output = await self._agent.run_turn(user_id, conversation_id, user_message.id, content, history)
        agent_run_id = output.agent_run_id

        assistant_message = await self._convs.add_message(
            conversation_id,
            MessageRole.ASSISTANT,
            output.reply,
            reply_to_message_id=user_message.id,
            status="completed",
        )

        # 把本轮 assistant 消息 id 关联回 AgentRun
        if agent_run_id is not None:
            await self._agent.bind_assistant_message(agent_run_id, assistant_message.id)

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

        # 联网搜索：模型请求过、且用户开启联网 → 记录工具调用、执行搜索、保存引用，
        # 并把检索结果回流给模型二次生成最终回复（真正的 function-calling）。
        if web_search_enabled and output.search_requests:
            await self._run_search(
                assistant_message,
                output.search_requests,
                agent_run_id,
                user_id=user_id,
                conversation_id=conversation_id,
                history=history,
                user_content=content,
            )

        await self._convs.touch_last_message_at(conversation_id)
        project = await self._projects.get_current_brief(user_id, conversation_id)
        return user_message, assistant_message, project

    async def _run_search(
        self,
        assistant_message: Message,
        queries: list[str],
        agent_run_id: str | None,
        *,
        user_id: str,
        conversation_id: str,
        history: list[dict[str, str]],
        user_content: str,
    ) -> None:
        """执行搜索、保存来源引用，并把检索结果回流给模型二次生成最终回复。

        每个查询记录一条 ToolExecution（web_search），并把该轮每个来源 MessageCitation
        的 tool_execution_id 指向对应工具调用。单条搜索失败不阻断回复，仅标记工具失败并跳过。
        agent_run_id 为 None 时不落工具调用（保留原有仅存引用的行为）。

        若本轮至少拿到一条检索结果，就调用 AgentService.refine_with_search 让模型基于检索结果
        重写最终回复并替换 assistant_message 正文；若二次生成失败或没有结果（无检索文本），
        则保留初版 reply 作为正文——不丢消息、不报错。旧实现里的"【检索到的参考资料】"固定
        文案追加被移除，来源依旧结构化落库到 message_citations 供前端展示。
        """
        provider = get_search_provider()
        citations: list[MessageCitation] = []
        tools: list[ToolExecution] = []
        result_blocks: list[str] = []  # 每个查询一组可读检索结果文本（供第二阶段喂给模型）
        position = 0
        sequence = 0
        for query in queries[: settings.search_max_calls]:
            tool = None
            if agent_run_id is not None:
                tool = ToolExecution(
                    agent_run_id=agent_run_id,
                    sequence=sequence,
                    tool_name="web_search",
                    input_json=json.dumps({"query": query}, ensure_ascii=False),
                    status=ToolExecutionStatus.REQUESTED.value,
                    started_at=now(),
                )
                sequence += 1
            try:
                results = await provider.search(query, limit=5)
            except SearchProviderError as exc:
                if tool is not None:
                    tool.status = ToolExecutionStatus.FAILED.value
                    tool.error_code = exc.code
                    tool.completed_at = now()
                    tool.result_json = json.dumps({"error": exc.message[:2000]}, ensure_ascii=False)
                    tools.append(tool)
                continue
            if tool is not None:
                tool.status = ToolExecutionStatus.SUCCEEDED.value
                tool.completed_at = now()
                tool.result_json = json.dumps(
                    {
                        "query": query,
                        "results": [
                            {"title": r.title[:500], "url": r.url[:1000], "snippet": r.snippet[:2000]}
                            for r in results
                        ],
                    },
                    ensure_ascii=False,
                )
                tools.append(tool)
            # 组装该查询的可读结果文本段（供第二阶段回流给模型）
            lines = [f"查询：{query}"]
            for idx, r in enumerate(results, 1):
                lines.append(f"{idx}. {r.title}")
                lines.append(f"   链接：{r.url}")
                lines.append(f"   摘要：{r.snippet[:400]}")
            result_blocks.append("\n".join(lines))
            for result in results:
                citations.append(
                    MessageCitation(
                        message_id=assistant_message.id,
                        tool_execution_id=tool.id if tool is not None else None,
                        position=position,
                        title=result.title[:500],
                        url=result.url[:1000],
                        snippet=result.snippet[:2000],
                        retrieved_at=result.retrieved_at,
                    )
                )
                position += 1
        if not tools and not citations:
            return
        if tools:
            self._session.add_all(tools)
        if citations:
            self._session.add_all(citations)
        await self._session.commit()
        if tools and agent_run_id is not None:
            await self._agent.set_tool_call_count(agent_run_id, len(tools))
        search_results_text = "\n\n".join(result_blocks)
        if search_results_text.strip():
            final_reply = await self._agent.refine_with_search(
                user_id,
                conversation_id,
                history,
                user_content,
                search_results_text,
            )
            if final_reply:
                assistant_message.content = final_reply
                await self._session.commit()

    async def _find_reply(self, user_message: Message) -> Message | None:
        """找到某条用户消息对应的助手回复。"""
        rows = await self._convs.list_messages(user_message.conversation_id, 1000, None)
        for row in rows:
            if row.role == MessageRole.ASSISTANT.value and row.reply_to_message_id == user_message.id:
                return row
        return None

    async def _history(self, conversation_id: str) -> list[dict[str, str]]:
        """构造发送给模型的历史消息（本轮之前的 user/assistant，按时间顺序）。"""
        rows = await self._convs.list_messages(conversation_id, 1000, None)
        out: list[dict[str, str]] = []
        for row in rows:
            if row.role not in (MessageRole.USER.value, MessageRole.ASSISTANT.value):
                continue
            if row.content == "" or row.status not in ("completed", "failed"):
                continue
            out.append({"role": row.role, "content": row.content})
        return out

    async def list_conversations(self, user_id: str, status: str | None, limit: int, cursor: str | None):
        """返回 (page_rows, next_cursor)。page_rows 长度不超过 limit；next_cursor=None 表示已到末尾。"""
        rows = await self._convs.list_conversations(user_id, status, limit, cursor)
        has_more = len(rows) > limit
        page = rows[:limit]
        next_cursor = encode_cursor(page[-1].updated_at, page[-1].id) if page and has_more else None
        return page, next_cursor

    async def list_messages(self, user_id: str, conversation_id: str, limit: int, cursor: str | None):
        await self.get_or_404(user_id, conversation_id)
        rows = await self._convs.list_messages(conversation_id, limit, cursor)
        has_more = len(rows) > limit
        page = rows[:limit]
        next_cursor = encode_cursor(page[-1].created_at, page[-1].id) if page and has_more else None
        return page, next_cursor

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
