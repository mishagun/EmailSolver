from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.db import ClassifiedEmail
from app.models.schemas import (
    CategoryMerge,
    ClassificationResult,
    EmailMetadata,
    VerificationResult,
)
from app.services.analysis_service import AnalysisService


def _make_email_metadata(*, msg_id: str = "msg-1") -> EmailMetadata:
    return EmailMetadata(
        gmail_message_id=msg_id,
        gmail_thread_id="thread-1",
        sender="sender@example.com",
        sender_domain="example.com",
        subject="Test Email",
        snippet="Hello world",
        has_unsubscribe=False,
    )


def _make_classification_result(
    *, msg_id: str = "msg-1", category: str = "promotions"
) -> ClassificationResult:
    return ClassificationResult(
        gmail_message_id=msg_id,
        category=category,
        importance=2,
        sender_type="marketing",
        confidence=0.9,
    )


def _make_classified_email(
    *,
    email_id: int = 1,
    msg_id: str = "msg-1",
    category: str = "promotions",
    action_taken: str | None = None,
    has_unsubscribe: bool = False,
) -> ClassifiedEmail:
    email = ClassifiedEmail(
        analysis_id=1,
        gmail_message_id=msg_id,
        gmail_thread_id="thread-1",
        sender="sender@example.com",
        sender_domain="example.com",
        subject="Test Email",
        snippet="Hello",
        category=category,
        importance=2,
        sender_type="marketing",
        confidence=0.9,
        has_unsubscribe=has_unsubscribe,
        action_taken=action_taken,
    )
    email.id = email_id
    return email


def _default_verification() -> VerificationResult:
    return VerificationResult(
        merges=[],
        category_actions={"promotions": ["move_to_category", "mark_read"]},
    )


def _build_service(
    *,
    email_service: MagicMock | None = None,
    classification_service: MagicMock | None = None,
    security_service: MagicMock | None = None,
    classified_email_repo: MagicMock | None = None,
) -> AnalysisService:
    if email_service is None:
        email_service = MagicMock()
        email_service.build_credentials = MagicMock(return_value=MagicMock())
        email_service.list_messages = AsyncMock(return_value=["msg-1"])
        email_service.get_messages_batch = AsyncMock(
            return_value=[_make_email_metadata()]
        )
        email_service.modify_messages = AsyncMock()

    if classification_service is None:
        classification_service = MagicMock()
        classification_service.classify_emails = AsyncMock(
            return_value=[_make_classification_result()]
        )
        classification_service.verify_categories = AsyncMock(
            return_value=_default_verification()
        )

    if security_service is None:
        security_service = MagicMock()
        security_service.decrypt_token = MagicMock(return_value="decrypted-token")

    if classified_email_repo is None:
        classified_email_repo = MagicMock()
        classified_email_repo.bulk_create = AsyncMock(
            return_value=[_make_classified_email()]
        )
        classified_email_repo.update_action_taken = AsyncMock()
        classified_email_repo.bulk_update_action_taken = AsyncMock()
        classified_email_repo.bulk_update_category = AsyncMock()

    session_maker = MagicMock()

    return AnalysisService(
        email_service=email_service,
        classification_service=classification_service,
        security_service=security_service,
        classified_email_repo=classified_email_repo,
        async_session_maker=session_maker,
    )


def _setup_analysis_repo_mock(*, service: AnalysisService) -> AsyncMock:
    mock_repo = AsyncMock()
    service._create_analysis_repo = MagicMock(return_value=mock_repo)
    return mock_repo


