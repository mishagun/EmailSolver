from __future__ import annotations

from typing import TYPE_CHECKING

from textual.screen import ModalScreen, Screen

if TYPE_CHECKING:
    from tui.app import EmailSolverApp
    from tui.client import EmailSolverClient
    from tui.config import TuiConfig


class AppScreen(Screen):
    @property
    def email_app(self) -> EmailSolverApp:
        return self.app  # type: ignore[return-value]

    @property
    def client(self) -> EmailSolverClient:
        return self.email_app.client

    @property
    def tui_config(self) -> TuiConfig:
        return self.email_app.tui_config


class AppModalScreen(ModalScreen[None]):
    @property
    def email_app(self) -> EmailSolverApp:
        return self.app  # type: ignore[return-value]
