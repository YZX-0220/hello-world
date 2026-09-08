"""认证链路测试：验证码 → 注册 → 当前用户 → 注销 → 密码登录。"""

import httpx
from app.providers.email.fake import fake_instance

EMAIL = "user@example.com"
PASSWORD = "password123"


def _last_code() -> str:
    """取最近一次 Fake 邮件发送的验证码。"""
    return fake_instance.sent[-1]["code"]


async def _send_register_code(client: httpx.AsyncClient, email: str = EMAIL) -> None:
    resp = await client.post("/api/v1/auth/email-codes", json={"email": email, "purpose": "register"})
    assert resp.status_code == 202
    assert resp.json()["accepted"] is True


async def test_register_sets_cookies_and_current_user(client: httpx.AsyncClient) -> None:
    await _send_register_code(client)
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": EMAIL, "code": _last_code(), "password": PASSWORD},
    )
    assert resp.status_code == 201
    assert resp.json()["email"] == EMAIL
    assert "hw_session" in client.cookies
    assert "hw_csrf" in client.cookies

    # Cookie 已自动带上，读取当前用户
    me = await client.get("/api/v1/users/me")
    assert me.status_code == 200
    assert me.json()["email"] == EMAIL


async def test_logout_revokes_session(client: httpx.AsyncClient) -> None:
    await _send_register_code(client)
    await client.post("/api/v1/auth/register", json={"email": EMAIL, "code": _last_code(), "password": PASSWORD})

    csrf = client.cookies.get("hw_csrf", "")
    logout = await client.post(
        "/api/v1/auth/logout",
        headers={"X-CSRF-Token": csrf, "Origin": "http://127.0.0.1:5173"},
    )
    assert logout.status_code == 204

    me = await client.get("/api/v1/users/me")
    assert me.status_code == 401


async def test_password_login_and_wrong_password(client: httpx.AsyncClient) -> None:
    await _send_register_code(client)
    await client.post("/api/v1/auth/register", json={"email": EMAIL, "code": _last_code(), "password": PASSWORD})

    # 正确密码登录
    ok = await client.post("/api/v1/auth/login/password", json={"email": EMAIL, "password": PASSWORD})
    assert ok.status_code == 200
    assert ok.json()["email"] == EMAIL

    # 错误密码 → 401 INVALID_CREDENTIALS
    bad = await client.post("/api/v1/auth/login/password", json={"email": EMAIL, "password": "wrong-password"})
    assert bad.status_code == 401
    assert bad.json()["error"]["code"] == "INVALID_CREDENTIALS"


async def test_register_with_bad_code_rejected(client: httpx.AsyncClient) -> None:
    await _send_register_code(client)
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": EMAIL, "code": "000000", "password": PASSWORD},
    )
    assert resp.status_code != 201
    assert "authorization" not in resp.text.lower()
