"""Small environment-based configuration for Paper2Repro."""

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    """Runtime settings read from environment variables."""

    api_key: str | None = None
    model: str = "gemini-3.8-flash"

    @classmethod
    def from_env(cls) -> "Settings":
        """Read optional provider credentials from the process environment."""
        return cls(
            api_key=os.getenv("PAPER2REPRO_API_KEY") or None,
            model=os.getenv("PAPER2REPRO_MODEL") or "gemini-3.8-flash",
        )
