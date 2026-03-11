from unittest.mock import MagicMock, patch

import pytest

from app.services.gmail_service import GmailService


@pytest.fixture
def gmail_service() -> GmailService:
    return GmailService(
        client_id="test-client-id",
        client_secret="test-client-secret",
        token_uri="https://oauth2.googleapis.com/token",
    )


class TestExtractHeader:
    def test_finds_header(self) -> None:
        headers = [
            {"name": "From", "value": "alice@example.com"},
            {"name": "Subject", "value": "Hello"},
        ]
        assert GmailService._extract_header(headers=headers, name="From") == "alice@example.com"

    def test_case_insensitive(self) -> None:
        headers = [{"name": "from", "value": "alice@example.com"}]
        assert GmailService._extract_header(headers=headers, name="From") == "alice@example.com"

    def test_returns_none_when_missing(self) -> None:
        headers = [{"name": "From", "value": "alice@example.com"}]
        assert GmailService._extract_header(headers=headers, name="To") is None

    def test_empty_headers(self) -> None:
        assert GmailService._extract_header(headers=[], name="From") is None


class TestExtractSenderDomain:
    def test_simple_email(self) -> None:
        assert GmailService._extract_sender_domain(sender="alice@example.com") == "example.com"

    def test_formatted_sender(self) -> None:
        result = GmailService._extract_sender_domain(sender="Alice <alice@example.com>")
        assert result == "example.com"

    def test_none_sender(self) -> None:
        assert GmailService._extract_sender_domain(sender=None) is None

    def test_no_at_sign(self) -> None:
        assert GmailService._extract_sender_domain(sender="no-at-sign") is None


class TestParseDate:
    def test_valid_rfc2822_date(self) -> None:
        result = GmailService._parse_date(date_str="Mon, 1 Jan 2024 12:00:00 +0000")
        assert result is not None
        assert result.year == 2024

    def test_none_date(self) -> None:
        assert GmailService._parse_date(date_str=None) is None

    def test_invalid_date(self) -> None:
        assert GmailService._parse_date(date_str="not-a-date") is None


class TestParseMessage:
    def test_parses_full_message(self) -> None:
        message = {
            "id": "msg-123",
            "threadId": "thread-456",
            "snippet": "Hello world preview text",
            "payload": {
                "headers": [
                    {"name": "From", "value": "alice@example.com"},
                    {"name": "Subject", "value": "Test Subject"},
                    {"name": "Date", "value": "Mon, 1 Jan 2024 12:00:00 +0000"},
                    {"name": "List-Unsubscribe", "value": "<mailto:unsub@example.com>"},
                ]
            },
        }
        result = GmailService._parse_message(message=message)
        assert result.gmail_message_id == "msg-123"
        assert result.gmail_thread_id == "thread-456"
        assert result.sender == "alice@example.com"
        assert result.sender_domain == "example.com"
        assert result.subject == "Test Subject"
        assert result.has_unsubscribe is True
        assert result.received_at is not None

    def test_parses_minimal_message(self) -> None:
        message = {"id": "msg-minimal", "payload": {"headers": []}}
        result = GmailService._parse_message(message=message)
        assert result.gmail_message_id == "msg-minimal"
        assert result.sender is None
        assert result.subject is None
        assert result.has_unsubscribe is False


class TestExtractGmailCategory:
    def test_social_label(self) -> None:
        # Arrange
        label_ids = ["INBOX", "CATEGORY_SOCIAL"]
        # Act
        result = GmailService._extract_gmail_category(label_ids=label_ids)
        # Assert
        assert result == "social"

    def test_promotions_label(self) -> None:
        # Arrange
        label_ids = ["CATEGORY_PROMOTIONS"]
        # Act
        result = GmailService._extract_gmail_category(label_ids=label_ids)
        # Assert
        assert result == "promotions"

    def test_updates_label(self) -> None:
        # Arrange
        label_ids = ["CATEGORY_UPDATES"]
        # Act
        result = GmailService._extract_gmail_category(label_ids=label_ids)
        # Assert
        assert result == "updates"

    def test_forums_label(self) -> None:
        # Arrange
        label_ids = ["CATEGORY_FORUMS"]
        # Act
        result = GmailService._extract_gmail_category(label_ids=label_ids)
        # Assert
        assert result == "forums"

    def test_personal_label_maps_to_primary(self) -> None:
        # Arrange
        label_ids = ["CATEGORY_PERSONAL"]
        # Act
        result = GmailService._extract_gmail_category(label_ids=label_ids)
        # Assert
        assert result == "primary"

    def test_no_category_labels_defaults_to_primary(self) -> None:
        # Arrange
        label_ids = ["INBOX", "UNREAD"]
        # Act
        result = GmailService._extract_gmail_category(label_ids=label_ids)
        # Assert
        assert result == "primary"

    def test_empty_labels_defaults_to_primary(self) -> None:
        # Arrange
        label_ids: list[str] = []
        # Act
        result = GmailService._extract_gmail_category(label_ids=label_ids)
        # Assert
        assert result == "primary"

    def test_multiple_labels_with_category(self) -> None:
        # Arrange
        label_ids = ["INBOX", "UNREAD", "CATEGORY_PROMOTIONS", "IMPORTANT"]
        # Act
        result = GmailService._extract_gmail_category(label_ids=label_ids)
        # Assert
        assert result == "promotions"


