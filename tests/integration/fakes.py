from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from app.core.protocols import BaseAuthService, BaseClassificationService, BaseEmailService
from app.models.schemas import (
    ClassificationResult,
    EmailMetadata,
    VerificationResult,
)

DEFAULT_FAKE_EMAILS = [
    EmailMetadata(
        gmail_message_id="msg-0",
        gmail_thread_id="thread-0",
        sender="news@newsletter.com",
        sender_domain="newsletter.com",
        subject="Weekly Newsletter #42",
        snippet="Here are this week's top stories...",
        has_unsubscribe=True,
    ),
    EmailMetadata(
        gmail_message_id="msg-1",
        gmail_thread_id="thread-1",
        sender="deals@promo.com",
        sender_domain="promo.com",
        subject="50% off everything!",
        snippet="Don't miss our biggest sale...",
        has_unsubscribe=True,
    ),
    EmailMetadata(
        gmail_message_id="msg-2",
        gmail_thread_id="thread-2",
        sender="friend@social.com",
        sender_domain="social.com",
        subject="You have a new follower",
        snippet="John started following you...",
    ),
    EmailMetadata(
        gmail_message_id="msg-3",
        gmail_thread_id="thread-3",
        sender="noreply@updates.com",
        sender_domain="updates.com",
        subject="Your order has shipped",
        snippet="Track your package...",
    ),
    EmailMetadata(
        gmail_message_id="msg-4",
        gmail_thread_id="thread-4",
        sender="boss@company.com",
        sender_domain="company.com",
        subject="Meeting tomorrow",
        snippet="Let's discuss the project...",
    ),
    EmailMetadata(
        gmail_message_id="msg-5",
        gmail_thread_id="thread-5",
        sender="sales@otherpromo.com",
        sender_domain="otherpromo.com",
        subject="Flash sale today!",
        snippet="Limited time offer on all items...",
        has_unsubscribe=True,
    ),
]

DOMAIN_CATEGORY_MAP: dict[str, str] = {
    "newsletter.com": "newsletters",
    "promo.com": "promotions",
    "social.com": "social",
    "updates.com": "updates",
    "otherpromo.com": "promotions",
}


@dataclass
class FakeCredentials:
    token: str
    refresh_token: str
    expiry: datetime


class FakeEmailService(BaseEmailService):
    def __init__(self, *, emails: list[EmailMetadata] | None = None) -> None:
        self.emails = emails or list(DEFAULT_FAKE_EMAILS)
        self.modify_calls: list[dict[str, Any]] = []
        self.trash_calls: list[list[str]] = []
        self.labels_created: dict[str, str] = {}

    def build_credentials(self, *, access_token: str, refresh_token: str) -> Any:
        return {"access_token": access_token, "refresh_token": refresh_token}

    async def list_messages(
        self,
        *,
        credentials: Any,
        query: str = "is:unread",
        max_results: int = 500,
    ) -> list[str]:
        return [e.gmail_message_id for e in self.emails[:max_results]]

    async def get_messages_batch(
        self, *, credentials: Any, message_ids: list[str]
    ) -> list[EmailMetadata]:
        id_set = set(message_ids)
        return [e for e in self.emails if e.gmail_message_id in id_set]

    async def modify_messages(
        self,
        *,
        credentials: Any,
        message_ids: list[str],
        add_labels: list[str] | None = None,
        remove_labels: list[str] | None = None,
    ) -> None:
        self.modify_calls.append({
            "message_ids": message_ids,
            "add_labels": add_labels,
            "remove_labels": remove_labels,
        })

    async def get_or_create_label(
        self, *, credentials: Any, label_name: str
    ) -> str:
        label_id = f"Label_{label_name}"
        self.labels_created[label_name] = label_id
        return label_id

    async def trash_messages(
        self, *, credentials: Any, message_ids: list[str]
    ) -> None:
        self.trash_calls.append(message_ids)


