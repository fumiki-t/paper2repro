# Evaluation scaffold

Paper2Repro does not ship unreviewed LLM output as gold annotations. `soccermaster_review_template.json` now contains the nine saved SoccerMaster claims and the run's candidate evidence/retrieval output. Its `candidate_output` section is model output, not gold. Fill only the separate `human_review` fields after checking the paper and repository.

Suggested metrics:

- claim extraction precision and recall against human-selected atomic claims
- paper evidence valid rate and citation-page accuracy
- repository retrieval Recall@k against human-identified relevant files
- repository evidence valid rate
- agreement between audit statuses and human review

The template separates candidate model output from human decisions so generated labels cannot be mistaken for ground truth.
