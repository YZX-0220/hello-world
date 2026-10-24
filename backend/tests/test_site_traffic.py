"""Real SQL transactions and API requests, without production data or paid providers."""

import asyncio
import os
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from app.core.config import settings
from app.core.security import token_sha256
from app.db.models.site_traffic import SiteTrafficTotal, SiteVisit, SiteVisitEvent
from app.db.models.user import User, UserSession
from app.db.redis import get_redis
from app.main import app
from app.services import site_traffic_service as traffic
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

SUMMARY = "/api/v1/site-traffic/summary"
VISITS = "/api/v1/site-traffic/visits"
CHROME = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130.0.0.0 Safari/537.36"
)


@pytest.fixture(autouse=True)
def traffic_config(monkeypatch):
    monkeypatch.setattr(settings, "app_base_url", "http://testserver")
    monkeypatch.setattr(settings, "frontend_origin", "http://frontend.test")
    monkeypatch.setattr(settings, "cookie_secure", False)
    monkeypatch.setattr(settings, "traffic_trusted_proxy_cidrs", "")


async def bootstrap(client):
    response = await client.get(SUMMARY)
    assert response.status_code == 200
    return response, client.cookies.get(traffic.VISITOR_COOKIE)


async def report(client, *, path="/", event=None, cookie=None, **kwargs):
    headers = {"Origin": "http://testserver", "User-Agent": CHROME}
    if cookie:
        headers["Cookie"] = f"{traffic.VISITOR_COOKIE}={cookie}"
    headers.update(kwargs.pop("headers", {}))
    return await client.post(
        VISITS,
        json={
            "event_id": event or str(uuid4()),
            "path": path,
            **kwargs,
        },
        headers=headers,
    )


async def records(engine, model):
    async with AsyncSession(engine) as session:
        return list((await session.exec(select(model))).all())


async def test_public_reads_bootstrap_cookie_but_never_increment(client, db_engine):
    for _ in range(3):
        response, cookie = await bootstrap(client)
        assert response.json() == {
            "total_visits": 0,
            "started_at": None,
            "session_timeout_minutes": 30,
        }
        assert traffic.visitor_identity(cookie)
        assert response.headers["cache-control"] == "no-store"
    client.cookies.clear()
    response, _ = await bootstrap(client)
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "SameSite=lax" in response.headers["set-cookie"]
    assert not await records(db_engine, SiteTrafficTotal)
    assert not await records(db_engine, SiteVisit)


async def test_anonymous_visit_persists_private_metadata_and_only_exposes_count(client, db_engine):
    await bootstrap(client)
    response = await report(
        client,
        path="/tv",
        referrer_origin="https://search.example/find?secret=never-store#fragment",
        headers={"X-Forwarded-For": "203.0.113.99"},
    )
    assert response.status_code == 200
    assert response.json()["total_visits"] == 1
    assert response.json()["counted"] is True
    assert set(response.json()) == {
        "total_visits",
        "started_at",
        "session_timeout_minutes",
        "counted",
    }
    (visit,) = await records(db_engine, SiteVisit)
    assert visit.user_id is None
    assert visit.entry_path == "/tv"
    assert (visit.device_type, visit.browser, visit.operating_system) == (
        "desktop",
        "Chrome",
        "Windows",
    )
    assert visit.referrer_host == "search.example"
    assert visit.ip_hash == traffic.private_digest("ip", "127.0.0.1")
    assert visit.ip_address == "127.0.0.1"
    assert visit.ip_version == 4
    assert visit.ip_is_public is False
    assert visit.ip_source == "asgi"
    assert "secret" not in str(visit.model_dump())
    assert len(visit.visitor_hash) == 64


async def test_sliding_window_refresh_route_changes_and_midnight(client, db_engine, monkeypatch):
    await bootstrap(client)
    base = datetime(2026, 10, 19, 23, 45)
    for minutes, path, count in (
        (0, "/", 1),
        (29, "/login", 1),
        (58, "/workspace", 1),
        (88, "/tv", 1),
        (119, "/", 2),
    ):
        monkeypatch.setattr(
            traffic, "now", lambda minutes=minutes: base + timedelta(minutes=minutes)
        )
        response = await report(client, path=path)
        assert response.status_code == 200
        assert response.json()["total_visits"] == count
    assert len(await records(db_engine, SiteVisit)) == 2
    assert len(await records(db_engine, SiteVisitEvent)) == 5
    assert (await client.get(SUMMARY)).json()["total_visits"] == 2


