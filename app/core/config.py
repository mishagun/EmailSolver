from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppConfig(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+asyncpg://emailsolver:emailsolver@localhost:5432/emailsolver"

    jwt_secret_key: str = ""
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440

    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/v1/auth/callback"
    google_token_uri: str = "https://oauth2.googleapis.com/token"
    google_auth_uri: str = "https://accounts.google.com/o/oauth2/auth"
    google_revoke_url: str = "https://oauth2.googleapis.com/revoke"

    fernet_key: str = ""

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-haiku-4-5-20251001"

    web_app_url: str = ""

    log_level: str = "INFO"
    app_env: str = "development"
    classified_email_ttl_days: int = 7

    @field_validator("jwt_secret_key")
    @classmethod
    def validate_jwt_secret(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError("jwt_secret_key must be at least 32 characters")
        return v

    @field_validator("fernet_key")
    @classmethod
    def validate_fernet_key(cls, v: str) -> str:
        if not v:
            raise ValueError("fernet_key is required")
        return v

    @field_validator("jwt_algorithm")
    @classmethod
    def validate_jwt_algorithm(cls, v: str) -> str:
        allowed = {"HS256", "HS384", "HS512"}
        if v not in allowed:
            raise ValueError(f"jwt_algorithm must be one of {allowed}")
        return v


config = AppConfig()
