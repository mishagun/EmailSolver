from unittest.mock import MagicMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_auth_service
from app.models.db import User
from app.services.auth_service import GoogleAuthService


class TestLoginRedirect:
    @pytest.mark.asyncio
    async def test_login_redirects_to_google(
        self, test_client, mock_auth_service: GoogleAuthService
    ) -> None:
        test_client._transport.app.dependency_overrides[get_auth_service] = (
            lambda: mock_auth_service
        )
        response = await test_client.get(
            "/api/v1/auth/login", follow_redirects=False
        )
        assert response.status_code == 307
        assert "accounts.google.com" in response.headers["location"]


class TestCallback:
    @pytest.mark.asyncio
    async def test_callback_creates_user_and_returns_jwt(
        self, test_client, db_session: AsyncSession, security_service
    ) -> None:
        mock_credentials = MagicMock()
        mock_credentials.token = "access-token"
        mock_credentials.refresh_token = "refresh-token"
        mock_credentials.expiry = None

        mock_auth = MagicMock(spec=GoogleAuthService)
        mock_auth.exchange_code = MagicMock(return_value=mock_credentials)
        mock_auth.get_user_info = MagicMock(return_value={
            "id": "google-new-user",
            "email": "newuser@example.com",
            "name": "New User",
        })

        test_client._transport.app.dependency_overrides[get_auth_service] = (
            lambda: mock_auth
        )

        response = await test_client.get(
            "/api/v1/auth/callback",
            params={"code": "auth-code", "state": "csrf|verifier"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

        result = await db_session.execute(
            select(User).where(User.google_id == "google-new-user")
        )
        user = result.scalar_one()
        assert user.email == "newuser@example.com"
        assert user.encrypted_access_token is not None
        assert user.encrypted_access_token != "access-token"

    @pytest.mark.asyncio
    async def test_callback_updates_existing_user(
        self, test_client, db_session: AsyncSession, test_user: User, security_service
    ) -> None:
        mock_credentials = MagicMock()
        mock_credentials.token = "new-access-token"
        mock_credentials.refresh_token = "new-refresh-token"
        mock_credentials.expiry = None

        mock_auth = MagicMock(spec=GoogleAuthService)
        mock_auth.exchange_code = MagicMock(return_value=mock_credentials)
        mock_auth.get_user_info = MagicMock(return_value={
            "id": test_user.google_id,
            "email": test_user.email,
            "name": "Updated Name",
        })

        test_client._transport.app.dependency_overrides[get_auth_service] = (
            lambda: mock_auth
        )

        response = await test_client.get(
            "/api/v1/auth/callback",
            params={"code": "auth-code", "state": "csrf|verifier"},
        )

        assert response.status_code == 200
        await db_session.refresh(test_user)
        assert test_user.display_name == "Updated Name"


class TestAuthStatus:
    @pytest.mark.asyncio
    async def test_status_returns_user_info(self, authenticated_client) -> None:
        response = await authenticated_client.get("/api/v1/auth/status")
        assert response.status_code == 200
        data = response.json()
        assert data["authenticated"] is True
        assert data["email"] == "test@example.com"

    @pytest.mark.asyncio
    async def test_status_rejects_unauthenticated(self, test_client) -> None:
        response = await test_client.get("/api/v1/auth/status")
        assert response.status_code in (401, 403)


class TestLogout:
    @pytest.mark.asyncio
    async def test_logout_clears_tokens(
        self, authenticated_client, db_session: AsyncSession, test_user: User,
        mock_auth_service: GoogleAuthService,
    ) -> None:
        authenticated_client._transport.app.dependency_overrides[get_auth_service] = (
            lambda: mock_auth_service
        )

        response = await authenticated_client.delete("/api/v1/auth/logout")

        assert response.status_code == 200
        await db_session.refresh(test_user)
        assert test_user.encrypted_access_token is None
        assert test_user.encrypted_refresh_token is None
