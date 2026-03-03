from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import httpx
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

from app.core.protocols import BaseAuthService

STATE_SEPARATOR = "|"


class GoogleAuthService(BaseAuthService):
    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        scopes: list[str],
        auth_uri: str,
        token_uri: str,
        revoke_url: str,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._redirect_uri = redirect_uri
        self._scopes = scopes
        self._auth_uri = auth_uri
        self._token_uri = token_uri
        self._revoke_url = revoke_url

    def _build_flow(self) -> Flow:
        return Flow.from_client_config(
            client_config={
                "web": {
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                    "auth_uri": self._auth_uri,
                    "token_uri": self._token_uri,
                }
            },
            scopes=self._scopes,
            redirect_uri=self._redirect_uri,
        )

    def start_authorization(self) -> str:
        flow = self._build_flow()
        auth_url, state = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
        )
        combined_state = f"{state}{STATE_SEPARATOR}{flow.code_verifier}"
        parsed = urlparse(auth_url)
        params = parse_qs(parsed.query, keep_blank_values=True)
        params["state"] = [combined_state]
        return urlunparse(parsed._replace(query=urlencode(params, doseq=True)))

    def exchange_code(self, *, code: str, state: str) -> Credentials:
        _, code_verifier = state.split(STATE_SEPARATOR, maxsplit=1)
        flow = self._build_flow()
        flow.fetch_token(code=code, code_verifier=code_verifier)
        return flow.credentials

    def get_user_info(self, *, credentials: Credentials) -> dict:
        oauth2_service = build("oauth2", "v2", credentials=credentials)
        return oauth2_service.userinfo().get().execute()

    async def revoke_token(self, *, token: str) -> None:
        async with httpx.AsyncClient() as client:
            await client.post(
                self._revoke_url,
                params={"token": token},
            )
