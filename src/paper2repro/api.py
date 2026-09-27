"""Minimal FastAPI application scaffold."""

from fastapi import FastAPI

from paper2repro.logging_config import configure_logging

configure_logging()

app = FastAPI(title="Paper2Repro", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/analysis")
def create_analysis() -> dict[str, str]:
    """Placeholder endpoint; analysis logic has not been implemented."""
    return {"status": "not_implemented"}
