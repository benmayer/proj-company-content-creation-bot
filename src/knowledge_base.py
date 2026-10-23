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
# What the product is really like and how passengers see it: the material public
# replies and memes joke about. Always included for those; never for press releases
# or internal Slack, which are not about the passenger experience; otherwise on a
# topic match only (e.g. a post about cabin bags).
BACKGROUND_TYPES = ("product_policy", "public_perception")
ALWAYS_BACKGROUND_FOR = ("reply", "meme")
NEVER_BACKGROUND_FOR = ("press_release",)
NEVER_BACKGROUND_CHANNELS = ("internal slack",)
# Secondary documents are only added when they overlap the topic (or are background).
MAX_SECONDARY_DOCUMENTS = 2
FALLBACK_SECONDARY_TYPE = "market_trends"

_WORD_RE = re.compile(r"[a-z0-9]+")
# "ryanair" is on every document, so it says nothing about the topic; matching on it
# pulled every tagged document into every reply that mentions the airline. The same
# goes for words almost every airline topic contains (an airport milestone release
# matched the fee and reputation documents on "passengers" and "airport").
_STOPWORDS = frozenset(
    "a an and are as at be by for from how in into is it of on or our the to we with what why ryanair "
    "passenger passengers airport airports flight flights".split()
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
        market trends so the secondary context is never empty. Replies and
        memes always get the product and public-perception background
        (BACKGROUND_TYPES), which takes the first secondary slot; press
        releases and internal Slack never do. Source
        provenance documents (``source_register``), channel / content-type
        profiles and channel examples are never selected here.
        """

        topic_words = _words(topic)
        match_words = topic_words | _words(channel or "")
        type_key = (content_type or "").strip().lower().replace(" ", "_")
        type_words = {
            "reply": "customer feedback competitor response",
            "press_release": "announcement route promotion schedule investment",
            "post": "update route promotion customer experience",
            "meme": "social humour travel passenger",
        }.get(type_key, "")
        match_words |= _words(type_words)
        channel_key = " ".join((channel or "").lower().split())
        never_background = type_key in NEVER_BACKGROUND_FOR or channel_key in NEVER_BACKGROUND_CHANNELS
        background = () if never_background or type_key not in ALWAYS_BACKGROUND_FOR else BACKGROUND_TYPES
        skipped = BACKGROUND_TYPES if never_background else ()

        primary: List[SelectedDocument] = []
        for doc in self.primary:
            if doc.metadata.get("type") in PROFILE_TYPES + skipped:
                continue
            if doc.metadata.get("type") in ALWAYS_PRIMARY_TYPES:
                primary.append(SelectedDocument(PRIMARY, doc, "always included"))
            elif doc.metadata.get("type") in background:
                primary.append(SelectedDocument(PRIMARY, doc, f"background for every {type_key}"))
            elif _score(doc, match_words) > 0:
                primary.append(SelectedDocument(PRIMARY, doc, _matched(doc, match_words)))

        candidates = [
            d for d in self.secondary if d.metadata.get("type") not in ("source_register",) + skipped
        ]
        pinned = [
            SelectedDocument(SECONDARY, d, f"background for every {type_key}")
            for d in candidates
            if d.metadata.get("type") in background
        ]
        ranked = sorted(
            ((_score(d, topic_words | _words(type_words)), d) for d in candidates if d.metadata.get("type") not in background),
            key=lambda pair: (-pair[0], str(pair[1].source_path)),
        )
        secondary = (pinned + [
            SelectedDocument(SECONDARY, d, _matched(d, topic_words)) for s, d in ranked if s > 0
        ])[:MAX_SECONDARY_DOCUMENTS]
        if not secondary:
            secondary = [
                SelectedDocument(SECONDARY, d, "fallback: no topic match")
                for d in candidates
                if d.metadata.get("type") == FALLBACK_SECONDARY_TYPE
            ][:1]

        return SelectedContext(primary=tuple(primary), secondary=tuple(secondary))
