import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest
from pydantic import ValidationError

from paper2repro.retrieval import evaluation
from paper2repro.retrieval.evaluation import (
    EvaluationSet,
    evaluate_retrieval,
    metrics_at_k,
    render_evaluation_markdown,
)


SAMPLE = Path(__file__).parents[1] / "evals" / "retrieval_sample"
SCRIPT = Path(__file__).parents[1] / "scripts" / "evaluate_retrieval.py"


@pytest.fixture
def dataset_path(tmp_path: Path) -> Path:
    shutil.copytree(SAMPLE, tmp_path / "sample")
    return tmp_path / "sample" / "dataset.json"


def test_metrics_hand_calculated_and_k_boundary() -> None:
    ranking = ["noise.txt", "a.txt", "b.txt"]
    relevant = ["a.txt", "b.txt"]
    assert metrics_at_k(ranking, relevant, 1) == {
        "hits": 0, "returned_count": 1, "recall": 0, "precision": 0, "rr": 0,
    }
    assert metrics_at_k(ranking, relevant, 2) == {
        "hits": 1, "returned_count": 2, "recall": 0.5, "precision": 0.5, "rr": 0.5,
    }
    assert metrics_at_k(ranking, relevant, 3)["precision"] == pytest.approx(2 / 3)
    assert metrics_at_k(ranking, relevant, 5)["precision"] == pytest.approx(2 / 5)
    assert metrics_at_k([], relevant, 10) == {
        "hits": 0, "returned_count": 0, "recall": 0, "precision": 0, "rr": 0,
    }


def test_same_documents_rankings_macro_and_timing(dataset_path: Path, monkeypatch) -> None:
    calls = {"inventory": 0, "load": 0, "baseline": [], "weighted": []}
    document_lists = []
    inventory = evaluation.inventory_repository
    loader = evaluation.load_repository_documents
    baseline = evaluation.retrieve_documents
    weighted = evaluation.retrieve_documents_weighted

    def inventory_spy(root):
        calls["inventory"] += 1
        return inventory(root)

    def load_spy(root, artifacts):
        calls["load"] += 1
        return loader(root, artifacts)

    def baseline_spy(claim, documents, top_k):
        calls["baseline"].append(top_k)
        document_lists.append(id(documents))
        return baseline(claim, documents, top_k)

    def weighted_spy(claim, documents, top_k):
        calls["weighted"].append(top_k)
        document_lists.append(id(documents))
        return weighted(claim, documents, top_k)

    monkeypatch.setattr(evaluation, "inventory_repository", inventory_spy)
    monkeypatch.setattr(evaluation, "load_repository_documents", load_spy)
    monkeypatch.setattr(evaluation, "retrieve_documents", baseline_spy)
    monkeypatch.setattr(evaluation, "retrieve_documents_weighted", weighted_spy)
    ticks = iter(range(14))  # one repo + 3 queries * 2 retrievers, two ticks each
    monkeypatch.setattr(evaluation, "perf_counter", lambda: next(ticks))
    monkeypatch.chdir(dataset_path.parent.parent)

    result = evaluate_retrieval(dataset_path, [5, 1, 3, 10])

    assert calls == {"inventory": 1, "load": 1, "baseline": [10] * 3, "weighted": [10] * 3}
    assert len(set(document_lists)) == 1
    assert result["ks"] == [1, 3, 5, 10]
    assert result["query_count"] == 3
    assert len(result["repositories"]) == 1
    assert result["repositories"][0]["document_count"] == 4
    assert result["coverage"]["indexed_relevant_count"] == 4
    assert result["coverage"]["total_relevant_count"] == 4
    assert result["warnings"] == []
    first = result["queries"][0]["retrievers"]
    assert [row["path"] for row in first["baseline"]["ranking"]] == [
        "README.md", "configs/decoder.yaml", "data/decoder.txt",
    ]
    assert first["weighted"]["ranking"][0]["path"] == "configs/decoder.yaml"
    assert result["macro"]["baseline"]["3"] == pytest.approx({
        "recall": 1 / 3, "precision": 2 / 9, "mrr": 1 / 6,
    })
    assert result["macro"]["weighted"]["1"] == pytest.approx({
        "recall": 0.5, "precision": 2 / 3, "mrr": 2 / 3,
    })
    assert result["macro"]["weighted"]["3"] == pytest.approx({
        "recall": 2 / 3, "precision": 1 / 3, "mrr": 2 / 3,
    })
    for name in ("baseline", "weighted"):
        assert result["queries"][2]["retrievers"][name]["metrics"]["10"]["rr"] == 0
        assert result["timing"]["retrieval"][name] == {
            "total_seconds": 3, "mean_seconds_per_query": 1,
        }
    assert result["timing"]["repository_load_seconds_total"] == 1
    markdown = render_evaluation_markdown(result)
    assert "Synthetic fixtures are not research results" in markdown
    assert "MRR@k" in markdown and "RR@k" in markdown


def test_multiple_repositories_loaded_once_each(dataset_path: Path) -> None:
    data = json.loads(dataset_path.read_text())
    shutil.copytree(dataset_path.parent / "repository", dataset_path.parent / "second")
    data["queries"][2]["repository"] = "second"
    dataset_path.write_text(json.dumps(data))
    result = evaluate_retrieval(dataset_path, [1])
    assert len(result["repositories"]) == 2