async def test_event_replay_after_expiry_does_not_count_or_extend_visit(
    client, db_engine, monkeypatch
):
    await bootstrap(client)
    base = datetime(2026, 10, 19, 12)
    monkeypatch.setattr(traffic, "now", lambda: base)
    event = str(uuid4())
    assert (await report(client, event=event)).json()["counted"]
    monkeypatch.setattr(traffic, "now", lambda: base + timedelta(hours=2))
    replay = await report(client, event=event)
    assert replay.json()["total_visits"] == 1
    assert replay.json()["counted"] is False
    (visit,) = await records(db_engine, SiteVisit)
    assert visit.last_seen_at == base
    assert (await report(client)).json()["total_visits"] == 2


async def test_shared_ip_is_not_used_as_visitor_identity_and_event_reuse_is_rejected(
    client, db_engine
):
    _, first = await bootstrap(client)
    event = str(uuid4())
    assert (await report(client, cookie=first, event=event)).json()["total_visits"] == 1
    assert (await report(client, cookie=first, event=event, path="/tv")).status_code == 409
    client.cookies.clear()
    _, second = await bootstrap(client)
    assert first != second
    assert (await report(client, cookie=second, event=event)).status_code == 409
    assert (await report(client, cookie=second)).json()["total_visits"] == 2
    assert len(await records(db_engine, SiteVisit)) == 2


async def test_parallel_tabs_and_parallel_visitors_keep_total_consistent(client, db_engine):
    _, shared = await bootstrap(client)
    responses = await asyncio.gather(*(report(client, cookie=shared) for _ in range(12)))
    assert all(response.status_code == 200 for response in responses)
    assert sum(response.json()["counted"] for response in responses) == 1
    cookies = []
    for _ in range(6):
        client.cookies.clear()
        _, cookie = await bootstrap(client)
        cookies.append(cookie)
    responses = await asyncio.gather(*(report(client, cookie=cookie) for cookie in cookies))
    assert all(response.status_code == 200 for response in responses)
    assert (await client.get(SUMMARY)).json()["total_visits"] == 7
    assert len(await records(db_engine, SiteVisit)) == 7
    assert len(await records(db_engine, SiteVisitEvent)) == 18


async def test_login_can_associate_same_visit_without_recounting(client, db_engine):
    _, visitor_cookie = await bootstrap(client)
    assert (await report(client)).json()["total_visits"] == 1
    token = "traffic-test-login"
    async with AsyncSession(db_engine) as session:
        user = User(email="traffic@example.test", password_hash="test-placeholder")
        session.add(user)
        await session.flush()
        user_id = user.id
        session.add(
            UserSession(
                user_id=user_id,
                token_hash=token_sha256(token),
                expires_at=datetime.now() + timedelta(days=1),
            )
        )
        await session.commit()
    response = await report(
        client,
        path="/workspace",
        headers={
            "Cookie": f"{traffic.VISITOR_COOKIE}={visitor_cookie}; {settings.session_cookie_name}={token}",
        },
    )
    assert response.json()["total_visits"] == 1
    (visit,) = await records(db_engine, SiteVisit)
    assert visit.user_id == user_id


@pytest.mark.parametrize(
    "origin",
    ["https://attacker.example", "null", "http://testserver.evil", "http://testserver/extra"],
)
async def test_foreign_origins_cannot_write_counts(client, db_engine, origin):
    await bootstrap(client)
    assert (await report(client, headers={"Origin": origin})).status_code == 403
    assert not await records(db_engine, SiteVisit)


async def test_cookie_and_path_validation_and_basic_bot_filter(client, db_engine):
    assert (await report(client)).status_code == 422
    _, cookie = await bootstrap(client)
    assert (
        await report(client, cookie=cookie[:-1] + ("a" if cookie[-1] != "a" else "b"))
    ).status_code == 422
    assert (await report(client, path="/tv/admin")).status_code == 422
    assert (await report(client, headers={"User-Agent": "Googlebot/2.1"})).json()[
        "counted"
    ] is False
    assert not await records(db_engine, SiteVisit)
    assert (await report(client)).json()["total_visits"] == 1


