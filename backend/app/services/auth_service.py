"""认证服务：注册、两种登录、重置密码、Session 与 CSRF 编排。

关键安全点（实施计划 4.2 / 接口说明 1.3/1.4）：
- 邮箱不存在与密码错误统一返回 INVALID_CREDENTIALS，防止账号枚举与时序差异；
- Session 只保存 token 摘要；CSRF token 为 session 的 HMAC 签名，绑定当前会话；
- 登录与验证码都做 Redis 限流。
"""

import hashlib
import hmac
from datetime import timedelta

import redis.asyncio as aioredis
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.core.constants import Limits
from app.core.emails import normalize_email
from app.core.enums import EmailCodePurpose, UserStatus
from app.core.errors import (
    EMAIL_CODE_ATTEMPTS_EXCEEDED,
    EMAIL_CODE_EXPIRED,
    EMAIL_CODE_INVALID,
    INVALID_CREDENTIALS,
    RATE_LIMITED,
    AppError,
)
from app.core.security import hash_password, new_session_token, verify_password
from app.core.time import now
from app.db.models.user import User
from app.providers.email import get_email_provider
from app.repositories.sessions import SessionRepository
from app.repositories.users import UserRepository
from app.services import otp_service

# 登录限流（邮箱 + IP）：300 秒窗口内最多 5 次失败尝试
_LOGIN_WINDOW_SECONDS = 300
_LOGIN_MAX_ATTEMPTS = 5
_LOGIN_RATE_LUA = """
local n = redis.call('INCR', KEYS[1])
if n == 1 then
  redis.call('EXPIRE', KEYS[1], tonumber(ARGV[1]))
end
return n
"""

# 用于账号枚举防护的虚拟 Argon2 哈希（用合法的空盐值，仅用于常量时间比较）
_DUMMY_PASSWORD_HASH = None


def _dummy_hash() -> str:
    global _DUMMY_PASSWORD_HASH
    if _DUMMY_PASSWORD_HASH is None:
        _DUMMY_PASSWORD_HASH = hash_password("dummy-password-to-keep-runtime-constant")
    return _DUMMY_PASSWORD_HASH


def _login_rate_key(email: str, ip: str) -> str:
    return f"auth:login:{email}:{ip}"


