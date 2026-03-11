from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.schemas import ClassificationResult
from tests.analysis_helpers import (
    build_service,
    default_verification,
    make_classification_result,
    make_classified_email,
    make_email_metadata,
    setup_analysis_repo_mock,
)


class TestRunInboxScan:
    @pytest.mark.asyncio
    async def test_happy_path(self) -> None:
        # Arrange
        email_meta = make_email_metadata()
        email_meta.gmail_category = "promotions"
        email_service = MagicMock()
        email_service.build_credentials = MagicMock(return_value=MagicMock())
        email_service.list_messages = AsyncMock(return_value=["msg-1"])
        email_service.get_messages_batch = AsyncMock(return_value=[email_meta])
        email_service.modify_messages = AsyncMock()

        classified_email_repo = MagicMock()
        classified_email_repo.bulk_create = AsyncMock(
            return_value=[make_classified_email(category="promotions")]
        )
        classified_email_repo.bulk_update_action_taken = AsyncMock()
        classified_email_repo.bulk_record_action = AsyncMock()
        classified_email_repo.pop_last_action = AsyncMock(return_value={})

        service = build_service(
            email_service=email_service,
            classified_email_repo=classified_email_repo,
        )
        mock_repo = setup_analysis_repo_mock(service=service)

        # Act
        await service._run_inbox_scan(
            analysis_id=1,
            encrypted_access_token="enc-access",
            encrypted_refresh_token="enc-refresh",
            unread_only=True,
            max_emails=100,
            auto_apply=False,
        )

        # Assert
        update_calls = mock_repo.update_status.call_args_list
        assert update_calls[0].kwargs["status"] == "processing"
        final_call = update_calls[-1].kwargs
        assert final_call["status"] == "completed"
        assert final_call["processed_emails"] == 1
        classified_email_repo.bulk_create.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_empty_inbox(self) -> None:
        # Arrange
        email_service = MagicMock()
        email_service.build_credentials = MagicMock(return_value=MagicMock())
        email_service.list_messages = AsyncMock(return_value=[])
        service = build_service(email_service=email_service)
        setup_analysis_repo_mock(service=service)
        mock_repo = service._create_analysis_repo()

        # Act
        await service._run_inbox_scan(
            analysis_id=1,
            encrypted_access_token="enc-access",
            encrypted_refresh_token="enc-refresh",
            unread_only=True,
            max_emails=100,
            auto_apply=False,
        )

        # Assert
        final_call = mock_repo.update_status.call_args_list[-1].kwargs
        assert final_call["status"] == "completed"
        assert final_call["total_emails"] == 0
        assert final_call["processed_emails"] == 0

    @pytest.mark.asyncio
    async def test_error_handling(self) -> None:
        # Arrange
        email_service = MagicMock()
        email_service.build_credentials = MagicMock(side_effect=RuntimeError("boom"))
        security_service = MagicMock()
        security_service.decrypt_token = MagicMock(return_value="token")
        service = build_service(
            email_service=email_service, security_service=security_service
        )
        setup_analysis_repo_mock(service=service)
        mock_repo = service._create_analysis_repo()

        # Act
        await service._run_inbox_scan(
            analysis_id=1,
            encrypted_access_token="enc-access",
            encrypted_refresh_token="enc-refresh",
            unread_only=True,
            max_emails=100,
            auto_apply=False,
        )

        # Assert
        final_call = mock_repo.update_status.call_args_list[-1].kwargs
        assert final_call["status"] == "failed"
        assert "boom" in final_call["error_message"]

    @pytest.mark.asyncio
    async def test_uses_gmail_category_as_category(self) -> None:
        # Arrange
        email_meta = make_email_metadata()
        email_meta.gmail_category = "social"
        email_service = MagicMock()
        email_service.build_credentials = MagicMock(return_value=MagicMock())
        email_service.list_messages = AsyncMock(return_value=["msg-1"])
        email_service.get_messages_batch = AsyncMock(return_value=[email_meta])

        created_emails: list = []

        async def capture_bulk_create(emails):
            created_emails.extend(emails)
            for e in emails:
                e.id = 1
            return emails

        classified_email_repo = MagicMock()
        classified_email_repo.bulk_create = AsyncMock(side_effect=capture_bulk_create)
        classified_email_repo.bulk_update_action_taken = AsyncMock()
        classified_email_repo.bulk_record_action = AsyncMock()
        classified_email_repo.pop_last_action = AsyncMock(return_value={})

        service = build_service(
            email_service=email_service,
            classified_email_repo=classified_email_repo,
        )
        setup_analysis_repo_mock(service=service)

        # Act
        await service._run_inbox_scan(
            analysis_id=1,
            encrypted_access_token="enc-access",
            encrypted_refresh_token="enc-refresh",
            unread_only=True,
            max_emails=100,
            auto_apply=False,
        )

        # Assert
        assert len(created_emails) == 1
        assert created_emails[0].category == "social"

    @pytest.mark.asyncio
    async def test_no_classification_service_calls(self) -> None:
        # Arrange
        email_meta = make_email_metadata()
        email_meta.gmail_category = "updates"
        email_service = MagicMock()
        email_service.build_credentials = MagicMock(return_value=MagicMock())
        email_service.list_messages = AsyncMock(return_value=["msg-1"])
        email_service.get_messages_batch = AsyncMock(return_value=[email_meta])

        classification_service = MagicMock()
        classification_service.classify_emails = AsyncMock()
        classification_service.verify_categories = AsyncMock()

        classified_email_repo = MagicMock()
        classified_email_repo.bulk_create = AsyncMock(
            return_value=[make_classified_email(category="updates")]
        )
        classified_email_repo.bulk_update_action_taken = AsyncMock()
        classified_email_repo.bulk_record_action = AsyncMock()
        classified_email_repo.pop_last_action = AsyncMock(return_value={})

        service = build_service(
            email_service=email_service,
            classification_service=classification_service,
            classified_email_repo=classified_email_repo,
        )
        setup_analysis_repo_mock(service=service)

        # Act
        await service._run_inbox_scan(
            analysis_id=1,
            encrypted_access_token="enc-access",
            encrypted_refresh_token="enc-refresh",
            unread_only=True,
            max_emails=100,
            auto_apply=False,
        )

        # Assert
        classification_service.classify_emails.assert_not_awaited()
        classification_service.verify_categories.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_auto_apply_uses_default_actions(self) -> None:
        # Arrange
        spam_meta = make_email_metadata(msg_id="msg-spam")
        spam_meta.gmail_category = "spam"
        promo_meta = make_email_metadata(msg_id="msg-promo")
        promo_meta.gmail_category = "promotions"

        email_service = MagicMock()
        email_service.build_credentials = MagicMock(return_value=MagicMock())
        email_service.list_messages = AsyncMock(return_value=["msg-spam", "msg-promo"])
        email_service.get_messages_batch = AsyncMock(
            return_value=[spam_meta, promo_meta]
        )
        email_service.modify_messages = AsyncMock()
        email_service.get_or_create_label = AsyncMock(return_value="label-id")

        spam_email = make_classified_email(
            email_id=1, msg_id="msg-spam", category="spam"
        )
        promo_email = make_classified_email(
            email_id=2, msg_id="msg-promo", category="promotions"
        )

        classified_email_repo = MagicMock()
        classified_email_repo.bulk_create = AsyncMock(
            return_value=[spam_email, promo_email]
        )
        classified_email_repo.bulk_update_action_taken = AsyncMock()
        classified_email_repo.bulk_record_action = AsyncMock()
        classified_email_repo.pop_last_action = AsyncMock(return_value={})

        service = build_service(
            email_service=email_service,
            classified_email_repo=classified_email_repo,
        )
        mock_repo = setup_analysis_repo_mock(service=service)

        # Act
        await service._run_inbox_scan(
            analysis_id=1,
            encrypted_access_token="enc-access",
            encrypted_refresh_token="enc-refresh",
            unread_only=True,
            max_emails=100,
            auto_apply=True,
        )

        # Assert
        mock_repo.update_category_actions.assert_awaited_once_with(
            analysis_id=1,
            category_actions={"spam": ["mark_spam"], "promotions": ["mark_read"]},
        )
        email_service.modify_messages.assert_awaited()
        classified_email_repo.bulk_update_action_taken.assert_awaited()

    @pytest.mark.asyncio
    async def test_batched_fetching(self) -> None:
        # Arrange
        msg_ids = [f"msg-{i}" for i in range(75)]
        emails_batch1 = [
            make_email_metadata(msg_id=f"msg-{i}") for i in range(50)
        ]
        for e in emails_batch1:
            e.gmail_category = "primary"
        emails_batch2 = [
            make_email_metadata(msg_id=f"msg-{i}") for i in range(50, 75)
        ]
        for e in emails_batch2:
            e.gmail_category = "primary"

        email_service = MagicMock()
        email_service.build_credentials = MagicMock(return_value=MagicMock())
        email_service.list_messages = AsyncMock(return_value=msg_ids)
        email_service.get_messages_batch = AsyncMock(
            side_effect=[emails_batch1, emails_batch2]
        )

        created_batch1 = [
            make_classified_email(email_id=i + 1, msg_id=f"msg-{i}", category="primary")
            for i in range(50)
        ]
        created_batch2 = [
            make_classified_email(email_id=i + 51, msg_id=f"msg-{i}", category="primary")
            for i in range(50, 75)
        ]

        classified_email_repo = MagicMock()
        classified_email_repo.bulk_create = AsyncMock(
            side_effect=[created_batch1, created_batch2]
        )
        classified_email_repo.bulk_update_action_taken = AsyncMock()
        classified_email_repo.bulk_record_action = AsyncMock()
        classified_email_repo.pop_last_action = AsyncMock(return_value={})

        service = build_service(
            email_service=email_service,
            classified_email_repo=classified_email_repo,
        )
        setup_analysis_repo_mock(service=service)

        # Act
        await service._run_inbox_scan(
            analysis_id=1,
            encrypted_access_token="enc-access",
            encrypted_refresh_token="enc-refresh",
            unread_only=True,
            max_emails=100,
            auto_apply=False,
        )

        # Assert
        assert email_service.get_messages_batch.await_count == 2
        assert classified_email_repo.bulk_create.await_count == 2


