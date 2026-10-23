"""Command-line entry point for the review-gated content pipeline."""

from __future__ import annotations

import argparse
from typing import List, Optional

from src.content_pipeline import ContentPipeline, ContentRequest, PipelineError


def _mock_generator(prompt: str, client: object = None) -> str:
    """Return a deterministic draft for a local demo without an API key."""
    return "Draft generated from approved company context.\n\nHUMAN REVIEW NOTES\n- Verify the final wording before approval."


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create a reviewable company content draft.")
    parser.add_argument("--content-type", choices=("social_post", "campaign_brief"), required=True)
    parser.add_argument("--product", required=True)
    parser.add_argument("--topic", required=True)
    parser.add_argument("--channel", default="social")
    parser.add_argument("--mock", action="store_true", help="Use a deterministic local LLM response.")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    generator = _mock_generator if args.mock else None
    pipeline = ContentPipeline(draft_generator=generator or ContentPipeline().draft_generator)
    request = ContentRequest(args.content_type, args.product, args.topic, args.channel)
    print("Generating draft for human review...\n")
    try:
        result = pipeline.run(
            request,
            approve=lambda draft: input(f"{draft}\n\nApprove this draft? [y/N] ").strip().lower() == "y",
            feedback=lambda _draft: input("What should be changed? ").strip(),
        )
    except (PipelineError, RuntimeError) as exc:
        print(f"Pipeline failed: {exc}")
        return 1
    print(f"Approved draft saved to {result.output_path} after {result.iterations} iteration(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
