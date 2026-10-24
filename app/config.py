"""Application configuration."""

import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Settings:
    """Runtime settings passed to the DI container."""

    database_url: str
    rabbit_url: str
    api_key: str
    debug: bool = False

    @classmethod
    def from_env(cls) -> "Settings":
        """Build settings from environment variables."""
        return cls(
            database_url=os.environ["DATABASE_URL"],
            rabbit_url=os.environ["RABBIT_URL"],
            api_key=os.environ["API_KEY"],
            debug=os.getenv("DEBUG", "").lower() in {"1", "true", "yes"},
        )
