from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.schemas import VerificationResult
from tests.analysis_helpers import (
    build_service,
    default_verification,
    make_classification_result,
    make_classified_email,
    make_email_metadata,
    setup_analysis_repo_mock,
)


class TestRunAnalysis:
    @pytest.mark.asyncio
    async def test_happy_path(self) -> None:
        service = build_service()
        mock_repo = setup_analysis_repo_mock(service=service)

        await service._run_analysis(
            analysis_id=1,
            encrypted_access_token="enc-access",
            encrypted_refresh_token="enc-refresh",
            unread_only=True,
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
        service = build_service()
        setup_analysis_repo_mock(service=service)

        await service._run_analysis(
            analysis_id=1,
            encrypted_access_token="enc-access",
            encrypted_refresh_token="enc-refresh",
            unread_only=True,
            max_emails=100,
            auto_apply=False,
        )

        call_kwargs = service._classification_service.classify_emails.call_args.kwargs
        assert "existing_categories" in call_kwargs
        assert "primary" in call_kwargs["existing_categories"]
        assert "promotions" in call_kwargs["existing_categories"]

    @pytest.mark.asyncio
    async def test_custom_categories_passed_through(self) -> None:
        service = build_service()
        setup_analysis_repo_mock(service=service)

        await service._run_analysis(
            analysis_id=1,
            encrypted_access_token="enc-access",
            encrypted_refresh_token="enc-refresh",
            unread_only=True,
            max_emails=100,
            auto_apply=False,
            custom_categories=["receipts", "travel"],
        )

        call_kwargs = service._classification_service.classify_emails.call_args.kwargs
        assert "receipts" in call_kwargs["existing_categories"]
        assert "travel" in call_kwargs["existing_categories"]

    @pytest.mark.asyncio
    async def test_new_categories_accumulate_across_batches(self) -> None:
        emails = [make_email_metadata(msg_id=f"msg-{i}") for i in range(25)]
        results_batch1 = [
            make_classification_result(msg_id=f"msg-{i}", category="receipts")
            for i in range(20)
        ]
        results_batch2 = [
            make_classification_result(msg_id=f"msg-{i}") for i in range(20, 25)
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
            return_value=default_verification()
        )

        created_batch1 = [
            make_classified_email(email_id=i + 1, msg_id=f"msg-{i}", category="receipts")
            for i in range(20)
        ]
        created_batch2 = [
            make_classified_email(email_id=i + 21, msg_id=f"msg-{i}")
            for i in range(20, 25)
        ]

        classified_email_repo = MagicMock()
        classified_email_repo.bulk_create = AsyncMock(
            side_effect=[created_batch1, created_batch2]
        )
        classified_email_repo.bulk_update_action_taken = AsyncMock()
        classified_email_repo.bulk_record_action = AsyncMock()
        classified_email_repo.pop_last_action = AsyncMock(return_value={})
        classified_email_repo.bulk_update_category = AsyncMock()

        service = build_service(
            email_service=email_service,
            classification_service=classification_service,
            classified_email_repo=classified_email_repo,
        )
        setup_analysis_repo_mock(service=service)

        await service._run_analysis(
            analysis_id=1,
            encrypted_access_token="enc-access",
            encrypted_refresh_token="enc-refresh",
            unread_only=True,
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
        service = build_service(email_service=email_service)
        setup_analysis_repo_mock(service=service)
        mock_repo = service._create_analysis_repo()

        await service._run_analysis(
            analysis_id=1,
            encrypted_access_token="enc-access",
            encrypted_refresh_token="enc-refresh",
            unread_only=True,
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
        service = build_service(
            email_service=email_service, security_service=security_service
        )
        setup_analysis_repo_mock(service=service)
        mock_repo = service._create_analysis_repo()

        await service._run_analysis(
            analysis_id=1,
            encrypted_access_token="enc-access",
            encrypted_refresh_token="enc-refresh",
            unread_only=True,
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
            return_value=[make_email_metadata()]
        )
        email_service.modify_messages = AsyncMock()

        classification_service = MagicMock()
        classification_service.classify_emails = AsyncMock(
            return_value=[make_classification_result()]
        )
        classification_service.verify_categories = AsyncMock(
            return_value=VerificationResult(
                merges=[],
                category_actions={"promotions": ["mark_read"]},
            )
        )

        classified_email_repo = MagicMock()
        classified_email_repo.bulk_create = AsyncMock(
            return_value=[make_classified_email()]
        )
        classified_email_repo.bulk_update_action_taken = AsyncMock()
        classified_email_repo.bulk_record_action = AsyncMock()
        classified_email_repo.pop_last_action = AsyncMock(return_value={})
        classified_email_repo.bulk_update_category = AsyncMock()

        service = build_service(
            email_service=email_service,
            classification_service=classification_service,
            classified_email_repo=classified_email_repo,
        )
        setup_analysis_repo_mock(service=service)

        await service._run_analysis(
            analysis_id=1,
            encrypted_access_token="enc-access",
            encrypted_refresh_token="enc-refresh",
            unread_only=True,
            max_emails=100,
            auto_apply=True,
        )

        email_service.modify_messages.assert_awaited()
        classified_email_repo.bulk_update_action_taken.assert_awaited()

    @pytest.mark.asyncio
    async def test_category_actions_stored_on_analysis(self) -> None:
        expected_actions = {"promotions": ["mark_read", "move_to_category"]}
        classification_service = MagicMock()
        classification_service.classify_emails = AsyncMock(
            return_value=[make_classification_result()]
        )
        classification_service.verify_categories = AsyncMock(
            return_value=VerificationResult(
                merges=[], category_actions=expected_actions
            )
        )

        classified_email_repo = MagicMock()
        classified_email_repo.bulk_create = AsyncMock(
            return_value=[make_classified_email()]
        )
        classified_email_repo.bulk_update_action_taken = AsyncMock()
        classified_email_repo.bulk_record_action = AsyncMock()
        classified_email_repo.pop_last_action = AsyncMock(return_value={})
        classified_email_repo.bulk_update_category = AsyncMock()

        service = build_service(
            classification_service=classification_service,
            classified_email_repo=classified_email_repo,
        )
        mock_repo = setup_analysis_repo_mock(service=service)

        await service._run_analysis(
            analysis_id=1,
            encrypted_access_token="enc-access",
            encrypted_refresh_token="enc-refresh",
            unread_only=True,
            max_emails=100,
            auto_apply=False,
        )

        mock_repo.update_category_actions.assert_awaited_once_with(
            analysis_id=1, category_actions=expected_actions
        )

    @pytest.mark.asyncio
    async def test_batch_classification(self) -> None:
        emails = [
            make_email_metadata(msg_id=f"msg-{i}") for i in range(25)
        ]
        results_batch1 = [
            make_classification_result(msg_id=f"msg-{i}") for i in range(20)
        ]
        results_batch2 = [
            make_classification_result(msg_id=f"msg-{i}") for i in range(20, 25)
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
            return_value=default_verification()
        )

        created_batch1 = [
            make_classified_email(email_id=i + 1, msg_id=f"msg-{i}")
            for i in range(20)
        ]
        created_batch2 = [
            make_classified_email(email_id=i + 21, msg_id=f"msg-{i}")
            for i in range(20, 25)
        ]

        classified_email_repo = MagicMock()
        classified_email_repo.bulk_create = AsyncMock(
            side_effect=[created_batch1, created_batch2]
        )
        classified_email_repo.update_action_taken = AsyncMock()
        classified_email_repo.bulk_update_action_taken = AsyncMock()
        classified_email_repo.bulk_record_action = AsyncMock()
        classified_email_repo.pop_last_action = AsyncMock(return_value={})
        classified_email_repo.bulk_update_category = AsyncMock()

        service = build_service(
            email_service=email_service,
            classification_service=classification_service,
            classified_email_repo=classified_email_repo,
        )
        setup_analysis_repo_mock(service=service)

        await service._run_analysis(
            analysis_id=1,
            encrypted_access_token="enc-access",
            encrypted_refresh_token="enc-refresh",
            unread_only=True,
            max_emails=100,
            auto_apply=False,
        )

        assert classification_service.classify_emails.await_count == 2
        assert classified_email_repo.bulk_create.await_count == 2
