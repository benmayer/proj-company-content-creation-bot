"""Command-line entry point for the review-gated content pipeline."""

from __future__ import annotations

import argparse
import mimetypes
import sys
from pathlib import Path
from typing import List, Optional

# Support both ``python -m src.main`` and running this file directly from an
# IDE. The latter does not automatically put the project root on sys.path.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.content_pipeline import ContentPipeline, ContentRequest, PipelineError, request_problem
from src.channel_profiles import CHANNELS, CONTENT_TYPES


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create a reviewable company content draft.")
    parser.add_argument("--content-type", choices=CONTENT_TYPES, required=True)
    parser.add_argument("--channel", choices=CHANNELS, default="LinkedIn")
    parser.add_argument("--topic", default="", help="What the content should communicate (not for replies).")
    parser.add_argument("--original", default="", help="Reply only: the text of the post to reply to.")
    parser.add_argument("--screenshot", type=Path, help="Reply only: a screenshot of the post to reply to.")
    return parser


def _request(args: argparse.Namespace) -> ContentRequest:
    screenshot, screenshot_type = b"", ""
    if args.screenshot:
        screenshot = args.screenshot.read_bytes()
        screenshot_type = mimetypes.guess_type(args.screenshot.name)[0] or ""
    return ContentRequest(args.content_type, args.topic, args.channel, args.original, screenshot, screenshot_type)


def main(argv: Optional[List[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    request = _request(args)
    problem = request_problem(request)
    if problem:
        print(problem)
        return 2
    pipeline = ContentPipeline()
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
