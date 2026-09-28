from pathlib import Path

from paper2repro.models import (
    AuditItem,
    ClaimExtractionResult,
    ClaimRepositoryAssessment,
    ClaimRepositoryMapping,
    ExperimentalClaim,
    LLMTokenUsage,
    PaperChunk,
    PaperEvidence,
    RepoEvidence,
)
from paper2repro.pipeline import analyze
from paper2repro.observability import LLMCallBudgetExceeded
from paper2repro.report import write_analysis_report


class PipelineLLMClient:
    def generate_structured(self, prompt, response_model):
        if response_model is ClaimExtractionResult:
            return ClaimExtractionResult(
                claims=[
                    ExperimentalClaim(
                        statement="The method reaches 72.4 mAP on SoccerNet.",
                        evidence=[
                            PaperEvidence(
                                page=1,
                                excerpt="The method reaches 72.4 mAP on SoccerNet.",
                            )
                        ],
                        dataset="SoccerNet",
                        metric="mAP",
                        reported_value="72.4",
                    )
                ]
            )
        if response_model is ClaimRepositoryAssessment:
            evidence = RepoEvidence(
                path="README.md",
                artifact_type="readme",
                excerpt="Evaluate SoccerNet mAP 72.4 with python evaluate.py",
            )
            return ClaimRepositoryAssessment(
                mapping=ClaimRepositoryMapping(
                    status="SUPPORTED",
                    evidence=[evidence],
                    explanation="The README provides an evaluation command.",
                ),
                audit=[
                    AuditItem(
                        check="evaluation_protocol_metric",
                        status="PRESENT",
                        evidence=[evidence],
                        notes="Metric and command are documented.",
                    )
                ],
            )
        raise AssertionError(f"Unexpected response model: {response_model}")


class InvalidPaperEvidenceClient(PipelineLLMClient):
    def generate_structured(self, prompt, response_model):
        if response_model is ClaimExtractionResult:
            return ClaimExtractionResult(
                claims=[
                    ExperimentalClaim(
                        statement="The method reaches 99.9 mAP on SoccerNet.",
                        evidence=[PaperEvidence(page=1, excerpt="99.9 mAP")],
                        dataset="SoccerNet",
                        metric="mAP",
                        reported_value="99.9",
                    )
                ]
            )
        return super().generate_structured(prompt, response_model)


def test_pipeline_runs_end_to_end_with_grounded_report(
    tmp_path: Path, monkeypatch
) -> None:
    paper_path = tmp_path / "paper.pdf"
    paper_path.write_bytes(b"mocked by parse_pdf")
    repository = tmp_path / "repository"
    repository.mkdir()
    (repository / "README.md").write_text(
        "Evaluate SoccerNet mAP 72.4 with python evaluate.py",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "paper2repro.pipeline.parse_pdf",
        lambda path: [
            PaperChunk(
                page=1,
                text="The method reaches 72.4 mAP on SoccerNet.",
            )
        ],
    )

    report = analyze(paper_path, repository, PipelineLLMClient())

    assert report.retriever == "baseline"
    assert len(report.claims) == 1
    assert report.claims[0].paper_evidence_validation[0].is_valid
    assert report.claims[0].retrieved_documents == ["README.md"]
    assert report.claims[0].mapping.status == "SUPPORTED"
    assert report.claims[0].mapping_evidence_validation[0].is_valid
    assert report.performance.prompt_characters_total == sum(
        request.prompt_characters for request in report.performance.llm_requests
    )
    assert report.performance.response_characters_total == sum(
        request.response_characters for request in report.performance.llm_requests
    )
    assert report.performance.total_input_tokens is None
    assert report.performance.total_output_tokens is None
    assert report.performance.total_thought_tokens is None
    assert report.performance.total_cached_tokens is None
    assert report.performance.total_tokens is None

    explicit_baseline = analyze(
        paper_path,
        repository,
        PipelineLLMClient(),
        retriever="baseline",
    )
    assert explicit_baseline.retriever == "baseline"
    assert explicit_baseline.claims[0].retrieved_documents == ["README.md"]

    metric_item = next(
        item
        for item in report.claims[0].audit
        if item.check == "evaluation_protocol_metric"
    )
    assert metric_item.status == "PRESENT"

    json_path, markdown_path = write_analysis_report(report, tmp_path / "output")
    assert '"is_valid": true' in json_path.read_text(encoding="utf-8")
    markdown = markdown_path.read_text(encoding="utf-8")
    assert '"retriever": "baseline"' in json_path.read_text(encoding="utf-8")
    assert "- Retriever: `baseline`" in markdown
    assert "**VALID**" in markdown
    assert "**evaluation_protocol_metric: PRESENT**" in markdown
    assert "## Summary" in markdown
    assert "| # | Claim | Dataset | Metric / value | Paper evidence | Mapping |" in markdown
    assert "LLM requests: 2" in markdown
    assert "not token counts" in markdown


