from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from app.models.db import Analysis, ClassifiedEmail, User
from app.models.schemas import ClassificationResult, EmailMetadata, VerificationResult


class BaseEmailService(ABC):
    @abstractmethod
    def build_credentials(
        self, *, access_token: str, refresh_token: str
    ) -> Any: ...

    @abstractmethod
    async def list_messages(
        self,
        *,
        credentials: Any,
        label_ids: list[str] | None = None,
        query: str = "",
        max_results: int = 500,
    ) -> list[str]: ...

    @abstractmethod
    async def get_messages_batch(
        self, *, credentials: Any, message_ids: list[str]
    ) -> list[EmailMetadata]: ...

    @abstractmethod
    async def modify_messages(
        self,
        *,
        credentials: Any,
        message_ids: list[str],
        add_labels: list[str] | None = None,
        remove_labels: list[str] | None = None,
    ) -> None: ...

    @abstractmethod
    async def get_or_create_label(
        self, *, credentials: Any, label_name: str
    ) -> str: ...

    @abstractmethod
    async def get_inbox_counts(
        self, *, credentials: Any
    ) -> dict[str, int]: ...

    @abstractmethod
    async def trash_messages(
        self, *, credentials: Any, message_ids: list[str]
    ) -> None: ...


class BaseAuthService(ABC):
    @abstractmethod
    def start_authorization(self) -> str: ...

    @abstractmethod
    def exchange_code(self, *, code: str, state: str) -> Any: ...

    @abstractmethod
    def get_user_info(self, *, credentials: Any) -> dict: ...

    @abstractmethod
    async def revoke_token(self, *, token: str) -> None: ...


class BaseSecurityService(ABC):
    @abstractmethod
    def encrypt_token(self, *, token: str) -> str: ...

    @abstractmethod
    def decrypt_token(self, *, encrypted_token: str) -> str: ...

    @abstractmethod
    def create_jwt(self, *, user_id: int) -> str: ...

    @abstractmethod
    def decode_jwt(self, *, token: str) -> dict: ...


class BaseUserRepository(ABC):
    @abstractmethod
    async def find_by_id(self, *, user_id: int) -> User | None: ...

    @abstractmethod
    async def find_by_google_id(self, *, google_id: str) -> User | None: ...

    @abstractmethod
    async def save(self, *, user: User) -> User: ...


class BaseClassificationService(ABC):
    @abstractmethod
    async def classify_emails(
        self, *, emails: list[EmailMetadata], existing_categories: list[str] | None = None
    ) -> list[ClassificationResult]: ...

    @abstractmethod
    async def verify_categories(
        self,
        category_samples: dict[str, list[dict]],
    ) -> VerificationResult: ...

    @abstractmethod
    async def submit_batch_classification(
        self,
        *,
        email_batches: list[list[EmailMetadata]],
        existing_categories: list[str] | None = None,
    ) -> str: ...

    @abstractmethod
    async def check_batch_status(self, *, batch_id: str) -> str: ...

    @abstractmethod
    async def retrieve_batch_results(
        self, *, batch_id: str
    ) -> dict[str, list[ClassificationResult]]: ...

    @abstractmethod
    async def generate_insights(
        self, category_samples: dict[str, list[dict]]
    ) -> list[str]: ...


class BaseAnalysisRepository(ABC):
    @abstractmethod
    async def find_by_id_and_user(
        self, *, analysis_id: int, user_id: int
    ) -> Analysis | None: ...

    @abstractmethod
    async def delete_with_emails(self, *, analysis: Analysis) -> None: ...

    @abstractmethod
    async def create(self, *, analysis: Analysis) -> Analysis: ...

    @abstractmethod
    async def list_by_user(self, *, user_id: int) -> list[Analysis]: ...

    @abstractmethod
    async def update_status(
        self,
        *,
        analysis_id: int,
        status: str,
        processed_emails: int | None = None,
        total_emails: int | None = None,
        batch_id: str | None = None,
        error_message: str | None = None,
        completed_at: datetime | None = None,
    ) -> None: ...

    @abstractmethod
    async def find_by_id_and_user_with_emails(
        self, *, analysis_id: int, user_id: int
    ) -> Analysis | None: ...

    @abstractmethod
    async def update_category_actions(
        self, *, analysis_id: int, category_actions: dict
    ) -> None: ...

    @abstractmethod
    async def update_insights(
        self, *, analysis_id: int, ai_insights: list[str]
    ) -> None: ...


class BaseClassifiedEmailRepository(ABC):
    @abstractmethod
    async def delete_expired(self) -> None: ...

    @abstractmethod
    async def bulk_create(
        self, *, emails: list[ClassifiedEmail]
    ) -> list[ClassifiedEmail]: ...

    @abstractmethod
    async def find_by_analysis_id(
        self, *, analysis_id: int
    ) -> list[ClassifiedEmail]: ...

    @abstractmethod
    async def find_by_ids_and_analysis(
        self, *, email_ids: list[int], analysis_id: int
    ) -> list[ClassifiedEmail]: ...

    @abstractmethod
    async def update_action_taken(
        self, *, email_id: int, action_taken: str
    ) -> None: ...

    @abstractmethod
    async def get_category_summary(
        self, *, analysis_id: int
    ) -> list[dict]: ...

    @abstractmethod
    async def find_by_category_and_analysis(
        self, *, category: str, analysis_id: int
    ) -> list[ClassifiedEmail]: ...

    @abstractmethod
    async def find_by_sender_domain_and_analysis(
        self, *, sender_domain: str, analysis_id: int
    ) -> list[ClassifiedEmail]: ...

    @abstractmethod
    async def bulk_update_action_taken(
        self, *, email_ids: list[int], action_taken: str | None
    ) -> None: ...

    @abstractmethod
    async def bulk_update_category(
        self, *, analysis_id: int, from_category: str, to_category: str
    ) -> None: ...

    @abstractmethod
    async def get_sender_summary(
        self, *, analysis_id: int, category: str | None = None
    ) -> list[dict]: ...

    @abstractmethod
    async def bulk_record_action(
        self, *, email_ids: list[int], action: str
    ) -> None: ...

    @abstractmethod
    async def find_by_filters(
        self,
        *,
        analysis_id: int,
        category: str | None = None,
        sender_domain: str | None = None,
    ) -> list[ClassifiedEmail]: ...

    @abstractmethod
    async def pop_last_action(
        self, *, email_ids: list[int]
    ) -> dict[int, str | None]: ...
