from unittest.mock import AsyncMock, MagicMock

from app.models.db import ClassifiedEmail
from app.models.schemas import (
    ClassificationResult,
    EmailMetadata,
    VerificationResult,
)
from app.services.analysis_service import AnalysisService


def make_email_metadata(*, msg_id: str = "msg-1") -> EmailMetadata:
    return EmailMetadata(
        gmail_message_id=msg_id,
        gmail_thread_id="thread-1",
        sender="sender@example.com",
        sender_domain="example.com",
        subject="Test Email",
        snippet="Hello world",
        has_unsubscribe=False,
    )


def make_classification_result(
    *, msg_id: str = "msg-1", category: str = "promotions"
) -> ClassificationResult:
    return ClassificationResult(
        gmail_message_id=msg_id,
        category=category,
        importance=2,
        sender_type="marketing",
        confidence=0.9,
    )


def make_classified_email(
    *,
    email_id: int = 1,
    msg_id: str = "msg-1",
    category: str = "promotions",
    action_taken: str | None = None,
    has_unsubscribe: bool = False,
    unsubscribe_header: str | None = None,
    unsubscribe_post_header: str | None = None,
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
        unsubscribe_header=unsubscribe_header,
        unsubscribe_post_header=unsubscribe_post_header,
        action_taken=action_taken,
    )
    email.id = email_id
    return email


def default_verification() -> VerificationResult:
    return VerificationResult(
        merges=[],
        category_actions={"promotions": ["move_to_category", "mark_read"]},
    )


def build_service(
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
            return_value=[make_email_metadata()]
        )
        email_service.modify_messages = AsyncMock()
        email_service.get_or_create_label = AsyncMock(return_value="label-id")

    if classification_service is None:
        classification_service = MagicMock()
        classification_service.classify_emails = AsyncMock(
            return_value=[make_classification_result()]
        )
        classification_service.verify_categories = AsyncMock(
            return_value=default_verification()
        )

    if security_service is None:
        security_service = MagicMock()
        security_service.decrypt_token = MagicMock(return_value="decrypted-token")

    if classified_email_repo is None:
        classified_email_repo = MagicMock()
        classified_email_repo.bulk_create = AsyncMock(
            return_value=[make_classified_email()]
        )
        classified_email_repo.update_action_taken = AsyncMock()
        classified_email_repo.bulk_update_action_taken = AsyncMock()
        classified_email_repo.bulk_record_action = AsyncMock()
        classified_email_repo.pop_last_action = AsyncMock(return_value={})
        classified_email_repo.bulk_update_category = AsyncMock()

    session_maker = MagicMock()

    return AnalysisService(
        email_service=email_service,
        classification_service=classification_service,
        security_service=security_service,
        classified_email_repo=classified_email_repo,
        async_session_maker=session_maker,
    )


def setup_analysis_repo_mock(*, service: AnalysisService) -> AsyncMock:
    mock_repo = AsyncMock()
    service._create_analysis_repo = MagicMock(return_value=mock_repo)
    return mock_repo
