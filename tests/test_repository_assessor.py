from paper2repro.mapping.assessor import AUDIT_CHECKS, assess_claim_repository
from paper2repro.models import (
    AuditItem,
    ClaimRepositoryAssessment,
    ClaimRepositoryMapping,
    ExperimentalClaim,
    RepoDocument,
    RepoEvidence,
)


class StubLLMClient:
    def __init__(self, response: ClaimRepositoryAssessment) -> None:
        self.response = response
        self.prompt = ""

    def generate_structured(self, prompt, response_model):
        self.prompt = prompt
        assert response_model is ClaimRepositoryAssessment
        return self.response


def _claim() -> ExperimentalClaim:
    return ExperimentalClaim(
        statement="The model reaches 72.4 mAP on SoccerNet.",
        evidence=[],
        dataset="SoccerNet",
        metric="mAP",
        reported_value="72.4",
    )


def _document() -> RepoDocument:
    return RepoDocument(
        path="README.md",
        artifact_type="readme",
        content="Evaluate on SoccerNet with mAP using python evaluate.py.",
    )


def _evidence(excerpt: str, path: str = "README.md") -> RepoEvidence:
    return RepoEvidence(path=path, artifact_type="readme", excerpt=excerpt)


def test_assessor_uses_only_supplied_documents_and_grounds_output() -> None:
    response = ClaimRepositoryAssessment(
        mapping=ClaimRepositoryMapping(
            status="SUPPORTED",
            evidence=[_evidence("Evaluate on SoccerNet with mAP")],
            explanation="Evaluation instructions are present.",
        ),
        audit=[
            AuditItem(
                check="evaluation_protocol_metric",
                status="PRESENT",
                evidence=[_evidence("mAP using python evaluate.py")],
                notes="The metric and command are shown.",
            )
        ],
    )
    client = StubLLMClient(response)

    grounded = assess_claim_repository(_claim(), [_document()], client)

    assert grounded.assessment.mapping.status == "SUPPORTED"
    assert grounded.mapping_validation[0].is_valid
    assert len(grounded.assessment.audit) == len(AUDIT_CHECKS)
    assert "[DOCUMENT path=README.md type=readme]" in client.prompt
    assert "unseen.txt" not in client.prompt


def test_assessor_downgrades_unanchored_mapping_and_present_audit() -> None:
    invented = _evidence("score: 99.9", path="invented.yaml")
    response = ClaimRepositoryAssessment(
        mapping=ClaimRepositoryMapping(
            status="SUPPORTED",
            evidence=[invented],
            explanation="Invented evidence.",
        ),
        audit=[
            AuditItem(
                check="checkpoint",
                status="PRESENT",
                evidence=[invented],
                notes="Invented checkpoint.",
            )
        ],
    )

    grounded = assess_claim_repository(
        _claim(), [_document()], StubLLMClient(response)
    )

    assert grounded.assessment.mapping.status == "UNSUPPORTED"
    checkpoint = next(
        item for item in grounded.assessment.audit if item.check == "checkpoint"
    )
    assert checkpoint.status == "AMBIGUOUS"
    assert not grounded.mapping_validation[0].is_valid
    assert any("path_not_retrieved" in warning for warning in grounded.warnings)


def test_assessor_skips_llm_when_retrieval_is_empty() -> None:
    class FailingClient:
        def generate_structured(self, prompt, response_model):
            raise AssertionError("LLM should not be called")

    grounded = assess_claim_repository(_claim(), [], FailingClient())

    assert grounded.assessment.mapping.status == "UNSUPPORTED"
    assert all(item.status == "NOT_FOUND" for item in grounded.assessment.audit)
