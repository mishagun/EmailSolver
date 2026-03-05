from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Label, Static

from tui.models import ClassifiedEmailResponse
from tui.screens import AppModalScreen


class EmailDetailScreen(AppModalScreen):
    BINDINGS = [
        ("escape", "dismiss", "Close"),
        ("q", "dismiss", "Close"),
    ]

    def __init__(self, *, email: ClassifiedEmailResponse) -> None:
        super().__init__()
        self.email = email

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
            yield Label(f"Action:      {e.action_taken or 'none'}")
            if e.snippet:
                yield Static("Snippet:", classes="detail-section")
                yield Label(e.snippet, id="email-snippet")
            yield Static("Press [ESC] to close", id="detail-hint")
