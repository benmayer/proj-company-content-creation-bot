"""Command-line entry point for the review-gated content pipeline."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional

# Support both ``python -m src.main`` and running this file directly from an
# IDE. The latter does not automatically put the project root on sys.path.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.content_pipeline import ContentPipeline, ContentRequest, PipelineError
from src.channel_profiles import CHANNELS, CONTENT_TYPES


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create a reviewable company content draft.")
    parser.add_argument("--content-type", choices=CONTENT_TYPES + ("social_post", "campaign_brief"), required=True)
    parser.add_argument("--product", required=True)
    parser.add_argument("--topic", required=True)
    parser.add_argument("--channel", choices=CHANNELS, default="LinkedIn")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    pipeline = ContentPipeline()
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
