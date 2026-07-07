from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import TelegramUser
from app.infra.database import flush_and_refresh
from app.models.user import User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: int) -> User | None:
        return await self._session.get(User, user_id)

    async def get_by_username(self, username: str) -> User | None:
        normalized = username.lstrip("@").lower()
        result = await self._session.execute(
            select(User).where(User.username == normalized)
        )
        return result.scalar_one_or_none()

    async def upsert_from_telegram(self, tg_user: TelegramUser) -> User:
        user = await self.get_by_id(tg_user.id)
        if user is None:
            user = User(
                id=tg_user.id,
                username=tg_user.username.lower() if tg_user.username else None,
                first_name=tg_user.first_name,
                last_name=tg_user.last_name,
            )
            self._session.add(user)
            await flush_and_refresh(self._session, user)
            return user

        user.username = tg_user.username.lower() if tg_user.username else user.username
        user.first_name = tg_user.first_name
        user.last_name = tg_user.last_name
        await self._session.flush()
        return user
