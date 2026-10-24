"""Compare channel-specific drafts with a generic prompt on the same model (MUST-08 evidence).

Run from the repo root:  python evidence/voice_check.py [--model MODEL]

For each case it drafts once through the pipeline and once from a plain
"write a Ryanair post" prompt, runs the measurable rules from the channel
profiles on both, and writes ``evidence/voice/comparison_<model>.md``. It uses a
throwaway feedback store and calls the LLM twice per case. The posts being
replied to are test inputs written by the team, not real customer posts.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import io
import os
from pathlib import Path
import re
import sys
import tempfile
from typing import Callable, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PIL import Image, ImageDraw, ImageFont  # noqa: E402  (installed with streamlit)

from src.channel_profiles import content_type_label  # noqa: E402
from src.content_pipeline import ContentPipeline, ContentRequest, PipelineError  # noqa: E402
from src.feedback_store import FeedbackStore, FileBackend  # noqa: E402
from src.llm_integration import generate_draft, load_config  # noqa: E402

OUTPUT_DIR = ROOT / "evidence" / "voice"
_EMOJI_RE = re.compile("[\U0001F000-\U0001FAFF☀-➿⬀-⯿]")
_APOLOGY_RE = re.compile(r"\b(sorry|apologi[sz]e|apologies|inconvenience)\b", re.IGNORECASE)

Check = Tuple[str, Callable[[str], bool]]


def _words(text: str) -> int:
    return len(text.split())


def max_words(limit: int, first_line_only: bool = False) -> Check:
    scope = "line 1" if first_line_only else "draft"
    return (
        f"{scope} ≤ {limit} words",
        lambda text: _words(text.strip().splitlines()[0] if first_line_only else text) <= limit,
    )


NO_EMOJI: Check = ("no emoji", lambda text: not _EMOJI_RE.search(text))
NO_HASHTAG: Check = ("no hashtag", lambda text: not re.search(r"#\w", text))
LOWERCASE: Check = ("lowercase", lambda text: text == text.lower())
NO_APOLOGY: Check = ("no apology", lambda text: not _APOLOGY_RE.search(text))
IMAGE_LINE: Check = ("has [image: …] line", lambda text: "[image:" in text.lower())
ENDS_LINE: Check = ("ends with ENDS", lambda text: text.strip().endswith("ENDS"))
NO_ENDS_LINE: Check = ("no ENDS line", lambda text: "ENDS" not in text)
QUOTE_PLACEHOLDER: Check = ("quote left as placeholder", lambda text: "QUOTE: TO BE SUPPLIED" in text.upper())
FEW_HASHTAGS: Check = ("≤ 3 hashtags", lambda text: len(re.findall(r"#\w", text)) <= 3)

REPLY_CHECKS = [LOWERCASE, max_words(15), NO_EMOJI, NO_HASHTAG, NO_APOLOGY]
MEME_CHECKS = [max_words(15, first_line_only=True), IMAGE_LINE, NO_EMOJI, NO_HASHTAG]


@dataclass(frozen=True)
class Case:
    request: ContentRequest
    checks: Sequence[Check]
    note: str = ""


def _screenshot(handle: str, text: str) -> bytes:
    """A plain image of a social post, to exercise the screenshot path."""

    image = Image.new("RGB", (900, 260), "white")
    draw = ImageDraw.Draw(image)
    draw.text((40, 40), handle, fill="#536471", font=ImageFont.load_default(size=26))
    draw.text((40, 100), text, fill="black", font=ImageFont.load_default(size=34))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


SCREENSHOT = _screenshot("@test_passenger · 2h", "@Ryanair why is my 'window seat' a wall??")

CASES: List[Case] = [
    Case(ContentRequest("reply", channel="X", original_content=(
        "ryanair delayed my flight 3 hours and still sold me a 4 euro coffee. never again"
    )), REPLY_CHECKS),
    Case(ContentRequest("reply", channel="X", screenshot=SCREENSHOT, screenshot_type="image/png"), REPLY_CHECKS,
         "Screenshot only. The image reads: \"@Ryanair why is my 'window seat' a wall??\""),
    Case(ContentRequest("reply", channel="X", original_content="https://x.com/test_passenger/status/1"), REPLY_CHECKS,
         "Link only: the pipeline should refuse before calling the model."),
    Case(ContentRequest("reply", channel="Instagram", original_content=(
        "can you guys please stop putting me in the middle seat every single time"
    )), REPLY_CHECKS),
    Case(ContentRequest("post", "cabin bag sizes", "X"), [max_words(25), NO_EMOJI, NO_HASHTAG]),
    Case(ContentRequest("meme", "the middle seat", "X"), MEME_CHECKS),
    Case(ContentRequest("post", "the first sunny weekend of spring and city breaks", "Instagram"),
         [IMAGE_LINE, NO_EMOJI, NO_HASHTAG]),
    Case(ContentRequest("meme", "people who stand up the second the plane lands", "Instagram"), MEME_CHECKS),
    Case(ContentRequest("post", "Ryanair has flown 15 million passengers through Oslo Torp airport since 1997", "LinkedIn"),
         [FEW_HASHTAGS]),
    Case(ContentRequest(
        "press_release", "Ryanair has flown 15 million passengers through Oslo Torp airport since 1997", "LinkedIn",
    ), [ENDS_LINE, QUOTE_PLACEHOLDER]),
    Case(ContentRequest("press_release", (
        "the new crew rostering app goes live on Monday; crew must log in once before their next duty; "
        "questions go to the ops support channel"
    ), "internal Slack"), [NO_ENDS_LINE, max_words(150)]),
    Case(ContentRequest("meme", "6am report times", "internal Slack"), MEME_CHECKS),
]


def _baseline_prompt(request: ContentRequest) -> str:
    """What someone would type into a generic chatbot, with no brand context."""

    if request.content_type == "reply":
        if request.original_content:
            return f"Write a reply from Ryanair's {request.channel} account to this post: {request.original_content}"
        return f"Write a reply from Ryanair's {request.channel} account to the post in this screenshot."
    label = content_type_label(request.content_type, request.channel)
    return f"Write a {label} for Ryanair's {request.channel} about: {request.topic}"


def _images(request: ContentRequest) -> Tuple[Tuple[str, bytes], ...]:
    return ((request.screenshot_type, request.screenshot),) if request.screenshot else ()


def _results(text: str, checks: Sequence[Check]) -> List[Tuple[str, bool]]:
    return [(name, check(text)) for name, check in checks]


def _score(results: Sequence[Tuple[str, bool]]) -> str:
    return f"{sum(ok for _, ok in results)}/{len(results)}"


def _describe(request: ContentRequest) -> str:
    if request.content_type != "reply":
        return f"Topic: {request.topic}"
    parts = []
    if request.original_content:
        parts.append(f"Post: {request.original_content}")
    if request.screenshot:
        parts.append("Post: (screenshot attached)")
    return " · ".join(parts)


def _block(text: str) -> str:
    return "```\n" + text.strip() + "\n```"


def run(model: Optional[str]) -> Path:
    if model:
        os.environ["LLM_MODEL"] = model
    model_name = load_config().model
    rows, sections = [], []
    with tempfile.TemporaryDirectory() as directory:
        store = FeedbackStore(FileBackend(Path(directory) / "feedback.jsonl"))
        pipeline = ContentPipeline(output_dir=directory, feedback_store=store)
        for number, case in enumerate(CASES, start=1):
            request = case.request
            title = f"{request.channel}: {content_type_label(request.content_type, request.channel)}"
            print(f"[{number}/{len(CASES)}] {title}")
            try:
                ours = pipeline.draft(request, pipeline.monitor(request))
            except PipelineError as exc:
                rows.append(f"| {number} | {title} | refused: {exc} | n/a |")
                sections.append(
                    f"## {number}. {title}\n\n{_describe(request)}\n\n{case.note}\n\n"
                    f"**Pipeline:** refused before calling the model: {exc}\n\n"
                    "**Generic prompt:** not run; a generic chatbot would receive only the URL."
                )
                continue
            baseline = generate_draft(_baseline_prompt(request), images=_images(request))
            ours_checks, base_checks = _results(ours, case.checks), _results(baseline, case.checks)
            rows.append(f"| {number} | {title} | {_score(ours_checks)} | {_score(base_checks)} |")
            check_lines = "\n".join(
                f"| {name} | {'✅' if a else '❌'} | {'✅' if b else '❌'} |"
                for (name, a), (_, b) in zip(ours_checks, base_checks)
            )
            sections.append(
                f"## {number}. {title}\n\n{_describe(request)}\n\n{case.note}\n\n"
                f"**Pipeline (KB voice rules + examples):**\n\n{_block(ours)}\n\n"
                f"**Generic prompt** (`{_baseline_prompt(request)}`):\n\n{_block(baseline)}\n\n"
                f"| Check | Pipeline | Generic |\n| --- | --- | --- |\n{check_lines}"
            )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output = OUTPUT_DIR / f"comparison_{model_name}.md"
    output.write_text(
        f"# Channel voice: pipeline vs generic prompt ({model_name})\n\n"
        "Generated by `evidence/voice_check.py`. Each case is drafted twice with the same model: once through the "
        "pipeline (channel and content-type rules from `knowledge_base/primary/`, verbatim past examples, KB context) "
        "and once from a one-line generic prompt. The checks are the measurable rules from the channel profiles; "
        "tone still needs a human read. Posts being replied to are team-written test inputs.\n\n"
        "| # | Channel and type | Pipeline checks passed | Generic checks passed |\n| --- | --- | --- | --- |\n"
        + "\n".join(rows) + "\n\n" + "\n\n".join(sections) + "\n",
        encoding="utf-8",
    )
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--model", help="Override LLM_MODEL for this run, e.g. to compare models.")
    output = run(parser.parse_args().model)
    print(f"Wrote {output.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
