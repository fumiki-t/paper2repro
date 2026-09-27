from pathlib import Path

from paper2repro.repo.inventory import inventory_repository


def test_inventory_classifies_repository_files_and_keeps_relative_paths(
    tmp_path: Path,
) -> None:
    (tmp_path / "README.md").write_text("project", encoding="utf-8")
    (tmp_path / "environment.yml").write_text("dependencies: []", encoding="utf-8")
    (tmp_path / "configs").mkdir()
    (tmp_path / "configs" / "experiment.yaml").write_text("seed: 1", encoding="utf-8")
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "run.py").write_text("pass", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("other", encoding="utf-8")

    artifacts = inventory_repository(tmp_path)
    by_path = {artifact.path: artifact.artifact_type for artifact in artifacts}

    assert by_path == {
        "README.md": "readme",
        "environment.yml": "environment",
        "configs/experiment.yaml": "config",
        "scripts/run.py": "script",
        "notes.txt": "other",
    }
