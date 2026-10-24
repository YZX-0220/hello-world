"""Client IP provenance, both address families and private metadata persistence."""

from contextlib import asynccontextmanager
from uuid import uuid4

import httpx
import pytest
from app.core.client_ip import resolve_client_ip
from app.core.config import Settings, settings
from app.db.models.site_traffic import SiteVisit, SiteVisitEvent
from app.main import app
from fastapi import Request
from pydantic import ValidationError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

SUMMARY = "/api/v1/site-traffic/summary"
VISITS = "/api/v1/site-traffic/visits"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/130.0.0.0"


@pytest.fixture(autouse=True)
def ip_config(monkeypatch):
    monkeypatch.setattr(settings, "traffic_trusted_proxy_cidrs", "")
    monkeypatch.setattr(settings, "app_base_url", "http://testserver")
    monkeypatch.setattr(settings, "frontend_origin", "http://frontend.test")
    monkeypatch.setattr(settings, "cookie_secure", False)


def request_from(peer, **headers):
    return Request(
        {
            "type": "http",
            "method": "POST",
            "scheme": "http",
            "path": "/",
            "client": (peer, 1234) if peer else None,
            "headers": [
                (name.replace("_", "-").encode(), value.encode()) for name, value in headers.items()
            ],
        }
    )


@pytest.mark.parametrize(
    ("raw", "canonical", "version", "public"),
    [
        ("8.8.8.8", "8.8.8.8", 4, True),
        ("2001:4860:4860:0:0:0:0:8888", "2001:4860:4860::8888", 6, True),
        ("::ffff:8.8.8.8", "8.8.8.8", 4, True),
        ("127.0.0.1", "127.0.0.1", 4, False),
        ("10.1.2.3", "10.1.2.3", 4, False),
        ("::1", "::1", 6, False),
        ("fe80::1", "fe80::1", 6, False),
        ("224.0.0.1", "224.0.0.1", 4, False),
    ],
)
def test_address_normalization_and_public_flag(raw, canonical, version, public):
    ip = resolve_client_ip(request_from(raw))
    assert (ip.address, ip.version, ip.is_public, ip.source) == (canonical, version, public, "asgi")


@pytest.mark.parametrize("peer", [None, "unknown", "testclient", "fe80::1%eth0", "8.8.8.8:80"])
def test_missing_or_invalid_asgi_ip_is_not_fabricated(peer):
    ip = resolve_client_ip(request_from(peer, x_forwarded_for="8.8.8.8"))
    assert ip.address is None
    assert ip.source == "unavailable"


def test_untrusted_peer_cannot_forge_forwarded_or_real_ip():
    ip = resolve_client_ip(request_from("9.9.9.9", x_forwarded_for="8.8.8.8", x_real_ip="1.1.1.1"))
    assert ip.address == "9.9.9.9"
    assert ip.source == "asgi"


def test_trusted_proxy_chain_uses_nearest_untrusted_hop(monkeypatch):
    monkeypatch.setattr(
        settings, "traffic_trusted_proxy_cidrs", "127.0.0.1/32, 10.0.0.0/8, ::1/128"
    )
    ip = resolve_client_ip(
        request_from(
            "127.0.0.1",
            x_forwarded_for="spoofed-leftmost, 1.1.1.1, 10.0.0.7",
        )
    )
    assert ip.address == "1.1.1.1"
    assert ip.is_public is True
    assert ip.source == "forwarded"
    ipv6 = resolve_client_ip(request_from("::1", x_forwarded_for="2001:4860:4860::8888"))
    assert ipv6.version == 6
    real = resolve_client_ip(request_from("127.0.0.1", x_real_ip="8.8.8.8"))
    assert real.address == "8.8.8.8"
    assert real.source == "real_ip"


@pytest.mark.parametrize(
    "header", [None, "", "unknown", "10.0.0.7", "8.8.8.8, invalid", ",".join(["8.8.8.8"] * 33)]
)
def test_unresolved_trusted_proxy_is_not_mistaken_for_visitor(monkeypatch, header):
    monkeypatch.setattr(settings, "traffic_trusted_proxy_cidrs", "127.0.0.1/32,10.0.0.0/8")
    kwargs = {"x_forwarded_for": header} if header is not None else {}
    ip = resolve_client_ip(request_from("127.0.0.1", **kwargs))
    assert ip.address is None
    assert ip.source == "proxy_unresolved"


@pytest.mark.parametrize("cidrs", ["*", "0.0.0.0/0", "::/0", "bad-host", "127.0.0.1/32,typo"])
def test_invalid_or_unrestricted_proxy_trust_fails_configuration(cidrs):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, traffic_trusted_proxy_cidrs=cidrs)


