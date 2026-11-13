"""国际传播国家负面提示词（Cultural Guidance）接口测试。"""

from datetime import datetime, timedelta

from app.core.enums import UserStatus
from app.core.security import new_session_token, token_sha256
from app.db.models.user import User, UserSession
from pytest import fixture as pytest_fixture
from pytest import mark
from sqlmodel.ext.asyncio.session import AsyncSession

GUIDANCES_URL = "/api/v1/cultural-guidances"


@pytest_fixture
async def auth_client(client, db_engine):
    """准备已登录的客户端会话。"""
    async with AsyncSession(db_engine) as session:
        user = User(
            id="usr_tester_guidance",
            email="tester_guidance@example.com",
            password_hash="hash",
            status=UserStatus.ACTIVE.value,
        )
        token = new_session_token()
        user_session = UserSession(
            id="ses_tester_guidance",
            user_id=user.id,
            token_hash=token_sha256(token),
            expires_at=datetime.now() + timedelta(days=1),
        )
        session.add(user)
        session.add(user_session)
        await session.commit()

    client.cookies.set("hw_session", token)
    return client


@mark.asyncio
async def test_cultural_guidances_flow(client, auth_client):
    # 1. 匿名/首次查询列表（触发默认数据写入并返回列表）
    res = await client.get(GUIDANCES_URL)
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert len(data["items"]) >= 7
    codes = [i["code"] for i in data["items"]]
    assert "CN" in codes
    assert "US" in codes
    assert "GB" in codes

    # 2. 登录用户创建新国家配置
    new_country = {
        "code": "SG",
        "name": "新加坡",
        "negative_prompt": "过度拥挤压抑感、生硬标语符号、粗糙CG滤镜",
        "taboo": "避免单一刻板视角，注重多元包容表达",
        "sort_order": 10,
        "is_enabled": True,
    }
    create_res = await auth_client.post(GUIDANCES_URL, json=new_country)
    assert create_res.status_code == 201
    created_item = create_res.json()
    assert created_item["code"] == "SG"
    assert created_item["name"] == "新加坡"
    assert created_item["id"] > 0

    # 3. 重复创建相同 code 报 409
    dup_res = await auth_client.post(GUIDANCES_URL, json=new_country)
    assert dup_res.status_code == 409

    # 4. 更新国家配置（如更新负面词与禁忌）
    update_payload = {
        "negative_prompt": "更新后的新加坡负面提示词：避免粗制滥造和死板构图",
        "taboo": "更新后的禁忌说明",
        "sort_order": 8,
    }
    put_res = await auth_client.put(f"{GUIDANCES_URL}/SG", json=update_payload)
    assert put_res.status_code == 200
    updated_item = put_res.json()
    assert updated_item["negative_prompt"] == update_payload["negative_prompt"]
    assert updated_item["taboo"] == update_payload["taboo"]
    assert updated_item["sort_order"] == 8

    # 5. 更新不存在的国家返回 404
    not_found_res = await auth_client.put(f"{GUIDANCES_URL}/NON_EXIST", json={"name": "不存在"})
    assert not_found_res.status_code == 404
