from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.protocols import BaseUserRepository
from app.models.db import User


class SQLAlchemyUserRepository(BaseUserRepository):
    def __init__(self, *, session: AsyncSession) -> None:
        self._session = session

    async def find_by_id(self, *, user_id: int) -> User | None:
        result = await self._session.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def find_by_google_id(self, *, google_id: str) -> User | None:
        result = await self._session.execute(
            select(User).where(User.google_id == google_id)
        )
        return result.scalar_one_or_none()

    async def save(self, *, user: User) -> User:
        self._session.add(user)
        await self._session.commit()
        await self._session.refresh(user)
        return user
