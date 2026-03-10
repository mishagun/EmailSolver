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

    @pytest.mark.asyncio
    async def test_login_embeds_callback_port_in_state(
        self, test_client, mock_auth_service: GoogleAuthService
    ) -> None:
        test_client._transport.app.dependency_overrides[get_auth_service] = (
            lambda: mock_auth_service
        )
        response = await test_client.get(
            "/api/v1/auth/login",
            params={"callback_port": 54321},
            follow_redirects=False,
        )
        assert response.status_code == 307
        location = response.headers["location"]
        assert "cb%3A54321" in location or "cb:54321" in location

    @pytest.mark.asyncio
    async def test_login_rejects_privileged_port(
        self, test_client, mock_auth_service: GoogleAuthService
    ) -> None:
        test_client._transport.app.dependency_overrides[get_auth_service] = (
            lambda: mock_auth_service
        )
        response = await test_client.get(
            "/api/v1/auth/login",
            params={"callback_port": 80},
            follow_redirects=False,
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_login_rejects_port_zero(
        self, test_client, mock_auth_service: GoogleAuthService
    ) -> None:
        test_client._transport.app.dependency_overrides[get_auth_service] = (
            lambda: mock_auth_service
        )
        response = await test_client.get(
            "/api/v1/auth/login",
            params={"callback_port": 0},
            follow_redirects=False,
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_login_rejects_negative_port(
        self, test_client, mock_auth_service: GoogleAuthService
    ) -> None:
        test_client._transport.app.dependency_overrides[get_auth_service] = (
            lambda: mock_auth_service
        )
        response = await test_client.get(
            "/api/v1/auth/login",
            params={"callback_port": -1},
            follow_redirects=False,
        )
        assert response.status_code == 400


class TestCallback:
    def _mock_auth(self, *, user_info: dict) -> MagicMock:
        mock_credentials = MagicMock()
        mock_credentials.token = "access-token"
        mock_credentials.refresh_token = "refresh-token"
        mock_credentials.expiry = None

        mock = MagicMock(spec=GoogleAuthService)
        mock.exchange_code = MagicMock(return_value=mock_credentials)
        mock.get_user_info = MagicMock(return_value=user_info)
        return mock

    @pytest.mark.asyncio
    async def test_callback_creates_user_and_redirects(
        self, test_client, db_session: AsyncSession, security_service
    ) -> None:
        mock_auth = self._mock_auth(user_info={
            "id": "google-new-user",
            "email": "newuser@example.com",
            "name": "New User",
        })

        test_client._transport.app.dependency_overrides[get_auth_service] = (
            lambda: mock_auth
        )

        response = await test_client.get(
            "/api/v1/auth/callback",
            params={"code": "auth-code", "state": "test-nonce"},
            follow_redirects=False,
        )

        assert response.status_code == 307
        location = response.headers["location"]
        assert location.startswith("/api/v1/auth/success?token=")

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
        mock_auth = self._mock_auth(user_info={
            "id": test_user.google_id,
            "email": test_user.email,
            "name": "Updated Name",
        })

        test_client._transport.app.dependency_overrides[get_auth_service] = (
            lambda: mock_auth
        )

        response = await test_client.get(
            "/api/v1/auth/callback",
            params={"code": "auth-code", "state": "test-nonce"},
            follow_redirects=False,
        )

        assert response.status_code == 307
        await db_session.refresh(test_user)
        assert test_user.display_name == "Updated Name"

    @pytest.mark.asyncio
    async def test_callback_with_callback_port_redirects_to_localhost(
        self, test_client, db_session: AsyncSession, security_service
    ) -> None:
        mock_auth = self._mock_auth(user_info={
            "id": "google-port-user",
            "email": "portuser@example.com",
            "name": "Port User",
        })

        test_client._transport.app.dependency_overrides[get_auth_service] = (
            lambda: mock_auth
        )

        response = await test_client.get(
            "/api/v1/auth/callback",
            params={"code": "auth-code", "state": "test-nonce|cb:54321"},
            follow_redirects=False,
        )

        assert response.status_code == 307
        location = response.headers["location"]
        assert location.startswith("http://localhost:54321/callback?token=")

    @pytest.mark.asyncio
    async def test_callback_rejects_invalid_state(
        self, test_client, security_service
    ) -> None:
        mock_auth = MagicMock(spec=GoogleAuthService)
        mock_auth.exchange_code = MagicMock(
            side_effect=ValueError("Invalid or expired OAuth state")
        )

        test_client._transport.app.dependency_overrides[get_auth_service] = (
            lambda: mock_auth
        )

        response = await test_client.get(
            "/api/v1/auth/callback",
            params={"code": "auth-code", "state": "unknown-nonce"},
            follow_redirects=False,
        )

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_callback_rejects_privileged_port(
        self, test_client, security_service
    ) -> None:
        mock_auth = self._mock_auth(user_info={
            "id": "google-bad-port-user",
            "email": "badport@example.com",
            "name": "Bad Port User",
        })

        test_client._transport.app.dependency_overrides[get_auth_service] = (
            lambda: mock_auth
        )

        response = await test_client.get(
            "/api/v1/auth/callback",
            params={"code": "auth-code", "state": "test-nonce|cb:80"},
            follow_redirects=False,
        )

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_callback_rejects_port_zero(
        self, test_client, security_service
    ) -> None:
        mock_auth = self._mock_auth(user_info={
            "id": "google-zero-port-user",
            "email": "zeroport@example.com",
            "name": "Zero Port User",
        })

        test_client._transport.app.dependency_overrides[get_auth_service] = (
            lambda: mock_auth
        )

        response = await test_client.get(
            "/api/v1/auth/callback",
            params={"code": "auth-code", "state": "test-nonce|cb:0"},
            follow_redirects=False,
        )

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_callback_rejects_failed_credentials(
        self, test_client, security_service
    ) -> None:
        mock_credentials = MagicMock()
        mock_credentials.token = None

        mock_auth = MagicMock(spec=GoogleAuthService)
        mock_auth.exchange_code = MagicMock(return_value=mock_credentials)

        test_client._transport.app.dependency_overrides[get_auth_service] = (
            lambda: mock_auth
        )

        response = await test_client.get(
            "/api/v1/auth/callback",
            params={"code": "auth-code", "state": "test-nonce"},
            follow_redirects=False,
        )

        assert response.status_code == 400
        assert "Failed to obtain credentials" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_callback_tokens_encrypted_in_db(
        self, test_client, db_session: AsyncSession, security_service
    ) -> None:
        mock_auth = self._mock_auth(user_info={
            "id": "google-encrypt-check",
            "email": "encryptcheck@example.com",
            "name": "Encrypt Check",
        })

        test_client._transport.app.dependency_overrides[get_auth_service] = (
            lambda: mock_auth
        )

        await test_client.get(
            "/api/v1/auth/callback",
            params={"code": "auth-code", "state": "test-nonce"},
            follow_redirects=False,
        )

        result = await db_session.execute(
            select(User).where(User.google_id == "google-encrypt-check")
        )
        user = result.scalar_one()
        assert user.encrypted_access_token is not None
        assert user.encrypted_access_token != "access-token"
        assert user.encrypted_refresh_token is not None
        assert user.encrypted_refresh_token != "refresh-token"


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


class TestAuthSuccess:
    @pytest.mark.asyncio
    async def test_success_renders_html_with_token(self, test_client) -> None:
        response = await test_client.get(
            "/api/v1/auth/success", params={"token": "my-jwt-token"}
        )
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "my-jwt-token" in response.text
        assert "Login successful" in response.text


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

    @pytest.mark.asyncio
    async def test_logout_clears_token_expiry(
        self, authenticated_client, db_session: AsyncSession, test_user: User,
        mock_auth_service: GoogleAuthService,
    ) -> None:
        from datetime import UTC, datetime

        test_user.token_expiry = datetime(2030, 1, 1, tzinfo=UTC)
        db_session.add(test_user)
        await db_session.commit()

        authenticated_client._transport.app.dependency_overrides[get_auth_service] = (
            lambda: mock_auth_service
        )

        response = await authenticated_client.delete("/api/v1/auth/logout")

        assert response.status_code == 200
        await db_session.refresh(test_user)
        assert test_user.token_expiry is None
