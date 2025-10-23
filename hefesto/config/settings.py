"""
Hefesto Configuration Settings

Loads configuration from environment variables with sensible defaults.
"""

import os
from dataclasses import dataclass
from typing import Optional


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
    api_host: str = "0.0.0.0"
    api_port: int = 8080
    api_timeout: int = 300

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
            api_host=os.getenv("HEFESTO_HOST", "0.0.0.0"),
            api_port=int(os.getenv("PORT", "8080")),
            api_timeout=int(os.getenv("HEFESTO_TIMEOUT", "300")),
        )


# Singleton instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get singleton Settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings.from_env()
    return _settings
