import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.schemas import ClassificationResult, EmailMetadata, VerificationResult
from app.services.classification_service import ClaudeClassificationService


def _make_emails(*, count: int = 2) -> list[EmailMetadata]:
    return [
        EmailMetadata(
            gmail_message_id=f"msg-{i}",
            gmail_thread_id=f"thread-{i}",
            sender=f"sender{i}@example.com",
            sender_domain="example.com",
            subject=f"Subject {i}",
            snippet=f"Snippet {i}",
        )
        for i in range(count)
    ]


def _make_ai_response(*, emails: list[EmailMetadata]) -> list[dict]:
    return [
        {
            "gmail_message_id": e.gmail_message_id,
            "category": "promotions",
            "importance": 2,
            "sender_type": "marketing",
            "confidence": 0.9,
        }
        for e in emails
    ]


def _build_service(*, response_text: str) -> ClaudeClassificationService:
    from anthropic.types import TextBlock

    service = ClaudeClassificationService(api_key="test-key", model="test-model")
    mock_client = AsyncMock()
    content_block = TextBlock(type="text", text=response_text)
    mock_client.messages.create.return_value = MagicMock(content=[content_block])
    service._client = mock_client
    return service


class TestClaudeClassificationService:
    @pytest.mark.asyncio
    async def test_classify_emails_returns_results(self) -> None:
        emails = _make_emails(count=2)
        ai_response = _make_ai_response(emails=emails)
        service = _build_service(response_text=json.dumps(ai_response))

        results = await service.classify_emails(emails=emails)

        assert len(results) == 2
        assert all(isinstance(r, ClassificationResult) for r in results)
        assert results[0].gmail_message_id == "msg-0"
        assert results[0].category == "promotions"
        assert results[0].importance == 2
        assert results[0].sender_type == "marketing"
        assert results[0].confidence == 0.9

    @pytest.mark.asyncio
    async def test_classify_emails_empty_input(self) -> None:
        service = _build_service(response_text="[]")

        results = await service.classify_emails(emails=[])

        assert results == []
        service._client.messages.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_classify_emails_malformed_json_raises(self) -> None:
        service = _build_service(response_text="not valid json")

        with pytest.raises(json.JSONDecodeError):
            await service.classify_emails(emails=_make_emails(count=1))

    @pytest.mark.asyncio
    async def test_prompt_includes_email_data(self) -> None:
        emails = _make_emails(count=1)
        ai_response = _make_ai_response(emails=emails)
        service = _build_service(response_text=json.dumps(ai_response))

        await service.classify_emails(emails=emails)

        call_kwargs = service._client.messages.create.call_args
        user_message = call_kwargs.kwargs["messages"][0]["content"]
        assert "msg-0" in user_message
        assert "sender0@example.com" in user_message

    @pytest.mark.asyncio
    async def test_classify_with_existing_categories(self) -> None:
        emails = _make_emails(count=1)
        ai_response = _make_ai_response(emails=emails)
        service = _build_service(response_text=json.dumps(ai_response))

        custom_cats = ["primary", "promotions", "receipts", "travel"]
        await service.classify_emails(
            emails=emails, existing_categories=custom_cats
        )

        call_kwargs = service._client.messages.create.call_args
        system_prompt = call_kwargs.kwargs["system"]
        assert "receipts" in system_prompt
        assert "travel" in system_prompt

    @pytest.mark.asyncio
    async def test_classify_without_existing_categories_uses_defaults(self) -> None:
        emails = _make_emails(count=1)
        ai_response = _make_ai_response(emails=emails)
        service = _build_service(response_text=json.dumps(ai_response))

        await service.classify_emails(emails=emails)

        call_kwargs = service._client.messages.create.call_args
        system_prompt = call_kwargs.kwargs["system"]
        assert "primary" in system_prompt
        assert "promotions" in system_prompt
        assert "newsletters" in system_prompt


class TestVerifyCategories:
    @pytest.mark.asyncio
    async def test_verify_returns_actions(self) -> None:
        verification_response = {
            "category_actions": {
                "promotions": ["mark_read", "move_to_category"],
                "spam": ["mark_spam"],
            },
        }
        service = _build_service(
            response_text=json.dumps(verification_response)
        )

        result = await service.verify_categories(
            category_samples={
                "promotions": [{"subject": "Sale!", "sender": "shop@store.com"}],
                "spam": [{"subject": "Win $$$", "sender": "spam@bad.com"}],
            }
        )

        assert isinstance(result, VerificationResult)
        assert result.merges == []
        assert result.category_actions["promotions"] == ["mark_read", "move_to_category"]
        assert result.category_actions["spam"] == ["mark_spam"]

    @pytest.mark.asyncio
    async def test_verify_empty_categories(self) -> None:
        service = _build_service(response_text="{}")

        result = await service.verify_categories(category_samples={})

        assert result.merges == []
        assert result.category_actions == {}
        service._client.messages.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_verify_no_merges(self) -> None:
        verification_response = {
            "merges": [],
            "category_actions": {
                "primary": ["keep"],
                "promotions": ["mark_read"],
            },
        }
        service = _build_service(
            response_text=json.dumps(verification_response)
        )

        result = await service.verify_categories(
            category_samples={
                "primary": [{"subject": "Hi", "sender": "friend@mail.com"}],
                "promotions": [{"subject": "Sale", "sender": "shop@store.com"}],
            }
        )

        assert result.merges == []
        assert len(result.category_actions) == 2

    @pytest.mark.asyncio
    async def test_verify_sends_samples_to_ai(self) -> None:
        verification_response = {"merges": [], "category_actions": {}}
        service = _build_service(
            response_text=json.dumps(verification_response)
        )

        samples = {
            "promotions": [
                {"subject": "Big Sale", "sender": "shop@store.com"},
            ]
        }
        await service.verify_categories(category_samples=samples)

        call_kwargs = service._client.messages.create.call_args
        user_message = call_kwargs.kwargs["messages"][0]["content"]
        assert "Big Sale" in user_message
        assert "shop@store.com" in user_message
