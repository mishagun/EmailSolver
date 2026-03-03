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
CLASSIFICATION_CONCURRENCY = 3



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
            processed_count = 0
            semaphore = asyncio.Semaphore(CLASSIFICATION_CONCURRENCY)

            async def _classify_batch(batch_emails: list) -> list[ClassifiedEmail]:
                async with semaphore:
                    results = await self._classification_service.classify_emails(
                        emails=batch_emails, existing_categories=list(existing_categories)
                    )

                email_map = {e.gmail_message_id: e for e in batch_emails}
                records = []
                for result in results:
                    email = email_map.get(result.gmail_message_id)
                    if not email:
                        continue

                    if result.category not in existing_categories:
                        existing_categories.append(result.category)

                    records.append(
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
                return records

            batches = [
                emails[i : i + BATCH_SIZE]
                for i in range(0, len(emails), BATCH_SIZE)
            ]
            total_batches = len(batches)
            logger.info(
                "Analysis %d: classifying %d emails in %d batches (concurrency=%d)",
                analysis_id, len(emails), total_batches, CLASSIFICATION_CONCURRENCY,
            )

            for chunk_start in range(0, total_batches, CLASSIFICATION_CONCURRENCY):
                chunk = batches[chunk_start : chunk_start + CLASSIFICATION_CONCURRENCY]
                chunk_results = await asyncio.gather(
                    *[_classify_batch(batch_emails=b) for b in chunk]
                )

                for records in chunk_results:
                    if records:
                        created = await self._classified_email_repo.bulk_create(
                            emails=records
                        )
                        all_classified.extend(created)
                    processed_count += BATCH_SIZE

                await analysis_repo.update_status(
                    analysis_id=analysis_id,
                    status="processing",
                    processed_emails=min(processed_count, len(emails)),
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
        if not classified_emails:
            return
        await self._apply_actions(
            classified_emails=classified_emails,
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
            for e in classified_emails:
                cat = e.category or "primary"
                by_category[cat].append(e.gmail_message_id)

            for cat, cat_msg_ids in by_category.items():
                label_id = await self._email_service.get_or_create_label(
                    credentials=credentials, label_name=cat,
                )
                await self._email_service.modify_messages(
                    credentials=credentials,
                    message_ids=cat_msg_ids,
                    add_labels=[label_id],
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
