from fastapi import APIRouter, Depends, Query

from app.core import protocols
from app.core.dependencies import get_current_user, get_email_service, get_security_service
from app.models.db import User
from app.models.schemas import EmailListResponse, EmailStatsResponse

router = APIRouter()


@router.get("", response_model=EmailListResponse)
async def list_emails(
    user: User = Depends(get_current_user),
    unread_only: bool = Query(default=True),
    max_results: int = Query(default=50, le=500),
    email_service: protocols.BaseEmailService = Depends(get_email_service),
    security_service: protocols.BaseSecurityService = Depends(get_security_service),
) -> EmailListResponse:
    credentials = email_service.build_credentials(
        access_token=security_service.decrypt_token(
            encrypted_token=user.encrypted_access_token
        ),
        refresh_token=security_service.decrypt_token(
            encrypted_token=user.encrypted_refresh_token
        ),
    )
    label_ids = ["UNREAD"] if unread_only else None
    message_ids = await email_service.list_messages(
        credentials=credentials, label_ids=label_ids, max_results=max_results
    )
    emails = await email_service.get_messages_batch(
        credentials=credentials, message_ids=message_ids
    )
    return EmailListResponse(emails=emails, total=len(emails), unread_only=unread_only)


@router.get("/stats", response_model=EmailStatsResponse)
async def email_stats(
    user: User = Depends(get_current_user),
    email_service: protocols.BaseEmailService = Depends(get_email_service),
    security_service: protocols.BaseSecurityService = Depends(get_security_service),
) -> EmailStatsResponse:
    credentials = email_service.build_credentials(
        access_token=security_service.decrypt_token(
            encrypted_token=user.encrypted_access_token
        ),
        refresh_token=security_service.decrypt_token(
            encrypted_token=user.encrypted_refresh_token
        ),
    )
    counts = await email_service.get_inbox_counts(credentials=credentials)
    return EmailStatsResponse(
        unread_count=counts["unread_count"],
        total_count=counts["total_count"],
    )
