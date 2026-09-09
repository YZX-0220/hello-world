"""对话服务：创建对话、发送消息并运行 Agent、幂等处理。

MVP 采用同步处理（发消息请求内等待模型返回并落库）。
"""

import hashlib
import json
import logging

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.core.cursor import encode_cursor
from app.core.enums import MessageRole, ToolExecutionStatus, VersionSource
from app.core.errors import CONVERSATION_NOT_FOUND, IDEMPOTENCY_KEY_REUSED, AppError
from app.core.time import now
from app.db.models.agent import MessageCitation, ToolExecution
from app.db.models.conversation import Conversation, ConversationContext, Message
from app.providers.search import get_search_provider
from app.providers.search.base import SearchProviderError
from app.repositories.conversations import ConversationRepository
from app.schemas.conversation import CitationView, MessageView
from app.services.agent_service import AgentService
from app.services.context_builder import build_summary_prompt
from app.services.project_service import ProjectService

logger = logging.getLogger(__name__)


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
        """保存用户消息并运行 Agent，返回 (user_message, assistant_message, project)。

        幂等命中时返回既有用户消息 + 对应助手消息（历史契约）。实际执行委托给
        _iter_message_pipeline，与流式端点复用同一条流水线，保证落库一致。
        """
        result: dict = {}
        async for _event in self._iter_message_pipeline(
            user_id=user_id,
            conversation_id=conversation_id,
            content=content,
            client_request_id=client_request_id,
            web_search_enabled=web_search_enabled,
            result=result,
        ):
            pass
        if result.get("replayed"):
            return result["user_message"], result["assistant_message"], None
        return result["user_message"], result["assistant_message"], result["project"]

    async def _iter_message_pipeline(
        self,
        *,
        user_id: str,
        conversation_id: str,
        content: str,
        client_request_id: str,
        web_search_enabled: bool,
        result: dict,
    ):
        """逐步执行发送流水线，yield (event_type, payload)。

        - 每条事件在对应产物可用后即刻产出，方便流式端逐段推送；
        - result 字典在生成器结束时携带最终状态：user_message / assistant_message /
          project / replayed，供同步端点换算返回值；
        - 幂等命中直接回放既有结果，不重复创建用户消息 / AgentRun。
        """
        # ---- 权限与幂等前置 ----
        await self.get_or_404(user_id, conversation_id)
        fingerprint = self._fingerprint(content)

        existing = await self._convs.get_message_by_client_request_id(conversation_id, client_request_id)
        if existing is not None:
            if existing.request_fingerprint != fingerprint:
                raise AppError(IDEMPOTENCY_KEY_REUSED)
            # 幂等命中：返回既有用户消息、对应助手消息（若有）与当前方案
            assistant = await self._find_reply(existing)
            result.update(user_message=existing, assistant_message=assistant, replayed=True)
            yield (
                "run_started",
                {"conversation_id": conversation_id, "client_request_id": client_request_id, "replayed": True},
            )
            yield (
                "run_completed",
                {
                    "user_message_id": existing.id,
                    "assistant_message_id": assistant.id if assistant is not None else None,
                    "replayed": True,
                },
            )
            return

        # ---- 新消息流程：创建用户消息 ----
        user_message = await self._convs.add_message(
            conversation_id,
            MessageRole.USER,
            content,
            client_request_id=client_request_id,
            request_fingerprint=fingerprint,
            status="completed",
        )
        result.update(user_message=user_message, assistant_message=None, replayed=False)
        yield (
            "run_started",
            {"conversation_id": conversation_id, "client_request_id": client_request_id, "replayed": False},
        )

        # 构造历史（本轮之前的所有 user/assistant 消息）
        history = await self._history(conversation_id)

        # 长对话摘要：读取当前摘要状态，供本轮构造上下文时压缩旧历史（尚未生成摘要时不会压缩）
        ctx = await self._convs.get_context(conversation_id)
        summary_text = ctx.summary_text if ctx is not None else ""
        summary_through_message_id = ctx.summary_through_message_id if ctx is not None else None
        # 联网搜索的累积依据：非空时注入后续轮次上下文
        retrieval_notes = (ctx.retrieval_notes if ctx is not None else "") or ""

        output = await self._agent.run_turn(
            user_id,
            conversation_id,
            user_message.id,
            content,
            history,
            summary_text=summary_text,
            summary_through_message_id=summary_through_message_id,
            retrieval_notes=retrieval_notes,
        )
        agent_run_id = output.agent_run_id

        assistant_message = await self._convs.add_message(
            conversation_id,
            MessageRole.ASSISTANT,
            output.reply,
            reply_to_message_id=user_message.id,
            status="completed",
        )
        result["assistant_message"] = assistant_message

        # 把本轮 assistant 消息 id 关联回 AgentRun
        if agent_run_id is not None:
            await self._agent.bind_assistant_message(agent_run_id, assistant_message.id)

        # 文本回复已生成（非逐 token 流式，一次性推全量回复）
        yield (
            "text_delta",
            {
                "content": output.reply,
                "user_message_id": user_message.id,
                "assistant_message_id": assistant_message.id,
                "agent_run_id": agent_run_id,
            },
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
            current_version = await self._projects.get_current_spec_version(user_id, conversation_id)
            yield ("patch_applied", {"version": current_version})

        # 联网搜索：模型请求过、且用户开启联网 → 记录工具调用、执行搜索、保存引用，
        # 并把检索结果回流给模型二次生成最终回复（真正的 function-calling）。
        if web_search_enabled and output.search_requests:
            citation_count = await self._run_search(
                assistant_message,
                output.search_requests,
                agent_run_id,
                user_id=user_id,
                conversation_id=conversation_id,
                history=history,
                user_content=content,
                summary_text=summary_text,
                summary_through_message_id=summary_through_message_id,
            )
            yield ("searched", {"citations": citation_count, "query_count": len(output.search_requests)})

        await self._convs.touch_last_message_at(conversation_id)

        # 长对话摘要：本轮结束时检查是否把较早历史压缩成摘要（不足阈值时不触发、不额外开销）
        await self._maybe_summarize(conversation_id)

        project = await self._projects.get_current_brief(user_id, conversation_id)
        result["project"] = project
        final_version = await self._projects.get_current_spec_version(user_id, conversation_id)
        yield (
            "run_completed",
            {
                "user_message_id": user_message.id,
                "assistant_message_id": assistant_message.id,
                "agent_run_id": agent_run_id,
                "project_version": final_version,
                "content": assistant_message.content,
                "project": project,
            },
        )

    async def stream_message_events(
        self, user_id: str, conversation_id: str, content: str, client_request_id: str, web_search_enabled: bool = False
    ):
        """事件流式发送消息：逐阶段 yield (event_type, payload)。

        落库与 send_message 完全一致（复用同一流水线）。任何流水线错误在方法内部转成
        ("error", payload) 事件，不向调用方抛异常，保证 SSE 流能干净结束。
        """
        try:
            async for event in self._iter_message_pipeline(
                user_id=user_id,
                conversation_id=conversation_id,
                content=content,
                client_request_id=client_request_id,
                web_search_enabled=web_search_enabled,
                result={},
            ):
                yield event
        except AppError as exc:
            yield ("error", {"code": exc.code, "message": exc.message, "details": exc.details})
        except Exception:
            logger.exception("发送消息流式事件时发生未预期错误")
            yield ("error", {"code": "INTERNAL_ERROR", "message": "服务器内部错误"})

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
        summary_text: str = "",
        summary_through_message_id: str | None = None,
    ) -> int:
        """执行搜索、保存来源引用，并把检索结果回流给模型二次生成最终回复。

        返回本轮结构化落库的引用总数目（用于 SSE searched 事件）。同步端点忽略该返回值。

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
            return 0
        if tools:
            self._session.add_all(tools)
            # 先落库工具执行记录，确保引用其 id 的引用外键有效（避免 SQLite 批量插入顺序导致 FK 失败）
            await self._session.flush()
        if citations:
            self._session.add_all(citations)
        await self._session.commit()
        if tools and agent_run_id is not None:
            await self._agent.set_tool_call_count(agent_run_id, len(tools))
        search_results_text = "\n\n".join(result_blocks)
        if search_results_text.strip():
            # 把本轮检索的详细依据追加到该对话的持久上下文，供后续多轮复用
            await self._append_retrieval_notes(conversation_id, result_blocks)
            final_reply = await self._agent.refine_with_search(
                user_id,
                conversation_id,
                history,
                user_content,
                search_results_text,
                summary_text=summary_text,
                summary_through_message_id=summary_through_message_id,
            )
            if final_reply:
                assistant_message.content = final_reply
                await self._session.commit()
        return len(citations)

    async def _append_retrieval_notes(self, conversation_id: str, result_blocks: list[str]) -> None:
        """把本轮联网搜索的详细依据追加到该对话的持久上下文（ConversationContext.retrieval_notes）。

        详情只用于后端后续轮次上下文（run_turn 注入），不进入任何前端响应字段（MessageView 不含它）。
        去重规则：某条结果段的"查询：{query}"若已存在于既有 retrieval_notes（或本轮前面已追加过），
        则跳过，避免同一查询被重复追加。该对话上下文尚未创建（retrieval_notes 为 None）时直接创建。
        """
        if not result_blocks:
            return
        ctx = await self._convs.get_context(conversation_id)
        if ctx is None:
            ctx = ConversationContext(conversation_id=conversation_id)
        existing = ctx.retrieval_notes or ""
        seen: set[str] = set()
        append_blocks: list[str] = []
        for block in result_blocks:
            query_line = block.split("\n", 1)[0]  # "查询：{query}"
            if query_line in existing or query_line in seen:
                continue
            seen.add(query_line)
            append_blocks.append(block)
        if not append_blocks:
            return
        joined = "\n\n".join(append_blocks)
        ctx.retrieval_notes = f"{existing}\n\n{joined}".strip() if existing else joined
        ctx.updated_at = now()
        self._session.add(ctx)
        await self._session.commit()

    async def _find_reply(self, user_message: Message) -> Message | None:
        """找到某条用户消息对应的助手回复。"""
        rows = await self._convs.list_messages(user_message.conversation_id, 1000, None)
        for row in rows:
            if row.role == MessageRole.ASSISTANT.value and row.reply_to_message_id == user_message.id:
                return row
        return None

    async def _history(self, conversation_id: str) -> list[dict[str, str]]:
        """构造发送给模型的历史消息（本轮之前的 user/assistant，按时间顺序）。

        每个元素带 "id"，供 build_context 在存在摘要时按 summary_through_message_id 匹配压缩。
        """
        rows = await self._convs.list_messages(conversation_id, 1000, None)
        out: list[dict[str, str]] = []
        for row in rows:
            if row.role not in (MessageRole.USER.value, MessageRole.ASSISTANT.value):
                continue
            if row.content == "" or row.status not in ("completed", "failed"):
                continue
            out.append({"id": row.id, "role": row.role, "content": row.content})
        return out

    async def _maybe_summarize(self, conversation_id: str) -> None:
        """当消息数超过阈值且仍有未摘要历史时，把较早的历史交给文本模型生成摘要并落库。

        触发条件（缺一不可，any 不满足则直接返回，不做任何事）：
        1. 当前 user/assistant 消息总数 > settings.history_summary_threshold；
        2. 距上次摘要边界（summary_through_message_id）之后还有至少一条可摘要的新消息。
        摘要生成失败（如 Provider 超时）静默跳过，不阻塞本轮聊天，下一轮再试。
        """
        messages = await self._convs.list_context_messages(conversation_id)
        total = len(messages)
        if total <= settings.history_summary_threshold:
            return

        ctx = await self._convs.get_context(conversation_id)
        boundary_idx = -1
        if ctx is not None and ctx.summary_through_message_id:
            for i, m in enumerate(messages):
                if m.id == ctx.summary_through_message_id:
                    boundary_idx = i
                    break

        # 保留最近 threshold 条不摘要，把更早的压缩进摘要；target_idx 为最后一条纳入摘要的下标
        target_idx = total - settings.history_summary_threshold - 1
        if target_idx <= boundary_idx:
            return  # 边界后无新增可摘要消息

        to_summarize = [{"role": row.role, "content": row.content} for row in messages[boundary_idx + 1 : target_idx + 1]]
        prev_summary = (ctx.summary_text if ctx is not None else "") or ""
        summary = await self._agent.summarize_history(build_summary_prompt(to_summarize, prev_summary=prev_summary))
        if not summary:
            return  # 生成失败：静默跳过，不阻塞聊天

        if ctx is None:
            ctx = ConversationContext(conversation_id=conversation_id)
        ctx.summary_text = summary
        ctx.summary_through_message_id = messages[target_idx].id
        ctx.summary_model = self._agent.provider_code
        ctx.summary_prompt_version = "v1"
        ctx.updated_at = now()
        self._session.add(ctx)
        await self._session.commit()

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
