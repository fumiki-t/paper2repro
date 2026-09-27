# Evaluation scaffold

Paper2Repro does not ship unreviewed LLM output as gold annotations. Use `soccermaster_review_template.json` as a human annotation template, then add reviewed examples from additional papers.

Suggested metrics:

- claim extraction precision and recall against human-selected atomic claims
- paper evidence valid rate and citation-page accuracy
- repository retrieval Recall@k against human-identified relevant files
- repository evidence valid rate
- agreement between audit statuses and human review

The template separates candidate model output from human decisions so generated labels cannot be mistaken for ground truth.
