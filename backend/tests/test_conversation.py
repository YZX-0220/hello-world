"""对话与消息链路测试：注册 → 建对话 → 发消息（Fake 模型）→ 读消息/项目。"""

import json
import uuid
from datetime import timedelta

import httpx
from app.core.enums import MessageRole, MessageStatus
from app.core.ids import new_id
from app.core.time import now
from app.db.models.conversation import Message
from app.providers.email.fake import fake_instance
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession

EMAIL = "chat@test.com"
PASSWORD = "password123"
ORIGIN = "http://127.0.0.1:5173"


async def _register(client: httpx.AsyncClient) -> None:
    await client.post("/api/v1/auth/email-codes", json={"email": EMAIL, "purpose": "register"})
    code = fake_instance.sent[-1]["code"]
    resp = await client.post(
        "/api/v1/auth/register", json={"email": EMAIL, "code": code, "password": PASSWORD}
    )
    assert resp.status_code == 201


def _csrf_headers(client: httpx.AsyncClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies.get("hw_csrf", ""), "Origin": ORIGIN}


def _parse_sse(text: str) -> list[dict[str, str]]:
    """把 SSE 响应体解析为 [{event, data}, ...]，data 为 JSON 原文（供下断言 json.loads）。"""
    events: list[dict[str, str]] = []
    for block in text.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        item: dict[str, str] = {}
        for line in block.split("\n"):
            key, sep, value = line.partition(":")
            if not sep:
                continue
            value = value[1:] if value.startswith(" ") else value
            if key == "event":
                item["event"] = value
            elif key == "data":
                item["data"] = value
        if item:
            events.append(item)
    return events


async def _read_sse(client: httpx.AsyncClient, method: str, url: str, json: dict, headers: dict) -> str:
    """用 httpx stream 方式读取 SSE 响应体并返回全文。"""
    body = b""
    async with client.stream(method, url, json=json, headers=headers) as resp:
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        async for chunk in resp.aiter_bytes():
            body += chunk
    return body.decode("utf-8")


async def test_create_conversation_and_send_message(client: httpx.AsyncClient) -> None:
    await _register(client)

    # 创建对话（登录后写接口需 CSRF）
    conv = await client.post("/api/v1/conversations", json={"title": "雨夜古城宣传片"}, headers=_csrf_headers(client))
    assert conv.status_code == 201
    conversation_id = conv.json()["conversation"]["id"]

    # 发送消息（Fake 模型返回结构化 state_patch：subject=content）
    content = "拍摄雨夜中的古城门，电影感"
    msg = await client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"content": content, "client_request_id": str(uuid.uuid4())},
        headers=_csrf_headers(client),
    )
    assert msg.status_code == 201
    body = msg.json()
    assert body["run_status"] == "succeeded"
    assert body["assistant_message"]["content"] != ""
    assert body["project"]["current_spec"]["subject"] == content

    # 消息列表含两条（user + assistant）
    listed = await client.get(f"/api/v1/conversations/{conversation_id}/messages")
    assert listed.status_code == 200
    assert len(listed.json()["items"]) == 2

    # 当前项目视图可读
    proj = await client.get(f"/api/v1/conversations/{conversation_id}/project")
    assert proj.status_code == 200
    assert proj.json()["current_spec_version"] >= 1


async def test_delete_conversation(client: httpx.AsyncClient) -> None:
    """软删除对话：204，列表不显示，再次访问 404。"""
    await _register(client)
    headers = _csrf_headers(client)
    conv = await client.post("/api/v1/conversations", json={"title": "待删除"}, headers=headers)
    assert conv.status_code == 201
    cid = conv.json()["conversation"]["id"]

    deleted = await client.delete(f"/api/v1/conversations/{cid}", headers=headers)
    assert deleted.status_code == 204

    listed = (await client.get("/api/v1/conversations")).json()
    assert all(c["id"] != cid for c in listed["items"])

    got = await client.get(f"/api/v1/conversations/{cid}")
    assert got.status_code == 404


