"""用户仓储：用户查询与创建（含邮箱唯一约束冲突处理）。"""

from sqlalchemy.exc import IntegrityError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.errors import EMAIL_ALREADY_REGISTERED, AppError
from app.core.time import now
from app.db.models.user import User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, user_id: str) -> User | None:
        return await self._session.get(User, user_id)

    async def find_by_email(self, email: str) -> User | None:
        """按规范化后的邮箱查找。email 需先由调用方规范化。"""
        stmt = select(User).where(User.email == email)
        result = await self._session.exec(stmt)
        return result.first()

    async def create(self, email: str, password_hash: str) -> User:
        """创建用户。邮箱已存在（竞态下唯一约束冲突）转成 EMAIL_ALREADY_REGISTERED。"""
        user = User(
            email=email,
            password_hash=password_hash,
            email_verified_at=now(),
        )
        self._session.add(user)
        try:
            await self._session.commit()
        except IntegrityError:
            await self._session.rollback()
            raise AppError(EMAIL_ALREADY_REGISTERED) from None
        await self._session.refresh(user)
        return user

    async def update_password(self, user: User, password_hash: str) -> None:
        """更新用户密码哈希。"""
        user.password_hash = password_hash
        user.updated_at = now()
        await self._session.commit()