class FakeClassificationService(BaseClassificationService):
    def __init__(self, *, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.classify_call_count = 0

    async def classify_emails(
        self,
        *,
        emails: list[EmailMetadata],
        existing_categories: list[str] | None = None,
    ) -> list[ClassificationResult]:
        if self.should_fail:
            raise RuntimeError("Classification API unavailable")

        self.classify_call_count += 1
        return [
            ClassificationResult(
                gmail_message_id=email.gmail_message_id,
                category=DOMAIN_CATEGORY_MAP.get(email.sender_domain or "", "primary"),
                importance=3,
                sender_type="automated" if email.has_unsubscribe else "human",
                confidence=0.95,
            )
            for email in emails
        ]

    async def verify_categories(
        self,
        category_samples: dict[str, list[dict]],
    ) -> VerificationResult:
        if self.should_fail:
            raise RuntimeError("Verification API unavailable")

        return VerificationResult(
            merges=[],
            category_actions={
                cat: ["move_to_category", "mark_read"]
                for cat in category_samples
            },
        )

    async def generate_insights(
        self,
        category_samples: dict[str, list[dict]],
    ) -> list[str]:
        return [
            "5 out of 6 emails here are automated noise",
            "only 1 email was written by an actual person",
            "promotions outnumber real mail 2 to 1",
        ]

    async def submit_batch_classification(
        self,
        *,
        email_batches: list[list[EmailMetadata]],
        existing_categories: list[str] | None = None,
    ) -> str:
        return "fake-batch-id"

    async def check_batch_status(self, *, batch_id: str) -> str:
        return "ended"

    async def retrieve_batch_results(
        self, *, batch_id: str
    ) -> dict[str, list[ClassificationResult]]:
        return {}


class FakeClassificationServiceWithMerge(BaseClassificationService):
    async def classify_emails(
        self,
        *,
        emails: list[EmailMetadata],
        existing_categories: list[str] | None = None,
    ) -> list[ClassificationResult]:
        results = []
        for email in emails:
            domain = email.sender_domain or ""
            if domain == "newsletter.com":
                category = "news_letters"
            else:
                category = DOMAIN_CATEGORY_MAP.get(domain, "primary")
            results.append(
                ClassificationResult(
                    gmail_message_id=email.gmail_message_id,
                    category=category,
                    importance=3,
                    sender_type="automated",
                    confidence=0.9,
                )
            )
        return results

    async def verify_categories(
        self,
        category_samples: dict[str, list[dict]],
    ) -> VerificationResult:
        return VerificationResult(
            merges=[],
            category_actions={
                cat: ["move_to_category"] for cat in category_samples
            },
        )

    async def generate_insights(
        self,
        category_samples: dict[str, list[dict]],
    ) -> list[str]:
        return ["most of this inbox is automated junk"]

    async def submit_batch_classification(
        self,
        *,
        email_batches: list[list[EmailMetadata]],
        existing_categories: list[str] | None = None,
    ) -> str:
        return "fake-batch-id"

    async def check_batch_status(self, *, batch_id: str) -> str:
        return "ended"

    async def retrieve_batch_results(
        self, *, batch_id: str
    ) -> dict[str, list[ClassificationResult]]:
        return {}


class FakeAuthService(BaseAuthService):
    def start_authorization(self) -> str:
        return "http://fake-auth.example.com/login?state=test-state"

    def exchange_code(self, *, code: str, state: str) -> Any:
        return FakeCredentials(
            token="fake-access-token-from-exchange",
            refresh_token="fake-refresh-token-from-exchange",
            expiry=datetime.now(UTC) + timedelta(hours=1),
        )

    def get_user_info(self, *, credentials: Any) -> dict:
        return {
            "id": "google-integration-test-123",
            "email": "integration@test.com",
            "name": "Integration Test User",
        }

    async def revoke_token(self, *, token: str) -> None:
        pass
