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
CLASSIFICATION_CONCURRENCY = 2
BATCH_THRESHOLD = 500
BATCH_POLL_INTERVAL = 30


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
            analysis_type: str = "ai",
            encrypted_access_token: str,
            encrypted_refresh_token: str,
            unread_only: bool,
            max_emails: int,
            auto_apply: bool,
            custom_categories: list[str] | None = None,
    ) -> asyncio.Task:
        if analysis_type == "inbox_scan":
            return asyncio.create_task(
                self._run_inbox_scan(
                    analysis_id=analysis_id,
                    encrypted_access_token=encrypted_access_token,
                    encrypted_refresh_token=encrypted_refresh_token,
                    unread_only=unread_only,
                    max_emails=max_emails,
                    auto_apply=auto_apply,
                )
            )
        return asyncio.create_task(
            self._run_analysis(
                analysis_id=analysis_id,
                encrypted_access_token=encrypted_access_token,
                encrypted_refresh_token=encrypted_refresh_token,
                unread_only=unread_only,
                max_emails=max_emails,
                auto_apply=auto_apply,
                custom_categories=custom_categories,
            )
        )

    def _create_analysis_repo(self) -> BaseAnalysisRepository:
        return SQLAlchemyAnalysisRepository(
            session_maker=self._async_session_maker
        )

    async def _run_inbox_scan(
            self,
            *,
            analysis_id: int,
            encrypted_access_token: str,
            encrypted_refresh_token: str,
            unread_only: bool,
            max_emails: int,
            auto_apply: bool,
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

            label_ids = ["UNREAD"] if unread_only else None
            message_ids = await self._email_service.list_messages(
                credentials=credentials, label_ids=label_ids, max_results=max_emails
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

            await analysis_repo.update_status(
                analysis_id=analysis_id,
                status="processing",
                total_emails=len(message_ids),
                processed_emails=0,
            )

            all_records: list[ClassifiedEmail] = []
            for i in range(0, len(message_ids), 50):
                chunk_ids = message_ids[i: i + 50]
                emails = await self._email_service.get_messages_batch(
                    credentials=credentials, message_ids=chunk_ids
                )
                records = [
                    ClassifiedEmail(
                        analysis_id=analysis_id,
                        gmail_message_id=email.gmail_message_id,
                        gmail_thread_id=email.gmail_thread_id,
                        sender=email.sender,
                        sender_domain=email.sender_domain,
                        subject=email.subject,
                        snippet=email.snippet,
                        received_at=email.received_at,
                        category=email.gmail_category or "primary",
                        has_unsubscribe=email.has_unsubscribe,
                        unsubscribe_header=email.unsubscribe_header,
                        unsubscribe_post_header=email.unsubscribe_post_header,
                    )
                    for email in emails
                ]
                created = await self._classified_email_repo.bulk_create(emails=records)
                all_records.extend(created)

                await analysis_repo.update_status(
                    analysis_id=analysis_id,
                    status="processing",
                    processed_emails=min(i + 50, len(message_ids)),
                )

            if auto_apply and all_records:
                category_actions = {
                    "spam": ["mark_spam"],
                    "promotions": ["mark_read"],
                }
                await analysis_repo.update_category_actions(
                    analysis_id=analysis_id,
                    category_actions=category_actions,
                )
                await self._auto_apply_actions(
                    classified_emails=all_records,
                    category_actions=category_actions,
                    encrypted_access_token=encrypted_access_token,
                    encrypted_refresh_token=encrypted_refresh_token,
                )

            if all_records:
                try:
                    category_samples = self._build_category_samples(
                        classified_emails=all_records
                    )
                    insights = await self._classification_service.generate_insights(
                        category_samples=category_samples,
                    )
                    if insights:
                        await analysis_repo.update_insights(
                            analysis_id=analysis_id,
                            ai_insights=insights,
                        )
                except Exception:
                    logger.warning("Failed to generate insights for inbox scan %d", analysis_id)

            await analysis_repo.update_status(
                analysis_id=analysis_id,
                status="completed",
                processed_emails=len(message_ids),
                completed_at=datetime.now(UTC),
            )

        except Exception as exc:
            logger.exception("Inbox scan %d failed", analysis_id)
            await analysis_repo.update_status(
                analysis_id=analysis_id,
                status="failed",
                error_message=str(exc),
                completed_at=datetime.now(UTC),
            )

    async def _run_analysis(
            self,
            *,
            analysis_id: int,
            encrypted_access_token: str,
            encrypted_refresh_token: str,
            unread_only: bool,
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

            label_ids = ["UNREAD"] if unread_only else None
            message_ids = await self._email_service.list_messages(
                credentials=credentials, label_ids=label_ids, max_results=max_emails
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

            existing_categories = list(BASE_CATEGORIES)
            if custom_categories:
                for cat in custom_categories:
                    if cat not in existing_categories:
                        existing_categories.append(cat)

            batches = [
                emails[i: i + BATCH_SIZE]
                for i in range(0, len(emails), BATCH_SIZE)
            ]

            use_batch = len(emails) > BATCH_THRESHOLD
            if use_batch:
                all_classified = await self._classify_with_batch_api(
                    analysis_id=analysis_id,
                    analysis_repo=analysis_repo,
                    emails=emails,
                    batches=batches,
                    existing_categories=existing_categories,
                )
            else:
                all_classified = await self._classify_realtime(
                    analysis_id=analysis_id,
                    analysis_repo=analysis_repo,
                    emails=emails,
                    batches=batches,
                    existing_categories=existing_categories,
                )

            # Pass 2: Verification
            category_samples = self._build_category_samples(
                classified_emails=all_classified
            )
            verification = await self._classification_service.verify_categories(
                category_samples=category_samples,
            )

            await analysis_repo.update_category_actions(
                analysis_id=analysis_id,
                category_actions=verification.category_actions,
            )

            try:
                insights = await self._classification_service.generate_insights(
                    category_samples=category_samples,
                )
                if insights:
                    await analysis_repo.update_insights(
                        analysis_id=analysis_id,
                        ai_insights=insights,
                    )
            except Exception:
                logger.warning("Failed to generate insights for analysis %d", analysis_id)

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

    async def _classify_realtime(
            self,
            *,
            analysis_id: int,
            analysis_repo: BaseAnalysisRepository,
            emails: list,
            batches: list[list],
            existing_categories: list[str],
    ) -> list[ClassifiedEmail]:
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
                        unsubscribe_header=email.unsubscribe_header,
                        unsubscribe_post_header=email.unsubscribe_post_header,
                    )
                )
            return records

        total_batches = len(batches)
        logger.info(
            "Analysis %d: classifying %d emails in %d batches (concurrency=%d)",
            analysis_id, len(emails), total_batches, CLASSIFICATION_CONCURRENCY,
        )

        for chunk_start in range(0, total_batches, CLASSIFICATION_CONCURRENCY):
            chunk = batches[chunk_start: chunk_start + CLASSIFICATION_CONCURRENCY]
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

        return all_classified

    async def _classify_with_batch_api(
            self,
            *,
            analysis_id: int,
            analysis_repo: BaseAnalysisRepository,
            emails: list,
            batches: list[list],
            existing_categories: list[str],
    ) -> list[ClassifiedEmail]:
        logger.info(
            "Analysis %d: using batch API for %d emails in %d batches",
            analysis_id, len(emails), len(batches),
        )

        batch_id = await self._classification_service.submit_batch_classification(
            email_batches=batches,
            existing_categories=existing_categories,
        )

        await analysis_repo.update_status(
            analysis_id=analysis_id,
            status="processing",
            batch_id=batch_id,
        )

        while True:
            status = await self._classification_service.check_batch_status(
                batch_id=batch_id
            )
            if status == "ended":
                break
            logger.info(
                "Analysis %d: batch %s still processing, waiting %ds",
                analysis_id, batch_id, BATCH_POLL_INTERVAL,
            )
            await asyncio.sleep(BATCH_POLL_INTERVAL)

        batch_results = await self._classification_service.retrieve_batch_results(
            batch_id=batch_id
        )

        all_classified: list[ClassifiedEmail] = []
        for batch_idx, batch_emails in enumerate(batches):
            custom_id = f"batch-{batch_idx}"
            results = batch_results.get(custom_id, [])
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
                        unsubscribe_header=email.unsubscribe_header,
                        unsubscribe_post_header=email.unsubscribe_post_header,
                    )
                )

            if records:
                created = await self._classified_email_repo.bulk_create(emails=records)
                all_classified.extend(created)

        await analysis_repo.update_status(
            analysis_id=analysis_id,
            status="processing",
            processed_emails=len(emails),
        )

        return all_classified

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

        if action == "undo":
            await self._undo_actions(
                classified_emails=classified_emails,
                credentials=credentials,
            )
            return

        if action == "keep":
            pass
        elif action == "move_to_category":
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
        elif action == "mark_read":
            await self._email_service.modify_messages(
                credentials=credentials,
                message_ids=msg_ids,
                remove_labels=["UNREAD"],
            )
        elif action == "mark_spam":
            await self._email_service.modify_messages(
                credentials=credentials,
                message_ids=msg_ids,
                add_labels=["SPAM"],
                remove_labels=["INBOX"],
            )
        elif action == "unsubscribe":
            from app.services.unsubscribe_service import (
                attempt_http_unsubscribe,
                parse_unsubscribe_urls,
            )

            archive_ids: list[str] = []
            failed_ids: list[str] = []
            unsubscribable = [e for e in classified_emails if e.has_unsubscribe]
            skipped_ids = [e.id for e in classified_emails if not e.has_unsubscribe]

            for e in unsubscribable:
                unsubscribed = False
                if e.unsubscribe_post_header and e.unsubscribe_header:
                    urls = parse_unsubscribe_urls(header=e.unsubscribe_header)
                    for url in urls:
                        if await attempt_http_unsubscribe(url=url):
                            unsubscribed = True
                            break

                if unsubscribed:
                    archive_ids.append(e.gmail_message_id)
                else:
                    failed_ids.append(e.gmail_message_id)

            if archive_ids:
                await self._email_service.modify_messages(
                    credentials=credentials,
                    message_ids=archive_ids,
                    remove_labels=["INBOX"],
                )
            if failed_ids:
                await self._email_service.modify_messages(
                    credentials=credentials,
                    message_ids=failed_ids,
                    add_labels=["SPAM"],
                    remove_labels=["INBOX"],
                )

            acted_ids = [e.id for e in unsubscribable]
            if acted_ids:
                await self._classified_email_repo.bulk_record_action(
                    email_ids=acted_ids, action=action
                )
                await self._classified_email_repo.bulk_update_action_taken(
                    email_ids=acted_ids, action_taken=action
                )
            if skipped_ids:
                logger.info(
                    "Skipped %d emails without unsubscribe headers", len(skipped_ids)
                )
            return

        await self._classified_email_repo.bulk_record_action(
            email_ids=email_ids, action=action
        )
        await self._classified_email_repo.bulk_update_action_taken(
            email_ids=email_ids, action_taken=action
        )

    async def _undo_actions(
            self,
            *,
            classified_emails: list[ClassifiedEmail],
            credentials: object,
    ) -> None:
        actionable = [e for e in classified_emails if e.action_taken is not None]
        if not actionable:
            return

        spam_msg_ids: list[str] = []
        read_msg_ids: list[str] = []
        moved_emails: list[ClassifiedEmail] = []
        unsub_msg_ids: list[str] = []

        for e in actionable:
            if e.action_taken == "mark_spam":
                spam_msg_ids.append(e.gmail_message_id)
            elif e.action_taken == "mark_read":
                read_msg_ids.append(e.gmail_message_id)
            elif e.action_taken == "move_to_category":
                moved_emails.append(e)
            elif e.action_taken == "unsubscribe":
                unsub_msg_ids.append(e.gmail_message_id)

        if spam_msg_ids:
            await self._email_service.modify_messages(
                credentials=credentials,
                message_ids=spam_msg_ids,
                add_labels=["INBOX"],
                remove_labels=["SPAM"],
            )
        if read_msg_ids:
            await self._email_service.modify_messages(
                credentials=credentials,
                message_ids=read_msg_ids,
                add_labels=["UNREAD"],
            )
        if moved_emails:
            by_cat: dict[str, list[str]] = defaultdict(list)
            for e in moved_emails:
                by_cat[e.category or "primary"].append(e.gmail_message_id)
            for cat, cat_msg_ids in by_cat.items():
                label_id = await self._email_service.get_or_create_label(
                    credentials=credentials, label_name=cat,
                )
                await self._email_service.modify_messages(
                    credentials=credentials,
                    message_ids=cat_msg_ids,
                    remove_labels=[label_id],
                )
        if unsub_msg_ids:
            await self._email_service.modify_messages(
                credentials=credentials,
                message_ids=unsub_msg_ids,
                add_labels=["INBOX"],
                remove_labels=["SPAM"],
            )

        await self._classified_email_repo.pop_last_action(
            email_ids=[e.id for e in actionable]
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
            action = next((a for a in actions if a != "keep"), None)
            if action is None:
                if cat in ("primary", "important"):
                    continue
                action = "mark_read"
            await self._apply_actions(
                classified_emails=emails_in_cat,
                action=action,
                encrypted_access_token=encrypted_access_token,
                encrypted_refresh_token=encrypted_refresh_token,
            )
