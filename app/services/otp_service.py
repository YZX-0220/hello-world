"""邮箱验证码（OTP）服务。

安全要点（实施计划 4.2）：
- 生成 6 位数字验证码，只把 HMAC 摘要存入 Redis，不存明文；
- 校验与删除在 Redis 中原子完成（Lua），避免并发重复消费；
- 错误尝试次数上限后再试即作废；
- 发送前对邮箱 + IP 做原子限流。
"""

import hashlib
import hmac
import secrets

import redis.asyncio as aioredis

from app.core.config import settings
from app.core.constants import Limits
from app.core.enums import EmailCodePurpose
from app.core.errors import RATE_LIMITED, AppError

# 发送限流（邮箱 + IP 维度）：60 秒窗口内允许 1 次
_SEND_WINDOW_SECONDS = 60
_SEND_MAX_PER_WINDOW = 1
# 跨窗口累计上限（如 300 秒内 3 次）作为额外保护，简化起见，仅用短窗口
_HMAC_DIGEST_ALGO = hashlib.sha256


def _otp_key(purpose: EmailCodePurpose, email: str) -> str:
    return f"otp:{purpose.value}:{email}"


def _attempts_key(purpose: EmailCodePurpose, email: str) -> str:
    return f"otp:attempts:{purpose.value}:{email}"


def _send_rate_key(email: str, ip: str) -> str:
    return f"otp:ratesend:{email}:{ip}"


def generate_code() -> str:
    """生成 6 位数字验证码。"""
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_code(code: str) -> str:
    """计算验证码的 HMAC 摘要（使用应用密钥作为签名密钥）。"""
    digest = hmac.new(
        settings.app_secret.encode("utf-8"),
        code.encode("utf-8"),
        _HMAC_DIGEST_ALGO,
    ).hexdigest()
    return digest


# Lua 脚本：原子消费验证码
# KEYS[1]=otp key, KEYS[2]=attempts key
# ARGV[1]=提交摘要, ARGV[2]=最大尝试次数, ARGV[3]=ttl 秒
# 返回 [status, remaining]；status: 0=不存在/过期, 1=成功, 3=错误且未超限
_CONSUME_LUA = """
local stored = redis.call('GET', KEYS[1])
if stored == false then
  return {0, 0}
end
if stored == ARGV[1] then
  redis.call('DEL', KEYS[1])
  redis.call('DEL', KEYS[2])
  return {1, 0}
end
local n = redis.call('INCR', KEYS[2])
redis.call('EXPIRE', KEYS[2], tonumber(ARGV[3]))
local max = tonumber(ARGV[2])
if n >= max then
  redis.call('DEL', KEYS[1])
  redis.call('DEL', KEYS[2])
  return {2, 0}
end
return {3, max - n}
"""

# Lua 脚本：发送限流（邮箱+IP 维度）
_SEND_RATE_LUA = """
local n = redis.call('INCR', KEYS[1])
if n == 1 then
  redis.call('EXPIRE', KEYS[1], tonumber(ARGV[1]))
end
return n
"""


async def store_code(
    redis: aioredis.Redis,
    email: str,
    purpose: EmailCodePurpose,
    code: str,
    ttl: int = Limits.EMAIL_CODE_TTL_SECONDS,
) -> None:
    """把验证码 HMAC 摘要写入 Redis，并设置 TTL。"""
    await redis.setex(_otp_key(purpose, email), int(ttl), hash_code(code))


async def consume_code(
    redis: aioredis.Redis,
    email: str,
    purpose: EmailCodePurpose,
    submitted_code: str,
    max_attempts: int = Limits.EMAIL_CODE_MAX_ATTEMPTS,
) -> int:
    """原子校验并消费验证码。

    返回：
    - 0：验证码不存在或已过期（EXPIRED）
    - 1：校验成功
    - 2：尝试次数超限（ATTEMPTS_EXCEEDED）
    - 3：验证码错误（INVALID，剩余次数见 attempts 计数）
    """
    result = await redis.eval(
        _CONSUME_LUA,
        2,
        _otp_key(purpose, email),
        _attempts_key(purpose, email),
        hash_code(submitted_code),
        str(max_attempts),
        str(Limits.EMAIL_CODE_TTL_SECONDS),
    )
    return int(result[0]) if result else 0


async def enforce_send_rate(
    redis: aioredis.Redis,
    email: str,
    ip: str,
    window: int = _SEND_WINDOW_SECONDS,
    max_per_window: int = _SEND_MAX_PER_WINDOW,
) -> None:
    """发送前限流（邮箱 + IP），超限抛 RATE_LIMITED。"""
    count = await redis.eval(_SEND_RATE_LUA, 1, _send_rate_key(email, ip), str(window))
    if int(count) > max_per_window:
        raise AppError(RATE_LIMITED)


async def clear_code(redis: aioredis.Redis, email: str, purpose: EmailCodePurpose) -> None:
    """删除验证码（如发送失败、重置后清理）。"""
    await redis.delete(_otp_key(purpose, email), _attempts_key(purpose, email))
