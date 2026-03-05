from pydantic_settings import BaseSettings, SettingsConfigDict


class AppConfig(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+asyncpg://emailsolver:emailsolver@localhost:5432/emailsolver"

    jwt_secret_key: str = "change-me-to-a-random-secret"
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

    log_level: str = "INFO"
    app_env: str = "development"
    classified_email_ttl_days: int = 7


config = AppConfig()
