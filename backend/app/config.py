"""app/config.py - Configuration management using environment variables"""
from pathlib import Path
from typing import List, Union

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Determine backend directory (absolute) to load backend/.env reliably
BACKEND_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BACKEND_DIR / ".env"


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # Application
    app_name: str = "Community Admin"
    debug: bool = Field(default=True, validation_alias="DEBUG")
    api_host: str = Field(default="0.0.0.0", validation_alias="API_HOST")
    api_port: int = Field(default=8000, validation_alias="API_PORT")

    # Database
    database_url: str = Field(
        default="",
        description="PostgreSQL database URL (required)",
        validation_alias="DATABASE_URL",
    )

    # CORS - Origins that can access the API
    cors_origins: Union[List[str], str] = Field(
        default=[
            "http://localhost:3000",
            "http://localhost:3001",
            "http://127.0.0.1:3000",
            "http://wintermute:3000",
            "http://wintermute:3001",
            "https://test.mrrc.online",
            "https://api.mrrc.online",
            "https://clerk.mrrc.online",
        ],
        validation_alias="CORS_ORIGINS",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        """Parse CORS origins from a comma-separated string or list"""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    # Local authentication foundation
    auth_secret_key: str = Field(default="dev-auth-secret-change-me", validation_alias="AUTH_SECRET_KEY")
    session_cookie_name: str = Field(default="clerk_session", validation_alias="SESSION_COOKIE_NAME")
    session_cookie_secure: bool = Field(default=False, validation_alias="SESSION_COOKIE_SECURE")
    session_cookie_samesite: str = Field(default="lax", validation_alias="SESSION_COOKIE_SAMESITE")
    session_ttl_seconds: int = Field(default=60 * 60 * 8, validation_alias="SESSION_TTL_SECONDS")

    # AWS (for production deployment)
    aws_region: str = Field(default="us-east-1", validation_alias="AWS_REGION")
    aws_access_key_id: str = Field(default="", validation_alias="AWS_ACCESS_KEY_ID")
    aws_secret_access_key: str = Field(default="", validation_alias="AWS_SECRET_ACCESS_KEY")

    # Reports
    roster_reports_dir: str = Field(default="files_roster_reports", validation_alias="ROSTER_REPORTS_DIR")
    enable_ionos_roster_publish: bool = Field(
        default=False,
        validation_alias="ENABLE_IONOS_ROSTER_PUBLISH",
    )
    ionos_sftp_secret_name: str = Field(default="", validation_alias="IONOS_SFTP_SECRET_NAME")

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


# Create the settings instance
settings = Settings()