class TestRunAnalysis:
    @pytest.mark.asyncio
    async def test_happy_path(self) -> None:
        service = _build_service()
        mock_repo = _setup_analysis_repo_mock(service=service)

        await service._run_analysis(
            analysis_id=1,
            encrypted_access_token="enc-access",
            encrypted_refresh_token="enc-refresh",
            query="is:unread",
            max_emails=100,
            auto_apply=False,
        )

        update_calls = mock_repo.update_status.call_args_list
        assert update_calls[0].kwargs["status"] == "processing"
        final_call = update_calls[-1].kwargs
        assert final_call["status"] == "completed"
        assert final_call["processed_emails"] == 1

        service._classification_service.classify_emails.assert_awaited_once()
        service._classified_email_repo.bulk_create.assert_awaited_once()
        service._classification_service.verify_categories.assert_awaited_once()
        mock_repo.update_category_actions.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_classify_receives_existing_categories(self) -> None:
        service = _build_service()
        _setup_analysis_repo_mock(service=service)

        await service._run_analysis(
            analysis_id=1,
            encrypted_access_token="enc-access",
            encrypted_refresh_token="enc-refresh",
            query="is:unread",
            max_emails=100,
            auto_apply=False,
        )

        call_kwargs = service._classification_service.classify_emails.call_args.kwargs
        assert "existing_categories" in call_kwargs
        assert "primary" in call_kwargs["existing_categories"]
        assert "promotions" in call_kwargs["existing_categories"]

    @pytest.mark.asyncio
    async def test_custom_categories_passed_through(self) -> None:
        service = _build_service()
        _setup_analysis_repo_mock(service=service)

        await service._run_analysis(
            analysis_id=1,
            encrypted_access_token="enc-access",
            encrypted_refresh_token="enc-refresh",
            query="is:unread",
            max_emails=100,
            auto_apply=False,
            custom_categories=["receipts", "travel"],
        )

        call_kwargs = service._classification_service.classify_emails.call_args.kwargs
        assert "receipts" in call_kwargs["existing_categories"]
        assert "travel" in call_kwargs["existing_categories"]

    @pytest.mark.asyncio
    async def test_new_categories_accumulate_across_batches(self) -> None:
        emails = [_make_email_metadata(msg_id=f"msg-{i}") for i in range(25)]
        results_batch1 = [
            _make_classification_result(msg_id=f"msg-{i}", category="receipts")
            for i in range(20)
        ]
        results_batch2 = [
            _make_classification_result(msg_id=f"msg-{i}") for i in range(20, 25)
        ]

        email_service = MagicMock()
        email_service.build_credentials = MagicMock(return_value=MagicMock())
        email_service.list_messages = AsyncMock(
            return_value=[f"msg-{i}" for i in range(25)]
        )
        email_service.get_messages_batch = AsyncMock(return_value=emails)

        classification_service = MagicMock()
        classification_service.classify_emails = AsyncMock(
            side_effect=[results_batch1, results_batch2]
        )
        classification_service.verify_categories = AsyncMock(
            return_value=_default_verification()
        )

        created_batch1 = [
            _make_classified_email(email_id=i + 1, msg_id=f"msg-{i}", category="receipts")
            for i in range(20)
        ]
        created_batch2 = [
            _make_classified_email(email_id=i + 21, msg_id=f"msg-{i}")
            for i in range(20, 25)
        ]

        classified_email_repo = MagicMock()
        classified_email_repo.bulk_create = AsyncMock(
            side_effect=[created_batch1, created_batch2]
        )
        classified_email_repo.bulk_update_action_taken = AsyncMock()
        classified_email_repo.bulk_update_category = AsyncMock()

        service = _build_service(
            email_service=email_service,
            classification_service=classification_service,
            classified_email_repo=classified_email_repo,
        )
        _setup_analysis_repo_mock(service=service)

        await service._run_analysis(
            analysis_id=1,
            encrypted_access_token="enc-access",
            encrypted_refresh_token="enc-refresh",
            query="is:unread",
            max_emails=100,
            auto_apply=False,
        )

        second_call = classification_service.classify_emails.call_args_list[1].kwargs
        assert "receipts" in second_call["existing_categories"]

    @pytest.mark.asyncio
    async def test_empty_inbox(self) -> None:
        email_service = MagicMock()
        email_service.build_credentials = MagicMock(return_value=MagicMock())
        email_service.list_messages = AsyncMock(return_value=[])
        service = _build_service(email_service=email_service)
        _setup_analysis_repo_mock(service=service)
        mock_repo = service._create_analysis_repo()

        await service._run_analysis(
            analysis_id=1,
            encrypted_access_token="enc-access",
            encrypted_refresh_token="enc-refresh",
            query="is:unread",
            max_emails=100,
            auto_apply=False,
        )

        final_call = mock_repo.update_status.call_args_list[-1].kwargs
        assert final_call["status"] == "completed"
        assert final_call["total_emails"] == 0
        assert final_call["processed_emails"] == 0

    @pytest.mark.asyncio
    async def test_error_handling(self) -> None:
        email_service = MagicMock()
        email_service.build_credentials = MagicMock(side_effect=RuntimeError("boom"))
        security_service = MagicMock()
        security_service.decrypt_token = MagicMock(return_value="token")
        service = _build_service(
            email_service=email_service, security_service=security_service
        )
        _setup_analysis_repo_mock(service=service)
        mock_repo = service._create_analysis_repo()

        await service._run_analysis(
            analysis_id=1,
            encrypted_access_token="enc-access",
            encrypted_refresh_token="enc-refresh",
            query="is:unread",
            max_emails=100,
            auto_apply=False,
        )

        final_call = mock_repo.update_status.call_args_list[-1].kwargs
        assert final_call["status"] == "failed"
        assert "boom" in final_call["error_message"]

    @pytest.mark.asyncio
    async def test_auto_apply_uses_category_actions(self) -> None:
        email_service = MagicMock()
        email_service.build_credentials = MagicMock(return_value=MagicMock())
        email_service.list_messages = AsyncMock(return_value=["msg-1"])
        email_service.get_messages_batch = AsyncMock(
            return_value=[_make_email_metadata()]
        )
        email_service.modify_messages = AsyncMock()

        classification_service = MagicMock()
        classification_service.classify_emails = AsyncMock(
            return_value=[_make_classification_result()]
        )
        classification_service.verify_categories = AsyncMock(
            return_value=VerificationResult(
                merges=[],
                category_actions={"promotions": ["mark_read"]},
            )
        )

        classified_email_repo = MagicMock()
        classified_email_repo.bulk_create = AsyncMock(
            return_value=[_make_classified_email()]
        )
        classified_email_repo.bulk_update_action_taken = AsyncMock()
        classified_email_repo.bulk_update_category = AsyncMock()

        service = _build_service(
            email_service=email_service,
            classification_service=classification_service,
            classified_email_repo=classified_email_repo,
        )
        _setup_analysis_repo_mock(service=service)

        await service._run_analysis(
            analysis_id=1,
            encrypted_access_token="enc-access",
            encrypted_refresh_token="enc-refresh",
            query="is:unread",
            max_emails=100,
            auto_apply=True,
        )

        email_service.modify_messages.assert_awaited()
        classified_email_repo.bulk_update_action_taken.assert_awaited()

    @pytest.mark.asyncio
    async def test_verification_merges_applied(self) -> None:
        classification_service = MagicMock()
        classification_service.classify_emails = AsyncMock(
            return_value=[_make_classification_result(category="promo")]
        )
        classification_service.verify_categories = AsyncMock(
            return_value=VerificationResult(
                merges=[CategoryMerge(from_category="promo", to_category="promotions")],
                category_actions={"promotions": ["mark_read"]},
            )
        )

        classified_email_repo = MagicMock()
        classified_email_repo.bulk_create = AsyncMock(
            return_value=[_make_classified_email(category="promo")]
        )
        classified_email_repo.bulk_update_action_taken = AsyncMock()
        classified_email_repo.bulk_update_category = AsyncMock()

        service = _build_service(
            classification_service=classification_service,
            classified_email_repo=classified_email_repo,
        )
        mock_repo = _setup_analysis_repo_mock(service=service)

        await service._run_analysis(
            analysis_id=1,
            encrypted_access_token="enc-access",
            encrypted_refresh_token="enc-refresh",
            query="is:unread",
            max_emails=100,
            auto_apply=False,
        )

        classified_email_repo.bulk_update_category.assert_awaited_once_with(
            analysis_id=1, from_category="promo", to_category="promotions"
        )
        mock_repo.update_category_actions.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_category_actions_stored_on_analysis(self) -> None:
        expected_actions = {"promotions": ["mark_read", "move_to_category"]}
        classification_service = MagicMock()
        classification_service.classify_emails = AsyncMock(
            return_value=[_make_classification_result()]
        )
        classification_service.verify_categories = AsyncMock(
            return_value=VerificationResult(
                merges=[], category_actions=expected_actions
            )
        )

        classified_email_repo = MagicMock()
        classified_email_repo.bulk_create = AsyncMock(
            return_value=[_make_classified_email()]
        )
        classified_email_repo.bulk_update_action_taken = AsyncMock()
        classified_email_repo.bulk_update_category = AsyncMock()

        service = _build_service(
            classification_service=classification_service,
            classified_email_repo=classified_email_repo,
        )
        mock_repo = _setup_analysis_repo_mock(service=service)

        await service._run_analysis(
            analysis_id=1,
            encrypted_access_token="enc-access",
            encrypted_refresh_token="enc-refresh",
            query="is:unread",
            max_emails=100,
            auto_apply=False,
        )

        mock_repo.update_category_actions.assert_awaited_once_with(
            analysis_id=1, category_actions=expected_actions
        )

    @pytest.mark.asyncio
    async def test_batch_classification(self) -> None:
        emails = [
            _make_email_metadata(msg_id=f"msg-{i}") for i in range(25)
        ]
        results_batch1 = [
            _make_classification_result(msg_id=f"msg-{i}") for i in range(20)
        ]
        results_batch2 = [
            _make_classification_result(msg_id=f"msg-{i}") for i in range(20, 25)
        ]

        email_service = MagicMock()
        email_service.build_credentials = MagicMock(return_value=MagicMock())
        email_service.list_messages = AsyncMock(
            return_value=[f"msg-{i}" for i in range(25)]
        )
        email_service.get_messages_batch = AsyncMock(return_value=emails)
        email_service.modify_messages = AsyncMock()

        classification_service = MagicMock()
        classification_service.classify_emails = AsyncMock(
            side_effect=[results_batch1, results_batch2]
        )
        classification_service.verify_categories = AsyncMock(
            return_value=_default_verification()
        )

        created_batch1 = [
            _make_classified_email(email_id=i + 1, msg_id=f"msg-{i}")
            for i in range(20)
        ]
        created_batch2 = [
            _make_classified_email(email_id=i + 21, msg_id=f"msg-{i}")
            for i in range(20, 25)
        ]

        classified_email_repo = MagicMock()
        classified_email_repo.bulk_create = AsyncMock(
            side_effect=[created_batch1, created_batch2]
        )
        classified_email_repo.update_action_taken = AsyncMock()
        classified_email_repo.bulk_update_action_taken = AsyncMock()
        classified_email_repo.bulk_update_category = AsyncMock()

        service = _build_service(
            email_service=email_service,
            classification_service=classification_service,
            classified_email_repo=classified_email_repo,
        )
        _setup_analysis_repo_mock(service=service)

        await service._run_analysis(
            analysis_id=1,
            encrypted_access_token="enc-access",
            encrypted_refresh_token="enc-refresh",
            query="is:unread",
            max_emails=100,
            auto_apply=False,
        )

        assert classification_service.classify_emails.await_count == 2
        assert classified_email_repo.bulk_create.await_count == 2


