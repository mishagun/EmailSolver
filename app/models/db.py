from datetime import UTC, datetime, timedelta

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import config
from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    google_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(255))
    encrypted_access_token: Mapped[str | None] = mapped_column(Text)
    encrypted_refresh_token: Mapped[str | None] = mapped_column(Text)
    token_expiry: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    analyses: Mapped[list["Analysis"]] = relationship(back_populates="user")


class Analysis(Base):
    __tablename__ = "analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    analysis_type: Mapped[str] = mapped_column(String(20), nullable=False, default="ai")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    query: Mapped[str | None] = mapped_column(String(500))
    total_emails: Mapped[int | None] = mapped_column(Integer)
    processed_emails: Mapped[int | None] = mapped_column(Integer)
    batch_id: Mapped[str | None] = mapped_column(String(255))
    error_message: Mapped[str | None] = mapped_column(Text)
    category_actions: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped["User"] = relationship(back_populates="analyses")
    classified_emails: Mapped[list["ClassifiedEmail"]] = relationship(
        back_populates="analysis", cascade="all, delete-orphan"
    )


def _default_expires_at() -> datetime:
    return datetime.now(UTC) + timedelta(days=config.classified_email_ttl_days)


class ClassifiedEmail(Base):
    __tablename__ = "classified_emails"
    __table_args__ = (
        Index("ix_classified_emails_category", "category"),
        Index("ix_classified_emails_sender_domain", "sender_domain"),
        Index("ix_classified_emails_expires_at", "expires_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    analysis_id: Mapped[int] = mapped_column(
        ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    gmail_message_id: Mapped[str] = mapped_column(String(255), nullable=False)
    gmail_thread_id: Mapped[str | None] = mapped_column(String(255))
    sender: Mapped[str | None] = mapped_column(String(500))
    sender_domain: Mapped[str | None] = mapped_column(String(255))
    subject: Mapped[str | None] = mapped_column(String(1000))
    snippet: Mapped[str | None] = mapped_column(Text)
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    category: Mapped[str | None] = mapped_column(String(50))
    importance: Mapped[int | None] = mapped_column(Integer)
    has_unsubscribe: Mapped[bool | None] = mapped_column(default=False)
    unsubscribe_header: Mapped[str | None] = mapped_column(Text, nullable=True)
    unsubscribe_post_header: Mapped[str | None] = mapped_column(Text, nullable=True)
    sender_type: Mapped[str | None] = mapped_column(String(50))
    confidence: Mapped[float | None] = mapped_column()
    action_taken: Mapped[str | None] = mapped_column(String(50))
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_default_expires_at
    )

    analysis: Mapped["Analysis"] = relationship(back_populates="classified_emails")
    action_history: Mapped[list["EmailActionHistory"]] = relationship(
        back_populates="classified_email", cascade="all, delete-orphan",
        order_by="EmailActionHistory.created_at.desc()",
    )


class EmailActionHistory(Base):
    __tablename__ = "email_action_history"
    __table_args__ = (
        Index("ix_email_action_history_email_id", "classified_email_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    classified_email_id: Mapped[int] = mapped_column(
        ForeignKey("classified_emails.id", ondelete="CASCADE"), nullable=False,
    )
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    classified_email: Mapped["ClassifiedEmail"] = relationship(
        back_populates="action_history"
    )
