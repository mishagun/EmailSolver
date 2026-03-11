from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from tui.client import ApiError, TidyInboxClient
from tui.models import ActionType, AnalysisCreateRequest, ApplyActionsRequest


@pytest.fixture
def client() -> TidyInboxClient:
    return TidyInboxClient(base_url="http://test:8000")


@asynccontextmanager
async def mock_request(
    client: TidyInboxClient, *, response: httpx.Response
) -> AsyncGenerator[AsyncMock]:
    with patch.object(
        client._client,
        "request",
        new_callable=AsyncMock,
        return_value=response,
    ) as mock:
        yield mock


class TestClientAuth:
    def test_initial_state_unauthenticated(self, client: TidyInboxClient) -> None:
        assert client.is_authenticated is False

    def test_set_token(self, client: TidyInboxClient) -> None:
        client.set_token(token="jwt-123")
        assert client.is_authenticated is True

    def test_clear_token(self, client: TidyInboxClient) -> None:
        client.set_token(token="jwt-123")
        client.clear_token()
        assert client.is_authenticated is False

    def test_get_login_url(self, client: TidyInboxClient) -> None:
        url = client.get_login_url()
        assert url == "http://test:8000/api/v1/auth/login"


class TestClientApiCalls:
    @pytest.fixture(autouse=True)
    def _setup(self, client: TidyInboxClient) -> None:
        client.set_token(token="jwt-123")
        self.client = client

    async def test_get_auth_status(self) -> None:
        resp = httpx.Response(
            status_code=200,
            json={
                "authenticated": True,
                "email": "user@test.com",
                "display_name": "User",
            },
        )
        async with mock_request(self.client, response=resp):
            result = await self.client.get_auth_status()
            assert result.authenticated is True
            assert result.email == "user@test.com"

    async def test_logout(self) -> None:
        resp = httpx.Response(
            status_code=200,
            json={"message": "Logged out successfully"},
        )
        async with mock_request(self.client, response=resp):
            result = await self.client.logout()
            assert result.message == "Logged out successfully"

    async def test_get_email_stats(self) -> None:
        resp = httpx.Response(
            status_code=200,
            json={"unread_count": 42, "total_count": 1500},
        )
        async with mock_request(self.client, response=resp):
            result = await self.client.get_email_stats()
            assert result.unread_count == 42
            assert result.total_count == 1500

    async def test_list_emails(self) -> None:
        resp = httpx.Response(
            status_code=200,
            json={
                "emails": [{"gmail_message_id": "msg-1", "subject": "Hello"}],
                "total": 1,
                "unread_only": True,
            },
        )
        async with mock_request(self.client, response=resp):
            result = await self.client.list_emails()
            assert result.total == 1
            assert result.emails[0].gmail_message_id == "msg-1"

    async def test_create_analysis(self) -> None:
        resp = httpx.Response(
            status_code=202,
            json={
                "id": 1,
                "status": "pending",
                "unread_only": True,
                "created_at": "2026-03-01T00:00:00Z",
            },
        )
        async with mock_request(self.client, response=resp):
            req = AnalysisCreateRequest(unread_only=True, max_emails=50)
            result = await self.client.create_analysis(request=req)
            assert result.id == 1
            assert result.status == "pending"

    async def test_list_analyses(self) -> None:
        resp = httpx.Response(
            status_code=200,
            json={
                "analyses": [
                    {
                        "id": 1,
                        "status": "completed",
                        "created_at": "2026-03-01T00:00:00Z",
                    }
                ],
                "total": 1,
            },
        )
        async with mock_request(self.client, response=resp):
            result = await self.client.list_analyses()
            assert result.total == 1

    async def test_get_analysis(self) -> None:
        resp = httpx.Response(
            status_code=200,
            json={
                "id": 1,
                "status": "completed",
                "total_emails": 50,
                "processed_emails": 50,
                "created_at": "2026-03-01T00:00:00Z",
                "summary": [
                    {
                        "category": "promotions",
                        "count": 30,
                        "recommended_actions": ["mark_read"],
                    }
                ],
                "classified_emails": [],
            },
        )
        async with mock_request(self.client, response=resp):
            result = await self.client.get_analysis(analysis_id=1)
            assert result.status == "completed"
            assert result.summary is not None
            assert result.summary[0].category == "promotions"

    async def test_apply_actions(self) -> None:
        resp = httpx.Response(
            status_code=200,
            json={"message": "Actions applied successfully"},
        )
        async with mock_request(self.client, response=resp):
            req = ApplyActionsRequest(
                action=ActionType.MARK_READ, category="promotions"
            )
            result = await self.client.apply_actions(
                analysis_id=1, request=req
            )
            assert result.message == "Actions applied successfully"

    async def test_delete_analysis(self) -> None:
        resp = httpx.Response(
            status_code=200,
            json={"message": "Analysis and classified emails deleted"},
        )
        async with mock_request(self.client, response=resp):
            result = await self.client.delete_analysis(analysis_id=1)
            assert "deleted" in result.message


class TestClientErrors:
    @pytest.fixture(autouse=True)
    def _setup(self, client: TidyInboxClient) -> None:
        client.set_token(token="jwt-123")
        self.client = client

    async def test_api_error_on_401(self) -> None:
        resp = httpx.Response(
            status_code=401,
            json={"detail": "Not authenticated"},
        )
        async with mock_request(self.client, response=resp):
            with pytest.raises(ApiError) as exc_info:
                await self.client.get_auth_status()
            assert exc_info.value.status_code == 401
            assert "Not authenticated" in exc_info.value.detail

    async def test_api_error_on_404(self) -> None:
        resp = httpx.Response(
            status_code=404,
            json={"detail": "Analysis not found"},
        )
        async with mock_request(self.client, response=resp):
            with pytest.raises(ApiError) as exc_info:
                await self.client.get_analysis(analysis_id=999)
            assert exc_info.value.status_code == 404

    async def test_api_error_on_422(self) -> None:
        resp = httpx.Response(
            status_code=422,
            json={"detail": "Invalid action"},
        )
        async with mock_request(self.client, response=resp):
            with pytest.raises(ApiError) as exc_info:
                req = ApplyActionsRequest(action=ActionType.KEEP)
                await self.client.apply_actions(
                    analysis_id=1, request=req
                )
            assert exc_info.value.status_code == 422

    async def test_api_error_non_json_response(self) -> None:
        resp = httpx.Response(
            status_code=500,
            text="Internal Server Error",
        )
        async with mock_request(self.client, response=resp):
            with pytest.raises(ApiError) as exc_info:
                await self.client.get_auth_status()
            assert exc_info.value.status_code == 500

    async def test_close(self, client: TidyInboxClient) -> None:
        mock_close = AsyncMock()
        with patch.object(client._client, "aclose", mock_close):
            await client.close()
            mock_close.assert_called_once()
