# Evaluation scaffold

Paper2Repro does not ship unreviewed LLM output as gold annotations. `soccermaster_review_template.json` now contains the nine saved SoccerMaster claims and the run's candidate evidence/retrieval output. Its `candidate_output` section is model output, not gold. Fill only the separate `human_review` fields after checking the paper and repository.

Suggested metrics:

- claim extraction precision and recall against human-selected atomic claims
- paper evidence valid rate and citation-page accuracy
- repository retrieval Recall@k against human-identified relevant files
- repository evidence valid rate
- agreement between audit statuses and human review

The template separates candidate model output from human decisions so generated labels cannot be mistaken for ground truth.

## Offline retrieval evaluation

Compare the existing baseline and weighted lexical retrievers on fixed file-level
labels, without calling Gemini or downloading repositories:

```bash
uv run --offline python scripts/evaluate_retrieval.py \
  --dataset evals/retrieval_sample/dataset.json \
  --top-k 1 3 5 10 \
  --output outputs/retrieval-sample
```

The bundled four-document repository and three queries are synthetic fixtures,
not research results. The evaluator writes JSON and Markdown with per-query
rankings, macro averages, label coverage, warnings, and separate repo loading /
retrieval timings. Precision@k always divides by k. Unindexed relevant paths stay
in the recall denominator.

See [日本語の仕様とデータ作成手順](../docs/RETRIEVAL_EVALUATION_JA.md) for the
JSON format, gold/silver distinctions, timing policy, and limitations. The saved
SoccerMaster review template is not automatically treated as a labeled dataset.
