import asyncio
from datetime import datetime
from email.utils import parsedate_to_datetime

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from app.core.protocols import BaseEmailService
from app.models.schemas import EmailMetadata

GMAIL_CATEGORY_MAP = {
    "CATEGORY_SOCIAL": "social",
    "CATEGORY_PROMOTIONS": "promotions",
    "CATEGORY_UPDATES": "updates",
    "CATEGORY_FORUMS": "forums",
    "CATEGORY_PERSONAL": "primary",
}


class GmailService(BaseEmailService):
    def __init__(
        self, *, client_id: str, client_secret: str, token_uri: str
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._token_uri = token_uri

    def build_credentials(
        self, *, access_token: str, refresh_token: str
    ) -> Credentials:
        return Credentials(
            token=access_token,
            refresh_token=refresh_token,
            token_uri=self._token_uri,
            client_id=self._client_id,
            client_secret=self._client_secret,
        )

    async def list_messages(
        self,
        *,
        credentials: Credentials,
        label_ids: list[str] | None = None,
        query: str = "",
        max_results: int = 500,
    ) -> list[str]:
        return await asyncio.to_thread(
            self._list_messages_sync,
            credentials=credentials,
            label_ids=label_ids,
            query=query,
            max_results=max_results,
        )

    async def get_messages_batch(
        self, *, credentials: Credentials, message_ids: list[str]
    ) -> list[EmailMetadata]:
        return await asyncio.to_thread(
            self._get_messages_batch_sync,
            credentials=credentials,
            message_ids=message_ids,
        )

    async def get_or_create_label(
        self, *, credentials: Credentials, label_name: str
    ) -> str:
        return await asyncio.to_thread(
            self._get_or_create_label_sync,
            credentials=credentials,
            label_name=label_name,
        )

    async def modify_messages(
        self,
        *,
        credentials: Credentials,
        message_ids: list[str],
        add_labels: list[str] | None = None,
        remove_labels: list[str] | None = None,
    ) -> None:
        await asyncio.to_thread(
            self._modify_messages_sync,
            credentials=credentials,
            message_ids=message_ids,
            add_labels=add_labels,
            remove_labels=remove_labels,
        )

    async def get_inbox_counts(
        self, *, credentials: Credentials
    ) -> dict[str, int]:
        return await asyncio.to_thread(
            self._get_inbox_counts_sync,
            credentials=credentials,
        )

    async def trash_messages(
        self, *, credentials: Credentials, message_ids: list[str]
    ) -> None:
        await asyncio.to_thread(
            self._trash_messages_sync,
            credentials=credentials,
            message_ids=message_ids,
        )

    @staticmethod
    def _extract_header(*, headers: list[dict], name: str) -> str | None:
        for header in headers:
            if header.get("name", "").lower() == name.lower():
                return header.get("value")
        return None

    @staticmethod
    def _extract_sender_domain(*, sender: str | None) -> str | None:
        if not sender:
            return None
        if "@" in sender:
            domain_part = sender.rsplit("@", 1)[1]
            return domain_part.rstrip(">").lower()
        return None

    @staticmethod
    def _parse_date(*, date_str: str | None) -> datetime | None:
        if not date_str:
            return None
        try:
            return parsedate_to_datetime(date_str)
        except Exception:
            return None

    @staticmethod
    def _extract_gmail_category(*, label_ids: list[str]) -> str:
        for label_id in label_ids:
            if label_id in GMAIL_CATEGORY_MAP:
                return GMAIL_CATEGORY_MAP[label_id]
        return "primary"

    @classmethod
    def _parse_message(cls, *, message: dict) -> EmailMetadata:
        headers = message.get("payload", {}).get("headers", [])
        sender = cls._extract_header(headers=headers, name="From")
        subject = cls._extract_header(headers=headers, name="Subject")
        date_str = cls._extract_header(headers=headers, name="Date")
        list_unsub = cls._extract_header(headers=headers, name="List-Unsubscribe")
        list_unsub_post = cls._extract_header(headers=headers, name="List-Unsubscribe-Post")
        label_ids = message.get("labelIds", [])

        return EmailMetadata(
            gmail_message_id=message["id"],
            gmail_thread_id=message.get("threadId"),
            sender=sender,
            sender_domain=cls._extract_sender_domain(sender=sender),
            subject=subject,
            snippet=message.get("snippet", "")[:300],
            received_at=cls._parse_date(date_str=date_str),
            has_unsubscribe=list_unsub is not None,
            unsubscribe_header=list_unsub,
            unsubscribe_post_header=list_unsub_post,
            gmail_category=cls._extract_gmail_category(label_ids=label_ids),
        )

    @staticmethod
    def _list_messages_sync(
        *,
        credentials: Credentials,
        label_ids: list[str] | None = None,
        query: str = "",
        max_results: int = 500,
    ) -> list[str]:
        service = build("gmail", "v1", credentials=credentials)
        message_ids: list[str] = []
        kwargs: dict = {
            "userId": "me",
            "maxResults": min(max_results, 500),
        }
        if label_ids:
            kwargs["labelIds"] = label_ids
        if query:
            kwargs["q"] = query
        request = service.users().messages().list(**kwargs)
        while request and len(message_ids) < max_results:
            response = request.execute()
            messages = response.get("messages", [])
            message_ids.extend(m["id"] for m in messages)
            request = service.users().messages().list_next(request, response)
        return message_ids[:max_results]

    @classmethod
    def _get_messages_batch_sync(
        cls, *, credentials: Credentials, message_ids: list[str]
    ) -> list[EmailMetadata]:
        service = build("gmail", "v1", credentials=credentials)
        results: list[EmailMetadata] = []

        for i in range(0, len(message_ids), 50):
            chunk = message_ids[i : i + 50]
            batch = service.new_batch_http_request()

            def callback(
                request_id: str, response: dict, exception: Exception | None
            ) -> None:
                if exception is None:
                    results.append(cls._parse_message(message=response))

            for msg_id in chunk:
                batch.add(
                    service.users()
                    .messages()
                    .get(
                        userId="me",
                        id=msg_id,
                        format="metadata",
                        metadataHeaders=[
                            "From",
                            "Subject",
                            "Date",
                            "List-Unsubscribe",
                            "List-Unsubscribe-Post",
                        ],
                    ),
                    callback=callback,
                )
            batch.execute()

        return results

    @staticmethod
    def _get_or_create_label_sync(
        *, credentials: Credentials, label_name: str
    ) -> str:
        service = build("gmail", "v1", credentials=credentials)
        labels = service.users().labels().list(userId="me").execute()
        for label in labels.get("labels", []):
            if label["name"] == label_name:
                return label["id"]
        created = service.users().labels().create(
            userId="me",
            body={
                "name": label_name,
                "labelListVisibility": "labelShow",
                "messageListVisibility": "show",
            },
        ).execute()
        return created["id"]

    @staticmethod
    def _modify_messages_sync(
        *,
        credentials: Credentials,
        message_ids: list[str],
        add_labels: list[str] | None = None,
        remove_labels: list[str] | None = None,
    ) -> None:
        service = build("gmail", "v1", credentials=credentials)
        body: dict = {}
        if add_labels:
            body["addLabelIds"] = add_labels
        if remove_labels:
            body["removeLabelIds"] = remove_labels

        for i in range(0, len(message_ids), 1000):
            chunk = message_ids[i : i + 1000]
            service.users().messages().batchModify(
                userId="me",
                body={"ids": chunk, **body},
            ).execute()

    @staticmethod
    def _get_inbox_counts_sync(*, credentials: Credentials) -> dict[str, int]:
        service = build("gmail", "v1", credentials=credentials)
        label = service.users().labels().get(userId="me", id="INBOX").execute()
        return {
            "unread_count": label.get("messagesUnread", 0),
            "total_count": label.get("messagesTotal", 0),
        }

    @staticmethod
    def _trash_messages_sync(
        *, credentials: Credentials, message_ids: list[str]
    ) -> None:
        service = build("gmail", "v1", credentials=credentials)
        for msg_id in message_ids:
            service.users().messages().trash(userId="me", id=msg_id).execute()
