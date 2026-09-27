"""Resolve local repositories and temporary shallow GitHub clones."""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
import subprocess
import tempfile
from urllib.parse import urlparse


class RepositorySourceError(RuntimeError):
    pass


def _is_github_url(source: str) -> bool:
    parsed = urlparse(source)
    return parsed.scheme == "https" and parsed.netloc.lower() == "github.com"


@contextmanager
def repository_source(source: str | Path) -> Iterator[Path]:
    """Yield a local repository path or a disposable shallow GitHub clone."""
    source_text = str(source)
    if _is_github_url(source_text):
        with tempfile.TemporaryDirectory(prefix="paper2repro-") as temp_dir:
            clone_path = Path(temp_dir) / "repository"
            try:
                subprocess.run(
                    [
                        "git",
                        "clone",
                        "--depth",
                        "1",
                        "--",
                        source_text,
                        str(clone_path),
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
            except (OSError, subprocess.SubprocessError) as error:
                detail = getattr(error, "stderr", "") or str(error)
                raise RepositorySourceError(
                    f"Could not clone repository {source_text}: {detail.strip()}"
                ) from error
            yield clone_path
        return

    local_path = Path(source).expanduser().resolve()
    if not local_path.is_dir():
        raise RepositorySourceError(
            f"Local repository does not exist or is not a directory: {local_path}"
        )
    yield local_path
