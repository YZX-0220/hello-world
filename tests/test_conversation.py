"""对话与消息链路测试：注册 → 建对话 → 发消息（Fake 模型）→ 读消息/项目。"""

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
