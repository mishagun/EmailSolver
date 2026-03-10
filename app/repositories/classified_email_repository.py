from datetime import UTC, datetime

from sqlalchemy import delete, func, inspect, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import Session

from app.core.protocols import BaseClassifiedEmailRepository
from app.models.db import ClassifiedEmail, EmailActionHistory


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
        self, *, email_ids: list[int], action_taken: str | None
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

    async def bulk_record_action(
        self, *, email_ids: list[int], action: str
    ) -> None:
        if not email_ids:
            return
        async with self._session_maker() as session:
            session.add_all([
                EmailActionHistory(classified_email_id=eid, action=action)
                for eid in email_ids
            ])
            await session.commit()

    async def pop_last_action(
        self, *, email_ids: list[int]
    ) -> dict[int, str | None]:
        if not email_ids:
            return {}
        async with self._session_maker() as session:
            # Get the most recent history entry per email
            latest_subq = (
                select(
                    EmailActionHistory.classified_email_id,
                    func.max(EmailActionHistory.id).label("max_id"),
                )
                .where(EmailActionHistory.classified_email_id.in_(email_ids))
                .group_by(EmailActionHistory.classified_email_id)
                .subquery()
            )
            latest_result = await session.execute(
                select(EmailActionHistory)
                .join(
                    latest_subq,
                    EmailActionHistory.id == latest_subq.c.max_id,
                )
            )
            latest_entries = list(latest_result.scalars().all())

            # Delete those entries
            if latest_entries:
                await session.execute(
                    delete(EmailActionHistory)
                    .where(EmailActionHistory.id.in_([e.id for e in latest_entries]))
                )

            # Now find the new most recent action per email (previous action)
            prev_subq = (
                select(
                    EmailActionHistory.classified_email_id,
                    func.max(EmailActionHistory.id).label("max_id"),
                )
                .where(EmailActionHistory.classified_email_id.in_(email_ids))
                .group_by(EmailActionHistory.classified_email_id)
                .subquery()
            )
            prev_result = await session.execute(
                select(EmailActionHistory)
                .join(
                    prev_subq,
                    EmailActionHistory.id == prev_subq.c.max_id,
                )
            )
            prev_by_email = {
                e.classified_email_id: e.action
                for e in prev_result.scalars().all()
            }

            # Build result: email_id -> previous action (or None if no history left)
            result_map: dict[int, str | None] = {}
            for eid in email_ids:
                result_map[eid] = prev_by_email.get(eid)

            # Update action_taken on each email to the previous action
            for eid, prev_action in result_map.items():
                await session.execute(
                    update(ClassifiedEmail)
                    .where(ClassifiedEmail.id == eid)
                    .values(action_taken=prev_action)
                )

            await session.commit()
            return result_map
