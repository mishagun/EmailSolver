from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import HTMLResponse, RedirectResponse

from app.core import protocols
from app.core.dependencies import (
    get_auth_service,
    get_current_user,
    get_security_service,
    get_user_repository,
)
from app.models.db import User
from app.models.schemas import AuthStatusResponse, MessageResponse

router = APIRouter()

_CALLBACK_STATE_PREFIX = "cb:"
_ALLOWED_PORT_RANGE = range(1024, 65536)

_SUCCESS_HTML = """<!DOCTYPE html>
<html><body style="font-family:sans-serif;text-align:center;padding:60px">
<h1>Login successful</h1>
<p>You can close this tab and return to your application.</p>
<pre style="margin:20px auto;padding:12px;background:#f5f5f5;border-radius:4px;max-width:600px;
word-break:break-all;text-align:left">{token}</pre>
</body></html>"""


@router.get("/login")
async def login(
    callback_port: int | None = Query(default=None),
    auth_service: protocols.BaseAuthService = Depends(get_auth_service),
) -> RedirectResponse:
    if callback_port is not None and callback_port not in _ALLOWED_PORT_RANGE:
        raise HTTPException(status_code=400, detail="Invalid callback port")
    auth_url = auth_service.start_authorization()
    if callback_port is not None:
        parsed = urlparse(auth_url)
        params = parse_qs(parsed.query, keep_blank_values=True)
        params["state"] = [f"{params['state'][0]}|{_CALLBACK_STATE_PREFIX}{callback_port}"]
        auth_url = urlunparse(parsed._replace(query=urlencode(params, doseq=True)))
    return RedirectResponse(url=auth_url)


@router.get("/callback")
async def callback(
    code: str,
    state: str,
    auth_service: protocols.BaseAuthService = Depends(get_auth_service),
    security_service: protocols.BaseSecurityService = Depends(get_security_service),
    user_repo: protocols.BaseUserRepository = Depends(get_user_repository),
) -> RedirectResponse:
    callback_port: int | None = None
    if f"|{_CALLBACK_STATE_PREFIX}" in state:
        state, cb_part = state.rsplit("|", 1)
        callback_port = int(cb_part[len(_CALLBACK_STATE_PREFIX):])

    if callback_port is not None and callback_port not in _ALLOWED_PORT_RANGE:
        raise HTTPException(status_code=400, detail="Invalid callback port")

    try:
        credentials = auth_service.exchange_code(code=code, state=state)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

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

    if callback_port is not None:
        return RedirectResponse(
            url=f"http://localhost:{callback_port}/callback?token={jwt_token}"
        )
    return RedirectResponse(url=f"/api/v1/auth/success?token={jwt_token}")


@router.get("/success", response_class=HTMLResponse)
async def auth_success(token: str) -> HTMLResponse:
    return HTMLResponse(content=_SUCCESS_HTML.format(token=token))


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
