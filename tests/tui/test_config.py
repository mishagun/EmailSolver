from pathlib import Path

from tui.config import TuiConfig


class TestTuiConfig:
    def test_defaults(self) -> None:
        config = TuiConfig()
        assert config.base_url == "http://localhost:8000"
        assert config.poll_interval_seconds == 2.0
        assert config.token_path == Path.home() / ".tidyinbox" / "token"

    def test_custom_values(self) -> None:
        config = TuiConfig(
            base_url="http://remote:9000",
            poll_interval_seconds=5.0,
            token_path=Path("/tmp/test-token"),
        )
        assert config.base_url == "http://remote:9000"
        assert config.poll_interval_seconds == 5.0
        assert config.token_path == Path("/tmp/test-token")
