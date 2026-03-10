from textual import work
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Label, Static

from tui.client import ApiError
from tui.models import ActionType, ApplyActionsRequest, ClassifiedEmailResponse
from tui.screens import AppModalScreen


class EmailDetailScreen(AppModalScreen):
    BINDINGS = [
        ("escape", "dismiss", "Close"),
        ("q", "dismiss", "Close"),
        ("k", "keep", "Keep"),
        ("m", "mark_read", "Mark Read"),
        ("v", "move", "Move"),
        ("s", "spam", "Spam"),
        ("u", "unsubscribe", "Unsubscribe"),
    ]

    def __init__(self, *, email: ClassifiedEmailResponse, analysis_id: int) -> None:
        super().__init__()
        self.email = email
        self.analysis_id = analysis_id

    def compose(self) -> ComposeResult:
        e = self.email
        importance = "*" * (e.importance or 0) + " " * (5 - (e.importance or 0))
        confidence_pct = f"{(e.confidence or 0) * 100:.0f}%"

        with Vertical(id="email-detail"):
            yield Static("Email Details", id="detail-title")
            yield Label(f"From:        {e.sender or 'unknown'}")
            yield Label(f"Domain:      {e.sender_domain or 'unknown'}")
            yield Label(f"Subject:     {e.subject or 'no subject'}")
            yield Label(f"Category:    {e.category or 'unclassified'}")
            yield Label(f"Importance:  [{importance}]")
            yield Label(f"Sender Type: {e.sender_type or 'unknown'}")
            yield Label(f"Confidence:  {confidence_pct}")
            if e.has_unsubscribe:
                if e.unsubscribe_post_header and e.unsubscribe_header:
                    unsub_text = "Yes (one-click)"
                elif e.unsubscribe_header:
                    unsub_text = "Yes (link only)"
                else:
                    unsub_text = "Yes"
            else:
                unsub_text = "No"
            yield Label(f"Unsubscribe: {unsub_text}")
            yield Label(f"Action:      {e.action_taken or 'none'}", id="detail-action")
            if e.snippet:
                yield Static("Snippet:", classes="detail-section")
                yield Label(e.snippet, id="email-snippet")
            yield Static("", id="detail-status")
            yield Static(
                "[ESC] Close | [k] Keep  [m] Read  [v] Move  [s] Spam  [u] Unsub",
                id="detail-hint",
            )

    def action_keep(self) -> None:
        self._apply_action(action=ActionType.KEEP)

    def action_mark_read(self) -> None:
        self._apply_action(action=ActionType.MARK_READ)

    def action_move(self) -> None:
        self._apply_action(action=ActionType.MOVE_TO_CATEGORY)

    def action_spam(self) -> None:
        self._apply_action(action=ActionType.MARK_SPAM)

    def action_unsubscribe(self) -> None:
        self._apply_action(action=ActionType.UNSUBSCRIBE)

    @work(exclusive=True, group="detail-action")
    async def _apply_action(self, *, action: ActionType) -> None:
        status_label = self.query_one("#detail-status", Static)
        status_label.update(f"applying {action.value}...")

        request = ApplyActionsRequest(
            action=action,
            email_ids=[self.email.id],
        )
        try:
            result = await self.client.apply_actions(
                analysis_id=self.analysis_id,
                request=request,
            )
            self.email.action_taken = action.value
            self.query_one("#detail-action", Label).update(
                f"Action:      {action.value}"
            )
            status_label.update(result.message)
        except ApiError as e:
            status_label.update(f"error: {e.detail}")
        except Exception as e:
            status_label.update(f"connection error: {e}")
