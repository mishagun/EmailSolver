import stat
from datetime import UTC, datetime
from pathlib import Path
from typing import ClassVar
from unittest.mock import AsyncMock, MagicMock, patch

from tui.app import TidyInboxApp
from tui.client import ApiError
from tui.config import TuiConfig
from tui.models import (
    AnalysisListResponse,
    AnalysisResponse,
    AuthStatusResponse,
    CategorySummary,
    ClassifiedEmailResponse,
    EmailStatsResponse,
    MessageResponse,
)
from tui.screens.analysis import AnalysisScreen
from tui.screens.dashboard import DashboardScreen
from tui.screens.email_detail import EmailDetailScreen
from tui.screens.login import LoginScreen, _CallbackHandler


def _make_config(tmp_path: Path) -> TuiConfig:
    return TuiConfig(
        base_url="http://test:8000",
        token_path=tmp_path / "token",
        poll_interval_seconds=100.0,
    )


class _NoAuthApp(TidyInboxApp):
    CSS_PATH: ClassVar[list[str]] = []

    def check_auth(self) -> None:  # type: ignore[override]
        pass


def _mock_server(*, token: str | None = None) -> MagicMock:
    mock = MagicMock()
    mock.server_address = ("localhost", 54321)
    mock.server_close.return_value = None
    mock.timeout = None

    def fake_handle_request() -> None:
        _CallbackHandler.token = token

    mock.handle_request.side_effect = fake_handle_request
    return mock


class TestLoginScreen:
    async def test_login_screen_renders(self, tmp_path: Path) -> None:
        app = _NoAuthApp(config=_make_config(tmp_path))
        async with app.run_test():
            await app.push_screen(LoginScreen())
            assert app.screen.query_one("#login-title")
            assert app.screen.query_one("#submit-token")
            assert app.screen.query_one("#login-error")

    @patch("tui.screens.login.webbrowser.open")
    @patch("tui.screens.login.HTTPServer")
    async def test_oauth_opens_browser_with_callback_port(
        self, mock_server_cls: MagicMock, mock_wb: MagicMock, tmp_path: Path
    ) -> None:
        mock_server_cls.return_value = _mock_server()

        app = _NoAuthApp(config=_make_config(tmp_path))
        async with app.run_test() as pilot:
            await app.push_screen(LoginScreen())
            await pilot.click("#submit-token")
            await pilot.pause()
            await pilot.pause()
            await pilot.pause()

        mock_wb.assert_called_once()
        call_url = mock_wb.call_args[0][0]
        assert "callback_port=54321" in call_url

    @patch("tui.screens.login.webbrowser.open")
    @patch("tui.screens.login.HTTPServer")
    async def test_valid_token_saves_and_navigates(
        self, mock_server_cls: MagicMock, _wb: MagicMock, tmp_path: Path
    ) -> None:
        mock_server_cls.return_value = _mock_server(token="valid-jwt")

        app = _NoAuthApp(config=_make_config(tmp_path))
        async with app.run_test() as pilot:
            await app.push_screen(LoginScreen())

            with patch.object(
                app.client,
                "get_auth_status",
                new_callable=AsyncMock,
                return_value=AuthStatusResponse(
                    authenticated=True, email="user@test.com"
                ),
            ):
                await pilot.click("#submit-token")
                await pilot.pause()
                await pilot.pause()
                await pilot.pause()

            assert (tmp_path / "token").read_text() == "valid-jwt"

    @patch("tui.screens.login.webbrowser.open")
    @patch("tui.screens.login.HTTPServer")
    async def test_failed_auth_shows_error(
        self, mock_server_cls: MagicMock, _wb: MagicMock, tmp_path: Path
    ) -> None:
        mock_server_cls.return_value = _mock_server(token="bad-jwt")

        app = _NoAuthApp(config=_make_config(tmp_path))
        async with app.run_test() as pilot:
            await app.push_screen(LoginScreen())

            with patch.object(
                app.client,
                "get_auth_status",
                new_callable=AsyncMock,
                side_effect=ApiError(status_code=401, detail="Invalid token"),
            ):
                await pilot.click("#submit-token")
                await pilot.pause()
                await pilot.pause()
                await pilot.pause()

            error = app.screen.query_one("#login-error")
            assert "Invalid token" in str(error.content)