class TestApplyActions:
    @pytest.mark.asyncio
    async def test_apply_move_to_category(self) -> None:
        service = _build_service()
        promo_email = _make_classified_email(
            email_id=1, msg_id="msg-1", category="promotions"
        )

        await service._apply_actions(
            classified_emails=[promo_email],
            action="move_to_category",
            encrypted_access_token="enc-access",
            encrypted_refresh_token="enc-refresh",
        )

        service._email_service.modify_messages.assert_awaited_once_with(
            credentials=service._email_service.build_credentials.return_value,
            message_ids=["msg-1"],
            add_labels=["CATEGORY_PROMOTIONS"],
            remove_labels=["INBOX"],
        )
        service._classified_email_repo.bulk_update_action_taken.assert_awaited_once_with(
            email_ids=[1], action_taken="move_to_category"
        )

    @pytest.mark.asyncio
    async def test_apply_actions_skips_already_applied(self) -> None:
        service = _build_service()
        already_applied = _make_classified_email(
            email_id=1, category="spam", action_taken="mark_spam"
        )

        await service.apply_actions_for_analysis(
            classified_emails=[already_applied],
            action="mark_spam",
            encrypted_access_token="enc-access",
            encrypted_refresh_token="enc-refresh",
        )

        service._email_service.modify_messages.assert_not_called()

    @pytest.mark.asyncio
    async def test_apply_actions_keep_is_noop(self) -> None:
        service = _build_service()
        primary_email = _make_classified_email(
            email_id=1, msg_id="msg-1", category="primary"
        )

        await service._apply_actions(
            classified_emails=[primary_email],
            action="keep",
            encrypted_access_token="enc-access",
            encrypted_refresh_token="enc-refresh",
        )

        service._email_service.modify_messages.assert_not_called()

    @pytest.mark.asyncio
    async def test_apply_actions_mark_spam(self) -> None:
        service = _build_service()
        spam_email = _make_classified_email(
            email_id=1, msg_id="msg-1", category="spam"
        )

        await service._apply_actions(
            classified_emails=[spam_email],
            action="mark_spam",
            encrypted_access_token="enc-access",
            encrypted_refresh_token="enc-refresh",
        )

        service._email_service.modify_messages.assert_awaited_once_with(
            credentials=service._email_service.build_credentials.return_value,
            message_ids=["msg-1"],
            add_labels=["SPAM"],
            remove_labels=["INBOX"],
        )
        service._classified_email_repo.bulk_update_action_taken.assert_awaited_once_with(
            email_ids=[1], action_taken="mark_spam"
        )

    @pytest.mark.asyncio
    async def test_apply_actions_mark_read(self) -> None:
        service = _build_service()
        email = _make_classified_email(
            email_id=1, msg_id="msg-1", category="promotions"
        )

        await service._apply_actions(
            classified_emails=[email],
            action="mark_read",
            encrypted_access_token="enc-access",
            encrypted_refresh_token="enc-refresh",
        )

        service._email_service.modify_messages.assert_awaited_once_with(
            credentials=service._email_service.build_credentials.return_value,
            message_ids=["msg-1"],
            remove_labels=["UNREAD"],
        )
        service._classified_email_repo.bulk_update_action_taken.assert_awaited_once_with(
            email_ids=[1], action_taken="mark_read"
        )

    @pytest.mark.asyncio
    async def test_apply_actions_unsubscribe(self) -> None:
        service = _build_service()
        newsletter_email = _make_classified_email(
            email_id=1, msg_id="msg-1", category="newsletters", has_unsubscribe=True
        )

        await service._apply_actions(
            classified_emails=[newsletter_email],
            action="unsubscribe",
            encrypted_access_token="enc-access",
            encrypted_refresh_token="enc-refresh",
        )

        service._email_service.modify_messages.assert_awaited_once_with(
            credentials=service._email_service.build_credentials.return_value,
            message_ids=["msg-1"],
            add_labels=["SPAM"],
            remove_labels=["INBOX"],
        )
        service._classified_email_repo.bulk_update_action_taken.assert_awaited_once_with(
            email_ids=[1], action_taken="unsubscribe"
        )


class TestBuildCategorySamples:
    def test_builds_samples_grouped_by_category(self) -> None:
        emails = [
            _make_classified_email(email_id=1, category="promotions"),
            _make_classified_email(email_id=2, category="spam"),
        ]

        result = AnalysisService._build_category_samples(classified_emails=emails)

        assert "promotions" in result
        assert "spam" in result
        assert len(result["promotions"]) == 1
        assert len(result["spam"]) == 1

    def test_limits_to_5_samples_per_category(self) -> None:
        emails = [
            _make_classified_email(email_id=i, category="promotions")
            for i in range(10)
        ]

        result = AnalysisService._build_category_samples(classified_emails=emails)

        assert len(result["promotions"]) == 5
