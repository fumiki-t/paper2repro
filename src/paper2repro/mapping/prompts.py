"""Prompt construction for repository mapping and audit."""

from paper2repro.models import ExperimentalClaim, RepoDocument


def build_repository_assessment_prompt(
    claim: ExperimentalClaim, documents: list[RepoDocument]
) -> str:
    """Present one claim and only its retrieved repository documents."""
    document_text = "\n\n".join(
        (
            f"[DOCUMENT path={document.path} type={document.artifact_type}]\n"
            f"{document.content}"
        )
        for document in documents
    )
    return f"""Assess whether the retrieved repository documents contain information
relevant to reproducing this experimental claim.

Claim:
{claim.model_dump_json(indent=2)}

Mapping status meanings:
- SUPPORTED: retrieved documents contain validated, actionable evidence relevant
  to reproducing the claim. This does not mean the claim was reproduced.
- PARTIALLY_SUPPORTED: some relevant information exists but important information
  is incomplete or ambiguous.
- UNSUPPORTED: the supplied documents do not provide relevant evidence.

Complete these seven audit checks exactly once: dataset_data_preparation,
model_config, checkpoint, training_or_inference_command,
environment_dependencies, random_seed, evaluation_protocol_metric.
Use PRESENT only when an exact repository excerpt supports the item. Use
AMBIGUOUS when related text exists but is incomplete. Use NOT_FOUND when the
supplied retrieved documents do not show it; NOT_FOUND does not prove absence
from the entire repository.

Every evidence path must exactly match a supplied document path. Every excerpt
must be a short verbatim substring copied from that document. Never invent paths
or paraphrase excerpts. Use an empty evidence list when no excerpt is available.

Retrieved documents:
{document_text}"""
