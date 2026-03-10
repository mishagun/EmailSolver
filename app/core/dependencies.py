from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import protocols
from app.core.config import config
from app.core.database import async_session_maker, get_db
from app.core.security import FernetSecurityService
from app.models.db import User
from app.repositories.analysis_repository import SQLAlchemyAnalysisRepository
from app.repositories.classified_email_repository import SQLAlchemyClassifiedEmailRepository
from app.repositories.user_repository import SQLAlchemyUserRepository
from app.services.analysis_service import AnalysisService
from app.services.auth_service import GoogleAuthService
from app.services.classification_service import ClaudeClassificationService
from app.services.gmail_service import GmailService

bearer_scheme = HTTPBearer()

GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "openid",
]


def get_security_service() -> protocols.BaseSecurityService:
    return FernetSecurityService(
        fernet_key=config.fernet_key,
        jwt_secret_key=config.jwt_secret_key,
        jwt_algorithm=config.jwt_algorithm,
        jwt_expire_minutes=config.jwt_expire_minutes,
    )


def get_email_service() -> protocols.BaseEmailService:
    return GmailService(
        client_id=config.google_client_id,
        client_secret=config.google_client_secret,
        token_uri=config.google_token_uri,
    )


_auth_service = GoogleAuthService(
    client_id=config.google_client_id,
    client_secret=config.google_client_secret,
    redirect_uri=config.google_redirect_uri,
    scopes=GOOGLE_SCOPES,
    auth_uri=config.google_auth_uri,
    token_uri=config.google_token_uri,
    revoke_url=config.google_revoke_url,
)


def get_auth_service() -> protocols.BaseAuthService:
    return _auth_service


def get_user_repository(
    session: AsyncSession = Depends(get_db),
) -> protocols.BaseUserRepository:
    return SQLAlchemyUserRepository(session=session)


def get_analysis_repository(
    session: AsyncSession = Depends(get_db),
) -> protocols.BaseAnalysisRepository:
    return SQLAlchemyAnalysisRepository(session=session)


def get_classification_service() -> protocols.BaseClassificationService:
    return ClaudeClassificationService(
        api_key=config.anthropic_api_key,
        model=config.anthropic_model,
    )


def get_classified_email_repository() -> protocols.BaseClassifiedEmailRepository:
    return SQLAlchemyClassifiedEmailRepository(session_maker=async_session_maker)


def get_analysis_service(
    email_service: protocols.BaseEmailService = Depends(get_email_service),
    classification_service: protocols.BaseClassificationService = Depends(
        get_classification_service
    ),
    security_service: protocols.BaseSecurityService = Depends(get_security_service),
    classified_email_repo: protocols.BaseClassifiedEmailRepository = Depends(
        get_classified_email_repository
    ),
) -> AnalysisService:
    return AnalysisService(
        email_service=email_service,
        classification_service=classification_service,
        security_service=security_service,
        classified_email_repo=classified_email_repo,
        async_session_maker=async_session_maker,
    )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    security_service: protocols.BaseSecurityService = Depends(get_security_service),
    user_repo: protocols.BaseUserRepository = Depends(get_user_repository),
) -> User:
    try:
        payload = security_service.decode_jwt(token=credentials.credentials)
        user_id = int(payload["sub"])
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from exc
    user = await user_repo.find_by_id(user_id=user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    return user
