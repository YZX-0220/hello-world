"""提示词模板与版本控制管理接口测试。"""

from datetime import datetime, timedelta

import pytest
from app.core.enums import UserStatus
from app.core.security import new_session_token, token_sha256
from app.db.models.user import User, UserSession
from sqlmodel.ext.asyncio.session import AsyncSession

TEMPLATES_URL = "/api/v1/prompt-templates"


@pytest.fixture
async def auth_client(client, db_engine):
    """准备已登录的客户端会话。"""
    async with AsyncSession(db_engine) as session:
        user = User(
            id="usr_tester_tpl",
            email="tester_tpl@example.com",
            password_hash="hash",
            status=UserStatus.ACTIVE.value,
        )
        token = new_session_token()
        user_session = UserSession(
            id="ses_tester_tpl",
            user_id=user.id,
            token_hash=token_sha256(token),
            expires_at=datetime.now() + timedelta(days=1),
        )
        session.add(user)
        session.add(user_session)
        await session.commit()

    client.cookies.set("hw_session", token)
    return client


@pytest.mark.asyncio
async def test_prompt_templates_full_lifecycle_and_versioning(client, auth_client):
    # 1. 列表查询（自动加载系统预置模板）
    list_res = await client.get(TEMPLATES_URL)
    assert list_res.status_code == 200
    items = list_res.json()["items"]
    assert len(items) >= 3
    sys_tpl_storyboard = next(i for i in items if i["code"] == "system_global_storyboard_v1")
    assert sys_tpl_storyboard["current_version"] == 1
    assert len(sys_tpl_storyboard["variables"]) > 0

    # 2. 登录用户创建自定义模板（含 {{subject}} 与 {{lighting}} 占位符）
    new_tpl_payload = {
        "name": "东方水墨风叙事模板",
        "category": "positive",
        "content": "东方古典水墨画卷风格，主体是{{subject}}，环境在{{scene}}，光线柔和如{{lighting}}，留白写意。",
        "negative_prompt": "浓烈艳俗、现代建筑、电线杆、硬质3D感",
        "description": "用于中国风美学视听生成",
        "change_note": "创建初始东方水墨模板",
    }
    create_res = await auth_client.post(TEMPLATES_URL, json=new_tpl_payload)
    assert create_res.status_code == 201
    tpl_data = create_res.json()
    tpl_id = tpl_data["id"]
    assert tpl_data["current_version"] == 1
    assert set(tpl_data["variables"]) == {"subject", "scene", "lighting"}

    # 验证初始版本快照 (v1)
    v_res = await client.get(f"{TEMPLATES_URL}/{tpl_id}/versions")
    assert v_res.status_code == 200
    versions = v_res.json()
    assert len(versions) == 1
    assert versions[0]["version"] == 1
    assert versions[0]["source_type"] == "init"

    # 3. 编辑模板（修改正文和负面词，触发自动生成 v2）
    update_payload = {
        "name": "东方水墨风叙事模板 (进阶版)",
        "content": "4k 高清宣纸质感，主体{{subject}}伴随水墨晕染，运镜如{{camera}}缓缓推进。",
        "negative_prompt": "浓烈艳俗、现代建筑、硬质塑料感、闪烁噪点",
        "change_note": "补充宣纸质感与镜头运动变量",
    }
    put_res = await auth_client.put(f"{TEMPLATES_URL}/{tpl_id}", json=update_payload)
    assert put_res.status_code == 200
    updated_tpl = put_res.json()
    assert updated_tpl["current_version"] == 2
    assert set(updated_tpl["variables"]) == {"subject", "camera"}

    # 检查版本列表已包含 v2 和 v1
    v_res2 = await client.get(f"{TEMPLATES_URL}/{tpl_id}/versions")
    assert v_res2.status_code == 200
    versions2 = v_res2.json()
    assert len(versions2) == 2
    assert versions2[0]["version"] == 2
    assert versions2[0]["source_type"] == "edit"
    assert versions2[1]["version"] == 1

    # 查询指定 v1 快照内容
    v1_detail = await client.get(f"{TEMPLATES_URL}/{tpl_id}/versions/1")
    assert v1_detail.status_code == 200
    assert "东方古典水墨画卷风格" in v1_detail.json()["content"]

    # 4. 一键回滚到 v1（自动生成 v3 快照，内容与 v1 相同，source_type='rollback'）
    rollback_payload = {
        "target_version": 1,
        "change_note": "测试一键回滚到初始经典水墨版本",
    }
    rb_res = await auth_client.post(f"{TEMPLATES_URL}/{tpl_id}/rollback", json=rollback_payload)
    assert rb_res.status_code == 200
    rolled_tpl = rb_res.json()
    assert rolled_tpl["current_version"] == 3
    assert "东方古典水墨画卷风格" in rolled_tpl["content"]

    # 检查版本列表当前为 3 条记录
    v_res3 = await client.get(f"{TEMPLATES_URL}/{tpl_id}/versions")
    versions3 = v_res3.json()
    assert len(versions3) == 3
    assert versions3[0]["version"] == 3
    assert versions3[0]["source_type"] == "rollback"
    assert versions3[0]["change_note"] == "测试一键回滚到初始经典水墨版本"

    # 5. 软删除模板
    del_res = await auth_client.delete(f"{TEMPLATES_URL}/{tpl_id}")
    assert del_res.status_code == 204

    # 再次查询应报 404
    get_after_del = await client.get(f"{TEMPLATES_URL}/{tpl_id}")
    assert get_after_del.status_code == 404
