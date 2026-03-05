from unittest.mock import AsyncMock, patch

import pytest

from app.services.unsubscribe_service import (
    attempt_http_unsubscribe,
    parse_unsubscribe_urls,
)


class TestParseUnsubscribeUrls:
    def test_single_url(self) -> None:
        header = "<https://example.com/unsub?id=123>"
        result = parse_unsubscribe_urls(header=header)
        assert result == ["https://example.com/unsub?id=123"]

    def test_multiple_urls(self) -> None:
        header = "<https://example.com/unsub>, <mailto:unsub@example.com>, <http://other.com/out>"
        result = parse_unsubscribe_urls(header=header)
        assert result == ["https://example.com/unsub", "http://other.com/out"]

    def test_mailto_only(self) -> None:
        header = "<mailto:unsub@example.com>"
        result = parse_unsubscribe_urls(header=header)
        assert result == []

    def test_empty_header(self) -> None:
        result = parse_unsubscribe_urls(header="")
        assert result == []

    def test_malformed_header(self) -> None:
        result = parse_unsubscribe_urls(header="not a valid header")
        assert result == []

    def test_url_with_query_params(self) -> None:
        header = "<https://example.com/unsub?token=abc&user=123>"
        result = parse_unsubscribe_urls(header=header)
        assert result == ["https://example.com/unsub?token=abc&user=123"]


class TestAttemptHttpUnsubscribe:
    @pytest.mark.asyncio
    async def test_success_returns_true(self) -> None:
        mock_response = AsyncMock()
        mock_response.status_code = 200

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.unsubscribe_service.httpx.AsyncClient", return_value=mock_client):
            result = await attempt_http_unsubscribe(url="https://example.com/unsub")

        assert result is True
        mock_client.post.assert_called_once_with(
            "https://example.com/unsub",
            content="List-Unsubscribe=One-Click-Unsubscribe",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    @pytest.mark.asyncio
    async def test_404_returns_false(self) -> None:
        mock_response = AsyncMock()
        mock_response.status_code = 404

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.unsubscribe_service.httpx.AsyncClient", return_value=mock_client):
            result = await attempt_http_unsubscribe(url="https://example.com/unsub")

        assert result is False

    @pytest.mark.asyncio
    async def test_exception_returns_false(self) -> None:
        mock_client = AsyncMock()
        mock_client.post.side_effect = Exception("connection error")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.unsubscribe_service.httpx.AsyncClient", return_value=mock_client):
            result = await attempt_http_unsubscribe(url="https://example.com/unsub")

        assert result is False
