import httpx

from tui.models import (
    AnalysisCreateRequest,
    AnalysisListResponse,
    AnalysisResponse,
    ApplyActionsRequest,
    AuthStatusResponse,
    EmailListResponse,
    EmailStatsResponse,
    MessageResponse,
    SenderGroupSummary,
)


class ApiError(Exception):
    def __init__(self, *, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"[{status_code}] {detail}")


class EmailSolverClient:
    def __init__(self, *, base_url: str) -> None:
        self._base_url = base_url
        self._token: str | None = None
        self._client = httpx.AsyncClient(base_url=base_url, timeout=30.0)

    @property
    def is_authenticated(self) -> bool:
        return self._token is not None

    def set_token(self, *, token: str) -> None:
        self._token = token
        self._client.headers["Authorization"] = f"Bearer {token}"

    def clear_token(self) -> None:
        self._token = None
        self._client.headers.pop("Authorization", None)

    def get_login_url(self, *, callback_port: int | None = None) -> str:
        url = f"{self._base_url}/api/v1/auth/login"
        if callback_port:
            url += f"?callback_port={callback_port}"
        return url

    async def _request(
        self,
        *,
        method: str,
        path: str,
        json: dict | None = None,
        params: dict | None = None,
    ) -> httpx.Response:
        response = await self._client.request(
            method=method,
            url=path,
            json=json,
            params=params,
        )
        if response.status_code >= 400:
            try:
                detail = response.json().get("detail", response.text)
            except Exception:
                detail = response.text
            raise ApiError(status_code=response.status_code, detail=str(detail))
        return response

    async def get_auth_status(self) -> AuthStatusResponse:
        resp = await self._request(method="GET", path="/api/v1/auth/status")
        return AuthStatusResponse.model_validate(resp.json())

    async def logout(self) -> MessageResponse:
        resp = await self._request(method="DELETE", path="/api/v1/auth/logout")
        return MessageResponse.model_validate(resp.json())

    async def list_emails(
        self, *, query: str = "is:unread", max_results: int = 500
    ) -> EmailListResponse:
        resp = await self._request(
            method="GET",
            path="/api/v1/emails",
            params={"query": query, "max_results": max_results},
        )
        return EmailListResponse.model_validate(resp.json())

    async def get_email_stats(self) -> EmailStatsResponse:
        resp = await self._request(method="GET", path="/api/v1/emails/stats")
        return EmailStatsResponse.model_validate(resp.json())

    async def create_analysis(self, *, request: AnalysisCreateRequest) -> AnalysisResponse:
        resp = await self._request(
            method="POST",
            path="/api/v1/analysis",
            json=request.model_dump(exclude_none=True),
        )
        return AnalysisResponse.model_validate(resp.json())

    async def list_analyses(self) -> AnalysisListResponse:
        resp = await self._request(method="GET", path="/api/v1/analysis")
        return AnalysisListResponse.model_validate(resp.json())

    async def get_analysis(self, *, analysis_id: int) -> AnalysisResponse:
        resp = await self._request(method="GET", path=f"/api/v1/analysis/{analysis_id}")
        return AnalysisResponse.model_validate(resp.json())

    async def apply_actions(
        self, *, analysis_id: int, request: ApplyActionsRequest
    ) -> MessageResponse:
        resp = await self._request(
            method="POST",
            path=f"/api/v1/analysis/{analysis_id}/apply",
            json=request.model_dump(exclude_none=True),
        )
        return MessageResponse.model_validate(resp.json())

    async def get_sender_groups(
        self, *, analysis_id: int, category: str
    ) -> list[SenderGroupSummary]:
        resp = await self._request(
            method="GET",
            path=f"/api/v1/analysis/{analysis_id}/senders",
            params={"category": category},
        )
        return [SenderGroupSummary.model_validate(item) for item in resp.json()]

    async def delete_analysis(self, *, analysis_id: int) -> MessageResponse:
        resp = await self._request(method="DELETE", path=f"/api/v1/analysis/{analysis_id}")
        return MessageResponse.model_validate(resp.json())

    async def close(self) -> None:
        await self._client.aclose()