class TestDashboardScreen:
    async def test_dashboard_renders_with_stats(
        self, tmp_path: Path
    ) -> None:
        app = _NoAuthApp(config=_make_config(tmp_path))
        async with app.run_test() as pilot:
            with (
                patch.object(
                    app.client,
                    "get_auth_status",
                    new_callable=AsyncMock,
                    return_value=AuthStatusResponse(
                        authenticated=True, email="user@test.com"
                    ),
                ),
                patch.object(
                    app.client,
                    "get_email_stats",
                    new_callable=AsyncMock,
                    return_value=EmailStatsResponse(
                        unread_count=42, total_count=1500
                    ),
                ),
                patch.object(
                    app.client,
                    "list_analyses",
                    new_callable=AsyncMock,
                    return_value=AnalysisListResponse(
                        analyses=[], total=0
                    ),
                ),
            ):
                await app.push_screen(DashboardScreen())
                await pilot.pause()

                unread = app.screen.query_one("#unread-count")
                assert "42" in str(unread.content)

    async def test_dashboard_analyses_table_populated(
        self, tmp_path: Path
    ) -> None:
        app = _NoAuthApp(config=_make_config(tmp_path))
        async with app.run_test() as pilot:
            with (
                patch.object(
                    app.client,
                    "get_auth_status",
                    new_callable=AsyncMock,
                    return_value=AuthStatusResponse(
                        authenticated=True, email="user@test.com"
                    ),
                ),
                patch.object(
                    app.client,
                    "get_email_stats",
                    new_callable=AsyncMock,
                    return_value=EmailStatsResponse(
                        unread_count=10, total_count=100
                    ),
                ),
                patch.object(
                    app.client,
                    "list_analyses",
                    new_callable=AsyncMock,
                    return_value=AnalysisListResponse(
                        analyses=[
                            AnalysisResponse(
                                id=1,
                                status="completed",
                                unread_only=True,
                                total_emails=50,
                                processed_emails=50,
                                created_at=datetime(
                                    2026, 3, 1, tzinfo=UTC
                                ),
                            ),
                        ],
                        total=1,
                    ),
                ),
            ):
                await app.push_screen(DashboardScreen())
                await pilot.pause()

                from textual.widgets import DataTable

                table = app.screen.query_one("#analyses-table", DataTable)
                assert table.row_count == 1


class TestAnalysisScreen:
    def _completed_analysis(self) -> AnalysisResponse:
        return AnalysisResponse(
            id=1,
            status="completed",
            unread_only=True,
            total_emails=2,
            processed_emails=2,
            created_at=datetime(2026, 3, 1, tzinfo=UTC),
            summary=[
                CategorySummary(
                    category="promotions",
                    count=2,
                    recommended_actions=[
                        "mark_read",
                        "move_to_category",
                    ],
                ),
            ],
            classified_emails=[
                ClassifiedEmailResponse(
                    id=1,
                    gmail_message_id="msg-1",
                    sender="shop@store.com",
                    subject="Sale!",
                    category="promotions",
                    importance=2,
                    sender_type="marketing",
                    confidence=0.95,
                ),
            ],
        )

    async def test_analysis_screen_renders_completed(
        self, tmp_path: Path
    ) -> None:
        app = _NoAuthApp(config=_make_config(tmp_path))
        async with app.run_test() as pilot:
            with patch.object(
                app.client,
                "get_analysis",
                new_callable=AsyncMock,
                return_value=self._completed_analysis(),
            ):
                await app.push_screen(AnalysisScreen(analysis_id=1))
                await pilot.pause()

                status_label = app.screen.query_one("#analysis-status")
                assert "completed" in str(status_label.content)

    async def test_analysis_screen_hides_progress_when_completed(
        self, tmp_path: Path
    ) -> None:
        app = _NoAuthApp(config=_make_config(tmp_path))
        async with app.run_test() as pilot:
            with patch.object(
                app.client,
                "get_analysis",
                new_callable=AsyncMock,
                return_value=self._completed_analysis(),
            ):
                await app.push_screen(AnalysisScreen(analysis_id=1))
                await pilot.pause()

                from textual.widgets import ProgressBar

                progress = app.screen.query_one(
                    "#analysis-progress", ProgressBar
                )
                assert progress.display is False

    async def test_analysis_screen_shows_progress_when_processing(
        self, tmp_path: Path
    ) -> None:
        processing = AnalysisResponse(
            id=1,
            status="processing",
            unread_only=True,
            total_emails=100,
            processed_emails=40,
            created_at=datetime(2026, 3, 1, tzinfo=UTC),
        )
        app = _NoAuthApp(config=_make_config(tmp_path))
        async with app.run_test() as pilot:
            with patch.object(
                app.client,
                "get_analysis",
                new_callable=AsyncMock,
                return_value=processing,
            ):
                await app.push_screen(AnalysisScreen(analysis_id=1))
                await pilot.pause()

                progress_label = app.screen.query_one("#progress-label")
                assert "40" in str(progress_label.content)
                assert "100" in str(progress_label.content)

    async def test_analysis_screen_populates_summary_table(
        self, tmp_path: Path
    ) -> None:
        app = _NoAuthApp(config=_make_config(tmp_path))
        async with app.run_test() as pilot:
            with patch.object(
                app.client,
                "get_analysis",
                new_callable=AsyncMock,
                return_value=self._completed_analysis(),
            ):
                await app.push_screen(AnalysisScreen(analysis_id=1))
                await pilot.pause()

                from textual.widgets import DataTable

                summary = app.screen.query_one("#summary-table", DataTable)
                assert summary.row_count == 1

    async def test_apply_action_calls_client(
        self, tmp_path: Path
    ) -> None:
        app = _NoAuthApp(config=_make_config(tmp_path))
        async with app.run_test() as pilot:
            mock_apply = AsyncMock(
                return_value=MessageResponse(
                    message="Actions applied successfully"
                )
            )
            with (
                patch.object(
                    app.client,
                    "get_analysis",
                    new_callable=AsyncMock,
                    return_value=self._completed_analysis(),
                ),
                patch.object(app.client, "apply_actions", mock_apply),
            ):
                await app.push_screen(AnalysisScreen(analysis_id=1))
                await pilot.pause()

                screen = app.screen
                screen.action_mark_read()
                await pilot.pause()
                await pilot.pause()

                mock_apply.assert_called_once()
                call_kwargs = mock_apply.call_args
                assert call_kwargs.kwargs["analysis_id"] == 1
                assert (
                    call_kwargs.kwargs["request"].action.value
                    == "mark_read"
                )


