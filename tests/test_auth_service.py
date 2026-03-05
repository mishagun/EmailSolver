import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from app.services.auth_service import GoogleAuthService


@pytest.fixture
def auth_service() -> GoogleAuthService:
    return GoogleAuthService(
        client_id="test-id",
        client_secret="test-secret",
        redirect_uri="http://localhost/callback",
        scopes=["openid", "email"],
        auth_uri="https://accounts.google.com/o/oauth2/auth",
        token_uri="https://oauth2.googleapis.com/token",
        revoke_url="https://oauth2.googleapis.com/revoke",
    )


def _make_flow_mock(*, state: str, code_verifier: str) -> MagicMock:
    flow = MagicMock()
    flow.authorization_url.return_value = (f"https://accounts.google.com/auth?state={state}", state)
    flow.code_verifier = code_verifier
    return flow


class TestStartAuthorization:
    def test_start_authorization_stores_state(self, auth_service: GoogleAuthService) -> None:
        flow_mock = _make_flow_mock(state="nonce123", code_verifier="verifier-abc")

        with patch.object(auth_service, "_build_flow", return_value=flow_mock):
            url = auth_service.start_authorization()

        assert "nonce123" in auth_service._state_store
        verifier, expires_at = auth_service._state_store["nonce123"]
        assert verifier == "verifier-abc"
        assert expires_at > time.monotonic()
        assert "nonce123" in url

    def test_start_authorization_sets_ttl(self, auth_service: GoogleAuthService) -> None:
        flow_mock = _make_flow_mock(state="nonce-ttl", code_verifier="verifier-ttl")

        before = time.monotonic()
        with patch.object(auth_service, "_build_flow", return_value=flow_mock):
            auth_service.start_authorization()
        after = time.monotonic()

        _, expires_at = auth_service._state_store["nonce-ttl"]
        assert before + 600 <= expires_at <= after + 600


class TestExchangeCode:
    def test_exchange_code_consumes_state(self, auth_service: GoogleAuthService) -> None:
        future = time.monotonic() + 600
        auth_service._state_store["nonce123"] = ("verifier-abc", future)

        flow_mock = MagicMock()
        flow_mock.fetch_token.return_value = None
        flow_mock.credentials = MagicMock()

        with patch.object(auth_service, "_build_flow", return_value=flow_mock):
            auth_service.exchange_code(code="auth-code", state="nonce123")

        assert "nonce123" not in auth_service._state_store

    def test_exchange_code_rejects_unknown_state(self, auth_service: GoogleAuthService) -> None:
        with pytest.raises(ValueError, match="Invalid or expired OAuth state"):
            auth_service.exchange_code(code="auth-code", state="unknown-nonce")

    def test_exchange_code_rejects_replayed_state(self, auth_service: GoogleAuthService) -> None:
        future = time.monotonic() + 600
        auth_service._state_store["nonce123"] = ("verifier-abc", future)

        flow_mock = MagicMock()
        flow_mock.fetch_token.return_value = None
        flow_mock.credentials = MagicMock()

        with patch.object(auth_service, "_build_flow", return_value=flow_mock):
            auth_service.exchange_code(code="auth-code", state="nonce123")

        with pytest.raises(ValueError, match="Invalid or expired OAuth state"):
            with patch.object(auth_service, "_build_flow", return_value=flow_mock):
                auth_service.exchange_code(code="auth-code", state="nonce123")

    def test_exchange_code_passes_verifier_to_flow(self, auth_service: GoogleAuthService) -> None:
        future = time.monotonic() + 600
        auth_service._state_store["nonce-verify"] = ("expected-verifier", future)

        flow_mock = MagicMock()
        flow_mock.credentials = MagicMock()

        with patch.object(auth_service, "_build_flow", return_value=flow_mock):
            auth_service.exchange_code(code="the-code", state="nonce-verify")

        flow_mock.fetch_token.assert_called_once_with(
            code="the-code", code_verifier="expected-verifier"
        )


class TestCleanupExpired:
    def test_expired_state_cleaned_up_on_start_authorization(
        self, auth_service: GoogleAuthService
    ) -> None:
        auth_service._state_store["old-nonce"] = ("old-verifier", time.monotonic() - 1)

        flow_mock = _make_flow_mock(state="new-nonce", code_verifier="new-verifier")
        with patch.object(auth_service, "_build_flow", return_value=flow_mock):
            auth_service.start_authorization()

        assert "old-nonce" not in auth_service._state_store
        assert "new-nonce" in auth_service._state_store

    def test_expired_state_cleaned_up_on_exchange_code(
        self, auth_service: GoogleAuthService
    ) -> None:
        auth_service._state_store["expired-nonce"] = ("verifier", time.monotonic() - 1)
        future = time.monotonic() + 600
        auth_service._state_store["valid-nonce"] = ("valid-verifier", future)

        flow_mock = MagicMock()
        flow_mock.credentials = MagicMock()

        with patch.object(auth_service, "_build_flow", return_value=flow_mock):
            auth_service.exchange_code(code="code", state="valid-nonce")

        assert "expired-nonce" not in auth_service._state_store

    def test_non_expired_state_not_removed(self, auth_service: GoogleAuthService) -> None:
        future = time.monotonic() + 600
        auth_service._state_store["live-nonce"] = ("verifier", future)

        auth_service._cleanup_expired()

        assert "live-nonce" in auth_service._state_store


class TestThreadSafety:
    def test_state_store_is_thread_safe(self, auth_service: GoogleAuthService) -> None:
        counter = [0]
        lock = threading.Lock()
        errors: list[Exception] = []

        def worker(index: int) -> None:
            state = f"nonce-{index}"
            flow_mock = _make_flow_mock(state=state, code_verifier=f"verifier-{index}")
            try:
                with patch.object(auth_service, "_build_flow", return_value=flow_mock):
                    auth_service.start_authorization()
                with lock:
                    counter[0] += 1
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker, kwargs={"index": i}) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert counter[0] == 10
        assert len(auth_service._state_store) == 10
