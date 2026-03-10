from datetime import UTC, datetime

from sqlalchemy import delete, func, inspect, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import Session

from app.core.protocols import BaseClassifiedEmailRepository
from app.models.db import ClassifiedEmail


class SQLAlchemyClassifiedEmailRepository(BaseClassifiedEmailRepository):
    def __init__(self, *, session_maker: async_sessionmaker[AsyncSession]) -> None:
        self._session_maker = session_maker

    @staticmethod
    def _check_table_exists(session: Session) -> bool:
        return inspect(session.get_bind()).has_table(ClassifiedEmail.__tablename__)

    async def delete_expired(self) -> None:
        async with self._session_maker() as session:
            if not await session.run_sync(self._check_table_exists):
                return
            stmt = delete(ClassifiedEmail).where(
                ClassifiedEmail.expires_at < datetime.now(UTC)
            )
            await session.execute(stmt)
            await session.commit()

    async def bulk_create(
        self, *, emails: list[ClassifiedEmail]
    ) -> list[ClassifiedEmail]:
        async with self._session_maker() as session:
            session.add_all(emails)
            await session.commit()
            for email in emails:
                await session.refresh(email)
            return emails

    async def find_by_analysis_id(
        self, *, analysis_id: int
    ) -> list[ClassifiedEmail]:
        async with self._session_maker() as session:
            result = await session.execute(
                select(ClassifiedEmail).where(
                    ClassifiedEmail.analysis_id == analysis_id
                )
            )
            return list(result.scalars().all())

    async def find_by_ids_and_analysis(
        self, *, email_ids: list[int], analysis_id: int
    ) -> list[ClassifiedEmail]:
        async with self._session_maker() as session:
            result = await session.execute(
                select(ClassifiedEmail).where(
                    ClassifiedEmail.id.in_(email_ids),
                    ClassifiedEmail.analysis_id == analysis_id,
                )
            )
            return list(result.scalars().all())

    async def update_action_taken(
        self, *, email_id: int, action_taken: str
    ) -> None:
        async with self._session_maker() as session:
            await session.execute(
                update(ClassifiedEmail)
                .where(ClassifiedEmail.id == email_id)
                .values(action_taken=action_taken)
            )
            await session.commit()

    async def get_category_summary(
        self, *, analysis_id: int
    ) -> list[dict]:
        async with self._session_maker() as session:
            result = await session.execute(
                select(
                    ClassifiedEmail.category,
                    func.count().label("count"),
                )
                .where(ClassifiedEmail.analysis_id == analysis_id)
                .group_by(ClassifiedEmail.category)
            )
            return [{"category": row.category, "count": row.count} for row in result.all()]

    async def find_by_category_and_analysis(
        self, *, category: str, analysis_id: int
    ) -> list[ClassifiedEmail]:
        async with self._session_maker() as session:
            result = await session.execute(
                select(ClassifiedEmail).where(
                    ClassifiedEmail.category == category,
                    ClassifiedEmail.analysis_id == analysis_id,
                )
            )
            return list(result.scalars().all())

    async def find_by_sender_domain_and_analysis(
        self, *, sender_domain: str, analysis_id: int
    ) -> list[ClassifiedEmail]:
        async with self._session_maker() as session:
            result = await session.execute(
                select(ClassifiedEmail).where(
                    ClassifiedEmail.sender_domain == sender_domain,
                    ClassifiedEmail.analysis_id == analysis_id,
                )
            )
            return list(result.scalars().all())

    async def bulk_update_action_taken(
        self, *, email_ids: list[int], action_taken: str
    ) -> None:
        if not email_ids:
            return
        async with self._session_maker() as session:
            await session.execute(
                update(ClassifiedEmail)
                .where(ClassifiedEmail.id.in_(email_ids))
                .values(action_taken=action_taken)
            )
            await session.commit()

    async def bulk_update_category(
        self, *, analysis_id: int, from_category: str, to_category: str
    ) -> None:
        async with self._session_maker() as session:
            await session.execute(
                update(ClassifiedEmail)
                .where(
                    ClassifiedEmail.analysis_id == analysis_id,
                    ClassifiedEmail.category == from_category,
                )
                .values(category=to_category)
            )
            await session.commit()

    async def get_sender_summary(
        self, *, analysis_id: int, category: str | None = None
    ) -> list[dict]:
        async with self._session_maker() as session:
            query = (
                select(
                    ClassifiedEmail.sender_domain,
                    func.min(ClassifiedEmail.sender).label("sender_display"),
                    func.count().label("count"),
                    func.bool_or(ClassifiedEmail.has_unsubscribe).label("has_unsubscribe"),
                )
                .where(ClassifiedEmail.analysis_id == analysis_id)
            )
            if category is not None:
                query = query.where(ClassifiedEmail.category == category)
            query = query.group_by(ClassifiedEmail.sender_domain).order_by(func.count().desc())
            result = await session.execute(query)
            return [
                {
                    "sender_domain": row.sender_domain or "unknown",
                    "sender_display": row.sender_display or "unknown",
                    "count": row.count,
                    "has_unsubscribe": row.has_unsubscribe or False,
                }
                for row in result.all()
            ]
