from textual import work
from textual.app import App

from tui.client import EmailSolverClient
from tui.config import TuiConfig, tui_config
from tui.screens.analysis import AnalysisScreen
from tui.screens.dashboard import DashboardScreen
from tui.screens.login import LoginScreen


class EmailSolverApp(App):
    CSS_PATH = "styles/app.tcss"
    TITLE = "EmailSolver"

    BINDINGS = [
        ("q", "quit", "Quit"),
    ]

    def __init__(self, *, config: TuiConfig | None = None) -> None:
        super().__init__()
        self.tui_config = config or tui_config
        self.client = EmailSolverClient(base_url=self.tui_config.base_url)
        self.user_email: str = ""

    def on_mount(self) -> None:
        self.check_auth()

    @work(exclusive=True)
    async def check_auth(self) -> None:
        token = self._load_token()
        if token:
            self.client.set_token(token=token)
            try:
                status = await self.client.get_auth_status()
                if status.authenticated:
                    self.user_email = status.email or ""
                    self.push_screen(DashboardScreen())
                    return
            except Exception:
                pass
            self.client.clear_token()
        self.push_screen(LoginScreen())

    def navigate_to_dashboard(self) -> None:
        self.switch_screen(DashboardScreen())

    def navigate_to_login(self) -> None:
        self.switch_screen(LoginScreen())

    def push_analysis_screen(self, *, analysis_id: int) -> None:
        self.push_screen(AnalysisScreen(analysis_id=analysis_id))

    def save_token(self, *, token: str) -> None:
        self.client.set_token(token=token)
        self.tui_config.token_path.parent.mkdir(parents=True, exist_ok=True)
        self.tui_config.token_path.write_text(token)

    def clear_saved_token(self) -> None:
        self.client.clear_token()
        if self.tui_config.token_path.exists():
            self.tui_config.token_path.unlink()

    def _load_token(self) -> str | None:
        if self.tui_config.token_path.exists():
            token = self.tui_config.token_path.read_text().strip()
            if token:
                return token
        return None

    async def on_shutdown(self) -> None:
        await self.client.close()
