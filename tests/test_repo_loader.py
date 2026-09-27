from pathlib import Path

from paper2repro.models import RepoArtifact
from paper2repro.repo.loader import load_repository_documents


def test_loader_reads_supported_text_and_prioritizes_artifact_types(
    tmp_path: Path,
) -> None:
    (tmp_path / "train.py").write_text("print('train')", encoding="utf-8")
    (tmp_path / "README.md").write_text("setup", encoding="utf-8")
    artifacts = [
        RepoArtifact(path="train.py", artifact_type="script"),
        RepoArtifact(path="README.md", artifact_type="readme"),
    ]

    documents = load_repository_documents(tmp_path, artifacts)

    assert [document.path for document in documents] == ["README.md", "train.py"]
    assert documents[0].content == "setup"


def test_loader_supports_special_build_and_requirement_files(tmp_path: Path) -> None:
    (tmp_path / "Dockerfile").write_text("FROM python:3.11", encoding="utf-8")
    (tmp_path / "requirements-dev.txt").write_text("pytest", encoding="utf-8")
    artifacts = [
        RepoArtifact(path="Dockerfile", artifact_type="other"),
        RepoArtifact(path="requirements-dev.txt", artifact_type="other"),
    ]

    documents = load_repository_documents(tmp_path, artifacts)

    assert {document.path for document in documents} == {
        "Dockerfile",
        "requirements-dev.txt",
    }


def test_loader_skips_binary_excluded_and_large_files(tmp_path: Path) -> None:
    (tmp_path / "image.png").write_bytes(b"\x89PNG")
    (tmp_path / "large.txt").write_text("x" * 20, encoding="utf-8")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("secret", encoding="utf-8")
    artifacts = [
        RepoArtifact(path="image.png", artifact_type="other"),
        RepoArtifact(path="large.txt", artifact_type="other"),
        RepoArtifact(path=".git/config", artifact_type="other"),
    ]

    documents = load_repository_documents(tmp_path, artifacts, max_file_size=10)

    assert documents == []


def test_loader_skips_invalid_utf8_without_stopping(tmp_path: Path) -> None:
    (tmp_path / "bad.txt").write_bytes(b"\xff\xfe")
    (tmp_path / "binary.txt").write_bytes(b"text\x00binary")
    (tmp_path / "good.toml").write_text("seed = 7", encoding="utf-8")
    artifacts = [
        RepoArtifact(path="bad.txt", artifact_type="other"),
        RepoArtifact(path="binary.txt", artifact_type="other"),
        RepoArtifact(path="good.toml", artifact_type="config"),
    ]

    documents = load_repository_documents(tmp_path, artifacts)

    assert [document.path for document in documents] == ["good.toml"]


def test_loader_skips_symlinks_outside_repository(tmp_path: Path) -> None:
    outside_file = tmp_path.parent / "outside-paper2repro.txt"
    outside_file.write_text("do not load", encoding="utf-8")
    link = tmp_path / "linked.txt"
    link.symlink_to(outside_file)

    documents = load_repository_documents(
        tmp_path,
        [RepoArtifact(path="linked.txt", artifact_type="other")],
    )

    assert documents == []
