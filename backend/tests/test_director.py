"""全片 AI 统筹规划（AI 导演向导）接口与服务测试。"""

from app.core.config import settings
from app.providers.email.fake import fake_instance
from httpx import AsyncClient, Response
from pytest import MonkeyPatch, mark

ORIGIN = "http://127.0.0.1:5173"


async def _register(client: AsyncClient, email: str = "director@test.com") -> None:
    await client.post("/api/v1/auth/email-codes", json={"email": email, "purpose": "register"})
    code = fake_instance.sent[-1]["code"]
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "code": code, "password": "password123"},
    )
    assert resp.status_code == 201


def _csrf_headers(client: AsyncClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies.get("hw_csrf", ""), "Origin": ORIGIN}


async def _create_conversation(client: AsyncClient, title: str = "竹编出海短片") -> str:
    resp = await client.post(
        "/api/v1/conversations", json={"title": title}, headers=_csrf_headers(client)
    )
    assert resp.status_code == 201
    return resp.json()["conversation"]["id"]


@mark.asyncio
async def test_director_auth_csrf_and_ownership(client: AsyncClient) -> None:
    # 1. 未登录访问（带或不带 CSRF 均应被拦截，不能返回 200/404）
    res_unauth = await client.post(
        "/api/v1/conversations/conv_any/director/outline",
        json={"total_duration": 45, "user_idea": "展现东方竹编工艺"},
    )
    assert res_unauth.status_code == 401
    assert res_unauth.json()["error"]["code"] == "AUTH_REQUIRED"

    # 2. 注册用户 A 并创建对话
    await _register(client, "user_a@test.com")
    conv_id = await _create_conversation(client)

    # 3. 缺少 CSRF 头被拦截
    res_no_csrf = await client.post(
        f"/api/v1/conversations/{conv_id}/director/outline",
        json={"total_duration": 45, "user_idea": "展现东方竹编工艺"},
    )
    assert res_no_csrf.status_code == 403
    assert res_no_csrf.json()["error"]["code"] == "CSRF_INVALID"

    # 4. 访问不存在的对话返回 404
    res_missing = await client.post(
        "/api/v1/conversations/not_exist_conv/director/outline",
        json={"total_duration": 45, "user_idea": "展现东方竹编工艺"},
        headers=_csrf_headers(client),
    )
    assert res_missing.status_code == 404
    assert res_missing.json()["error"]["code"] == "CONVERSATION_NOT_FOUND"

    # 5. 注册用户 B，尝试访问用户 A 的对话，必须 404 隔离
    client.cookies.clear()
    await _register(client, "user_b@test.com")
    res_other = await client.post(
        f"/api/v1/conversations/{conv_id}/director/breakdown",
        json={
            "total_duration": 45,
            "segment_count": 3,
            "script_draft": "【核心立意】东方美学走进欧洲家庭的温暖故事",
        },
        headers=_csrf_headers(client),
    )
    assert res_other.status_code == 404
    assert res_other.json()["error"]["code"] == "CONVERSATION_NOT_FOUND"


@mark.asyncio
async def test_director_schema_extra_forbid_and_validation(client: AsyncClient) -> None:
    await _register(client, "schema@test.com")
    conv_id = await _create_conversation(client)

    # 传入多余字段应被 ConfigDict(extra="forbid") 拒绝
    res_extra = await client.post(
        f"/api/v1/conversations/{conv_id}/director/outline",
        json={"total_duration": 45, "user_idea": "竹编灯具故事", "unexpected": 1},
        headers=_csrf_headers(client),
    )
    assert res_extra.status_code == 422

    # total_duration 越界
    res_range = await client.post(
        f"/api/v1/conversations/{conv_id}/director/breakdown",
        json={
            "total_duration": 2,
            "segment_count": 1,
            "script_draft": "【核心立意】竹编工艺微电影完整剧本大纲",
        },
        headers=_csrf_headers(client),
    )
    assert res_range.status_code == 422