async def test_confirm_project_and_manual_patch(client: httpx.AsyncClient) -> None:
    await _register(client)
    headers = _csrf_headers(client)
    conv = await client.post("/api/v1/conversations", json={"title": "手动改方案测试"}, headers=headers)
    cid = conv.json()["conversation"]["id"]

    # 先发消息让方案版本>=1
    await client.post(
        f"/api/v1/conversations/{cid}/messages",
        json={"content": "主体是雨夜古城门", "client_request_id": str(uuid.uuid4())},
        headers=headers,
    )
    proj = (await client.get(f"/api/v1/conversations/{cid}/project")).json()
    v = proj["current_spec_version"]

    # 手动改方案：改时长和画幅，乐观锁用当前版本
    patched = await client.patch(
        f"/api/v1/conversations/{cid}/project",
        json={"expected_spec_version": v, "patch": {"duration_seconds": 12, "aspect_ratio": "9:16"}},
        headers=headers,
    )
    assert patched.status_code == 200
    assert patched.json()["current_spec_version"] == v + 1
    assert patched.json()["current_spec"]["duration_seconds"] == 12

    # 确认当前版本
    confirmed = await client.post(
        f"/api/v1/conversations/{cid}/project/confirm",
        json={"spec_version": v + 1},
        headers=headers,
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["is_current_version_confirmed"] is True

    # 旧版本再改 → 409 版本冲突
    stale = await client.patch(
        f"/api/v1/conversations/{cid}/project",
        json={"expected_spec_version": v, "patch": {"duration_seconds": 8}},
        headers=headers,
    )
    assert stale.status_code == 409


async def test_search_tool_records_citations(client: httpx.AsyncClient, monkeypatch) -> None:
    """联网搜索：模型请求 search_requests → 后端搜索 → 检索结果回流给模型二次生成最终回复。

    断言证明了"第二次生成确实拿到了检索结果"：
    - provider.refine_calls == 1 说明第二阶段真实触发；
    - provider.received_messages[1] 里含检索结果注入消息，说明搜索文本被传回模型；
    - 最终正文是模型基于检索结果重写的回复（含"根据检索结果"与来源 URL），而非旧版固定文案。
    """
    from app.providers.text.base import TextCapabilities, TextProvider, TextResult
    from app.services import agent_service as ag

    class SearchThenRefineProvider(TextProvider):
        code = "searchthenrefine"

        def __init__(self) -> None:
            self.refine_calls = 0
            self.received_messages: list[list[dict[str, str]]] = []

        @property
        def capabilities(self) -> TextCapabilities:
            return TextCapabilities(supports_structured_output=True)

        async def generate(self, messages, *, structured: bool = False) -> TextResult:
            self.received_messages.append(messages)
            # 检测第二阶段：消息里含检索结果注入（注入标记为中文书名号 【检索结果】）
            injected = any("【检索结果】" in (m.get("content") or "") for m in messages)
            if injected:
                self.refine_calls += 1
                return TextResult(
                    reply="根据检索结果：故宫夜景很适合做成电影感宣传片，参考资料：https://example.com/reference/1（Fake 数据）",
                    model="fake-model",
                    structured=None,
                )
            return TextResult(
                reply="好的，我核实一下资料并附上来源。",
                structured={"reply": "好的，我核实一下资料并附上来源。", "state_patch": {}, "search_requests": ["故宫 夜景 宣传片"]},
                model="fake-model",
            )

    provider = SearchThenRefineProvider()
    monkeypatch.setattr(ag, "get_text_provider", lambda: provider)

    await _register(client)
    headers = _csrf_headers(client)
    conv = await client.post("/api/v1/conversations", json={"title": "搜索测试"}, headers=headers)
    cid = conv.json()["conversation"]["id"]

    msg = await client.post(
        f"/api/v1/conversations/{cid}/messages",
        json={"content": "帮我查一下故宫夜景宣传片的资料", "client_request_id": str(uuid.uuid4()), "web_search_enabled": True},
        headers=headers,
    )
    assert msg.status_code == 201
    content = msg.json()["assistant_message"]["content"]
    # 正文取自模型基于检索结果重写的最终回复（不再含旧版固定文案"【检索到的参考资料】"）
    assert "根据检索结果" in content
    assert "https://example.com" in content
    assert "检索到的参考资料" not in content

    # 证明第二次生成确实拿到了检索结果
    assert provider.refine_calls == 1
    assert len(provider.received_messages) == 2
    assert any("【检索结果】" in (m.get("content") or "") for m in provider.received_messages[1])

    # citations 应以结构化列表返回（而不是只附在正文文本里）
    listed = (await client.get(f"/api/v1/conversations/{cid}/messages")).json()
    assistant = next(m for m in listed["items"] if m["role"] == "assistant")
    assert len(assistant["citations"]) >= 1
    assert assistant["citations"][0]["url"].startswith("https://example.com")


async def test_agent_run_and_tool_execution_persist(client, db_engine, monkeypatch) -> None:
    """发送一条触发联网搜索的消息后，落库 AgentRun + ToolExecution，且 citation.tool_execution_id 指向该 ToolExecution。"""
    from app.db.models.agent import AgentRun, MessageCitation, ToolExecution
    from app.providers.text.base import TextCapabilities, TextProvider, TextResult
    from app.services import agent_service as ag
    from sqlalchemy.ext.asyncio import async_sessionmaker
    from sqlmodel import select
    from sqlmodel.ext.asyncio.session import AsyncSession

    class SearchTriggerProvider(TextProvider):
        code = "searchtrigger"

        @property
        def capabilities(self) -> TextCapabilities:
            return TextCapabilities(supports_structured_output=True)

        async def generate(self, messages, *, structured: bool = False) -> TextResult:
            return TextResult(
                reply="好的，我核实一下资料并附上来源。",
                structured={
                    "reply": "好的，我核实一下资料并附上来源。",
                    "state_patch": {},
                    "search_requests": ["故宫 夜景 宣传片"],
                },
                model="fake-model",
            )

    monkeypatch.setattr(ag, "get_text_provider", lambda: SearchTriggerProvider())

    await _register(client)
    headers = _csrf_headers(client)
    conv = await client.post("/api/v1/conversations", json={"title": "运行落库"}, headers=headers)
    cid = conv.json()["conversation"]["id"]

    msg = await client.post(
        f"/api/v1/conversations/{cid}/messages",
        json={"content": "帮我查一故宫夜景宣传片的资料", "client_request_id": str(uuid.uuid4()), "web_search_enabled": True},
        headers=headers,
    )
    assert msg.status_code == 201
    user_msg_id = msg.json()["user_message"]["id"]
    assistant_msg_id = msg.json()["assistant_message"]["id"]

    # 直接读取库表验证落库与关联
    async with async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)() as session:
        runs = (await session.exec(select(AgentRun))).all()
        assert len(runs) == 1
        run = runs[0]
        assert run.status == "succeeded"
        assert run.user_message_id == user_msg_id
        assert run.assistant_message_id == assistant_msg_id

        tools = (await session.exec(select(ToolExecution))).all()
        assert len(tools) == 1
        tool = tools[0]
        assert tool.tool_name == "web_search"
        assert tool.agent_run_id == run.id
        assert tool.status == "succeeded"
        assert run.tool_call_count == 1

        cites = (await session.exec(select(MessageCitation))).all()
        assert len(cites) >= 1
        assert all(c.tool_execution_id == tool.id for c in cites)


