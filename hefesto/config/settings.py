"""
Hefesto Configuration Settings

Loads configuration from environment variables with sensible defaults.
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass
class Settings:
    """Hefesto configuration settings."""

    # Version
    version: str = "3.5.0"
    environment: str = "production"

    # GCP Configuration
    gcp_project_id: Optional[str] = None

    # Gemini API
    gemini_api_key: Optional[str] = None
    gemini_model: str = "gemini-2.0-flash-exp"

    # Budget Limits
    daily_budget_usd: float = 10.0
    monthly_budget_usd: float = 200.0

    # Rate Limiting
    rate_limit_per_minute: int = 60
    rate_limit_per_hour: int = 1000

    # BigQuery
    bigquery_dataset: str = "hefesto_data"
    bigquery_llm_events_table: str = "llm_events"
    bigquery_feedback_table: str = "suggestion_feedback"

    # License (Pro features)
    license_key: Optional[str] = None

    # API Server
    api_host: str = "127.0.0.1"
    api_port: int = 8080
    api_timeout: int = 300

    # --- Patch C: API Hardening ---
    # CORS
    cors_origins: str = ""  # CSV allowlist; empty = localhost only
    cors_allow_credentials: bool = False

    # Docs / OpenAPI
    expose_docs: bool = False  # /docs, /redoc, /openapi.json

    # Auth
    api_key: str = ""  # empty = no auth required

    # Rate limiting (requests per minute; 0 = disabled)
    api_rate_limit_per_minute: int = 0

    # Workspace sandbox root (empty = autodetect)
    workspace_root: str = ""

    # Analysis cache guardrails
    cache_max_items: int = 256
    cache_ttl_seconds: int = 600

    @property
    def parsed_cors_origins(self) -> List[str]:
        """Parse CORS origins CSV into list."""
        if not self.cors_origins:
            return ["http://localhost", "http://127.0.0.1"]
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def resolved_workspace_root(self) -> Path:
        """Resolve workspace root with autodetect fallback."""
        if self.workspace_root:
            return Path(self.workspace_root).resolve()
        for candidate in ["/workspace", "/app"]:
            p = Path(candidate)
            if p.is_dir():
                return p.resolve()
        return Path.cwd().resolve()

    @classmethod
    def from_env(cls) -> "Settings":
        """Load settings from environment variables."""
        return cls(
            version=os.getenv("HEFESTO_VERSION", "3.5.0"),
            environment=os.getenv("HEFESTO_ENV", "production"),
            gcp_project_id=os.getenv("GCP_PROJECT_ID"),
            gemini_api_key=os.getenv("GEMINI_API_KEY"),
            gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.0-flash-exp"),
            daily_budget_usd=float(os.getenv("HEFESTO_DAILY_BUDGET_USD", "10.0")),
            monthly_budget_usd=float(os.getenv("HEFESTO_MONTHLY_BUDGET_USD", "200.0")),
            rate_limit_per_minute=int(os.getenv("HEFESTO_RATE_LIMIT_MINUTE", "60")),
            rate_limit_per_hour=int(os.getenv("HEFESTO_RATE_LIMIT_HOUR", "1000")),
            bigquery_dataset=os.getenv("HEFESTO_BQ_DATASET", "hefesto_data"),
            bigquery_llm_events_table=os.getenv("HEFESTO_BQ_LLM_TABLE", "llm_events"),
            bigquery_feedback_table=os.getenv("HEFESTO_BQ_FEEDBACK_TABLE", "suggestion_feedback"),
            license_key=os.getenv("HEFESTO_LICENSE_KEY"),
            api_host=os.getenv("HEFESTO_HOST", "127.0.0.1"),
            api_port=int(os.getenv("PORT", "8080")),
            api_timeout=int(os.getenv("HEFESTO_TIMEOUT", "300")),
            # Patch C: API hardening
            cors_origins=os.getenv("HEFESTO_CORS_ORIGINS", ""),
            cors_allow_credentials=os.getenv("HEFESTO_CORS_ALLOW_CREDENTIALS", "false").lower()
            in ("true", "1", "yes"),
            expose_docs=os.getenv("HEFESTO_EXPOSE_DOCS", "false").lower() in ("true", "1", "yes"),
            api_key=os.getenv("HEFESTO_API_KEY", ""),
            api_rate_limit_per_minute=int(os.getenv("HEFESTO_API_RATE_LIMIT_PER_MINUTE", "0")),
            workspace_root=os.getenv("HEFESTO_WORKSPACE_ROOT", ""),
            cache_max_items=int(os.getenv("HEFESTO_CACHE_MAX_ITEMS", "256")),
            cache_ttl_seconds=int(os.getenv("HEFESTO_CACHE_TTL_SECONDS", "600")),
        )


# Singleton instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get singleton Settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings.from_env()
    return _settings