class TestStartAnalysisRouting:
    @pytest.mark.asyncio
    async def test_routes_to_inbox_scan(self) -> None:
        # Arrange
        service = build_service()
        setup_analysis_repo_mock(service=service)

        with patch.object(service, "_run_inbox_scan", new_callable=AsyncMock) as mock_scan, \
             patch.object(service, "_run_analysis", new_callable=AsyncMock):
            # Act
            task = service.start_analysis(
                analysis_id=1,
                analysis_type="inbox_scan",
                encrypted_access_token="enc-access",
                encrypted_refresh_token="enc-refresh",
                unread_only=True,
                max_emails=100,
                auto_apply=False,
            )
            await task

            # Assert
            mock_scan.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_routes_to_ai_by_default(self) -> None:
        # Arrange
        service = build_service()
        setup_analysis_repo_mock(service=service)

        with patch.object(service, "_run_inbox_scan", new_callable=AsyncMock), \
             patch.object(service, "_run_analysis", new_callable=AsyncMock) as mock_ai:
            # Act
            task = service.start_analysis(
                analysis_id=1,
                analysis_type="ai",
                encrypted_access_token="enc-access",
                encrypted_refresh_token="enc-refresh",
                unread_only=True,
                max_emails=100,
                auto_apply=False,
            )
            await task

            # Assert
            mock_ai.assert_awaited_once()


