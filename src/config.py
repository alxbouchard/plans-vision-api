"""Configuration management via environment variables."""

from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # OpenAI API
    openai_api_key: str = Field(..., description="OpenAI API key")

    # Database
    database_url: str = Field(
        default="sqlite+aiosqlite:///./plans_vision.db",
        description="Database connection URL"
    )

    # Storage
    upload_dir: str = Field(
        default="./uploads",
        description="Directory for uploaded images"
    )

    # API
    api_host: str = Field(default="0.0.0.0", description="API host")
    api_port: int = Field(default=8000, description="API port")

    # Logging
    log_level: str = Field(default="INFO", description="Logging level")

    # Model configuration (from spec)
    model_guide_builder: str = Field(
        default="gpt-5.2-pro",
        description="Model for Guide Builder agent"
    )
    model_guide_applier: str = Field(
        default="gpt-5.2",
        description="Model for Guide Applier agent"
    )
    model_self_validator: str = Field(
        default="gpt-5.2-pro",
        description="Model for Self-Validator agent"
    )
    model_guide_consolidator: str = Field(
        default="gpt-5.2",
        description="Model for Guide Consolidator agent"
    )

    # Stability thresholds
    min_stable_rules_ratio: float = Field(
        default=0.6,
        description="Minimum ratio of stable rules to generate final guide"
    )

    # Multi-tenant / Rate limiting
    rate_limit_requests_per_minute: int = Field(
        default=60,
        description="Maximum API requests per minute per tenant"
    )
    max_projects_per_tenant: int = Field(
        default=100,
        description="Maximum number of projects per tenant"
    )
    max_pages_per_project: int = Field(
        default=50,
        description="Maximum number of pages per project"
    )
    max_pages_per_month: int = Field(
        default=1000,
        description="Maximum pages processed per tenant per month"
    )

    # Upload limits
    max_upload_size_bytes: int = Field(
        default=10 * 1024 * 1024,  # 10 MB
        description="Maximum upload file size in bytes"
    )
    max_image_dimension: int = Field(
        default=10000,
        description="Maximum image width/height in pixels"
    )

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