async def test_redis_failure_does_not_lose_sql_counts_and_rate_limit_still_blocks(
    client, db_engine
):
    await bootstrap(client)

    async def unavailable():
        class OfflineRedis:
            async def eval(self, *args):
                raise ConnectionError("offline")

        yield OfflineRedis()

    previous = app.dependency_overrides[get_redis]
    app.dependency_overrides[get_redis] = unavailable
    try:
        assert (await report(client)).json()["total_visits"] == 1
    finally:
        app.dependency_overrides[get_redis] = previous
    async for redis in previous():
        key = "site-traffic:rate:ip:" + traffic.private_digest("ip", "127.0.0.1")
        await redis.set(key, 600, ex=60)
    assert (await report(client)).status_code == 429
    assert len(await records(db_engine, SiteVisitEvent)) == 1


@pytest.mark.parametrize(
    ("ua", "expected"),
    [
        (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Version/18.0 Mobile/15E148 Safari/604.1",
            ("mobile", "Safari", "iOS"),
        ),
        (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15) AppleWebKit/605.1.15 Mobile/15E148 Safari/604.1",
            ("tablet", "Safari", "iPadOS"),
        ),
        (CHROME + " Edg/130.0", ("desktop", "Edge", "Windows")),
        ("unknown-client", ("unknown", "unknown", "unknown")),
    ],
)
def test_device_classification_is_only_a_coarse_hint(ua, expected):
    assert traffic.device_info(ua) == expected


def test_migration_preserves_existing_data_and_has_one_head(tmp_path):
    path = tmp_path / "migration.db"
    environment = {
        **os.environ,
        "DATABASE_URL": f"sqlite+aiosqlite:///{path.as_posix()}",
        "APP_ENV": "dev",
    }

    def migrate(target, command="upgrade"):
        result = subprocess.run(
            [sys.executable, "-m", "alembic", command, target],
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        assert result.returncode == 0, result.stdout + result.stderr

    migrate("f1a2b3c4d5e6")
    with sqlite3.connect(path) as connection:
        connection.execute(
            "INSERT INTO users (id,email,email_verified_at,password_hash,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?)",
            (
                "existing",
                "existing@example.test",
                "2026-10-19",
                "placeholder",
                "active",
                "2026-10-19",
                "2026-10-19",
            ),
        )
    migrate("a2b3c4d5e6f7")
    with sqlite3.connect(path) as connection:
        connection.execute(
            "INSERT INTO site_visits (id,visitor_hash,started_at,last_seen_at,entry_path,ip_hash,device_type,browser,operating_system) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (
                "old-visit",
                "v" * 64,
                "2026-10-19",
                "2026-10-19",
                "/",
                "i" * 64,
                "desktop",
                "Chrome",
                "Windows",
            ),
        )
        connection.execute(
            "INSERT INTO site_visit_events (id,visitor_hash,visit_id,path,created_at) VALUES (?,?,?,?,?)",
            ("old-event", "v" * 64, "old-visit", "/", "2026-10-19"),
        )
        connection.execute(
            "INSERT INTO site_traffic_totals (id,total_visits,started_at,updated_at) VALUES (1,1,?,?)",
            ("2026-10-19", "2026-10-19"),
        )
    migrate("head")
    with sqlite3.connect(path) as connection:
        assert (
            connection.execute("SELECT email FROM users WHERE id='existing'").fetchone()[0]
            == "existing@example.test"
        )
        assert connection.execute("SELECT version_num FROM alembic_version").fetchall() == [
            ("b3c4d5e6f7a8",)
        ]
        for table in ("site_visits", "site_visit_events", "site_traffic_totals"):
            assert connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
            ).fetchone()
        assert connection.execute("SELECT total_visits FROM site_traffic_totals").fetchone()[0] == 1
        for table in ("site_visits", "site_visit_events"):
            assert connection.execute(
                f"SELECT ip_address,ip_version,ip_is_public,ip_source FROM {table}"
            ).fetchall() == [(None, None, None, None)]
    migrate("a2b3c4d5e6f7", "downgrade")
    migrate("head")
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT total_visits FROM site_traffic_totals").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM site_visits").fetchone()[0] == 1