def test_pipeline_selects_weighted_retriever_and_records_it(
    tmp_path: Path, monkeypatch
) -> None:
    paper_path = tmp_path / "paper.pdf"
    paper_path.write_bytes(b"mocked by parse_pdf")
    repository = tmp_path / "repository"
    repository.mkdir()
    (repository / "README.md").write_text(
        "Evaluate SoccerNet mAP 72.4 with python evaluate.py", encoding="utf-8"
    )
    (repository / "train.py").write_text(
        "SoccerNet mAP 72.4 method reaches", encoding="utf-8"
    )
    monkeypatch.setattr(
        "paper2repro.pipeline.parse_pdf",
        lambda path: [
            PaperChunk(page=1, text="The method reaches 72.4 mAP on SoccerNet.")
        ],
    )

    report = analyze(
        paper_path,
        repository,
        PipelineLLMClient(),
        retriever="weighted",
        top_k=1,
    )

    assert report.retriever == "weighted"
    assert report.claims[0].retrieved_documents == ["train.py"]
    json_path, markdown_path = write_analysis_report(report, tmp_path / "output")
    assert '"retriever": "weighted"' in json_path.read_text(encoding="utf-8")
    assert "- Retriever: `weighted`" in markdown_path.read_text(encoding="utf-8")


def test_pipeline_saves_provider_token_usage_totals(
    tmp_path: Path, monkeypatch
) -> None:
    class TokenUsageClient(PipelineLLMClient):
        def __init__(self):
            self.request_index = 0
            self.last_token_usage = None
            self.usages = [
                LLMTokenUsage(
                    total_input_tokens=100,
                    total_output_tokens=30,
                    total_thought_tokens=4,
                    total_cached_tokens=10,
                    total_tokens=134,
                ),
                LLMTokenUsage(
                    total_input_tokens=50,
                    total_output_tokens=20,
                    total_thought_tokens=0,
                    total_cached_tokens=0,
                    total_tokens=70,
                ),
            ]

        def generate_structured(self, prompt, response_model):
            result = super().generate_structured(prompt, response_model)
            self.last_token_usage = self.usages[self.request_index]
            self.request_index += 1
            return result

    paper_path = tmp_path / "paper.pdf"
    paper_path.write_bytes(b"mocked by parse_pdf")
    repository = tmp_path / "repository"
    repository.mkdir()
    (repository / "README.md").write_text(
        "Evaluate SoccerNet mAP 72.4 with python evaluate.py", encoding="utf-8"
    )
    monkeypatch.setattr(
        "paper2repro.pipeline.parse_pdf",
        lambda path: [
            PaperChunk(page=1, text="The method reaches 72.4 mAP on SoccerNet.")
        ],
    )

    report = analyze(paper_path, repository, TokenUsageClient())
    serialized_performance = report.model_dump(mode="json")["performance"]

    assert serialized_performance["total_input_tokens"] == 150
    assert serialized_performance["total_output_tokens"] == 50
    assert serialized_performance["total_thought_tokens"] == 4
    assert serialized_performance["total_cached_tokens"] == 10
    assert serialized_performance["total_tokens"] == 204
    assert report.performance.prompt_characters_total == sum(
        request.prompt_characters for request in report.performance.llm_requests
    )
    assert report.performance.response_characters_total == sum(
        request.response_characters for request in report.performance.llm_requests
    )
    assert report.performance.llm_requests[0].total_input_tokens == 100

    _, markdown_path = write_analysis_report(report, tmp_path / "output")
    markdown = markdown_path.read_text(encoding="utf-8")
    assert (
        "Provider-reported tokens: input 150; output 50; thought 4; cached 10; "
        "total 204"
    ) in markdown
    assert "recorded separately from character counts" in markdown


