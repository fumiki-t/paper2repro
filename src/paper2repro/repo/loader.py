"""Load small, text-based repository artifacts for retrieval."""

from pathlib import Path, PurePosixPath

from paper2repro.models import RepoArtifact, RepoDocument


DEFAULT_MAX_FILE_SIZE = 256_000

_TEXT_SUFFIXES = {
    ".cfg",
    ".ini",
    ".json",
    ".md",
    ".py",
    ".sh",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}
_TEXT_NAMES = {"dockerfile", "makefile"}
_EXCLUDED_PARTS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "outputs",
    "results",
}
_TYPE_PRIORITY = {"readme": 0, "environment": 1, "config": 2, "script": 3}


def _is_text_candidate(path: PurePosixPath) -> bool:
    name = path.name.lower()
    return (
        path.suffix.lower() in _TEXT_SUFFIXES
        or name in _TEXT_NAMES
        or (name.startswith("requirements") and name.endswith(".txt"))
    )


def load_repository_documents(
    root: Path,
    artifacts: list[RepoArtifact],
    *,
    max_file_size: int = DEFAULT_MAX_FILE_SIZE,
) -> list[RepoDocument]:
    """Load safe text candidates while skipping large or undecodable files.

    The size limit bounds memory and prompt growth for repositories that contain
    generated logs or data disguised as text. Decode failures are skipped so one
    unusual file cannot stop the analysis pipeline.
    """
    documents: list[RepoDocument] = []
    resolved_root = root.resolve()
    ordered_artifacts = sorted(
        artifacts,
        key=lambda item: (_TYPE_PRIORITY.get(item.artifact_type, 4), item.path),
    )

    for artifact in ordered_artifacts:
        relative_path = PurePosixPath(artifact.path)
        if any(part.lower() in _EXCLUDED_PARTS for part in relative_path.parts):
            continue
        if not _is_text_candidate(relative_path):
            continue

        file_path = root / Path(*relative_path.parts)
        try:
            if file_path.is_symlink():
                continue
            file_path.resolve().relative_to(resolved_root)
            if not file_path.is_file() or file_path.stat().st_size > max_file_size:
                continue
            content = file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError, ValueError):
            continue

        if "\x00" in content:
            continue
        documents.append(
            RepoDocument(
                path=artifact.path,
                artifact_type=artifact.artifact_type,
                content=content,
            )
        )

    return documents
