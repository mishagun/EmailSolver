import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

from textual import work
from textual.app import ComposeResult
from textual.containers import Center, Vertical
from textual.widgets import Button, Footer, Label, Static

from tui.client import ApiError
from tui.screens import AppScreen


class _CallbackHandler(BaseHTTPRequestHandler):
    token: str | None = None

    def do_GET(self) -> None:
        params = parse_qs(urlparse(self.path).query)
        token = params.get("token", [None])[0]
        if token:
            _CallbackHandler.token = token
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(
                b"<html><body style='font-family:sans-serif;text-align:center;padding:60px'>"
                b"<h1>Login successful</h1>"
                b"<p>You can close this tab and return to the terminal.</p>"
                b"</body></html>"
            )
        else:
            self.send_response(400)
            self.end_headers()

    def log_message(self, fmt: str, *args: object) -> None:
        pass


class LoginScreen(AppScreen):
    BINDINGS = [
        ("q", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        with Center(), Vertical(id="login-box"):
            yield Static("emailsolver", id="login-title")
            yield Static(
                "Login with your Google account\nto grant access to your emails.",
                id="login-subtitle",
            )
            yield Button("Login with Google", id="submit-token", variant="default")
            yield Label("", id="login-error")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "submit-token":
            self._start_oauth()

    @work(exclusive=True, group="oauth")
    async def _start_oauth(self) -> None:
        msg_label = self.query_one("#login-error", Label)
        msg_label.update("opening browser...")

        _CallbackHandler.token = None
        server = HTTPServer(("localhost", self.tui_config.callback_port), _CallbackHandler)
        port = server.server_address[1]

        thread = threading.Thread(target=server.handle_request, daemon=True)
        thread.start()

        login_url = self.client.get_login_url(callback_port=port)
        webbrowser.open(login_url)

        msg_label.update("waiting for login...")

        import asyncio
        while thread.is_alive():
            await asyncio.sleep(0.3)

        token = _CallbackHandler.token
        server.server_close()

        if not token:
            msg_label.update("login failed — no token received")
            return

        self.client.set_token(token=token)
        try:
            status = await self.client.get_auth_status()
            if status.authenticated:
                self.email_app.user_email = status.email or ""
                self.email_app.save_token(token=token)
                self.email_app.navigate_to_dashboard()
            else:
                msg_label.update("invalid token received")
                self.client.clear_token()
        except ApiError as e:
            msg_label.update(f"error: {e.detail}")
            self.client.clear_token()
        except Exception as e:
            msg_label.update(f"connection error: {e}")
            self.client.clear_token()