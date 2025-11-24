"""app/config.py - Configuration management using environment variables"""

from pathlib import Path
from pydantic_settings import BaseSettings
from typing import List, Union
from pydantic import field_validator, Field

# Determine base directory (backend folder)
BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # Application
    app_name: str = "Clerk"
    debug: bool = True
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # Database
    database_url: str = Field(default="", description="PostgreSQL database URL (required)")

    # CORS - Origins that can access the API
    cors_origins: Union[List[str], str] = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
        "https://test.mrrc.online",
        "https://api.mrrc.online",
    ]

    @field_validator('cors_origins', mode='before')
    @classmethod
    def parse_cors_origins(cls, v):
        """Parse CORS origins from a comma-separated string or list"""
        if isinstance(v, str):
            # Split by comma and strip whitespace
            return [origin.strip() for origin in v.split(',') if origin.strip()]
        return v

    # Authentication (Clerk)
    clerk_secret_key: str = ""
    clerk_publishable_key: str = ""

    # AWS (for production deployment)
    aws_region: str = "us-east-1"
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""

    class Config:
        env_file = ".env"
        case_sensitive = False
        env_file_encoding = 'utf-8'


# Create the settings instance
settings = Settings()
