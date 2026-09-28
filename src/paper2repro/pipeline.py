"""End-to-end Paper2Repro analysis workflow."""

from dataclasses import asdict
from hashlib import sha256
from pathlib import Path
from time import perf_counter
from typing import Callable, Literal

from paper2repro.cache import AnalysisCache, stable_hash
from paper2repro.claims.evidence import validate_evidence
from paper2repro.claims.extractor import extract_claims
from paper2repro.llm import LLMClient
from paper2repro.mapping.assessor import assess_claim_repository
from paper2repro.models import (
    AnalysisReport,
    AuditEvidenceChecks,
    ClaimAnalysis,
    ClaimExtractionResult,
    ClaimRepositoryAssessment,
    ClaimRuntimeMetric,
    LLMRequestMetric,
    PaperEvidenceCheck,
    PerformanceMetrics,
    RepoEvidenceCheck,
)
from paper2repro.observability import CachedLLMClient, InstrumentedLLMClient
from paper2repro.pdf import parse_pdf
from paper2repro.repo.inventory import inventory_repository
from paper2repro.repo.loader import load_repository_documents
from paper2repro.repo.source import repository_source
from paper2repro.retrieval.keyword import (
    retrieve_documents,
    retrieve_documents_weighted,
)


DEFAULT_LIMITATIONS = [
    "Evidence validation checks textual anchoring, not semantic entailment.",
    "Repository retrieval is lexical and may miss relevant files.",
    "NOT_FOUND means not found in the inspected retrieved artifacts, not proven absent.",
    "Paper2Repro does not execute training, inference, or evaluation commands.",
]

CLAIM_PROMPT_VERSION = "claim-extraction-v1"
MAPPING_PROMPT_VERSION = "repository-assessment-v1"
BASELINE_RETRIEVAL_VERSION = "keyword-dataset-metric-value-v1"
WEIGHTED_RETRIEVAL_VERSION = "weighted-lexical-v1"


def _schema_hash(response_model: type) -> str:
    return stable_hash(response_model.model_json_schema())


def _sum_complete_token_usage(
    requests: list[LLMRequestMetric], field: str
) -> int | None:
    """Return a total only when every recorded request has that usage value."""
    if not requests:
        return None
    values = [getattr(request, field) for request in requests]
    if any(value is None for value in values):
        return None
    return sum(values)


