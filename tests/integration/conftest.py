import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import (
    get_analysis_service,
    get_auth_service,
    get_classification_service,
    get_classified_email_repository,
    get_email_service,
    get_security_service,
)
from app.core.security import FernetSecurityService
from app.models.db import User
from app.repositories.classified_email_repository import SQLAlchemyClassifiedEmailRepository
from app.services.analysis_service import AnalysisService
from tests.conftest import test_session_maker
from tests.integration.fakes import (
    FakeAuthService,
    FakeClassificationService,
    FakeEmailService,
)


@asynccontextmanager
async def _null_lifespan(app: FastAPI) -> AsyncGenerator[None]:
    yield


@pytest.fixture
def fake_email_service() -> FakeEmailService:
    return FakeEmailService()


@pytest.fixture
def fake_classification_service() -> FakeClassificationService:
    return FakeClassificationService()


@pytest.fixture
def fake_auth_service() -> FakeAuthService:
    return FakeAuthService()


@pytest_asyncio.fixture
async def integration_client(
    db_session: AsyncSession,
    security_service: FernetSecurityService,
    fake_email_service: FakeEmailService,
    fake_classification_service: FakeClassificationService,
    fake_auth_service: FakeAuthService,
) -> AsyncGenerator[AsyncClient]:
    classified_email_repo = SQLAlchemyClassifiedEmailRepository(
        session_maker=test_session_maker
    )

    def make_analysis_service() -> AnalysisService:
        return AnalysisService(
            email_service=fake_email_service,
            classification_service=fake_classification_service,
            security_service=security_service,
            classified_email_repo=classified_email_repo,
            async_session_maker=test_session_maker,
        )

    from app.main import create_app

    test_app = create_app()

    async def override_get_db() -> AsyncGenerator[AsyncSession]:
        async with test_session_maker() as session:
            yield session

    test_app.dependency_overrides[get_db] = override_get_db
    test_app.dependency_overrides[get_security_service] = lambda: security_service
    test_app.dependency_overrides[get_email_service] = lambda: fake_email_service
    test_app.dependency_overrides[get_classification_service] = (
        lambda: fake_classification_service
    )
    test_app.dependency_overrides[get_auth_service] = lambda: fake_auth_service
    test_app.dependency_overrides[get_classified_email_repository] = (
        lambda: classified_email_repo
    )
    test_app.dependency_overrides[get_analysis_service] = make_analysis_service
    test_app.router.lifespan_context = _null_lifespan

    async with AsyncClient(
        transport=ASGITransport(app=test_app), base_url="http://test"
    ) as client:
        yield client

    test_app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def authenticated_integration_client(
    integration_client: AsyncClient,
    test_user: User,
    security_service: FernetSecurityService,
) -> AsyncClient:
    token = security_service.create_jwt(user_id=test_user.id)
    integration_client.headers["Authorization"] = f"Bearer {token}"
    return integration_client


async def wait_for_analysis(
    client: AsyncClient, analysis_id: int, *, timeout: float = 10
) -> dict:
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        response = await client.get(f"/api/v1/analysis/{analysis_id}")
        assert response.status_code == 200
        data = response.json()
        if data["status"] in ("completed", "failed"):
            return data
        await asyncio.sleep(0.1)
    raise TimeoutError(f"Analysis {analysis_id} did not complete in {timeout}s")