def test_pipeline_cache_reuses_extraction_and_mapping_and_invalidates_changed_docs(
    tmp_path: Path, monkeypatch
) -> None:
    class CountingClient(PipelineLLMClient):
        def __init__(self):
            self.calls = 0

        def generate_structured(self, prompt, response_model):
            self.calls += 1
            return super().generate_structured(prompt, response_model)

    paper_path = tmp_path / "paper.pdf"
    paper_path.write_bytes(b"paper")
    repository = tmp_path / "repository"
    repository.mkdir()
    readme = repository / "README.md"
    readme.write_text(
        "Evaluate SoccerNet mAP 72.4 with python evaluate.py", encoding="utf-8"
    )
    monkeypatch.setattr(
        "paper2repro.pipeline.parse_pdf",
        lambda path: [
            PaperChunk(page=1, text="The method reaches 72.4 mAP on SoccerNet.")
        ],
    )
    client = CountingClient()
    cache_dir = tmp_path / "cache"

    first = analyze(
        paper_path, repository, client, model_name="fake-v1", cache_dir=cache_dir
    )
    second = analyze(
        paper_path, repository, client, model_name="fake-v1", cache_dir=cache_dir
    )

    assert client.calls == 2
    assert first.performance.llm_request_count == 2
    assert second.performance.llm_request_count == 0
    assert second.performance.cache_hits == 2
    cache_records = list(cache_dir.glob("*.json"))
    assert len(cache_records) == 2
    assert all(
        '"metadata"' in path.read_text(encoding="utf-8") for path in cache_records
    )

    readme.write_text(
        readme.read_text(encoding="utf-8") + " Updated repository document.",
        encoding="utf-8",
    )
    third = analyze(
        paper_path, repository, client, model_name="fake-v1", cache_dir=cache_dir
    )
    assert client.calls == 3
    assert third.performance.cache_hits == 1
    assert third.performance.llm_request_count == 1

    weighted = analyze(
        paper_path,
        repository,
        client,
        model_name="fake-v1",
        cache_dir=cache_dir,
        retriever="weighted",
    )
    assert weighted.retriever == "weighted"
    assert client.calls == 4
    assert weighted.performance.cache_hits == 1
    assert weighted.performance.cache_misses == 1
    assert weighted.performance.llm_request_count == 1


def test_pipeline_call_budget_blocks_mapping_and_reuses_completed_extraction(
    tmp_path: Path, monkeypatch
) -> None:
    class CountingClient(PipelineLLMClient):
        def __init__(self):
            self.calls = 0

        def generate_structured(self, prompt, response_model):
            self.calls += 1
            return super().generate_structured(prompt, response_model)

    paper_path = tmp_path / "paper.pdf"
    paper_path.write_bytes(b"paper")
    repository = tmp_path / "repository"
    repository.mkdir()
    (repository / "README.md").write_text("SoccerNet mAP 72.4", encoding="utf-8")
    monkeypatch.setattr(
        "paper2repro.pipeline.parse_pdf",
        lambda path: [
            PaperChunk(page=1, text="The method reaches 72.4 mAP on SoccerNet.")
        ],
    )
    client = CountingClient()
    cache_dir = tmp_path / "cache"

    try:
        analyze(
            paper_path,
            repository,
            client,
            model_name="fake-v1",
            cache_dir=cache_dir,
            max_llm_calls=1,
        )
    except LLMCallBudgetExceeded:
        pass
    else:
        raise AssertionError("The mapping request should exceed the one-call budget")

    assert client.calls == 1
    assert len(list(cache_dir.glob("*.json"))) == 1

    resumed = analyze(
        paper_path,
        repository,
        client,
        model_name="fake-v1",
        cache_dir=cache_dir,
        max_llm_calls=1,
    )
    assert client.calls == 2
    assert resumed.performance.cache_hits == 1
    assert resumed.performance.llm_request_count == 1


def test_report_keeps_invalid_paper_evidence_visible(
    tmp_path: Path, monkeypatch
) -> None:
    paper_path = tmp_path / "paper.pdf"
    paper_path.write_bytes(b"mocked by parse_pdf")
    repository = tmp_path / "repository"
    repository.mkdir()
    (repository / "README.md").write_text("SoccerNet mAP 99.9", encoding="utf-8")
    monkeypatch.setattr(
        "paper2repro.pipeline.parse_pdf",
        lambda path: [PaperChunk(page=1, text="The measured score was 72.4 mAP.")],
    )

    report = analyze(paper_path, repository, InvalidPaperEvidenceClient())
    _, markdown_path = write_analysis_report(report, tmp_path / "output")

    assert not report.claims[0].paper_evidence_validation[0].is_valid
    assert "could not be anchored" in report.warnings[0]
    assert "**INVALID**" in markdown_path.read_text(encoding="utf-8")