class TestParseMessageGmailCategory:
    def test_extracts_gmail_category_from_label_ids(self) -> None:
        # Arrange
        message = {
            "id": "msg-1",
            "labelIds": ["INBOX", "CATEGORY_PROMOTIONS"],
            "payload": {
                "headers": [
                    {"name": "From", "value": "shop@example.com"},
                    {"name": "Subject", "value": "Sale!"},
                ]
            },
        }
        # Act
        result = GmailService._parse_message(message=message)
        # Assert
        assert result.gmail_category == "promotions"

    def test_no_category_label_defaults_to_primary(self) -> None:
        # Arrange
        message = {
            "id": "msg-2",
            "labelIds": ["INBOX", "UNREAD"],
            "payload": {"headers": []},
        }
        # Act
        result = GmailService._parse_message(message=message)
        # Assert
        assert result.gmail_category == "primary"

    def test_no_label_ids_key_defaults_to_primary(self) -> None:
        # Arrange
        message = {
            "id": "msg-3",
            "payload": {"headers": []},
        }
        # Act
        result = GmailService._parse_message(message=message)
        # Assert
        assert result.gmail_category == "primary"


class TestListMessages:
    @pytest.mark.asyncio
    async def test_list_messages_calls_gmail_api(
        self, gmail_service: GmailService
    ) -> None:
        mock_service = MagicMock()
        mock_list = MagicMock()
        mock_list.execute.return_value = {
            "messages": [{"id": "msg-1"}, {"id": "msg-2"}]
        }
        mock_service.users.return_value.messages.return_value.list.return_value = mock_list
        mock_service.users.return_value.messages.return_value.list_next.return_value = None

        with patch("app.services.gmail_service.build", return_value=mock_service):
            mock_creds = MagicMock()
            result = await gmail_service.list_messages(
                credentials=mock_creds, label_ids=["UNREAD"]
            )

        assert result == ["msg-1", "msg-2"]


class TestGetMessagesBatch:
    @pytest.mark.asyncio
    async def test_get_messages_batch_processes_messages(
        self, gmail_service: GmailService
    ) -> None:
        mock_service = MagicMock()

        mock_batch = MagicMock()
        mock_service.new_batch_http_request.return_value = mock_batch

        responses: list = []

        def fake_add(request, callback):
            responses.append(callback)

        mock_batch.add = fake_add

        def execute_batch():
            for cb in responses:
                cb(
                    "req-1",
                    {
                        "id": "msg-1",
                        "threadId": "thread-1",
                        "snippet": "Test snippet",
                        "payload": {
                            "headers": [
                                {"name": "From", "value": "test@example.com"},
                                {"name": "Subject", "value": "Test"},
                                {"name": "Date", "value": "Mon, 1 Jan 2024 12:00:00 +0000"},
                            ]
                        },
                    },
                    None,
                )

        mock_batch.execute = execute_batch

        mock_service.users.return_value.messages.return_value.get.return_value = MagicMock()

        with patch("app.services.gmail_service.build", return_value=mock_service):
            mock_creds = MagicMock()
            result = await gmail_service.get_messages_batch(
                credentials=mock_creds, message_ids=["msg-1"]
            )

        assert len(result) == 1
        assert result[0].gmail_message_id == "msg-1"
        assert result[0].sender == "test@example.com"
