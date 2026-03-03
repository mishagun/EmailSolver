from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel


class AuthStatusResponse(BaseModel):
    authenticated: bool
    email: str | None = None
    display_name: str | None = None


class AuthCallbackResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MessageResponse(BaseModel):
    message: str


class EmailMetadata(BaseModel):
    gmail_message_id: str
    gmail_thread_id: str | None = None
    sender: str | None = None
    sender_domain: str | None = None
    subject: str | None = None
    snippet: str | None = None
    received_at: datetime | None = None
    has_unsubscribe: bool = False


class EmailListResponse(BaseModel):
    emails: list[EmailMetadata]
    total: int
    query: str


class EmailStatsResponse(BaseModel):
    unread_count: int
    total_count: int


class ActionType(StrEnum):
    KEEP = "keep"
    MOVE_TO_CATEGORY = "move_to_category"
    MARK_READ = "mark_read"
    MARK_SPAM = "mark_spam"
    UNSUBSCRIBE = "unsubscribe"


class ClassificationResult(BaseModel):
    gmail_message_id: str
    category: str
    importance: int
    sender_type: str
    confidence: float


class CategoryMerge(BaseModel):
    from_category: str
    to_category: str


class VerificationResult(BaseModel):
    merges: list[CategoryMerge]
    category_actions: dict[str, list[str]]


class CategorySummary(BaseModel):
    category: str
    count: int
    recommended_actions: list[str]


class AnalysisCreateRequest(BaseModel):
    query: str = "is:unread"
    max_emails: int = 100
    auto_apply: bool = False
    custom_categories: list[str] | None = None


class ClassifiedEmailResponse(BaseModel):
    id: int
    gmail_message_id: str
    gmail_thread_id: str | None = None
    sender: str | None = None
    sender_domain: str | None = None
    subject: str | None = None
    snippet: str | None = None
    received_at: datetime | None = None
    category: str | None = None
    importance: int | None = None
    sender_type: str | None = None
    confidence: float | None = None
    has_unsubscribe: bool | None = None
    action_taken: str | None = None


class AnalysisResponse(BaseModel):
    id: int
    status: str
    query: str | None = None
    total_emails: int | None = None
    processed_emails: int | None = None
    error_message: str | None = None
    created_at: datetime
    completed_at: datetime | None = None
    summary: list[CategorySummary] | None = None
    classified_emails: list[ClassifiedEmailResponse] | None = None


class AnalysisListResponse(BaseModel):
    analyses: list[AnalysisResponse]
    total: int


class ApplyActionsRequest(BaseModel):
    action: ActionType
    category: str | None = None
    sender_domain: str | None = None
    email_ids: list[int] | None = None


class HealthResponse(BaseModel):
    status: str
    environment: str
