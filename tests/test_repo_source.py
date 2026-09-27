from pathlib import Path

import pytest

from paper2repro.repo.source import RepositorySourceError, repository_source


def test_repository_source_yields_existing_local_directory(tmp_path: Path) -> None:
    with repository_source(tmp_path) as resolved:
        assert resolved == tmp_path.resolve()


def test_repository_source_rejects_missing_local_directory(tmp_path: Path) -> None:
    with pytest.raises(RepositorySourceError, match="does not exist"):
        with repository_source(tmp_path / "missing"):
            pass
