"""Database-authoritative visit counting; no Redis counter can lose the total."""

import asyncio
import hashlib
import hmac
import re
import secrets
import time
from datetime import timedelta
from urllib.parse import urlsplit

from fastapi import Request, Response
from redis.exceptions import RedisError
from sqlalchemy import func, update
from sqlalchemy.dialects.sqlite import insert
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.client_ip import resolve_client_ip
from app.core.config import settings
from app.core.enums import UserStatus
from app.core.errors import (
    IDEMPOTENCY_KEY_REUSED,
    RATE_LIMITED,
    TRAFFIC_COOKIE_REQUIRED,
    TRAFFIC_ORIGIN_INVALID,
    AppError,
)
from app.core.security import token_sha256
from app.core.time import now
from app.db.models.site_traffic import SiteTrafficTotal, SiteVisit, SiteVisitEvent
from app.db.models.user import User, UserSession
from app.schemas.site_traffic import SiteTrafficSummary, TrackSiteVisit, TrackSiteVisitResult

VISITOR_COOKIE = "hw_visitor"
COOKIE_PATH = "/api/v1/site-traffic"
COOKIE_TTL = 365 * 24 * 60 * 60
IDLE_TIMEOUT = timedelta(minutes=30)
_BOT = re.compile(
    r"bot\b|crawler|spider|headlesschrome|curl/|wget/|python-requests/|python-httpx/", re.I
)
_RATE_SCRIPT = """
local n = redis.call('INCR', KEYS[1])
if n == 1 then redis.call('EXPIRE', KEYS[1], 60) end
return n
"""


def private_digest(kind: str, value: str) -> str:
    return hmac.new(
        settings.app_secret.encode(), f"site-traffic:{kind}:{value}".encode(), hashlib.sha256
    ).hexdigest()


def visitor_identity(cookie: str | None) -> str | None:
    if not cookie or len(cookie) > 160:
        return None
    try:
        identity, issued, signature = cookie.split(".")
        timestamp = int(issued)
    except (ValueError, TypeError):
        return None
    if not re.fullmatch(r"[A-Za-z0-9_-]{32}", identity):
        return None
    age = time.time() - timestamp
    if not -60 <= age <= COOKIE_TTL:
        return None
    expected = private_digest("cookie", f"{identity}.{issued}")
    return identity if hmac.compare_digest(expected, signature) else None


def ensure_visitor_cookie(request: Request, response: Response) -> None:
    if visitor_identity(request.cookies.get(VISITOR_COOKIE)):
        return
    identity, issued = secrets.token_urlsafe(24), str(int(time.time()))
    signature = private_digest("cookie", f"{identity}.{issued}")
    response.set_cookie(
        VISITOR_COOKIE,
        f"{identity}.{issued}.{signature}",
        max_age=COOKIE_TTL,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path=COOKIE_PATH,
    )


def _origin(value: str) -> str | None:
    try:
        parsed = urlsplit(value)
        if (
            parsed.scheme not in ("http", "https")
            or not parsed.hostname
            or parsed.username
            or parsed.password
        ):
            return None
        port = parsed.port
        host = parsed.hostname.lower()
        if ":" in host:
            host = f"[{host}]"
        suffix = f":{port}" if port and port != (443 if parsed.scheme == "https" else 80) else ""
        return f"{parsed.scheme}://{host}{suffix}"
    except ValueError:
        return None


def validate_traffic_origin(request: Request) -> None:
    # Public writes use an anonymous cookie; they must not require a login CSRF token.
    # Only browser same-origin requests or explicitly configured frontend origins pass.
    origin = request.headers.get("origin")
    allowed = {_origin(value.strip()) for value in settings.frontend_origin.split(",")}
    allowed.add(_origin(settings.app_base_url))
    allowed.discard(None)
    if origin:
        if _origin(origin) not in allowed or origin.rstrip("/") != _origin(origin):
            raise AppError(TRAFFIC_ORIGIN_INVALID)
    elif request.headers.get("sec-fetch-site") != "same-origin":
        raise AppError(TRAFFIC_ORIGIN_INVALID)


def device_info(user_agent: str) -> tuple[str, str, str]:
    ua = user_agent[:500].lower()
    tablet = (
        "ipad" in ua
        or ("macintosh" in ua and "mobile" in ua)
        or ("android" in ua and "mobile" not in ua)
    )
    mobile = "mobile" in ua or "iphone" in ua or "ipod" in ua
    device = (
        "tablet"
        if tablet
        else "mobile"
        if mobile
        else "desktop"
        if any(name in ua for name in ("windows", "macintosh", "x11", "linux"))
        else "unknown"
    )
    os = next(
        (
            name
            for marker, name in (
                ("iphone", "iOS"),
                ("ipad", "iPadOS"),
                ("android", "Android"),
                ("windows", "Windows"),
                ("macintosh", "iPadOS" if tablet else "macOS"),
                ("linux", "Linux"),
            )
            if marker in ua
        ),
        "unknown",
    )
    browser = next(
        (
            name
            for markers, name in (
                (("edg/", "edga/", "edgios/"), "Edge"),
                (("opr/", "opera"), "Opera"),
                (("samsungbrowser/",), "Samsung Internet"),
                (("firefox/", "fxios/"), "Firefox"),
                (("chrome/", "crios/"), "Chrome"),
                (("safari/",), "Safari"),
            )
            if any(marker in ua for marker in markers)
        ),
        "unknown",
    )
    return device, browser, os


