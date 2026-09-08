"""SSRF 防护：对外部视频/中转地址做结构校验与 DNS 解析后的安全判定。

依据《实施计划》4.8 中转地址安全：
  - 仅允许 HTTPS，无端口时默认 443；
  - 禁止 URL 携带用户名和密码；
  - 主机名规范化并限制长度；
  - DNS 解析后拒绝回环、私网、链路本地、保留、多播、未指定与云元数据地址；
  - 实际请求前会【再次】调用 validate_public_host，避免 TOCTOU。

本模块只返回「结构已被校验」的结果，真正的请求超时/trust_env/跳转等由 Provider 层落地。
"""

import ipaddress
import socket
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

_MAX_HOST_LEN = 253
_DEFAULT_HTTPS_PORT = 443
# 常见云厂商元数据/IPv6 中继地址，即使落在允许网段也显式拒绝
_DENY_ADDRS = {"169.254.169.254", "169.254.170.2", "0.0.0.0"}


class UnsafeUrlError(ValueError):
    """地址不符合安全要求或被判定为不可信。message 为可展示的中文说明。"""


@dataclass(frozen=True)
class CheckedBaseUrl:
    """一次地址校验通过后的结果，供 Service/Provider 使用。"""

    normalized: str  # 规范化后的 HTTPS 地址（含路径前缀，去尾斜杠）
    host: str  # 小写主机名
    port: int  # 实际连接端口（未给出时取 443）
    resolved_ip: str  # 首个成功解析的 IP（校验通过）
    path_prefix: str  # 路径前缀，如 /v1，可能为空串


def _is_public_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """判断解析出的 IP 是否为可访问的公网地址。

    对任一 IP，只要落在下列任一不安全段即判为不可信：
      - 回环 / 私网 / 链路本地 / 保留 / 多播 / 未指定；
      - 云元数据等显式黑名单地址。
    """
    if str(ip) in _DENY_ADDRS:
        return False
    if ip.version == 4:
        return not (
            ip.is_loopback
            or ip.is_private
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        )
    return not (
        ip.is_loopback
        or ip.is_link_local
        or ip.is_site_local
        or ip.is_private
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def normalize_base_url(url: str) -> str:
    """规范化中转 Base URL。

    负责结构校验：仅 HTTPS、禁用户名密码、主机名小写且限长、去掉默认 443 端口与末尾斜杠。
    不做 DNS 解析（见 validate_public_host）。
    """
    if not url or not url.strip():
        raise UnsafeUrlError("接口地址为空")
    raw = url.strip()
    try:
        parsed = urlsplit(raw)
    except ValueError as exc:  # 如端口非法
        raise UnsafeUrlError("接口地址格式非法") from exc

    if parsed.scheme != "https":
        raise UnsafeUrlError("接口地址仅支持 HTTPS")
    if parsed.username is not None or parsed.password is not None:
        raise UnsafeUrlError("接口地址不允许携带用户名或密码")
    if not parsed.hostname:
        raise UnsafeUrlError("接口地址缺失主机名")

    host = parsed.hostname.lower()
    if len(host) > _MAX_HOST_LEN:
        raise UnsafeUrlError("接口地址主机名过长")

    try:
        port = parsed.port  # 缺省时 None；非法端口此时抛出
    except ValueError as exc:
        raise UnsafeUrlError("接口地址端口非法") from exc

    netloc = host if port is None or port == _DEFAULT_HTTPS_PORT else f"{host}:{port}"
    path = parsed.path.rstrip("/")
    return urlunsplit(("https", netloc, path, "", ""))


def _default_resolver(host: str) -> list[str]:
    """真实 DNS 解析，返回去重的 IP 字符串列表；失败抛 UnsafeUrlError。"""
    try:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise UnsafeUrlError("接口地址无法解析主机名") from exc
    addrs: list[str] = []
    for family, _socktype, _proto, _canon, sockaddr in infos:
        if family in (socket.AF_INET, socket.AF_INET6):
            addrs.append(str(sockaddr[0]))
    return list(dict.fromkeys(addrs))


def validate_public_host(host: str, resolver: Callable[[str], list[str]] | None = None) -> str:
    """解析主机名并校验全部解析结果均为安全公网地址。

    任一条解析命中不安全段即拒绝（因为实际连接可能命中该 IP）。
    resolver 可注入以便测试；默认走真实 DNS。
    返回首个安全 IP，供调用方用于连接。
    """
    resolve = resolver or _default_resolver
    addrs = resolve(host)
    if not addrs:
        raise UnsafeUrlError("接口地址无可解析的地址")
    for addr in addrs:
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError as exc:
            raise UnsafeUrlError("接口地址包含无法识别的地址") from exc
        if not _is_public_ip(ip):
            raise UnsafeUrlError("接口地址指向内网或云元数据等不安全地址")
    return addrs[0]


def check_base_url(url: str, resolver: Callable[[str], list[str]] | None = None) -> CheckedBaseUrl:
    """完整校验：结构规范化 + DNS 安全判定，返回可供 Service/Provider 使用的结果。"""
    normalized = normalize_base_url(url)
    parsed = urlsplit(normalized)
    host = parsed.hostname  # 已小写
    assert host is not None, "normalize_base_url 已保证主机名非空"
    port = parsed.port or _DEFAULT_HTTPS_PORT
    resolved = validate_public_host(host, resolver)
    return CheckedBaseUrl(
        normalized=normalized,
        host=host,
        port=port,
        resolved_ip=resolved,
        path_prefix=parsed.path.rstrip("/"),
    )


__all__ = [
    "CheckedBaseUrl",
    "UnsafeUrlError",
    "check_base_url",
    "normalize_base_url",
    "validate_public_host",
]
