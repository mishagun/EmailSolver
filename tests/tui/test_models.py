from datetime import UTC, datetime

from tui.models import (
    ActionType,
    AnalysisCreateRequest,
    AnalysisListResponse,
    AnalysisResponse,
    ApplyActionsRequest,
    AuthCallbackResponse,
    AuthStatusResponse,
    CategorySummary,
    ClassifiedEmailResponse,
    EmailListResponse,
    EmailMetadata,
    EmailStatsResponse,
    MessageResponse,
)


class TestAuthModels:
    def test_auth_callback_response(self) -> None:
        resp = AuthCallbackResponse(access_token="jwt-token-123")
        assert resp.access_token == "jwt-token-123"
        assert resp.token_type == "bearer"

    def test_auth_status_response_authenticated(self) -> None:
        resp = AuthStatusResponse(
            authenticated=True, email="user@gmail.com", display_name="User"
        )
        assert resp.authenticated is True
        assert resp.email == "user@gmail.com"

    def test_auth_status_response_unauthenticated(self) -> None:
        resp = AuthStatusResponse(authenticated=False)
        assert resp.email is None
        assert resp.display_name is None

    def test_message_response(self) -> None:
        resp = MessageResponse(message="ok")
        assert resp.message == "ok"


class TestEmailModels:
    def test_email_metadata_minimal(self) -> None:
        email = EmailMetadata(gmail_message_id="msg-1")
        assert email.gmail_message_id == "msg-1"
        assert email.sender is None
        assert email.has_unsubscribe is False

    def test_email_metadata_full(self) -> None:
        email = EmailMetadata(
            gmail_message_id="msg-1",
            gmail_thread_id="thread-1",
            sender="test@example.com",
            sender_domain="example.com",
            subject="Hello",
            snippet="World",
            received_at=datetime(2026, 3, 1, tzinfo=UTC),
            has_unsubscribe=True,
        )
        assert email.sender_domain == "example.com"
        assert email.has_unsubscribe is True

    def test_email_list_response(self) -> None:
        resp = EmailListResponse(
            emails=[EmailMetadata(gmail_message_id="msg-1")],
            total=1,
            unread_only=True,
        )
        assert resp.total == 1
        assert len(resp.emails) == 1

    def test_email_stats_response(self) -> None:
        resp = EmailStatsResponse(unread_count=42, total_count=1500)
        assert resp.unread_count == 42


class TestAnalysisModels:
    def test_analysis_create_request_defaults(self) -> None:
        req = AnalysisCreateRequest()
        assert req.unread_only is True
        assert req.max_emails == 500
        assert req.auto_apply is False
        assert req.custom_categories is None

    def test_analysis_create_request_custom(self) -> None:
        req = AnalysisCreateRequest(
            unread_only=False,
            max_emails=50,
            auto_apply=True,
            custom_categories=["receipts", "travel"],
        )
        assert req.custom_categories == ["receipts", "travel"]

    def test_analysis_response_pending(self) -> None:
        resp = AnalysisResponse(
            id=1,
            status="pending",
            unread_only=True,
            created_at=datetime(2026, 3, 1, tzinfo=UTC),
        )
        assert resp.status == "pending"
        assert resp.summary is None
        assert resp.classified_emails is None

    def test_analysis_response_completed_with_summary(self) -> None:
        resp = AnalysisResponse(
            id=1,
            status="completed",
            unread_only=True,
            total_emails=50,
            processed_emails=50,
            created_at=datetime(2026, 3, 1, tzinfo=UTC),
            completed_at=datetime(2026, 3, 1, 0, 1, 30, tzinfo=UTC),
            summary=[
                CategorySummary(
                    category="promotions",
                    count=30,
                    recommended_actions=["mark_read", "move_to_category"],
                ),
            ],
            classified_emails=[
                ClassifiedEmailResponse(
                    id=1,
                    gmail_message_id="msg-1",
                    sender="shop@store.com",
                    category="promotions",
                    importance=2,
                    sender_type="marketing",
                    confidence=0.95,
                ),
            ],
        )
        assert resp.summary is not None
        assert len(resp.summary) == 1
        assert resp.summary[0].category == "promotions"
        assert resp.classified_emails is not None
        assert resp.classified_emails[0].confidence == 0.95

    def test_analysis_list_response(self) -> None:
        resp = AnalysisListResponse(
            analyses=[
                AnalysisResponse(
                    id=1,
                    status="completed",
                    created_at=datetime(2026, 3, 1, tzinfo=UTC),
                )
            ],
            total=1,
        )
        assert resp.total == 1


class TestActionModels:
    def test_action_type_values(self) -> None:
        assert ActionType.KEEP == "keep"
        assert ActionType.MOVE_TO_CATEGORY == "move_to_category"
        assert ActionType.MARK_READ == "mark_read"
        assert ActionType.MARK_SPAM == "mark_spam"
        assert ActionType.UNSUBSCRIBE == "unsubscribe"

    def test_apply_actions_request_minimal(self) -> None:
        req = ApplyActionsRequest(action=ActionType.MARK_READ)
        assert req.category is None
        assert req.email_ids is None

    def test_apply_actions_request_with_category(self) -> None:
        req = ApplyActionsRequest(action=ActionType.MARK_READ, category="promotions")
        assert req.category == "promotions"

    def test_apply_actions_request_with_email_ids(self) -> None:
        req = ApplyActionsRequest(
            action=ActionType.MARK_SPAM, email_ids=[1, 5, 12]
        )
        assert req.email_ids == [1, 5, 12]

    def test_apply_actions_request_serialization(self) -> None:
        req = ApplyActionsRequest(
            action=ActionType.MOVE_TO_CATEGORY, category="newsletters"
        )
        data = req.model_dump(exclude_none=True)
        assert data == {"action": "move_to_category", "category": "newsletters"}
        assert "email_ids" not in data
        assert "sender_domain" not in data
