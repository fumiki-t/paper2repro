"""Minimal application logging setup."""

import logging


def configure_logging(level: int = logging.INFO) -> None:
    """Configure a readable default format for the application."""
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
