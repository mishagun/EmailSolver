import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from cryptography.fernet import Fernet
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import NullPool, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload

from app.core.database import Base, get_db
from app.core.dependencies import get_security_service
from app.core.security import FernetSecurityService
from app.models.db import Analysis, ClassifiedEmail, User
from app.models.schemas import EmailMetadata
from app.services.analysis_service import AnalysisService
from app.services.auth_service import GoogleAuthService
from app.services.gmail_service import GmailService

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://emailsolver:emailsolver@localhost:5432/emailsolver_test",
)

TEST_FERNET_KEY = Fernet.generate_key().decode()

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False, poolclass=NullPool)
test_session_maker = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture
def security_service() -> FernetSecurityService:
    return FernetSecurityService(
        fernet_key=TEST_FERNET_KEY,
        jwt_secret_key="test-jwt-secret",
        jwt_algorithm="HS256",
        jwt_expire_minutes=60,
    )


@asynccontextmanager
async def _null_lifespan(app: FastAPI) -> AsyncGenerator[None]:
    yield


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession]:
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with test_session_maker() as session:
        yield session

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def test_client(
    db_session: AsyncSession, security_service: FernetSecurityService
) -> AsyncGenerator[AsyncClient]:
    async def override_get_db() -> AsyncGenerator[AsyncSession]:
        yield db_session

    from app.main import create_app

    test_app = create_app()
    test_app.dependency_overrides[get_db] = override_get_db
    test_app.dependency_overrides[get_security_service] = lambda: security_service
    test_app.router.lifespan_context = _null_lifespan

    async with AsyncClient(
        transport=ASGITransport(app=test_app), base_url="http://test"
    ) as client:
        yield client

    test_app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def test_user(
    db_session: AsyncSession, security_service: FernetSecurityService
) -> User:
    user = User(
        email="test@example.com",
        google_id="google-123",
        display_name="Test User",
        encrypted_access_token=security_service.encrypt_token(token="fake-access-token"),
        encrypted_refresh_token=security_service.encrypt_token(token="fake-refresh-token"),
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def authenticated_client(
    test_client: AsyncClient, test_user: User, security_service: FernetSecurityService
) -> AsyncClient:
    token = security_service.create_jwt(user_id=test_user.id)
    test_client.headers["Authorization"] = f"Bearer {token}"
    return test_client


@pytest.fixture
def mock_email_service() -> GmailService:
    mock = MagicMock(spec=GmailService)
    mock.build_credentials = MagicMock(return_value=MagicMock())
    mock.list_messages = AsyncMock(return_value=["msg-1", "msg-2"])
    mock.get_messages_batch = AsyncMock(return_value=[
        EmailMetadata(
            gmail_message_id="msg-1",
            gmail_thread_id="thread-1",
            sender="sender@example.com",
            sender_domain="example.com",
            subject="Test Email",
            snippet="Hello world",
        )
    ])
    return mock


@pytest.fixture
def mock_auth_service() -> GoogleAuthService:
    mock = MagicMock(spec=GoogleAuthService)
    mock.start_authorization = MagicMock(
        return_value="https://accounts.google.com/o/oauth2/auth?fake=1&state=csrf%7Cverifier"
    )
    mock.revoke_token = AsyncMock()
    return mock


@pytest.fixture
def mock_analysis_service() -> AnalysisService:
    mock = MagicMock(spec=AnalysisService)
    mock.start_analysis = MagicMock(return_value=MagicMock())
    mock.apply_actions_for_analysis = AsyncMock()
    return mock


@pytest_asyncio.fixture
async def analysis_with_classified_emails(
    db_session: AsyncSession, test_user: User
) -> Analysis:
    analysis = Analysis(
        user_id=test_user.id,
        status="completed",
        query="is:unread",
        total_emails=2,
        processed_emails=2,
    )
    db_session.add(analysis)
    await db_session.commit()
    await db_session.refresh(analysis)

    emails = [
        ClassifiedEmail(
            analysis_id=analysis.id,
            gmail_message_id=f"msg-{i}",
            gmail_thread_id=f"thread-{i}",
            sender=f"sender{i}@example.com",
            sender_domain="example.com",
            subject=f"Subject {i}",
            snippet=f"Snippet {i}",
            category="promotions",
            importance=2,
            sender_type="marketing",
            confidence=0.9,
        )
        for i in range(2)
    ]
    db_session.add_all(emails)
    await db_session.commit()

    result = await db_session.execute(
        select(Analysis)
        .options(selectinload(Analysis.classified_emails))
        .where(Analysis.id == analysis.id)
    )
    return result.scalar_one()
