from httpx import AsyncClient
from sqlalchemy import select

from app.models.db import User
from tests.conftest import test_session_maker


async def test_auth_callback_creates_user_and_returns_jwt(
    integration_client: AsyncClient,
) -> None:
    response = await integration_client.get(
        "/api/v1/auth/callback",
        params={"code": "fake-code", "state": "fake-state"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

    async with test_session_maker() as session:
        user = (
            await session.execute(
                select(User).where(User.google_id == "google-integration-test-123")
            )
        ).scalar_one_or_none()
        assert user is not None
        assert user.email == "integration@test.com"
        assert user.display_name == "Integration Test User"
        assert user.encrypted_access_token is not None
        assert user.encrypted_refresh_token is not None


async def test_auth_status_after_login(
    integration_client: AsyncClient,
) -> None:
    callback_response = await integration_client.get(
        "/api/v1/auth/callback",
        params={"code": "fake-code", "state": "fake-state"},
    )
    jwt_token = callback_response.json()["access_token"]

    integration_client.headers["Authorization"] = f"Bearer {jwt_token}"
    status_response = await integration_client.get("/api/v1/auth/status")
    assert status_response.status_code == 200
    data = status_response.json()
    assert data["authenticated"] is True
    assert data["email"] == "integration@test.com"
    assert data["display_name"] == "Integration Test User"


async def test_logout_clears_tokens(
    integration_client: AsyncClient,
) -> None:
    callback_response = await integration_client.get(
        "/api/v1/auth/callback",
        params={"code": "fake-code", "state": "fake-state"},
    )
    jwt_token = callback_response.json()["access_token"]
    integration_client.headers["Authorization"] = f"Bearer {jwt_token}"

    logout_response = await integration_client.delete("/api/v1/auth/logout")
    assert logout_response.status_code == 200

    async with test_session_maker() as session:
        user = (
            await session.execute(
                select(User).where(User.google_id == "google-integration-test-123")
            )
        ).scalar_one()
        assert user.encrypted_access_token is None
        assert user.encrypted_refresh_token is None


async def test_unauthenticated_request_returns_403(
    integration_client: AsyncClient,
) -> None:
    response = await integration_client.get("/api/v1/auth/status")
    assert response.status_code in (401, 403)


async def test_login_redirect(
    integration_client: AsyncClient,
) -> None:
    response = await integration_client.get(
        "/api/v1/auth/login",
        follow_redirects=False,
    )
    assert response.status_code == 307
    assert "fake-auth.example.com" in response.headers["location"]


async def test_repeated_login_updates_existing_user(
    integration_client: AsyncClient,
) -> None:
    await integration_client.get(
        "/api/v1/auth/callback",
        params={"code": "fake-code", "state": "fake-state"},
    )
    await integration_client.get(
        "/api/v1/auth/callback",
        params={"code": "fake-code-2", "state": "fake-state-2"},
    )

    async with test_session_maker() as session:
        users = (
            await session.execute(
                select(User).where(User.google_id == "google-integration-test-123")
            )
        ).scalars().all()
        assert len(users) == 1
