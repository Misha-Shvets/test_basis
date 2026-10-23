"""Application configuration."""

import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Settings:
    """Runtime settings passed to the DI container."""

    database_url: str = (
        "postgresql+psycopg://payments:payments@localhost:5432/payments"
    )
    rabbit_url: str = "amqp://guest:guest@localhost:5672/"
    api_key: str = "test-api-key"
    debug: bool = False

    @classmethod
    def from_env(cls) -> "Settings":
        """Build settings from environment variables."""
        return cls(
            database_url=os.getenv(
                "DATABASE_URL",
                "postgresql+psycopg://payments:payments@localhost:5432/payments",
            ),
            rabbit_url=os.getenv(
                "RABBIT_URL",
                "amqp://guest:guest@localhost:5672/",
            ),
            api_key=os.getenv("API_KEY", "test-api-key"),
            debug=os.getenv("DEBUG", "").lower() in {"1", "true", "yes"},
        )
