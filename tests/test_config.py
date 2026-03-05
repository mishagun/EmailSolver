import pytest
from cryptography.fernet import Fernet
from pydantic import ValidationError

from app.core.config import AppConfig

_VALID_JWT_SECRET = "x" * 32
_VALID_FERNET_KEY = Fernet.generate_key().decode()


def _make_config(**overrides: str) -> AppConfig:
    defaults: dict[str, str] = {
        "jwt_secret_key": _VALID_JWT_SECRET,
        "fernet_key": _VALID_FERNET_KEY,
    }
    defaults.update(overrides)
    return AppConfig(_env_file=None, **defaults)


class TestJwtSecretValidation:
    def test_rejects_short_jwt_secret(self) -> None:
        with pytest.raises(ValidationError, match="at least 32"):
            AppConfig(
                jwt_secret_key="short",
                fernet_key=_VALID_FERNET_KEY,
                _env_file=None,
            )

    def test_rejects_empty_jwt_secret(self) -> None:
        with pytest.raises(ValidationError, match="at least 32"):
            AppConfig(
                jwt_secret_key="",
                fernet_key=_VALID_FERNET_KEY,
                _env_file=None,
            )

    def test_accepts_32_char_jwt_secret(self) -> None:
        config = _make_config(jwt_secret_key="a" * 32)
        assert len(config.jwt_secret_key) == 32

    def test_accepts_long_jwt_secret(self) -> None:
        config = _make_config(jwt_secret_key="a" * 64)
        assert len(config.jwt_secret_key) == 64


class TestFernetKeyValidation:
    def test_rejects_empty_fernet_key(self) -> None:
        with pytest.raises(ValidationError, match="required"):
            AppConfig(
                jwt_secret_key=_VALID_JWT_SECRET,
                fernet_key="",
                _env_file=None,
            )

    def test_accepts_valid_fernet_key(self) -> None:
        key = Fernet.generate_key().decode()
        config = _make_config(fernet_key=key)
        assert config.fernet_key == key


class TestJwtAlgorithmValidation:
    def test_rejects_invalid_algorithm(self) -> None:
        with pytest.raises(ValidationError, match="must be one of"):
            _make_config(jwt_algorithm="none")

    def test_rejects_rs256_algorithm(self) -> None:
        with pytest.raises(ValidationError, match="must be one of"):
            _make_config(jwt_algorithm="RS256")

    def test_accepts_hs256(self) -> None:
        config = _make_config(jwt_algorithm="HS256")
        assert config.jwt_algorithm == "HS256"

    def test_accepts_hs384(self) -> None:
        config = _make_config(jwt_algorithm="HS384")
        assert config.jwt_algorithm == "HS384"

    def test_accepts_hs512(self) -> None:
        config = _make_config(jwt_algorithm="HS512")
        assert config.jwt_algorithm == "HS512"


class TestValidConfig:
    def test_accepts_valid_config(self) -> None:
        config = _make_config()
        assert config.jwt_secret_key == _VALID_JWT_SECRET
        assert config.fernet_key == _VALID_FERNET_KEY

    def test_defaults_are_set(self) -> None:
        config = _make_config()
        assert config.jwt_algorithm == "HS256"
        assert config.jwt_expire_minutes == 1440
        assert config.log_level == "INFO"
        assert config.app_env == "development"
