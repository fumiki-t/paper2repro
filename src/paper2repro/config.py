"""Small environment-based configuration for Paper2Repro."""

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    """Runtime settings read from environment variables."""

    api_key: str | None = None

    @classmethod
    def from_env(cls) -> "Settings":
        """Read optional provider credentials from the process environment."""
        return cls(api_key=os.getenv("PAPER2REPRO_API_KEY") or None)