async def test_search_refine_failure_keeps_original_reply(client: httpx.AsyncClient, monkeypatch) -> None:
    """联网搜索二次生成失败时：保留初版 reply 作为正文，不丢消息、不报错，引用仍结构化落库。"""
    from app.providers.text.base import (
        TextCapabilities,
        TextProvider,
        TextProviderError,
        TextResult,
    )
    from app.services import agent_service as ag

    class FailRefineProvider(TextProvider):
        code = "failrefine"

        def __init__(self) -> None:
            self.calls = 0

        @property
        def capabilities(self) -> TextCapabilities:
            return TextCapabilities(supports_structured_output=True)

        async def generate(self, messages, *, structured: bool = False) -> TextResult:
            self.calls += 1
            if self.calls >= 2:  # 第二阶段：模拟二次生成失败
                raise TextProviderError("TEXT_PROVIDER_TIMEOUT", "二次生成失败", retryable=True)
            return TextResult(
                reply="好的，我核实一下资料并附上来源。",
                structured={
                    "reply": "好的，我核实一下资料并附上来源。",
                    "state_patch": {},
                    "search_requests": ["故宫 夜景 宣传片"],
                },
                model="fake-model",
            )

    monkeypatch.setattr(ag, "get_text_provider", lambda: FailRefineProvider())

    await _register(client)
    headers = _csrf_headers(client)
    conv = await client.post("/api/v1/conversations", json={"title": "搜索失败回退"}, headers=headers)
    cid = conv.json()["conversation"]["id"]

    msg = await client.post(
        f"/api/v1/conversations/{cid}/messages",
        json={"content": "帮我查一下故宫夜景宣传片资料", "client_request_id": str(uuid.uuid4()), "web_search_enabled": True},
        headers=headers,
    )
    assert msg.status_code == 201
    content = msg.json()["assistant_message"]["content"]
    # 二次生成失败：正文保留初版 reply，不丢消息（接口照常返回 201）
    assert content == "好的，我核实一下资料并附上来源。"
    # 引用仍结构化落库
    listed = (await client.get(f"/api/v1/conversations/{cid}/messages")).json()
    assistant = next(m for m in listed["items"] if m["role"] == "assistant")
    assert len(assistant["citations"]) >= 1
    assert assistant["citations"][0]["url"].startswith("https://example.com")


async def _insert_messages(db_engine, conversation_id: str, count: int) -> list[str]:
    """直接向库里插入 count 条 created_at 严格递增的消息（绕过 Agent，便于造超过 limit 条数）。"""
    sf = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    base = now()
    ids: list[str] = []
    async with sf() as session:
        for i in range(count):
            msg_id = new_id()
            ids.append(msg_id)
            session.add(
                Message(
                    id=msg_id,
                    conversation_id=conversation_id,
                    role=MessageRole.USER.value,
                    content=f"paging-{i}",
                    status=MessageStatus.COMPLETED.value,
                    client_request_id=f"paging-{i}-{uuid.uuid4().hex[:8]}",
                    created_at=base + timedelta(seconds=i),
                )
            )
        await session.commit()
    return ids


