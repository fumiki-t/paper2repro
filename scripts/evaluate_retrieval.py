"""Compare existing lexical retrievers locally, with no provider or download step."""

import argparse
import json
from pathlib import Path
import sys

from pydantic import ValidationError

from paper2repro.retrieval.evaluation import (
    evaluate_retrieval,
    render_evaluation_markdown,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--top-k", nargs="+", type=int, default=[1, 3, 5, 10])
    parser.add_argument(
        "--output", type=Path, default=Path("outputs/retrieval-evaluation")
    )
    args = parser.parse_args()
    try:
        result = evaluate_retrieval(args.dataset, args.top_k)
        markdown = render_evaluation_markdown(result)
        args.output.mkdir(parents=True, exist_ok=True)
        json_path = args.output / "evaluation.json"
        markdown_path = args.output / "evaluation.md"
        json_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        markdown_path.write_text(markdown, encoding="utf-8")
    except ValidationError as error:
        # Do not echo the complete input JSON or claim content in an error.
        messages = [
            f"{'.'.join(map(str, item['loc']))}: {item['msg']}" for item in error.errors()
        ]
        parser.error("Invalid evaluation set: " + "; ".join(messages))
    except (OSError, ValueError) as error:
        parser.error(str(error))
    for warning in result["warnings"]:
        print(f"WARNING: {warning}", file=sys.stderr)
    coverage = result["coverage"]
    print(
        f"Queries: {result['query_count']}; labels: {result['label_type']}; LLM/API calls: 0"
    )
    print(
        f"Indexed relevant paths: {coverage['indexed_relevant_count']} / "
        f"{coverage['total_relevant_count']}"
    )
    print(f"JSON: {json_path}\nMarkdown: {markdown_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