@mark.asyncio
async def test_director_outline_and_breakdown_happy_path(client: AsyncClient) -> None:
    await _register(client, "happy@test.com")
    conv_id = await _create_conversation(client)

    # Step 1a: 首次生成剧本大纲
    outline_res = await client.post(
        f"/api/v1/conversations/{conv_id}/director/outline",
        json={
            "total_duration": 45,
            "user_idea": "展现中国非遗竹编工艺走进现代欧洲家庭，传递环保与东方美学",
        },
        headers=_csrf_headers(client),
    )
    assert outline_res.status_code == 200
    outline_data = outline_res.json()
    assert outline_data["recommended_segments"] == 3
    assert "【核心立意】" in outline_data["script_draft"]

    # Step 1b: 带入用户手改草稿与修改意见迭代
    rev_res = await client.post(
        f"/api/v1/conversations/{conv_id}/director/outline",
        json={
            "total_duration": 40,
            "user_idea": "竹编工艺走进欧洲家庭",
            "current_draft": outline_data["script_draft"] + "\n4. 手改细节：加入欧洲小女孩。",
            "revision_instruction": "节奏更紧凑，突出小女孩触摸竹灯的特写",
        },
        headers=_csrf_headers(client),
    )
    assert rev_res.status_code == 200
    assert rev_res.json()["recommended_segments"] == 3

    # Step 2 -> 3: 先拉取系统默认模板，测试按模板与多国家 code 拆解，且包含尾差时长分配（40s -> 15,15,10）
    tpl_res = await client.get("/api/v1/prompt-templates")
    assert tpl_res.status_code == 200
    tpl_id = tpl_res.json()["items"][0]["id"]

    bd_res = await client.post(
        f"/api/v1/conversations/{conv_id}/director/breakdown",
        json={
            "total_duration": 40,
            "segment_count": 3,
            "script_draft": outline_data["script_draft"],
            "country_codes": ["FR", "DE"],
            "style_template_id": tpl_id,
            "custom_style_desc": "4K纪录片质感，丁达尔光效",
        },
        headers=_csrf_headers(client),
    )
    assert bd_res.status_code == 200
    bd = bd_res.json()
    assert len(bd["segments"]) == 3
    assert [s["title"] for s in bd["segments"]] == ["片段一", "片段二", "片段三"]
    assert [s["duration"] for s in bd["segments"]] == [15, 15, 10]
    # 数据库 FR / DE 的负面提示词必须保底注入到 cultural_node_content
    assert "工业化流水线塑料感" in bd["cultural_node_content"]
    assert "虚假浮夸" in bd["cultural_node_content"]

    # Step 2 -> 3 空国家列表 + 大于 10 个片段（12 段 -> 片段十二）边界测试
    bd_12_res = await client.post(
        f"/api/v1/conversations/{conv_id}/director/breakdown",
        json={
            "total_duration": 180,
            "segment_count": 12,
            "script_draft": outline_data["script_draft"],
            "country_codes": [],
        },
        headers=_csrf_headers(client),
    )
    assert bd_12_res.status_code == 200
    bd_12 = bd_12_res.json()
    assert len(bd_12["segments"]) == 12
    assert bd_12["segments"][10]["title"] == "片段十一"
    assert bd_12["segments"][11]["title"] == "片段十二"