class TestBatchClassification:
    @pytest.mark.asyncio
    async def test_batch_api_used_when_over_threshold(self) -> None:
        # Arrange
        emails = [make_email_metadata(msg_id=f"msg-{i}") for i in range(600)]
        results_by_batch: dict[str, list[ClassificationResult]] = {}
        for batch_idx in range(30):
            start = batch_idx * 20
            batch_results = [
                make_classification_result(msg_id=f"msg-{start + j}")
                for j in range(20)
            ]
            results_by_batch[f"batch-{batch_idx}"] = batch_results

        classification_service = MagicMock()
        classification_service.submit_batch_classification = AsyncMock(
            return_value="test-batch-id"
        )
        classification_service.check_batch_status = AsyncMock(return_value="ended")
        classification_service.retrieve_batch_results = AsyncMock(
            return_value=results_by_batch
        )
        classification_service.verify_categories = AsyncMock(
            return_value=default_verification()
        )

        email_service = MagicMock()
        email_service.build_credentials = MagicMock(return_value=MagicMock())
        email_service.list_messages = AsyncMock(
            return_value=[f"msg-{i}" for i in range(600)]
        )
        email_service.get_messages_batch = AsyncMock(return_value=emails)
        email_service.modify_messages = AsyncMock()

        classified_email_repo = MagicMock()
        classified_email_repo.bulk_create = AsyncMock(side_effect=lambda emails: emails)
        classified_email_repo.bulk_update_category = AsyncMock()

        service = build_service(
            email_service=email_service,
            classification_service=classification_service,
            classified_email_repo=classified_email_repo,
        )
        mock_repo = setup_analysis_repo_mock(service=service)

        # Act
        await service._run_analysis(
            analysis_id=1,
            encrypted_access_token="enc-access",
            encrypted_refresh_token="enc-refresh",
            unread_only=True,
            max_emails=600,
            auto_apply=False,
        )

        # Assert
        classification_service.submit_batch_classification.assert_awaited_once()
        classification_service.check_batch_status.assert_awaited_once()
        classification_service.retrieve_batch_results.assert_awaited_once()
        classification_service.classify_emails.assert_not_called()

        batch_call = mock_repo.update_status.call_args_list
        batch_id_calls = [c for c in batch_call if c.kwargs.get("batch_id")]
        assert len(batch_id_calls) == 1
        assert batch_id_calls[0].kwargs["batch_id"] == "test-batch-id"

    @pytest.mark.asyncio
    async def test_realtime_used_when_under_threshold(self) -> None:
        # Arrange
        service = build_service()
        setup_analysis_repo_mock(service=service)

        # Act
        await service._run_analysis(
            analysis_id=1,
            encrypted_access_token="enc-access",
            encrypted_refresh_token="enc-refresh",
            unread_only=True,
            max_emails=100,
            auto_apply=False,
        )

        # Assert
        service._classification_service.classify_emails.assert_awaited_once()
        service._classification_service.submit_batch_classification.assert_not_called()
