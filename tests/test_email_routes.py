from unittest.mock import AsyncMock

import pytest

from app.core.dependencies import get_email_service
from app.models.schemas import EmailMetadata
from app.services.gmail_service import GmailService


class TestListEmails:
    @pytest.mark.asyncio
    async def test_list_emails_returns_emails(
        self, authenticated_client, mock_email_service: GmailService
    ) -> None:
        mock_email_service.get_messages_batch.return_value = [
            EmailMetadata(
                gmail_message_id="msg-1",
                gmail_thread_id="thread-1",
                sender="test@example.com",
                sender_domain="example.com",
                subject="Test Email",
                snippet="Hello world",
            )
        ]
        authenticated_client._transport.app.dependency_overrides[get_email_service] = (
            lambda: mock_email_service
        )
        response = await authenticated_client.get("/api/v1/emails")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["emails"][0]["gmail_message_id"] == "msg-1"
        assert data["unread_only"] is True

    @pytest.mark.asyncio
    async def test_list_emails_with_unread_only_false(
        self, authenticated_client, mock_email_service: GmailService
    ) -> None:
        mock_email_service.get_messages_batch.return_value = []
        authenticated_client._transport.app.dependency_overrides[get_email_service] = (
            lambda: mock_email_service
        )
        response = await authenticated_client.get(
            "/api/v1/emails", params={"unread_only": "false"}
        )
        assert response.status_code == 200
        assert response.json()["unread_only"] is False

    @pytest.mark.asyncio
    async def test_list_emails_rejects_unauthenticated(self, test_client) -> None:
        response = await test_client.get("/api/v1/emails")
        assert response.status_code in (401, 403)


class TestEmailStats:
    @pytest.mark.asyncio
    async def test_stats_returns_counts(
        self, authenticated_client, mock_email_service: GmailService
    ) -> None:
        mock_email_service.list_messages = AsyncMock(
            side_effect=[["msg-1"], ["msg-1", "msg-2", "msg-3"]]
        )
        authenticated_client._transport.app.dependency_overrides[get_email_service] = (
            lambda: mock_email_service
        )
        response = await authenticated_client.get("/api/v1/emails/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["unread_count"] == 1
        assert data["total_count"] == 3

    @pytest.mark.asyncio
    async def test_stats_rejects_unauthenticated(self, test_client) -> None:
        response = await test_client.get("/api/v1/emails/stats")
        assert response.status_code in (401, 403)
