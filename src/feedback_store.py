"""Store approved and declined drafts and select them as learned feedback.

Learning works by injection, not training: the latest reviewer decisions for the
same channel and content type are rendered into a labelled prompt block. Learned
feedback is style guidance only and is never part of the primary or secondary
knowledge base.

Feedback lives in one JSONL file. Set ``FEEDBACK_STORE_PATH`` to a path on a
mounted persistent disk (e.g. Render) so it survives redeploys.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
from typing import List, Mapping, Optional, Tuple, Union

from dotenv import load_dotenv

from src.prompt_templates import NO_LEARNED_FEEDBACK

PathLike = Union[str, Path]

APPROVED = "approved"
DECLINED = "declined"
# Models vary the formatting: "HUMAN REVIEW NOTES", "**HUMAN REVIEW NOTES:**", "---" separators, a bold label line.
_REVIEW_NOTES_RE = re.compile(r"^\W*HUMAN REVIEW NOTES", re.IGNORECASE | re.MULTILINE)
_LEADING_LABEL_RE = re.compile(r"^\s*\*\*[^\n*]*:\*\*[ \t]*\n")
_MAX_EXAMPLE_CHARS = 800


class FeedbackStoreError(RuntimeError):
    """Raised when feedback cannot be read from or written to its storage."""


@dataclass(frozen=True)
class FeedbackEvent:
    """One reviewer decision on a draft."""

    outcome: str
    channel: str
    content_type: str
    product: str
    topic: str
    draft: str
    reason: str
    created_at: str


@dataclass(frozen=True)
class LearnedFeedback:
    """Feedback selected for one channel and content type."""

    approved: Tuple[FeedbackEvent, ...] = ()
    declined: Tuple[FeedbackEvent, ...] = ()

    def render(self) -> str:
        """Render the labelled prompt block, or a placeholder when empty."""
        if not self.approved and not self.declined:
            return NO_LEARNED_FEEDBACK
        parts = [
            "Past reviewer decisions for this channel and type. These are style and tone "
            "preferences only. They are not company facts and must not be cited as support for a claim."
        ]
        if self.approved:
            parts.append("Approved drafts (imitate the style, do not reuse their claims):")
            for number, event in enumerate(self.approved, start=1):
                parts.append(f"{number}. {_example_text(event.draft)}")
        if self.declined:
            parts.append("Declined drafts (avoid these problems):")
            for number, event in enumerate(self.declined, start=1):
                parts.append(f"{number}. {event.reason}")
        return "\n".join(parts)


def _example_text(draft: str) -> str:
    notes = _REVIEW_NOTES_RE.search(draft)
    text = draft[: notes.start()] if notes else draft
    text = _LEADING_LABEL_RE.sub("", text).strip().rstrip("-*_# \n")
    if len(text) > _MAX_EXAMPLE_CHARS:
        text = text[:_MAX_EXAMPLE_CHARS].rstrip() + "..."
    return text


def _key(value: str) -> str:
    return value.strip().casefold().replace("_", " ")


class FileBackend:
    """Append-only JSONL file; point it at a persistent disk to survive redeploys."""

    def __init__(self, path: PathLike) -> None:
        self.path = Path(path)

    def read_text(self) -> str:
        try:
            return self.path.read_text(encoding="utf-8") if self.path.is_file() else ""
        except OSError as exc:
            raise FeedbackStoreError(f"Cannot read feedback file {self.path}: {exc}") from exc

    def append(self, line: str) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        except OSError as exc:
            raise FeedbackStoreError(f"Cannot write feedback file {self.path}: {exc}") from exc

    def describe(self) -> str:
        return str(self.path)


class FeedbackStore:
    """Record reviewer decisions and select the latest ones for a channel and type."""

    def __init__(self, backend: FileBackend) -> None:
        self.backend = backend

    @classmethod
    def from_env(cls, default_path: PathLike, env: Optional[Mapping[str, str]] = None) -> "FeedbackStore":
        """Use ``FEEDBACK_STORE_PATH`` if set, otherwise ``default_path``."""
        if env is None:
            load_dotenv()  # the store is built before the first LLM call loads .env
            env = os.environ
        return cls(FileBackend(env.get("FEEDBACK_STORE_PATH", "").strip() or default_path))

    def record(
        self,
        outcome: str,
        channel: str,
        content_type: str,
        product: str,
        topic: str,
        draft: str,
        reason: str = "",
    ) -> FeedbackEvent:
        if outcome not in {APPROVED, DECLINED}:
            raise FeedbackStoreError(f"Unknown feedback outcome: {outcome}")
        event = FeedbackEvent(
            outcome=outcome,
            channel=channel,
            content_type=content_type,
            product=product,
            topic=topic,
            draft=draft.strip(),
            reason=reason.strip(),
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self.backend.append(json.dumps(asdict(event), sort_keys=True))
        return event

    def events(self) -> List[FeedbackEvent]:
        """All stored events, oldest first. Malformed lines are skipped."""
        events = []
        for line in self.backend.read_text().splitlines():
            if not line.strip():
                continue
            try:
                events.append(FeedbackEvent(**json.loads(line)))
            except (TypeError, ValueError):
                continue
        return events

    def select(
        self,
        channel: str,
        content_type: str,
        approved_limit: int = 2,
        declined_limit: int = 3,
    ) -> LearnedFeedback:
        """Latest approved drafts and decline reasons for the same channel and type."""
        matching = [
            event
            for event in self.events()
            if _key(event.channel) == _key(channel) and _key(event.content_type) == _key(content_type)
        ]
        approved = [event for event in matching if event.outcome == APPROVED]
        declined = [event for event in matching if event.outcome == DECLINED and event.reason]
        return LearnedFeedback(
            approved=tuple(reversed(approved[-approved_limit:])) if approved_limit > 0 else (),
            declined=tuple(reversed(declined[-declined_limit:])) if declined_limit > 0 else (),
        )