class TestEmailDetailScreen:
    async def test_email_detail_renders(self, tmp_path: Path) -> None:
        email = ClassifiedEmailResponse(
            id=1,
            gmail_message_id="msg-1",
            sender="shop@store.com",
            sender_domain="store.com",
            subject="Big Sale!",
            snippet="Don't miss out...",
            category="promotions",
            importance=3,
            sender_type="marketing",
            confidence=0.92,
            has_unsubscribe=True,
            action_taken="mark_read",
        )
        app = _NoAuthApp(config=_make_config(tmp_path))
        async with app.run_test() as pilot:
            await app.push_screen(EmailDetailScreen(email=email, analysis_id=1))
            await pilot.pause()

            detail = app.screen.query_one("#email-detail")
            assert detail is not None
            title = app.screen.query_one("#detail-title")
            assert "Email Details" in str(title.content)


class TestAppTokenPersistence:
    async def test_save_and_load_token(self, tmp_path: Path) -> None:
        config = _make_config(tmp_path)
        app = TidyInboxApp(config=config)
        app.save_token(token="test-jwt-token")

        assert (tmp_path / "token").read_text() == "test-jwt-token"
        assert app.client.is_authenticated is True

    async def test_clear_saved_token(self, tmp_path: Path) -> None:
        config = _make_config(tmp_path)
        app = TidyInboxApp(config=config)
        app.save_token(token="test-jwt-token")
        app.clear_saved_token()

        assert not (tmp_path / "token").exists()
        assert app.client.is_authenticated is False

    async def test_load_token_file_missing(self, tmp_path: Path) -> None:
        config = _make_config(tmp_path)
        app = TidyInboxApp(config=config)
        result = app._load_token()
        assert result is None

    async def test_load_token_file_empty(self, tmp_path: Path) -> None:
        config = _make_config(tmp_path)
        (tmp_path / "token").write_text("")
        app = TidyInboxApp(config=config)
        result = app._load_token()
        assert result is None

    async def test_load_token_file_with_whitespace(
        self, tmp_path: Path
    ) -> None:
        config = _make_config(tmp_path)
        (tmp_path / "token").write_text("  jwt-token  \n")
        app = TidyInboxApp(config=config)
        result = app._load_token()
        assert result == "jwt-token"

    async def test_save_token_sets_owner_only_permissions(self, tmp_path: Path) -> None:
        config = _make_config(tmp_path)
        app = TidyInboxApp(config=config)
        app.save_token(token="test-jwt-token")

        token_file = tmp_path / "token"
        file_mode = token_file.stat().st_mode & 0o777
        assert file_mode == stat.S_IRUSR | stat.S_IWUSR
