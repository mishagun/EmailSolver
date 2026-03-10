from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, status

from app.core import protocols
from app.core.dependencies import (
    get_analysis_repository,
    get_analysis_service,
    get_classified_email_repository,
    get_current_user,
)
from app.models.db import User
from app.models.schemas import (
    AnalysisCreateRequest,
    AnalysisListResponse,
    AnalysisResponse,
    ApplyActionsRequest,
    CategorySummary,
    ClassifiedEmailResponse,
    MessageResponse,
    SenderGroupSummary,
)
from app.services.analysis_service import AnalysisService

router = APIRouter()


@router.post("", status_code=status.HTTP_202_ACCEPTED, response_model=AnalysisResponse)
async def create_analysis(
    request: AnalysisCreateRequest,
    user: User = Depends(get_current_user),
    analysis_repo: protocols.BaseAnalysisRepository = Depends(get_analysis_repository),
    analysis_service: AnalysisService = Depends(get_analysis_service),
) -> AnalysisResponse:
    from app.models.db import Analysis

    analysis = await analysis_repo.create(
        analysis=Analysis(
            user_id=user.id,
            analysis_type=request.analysis_type.value,
            status="pending",
            query=request.query,
        )
    )

    analysis_service.start_analysis(
        analysis_id=analysis.id,
        analysis_type=request.analysis_type.value,
        encrypted_access_token=user.encrypted_access_token,
        encrypted_refresh_token=user.encrypted_refresh_token,
        query=request.query,
        max_emails=request.max_emails,
        auto_apply=request.auto_apply,
        custom_categories=request.custom_categories,
    )

    return AnalysisResponse(
        id=analysis.id,
        analysis_type=analysis.analysis_type,
        status=analysis.status,
        query=analysis.query,
        created_at=analysis.created_at,
    )


@router.get("", response_model=AnalysisListResponse)
async def list_analyses(
    user: User = Depends(get_current_user),
    analysis_repo: protocols.BaseAnalysisRepository = Depends(get_analysis_repository),
) -> AnalysisListResponse:
    analyses = await analysis_repo.list_by_user(user_id=user.id)
    return AnalysisListResponse(
        analyses=[
            AnalysisResponse(
                id=a.id,
                analysis_type=a.analysis_type,
                status=a.status,
                query=a.query,
                total_emails=a.total_emails,
                processed_emails=a.processed_emails,
                error_message=a.error_message,
                created_at=a.created_at,
                completed_at=a.completed_at,
            )
            for a in analyses
        ],
        total=len(analyses),
    )


@router.get("/{analysis_id}", response_model=AnalysisResponse)
async def get_analysis(
    analysis_id: int,
    user: User = Depends(get_current_user),
    analysis_repo: protocols.BaseAnalysisRepository = Depends(get_analysis_repository),
) -> AnalysisResponse:
    analysis = await analysis_repo.find_by_id_and_user_with_emails(
        analysis_id=analysis_id, user_id=user.id
    )
    if analysis is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis not found",
        )

    classified = [
        ClassifiedEmailResponse(
            id=e.id,
            gmail_message_id=e.gmail_message_id,
            gmail_thread_id=e.gmail_thread_id,
            sender=e.sender,
            sender_domain=e.sender_domain,
            subject=e.subject,
            snippet=e.snippet,
            received_at=e.received_at,
            category=e.category,
            importance=e.importance,
            sender_type=e.sender_type,
            confidence=e.confidence,
            has_unsubscribe=e.has_unsubscribe,
            unsubscribe_header=e.unsubscribe_header,
            unsubscribe_post_header=e.unsubscribe_post_header,
            action_taken=e.action_taken,
        )
        for e in analysis.classified_emails
    ]

    summary = _build_summary(
        classified_emails=analysis.classified_emails,
        category_actions=analysis.category_actions,
    )

    return AnalysisResponse(
        id=analysis.id,
        analysis_type=analysis.analysis_type,
        status=analysis.status,
        query=analysis.query,
        total_emails=analysis.total_emails,
        processed_emails=analysis.processed_emails,
        error_message=analysis.error_message,
        created_at=analysis.created_at,
        completed_at=analysis.completed_at,
        summary=summary,
        classified_emails=classified,
    )


def _build_summary(
    *,
    classified_emails: list,
    category_actions: dict | None,
) -> list[CategorySummary]:
    counts: dict[str, int] = defaultdict(int)
    for e in classified_emails:
        cat = e.category or "primary"
        counts[cat] += 1

    actions_map = category_actions or {}
    return [
        CategorySummary(
            category=cat,
            count=count,
            recommended_actions=actions_map.get(cat, []),
        )
        for cat, count in sorted(counts.items(), key=lambda x: -x[1])
    ]


@router.get("/{analysis_id}/senders", response_model=list[SenderGroupSummary])
async def get_sender_groups(
    analysis_id: int,
    category: str | None = None,
    user: User = Depends(get_current_user),
    analysis_repo: protocols.BaseAnalysisRepository = Depends(get_analysis_repository),
    classified_email_repo: protocols.BaseClassifiedEmailRepository = Depends(
        get_classified_email_repository
    ),
) -> list[SenderGroupSummary]:
    analysis = await analysis_repo.find_by_id_and_user(
        analysis_id=analysis_id, user_id=user.id
    )
    if analysis is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis not found",
        )
    rows = await classified_email_repo.get_sender_summary(
        analysis_id=analysis_id, category=category
    )
    return [SenderGroupSummary(**row) for row in rows]


@router.post("/{analysis_id}/apply", response_model=MessageResponse)
async def apply_actions(
    analysis_id: int,
    request: ApplyActionsRequest,
    user: User = Depends(get_current_user),
    analysis_repo: protocols.BaseAnalysisRepository = Depends(get_analysis_repository),
    analysis_service: AnalysisService = Depends(get_analysis_service),
    classified_email_repo: protocols.BaseClassifiedEmailRepository = Depends(
        get_classified_email_repository
    ),
) -> MessageResponse:
    analysis = await analysis_repo.find_by_id_and_user_with_emails(
        analysis_id=analysis_id, user_id=user.id
    )
    if analysis is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis not found",
        )
    if analysis.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Analysis is not completed yet",
        )

    if request.email_ids is not None:
        emails = await classified_email_repo.find_by_ids_and_analysis(
            email_ids=request.email_ids, analysis_id=analysis_id
        )
    elif request.category is not None:
        emails = await classified_email_repo.find_by_category_and_analysis(
            category=request.category, analysis_id=analysis_id
        )
    elif request.sender_domain is not None:
        emails = await classified_email_repo.find_by_sender_domain_and_analysis(
            sender_domain=request.sender_domain, analysis_id=analysis_id
        )
    else:
        emails = list(analysis.classified_emails)

    await analysis_service.apply_actions_for_analysis(
        classified_emails=emails,
        action=request.action.value,
        encrypted_access_token=user.encrypted_access_token,
        encrypted_refresh_token=user.encrypted_refresh_token,
    )

    return MessageResponse(message="Actions applied successfully")


@router.delete("/{analysis_id}", response_model=MessageResponse)
async def delete_analysis(
    analysis_id: int,
    user: User = Depends(get_current_user),
    analysis_repo: protocols.BaseAnalysisRepository = Depends(get_analysis_repository),
) -> MessageResponse:
    analysis = await analysis_repo.find_by_id_and_user(
        analysis_id=analysis_id, user_id=user.id
    )
    if analysis is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis not found",
        )

    await analysis_repo.delete_with_emails(analysis=analysis)

    return MessageResponse(message="Analysis and classified emails deleted")