async def test_messages_cursor_pagination_no_dup_no_missing(client, db_engine) -> None:
    """消息列表（created_at asc, id asc）：造 7 条 > limit=3，连续翻页取全。

    断言：每页不超过 limit；非末页 next_cursor 非空、末页为空；拼接后顺序与全量一致、
    无重复、无遗漏；无 cursor 的第 1 页返回最前 limit 条。
    """
    await _register(client)
    headers = _csrf_headers(client)
    conv = await client.post("/api/v1/conversations", json={"title": "分页测试"}, headers=headers)
    cid = conv.json()["conversation"]["id"]

    expected_ids = await _insert_messages(db_engine, cid, 7)

    # 规范顺序（limit 足够大时即按 created_at asc, id asc）
    all_resp = await client.get(f"/api/v1/conversations/{cid}/messages", params={"limit": 100})
    assert all_resp.status_code == 200
    canonical_ids = [m["id"] for m in all_resp.json()["items"]]
    assert canonical_ids == expected_ids  # 插入即按 createdAt 递增

    # 第 1 页无 cursor：返回最前 limit 条，且 next_cursor 非空
    limit = 3
    first = (await client.get(f"/api/v1/conversations/{cid}/messages", params={"limit": limit})).json()
    assert len(first["items"]) == limit
    assert first["items"][0]["id"] == canonical_ids[0]
    assert first["items"][1]["id"] == canonical_ids[1]
    assert first["items"][2]["id"] == canonical_ids[2]
    assert first["next_cursor"] is not None

    # 连续翻页取全
    collected: list[str] = []
    cursor: str | None = None
    page = 0
    while True:
        params = {"limit": limit}
        if cursor:
            params["cursor"] = cursor
        resp = (await client.get(f"/api/v1/conversations/{cid}/messages", params=params)).json()
        page += 1
        assert len(resp["items"]) <= limit, f"第 {page} 页超出 limit"
        collected.extend(m["id"] for m in resp["items"])
        if resp["next_cursor"] is None:
            break
        cursor = resp["next_cursor"]
        assert cursor  # 非末页时 next_cursor 必须非空

    # 不重、不漏、顺序与规范顺序一致
    assert len(collected) == 7
    assert len(set(collected)) == 7
    assert collected == canonical_ids


async def test_conversations_cursor_pagination_no_dup_no_missing(client) -> None:
    """对话列表（updated_at desc, id desc）：造 N 条，连续翻页取全。

    说明：对话排序按 updated_at desc，同 updated_at 时按 id desc 兜底，因此这里不断言具体
    顺序，只断言不重、不漏、页大小与 next_cursor 语义正确，且拼接顺序与全量规范顺序一致。
    """
    await _register(client)
    headers = _csrf_headers(client)
    N = 5
    created_ids: list[str] = []
    for i in range(N):
        c = await client.post("/api/v1/conversations", json={"title": f"会话{i}"}, headers=headers)
        assert c.status_code == 201
        created_ids.append(c.json()["conversation"]["id"])

    all_resp = (await client.get("/api/v1/conversations", params={"limit": 100})).json()
    canonical_ids = [x["id"] for x in all_resp["items"]]
    assert len(canonical_ids) == N

    collected: list[str] = []
    cursor: str | None = None
    limit = 2
    while True:
        params = {"limit": limit}
        if cursor:
            params["cursor"] = cursor
        resp = (await client.get("/api/v1/conversations", params=params)).json()
        assert len(resp["items"]) <= limit
        collected.extend(x["id"] for x in resp["items"])
        if resp["next_cursor"] is None:
            break
        cursor = resp["next_cursor"]
        assert cursor

    assert len(collected) == N
    assert len(set(collected)) == N
    assert set(collected) == set(created_ids)
    assert collected == canonical_ids


async def test_build_context_compresses_when_summary_present() -> None:
    """构造上下文：存在摘要时把摘要边界（含）之前的历史压缩成一条 system 摘要消息，边界之后的消息保留。

    同时验证：未生成摘要时回退到完整最近历史（旧消息不被吞掉）。
    """
    from app.schemas.agent import VideoBrief
    from app.services.context_builder import build_context

    history = [
        {"id": "m0", "role": "user", "content": "old-0"},
        {"id": "m1", "role": "assistant", "content": "old-1"},
        {"id": "m2", "role": "user", "content": "old-2"},
        {"id": "m3", "role": "assistant", "content": "old-3"},
        {"id": "m4", "role": "user", "content": "new-4"},
        {"id": "m5", "role": "assistant", "content": "new-5"},
    ]

    # 摘要覆盖到 m3（含 m3），m4/m5 保留
    msgs = build_context(
        VideoBrief(), history, "current", summary_text="要点ABC", summary_through_message_id="m3"
    )
    assert msgs[0]["role"] == "system"
    # 摘要作为一条独立 system 消息跟在系统提示之后
    assert msgs[1]["role"] == "system"
    assert "对话摘要：要点ABC" in msgs[1]["content"]
    contents = [m.get("content") or "" for m in msgs]
    # 被压缩的旧消息不出现；摘要边界之后的较新消息保留；当前用户消息在最后
    for old in ("old-0", "old-1", "old-2", "old-3"):
        assert all(old not in c for c in contents)
    assert any("new-4" in c for c in contents)
    assert any("new-5" in c for c in contents)
    assert msgs[-1]["content"] == "current"

    # 无摘要时回退到完整最近历史（这里历史只有 6 条 < 12，全部保留）
    msgs2 = build_context(VideoBrief(), history, "current")
    contents2 = [m.get("content") or "" for m in msgs2]
    assert any("old-0" in c for c in contents2)
    assert msgs2[-1]["content"] == "current"


