from datetime import datetime

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from app.core.protocols import BaseAnalysisRepository
from app.models.db import Analysis, ClassifiedEmail


class SQLAlchemyAnalysisRepository(BaseAnalysisRepository):
    def __init__(
        self,
        *,
        session: AsyncSession | None = None,
        session_maker: async_sessionmaker[AsyncSession] | None = None,
    ) -> None:
        self._session = session
        self._session_maker = session_maker

    async def find_by_id_and_user(
        self, *, analysis_id: int, user_id: int
    ) -> Analysis | None:
        result = await self._session.execute(
            select(Analysis).where(
                Analysis.id == analysis_id, Analysis.user_id == user_id
            )
        )
        return result.scalar_one_or_none()

    async def delete_with_emails(self, *, analysis: Analysis) -> None:
        await self._session.execute(
            delete(ClassifiedEmail).where(
                ClassifiedEmail.analysis_id == analysis.id
            )
        )
        await self._session.delete(analysis)
        await self._session.commit()

    async def create(self, *, analysis: Analysis) -> Analysis:
        self._session.add(analysis)
        await self._session.commit()
        await self._session.refresh(analysis)
        return analysis

    async def list_by_user(self, *, user_id: int) -> list[Analysis]:
        result = await self._session.execute(
            select(Analysis)
            .where(Analysis.user_id == user_id)
            .order_by(Analysis.created_at.desc())
        )
        return list(result.scalars().all())

    async def update_status(
        self,
        *,
        analysis_id: int,
        status: str,
        processed_emails: int | None = None,
        total_emails: int | None = None,
        error_message: str | None = None,
        completed_at: datetime | None = None,
    ) -> None:
        values: dict = {"status": status}
        if processed_emails is not None:
            values["processed_emails"] = processed_emails
        if total_emails is not None:
            values["total_emails"] = total_emails
        if error_message is not None:
            values["error_message"] = error_message
        if completed_at is not None:
            values["completed_at"] = completed_at

        if self._session_maker:
            async with self._session_maker() as session:
                await session.execute(
                    update(Analysis).where(Analysis.id == analysis_id).values(**values)
                )
                await session.commit()
        else:
            await self._session.execute(
                update(Analysis).where(Analysis.id == analysis_id).values(**values)
            )
            await self._session.commit()

    async def find_by_id_and_user_with_emails(
        self, *, analysis_id: int, user_id: int
    ) -> Analysis | None:
        result = await self._session.execute(
            select(Analysis)
            .options(selectinload(Analysis.classified_emails))
            .where(Analysis.id == analysis_id, Analysis.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def update_category_actions(
        self, *, analysis_id: int, category_actions: dict
    ) -> None:
        if self._session_maker:
            async with self._session_maker() as session:
                await session.execute(
                    update(Analysis)
                    .where(Analysis.id == analysis_id)
                    .values(category_actions=category_actions)
                )
                await session.commit()
        else:
            await self._session.execute(
                update(Analysis)
                .where(Analysis.id == analysis_id)
                .values(category_actions=category_actions)
            )
            await self._session.commit()
