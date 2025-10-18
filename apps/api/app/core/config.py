from typing import Optional
from pydantic import Field, AliasChoices, computed_field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
import base64


class Settings(BaseSettings):
    # Primary app settings (lowercase fields as required)
    app_name: str = "Community Admin API"
    debug: bool = Field(default=True, validation_alias=AliasChoices("DEBUG", "debug"))

    # CORS
    allowed_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000"],
        validation_alias=AliasChoices("ALLOWED_ORIGINS", "allowed_origins"),
    )

    # Clerk Authentication
    clerk_publishable_key: str = Field(
        validation_alias=AliasChoices("CLERK_PUBLISHABLE_KEY", "clerk_publishable_key")
    )
    clerk_secret_key: str = Field(
        validation_alias=AliasChoices("CLERK_SECRET_KEY", "clerk_secret_key")
    )
    # Frontend API can be provided directly or derived from the publishable key when using modern Clerk keys
    clerk_frontend_api: Optional[str] = Field(
        default=None, validation_alias=AliasChoices("CLERK_FRONTEND_API", "clerk_frontend_api")
    )

    # Database
    database_url: str = Field(
        default="sqlite:///./community_admin.db",
        validation_alias=AliasChoices("DATABASE_URL", "database_url"),
    )

    # Backwards-compat fields/properties (to avoid changing existing code)
    API_V1_PREFIX: str = "/api/v1"
    PDF_STORAGE_PATH: str = "./storage/pdfs"

    # Letter generation
    xelatex_path: str = Field(default="xelatex", validation_alias=AliasChoices("XELATEX_PATH", "xelatex_path"))
    pdf_output_dir: str = Field(default="files_letters", validation_alias=AliasChoices("PDF_OUTPUT_DIR", "pdf_output_dir"))
    roster_output_dir: str = Field(
        default="files_roster_reports",
        description="Directory for generated roster PDFs"
    )

    # Templates use Jinja2 with custom delimiters <% %> for blocks and << >> for variables to avoid conflicts with LaTeX syntax
    # Path is relative to the API app directory (apps/api/)
    templates_dir: str = Field(
        default="app/templates",
        description="Directory containing LaTeX Jinja2 templates for rosters and reports"
    )

    # Deprecated/optional Clerk fields (issuer will be determined dynamically from tokens)
    CLERK_JWKS_URL: Optional[str] = None
    CLERK_JWT_ISSUER: Optional[str] = None

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )

    @model_validator(mode="after")
    def _derive_frontend_api(self):
        """
        Attempt to derive clerk_frontend_api from the publishable key if not provided.
        Modern Clerk publishable keys often follow: pk_{env}_{base64(frontend_api[+$…])}
        We'll best-effort decode the base64 segment and strip trailing "$" if present.
        If decoding fails, we leave clerk_frontend_api as None.
        """
        if not self.clerk_frontend_api and self.clerk_publishable_key:
            parts = self.clerk_publishable_key.split("_", 2)
            if len(parts) == 3:
                b64_part = parts[2]
                # add padding if missing
                padding_needed = (-len(b64_part)) % 4
                b64_padded = b64_part + ("=" * padding_needed)
                try:
                    decoded = base64.urlsafe_b64decode(b64_padded.encode()).decode()
                    # value format like "<frontend_api>$..." — take before "$" if present
                    self.clerk_frontend_api = decoded.split("$", 1)[0]
                except Exception:
                    # Leave as None if we can't decode
                    pass
        return self

    # Backward compatibility properties for existing code using UPPER_CASE names
    @computed_field(return_type=str)
    @property
    def APP_NAME(self) -> str:
        return self.app_name

    @computed_field(return_type=bool)
    @property
    def DEBUG(self) -> bool:
        return self.debug

    @computed_field(return_type=list)
    @property
    def ALLOWED_ORIGINS(self) -> list[str]:
        return self.allowed_origins

    @computed_field(return_type=str)
    @property
    def CLERK_PUBLISHABLE_KEY(self) -> str:
        return self.clerk_publishable_key

    @computed_field(return_type=str)
    @property
    def CLERK_SECRET_KEY(self) -> str:
        return self.clerk_secret_key

    @computed_field(return_type=str)
    @property
    def DATABASE_URL(self) -> str:
        return self.database_url


settings = Settings()
