"""会话仓储：创建 / 校验 / 撤销 Session。"""

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.security import token_sha256
from app.core.time import now
from app.db.models.user import UserSession


class SessionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self, user_id: str, token: str, expires_at, ip_address: str | None, user_agent: str | None
    ) -> UserSession:
        """创建会话，只保存 token 的 SHA-256 摘要。"""
        record = UserSession(
            user_id=user_id,
            token_hash=token_sha256(token),
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self._session.add(record)
        await self._session.commit()
        await self._session.refresh(record)
        return record

    async def find_active_by_token(self, token: str) -> UserSession | None:
        """按 token 查找有效会话（未过期、未撤销）。"""
        digest = token_sha256(token)
        stmt = (
            select(UserSession)
            .where(
                UserSession.token_hash == digest,
                UserSession.expires_at > now(),
                UserSession.revoked_at.is_(None),  # type: ignore[union-attr]
            )
        )
        result = await self._session.exec(stmt)
        return result.first()

    async def revoke(self, session_id: str) -> None:
        record = await self._session.get(UserSession, session_id)
        if record is not None and record.revoked_at is None:
            record.revoked_at = now()
            await self._session.commit()

    async def revoke_all_for_user(self, user_id: str) -> None:
        """撤销用户全部未撤销会话（重置密码后调用）。"""
        stmt = select(UserSession).where(
            UserSession.user_id == user_id,
            UserSession.revoked_at.is_(None),  # type: ignore[union-attr]
        )
        result = await self._session.exec(stmt)
        for record in result.all():
            record.revoked_at = now()
        await self._session.commit()