@asynccontextmanager
async def browser_from(ip, target=app):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=target, client=(ip, 1234)),
        base_url="http://testserver",
        headers={"Origin": "http://testserver", "User-Agent": UA},
    ) as browser:
        yield browser


async def test_public_ips_are_private_in_sql_and_network_switches_do_not_recount(client, db_engine):
    async with browser_from("8.8.8.8") as browser:
        await browser.get(SUMMARY)
        cookie = browser.cookies.get("hw_visitor")
        first = await browser.post(VISITS, json={"event_id": str(uuid4()), "path": "/"})
        assert first.status_code == 200
        assert first.json()["total_visits"] == 1
    event_id = str(uuid4())
    async with browser_from("2001:4860:4860::8888") as browser:
        headers = {"Cookie": f"hw_visitor={cookie}", "X-Forwarded-For": "9.9.9.9"}
        response = await browser.post(
            VISITS, headers=headers, json={"event_id": event_id, "path": "/tv"}
        )
        assert response.status_code == 200
        assert response.json()["total_visits"] == 1
        assert "ip_address" not in response.text
        assert "8.8.8.8" not in response.text
        assert "2001:4860" not in response.text
        assert "ip_source" not in (await browser.get(SUMMARY)).text
    async with AsyncSession(db_engine) as session:
        visits = (await session.exec(select(SiteVisit))).all()
        assert len(visits) == 1
        assert visits[0].ip_address == "8.8.8.8"
        assert visits[0].ip_is_public is True
        event = await session.get(SiteVisitEvent, event_id)
        assert event.ip_address == "2001:4860:4860::8888"
        assert event.ip_version == 6
        assert event.ip_is_public is True
        assert event.ip_source == "asgi"


async def test_application_proxy_mode_records_forwarded_client(client, db_engine, monkeypatch):
    monkeypatch.setattr(settings, "traffic_trusted_proxy_cidrs", "127.0.0.1/32")
    async with browser_from("127.0.0.1") as browser:
        await browser.get(SUMMARY)
        result = await browser.post(
            VISITS,
            json={"event_id": str(uuid4()), "path": "/"},
            headers={"X-Forwarded-For": "spoofed, 1.1.1.1"},
        )
        assert result.status_code == 200
    async with AsyncSession(db_engine) as session:
        visit = (await session.exec(select(SiteVisit))).one()
        assert visit.ip_address == "1.1.1.1"
        assert visit.ip_source == "forwarded"


async def test_uvicorn_proxy_mode_preserves_prevalidated_asgi_address(client, db_engine):
    middleware = ProxyHeadersMiddleware(app, trusted_hosts="127.0.0.1")
    async with browser_from("127.0.0.1", target=middleware) as browser:
        await browser.get(SUMMARY)
        result = await browser.post(
            VISITS,
            json={"event_id": str(uuid4()), "path": "/"},
            headers={"X-Forwarded-For": "8.8.8.8, 1.1.1.1"},
        )
        assert result.status_code == 200
    async with AsyncSession(db_engine) as session:
        visit = (await session.exec(select(SiteVisit))).one()
        assert visit.ip_address == "1.1.1.1"
        assert visit.ip_source == "asgi"


async def test_browser_cannot_supply_its_own_ip_or_country(client, db_engine):
    await client.get(SUMMARY)
    result = await client.post(
        VISITS,
        json={"event_id": str(uuid4()), "path": "/", "ip_address": "8.8.8.8", "country_code": "US"},
        headers={"Origin": "http://testserver", "User-Agent": UA},
    )
    assert result.status_code == 422
    assert (await client.get(SUMMARY)).json()["total_visits"] == 0
    async with AsyncSession(db_engine) as session:
        assert not (await session.exec(select(SiteVisit))).all()


async def test_missing_client_header_does_not_count_proxy_as_visitor_or_block_counts(
    client,
    db_engine,
    monkeypatch,
):
    monkeypatch.setattr(settings, "traffic_trusted_proxy_cidrs", "127.0.0.1/32")
    async with browser_from("127.0.0.1") as browser:
        await browser.get(SUMMARY)
        result = await browser.post(VISITS, json={"event_id": str(uuid4()), "path": "/"})
        assert result.status_code == 200
        assert result.json()["total_visits"] == 1
    async with AsyncSession(db_engine) as session:
        visit = (await session.exec(select(SiteVisit))).one()
        assert visit.ip_address is None
        assert visit.ip_source == "proxy_unresolved"
        assert visit.ip_is_public is None