def analyze(
    paper_path: Path,
    repository: str | Path,
    llm_client: LLMClient,
    *,
    top_k: int = 5,
    retriever: Literal["baseline", "weighted"] = "baseline",
    model_name: str | None = None,
    cache_dir: Path | None = None,
    max_llm_calls: int | None = None,
    progress: Callable[[str], None] | None = None,
) -> AnalysisReport:
    """Run claim extraction, repository mapping, and audit for one paper/repo pair."""
    if retriever == "baseline":
        retrieval_version = BASELINE_RETRIEVAL_VERSION
    elif retriever == "weighted":
        retrieval_version = WEIGHTED_RETRIEVAL_VERSION
    else:
        raise ValueError("retriever must be 'baseline' or 'weighted'")

    run_started = perf_counter()
    model_name = model_name or getattr(llm_client, "model", "unknown")
    observed_client = InstrumentedLLMClient(
        llm_client, model_name=model_name, max_calls=max_llm_calls
    )
    cache = AnalysisCache(cache_dir) if cache_dir is not None else None
    cached_client = CachedLLMClient(observed_client, cache)

    def report_progress(message: str) -> None:
        if progress is not None:
            progress(message)

    report_progress("[1/6] Parsing PDF...")
    started = perf_counter()
    chunks = parse_pdf(paper_path)
    pdf_parsing_seconds = perf_counter() - started

    paper_hash = stable_hash(
        [{"page": chunk.page, "text": chunk.text} for chunk in chunks]
    )
    cached_client.prepare_cache_key(
        {
            "operation": "claim_extraction",
            "paper_content_hash": paper_hash,
            "model": model_name,
            "prompt_version": CLAIM_PROMPT_VERSION,
            "schema_version": _schema_hash(ClaimExtractionResult),
        }
    )
    report_progress("[2/6] Extracting experimental claims...")
    started = perf_counter()
    extracted = extract_claims(chunks, cached_client)
    claim_extraction_seconds = perf_counter() - started
    paper_validations = validate_evidence(chunks, extracted)
    validations_by_claim: dict[int, list[PaperEvidenceCheck]] = {}
    for validation in paper_validations:
        validations_by_claim.setdefault(validation.claim_index, []).append(
            PaperEvidenceCheck(**asdict(validation))
        )

    report_progress("[3/6] Preparing repository...")
    started = perf_counter()
    with repository_source(repository) as repository_path:
        repository_preparation_seconds = perf_counter() - started
        report_progress("[4/6] Loading repository documents...")
        started = perf_counter()
        artifacts = inventory_repository(repository_path)
        documents = load_repository_documents(repository_path, artifacts)
        inventory_loading_seconds = perf_counter() - started

        claim_analyses: list[ClaimAnalysis] = []
        report_warnings: list[str] = []
        claim_runtime: list[ClaimRuntimeMetric] = []
        retrieval_seconds_total = 0.0
        for claim_index, claim in enumerate(extracted.claims, start=1):
            claim_started = perf_counter()
            report_progress(
                f"[5/6] Assessing claim {claim_index}/{len(extracted.claims)}..."
            )
            retrieval_started = perf_counter()
            if retriever == "baseline":
                retrieved = retrieve_documents(claim, documents, top_k=top_k)
            else:
                retrieved = retrieve_documents_weighted(claim, documents, top_k=top_k)
            retrieval_seconds = perf_counter() - retrieval_started
            retrieval_seconds_total += retrieval_seconds

            document_fingerprints = [
                {
                    "path": document.path,
                    "artifact_type": document.artifact_type,
                    "content_sha256": sha256(
                        document.content.encode("utf-8")
                    ).hexdigest(),
                }
                for document in retrieved
            ]
            cached_client.prepare_cache_key(
                {
                    "operation": "repository_assessment",
                    "claim_content": claim.model_dump(mode="json"),
                    "model": model_name,
                    "prompt_version": MAPPING_PROMPT_VERSION,
                    "schema_version": _schema_hash(ClaimRepositoryAssessment),
                    "retrieval_version": retrieval_version,
                    "top_k": top_k,
                    "retrieved_documents": document_fingerprints,
                }
            )
            hits_before = cached_client.cache_hits
            mapping_started = perf_counter()
            grounded = assess_claim_repository(claim, retrieved, cached_client)
            mapping_audit_seconds = perf_counter() - mapping_started
            claim_runtime.append(
                ClaimRuntimeMetric(
                    claim_index=claim_index,
                    retrieval_seconds=retrieval_seconds,
                    mapping_audit_seconds=mapping_audit_seconds,
                    total_seconds=perf_counter() - claim_started,
                    cache_hit=cached_client.cache_hits > hits_before,
                )
            )
            warnings = [
                f"Claim {claim_index}: {warning}" for warning in grounded.warnings
            ]
            report_warnings.extend(warnings)
            claim_analyses.append(
                ClaimAnalysis(
                    claim=claim,
                    paper_evidence_validation=validations_by_claim.get(
                        claim_index, []
                    ),
                    retrieved_documents=[document.path for document in retrieved],
                    mapping=grounded.assessment.mapping,
                    mapping_evidence_validation=[
                        RepoEvidenceCheck(**asdict(validation))
                        for validation in grounded.mapping_validation
                    ],
                    audit=grounded.assessment.audit,
                    audit_evidence_validation=[
                        AuditEvidenceChecks(
                            check=check,
                            evidence=[
                                RepoEvidenceCheck(**asdict(validation))
                                for validation in validations
                            ],
                        )
                        for check, validations in grounded.audit_validation.items()
                    ],
                    warnings=warnings,
                )
            )

    invalid_paper_evidence = sum(
        not check.is_valid
        for claim in claim_analyses
        for check in claim.paper_evidence_validation
    )
    if invalid_paper_evidence:
        report_warnings.insert(
            0,
            f"{invalid_paper_evidence} paper evidence excerpt(s) could not be anchored "
            "to the cited page.",
        )

    llm_requests = observed_client.requests
    performance = PerformanceMetrics(
        total_elapsed_seconds=perf_counter() - run_started,
        pdf_parsing_seconds=pdf_parsing_seconds,
        claim_extraction_seconds=claim_extraction_seconds,
        repository_preparation_seconds=repository_preparation_seconds,
        inventory_loading_seconds=inventory_loading_seconds,
        retrieval_seconds_total=retrieval_seconds_total,
        llm_request_count=observed_client.call_count,
        prompt_characters_total=sum(
            request.prompt_characters for request in llm_requests
        ),
        response_characters_total=sum(
            request.response_characters for request in llm_requests
        ),
        total_input_tokens=_sum_complete_token_usage(
            llm_requests, "total_input_tokens"
        ),
        total_output_tokens=_sum_complete_token_usage(
            llm_requests, "total_output_tokens"
        ),
        total_thought_tokens=_sum_complete_token_usage(
            llm_requests, "total_thought_tokens"
        ),
        total_cached_tokens=_sum_complete_token_usage(
            llm_requests, "total_cached_tokens"
        ),
        total_tokens=_sum_complete_token_usage(llm_requests, "total_tokens"),
        cache_hits=cached_client.cache_hits,
        cache_misses=cached_client.cache_misses,
        llm_requests=llm_requests,
        claims=claim_runtime,
    )
    return AnalysisReport(
        paper=str(paper_path),
        repository=str(repository),
        retriever=retriever,
        repository_artifact_count=len(artifacts),
        repository_document_count=len(documents),
        claims=claim_analyses,
        warnings=report_warnings,
        limitations=DEFAULT_LIMITATIONS,
        performance=performance,
    )
