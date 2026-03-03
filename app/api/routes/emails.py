from fastapi import APIRouter, Depends, Query

from app.core import protocols
from app.core.dependencies import get_current_user, get_email_service, get_security_service
from app.models.db import User
from app.models.schemas import EmailListResponse, EmailStatsResponse

router = APIRouter()


@router.get("", response_model=EmailListResponse)
async def list_emails(
    user: User = Depends(get_current_user),
    query: str = Query(default="is:unread"),
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
    message_ids = await email_service.list_messages(
        credentials=credentials, query=query, max_results=max_results
    )
    emails = await email_service.get_messages_batch(
        credentials=credentials, message_ids=message_ids
    )
    return EmailListResponse(emails=emails, total=len(emails), query=query)


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
    unread_ids = await email_service.list_messages(
        credentials=credentials, query="is:unread", max_results=1
    )
    total_ids = await email_service.list_messages(
        credentials=credentials, query="", max_results=1
    )
    return EmailStatsResponse(
        unread_count=len(unread_ids),
        total_count=len(total_ids),
    )