def referrer_host(value: str | None, request: Request) -> str | None:
    # Never persist full URLs, query strings, hash routes or credentials.
    origin = _origin(value or "")
    own = {_origin(settings.app_base_url), _origin(str(request.base_url))}
    own.update(_origin(item.strip()) for item in settings.frontend_origin.split(","))
    if not origin or origin in own:
        return None
    host = urlsplit(origin).hostname
    return host if host and len(host) <= 253 else None


async def limit_traffic(redis, request: Request, identity: str) -> None:
    # This is a basic abuse filter, not proof that a visitor is a human.
    ip = resolve_client_ip(request).address or "unknown"
    for kind, value, maximum in (("ip", ip, 600), ("visitor", identity, 120)):
        try:
            async with asyncio.timeout(0.3):
                key = f"site-traffic:rate:{kind}:{private_digest(kind, value)}"
                count = await redis.eval(_RATE_SCRIPT, 1, key)
            if int(count) > maximum:
                raise AppError(RATE_LIMITED)
        except (RedisError, TimeoutError, OSError):
            # Redis is optional for traffic counts; durable deduplication remains in SQL.
            return


class SiteTrafficService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def summary(self) -> SiteTrafficSummary:
        total = await self.session.get(SiteTrafficTotal, 1)
        return SiteTrafficSummary(
            total_visits=total.total_visits if total else 0,
            started_at=total.started_at if total else None,
        )

    async def _user_id(self, request: Request, timestamp) -> str | None:
        token = request.cookies.get(settings.session_cookie_name)
        if not token:
            return None
        result = await self.session.exec(
            select(UserSession.user_id)
            .join(User, col(User.id) == col(UserSession.user_id))
            .where(
                UserSession.token_hash == token_sha256(token),
                UserSession.expires_at > timestamp,
                col(UserSession.revoked_at).is_(None),
                User.status == UserStatus.ACTIVE.value,
            )
        )
        return result.first()

    async def track(self, request: Request, payload: TrackSiteVisit) -> TrackSiteVisitResult:
        validate_traffic_origin(request)
        identity = visitor_identity(request.cookies.get(VISITOR_COOKIE))
        if identity is None:
            raise AppError(TRAFFIC_COOKIE_REQUIRED)
        if _BOT.search(request.headers.get("user-agent", "")[:500]):
            return TrackSiteVisitResult(**(await self.summary()).model_dump(), counted=False)
        timestamp = now()
        client_ip = resolve_client_ip(request)
        visitor_hash = private_digest("visitor", identity)
        event_id = str(payload.event_id)
        try:
            # This must be the FIRST SQL statement of a write request: acquire SQLite's
            # write reservation before reading the event/visit. Competing tabs serialize
            # here instead of both observing an expired/missing visit.
            await self.session.execute(
                insert(SiteTrafficTotal)
                .values(
                    id=1,
                    total_visits=0,
                    started_at=None,
                    updated_at=timestamp,
                )
                .on_conflict_do_nothing(index_elements=["id"])
            )
            event = await self.session.get(SiteVisitEvent, event_id)
            if event:
                if event.visitor_hash != visitor_hash or event.path != payload.path:
                    raise AppError(IDEMPOTENCY_KEY_REUSED)
                summary = await self.summary()
                await self.session.commit()
                return TrackSiteVisitResult(**summary.model_dump(), counted=False)
            visit = (
                await self.session.exec(
                    select(SiteVisit)
                    .where(
                        SiteVisit.visitor_hash == visitor_hash,
                    )
                    .order_by(col(SiteVisit.last_seen_at).desc(), col(SiteVisit.id).desc())
                    .limit(1)
                )
            ).first()
            user_id = await self._user_id(request, timestamp)
            counted = visit is None or timestamp - visit.last_seen_at > IDLE_TIMEOUT
            if counted:
                device, browser, os = device_info(request.headers.get("user-agent", ""))
                ip = client_ip.address
                visit = SiteVisit(
                    visitor_hash=visitor_hash,
                    user_id=user_id,
                    started_at=timestamp,
                    last_seen_at=timestamp,
                    entry_path=payload.path,
                    ip_hash=private_digest("ip", ip) if ip else None,
                    ip_address=client_ip.address,
                    ip_version=client_ip.version,
                    ip_is_public=client_ip.is_public,
                    ip_source=client_ip.source,
                    device_type=device,
                    browser=browser,
                    operating_system=os,
                    referrer_host=referrer_host(payload.referrer_origin, request),
                )
                self.session.add(visit)
                await self.session.execute(
                    update(SiteTrafficTotal)
                    .where(col(SiteTrafficTotal.id) == 1)
                    .values(
                        total_visits=col(SiteTrafficTotal.total_visits) + 1,
                        started_at=func.coalesce(SiteTrafficTotal.started_at, timestamp),
                        updated_at=timestamp,
                    )
                )
            else:
                assert visit is not None
                visit.last_seen_at = max(visit.last_seen_at, timestamp)
                if visit.user_id is None and user_id:
                    visit.user_id = user_id
                self.session.add(visit)
            await self.session.flush()
            self.session.add(
                SiteVisitEvent(
                    id=event_id,
                    visitor_hash=visitor_hash,
                    visit_id=visit.id,
                    path=payload.path,
                    ip_address=client_ip.address,
                    ip_version=client_ip.version,
                    ip_is_public=client_ip.is_public,
                    ip_source=client_ip.source,
                    created_at=timestamp,
                )
            )
            await self.session.flush()
            # refresh avoids an identity-map value left over from a previous summary read.
            total = await self.session.get(SiteTrafficTotal, 1, populate_existing=True)
            assert total is not None
            result = TrackSiteVisitResult(
                total_visits=total.total_visits,
                started_at=total.started_at,
                counted=counted,
            )
            await self.session.commit()
            return result
        except Exception:
            await self.session.rollback()
            raise