@mark.asyncio
async def test_director_openai_compatible_markdown_fence_and_error_format(
    client: AsyncClient, monkeypatch: MonkeyPatch
) -> None:
    await _register(client, "llm@test.com")
    conv_id = await _create_conversation(client)

    monkeypatch.setattr(settings, "text_provider", "openai_compatible")
    monkeypatch.setattr(settings, "text_base_url", "https://mock-llm.example.com/v1")
    monkeypatch.setattr(settings, "text_api_key", "sk-test")
    monkeypatch.setattr(settings, "text_model", "deepseek-v3")

    # 1. 模拟 LLM 返回带 ```json 代码围栏的包装对象 + 别名字段（shots/prompt）+ 片段数超出时截断 + 验证 temperature/max_tokens 透传
    captured_payload: dict = {}

    async def mock_post_fence(self, url, *, json=None, headers=None, **kwargs):
        if str(url).startswith("https://mock-llm.example.com"):
            captured_payload.update(json or {})
        content = (
            "```json\n"
            "{\n"
            '  "data": {\n'
            '    "style_prompt": "暖调写实电影质感",\n'
            '    "cultural_prompt": "法国受众适配",\n'
            '    "key_frames": "老匠人首帧图",\n'
            '    "shots": [\n'
            '      {"index": 1, "title": "Seg1", "duration": 15, "prompt": "0-5秒：全景竹林"},\n'
            '      {"index": 2, "title": "Seg2", "duration": 15, "prompt": "0-5秒：欧洲客厅"},\n'
            '      {"index": 3, "title": "Seg3", "duration": 15, "prompt": "多余片段"}\n'
            "    ]\n"
            "  }\n"
            "}\n"
            "```"
        )
        return Response(
            200,
            json={"model": "deepseek-v3", "choices": [{"message": {"content": content}}]},
        )

    orig_post = AsyncClient.post

    async def dispatch_post(self, url, *args, **kwargs):
        if str(url).startswith("https://mock-llm.example.com"):
            return await mock_post_fence(self, url, *args, **kwargs)
        return await orig_post(self, url, *args, **kwargs)

    monkeypatch.setattr(AsyncClient, "post", dispatch_post)
    res_ok = await client.post(
        f"/api/v1/conversations/{conv_id}/director/breakdown",
        json={
            "total_duration": 30,
            "segment_count": 2,
            "script_draft": "【核心立意】东方匠心走进欧洲家庭的跨文化微电影",
            "country_codes": ["fr", " "],
        },
        headers=_csrf_headers(client),
    )
    assert res_ok.status_code == 200
    assert captured_payload["temperature"] == settings.director_breakdown_temperature
    assert captured_payload["max_tokens"] == settings.director_breakdown_max_tokens
    data_ok = res_ok.json()
    assert len(data_ok["segments"]) == 2
    assert [s["title"] for s in data_ok["segments"]] == ["片段一", "片段二"]
    assert data_ok["style_node_content"] == "暖调写实电影质感"
    assert "老匠人首帧图" in data_ok["image_asset_prompts"]

    # 2. 模拟首次片段数量不足，但在自动受控修复重试后成功补齐
    attempt_calls = 0

    async def mock_post_repaired(self, url, *, json=None, headers=None, **kwargs):
        nonlocal attempt_calls
        if not str(url).startswith("https://mock-llm.example.com"):
            return await orig_post(self, url, json=json, headers=headers, **kwargs)
        attempt_calls += 1
        if attempt_calls == 1:
            content = (
                '{"style_node_content": "a", "cultural_node_content": "b", "image_asset_prompts": "c",'
                ' "segments": [{"index": 1, "title": "片段一", "duration": 15, "timeline_prompt": "0-5秒：首段"}]}'
            )
        else:
            content = (
                '{"style_node_content": "a", "cultural_node_content": "b", "image_asset_prompts": "c",'
                ' "segments": ['
                '{"index": 1, "title": "片段一", "duration": 15, "timeline_prompt": "0-5秒：首段"},'
                '{"index": 2, "title": "片段二", "duration": 15, "timeline_prompt": "0-5秒：次段"}'
                "]}"
            )
        return Response(200, json={"choices": [{"message": {"content": content}}]})

    monkeypatch.setattr(AsyncClient, "post", mock_post_repaired)
    res_repaired = await client.post(
        f"/api/v1/conversations/{conv_id}/director/breakdown",
        json={
            "total_duration": 30,
            "segment_count": 2,
            "script_draft": "【核心立意】东方匠心走进欧洲家庭的跨文化微电影",
        },
        headers=_csrf_headers(client),
    )
    assert res_repaired.status_code == 200
    assert attempt_calls == 2
    assert len(res_repaired.json()["segments"]) == 2

    # 3. 模拟修复重试后片段数量仍不足 -> 返回统一 error 信封
    async def mock_post_short(self, url, *, json=None, headers=None, **kwargs):
        if not str(url).startswith("https://mock-llm.example.com"):
            return await orig_post(self, url, json=json, headers=headers, **kwargs)
        content = (
            '{"style_node_content": "a", "cultural_node_content": "b", "image_asset_prompts": "c",'
            ' "segments": [{"index": 1, "title": "片段一", "duration": 15, "timeline_prompt": "0-5秒：..."}]}'
        )
        return Response(200, json={"choices": [{"message": {"content": content}}]})

    monkeypatch.setattr(AsyncClient, "post", mock_post_short)
    res_err = await client.post(
        f"/api/v1/conversations/{conv_id}/director/breakdown",
        json={
            "total_duration": 30,
            "segment_count": 2,
            "script_draft": "【核心立意】东方匠心走进欧洲家庭的跨文化微电影",
        },
        headers=_csrf_headers(client),
    )
    assert res_err.status_code == 502
    err_body = res_err.json()
    assert err_body["error"]["code"] == "AGENT_OUTPUT_INVALID"
    assert "request_id" in err_body["error"]
