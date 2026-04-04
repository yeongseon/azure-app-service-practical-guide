"""Application settings loaded from environment variables."""

from __future__ import annotations

from dataclasses import dataclass
import os

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    """Runtime settings for application behavior and telemetry."""

    port: int = 8000
    app_name: str = "azure-appservice-python-guide"
    app_version: str = "1.0.0"
    environment: str = "development"
    telemetry_mode: str = "basic"
    log_level: str = "INFO"
    applicationinsights_connection_string: str = ""
    external_api_timeout_seconds: int = 10

    @classmethod
    def from_env(cls) -> "Settings":
        telemetry_mode = os.getenv("TELEMETRY_MODE", "basic").strip().lower()
        if telemetry_mode not in {"basic", "advanced"}:
            telemetry_mode = "basic"

        return cls(
            port=int(os.getenv("PORT", "8000")),
            app_name=os.getenv("APP_NAME", "azure-appservice-python-guide"),
            app_version=os.getenv("APP_VERSION", "1.0.0"),
            environment=os.getenv("APP_ENV", os.getenv("FLASK_ENV", "development")),
            telemetry_mode=telemetry_mode,
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
            applicationinsights_connection_string=os.getenv(
                "APPLICATIONINSIGHTS_CONNECTION_STRING", ""
            ),
            external_api_timeout_seconds=int(
                os.getenv("EXTERNAL_API_TIMEOUT_SECONDS", "10")
            ),
        )


_SETTINGS: Settings | None = None


def get_settings() -> Settings:
    """Return singleton settings instance."""
    global _SETTINGS
    if _SETTINGS is None:
        _SETTINGS = Settings.from_env()
    return _SETTINGS
