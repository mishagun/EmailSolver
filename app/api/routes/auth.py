from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse

from app.core import protocols
from app.core.dependencies import (
    get_auth_service,
    get_current_user,
    get_security_service,
    get_user_repository,
)
from app.models.db import User
from app.models.schemas import AuthCallbackResponse, AuthStatusResponse, MessageResponse

router = APIRouter()


@router.get("/login")
async def login(
    auth_service: protocols.BaseAuthService = Depends(get_auth_service),
) -> RedirectResponse:
    auth_url = auth_service.start_authorization()
    return RedirectResponse(url=auth_url)


@router.get("/callback", response_model=AuthCallbackResponse)
async def callback(
    code: str,
    state: str,
    auth_service: protocols.BaseAuthService = Depends(get_auth_service),
    security_service: protocols.BaseSecurityService = Depends(get_security_service),
    user_repo: protocols.BaseUserRepository = Depends(get_user_repository),
) -> AuthCallbackResponse:
    credentials = auth_service.exchange_code(code=code, state=state)

    if not credentials or not credentials.token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to obtain credentials",
        )

    user_info = auth_service.get_user_info(credentials=credentials)

    google_id = user_info["id"]
    email = user_info["email"]
    display_name = user_info.get("name")

    user = await user_repo.find_by_google_id(google_id=google_id)

    encrypted_access = security_service.encrypt_token(token=credentials.token)
    encrypted_refresh = (
        security_service.encrypt_token(token=credentials.refresh_token)
        if credentials.refresh_token
        else None
    )

    if user is None:
        user = User(
            email=email,
            google_id=google_id,
            display_name=display_name,
            encrypted_access_token=encrypted_access,
            encrypted_refresh_token=encrypted_refresh,
            token_expiry=credentials.expiry,
        )
    else:
        user.email = email
        user.display_name = display_name
        user.encrypted_access_token = encrypted_access
        if encrypted_refresh:
            user.encrypted_refresh_token = encrypted_refresh
        user.token_expiry = credentials.expiry

    user = await user_repo.save(user=user)

    jwt_token = security_service.create_jwt(user_id=user.id)
    return AuthCallbackResponse(access_token=jwt_token)


@router.get("/status", response_model=AuthStatusResponse)
async def auth_status(
    user: User = Depends(get_current_user),
) -> AuthStatusResponse:
    return AuthStatusResponse(
        authenticated=True,
        email=user.email,
        display_name=user.display_name,
    )


@router.delete("/logout", response_model=MessageResponse)
async def logout(
    user: User = Depends(get_current_user),
    auth_service: protocols.BaseAuthService = Depends(get_auth_service),
    security_service: protocols.BaseSecurityService = Depends(get_security_service),
    user_repo: protocols.BaseUserRepository = Depends(get_user_repository),
) -> MessageResponse:
    if user.encrypted_access_token:
        try:
            access_token = security_service.decrypt_token(
                encrypted_token=user.encrypted_access_token
            )
            await auth_service.revoke_token(token=access_token)
        except Exception:
            pass

    user.encrypted_access_token = None
    user.encrypted_refresh_token = None
    user.token_expiry = None
    await user_repo.save(user=user)

    return MessageResponse(message="Logged out successfully")
