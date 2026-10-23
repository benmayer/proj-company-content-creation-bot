"""Load the primary and secondary knowledge bases and select context for a request.

Selection is deterministic (no RAG, see rag_decision.md): documents are chosen
by frontmatter ``type`` and ``tags`` plus word overlap with the request topic,
and returned whole. Primary (company) and secondary (industry) documents are
kept in separate fields so they can never be presented as the same thing.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import FrozenSet, List, Optional, Tuple, Union

from src.document_processor import Document, ingest_directory


PathLike = Union[str, Path]

DEFAULT_ROOT = Path(__file__).resolve().parent.parent / "knowledge_base"

PRIMARY = "primary"
SECONDARY = "secondary"

# Primary documents every draft needs, whatever the topic.
ALWAYS_PRIMARY_TYPES = ("brand_voice", "company_profile", "editorial_guardrails")
# Documents rendered in their own prompt blocks (VOICE RULES, GUARDRAILS), not under PRIMARY CONTEXT.
BRAND_VOICE_TYPE = "brand_voice"
GUARDRAILS_TYPE = "editorial_guardrails"
VOICE_RULE_TYPES = (BRAND_VOICE_TYPE, GUARDRAILS_TYPE)
# Team editorial profiles and verbatim channel examples, looked up by channel /
# content type (see channel_profiles.py), never selected by topic.
CHANNEL_PROFILE_TYPE = "channel_profile"
CONTENT_TYPE_PROFILE_TYPE = "content_type_profile"
CHANNEL_EXAMPLES_TYPE = "channel_examples"
PROFILE_TYPES = (CHANNEL_PROFILE_TYPE, CONTENT_TYPE_PROFILE_TYPE, CHANNEL_EXAMPLES_TYPE)
# Secondary documents are only added when they overlap the topic.
MAX_SECONDARY_DOCUMENTS = 2
FALLBACK_SECONDARY_TYPE = "market_trends"

_WORD_RE = re.compile(r"[a-z0-9]+")
# "ryanair" is on every document, so it says nothing about the topic; matching on it
# pulled every tagged document into every reply that mentions the airline.
_STOPWORDS = frozenset(
    "a an and are as at be by for from how in into is it of on or our the to we with what why ryanair".split()
)


@dataclass(frozen=True)
class SelectedDocument:
    """A whole document chosen for a request, labelled with its source kind."""

    source_kind: str
    document: Document
    reason: str

    @property
    def title(self) -> str:
        return str(self.document.metadata.get("title", self.document.source_path.stem))


@dataclass(frozen=True)
class SelectedContext:
    """Context for one request; primary and secondary are never mixed."""

    primary: Tuple[SelectedDocument, ...]
    secondary: Tuple[SelectedDocument, ...]

    def render(self) -> str:
        """Render labelled prompt context with company facts and industry context apart."""

        def block(heading: str, selected: Tuple[SelectedDocument, ...]) -> str:
            parts = [f"# {heading}"]
            for item in selected:
                parts.append(f"## Source: {item.title} ({item.document.source_path.name})")
                for section in item.document.sections:
                    parts.append(f"### {section.heading}\n{section.body}")
            return "\n\n".join(parts)

        return "\n\n".join(
            [
                block("PRIMARY: company facts and brand guidance", self.primary),
                block("SECONDARY: industry context, not company fact", self.secondary),
            ]
        )


def _words(text: str) -> FrozenSet[str]:
    return frozenset(w for w in _WORD_RE.findall(text.lower()) if w not in _STOPWORDS and len(w) > 2)


def _tag_words(document: Document) -> FrozenSet[str]:
    tags = document.metadata.get("tags") or []
    return frozenset(w for tag in tags for w in _WORD_RE.findall(str(tag).lower()))


def _text_words(document: Document) -> FrozenSet[str]:
    meta = document.metadata
    return _words(f"{meta.get('title', '')} {meta.get('description', '')}")


def _score(document: Document, topic_words: FrozenSet[str]) -> int:
    """Tag matches count double; title/description matches count once."""

    return 2 * len(topic_words & _tag_words(document)) + len(topic_words & _text_words(document))


def _matched(document: Document, topic_words: FrozenSet[str]) -> str:
    hits = sorted(topic_words & (_tag_words(document) | _text_words(document)))
    return "matches topic: " + ", ".join(hits)


class KnowledgeBase:
    """Both knowledge bases, loaded once and kept separate."""

    def __init__(self, primary: List[Document], secondary: List[Document]) -> None:
        self.primary = primary
        self.secondary = secondary

    @classmethod
    def load(cls, root: Optional[PathLike] = None) -> "KnowledgeBase":
        base = Path(root) if root is not None else DEFAULT_ROOT
        return cls(
            primary=ingest_directory(base / PRIMARY),
            secondary=ingest_directory(base / SECONDARY),
        )

    def select(
        self,
        topic: str,
        channel: Optional[str] = None,
        content_type: Optional[str] = None,
    ) -> SelectedContext:
        """Select context for a topic, channel and content type.

        Primary: the always-needed brand and guardrail documents, plus any
        other primary document matching the topic or channel. Secondary: the
        best topic matches (up to MAX_SECONDARY_DOCUMENTS), falling back to
        market trends so the secondary context is never empty. Source
        provenance documents (``source_register``), channel / content-type
        profiles and channel examples are never selected here.
        """

        topic_words = _words(topic)
        match_words = topic_words | _words(channel or "")
        type_words = {
            "reply": "customer feedback competitor response",
            "press_release": "announcement route promotion schedule investment",
            "post": "update route promotion customer experience",
            "meme": "social humour travel passenger",
        }.get((content_type or "").strip().lower().replace(" ", "_"), "")
        match_words |= _words(type_words)

        primary: List[SelectedDocument] = []
        for doc in self.primary:
            if doc.metadata.get("type") in PROFILE_TYPES:
                continue
            if doc.metadata.get("type") in ALWAYS_PRIMARY_TYPES:
                primary.append(SelectedDocument(PRIMARY, doc, "always included"))
            elif _score(doc, match_words) > 0:
                primary.append(SelectedDocument(PRIMARY, doc, _matched(doc, match_words)))

        candidates = [d for d in self.secondary if d.metadata.get("type") != "source_register"]
        ranked = sorted(
            ((_score(d, topic_words | _words(type_words)), d) for d in candidates),
            key=lambda pair: (-pair[0], str(pair[1].source_path)),
        )
        secondary = [
            SelectedDocument(SECONDARY, d, _matched(d, topic_words)) for s, d in ranked if s > 0
        ][:MAX_SECONDARY_DOCUMENTS]
        if not secondary:
            secondary = [
                SelectedDocument(SECONDARY, d, "fallback: no topic match")
                for d in candidates
                if d.metadata.get("type") == FALLBACK_SECONDARY_TYPE
            ][:1]

        return SelectedContext(primary=tuple(primary), secondary=tuple(secondary))
