from pathlib import Path

from paper2repro.models import RepoArtifact


def inventory_repository(root: Path) -> list[RepoArtifact]:
    artifacts = []

    for path in root.rglob("*"):
        if not path.is_file():
            continue

        # ここでファイルの種類を判定
        name = path.name.lower()
        suffix = path.suffix.lower()
        artifact_type = "other"

        if "readme" in name:
            artifact_type = "readme"
        elif name in ["requirements.txt", "pyproject.toml", "environment.yml"]:
            artifact_type = "environment"
        elif suffix in [".yaml", ".yml", ".json"]:
            artifact_type = "config"
        elif suffix in [".py", ".sh"]:
            artifact_type = "script"

        artifact = RepoArtifact(
            path=str(path.relative_to(root)),
            artifact_type=artifact_type,
        )

        artifacts.append(artifact)

    return artifacts