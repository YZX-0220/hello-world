"""Normalize client IPs; forwarded values are accepted only behind configured proxies."""

from dataclasses import dataclass
from functools import lru_cache
from ipaddress import IPv4Address, IPv4Network, IPv6Address, IPv6Network, ip_address, ip_network

from fastapi import Request

from app.core.config import settings

IPAddress = IPv4Address | IPv6Address
IPNetwork = IPv4Network | IPv6Network


@dataclass(frozen=True)
class ClientIP:
    address: str | None
    version: int | None
    is_public: bool | None
    source: str


def _parse(value: str | None) -> IPAddress | None:
    if not value or len(value) > 64 or "%" in value:
        return None
    try:
        parsed = ip_address(value.strip())
    except ValueError:
        return None
    if isinstance(parsed, IPv6Address) and parsed.ipv4_mapped:
        return parsed.ipv4_mapped
    return parsed


@lru_cache(maxsize=16)
def _networks(raw: str) -> tuple[IPNetwork, ...]:
    return tuple(ip_network(item.strip(), strict=False) for item in raw.split(",") if item.strip())


def _result(address: IPAddress | None, source: str) -> ClientIP:
    if address is None:
        return ClientIP(None, None, None, source)
    return ClientIP(
        str(address),
        address.version,
        address.is_global and not address.is_multicast,
        source,
    )


def resolve_client_ip(request: Request) -> ClientIP:
    # ASGI may already contain Uvicorn's trusted-proxy result. Do not re-trust
    # request headers unless this immediate address is explicitly configured.
    peer = _parse(request.client.host if request.client else None)
    if peer is None:
        return _result(None, "unavailable")
    networks = _networks(settings.traffic_trusted_proxy_cidrs)

    def trusted(address: IPAddress) -> bool:
        return any(address in network for network in networks)

    if not trusted(peer):
        return _result(peer, "asgi")
    forwarded = ",".join(request.headers.getlist("x-forwarded-for"))
    if forwarded:
        chain = forwarded.split(",")
        if len(forwarded) > 2048 or len(chain) > 32:
            return _result(None, "proxy_unresolved")
        # Stop at the first untrusted hop from the right. Never pick a caller's
        # arbitrary left-most value across an untrusted boundary.
        for value in reversed(chain):
            candidate = _parse(value)
            if candidate is None:
                return _result(None, "proxy_unresolved")
            if not trusted(candidate):
                return _result(candidate, "forwarded")
        return _result(None, "proxy_unresolved")
    real_ip = _parse(request.headers.get("x-real-ip"))
    if real_ip and not trusted(real_ip):
        return _result(real_ip, "real_ip")
    # A known proxy without a usable client header must not become a "visitor IP".
    return _result(None, "proxy_unresolved")