async def _backdate_messages(db_engine, conversation_id: str, count: int) -> list[str]:
    """向库里插入 count 条 created_at 明显早于当前时刻的 user 消息（绕过 Agent）。

    与上方分页测试不同：这里把 created_at 回拨到 now()-10s 之前，确保其后经 API 发起的
    实时消息在摘要统计的 time 序中排在这些消息之后，从而让边界定位确定。
    """
    sf = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    base = now() - timedelta(seconds=count + 10)
    ids: list[str] = []
    async with sf() as session:
        for i in range(count):
            msg_id = new_id()
            ids.append(msg_id)
            session.add(
                Message(
                    id=msg_id,
                    conversation_id=conversation_id,
                    role=MessageRole.USER.value,
                    content=f"paging-{i}",
                    status=MessageStatus.COMPLETED.value,
                    client_request_id=f"summ-{i}-{uuid.uuid4().hex[:8]}",
                    created_at=base + timedelta(seconds=i),
                )
            )
        await session.commit()
    return ids


async def test_long_conversation_generates_summary_and_compresses(
    client, db_engine, monkeypatch
) -> None:
    """长对话（超过阈值）自动生成摘要并压缩发给模型的上下文。

    覆盖缺口⑥三个要求：a) 生成摘要并正确记录 summary_text / summary_through_message_id；
    b) 后续轮次构建的上下文含"对话摘要"、不再包含被压缩的旧消息、仍包含摘要边界之后的较新消息；
    c) 短对话（现有测试场景）不受影响（由既有用例覆盖）。
    """
    from app.core.config import settings
    from app.db.models.conversation import ConversationContext
    from app.providers.text.base import TextCapabilities, TextProvider, TextResult
    from app.services import agent_service as ag

    class SummaryProvider(TextProvider):
        code = "summaryprov"

        def __init__(self) -> None:
            self.received: list[tuple[bool, list[dict[str, str]]]] = []

        @property
        def capabilities(self) -> TextCapabilities:
            return TextCapabilities(supports_structured_output=True)

        async def generate(self, messages, *, structured: bool = False) -> TextResult:
            self.received.append((structured, messages))
            if structured:
                # 主对话：返回结构化输出（空 patch，不触发方案版本更新/搜索）
                return TextResult(
                    reply="好的，已记录。",
                    structured={"reply": "好的，已记录。", "state_patch": {}},
                    model="fake-model",
                )
            # 摘要调用：返回一段固定中文摘要
            return TextResult(reply="【摘要】已压缩历史要点", model="fake-model", structured=None)

    provider = SummaryProvider()
    monkeypatch.setattr(ag, "get_text_provider", lambda: provider)
    monkeypatch.setattr(settings, "history_summary_threshold", 3)

    await _register(client)
    headers = _csrf_headers(client)
    conv = await client.post("/api/v1/conversations", json={"title": "长对话摘要测试"}, headers=headers)
    cid = conv.json()["conversation"]["id"]

    # 先造 5 条较早历史：总消息数因此超过阈值(3)
    expected_ids = await _backdate_messages(db_engine, cid, 5)

    # 第 1 轮：发起一条实时消息 → 本轮结束时应生成摘要
    r1 = await client.post(
        f"/api/v1/conversations/{cid}/messages",
        json={"content": "补充一点：时长30秒", "client_request_id": str(uuid.uuid4())},
        headers=headers,
    )
    assert r1.status_code == 201

    # a) 摘要已生成且边界正确：summarize 了最早 4 条（paging-0..3），边界 = 第 4 条插入消息
    async with async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)() as session:
        ctx = await session.get(ConversationContext, cid)
        assert ctx is not None
        assert ctx.summary_text == "【摘要】已压缩历史要点"
        assert ctx.summary_through_message_id == expected_ids[3]
        assert ctx.summary_model == "summaryprov"

    # 第 2 轮：发起一条新消息 → 本轮构建给模型的上下文应已压缩
    r2 = await client.post(
        f"/api/v1/conversations/{cid}/messages",
        json={"content": "再补充：16:9 画幅", "client_request_id": str(uuid.uuid4())},
        headers=headers,
    )
    assert r2.status_code == 201

    # b) 取"第 2 轮主对话"发送给模型的上下文（最后一次 structured=True 的 generate）
    last_structured: list[dict[str, str]] | None = None
    for structured, msgs in provider.received:
        if structured:
            last_structured = msgs
    assert last_structured is not None
    contents = [m.get("content") or "" for m in last_structured]
    # 上下文里出现摘要标记
    assert any("对话摘要" in c for c in contents)
    # 已压缩的最早 4 条旧消息不再出现
    for i in range(4):
        assert all(f"paging-{i}" not in c for c in contents)
    # 摘要边界之后的较新消息仍保留
    assert any("paging-4" in c for c in contents)

    # 触发过摘要调用（第 1 轮 + 第 2 轮结尾各一次 structured=False）
    assert any(not structured for structured, _msgs in provider.received)