def test_unindexed_labels_retained_with_warning(dataset_path: Path) -> None:
    data = json.loads(dataset_path.read_text())
    data["queries"] = [data["queries"][0]]
    data["queries"][0]["relevant_paths"] = [
        "configs/decoder.yaml", "missing.yaml", "weights.bin",
    ]
    (dataset_path.parent / "repository" / "weights.bin").write_bytes(b"weights")
    dataset_path.write_text(json.dumps(data))
    result = evaluate_retrieval(dataset_path, [1, 10])

    assert result["coverage"]["indexed_relevant_count"] == 1
    assert result["coverage"]["total_relevant_count"] == 3
    assert result["coverage"]["queries_with_missing_paths"] == 1
    query = result["queries"][0]
    assert query["coverage"]["missing_paths"] == ["missing.yaml", "weights.bin"]
    assert query["retrievers"]["weighted"]["metrics"]["10"]["recall"] == pytest.approx(1 / 3)
    assert "weights.bin" in result["warnings"][0]
    assert "missing.yaml" in render_evaluation_markdown(result)


@pytest.mark.parametrize("invalid", [
    "", "/absolute.py", "../escape.py", "a/../b.py", "./a.py", "a//b.py",
    "a/", "a\\b.py", "C:/a.py", "https://example.com/a.py", "a\nb.py", " a.py",
])
def test_invalid_relevance_paths_rejected(dataset_path: Path, invalid: str) -> None:
    data = json.loads(dataset_path.read_text())
    data["queries"][0]["relevant_paths"] = [invalid]
    with pytest.raises(ValidationError):
        EvaluationSet.model_validate(data)


@pytest.mark.parametrize("change", ["empty-gold", "duplicate-path", "duplicate-id", "empty-set"])
def test_invalid_labels_and_ids_rejected(dataset_path: Path, change: str) -> None:
    data = json.loads(dataset_path.read_text())
    if change == "empty-gold":
        data["queries"][0]["relevant_paths"] = []
    elif change == "duplicate-path":
        data["queries"][0]["relevant_paths"] = ["README.md", "README.md"]
    elif change == "duplicate-id":
        data["queries"][1]["query_id"] = data["queries"][0]["query_id"]
    else:
        data["queries"] = []
    with pytest.raises(ValidationError):
        EvaluationSet.model_validate(data)


@pytest.mark.parametrize("repository", ["https://example.com/repo", "git@example.com:repo", "~/repo", "C:\\repo"])
def test_remote_or_nonlocal_repository_syntax_rejected(dataset_path: Path, repository: str) -> None:
    data = json.loads(dataset_path.read_text())
    data["queries"][0]["repository"] = repository
    with pytest.raises(ValidationError):
        EvaluationSet.model_validate(data)


@pytest.mark.parametrize("ks", [[], [0], [-1], [True], [1.5]])
def test_invalid_k_rejected(dataset_path: Path, ks: list) -> None:
    with pytest.raises(ValueError, match="positive integers"):
        evaluate_retrieval(dataset_path, ks)


def test_missing_repository_and_invalid_dataset_errors(dataset_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        evaluate_retrieval(dataset_path.parent / "missing.json", [1])
    data = json.loads(dataset_path.read_text())
    data["queries"][0]["repository"] = "missing-repo"
    dataset_path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="not an existing local directory"):
        evaluate_retrieval(dataset_path, [1])
    dataset_path.write_text("invalid JSON")
    with pytest.raises(ValidationError):
        evaluate_retrieval(dataset_path, [1])


def test_cli_writes_reports_offline_and_warns(dataset_path: Path, tmp_path: Path) -> None:
    data = json.loads(dataset_path.read_text())
    data["queries"][0]["relevant_paths"].append("missing.yaml")
    dataset_path.write_text(json.dumps(data))
    output = tmp_path / "evaluation-output"
    # Execute the real CLI with network connection attempts forbidden.
    runner = (
        "import runpy, socket, sys; "
        "deny = lambda *a, **k: (_ for _ in ()).throw(AssertionError('network forbidden')); "
        "socket.socket.connect = deny; socket.create_connection = deny; "
        "script = sys.argv.pop(1); runpy.run_path(script, run_name='__main__')"
    )
    result = subprocess.run(
        [sys.executable, "-c", runner, str(SCRIPT), "--dataset", str(dataset_path),
         "--top-k", "1", "3", "--output", str(output)],
        cwd=tmp_path, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "LLM/API calls: 0" in result.stdout
    assert "WARNING" in result.stderr and "missing.yaml" in result.stderr
    saved = json.loads((output / "evaluation.json").read_text())
    assert saved["query_count"] == 3 and saved["ks"] == [1, 3]
    assert "missing.yaml" in (output / "evaluation.md").read_text()


def test_cli_invalid_input_exits_without_reports(dataset_path: Path, tmp_path: Path) -> None:
    dataset_path.write_text("{}")
    output = tmp_path / "no-output"
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--dataset", str(dataset_path), "--output", str(output)],
        capture_output=True, text=True,
    )
    assert result.returncode == 2
    assert "Invalid evaluation set" in result.stderr
    assert not output.exists()
