"""Offline, file-level retrieval evaluation against fixed relevance labels."""

import re
from pathlib import Path
from time import perf_counter
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from paper2repro.models import ExperimentalClaim, PaperEvidence
from paper2repro.repo.inventory import inventory_repository
from paper2repro.repo.loader import load_repository_documents
from paper2repro.retrieval.keyword import (
    retrieve_documents,
    retrieve_documents_weighted,
)


class EvaluationClaim(ExperimentalClaim):
    """A fixed query claim; PDF evidence is optional for retrieval evaluation."""

    model_config = ConfigDict(extra="forbid", strict=True)
    evidence: list[PaperEvidence] = Field(default_factory=list)


class EvaluationQuery(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    query_id: str
    repository: str
    claim: EvaluationClaim
    relevant_paths: list[str] = Field(min_length=1)

    @field_validator("query_id", "repository")
    @classmethod
    def validate_text(cls, value: str) -> str:
        if not value.strip() or value != value.strip() or any(
            ord(character) < 32 or ord(character) == 127 for character in value
        ):
            raise ValueError(
                "must be nonempty text without surrounding whitespace or controls"
            )
        return value

    @field_validator("repository")
    @classmethod
    def validate_repository(cls, value: str) -> str:
        if (
            re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", value)
            or value.startswith(("//", "~", "git@"))
            or "\\" in value
        ):
            raise ValueError(
                "repository must be a local POSIX path, not a URL or shell expansion"
            )
        return value

    @field_validator("relevant_paths")
    @classmethod
    def validate_relevant_paths(cls, paths: list[str]) -> list[str]:
        for path in paths:
            if (
                not path
                or path != path.strip()
                or "\\" in path
                or ":" in path
                or any(part in {"", ".", ".."} for part in path.split("/"))
                or any(
                    ord(character) < 32 or ord(character) == 127 for character in path
                )
            ):
                raise ValueError(
                    "relevant_paths must be canonical relative POSIX file paths"
                )
        if len(paths) != len(set(paths)):
            raise ValueError("duplicate relevant_paths are not allowed")
        return paths


class EvaluationSet(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: Literal[1]
    label_type: Literal["synthetic", "gold", "silver"]
    description: str = ""
    queries: list[EvaluationQuery] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_query_ids(self) -> "EvaluationSet":
        ids = [query.query_id for query in self.queries]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate query_id values are not allowed")
        return self


def metrics_at_k(ranking: list[str], relevant_paths: list[str], k: int) -> dict:
    """Score one ranked prefix; missing gold stays in recall's denominator."""
    if isinstance(k, bool) or not isinstance(k, int) or k < 1:
        raise ValueError("k must be a positive integer")
    if not relevant_paths or len(relevant_paths) != len(set(relevant_paths)):
        raise ValueError("relevant_paths must be nonempty and unique")
    if len(ranking) != len(set(ranking)):
        raise ValueError("ranking must contain unique file paths")
    relevant = set(relevant_paths)
    prefix = ranking[:k]
    hits = sum(path in relevant for path in prefix)
    rr = next(
        (1 / rank for rank, path in enumerate(prefix, start=1) if path in relevant),
        0.0,
    )
    return {
        "hits": hits,
        "returned_count": len(prefix),
        "recall": hits / len(relevant),
        "precision": hits / k,
        "rr": rr,
    }


def evaluate_retrieval(dataset_path: Path, ks: list[int]) -> dict:
    """Load each resolved local repo once, then compare the two existing retrievers.

    Retrieval timing covers only each retriever call at max(ks). Smaller k values
    use prefixes of that ranking; there are no repeated or warm-up retrieval runs.
    """
    if not ks or any(
        isinstance(k, bool) or not isinstance(k, int) or k < 1 for k in ks
    ):
        raise ValueError("ks must contain positive integers")
    ks = sorted(set(ks))
    dataset_path = Path(dataset_path).resolve()
    dataset = EvaluationSet.model_validate_json(
        dataset_path.read_text(encoding="utf-8")
    )
    roots = [
        (dataset_path.parent / query.repository).resolve() for query in dataset.queries
    ]
    for root in roots:
        if not root.is_dir():
            raise ValueError(f"Repository is not an existing local directory: {root}")

    documents_by_root = {}
    repositories = []
    for root in dict.fromkeys(roots):
        started = perf_counter()
        artifacts = inventory_repository(root)
        documents = load_repository_documents(root, artifacts)
        elapsed = perf_counter() - started
        documents_by_root[root] = documents
        repositories.append(
            {
                "repository": str(root),
                "artifact_count": len(artifacts),
                "document_count": len(documents),
                "load_seconds": elapsed,
            }
        )

    retrievers = {
        "baseline": retrieve_documents,
        "weighted": retrieve_documents_weighted,
    }
    query_results = []
    warnings = []
    for query, root in zip(dataset.queries, roots):
        documents = documents_by_root[root]
        indexed = {document.path for document in documents}
        missing = [path for path in query.relevant_paths if path not in indexed]
        if missing:
            warnings.append(
                f"Query {query.query_id}: relevant paths not indexed: {', '.join(missing)}"
            )
        results = {}
        for name, retriever in retrievers.items():
            started = perf_counter()
            retrieved = retriever(query.claim, documents, top_k=max(ks))
            elapsed = perf_counter() - started
            ranking = [document.path for document in retrieved]
            results[name] = {
                "ranking": [
                    {"rank": rank, "path": path, "relevant": path in query.relevant_paths}
                    for rank, path in enumerate(ranking, start=1)
                ],
                "metrics": {
                    str(k): metrics_at_k(ranking, query.relevant_paths, k) for k in ks
                },
                "retrieval_seconds": elapsed,
            }
        query_results.append(
            {
                "query_id": query.query_id,
                "repository": str(root),
                "claim": query.claim.model_dump(mode="json"),
                "relevant_paths": query.relevant_paths,
                "coverage": {
                    "indexed_relevant_count": len(query.relevant_paths) - len(missing),
                    "total_relevant_count": len(query.relevant_paths),
                    "missing_paths": missing,
                },
                "retrievers": results,
            }
        )

    count = len(query_results)
    macro = {}
    timings = {}
    for name in retrievers:
        macro[name] = {}
        for k in ks:
            per_query = [
                query["retrievers"][name]["metrics"][str(k)] for query in query_results
            ]
            macro[name][str(k)] = {
                output: sum(metrics[metric] for metrics in per_query) / count
                for output, metric in (
                    ("recall", "recall"), ("precision", "precision"), ("mrr", "rr")
                )
            }
        total = sum(
            query["retrievers"][name]["retrieval_seconds"] for query in query_results
        )
        timings[name] = {"total_seconds": total, "mean_seconds_per_query": total / count}

    return {
        "schema_version": 1,
        "dataset_path": str(dataset_path),
        "label_type": dataset.label_type,
        "description": dataset.description,
        "ks": ks,
        "query_count": count,
        "metric_policy": (
            "Recall@k = hits / all labeled relevant paths, including unindexed paths. "
            "Precision@k = hits / k, including unreturned slots. "
            "RR@k = reciprocal of first relevant rank within k, or 0. "
            "Macro means weight every query equally; MRR@k is mean RR@k."
        ),
        "timing_policy": (
            "perf_counter wall seconds; repo loading includes inventory and text loading once "
            "per resolved repo. Retrieval times only the existing retriever call at max(k), "
            "once per query/method, always baseline then weighted. Other k use ranking prefixes. "
            "Parsing, coverage, metrics and output are excluded from both timers. "
            "Totals sum measured calls; means divide by query count. No warm-up or repeated runs."
        ),
        "repositories": repositories,
        "coverage": {
            "indexed_relevant_count": sum(
                q["coverage"]["indexed_relevant_count"] for q in query_results
            ),
            "total_relevant_count": sum(
                q["coverage"]["total_relevant_count"] for q in query_results
            ),
            "queries_with_missing_paths": sum(
                bool(q["coverage"]["missing_paths"]) for q in query_results
            ),
            "unit": "query-file pairs (the same file labeled for two queries counts twice)",
        },
        "warnings": warnings,
        "macro": macro,
        "timing": {
            "repository_load_seconds_total": sum(
                repo["load_seconds"] for repo in repositories
            ),
            "retrieval": timings,
        },
        "queries": query_results,
    }


def _cell(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(
        ">", "&gt;"
    ).replace("|", "&#124;").replace("`", "&#96;").replace("\n", " ")


def render_evaluation_markdown(result: dict) -> str:
    """Render aggregate and per-query metrics without hiding label coverage."""
    coverage = result["coverage"]
    lines = [
        "# Retrieval evaluation", "",
        f"- Dataset: {_cell(result['dataset_path'])}",
        f"- Labels: {result['label_type']}; queries: {result['query_count']}",
        f"- Description: {_cell(result['description'])}",
        "- No LLM/API calls. Synthetic fixtures are not research results.",
        "", "## Metric policy", "", result["metric_policy"],
        "", "## Label coverage", "",
        f"- Indexed relevant paths: {coverage['indexed_relevant_count']} / {coverage['total_relevant_count']}",
        f"- Queries with missing paths: {coverage['queries_with_missing_paths']}",
        f"- Count unit: {coverage['unit']}",
        "", "### Warnings", "",
    ]
    lines.extend([f"- {_cell(warning)}" for warning in result["warnings"]] or ["- None."])
    lines.extend([
        "", "## Macro averages", "",
        "| Retriever | k | Recall@k | Precision@k | MRR@k |",
        "|---|---:|---:|---:|---:|",
    ])
    for name, by_k in result["macro"].items():
        for k, metrics in by_k.items():
            lines.append(f"| {name} | {k} | {metrics['recall']:.4f} | {metrics['precision']:.4f} | {metrics['mrr']:.4f} |")
    lines.extend(["", "## Timing", "", result["timing_policy"], ""])
    for repo in result["repositories"]:
        lines.append(f"- Repo load: {_cell(repo['repository'])}: {repo['load_seconds']:.6f}s; {repo['document_count']} documents")
    for name, timing in result["timing"]["retrieval"].items():
        lines.append(f"- {name} retrieval: total {timing['total_seconds']:.6f}s; mean/query {timing['mean_seconds_per_query']:.6f}s")
    for query in result["queries"]:
        lines.extend([
            "", f"## Query: {_cell(query['query_id'])}", "",
            _cell(query["claim"]["statement"]), "",
            f"- Repository: {_cell(query['repository'])}",
            "- Relevant paths: " + ", ".join(_cell(path) for path in query["relevant_paths"]),
            "- Missing from index: " + (", ".join(_cell(path) for path in query["coverage"]["missing_paths"]) or "none"),
        ])
        for name, evaluation in query["retrievers"].items():
            lines.extend(["", f"### {name}", "", "| Rank | Path | Labeled relevant |", "|---:|---|:---:|"])
            lines.extend([
                f"| {item['rank']} | {_cell(item['path'])} | {'yes' if item['relevant'] else 'no'} |"
                for item in evaluation["ranking"]
            ] or ["| — | No documents returned | — |"])
            lines.extend(["", "| k | Hits | Returned | Recall@k | Precision@k | RR@k |", "|---:|---:|---:|---:|---:|---:|"])
            for k, metrics in evaluation["metrics"].items():
                lines.append(f"| {k} | {metrics['hits']} | {metrics['returned_count']} | {metrics['recall']:.4f} | {metrics['precision']:.4f} | {metrics['rr']:.4f} |")
    return "\n".join(lines) + "\n"