async def test_send_message_stream_events_and_persist(client: httpx.AsyncClient) -> None:
    """SSE 事件流式发消息：收到 run_started / run_completed（及中间阶段事件），data 均合法 JSON，
    且随后 GET /messages 能查到 user + assistant 各 1 条（落库与同步端点一致）。"""
    await _register(client)
    headers = _csrf_headers(client)
    conv = await client.post("/api/v1/conversations", json={"title": "SSE 流式测试"}, headers=headers)
    cid = conv.json()["conversation"]["id"]

    text = await _read_sse(
        client,
        "POST",
        f"/api/v1/conversations/{cid}/messages/stream",
        json={"content": "拍摄雨夜中的古城门，电影感", "client_request_id": str(uuid.uuid4())},
        headers=headers,
    )
    events = _parse_sse(text)
    assert events, "SSE 流应至少产出一条事件"

    # 事件序列：run_started 在最前，run_completed 在最后，且含 text_delta / patch_applied
    types = [e["event"] for e in events]
    assert types[0] == "run_started", types
    assert types[-1] == "run_completed", types
    assert "text_delta" in types
    assert "patch_applied" in types  # 默认 fake 模型返回 subject state_patch，触发方案更新

    # 每条 data 都是合法 JSON
    for e in events:
        parsed = json.loads(e["data"])
        assert isinstance(parsed, dict)

    # run_completed 携带 user/assistant 两 id
    completed = json.loads(events[-1]["data"])
    assert completed["user_message_id"]
    assert completed["assistant_message_id"]

    # 落库一致：随后列表能查到 user + assistant 各 1 条
    listed = (await client.get(f"/api/v1/conversations/{cid}/messages")).json()
    roles = [m["role"] for m in listed["items"]]
    assert roles == ["user", "assistant"]


async def test_send_message_stream_idempotent_replay(client: httpx.AsyncClient) -> None:
    """同一 client_request_id 再次发起流式幂等：不重复创建消息/AgentRun，回放已有结果。"""
    await _register(client)
    headers = _csrf_headers(client)
    conv = await client.post("/api/v1/conversations", json={"title": "SSE 幂等"}, headers=headers)
    cid = conv.json()["conversation"]["id"]
    rid = str(uuid.uuid4())
    payload = {"content": "主体是雨夜古城门", "client_request_id": rid}

    first = await _read_sse(client, "POST", f"/api/v1/conversations/{cid}/messages/stream", json=payload, headers=headers)
    first_types = [e["event"] for e in _parse_sse(first)]
    assert first_types[-1] == "run_completed"

    second = await _read_sse(client, "POST", f"/api/v1/conversations/{cid}/messages/stream", json=payload, headers=headers)
    second_events = _parse_sse(second)
    second_types = [e["event"] for e in second_events]
    assert second_types[0] == "run_started"
    assert second_types[-1] == "run_completed"
    # 幂等回放：run_completed 标记 replayed=True 且重复出现不新增消息
    replayed = json.loads(second_events[-1]["data"])
    assert replayed["replayed"] is True

    # 仍只有 user + assistant 各 1 条（未因重复请求而重复落库）
    listed = (await client.get(f"/api/v1/conversations/{cid}/messages")).json()
    assert [m["role"] for m in listed["items"]] == ["user", "assistant"]


async def test_send_message_stream_search_event(client: httpx.AsyncClient, monkeypatch) -> None:
    """web_search_enabled=True 且模型请求了 search_requests：流中产出 searched 事件（带引用数），
    且检索结果回流给模型二次生成最终回复（事件序列正确、端到端可用）。"""
    from app.providers.text.base import TextCapabilities, TextProvider, TextResult
    from app.services import agent_service as ag

    class SearchStreamProvider(TextProvider):
        code = "searchstream"

        @property
        def capabilities(self) -> TextCapabilities:
            return TextCapabilities(supports_structured_output=True)

        async def generate(self, messages, *, structured: bool = False) -> TextResult:
            if any("【检索结果】" in (m.get("content") or "") for m in messages):
                return TextResult(
                    reply="根据检索结果：故宫夜景很适合做成电影感宣传片，参考资料：https://example.com/reference/1",
                    model="fake-model",
                    structured=None,
                )
            return TextResult(
                reply="好的，我核实一下资料并附上来源。",
                structured={"reply": "好的，我核实一下资料并附上来源。", "state_patch": {}, "search_requests": ["故宫 夜景 宣传片"]},
                model="fake-model",
            )

    monkeypatch.setattr(ag, "get_text_provider", lambda: SearchStreamProvider())

    await _register(client)
    headers = _csrf_headers(client)
    conv = await client.post("/api/v1/conversations", json={"title": "SSE 搜索"}, headers=headers)
    cid = conv.json()["conversation"]["id"]

    text = await _read_sse(
        client,
        "POST",
        f"/api/v1/conversations/{cid}/messages/stream",
        json={"content": "帮我查一下故宫夜景宣传片的资料", "client_request_id": str(uuid.uuid4()), "web_search_enabled": True},
        headers=headers,
    )
    events = _parse_sse(text)
    types = [e["event"] for e in events]
    assert types[0] == "run_started"
    assert types[-1] == "run_completed"
    assert "searched" in types

    searched = json.loads(next(e["data"] for e in events if e["event"] == "searched"))
    assert searched["citations"] >= 1  # fake_search 每条查询至少返回 1 条引用

    # 最终回复是模型基于检索结果二次生成的（含"根据检索结果"与来源 URL）
    completed = json.loads(events[-1]["data"])
    assert "根据检索结果" in completed["content"]

    # 落库：引用结构化返回
    listed = (await client.get(f"/api/v1/conversations/{cid}/messages")).json()
    assistant = next(m for m in listed["items"] if m["role"] == "assistant")
    assert len(assistant["citations"]) >= 1


