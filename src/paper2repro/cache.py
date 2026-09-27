"""Small, inspectable JSON cache for expensive Paper2Repro LLM responses."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import TypeVar

from pydantic import BaseModel, ValidationError


ResponseModel = TypeVar("ResponseModel", bound=BaseModel)


def stable_hash(value: object) -> str:
    """Hash JSON-compatible data using a stable representation."""
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class AnalysisCache:
    """Persist structured model responses as atomic, human-readable JSON files."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory.expanduser()

    def _path(self, metadata: dict[str, object]) -> Path:
        return self.directory / f"{stable_hash(metadata)}.json"

    def get(
        self, metadata: dict[str, object], response_model: type[ResponseModel]
    ) -> ResponseModel | None:
        path = self._path(metadata)
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
            if record.get("metadata") != metadata:
                return None
            return response_model.model_validate(record["result"])
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValidationError):
            return None

    def put(self, metadata: dict[str, object], result: BaseModel) -> None:
        """Atomically store a validated response and its inspectable cache key."""
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self._path(metadata)
        record = {
            "cache_version": 1,
            "metadata": metadata,
            "result": result.model_dump(mode="json"),
        }
        payload = json.dumps(record, ensure_ascii=False, indent=2) + "\n"
        temp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", dir=self.directory, delete=False
            ) as temp_file:
                temp_path = Path(temp_file.name)
                temp_file.write(payload)
                temp_file.flush()
                os.fsync(temp_file.fileno())
            os.replace(temp_path, path)
        finally:
            if temp_path is not None and temp_path.exists():
                temp_path.unlink()
