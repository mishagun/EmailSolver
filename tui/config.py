from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class TuiConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="TIDYINBOX_TUI_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    base_url: str = "http://localhost:8000"
    token_path: Path = Path.home() / ".tidyinbox" / "token"
    poll_interval_seconds: float = 2.0
    callback_port: int = 0


tui_config = TuiConfig()
