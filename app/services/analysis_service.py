import asyncio
import logging
from collections import defaultdict
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.protocols import (
    BaseAnalysisRepository,
    BaseClassificationService,
    BaseClassifiedEmailRepository,
    BaseEmailService,
    BaseSecurityService,
)
from app.models.db import ClassifiedEmail
from app.repositories.analysis_repository import SQLAlchemyAnalysisRepository
from app.services.classification_service import BASE_CATEGORIES

logger = logging.getLogger(__name__)

BATCH_SIZE = 20

CATEGORY_TO_LABEL: dict[str, str] = {
    "promotions": "CATEGORY_PROMOTIONS",
    "social": "CATEGORY_SOCIAL",
    "updates": "CATEGORY_UPDATES",
    "primary": "CATEGORY_PERSONAL",
}


class AnalysisService:
    def __init__(
        self,
        *,
        email_service: BaseEmailService,
        classification_service: BaseClassificationService,
        security_service: BaseSecurityService,
        classified_email_repo: BaseClassifiedEmailRepository,
        async_session_maker: async_sessionmaker[AsyncSession],
    ) -> None:
        self._email_service = email_service
        self._classification_service = classification_service
        self._security_service = security_service
        self._classified_email_repo = classified_email_repo
        self._async_session_maker = async_session_maker

    def start_analysis(
        self,
        *,
        analysis_id: int,
        encrypted_access_token: str,
        encrypted_refresh_token: str,
        query: str,
        max_emails: int,
        auto_apply: bool,
        custom_categories: list[str] | None = None,
    ) -> asyncio.Task:
        return asyncio.create_task(
            self._run_analysis(
                analysis_id=analysis_id,
                encrypted_access_token=encrypted_access_token,
                encrypted_refresh_token=encrypted_refresh_token,
                query=query,
                max_emails=max_emails,
                auto_apply=auto_apply,
                custom_categories=custom_categories,
            )
        )

    def _create_analysis_repo(self) -> BaseAnalysisRepository:
        return SQLAlchemyAnalysisRepository(
            session_maker=self._async_session_maker
        )

    async def _run_analysis(
        self,
        *,
        analysis_id: int,
        encrypted_access_token: str,
        encrypted_refresh_token: str,
        query: str,
        max_emails: int,
        auto_apply: bool,
        custom_categories: list[str] | None = None,
    ) -> None:
        analysis_repo = self._create_analysis_repo()
        try:
            await analysis_repo.update_status(
                analysis_id=analysis_id, status="processing"
            )

            access_token = self._security_service.decrypt_token(
                encrypted_token=encrypted_access_token
            )
            refresh_token = self._security_service.decrypt_token(
                encrypted_token=encrypted_refresh_token
            )
            credentials = self._email_service.build_credentials(
                access_token=access_token, refresh_token=refresh_token
            )

            message_ids = await self._email_service.list_messages(
                credentials=credentials, query=query, max_results=max_emails
            )

            if not message_ids:
                await analysis_repo.update_status(
                    analysis_id=analysis_id,
                    status="completed",
                    total_emails=0,
                    processed_emails=0,
                    completed_at=datetime.now(UTC),
                )
                return

            emails = await self._email_service.get_messages_batch(
                credentials=credentials, message_ids=message_ids
            )

            await analysis_repo.update_status(
                analysis_id=analysis_id,
                status="processing",
                total_emails=len(emails),
                processed_emails=0,
            )

            # Pass 1: Classification with dynamic categories
            existing_categories = list(BASE_CATEGORIES)
            if custom_categories:
                for cat in custom_categories:
                    if cat not in existing_categories:
                        existing_categories.append(cat)

            all_classified: list[ClassifiedEmail] = []

            for i in range(0, len(emails), BATCH_SIZE):
                batch = emails[i : i + BATCH_SIZE]
                results = await self._classification_service.classify_emails(
                    emails=batch, existing_categories=existing_categories
                )

                email_map = {e.gmail_message_id: e for e in batch}
                classified_records = []
                for result in results:
                    email = email_map.get(result.gmail_message_id)
                    if not email:
                        continue

                    if result.category not in existing_categories:
                        existing_categories.append(result.category)

                    classified_records.append(
                        ClassifiedEmail(
                            analysis_id=analysis_id,
                            gmail_message_id=result.gmail_message_id,
                            gmail_thread_id=email.gmail_thread_id,
                            sender=email.sender,
                            sender_domain=email.sender_domain,
                            subject=email.subject,
                            snippet=email.snippet,
                            received_at=email.received_at,
                            category=result.category,
                            importance=result.importance,
                            sender_type=result.sender_type,
                            confidence=result.confidence,
                            has_unsubscribe=email.has_unsubscribe,
                        )
                    )

                if classified_records:
                    created = await self._classified_email_repo.bulk_create(
                        emails=classified_records
                    )
                    all_classified.extend(created)

                await analysis_repo.update_status(
                    analysis_id=analysis_id,
                    status="processing",
                    processed_emails=min(i + BATCH_SIZE, len(emails)),
                )

            # Pass 2: Verification
            category_samples = self._build_category_samples(
                classified_emails=all_classified
            )
            verification = await self._classification_service.verify_categories(
                category_samples=category_samples
            )

            for merge in verification.merges:
                await self._classified_email_repo.bulk_update_category(
                    analysis_id=analysis_id,
                    from_category=merge.from_category,
                    to_category=merge.to_category,
                )
                for email in all_classified:
                    if email.category == merge.from_category:
                        email.category = merge.to_category

            await analysis_repo.update_category_actions(
                analysis_id=analysis_id,
                category_actions=verification.category_actions,
            )

            if auto_apply and all_classified:
                await self._auto_apply_actions(
                    classified_emails=all_classified,
                    category_actions=verification.category_actions,
                    encrypted_access_token=encrypted_access_token,
                    encrypted_refresh_token=encrypted_refresh_token,
                )

            await analysis_repo.update_status(
                analysis_id=analysis_id,
                status="completed",
                processed_emails=len(emails),
                completed_at=datetime.now(UTC),
            )

        except Exception as exc:
            logger.exception("Analysis %d failed", analysis_id)
            await analysis_repo.update_status(
                analysis_id=analysis_id,
                status="failed",
                error_message=str(exc),
                completed_at=datetime.now(UTC),
            )

    @staticmethod
    def _build_category_samples(
        *, classified_emails: list[ClassifiedEmail]
    ) -> dict[str, list[dict]]:
        by_category: dict[str, list[dict]] = defaultdict(list)
        for email in classified_emails:
            cat = email.category or "primary"
            if len(by_category[cat]) < 5:
                by_category[cat].append({
                    "subject": email.subject,
                    "sender": email.sender,
                    "sender_domain": email.sender_domain,
                })
        return dict(by_category)

    async def apply_actions_for_analysis(
        self,
        *,
        classified_emails: list[ClassifiedEmail],
        action: str,
        encrypted_access_token: str,
        encrypted_refresh_token: str,
    ) -> None:
        emails_to_apply = [e for e in classified_emails if not e.action_taken]
        if not emails_to_apply:
            return
        await self._apply_actions(
            classified_emails=emails_to_apply,
            action=action,
            encrypted_access_token=encrypted_access_token,
            encrypted_refresh_token=encrypted_refresh_token,
        )

    async def _apply_actions(
        self,
        *,
        classified_emails: list[ClassifiedEmail],
        action: str,
        encrypted_access_token: str,
        encrypted_refresh_token: str,
    ) -> None:
        access_token = self._security_service.decrypt_token(
            encrypted_token=encrypted_access_token
        )
        refresh_token = self._security_service.decrypt_token(
            encrypted_token=encrypted_refresh_token
        )
        credentials = self._email_service.build_credentials(
            access_token=access_token, refresh_token=refresh_token
        )

        msg_ids = [e.gmail_message_id for e in classified_emails]
        email_ids = [e.id for e in classified_emails]

        if action == "keep":
            return

        if action == "move_to_category":
            by_category: dict[str, list[str]] = defaultdict(list)
            by_category_ids: dict[str, list[int]] = defaultdict(list)
            for e in classified_emails:
                cat = e.category or "primary"
                by_category[cat].append(e.gmail_message_id)
                by_category_ids[cat].append(e.id)

            for cat, cat_msg_ids in by_category.items():
                label = CATEGORY_TO_LABEL.get(cat)
                if label:
                    await self._email_service.modify_messages(
                        credentials=credentials,
                        message_ids=cat_msg_ids,
                        add_labels=[label],
                        remove_labels=["INBOX"],
                    )
            await self._classified_email_repo.bulk_update_action_taken(
                email_ids=email_ids, action_taken="move_to_category"
            )

        elif action == "mark_read":
            await self._email_service.modify_messages(
                credentials=credentials,
                message_ids=msg_ids,
                remove_labels=["UNREAD"],
            )
            await self._classified_email_repo.bulk_update_action_taken(
                email_ids=email_ids, action_taken="mark_read"
            )

        elif action in ("mark_spam", "unsubscribe"):
            await self._email_service.modify_messages(
                credentials=credentials,
                message_ids=msg_ids,
                add_labels=["SPAM"],
                remove_labels=["INBOX"],
            )
            await self._classified_email_repo.bulk_update_action_taken(
                email_ids=email_ids, action_taken=action
            )

    async def _auto_apply_actions(
        self,
        *,
        classified_emails: list[ClassifiedEmail],
        category_actions: dict[str, list[str]],
        encrypted_access_token: str,
        encrypted_refresh_token: str,
    ) -> None:
        by_category: dict[str, list[ClassifiedEmail]] = defaultdict(list)
        for email in classified_emails:
            cat = email.category or "primary"
            by_category[cat].append(email)

        for cat, emails_in_cat in by_category.items():
            actions = category_actions.get(cat, [])
            if not actions:
                continue
            action = actions[0]
            if action == "keep":
                continue
            await self._apply_actions(
                classified_emails=emails_in_cat,
                action=action,
                encrypted_access_token=encrypted_access_token,
                encrypted_refresh_token=encrypted_refresh_token,
            )
