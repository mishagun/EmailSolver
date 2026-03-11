from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db import Analysis, ClassifiedEmail, User
from app.repositories.classified_email_repository import SQLAlchemyClassifiedEmailRepository
from app.services.cleanup_service import CleanupService
from tests.conftest import test_session_maker


@pytest.fixture
async def analysis_with_emails(db_session: AsyncSession, test_user: User) -> Analysis:
    analysis = Analysis(user_id=test_user.id, status="completed", unread_only=True)
    db_session.add(analysis)
    await db_session.commit()
    await db_session.refresh(analysis)

    expired_email = ClassifiedEmail(
        analysis_id=analysis.id,
        gmail_message_id="expired-msg",
        category="spam",
        expires_at=datetime.now(UTC) - timedelta(days=1),
    )
    active_email = ClassifiedEmail(
        analysis_id=analysis.id,
        gmail_message_id="active-msg",
        category="primary",
        expires_at=datetime.now(UTC) + timedelta(days=6),
    )
    db_session.add_all([expired_email, active_email])
    await db_session.commit()
    return analysis


class TestCleanupExpiredEmails:
    @pytest.mark.asyncio
    async def test_deletes_expired_rows(
        self, db_session: AsyncSession, analysis_with_emails: Analysis
    ) -> None:
        repository = SQLAlchemyClassifiedEmailRepository(
            session_maker=test_session_maker
        )
        cleanup_service = CleanupService(repository=repository)
        await cleanup_service.cleanup_expired_emails()

        result = await db_session.execute(
            select(ClassifiedEmail).where(
                ClassifiedEmail.analysis_id == analysis_with_emails.id
            )
        )
        remaining = result.scalars().all()
        assert len(remaining) == 1
        assert remaining[0].gmail_message_id == "active-msg"

    @pytest.mark.asyncio
    async def test_keeps_non_expired_rows(
        self, db_session: AsyncSession, analysis_with_emails: Analysis
    ) -> None:
        repository = SQLAlchemyClassifiedEmailRepository(
            session_maker=test_session_maker
        )
        cleanup_service = CleanupService(repository=repository)
        await cleanup_service.cleanup_expired_emails()

        result = await db_session.execute(
            select(ClassifiedEmail).where(
                ClassifiedEmail.gmail_message_id == "active-msg"
            )
        )
        active = result.scalar_one_or_none()
        assert active is not None


class TestDeleteAnalysis:
    @pytest.mark.asyncio
    async def test_delete_analysis_removes_classified_emails(
        self,
        authenticated_client,
        db_session: AsyncSession,
        analysis_with_emails: Analysis,
    ) -> None:
        response = await authenticated_client.delete(
            f"/api/v1/analysis/{analysis_with_emails.id}"
        )
        assert response.status_code == 200

        result = await db_session.execute(
            select(ClassifiedEmail).where(
                ClassifiedEmail.analysis_id == analysis_with_emails.id
            )
        )
        assert result.scalars().all() == []
