from unittest.mock import AsyncMock, patch

import pytest

from app.services.analysis_service import AnalysisService
from tests.analysis_helpers import build_service, make_classified_email


class TestApplyActions:
    @pytest.mark.asyncio
    async def test_apply_move_to_category(self) -> None:
        service = build_service()
        promo_email = make_classified_email(
            email_id=1, msg_id="msg-1", category="promotions"
        )

        await service._apply_actions(
            classified_emails=[promo_email],
            action="move_to_category",
            encrypted_access_token="enc-access",
            encrypted_refresh_token="enc-refresh",
        )

        service._email_service.get_or_create_label.assert_awaited_once_with(
            credentials=service._email_service.build_credentials.return_value,
            label_name="promotions",
        )
        service._email_service.modify_messages.assert_awaited_once_with(
            credentials=service._email_service.build_credentials.return_value,
            message_ids=["msg-1"],
            add_labels=["label-id"],
        )
        service._classified_email_repo.bulk_update_action_taken.assert_awaited_once_with(
            email_ids=[1], action_taken="move_to_category"
        )

    @pytest.mark.asyncio
    async def test_apply_actions_reapplies_even_if_already_applied(self) -> None:
        service = build_service()
        already_applied = make_classified_email(
            email_id=1, msg_id="msg-1", category="spam", action_taken="mark_spam"
        )

        await service.apply_actions_for_analysis(
            classified_emails=[already_applied],
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

    @pytest.mark.asyncio
    async def test_apply_actions_keep_is_noop(self) -> None:
        service = build_service()
        primary_email = make_classified_email(
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
        service = build_service()
        spam_email = make_classified_email(
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
        service = build_service()
        email = make_classified_email(
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
    async def test_apply_actions_unsubscribe_falls_back_to_spam(self) -> None:
        service = build_service()
        newsletter_email = make_classified_email(
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

    @pytest.mark.asyncio
    async def test_unsubscribe_http_success_archives_without_spam(self) -> None:
        service = build_service()
        newsletter_email = make_classified_email(
            email_id=1,
            msg_id="msg-1",
            category="newsletters",
            has_unsubscribe=True,
            unsubscribe_header="<https://example.com/unsub>",
            unsubscribe_post_header="List-Unsubscribe=One-Click-Unsubscribe",
        )

        with patch(
            "app.services.unsubscribe_service.attempt_http_unsubscribe",
            new_callable=AsyncMock,
            return_value=True,
        ):
            await service._apply_actions(
                classified_emails=[newsletter_email],
                action="unsubscribe",
                encrypted_access_token="enc-access",
                encrypted_refresh_token="enc-refresh",
            )

        service._email_service.modify_messages.assert_awaited_once_with(
            credentials=service._email_service.build_credentials.return_value,
            message_ids=["msg-1"],
            remove_labels=["INBOX"],
        )
        service._classified_email_repo.bulk_update_action_taken.assert_awaited_once_with(
            email_ids=[1], action_taken="unsubscribe"
        )

    @pytest.mark.asyncio
    async def test_unsubscribe_http_failure_falls_back_to_spam(self) -> None:
        service = build_service()
        newsletter_email = make_classified_email(
            email_id=1,
            msg_id="msg-1",
            category="newsletters",
            has_unsubscribe=True,
            unsubscribe_header="<https://example.com/unsub>",
            unsubscribe_post_header="List-Unsubscribe=One-Click-Unsubscribe",
        )

        with patch(
            "app.services.unsubscribe_service.attempt_http_unsubscribe",
            new_callable=AsyncMock,
            return_value=False,
        ):
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
            make_classified_email(email_id=1, category="promotions"),
            make_classified_email(email_id=2, category="spam"),
        ]

        result = AnalysisService._build_category_samples(classified_emails=emails)

        assert "promotions" in result
        assert "spam" in result
        assert len(result["promotions"]) == 1
        assert len(result["spam"]) == 1

    def test_limits_to_5_samples_per_category(self) -> None:
        emails = [
            make_classified_email(email_id=i, category="promotions")
            for i in range(10)
        ]

        result = AnalysisService._build_category_samples(classified_emails=emails)

        assert len(result["promotions"]) == 5