async def test_sync_endpoint_idempotent_replay(client: httpx.AsyncClient) -> None:
    """同步 POST /messages 幂等命中不应因元组解包而报错，且不重复落库。"""
    await _register(client)
    headers = _csrf_headers(client)
    conv = await client.post("/api/v1/conversations", json={"title": "幂等回放"}, headers=headers)
    cid = conv.json()["conversation"]["id"]
    rid = str(uuid.uuid4())
    payload = {"content": "雨夜古城门", "client_request_id": rid}
    first = await client.post(f"/api/v1/conversations/{cid}/messages", json=payload, headers=headers)
    assert first.status_code == 201
    second = await client.post(f"/api/v1/conversations/{cid}/messages", json=payload, headers=headers)
    assert second.status_code == 201
    assert second.json()["run_id"] == first.json()["run_id"]
    listed = (await client.get(f"/api/v1/conversations/{cid}/messages")).json()
    assert len(listed["items"]) == 2  # 仅 user+assistant 各一条，未重复


async def test_search_persists_retrieval_notes(client, db_engine, monkeypatch) -> None:
    """联网搜索后，ConversationContext.retrieval_notes 非空且包含该查询相关文本。

    证明"详细依据被保存到对话记录"：检索结果块（每查询一组「查询/标题/链接/摘要」）被追加到
    该对话的持久上下文，且保留完整详细依据（含链接与摘要），而非只保存结构化引用。
    """
    from app.db.models.conversation import ConversationContext
    from app.providers.text.base import TextCapabilities, TextProvider, TextResult
    from app.services import agent_service as ag
    from sqlalchemy.ext.asyncio import async_sessionmaker
    from sqlmodel.ext.asyncio.session import AsyncSession

    class SearchNotesProvider(TextProvider):
        code = "searchnotes"

        @property
        def capabilities(self) -> TextCapabilities:
            return TextCapabilities(supports_structured_output=True)

        async def generate(self, messages, *, structured: bool = False) -> TextResult:
            if structured:
                # 主对话：请求联网搜索
                return TextResult(
                    reply="好的，我核实一下资料。",
                    structured={
                        "reply": "好的，我核实一下资料。",
                        "state_patch": {},
                        "search_requests": ["故宫 夜景 宣传片"],
                    },
                    model="fake-model",
                )
            # refine：基于检索结果二次生成最终回复
            return TextResult(
                reply="根据检索结果：故宫夜景适合做成电影感宣传片，参考资料：https://example.com/reference/1",
                model="fake-model",
                structured=None,
            )

    monkeypatch.setattr(ag, "get_text_provider", lambda: SearchNotesProvider())

    await _register(client)
    headers = _csrf_headers(client)
    conv = await client.post("/api/v1/conversations", json={"title": "检索依据落库"}, headers=headers)
    cid = conv.json()["conversation"]["id"]

    msg = await client.post(
        f"/api/v1/conversations/{cid}/messages",
        json={"content": "帮我查一下故宫夜景宣传片资料", "client_request_id": str(uuid.uuid4()), "web_search_enabled": True},
        headers=headers,
    )
    assert msg.status_code == 201

    async with async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)() as session:
        ctx = await session.get(ConversationContext, cid)
        assert ctx is not None
        assert ctx.retrieval_notes is not None
        assert ctx.retrieval_notes != ""
        # 该查询相关信息确实进入持久上下文
        assert "查询：故宫 夜景 宣传片" in ctx.retrieval_notes
        # 保留完整详细依据（链接/摘要），而非只存结构化引用
        assert "https://example.com" in ctx.retrieval_notes
        assert "摘要：" in ctx.retrieval_notes


