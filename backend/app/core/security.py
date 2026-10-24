"""安全工具。

覆盖：密码 Argon2 哈希、不透明 Session Token 生成与 SHA-256 摘要、常量时间比较。
首期提供认证所需的最小能力；视频 API 密钥加解密（Fernet）与 SSRF 防护在后续批次实现。
"""

import hashlib
import hmac
import secrets

from cryptography.fernet import Fernet, InvalidToken
from pwdlib import PasswordHash

# pwdlib 推荐的 Argon2 哈希器
_password_hasher = PasswordHash.recommended()


def hash_password(password: str) -> str:
    """生成 Argon2 密码哈希。Registers 不存储明文。"""
    return _password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """校验密码是否匹配，常量时间比较，用于对抗时序攻击。"""
    return _password_hasher.verify(password, password_hash)


def new_session_token() -> str:
    """生成不透明 Session Token（随机 32 字节）。数据库只保存其摘要。"""
    return secrets.token_urlsafe(32)


def token_sha256(token: str) -> str:
    """计算 Token 的 SHA-256 摘要，用于落库与校验，绝不保存原始 Token。"""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def new_csrf_token() -> str:
    """生成防跨站令牌的随机值，随后端 Cookie 下发，服务端校验签名与绑定。"""
    return secrets.token_urlsafe(32)


def constant_time_compare(a: str, b: str) -> bool:
    """常量时间字符串比较，用于验证码、Token 等敏感值的比对。"""
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


# ---- 视频 API 密钥加解密（Fernet，双钥轮换）----

def generate_fernet_key() -> str:
    """生成一把新的 Fernet 密钥（32 字节 urlsafe base64）。

    用于 CREDENTIAL_ENCRYPTION_KEYS 的初始生成与轮换新增。
    """
    return Fernet.generate_key().decode("utf-8")


def _parse_fernet_keys(raw_keys: str) -> list[Fernet]:
    """把逗号分隔的密钥字符串解析为 Fernet 实例列表。

    顺序即尝试顺序：第一把为「当前」密钥，后续为「上一把」，
    解密时依次尝试，从而支持平滑轮换（旧密文在新钥下仍能解开）。
    """
    keys = [k.strip() for k in raw_keys.split(",") if k.strip()]
    if not keys:
        raise ValueError("未配置 CREDENTIAL_ENCRYPTION_KEYS，无法加密/解密视频 API 凭据")
    instances: list[Fernet] = []
    for key in keys:
        try:
            instances.append(Fernet(key.encode("utf-8")))
        except (ValueError, TypeError) as exc:
            raise ValueError("CREDENTIAL_ENCRYPTION_KEYS 中存在无效 Fernet 密钥") from exc
    return instances


def encrypt_secret(plaintext: str, raw_keys: str) -> str:
    """用第一把（当前）密钥加密明文字符串，返回 Fernet token 文本。"""
    return _parse_fernet_keys(raw_keys)[0].encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_secret(token: str, raw_keys: str) -> str:
    """依次尝试各把密钥解密；全部失败则抛出 InvalidToken。

    密钥列表里同时保留上一把，可让运行中任务的旧密文在轮换后可读。
    """
    last_error: Exception | None = None
    for fernet in _parse_fernet_keys(raw_keys):
        try:
            return fernet.decrypt(token.encode("utf-8")).decode("utf-8")
        except InvalidToken as exc:
            last_error = exc
    raise InvalidToken("凭据解密失败：所有密钥均不匹配") from last_error
