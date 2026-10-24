"""健康检查接口测试（阶段 0~1 产出）。

注意：复用同一个 TestClient（模块级 fixture），避免多次触发 lifespan 时
异步 engine 跨事件循环复用导致的不稳定。
"""

import pytest
from app.main import app
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client() -> TestClient:
    with TestClient(app) as c:
        yield c


def test_healthz_returns_ok(client: TestClient) -> None:
    res = client.get("/healthz")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["service"] == "hello-world-backend"
    assert body["version"] == "0.1.0"
    assert "time" in body


def test_readyz_returns_db_ok(client: TestClient) -> None:
    res = client.get("/readyz")
    # DB 为必需依赖且可用；Redis 本地可能不可用 → 允许 degraded（200）
    assert res.status_code == 200
    body = res.json()
    assert body["components"]["database"]["status"] == "ok"
    assert body["status"] in {"ready", "degraded"}


def test_healthz_includes_request_id_header(client: TestClient) -> None:
    res = client.get("/healthz")
    assert res.headers.get("x-request-id")
