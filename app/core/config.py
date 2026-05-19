from functools import lru_cache
from typing import List

from pydantic import AnyUrl, Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = Field("CRM Backend", alias="APP_NAME")
    debug: bool = Field(True, alias="APP_DEBUG")
    host: str = Field("0.0.0.0", alias="APP_HOST")
    port: int = Field(8000, alias="APP_PORT")

    secret_key: str = Field("change-me-in-production", alias="SECRET_KEY")
    algorithm: str = Field("HS256", alias="ALGORITHM")
    access_token_expire_minutes: int = Field(60, alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    refresh_token_expire_minutes: int = Field(7 * 24 * 60, alias="REFRESH_TOKEN_EXPIRE_MINUTES")

    database_url: str = Field("sqlite+aiosqlite:///./data.db", alias="DATABASE_URL")

    cors_origins: List[str] = Field(default_factory=lambda: ["*"], alias="CORS_ORIGINS")

    # Set True only when HTTPS/SSL is configured on the server.
    # Keep False (default) for plain HTTP cloud deployments so session cookies work.
    https_only: bool = Field(False, alias="APP_HTTPS_ONLY")

    # Update System Configuration
    update_check_enabled: bool = Field(True, alias="UPDATE_CHECK_ENABLED")
    update_check_url: str = Field("", alias="UPDATE_CHECK_URL")
    update_check_interval: int = Field(86400, alias="UPDATE_CHECK_INTERVAL")

    # Email-to-Ticket Configuration
    email_check_interval: int = Field(120, alias="EMAIL_CHECK_INTERVAL")  # Default: 2 minutes (120 seconds)

    # Google OAuth Configuration
    google_client_id: str = Field("", alias="GOOGLE_CLIENT_ID")
    google_client_secret: str = Field("", alias="GOOGLE_CLIENT_SECRET")
    google_redirect_uri: str = Field("http://localhost:8000/web/auth/google/callback", alias="GOOGLE_REDIRECT_URI")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        populate_by_name = True


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