def make_csrf_token(session_token: str) -> str:
    """生成与当前会话绑定的 CSRF token（session token 的 HMAC 签名）。"""
    return hmac.new(
        settings.app_secret.encode("utf-8"),
        session_token.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def verify_csrf_token(session_token: str, provided: str) -> bool:
    """校验 CSRF token 是否匹配当前会话。"""
    expected = make_csrf_token(session_token)
    return hmac.compare_digest(expected, provided)


def _validate_password(password: str) -> None:
    """校验密码长度。非法则抛 INVALID_CREDENTIALS 以统一文案。"""
    if not (Limits.PASSWORD_MIN_LENGTH <= len(password) <= Limits.PASSWORD_MAX_LENGTH):
        raise AppError(INVALID_CREDENTIALS)


async def _consume_or_raise(redis: aioredis.Redis, email: str, purpose: EmailCodePurpose, code: str) -> None:
    """校验验证码，并按结果抛对应错误码。"""
    result = await otp_service.consume_code(redis, email, purpose, code)
    if result == 1:
        return
    if result == 2:
        raise AppError(EMAIL_CODE_ATTEMPTS_EXCEEDED)
    if result == 0:
        raise AppError(EMAIL_CODE_EXPIRED)
    raise AppError(EMAIL_CODE_INVALID)


async def _enforce_login_rate(redis: aioredis.Redis, email: str, ip: str) -> None:
    count = await redis.eval(_LOGIN_RATE_LUA, 1, _login_rate_key(email, ip), str(_LOGIN_WINDOW_SECONDS))
    if int(count) > _LOGIN_MAX_ATTEMPTS:
        raise AppError(RATE_LIMITED)


class AuthService:
    def __init__(self, session: AsyncSession, redis: aioredis.Redis) -> None:
        self._users = UserRepository(session)
        self._sessions = SessionRepository(session)
        self._redis = redis
        self._email = get_email_provider()

    # ---- 发送验证码 ----
    async def send_email_code(self, email: str, purpose: EmailCodePurpose, ip: str) -> int:
        """规范化邮箱、限流、生成并发送验证码。返回再次发送等待秒数。"""
        normalized = normalize_email(email)  # ValueError 由上层转 422
        await otp_service.enforce_send_rate(self._redis, normalized, ip)
        code = otp_service.generate_code()
        await otp_service.store_code(self._redis, normalized, purpose, code)
        try:
            await self._email.send_code(normalized, code, purpose)
        except Exception:
            await otp_service.clear_code(self._redis, normalized, purpose)
            raise
        # 简化返回：固定 60 秒窗口的再次发送等待
        return 60

    # ---- 注册 ----
    async def register(self, email: str, code: str, password: str, ip: str, user_agent: str | None) -> tuple[User, str]:
        normalized = normalize_email(email)
        _validate_password(password)
        await _consume_or_raise(self._redis, normalized, EmailCodePurpose.REGISTER, code)
        user = await self._users.create(normalized, hash_password(password))
        token = await self._create_session(user.id, ip, user_agent)
        return user, token

    # ---- 密码登录 ----
    async def login_password(self, email: str, password: str, ip: str, user_agent: str | None) -> tuple[User, str]:
        normalized = normalize_email(email)
        await _enforce_login_rate(self._redis, normalized, ip)
        user = await self._users.find_by_email(normalized)
        if user is None:
            # 对不存在的用户执行一次固定 Argon2 校验，保持时序一致，降低账号枚举风险
            verify_password(password, _dummy_hash())
            raise AppError(INVALID_CREDENTIALS)
        if not verify_password(password, user.password_hash):
            raise AppError(INVALID_CREDENTIALS)
        self._ensure_active(user)
        token = await self._create_session(user.id, ip, user_agent)
        return user, token

    # ---- 验证码登录 ----
    async def login_email_code(self, email: str, code: str, ip: str, user_agent: str | None) -> tuple[User, str]:
        normalized = normalize_email(email)
        await _enforce_login_rate(self._redis, normalized, ip)
        await _consume_or_raise(self._redis, normalized, EmailCodePurpose.LOGIN, code)
        user = await self._users.find_by_email(normalized)
        if user is None:
            raise AppError(INVALID_CREDENTIALS)
        self._ensure_active(user)
        token = await self._create_session(user.id, ip, user_agent)
        return user, token

    # ---- 重置密码 ----
    async def reset_password(self, email: str, code: str, new_password: str) -> None:
        normalized = normalize_email(email)
        _validate_password(new_password)
        # 先消费验证码，非法则直接抛错；用户不存在时不暴露差异（仍返回 204）
        await _consume_or_raise(self._redis, normalized, EmailCodePurpose.RESET_PASSWORD, code)
        user = await self._users.find_by_email(normalized)
        if user is None:
            return
        await self._users.update_password(user, hash_password(new_password))
        await self._sessions.revoke_all_for_user(user.id)

    # ---- 会话 ----
    async def _create_session(self, user_id: str, ip: str | None, user_agent: str | None) -> str:
        token = new_session_token()
        expires_at = now() + timedelta(seconds=settings.session_ttl_seconds)
        await self._sessions.create(user_id, token, expires_at, ip, user_agent)
        return token

    async def get_authenticated_user(self, session_token: str) -> User:
        """根据会话 token 获取用户，无效则抛 AUTH_REQUIRED。"""
        from app.core.errors import AUTH_REQUIRED

        record = await self._sessions.find_active_by_token(session_token)
        if record is None:
            raise AppError(AUTH_REQUIRED)
        user = await self._users.get(record.user_id)
        if user is None or user.status != UserStatus.ACTIVE.value:
            raise AppError(AUTH_REQUIRED)
        return user

    async def logout(self, session_token: str) -> None:
        record = await self._sessions.find_active_by_token(session_token)
        if record is not None:
            await self._sessions.revoke(record.id)

    async def logout_all(self, user_id: str) -> None:
        await self._sessions.revoke_all_for_user(user_id)

    @staticmethod
    def _ensure_active(user: User) -> None:
        if user.status != UserStatus.ACTIVE.value:
            raise AppError(INVALID_CREDENTIALS)
