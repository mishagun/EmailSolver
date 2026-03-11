import contextlib

from textual import work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Input,
    Label,
    Static,
    Switch,
)

from tui.client import ApiError
from tui.models import AnalysisCreateRequest, AnalysisResponse, AnalysisType
from tui.screens import AppScreen


class DashboardScreen(AppScreen):
    BINDINGS = [
        ("n", "focus_new", "New"),
        ("r", "refresh", "Refresh"),
        ("l", "logout", "Logout"),
        ("q", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="dashboard"):
            with Horizontal(id="stats-panel"):
                yield Label("", id="user-email")
                yield Label("unread: --", id="unread-count")
                yield Label("total: --", id="total-count")
            yield DataTable(id="analyses-table")
            with Vertical(id="new-analysis-form"):
                yield Static("New Analysis", classes="section-title")
                with Horizontal(classes="form-row"):
                    yield Label("Unread Only:", classes="form-label")
                    yield Switch(value=True, id="unread-only-switch")
                with Horizontal(classes="form-row"):
                    yield Label("Max Emails:", classes="form-label")
                    yield Input(
                        value="100",
                        id="max-emails-input",
                        classes="form-input",
                    )
                with Horizontal(classes="form-row"):
                    yield Label("Auto-Apply:", classes="form-label")
                    yield Switch(value=False, id="auto-apply-switch")
                with Horizontal(classes="form-row", id="categories-row"):
                    yield Label("Categories:", classes="form-label")
                    yield Input(
                        placeholder="comma-separated (optional)",
                        id="categories-input",
                        classes="form-input",
                    )
                with Horizontal(classes="form-row"):
                    yield Button(
                        "Start Inbox Scan", id="start-inbox-scan", variant="default"
                    )
                    yield Button(
                        "Start AI Analysis", id="start-ai-analysis", variant="default"
                    )
            yield Label("", id="dashboard-status")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#analyses-table", DataTable)
        table.add_columns("ID", "Type", "Status", "Filter", "Progress", "Created")
        table.cursor_type = "row"
        self.load_data()

    def action_focus_new(self) -> None:
        self.query_one("#unread-only-switch", Switch).focus()

    def action_refresh(self) -> None:
        self.load_data()

    def action_logout(self) -> None:
        self.do_logout()

    @work(exclusive=True, group="logout")
    async def do_logout(self) -> None:
        with contextlib.suppress(Exception):
            await self.client.logout()
        self.email_app.clear_saved_token()
        self.email_app.navigate_to_login()

    @work(exclusive=True, group="load")
    async def load_data(self) -> None:
        status_label = self.query_one("#dashboard-status", Label)
        self.query_one("#user-email", Label).update(self.email_app.user_email or "unknown")

        try:
            stats = await self.client.get_email_stats()
            self.query_one("#unread-count", Label).update(
                f"unread: {stats.unread_count}"
            )
            self.query_one("#total-count", Label).update(
                f"total: {stats.total_count}"
            )
        except ApiError as e:
            if e.status_code == 401:
                status_label.update("session expired")
                self.email_app.clear_saved_token()
                self.email_app.navigate_to_login()
                return
            status_label.update(f"error: {e.detail}")
        except Exception as e:
            status_label.update(f"connection error: {e}")

        try:
            analyses = await self.client.list_analyses()
            table = self.query_one("#analyses-table", DataTable)
            table.clear()
            for a in analyses.analyses:
                progress = self._format_progress(analysis=a)
                created = a.created_at.strftime("%Y-%m-%d %H:%M")
                type_label = "scan" if a.analysis_type == AnalysisType.INBOX_SCAN else "ai"
                filter_label = "unread" if a.unread_only else "all"
                table.add_row(
                    str(a.id),
                    type_label,
                    a.status,
                    filter_label,
                    progress,
                    created,
                    key=str(a.id),
                )
        except ApiError as e:
            status_label.update(f"error: {e.detail}")
        except Exception as e:
            status_label.update(f"connection error: {e}")

    def _format_progress(self, *, analysis: AnalysisResponse) -> str:
        if analysis.status == "completed":
            return f"{analysis.total_emails or 0} emails"
        if analysis.total_emails:
            return f"{analysis.processed_emails or 0}/{analysis.total_emails}"
        return "--"

    def on_data_table_row_selected(
        self, event: DataTable.RowSelected
    ) -> None:
        row_key = event.row_key
        if row_key and row_key.value:
            analysis_id = int(row_key.value)
            self.email_app.push_analysis_screen(analysis_id=analysis_id)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "start-inbox-scan":
            self.start_analysis(analysis_type=AnalysisType.INBOX_SCAN)
        elif event.button.id == "start-ai-analysis":
            self.start_analysis(analysis_type=AnalysisType.AI_ANALYSIS)

    @work(exclusive=True, group="create")
    async def start_analysis(self, analysis_type: str = AnalysisType.AI_ANALYSIS) -> None:
        status_label = self.query_one("#dashboard-status", Label)
        unread_only = self.query_one("#unread-only-switch", Switch).value
        max_emails_str = self.query_one(
            "#max-emails-input", Input
        ).value.strip()
        auto_apply = self.query_one("#auto-apply-switch", Switch).value

        try:
            max_emails = int(max_emails_str)
        except ValueError:
            status_label.update("max emails must be a number")
            return

        custom_categories: list[str] | None = None
        if analysis_type == AnalysisType.AI_ANALYSIS:
            categories_str = self.query_one(
                "#categories-input", Input
            ).value.strip()
            if categories_str:
                custom_categories = [
                    c.strip() for c in categories_str.split(",") if c.strip()
                ]

        request = AnalysisCreateRequest(
            analysis_type=analysis_type,
            unread_only=unread_only,
            max_emails=max_emails,
            auto_apply=auto_apply,
            custom_categories=custom_categories,
        )

        try:
            status_label.update("creating analysis...")
            analysis = await self.client.create_analysis(request=request)
            status_label.update(f"analysis #{analysis.id} created")
            self.email_app.push_analysis_screen(analysis_id=analysis.id)
        except ApiError as e:
            status_label.update(f"error: {e.detail}")
        except Exception as e:
            status_label.update(f"connection error: {e}")
