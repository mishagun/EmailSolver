from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.timer import Timer
from textual.widgets import (
    DataTable,
    Footer,
    Label,
    ProgressBar,
    Static,
    TabbedContent,
    TabPane,
)

from tui.client import ApiError
from tui.models import (
    ActionType,
    AnalysisResponse,
    AnalysisType,
    ApplyActionsRequest,
    SenderGroupSummary,
)
from tui.screens import AppScreen
from tui.screens.email_detail import EmailDetailScreen


class AnalysisScreen(AppScreen):
    BINDINGS = [
        Binding("escape", "go_back", "Back", priority=True),
        Binding("tab", "switch_tab", "Tab", priority=True),
        Binding("r", "refresh", "Refresh"),
        Binding("d", "delete", "Delete"),
        Binding("a", "show_all", "All"),
        Binding("g", "senders", "Senders"),
        Binding("k", "keep", "Keep"),
        Binding("m", "mark_read", "Read"),
        Binding("v", "move", "Move"),
        Binding("s", "spam", "Spam"),
        Binding("u", "unsubscribe", "Unsub"),
        Binding("space", "toggle_select", "Select", show=False),
        Binding("x", "clear_selection", "Clear", show=False),
    ]

    def __init__(self, *, analysis_id: int) -> None:
        super().__init__()
        self.analysis_id = analysis_id
        self._analysis: AnalysisResponse | None = None
        self._poll_timer: Timer | None = None
        self._selected_category: str | None = None
        self._email_filter: str | None = None
        self._selected_sender_domain: str | None = None
        self._sender_groups: list[SenderGroupSummary] = []
        self._selected_email_ids: set[int] = set()
        self._sel_col_key: str | None = None

    def compose(self) -> ComposeResult:
        with Vertical(id="analysis-view"):
            with Horizontal(id="analysis-header"):
                yield Static(f"#{self.analysis_id}", id="analysis-title")
                yield Label("loading...", id="analysis-status")
                yield Label("", id="analysis-query")
                yield Label("", id="analysis-user")
            yield ProgressBar(total=100, show_eta=False, id="analysis-progress")
            yield Label("", id="progress-label")
            with TabbedContent(id="analysis-tabs"):
                with TabPane("Summary", id="tab-summary"):
                    yield DataTable(id="summary-table")
                with TabPane("Emails", id="tab-emails"):
                    yield Label("", id="emails-filter-label")
                    yield DataTable(id="emails-table")
                with TabPane("Senders", id="tab-senders"):
                    yield Label("", id="senders-filter-label")
                    yield DataTable(id="senders-table")
            yield Label("", id="analysis-message")
            yield Static("", id="action-scope-bar")
        yield Footer()

    def on_mount(self) -> None:
        summary_table = self.query_one("#summary-table", DataTable)
        summary_table.add_columns("Category", "Count", "Recommended Actions")
        summary_table.cursor_type = "row"

        emails_table = self.query_one("#emails-table", DataTable)
        col_keys = emails_table.add_columns(
            " ", "Sender", "Subject", "Category", "Priority", "Action"
        )
        self._sel_col_key = col_keys[0]
        emails_table.cursor_type = "row"

        senders_table = self.query_one("#senders-table", DataTable)
        senders_table.add_columns("Domain", "Sender", "Count", "Unsub?")
        senders_table.cursor_type = "row"

        self.query_one("#analysis-user", Label).update(self.email_app.user_email)
        self.load_analysis()
        summary_table.focus()

    def on_tabbed_content_tab_activated(
        self, event: TabbedContent.TabActivated
    ) -> None:
        if event.pane.id == "tab-summary":
            self.query_one("#summary-table", DataTable).focus()
        elif event.pane.id == "tab-emails":
            self.query_one("#emails-table", DataTable).focus()
        elif event.pane.id == "tab-senders":
            self._load_sender_groups()
            self.query_one("#senders-table", DataTable).focus()
        self._update_scope_bar()

    def _update_scope_bar(self) -> None:
        bar = self.query_one("#action-scope-bar", Static)
        tabs = self.query_one("#analysis-tabs", TabbedContent)
        if tabs.active == "tab-summary":
            cat = self._selected_category or "all"
            bar.update(f"actions apply to: category [{cat}]")
        elif tabs.active == "tab-emails":
            n = len(self._selected_email_ids)
            if n:
                bar.update(
                    f"actions apply to: {n} selected  [Space] toggle  [x] clear"
                )
            else:
                bar.update(
                    "actions apply to: highlighted email  [Space] to select multiple"
                )
        elif tabs.active == "tab-senders":
            domain = self._selected_sender_domain or "all"
            bar.update(f"actions apply to: sender [{domain}]")

    def _start_polling(self) -> None:
        if self._poll_timer is None:
            interval = self.tui_config.poll_interval_seconds
            self._poll_timer = self.set_interval(interval=interval, callback=self._poll)

    def _stop_polling(self) -> None:
        if self._poll_timer is not None:
            self._poll_timer.stop()
            self._poll_timer = None

    def on_unmount(self) -> None:
        self._stop_polling()

    @work(exclusive=True, group="poll")
    async def _poll(self) -> None:
        await self._fetch_and_update()

    @work(exclusive=True, group="load")
    async def load_analysis(self) -> None:
        await self._fetch_and_update()

    async def _fetch_and_update(self) -> None:
        msg_label = self.query_one("#analysis-message", Label)
        try:
            self._analysis = await self.client.get_analysis(
                analysis_id=self.analysis_id
            )
            self._update_display()
        except ApiError as e:
            msg_label.update(f"Error: {e.detail}")
            self._stop_polling()
        except Exception as e:
            msg_label.update(f"Connection error: {e}")
            self._stop_polling()

    def _update_display(self) -> None:
        if self._analysis is None:
            return

        a = self._analysis
        self.query_one("#analysis-status", Label).update(a.status)
        self.query_one("#analysis-query", Label).update(a.query or "")

        progress_bar = self.query_one("#analysis-progress", ProgressBar)
        progress_label = self.query_one("#progress-label", Label)

        if a.status in ("pending", "processing"):
            progress_bar.display = True
            progress_label.display = True
            if a.total_emails and a.total_emails > 0:
                progress_bar.update(total=a.total_emails, progress=a.processed_emails or 0)
                progress_label.update(
                    f"{a.processed_emails or 0}/{a.total_emails} classified"
                )
            else:
                progress_bar.update(total=100, progress=0)
                progress_label.update("waiting...")
            self._start_polling()
        else:
            progress_bar.display = False
            progress_label.display = False
            self._stop_polling()

        if a.summary:
            summary_table = self.query_one("#summary-table", DataTable)
            summary_table.clear()
            for cat in a.summary:
                actions_str = ", ".join(cat.recommended_actions)
                summary_table.add_row(
                    cat.category,
                    str(cat.count),
                    actions_str,
                    key=cat.category,
                )

        self._update_emails_table()

    def _update_emails_table(self) -> None:
        if self._analysis is None or not self._analysis.classified_emails:
            return

        emails_table = self.query_one("#emails-table", DataTable)
        filter_label = self.query_one("#emails-filter-label", Label)
        emails_table.clear()
        self._selected_email_ids.clear()

        emails = self._analysis.classified_emails
        if self._email_filter:
            emails = [e for e in emails if e.category == self._email_filter]
        if self._selected_sender_domain:
            emails = [e for e in emails if e.sender_domain == self._selected_sender_domain]

        filter_parts: list[str] = []
        if self._email_filter:
            filter_parts.append(self._email_filter)
        if self._selected_sender_domain:
            filter_parts.append(f"sender: {self._selected_sender_domain}")
        filter_text = " > ".join(filter_parts) if filter_parts else "all"
        filter_label.update(f"showing: {filter_text} ({len(emails)} emails)")

        is_inbox_scan = (
            self._analysis is not None
            and self._analysis.analysis_type == AnalysisType.INBOX_SCAN
        )
        for email in emails:
            priority = "--" if is_inbox_scan else str(email.importance or 0)
            emails_table.add_row(
                " ",
                (email.sender or "")[:25],
                (email.subject or "")[:40],
                email.category or "",
                priority,
                email.action_taken or "--",
                key=str(email.id),
            )

        self._update_scope_bar()

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if event.data_table.id == "summary-table" and event.row_key and event.row_key.value:
            self._selected_category = event.row_key.value
            self._update_scope_bar()
        elif event.data_table.id == "senders-table" and event.row_key and event.row_key.value:
            self._selected_sender_domain = event.row_key.value
            self._update_scope_bar()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.data_table.id == "summary-table" and event.row_key and event.row_key.value:
            self._email_filter = event.row_key.value
            self._update_emails_table()
            self.query_one("#analysis-tabs", TabbedContent).active = "tab-emails"
        elif event.data_table.id == "senders-table" and event.row_key and event.row_key.value:
            self._selected_sender_domain = event.row_key.value
            self._update_emails_table()
            self.query_one("#analysis-tabs", TabbedContent).active = "tab-emails"
        elif event.data_table.id == "emails-table" and event.row_key and event.row_key.value:
            email_id = int(event.row_key.value)
            if self._analysis and self._analysis.classified_emails:
                email = next(
                    (e for e in self._analysis.classified_emails if e.id == email_id),
                    None,
                )
                if email:
                    self.app.push_screen(
                        EmailDetailScreen(
                            email=email, analysis_id=self.analysis_id
                        ),
                        callback=self._on_email_detail_dismiss,
                    )

    def _on_email_detail_dismiss(self, _result: None) -> None:
        self._update_emails_table()

    def action_switch_tab(self) -> None:
        tabs = self.query_one("#analysis-tabs", TabbedContent)
        if tabs.active == "tab-summary":
            tabs.active = "tab-emails"
        elif tabs.active == "tab-emails":
            tabs.active = "tab-senders"
        else:
            tabs.active = "tab-summary"

    def action_show_all(self) -> None:
        self._email_filter = None
        self._selected_sender_domain = None
        self._update_emails_table()

    def action_toggle_select(self) -> None:
        tabs = self.query_one("#analysis-tabs", TabbedContent)
        if tabs.active != "tab-emails":
            return
        table = self.query_one("#emails-table", DataTable)
        if table.row_count == 0:
            return
        row_key = table.get_row_at(table.cursor_row)
        if row_key is None:
            return
        email_id = int(row_key.value)
        if email_id in self._selected_email_ids:
            self._selected_email_ids.discard(email_id)
            table.update_cell(row_key, self._sel_col_key, " ")
        else:
            self._selected_email_ids.add(email_id)
            table.update_cell(row_key, self._sel_col_key, ">")
        self._update_scope_bar()

    def action_clear_selection(self) -> None:
        if not self._selected_email_ids:
            return
        table = self.query_one("#emails-table", DataTable)
        for row_key in table.rows:
            table.update_cell(row_key, self._sel_col_key, " ")
        self._selected_email_ids.clear()
        self._update_scope_bar()

    def _get_target_email_ids(self) -> list[int]:
        if self._selected_email_ids:
            return list(self._selected_email_ids)
        table = self.query_one("#emails-table", DataTable)
        if table.row_count == 0:
            return []
        row_key = table.get_row_at(table.cursor_row)
        if row_key and row_key.value:
            return [int(row_key.value)]
        return []

    def action_keep(self) -> None:
        self.apply_action(action=ActionType.KEEP)

    def action_mark_read(self) -> None:
        self.apply_action(action=ActionType.MARK_READ)

    def action_move(self) -> None:
        self.apply_action(action=ActionType.MOVE_TO_CATEGORY)

    def action_spam(self) -> None:
        self.apply_action(action=ActionType.MARK_SPAM)

    def action_unsubscribe(self) -> None:
        self.apply_action(action=ActionType.UNSUBSCRIBE)

    def action_senders(self) -> None:
        self._load_sender_groups()
        self.query_one("#analysis-tabs", TabbedContent).active = "tab-senders"

    @work(exclusive=True, group="senders")
    async def _load_sender_groups(self) -> None:
        msg_label = self.query_one("#analysis-message", Label)
        try:
            self._sender_groups = await self.client.get_sender_groups(
                analysis_id=self.analysis_id,
                category=self._email_filter,
            )
            self._update_senders_table()
        except Exception as e:
            msg_label.update(f"error loading senders: {e}")

    def _update_senders_table(self) -> None:
        senders_table = self.query_one("#senders-table", DataTable)
        filter_label = self.query_one("#senders-filter-label", Label)
        senders_table.clear()

        scope = self._email_filter or "all categories"
        filter_label.update(
            f"senders in: {scope} ({len(self._sender_groups)} senders)"
        )

        for group in self._sender_groups:
            senders_table.add_row(
                group.sender_domain,
                group.sender_display,
                str(group.count),
                "Yes" if group.has_unsubscribe else "No",
                key=group.sender_domain,
            )

    @work(exclusive=True, group="action")
    async def apply_action(self, *, action: ActionType) -> None:
        if self._analysis is None or self._analysis.status != "completed":
            return

        msg_label = self.query_one("#analysis-message", Label)
        tabs = self.query_one("#analysis-tabs", TabbedContent)

        if tabs.active == "tab-senders" and self._selected_sender_domain:
            request = ApplyActionsRequest(
                action=action,
                sender_domain=self._selected_sender_domain,
            )
            scope = f"sender {self._selected_sender_domain}"
        elif tabs.active == "tab-emails":
            email_ids = self._get_target_email_ids()
            if not email_ids:
                msg_label.update("no email selected")
                return
            request = ApplyActionsRequest(
                action=action,
                email_ids=email_ids,
            )
            scope = f"{len(email_ids)} email(s)"
        else:
            request = ApplyActionsRequest(
                action=action,
                category=self._selected_category,
            )
            scope = self._selected_category or "all"

        msg_label.update(f"applying {action.value} to {scope}...")

        try:
            result = await self.client.apply_actions(
                analysis_id=self.analysis_id,
                request=request,
            )
            msg_label.update(f"{result.message} ({action.value} on {scope})")
            self._selected_email_ids.clear()
            await self._fetch_and_update()
        except ApiError as e:
            msg_label.update(f"error: {e.detail}")
        except Exception as e:
            msg_label.update(f"connection error: {e}")

    def action_go_back(self) -> None:
        tabs = self.query_one("#analysis-tabs", TabbedContent)
        if tabs.active == "tab-senders":
            self._selected_sender_domain = None
            tabs.active = "tab-emails"
            self.query_one("#emails-table", DataTable).focus()
            return
        if tabs.active == "tab-emails":
            self._email_filter = None
            self._selected_sender_domain = None
            self._update_emails_table()
            tabs.active = "tab-summary"
            summary_table = self.query_one("#summary-table", DataTable)
            if self._selected_category:
                try:
                    row_idx = summary_table.get_row_index(self._selected_category)
                    summary_table.move_cursor(row=row_idx)
                except Exception:
                    pass
            summary_table.focus()
            return
        self.app.pop_screen()

    def action_refresh(self) -> None:
        self.load_analysis()

    def action_delete(self) -> None:
        self.do_delete()

    @work(exclusive=True, group="delete")
    async def do_delete(self) -> None:
        msg_label = self.query_one("#analysis-message", Label)
        try:
            result = await self.client.delete_analysis(
                analysis_id=self.analysis_id
            )
            msg_label.update(result.message)
            self.app.pop_screen()
        except ApiError as e:
            msg_label.update(f"error: {e.detail}")
        except Exception as e:
            msg_label.update(f"connection error: {e}")
