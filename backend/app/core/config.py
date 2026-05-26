from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """Single env-var entry point. Per code-gen-guide §10, no other module reads os.environ."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: Literal["development", "staging", "production"] = "development"
    service_version: str = "0.0.1"
    log_level: Literal["debug", "info", "warn", "error"] = "info"

    database_url: str = "postgresql+asyncpg://orthodox:orthodox@localhost:5432/orthodox"

    redis_url: str = "redis://localhost:6379/0"
    response_cache_ttl_seconds: int = 3600

    qdrant_url: str = ""
    qdrant_collection: str = "patristic"
    qdrant_collection_prefix: str = "chunks"
    qdrant_api_key: str = ""

    auth_provider: Literal["dev", "clerk"] = "dev"

    clerk_secret_key: str = "sk_test_REPLACE_ME"
    clerk_publishable_key: str = "pk_test_REPLACE_ME"
    clerk_jwt_issuer: str = ""
    clerk_authorized_parties: str = "http://localhost:3000"

    tesseract_binary_path: str = "/usr/bin/tesseract"
    tesseract_language_pack_path: str = "/usr/share/tesseract-ocr/4.00/tessdata"

    stripe_secret_key: str = "sk_test_REPLACE_ME"
    stripe_webhook_secret: str = "whsec_REPLACE_ME"
    stripe_usage_meter: str = "served_answer_count"

    anthropic_api_key: str = "REPLACE_ME"
    openai_api_key: str = "REPLACE_ME"

    make_webhook_secret: str = "REPLACE_ME"

    sensitive_log_data_key_base64: str = ""
    sensitive_log_retention_days: int = 30

    active_schema_version: str = "2026-05-01.1"
    active_prompt_version_a1a2: str = "qa_analyze@2026-05-01.1"
    active_prompt_version_a5: str = "a5_compose@2026-05-01.1"
    active_verifier_version: str = "a6_verify@2026-05-01.1"
    active_model_route_a1a2: str = "qa_analyze_anthropic@2026-05-01.1"
    active_model_route_a5: str = "a5_compose_anthropic@2026-05-01.1"
    active_model_route_embedding: str = "embedding_openai@2026-05-01.1"
    active_model_route_verifier: str = Field(default="")

    anthropic_model_a1a2: str = "claude-haiku-4-5-20251001"
    anthropic_model_a5: str = "claude-haiku-4-5-20251001"
    anthropic_model_verifier: str = "claude-haiku-4-5-20251001"

    sensitivity_keywords_path: str = str(_REPO_ROOT / "config" / "sensitivity_keywords.yaml")
    pastoral_filters_path: str = str(_REPO_ROOT / "config" / "pastoral_filters.yaml")


@lru_cache
def get_settings() -> Settings:
    return Settings()