async def test_next_turn_sees_retrieval_notes(client, db_engine, monkeypatch) -> None:
    """联网搜索后的下一轮，发送给模型的消息里包含【此前联网检索到的资料】与依据文本。

    证明"后续多轮 AI 都能看到检索依据"：取第二轮主对话（最后一次 structured=True 的 generate）
    的 messages，断言含注入标记与检索文本；同时本轮用户界面正文仍是模型自身回复，不被依据污染
    （依据只进入后端上下文）。且首轮 assistant 消息的 citations 结构化引用不受影响。
    """
    from app.providers.text.base import TextCapabilities, TextProvider, TextResult
    from app.services import agent_service as ag

    class NextTurnProvider(TextProvider):
        code = "nextturn"

        def __init__(self) -> None:
            self.received: list[tuple[bool, list[dict[str, str]]]] = []
            self.structured_calls = 0

        @property
        def capabilities(self) -> TextCapabilities:
            return TextCapabilities(supports_structured_output=True)

        async def generate(self, messages, *, structured: bool = False) -> TextResult:
            self.received.append((structured, messages))
            self.structured_calls += 1 if structured else 0
            if structured:
                if self.structured_calls == 1:
                    # 第 1 轮主对话：请求联网搜索
                    return TextResult(
                        reply="好的，我核实一下材料。",
                        structured={
                            "reply": "好的，我核实一下材料。",
                            "state_patch": {},
                            "search_requests": ["故宫 夜景 宣传片"],
                        },
                        model="fake-model",
                    )
                # 第 2 轮主对话：不再请求搜索
                return TextResult(
                    reply="好的，已了解。",
                    structured={"reply": "好的，已了解。", "state_patch": {}},
                    model="fake-model",
                )
            # 第 1 轮 refine：基于检索结果二次生成最终回复
            return TextResult(
                reply="根据检索结果：故宫夜景适合做成电影感宣传片，参考资料：https://example.com/reference/1",
                model="fake-model",
                structured=None,
            )

    provider = NextTurnProvider()
    monkeypatch.setattr(ag, "get_text_provider", lambda: provider)

    await _register(client)
    headers = _csrf_headers(client)
    conv = await client.post("/api/v1/conversations", json={"title": "检索依据跨轮"}, headers=headers)
    cid = conv.json()["conversation"]["id"]

    # 第 1 轮：联网搜索 → 依据入库，正文为 refine 结果
    r1 = await client.post(
        f"/api/v1/conversations/{cid}/messages",
        json={"content": "帮我查一下故宫夜景宣传片资料", "client_request_id": str(uuid.uuid4()), "web_search_enabled": True},
        headers=headers,
    )
    assert r1.status_code == 201
    assert "根据检索结果" in r1.json()["assistant_message"]["content"]

    # 第 2 轮：再次发消息（不联网），主对话上下文应带上累积的检索依据
    r2 = await client.post(
        f"/api/v1/conversations/{cid}/messages",
        json={"content": "在此基础上继续细化", "client_request_id": str(uuid.uuid4())},
        headers=headers,
    )
    assert r2.status_code == 201

    # 取第 2 轮主对话发送给模型的 messages（最后一次 structured=True 的 generate）
    second_structured: list[dict[str, str]] | None = None
    for structured, msgs in provider.received:
        if structured:
            second_structured = msgs
    assert second_structured is not None
    contents = [m.get("content") or "" for m in second_structured]
    assert any("【此前联网检索到的资料】" in c for c in contents)
    assert any("查询：故宫 夜景 宣传片" in c for c in contents)

    # 本轮用户界面正文不被检索依据污染（依据只进后端上下文，不进 reply）
    assert "根据检索结果" not in r2.json()["assistant_message"]["content"]

    # citations 结构化引用不受影响：首轮 assistant 消息仍返回结构化引用列表
    listed = (await client.get(f"/api/v1/conversations/{cid}/messages")).json()
    first_assistant = next(m for m in listed["items"] if m["role"] == "assistant")
    assert len(first_assistant["citations"]) >= 1
    assert first_assistant["citations"][0]["url"].startswith("https://example.com")


async def test_retrieval_notes_dedup_same_query(client, db_engine, monkeypatch) -> None:
    """同一查询在后续轮被再次联网搜索时，retrieval_notes 不重复追加该查询。

    证明去重逻辑：检索依据块以"查询：{query}"为唯一标识，已存在则跳过，避免积累冗余副本。
    """
    from app.db.models.conversation import ConversationContext
    from app.providers.text.base import TextCapabilities, TextProvider, TextResult
    from app.services import agent_service as ag
    from sqlalchemy.ext.asyncio import async_sessionmaker
    from sqlmodel.ext.asyncio.session import AsyncSession

    class DedupSearchProvider(TextProvider):
        code = "dedupsearch"

        @property
        def capabilities(self) -> TextCapabilities:
            return TextCapabilities(supports_structured_output=True)

        async def generate(self, messages, *, structured: bool = False) -> TextResult:
            if structured:
                return TextResult(
                    reply="好的，我核实一下资料。",
                    structured={
                        "reply": "好的，我核实一下资料。",
                        "state_patch": {},
                        "search_requests": ["故宫 夜景 宣传片"],
                    },
                    model="fake-model",
                )
            return TextResult(
                reply="根据检索结果：故宫夜景适合做成电影感宣传片，参考资料：https://example.com/reference/1",
                model="fake-model",
                structured=None,
            )

    monkeypatch.setattr(ag, "get_text_provider", lambda: DedupSearchProvider())

    await _register(client)
    headers = _csrf_headers(client)
    conv = await client.post("/api/v1/conversations", json={"title": "检索依据去重"}, headers=headers)
    cid = conv.json()["conversation"]["id"]

    # 两轮都触发同一查询的联网搜索
    for i in range(2):
        resp = await client.post(
            f"/api/v1/conversations/{cid}/messages",
            json={"content": f"再查一次故宫夜景宣传片（第{i + 1}轮）", "client_request_id": str(uuid.uuid4()), "web_search_enabled": True},
            headers=headers,
        )
        assert resp.status_code == 201

    async with async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)() as session:
        ctx = await session.get(ConversationContext, cid)
        assert ctx is not None
        assert ctx.retrieval_notes is not None
        # 同一查询只追加一次
        assert ctx.retrieval_notes.count("查询：故宫 夜景 宣传片") == 1
