"""对话与消息链路测试：注册 → 建对话 → 发消息（Fake 模型）→ 读消息/项目。"""

import uuid

import httpx
from app.providers.email.fake import fake_instance

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
    """联网搜索：模型请求 search_requests → 后端执行搜索 → 回复附来源并落库引用。"""
    from app.providers.text.base import TextCapabilities, TextProvider, TextResult
    from app.services import agent_service as ag

    class SearchTriggerProvider(TextProvider):
        code = "searchtrigger"

        @property
        def capabilities(self) -> TextCapabilities:
            return TextCapabilities(supports_structured_output=True)

        async def generate(self, messages, *, structured: bool = False) -> TextResult:
            return TextResult(
                reply="好的，我核实一下资料并附上来源。",
                structured={"reply": "好的，我核实一下资料并附上来源。", "state_patch": {}, "search_requests": ["故宫 夜景 宣传片"]},
                model="fake-model",
            )

    monkeypatch.setattr(ag, "get_text_provider", lambda: SearchTriggerProvider())

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
    assert "检索到的参考资料" in content
    assert "https://example.com" in content

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
