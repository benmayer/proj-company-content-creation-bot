"""Channel and content-type rules, read from profile documents in the primary KB.

The wording lives in ``knowledge_base/primary/channel_*.md``,
``content_type_*.md`` and ``past_content/examples_*.md`` so it can be edited as
Markdown. This module only looks the sections up; it holds no editorial text of
its own. Files are read on every call (they are small), so edits apply without
restarting the app.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple

from src.document_processor import Document, ingest_document
from src.knowledge_base import (
    CHANNEL_EXAMPLES_TYPE,
    CHANNEL_PROFILE_TYPE,
    CONTENT_TYPE_PROFILE_TYPE,
    DEFAULT_ROOT,
    PRIMARY,
)


CHANNELS: Tuple[str, ...] = ("LinkedIn", "Instagram", "X", "internal Slack")
CONTENT_TYPES: Tuple[str, ...] = ("post", "reply", "meme", "press_release")


@dataclass(frozen=True)
class ChannelProfile:
    """Tone, format and offered content types for one publishing channel."""

    name: str
    tone: str
    format: str
    content_types: Tuple[str, ...]
    source: str


def _channel_key(channel: str) -> str:
    key = " ".join(channel.strip().lower().split())
    # ``social`` was the pre-ticket pipeline default; keep old CLI callers working.
    return "linkedin" if key == "social" else key


def _content_type_key(content_type: str) -> str:
    return content_type.strip().lower().replace(" ", "_")


def _profile_documents(root: Path) -> Dict[Tuple[str, str], Document]:
    """Load every profile and example document, keyed by (type, channel or content type)."""

    documents: Dict[Tuple[str, str], Document] = {}
    for pattern, doc_type, field, normalise in (
        ("channel_*.md", CHANNEL_PROFILE_TYPE, "channel", _channel_key),
        ("content_type_*.md", CONTENT_TYPE_PROFILE_TYPE, "content_type", _content_type_key),
        ("past_content/examples_*.md", CHANNEL_EXAMPLES_TYPE, "channel", _channel_key),
    ):
        for path in sorted((root / PRIMARY).glob(pattern)):
            document = ingest_document(path)
            if document.metadata.get("type") != doc_type or not document.metadata.get(field):
                raise ValueError(f"{path}: expected type '{doc_type}' with a '{field}' key")
            documents[(doc_type, normalise(str(document.metadata[field])))] = document
    return documents


def _section(document: Document, heading: str, required: bool = True) -> str:
    for section in document.sections:
        if section.heading.strip().lower() == heading:
            return section.body
    if required:
        raise ValueError(f"{document.source_path}: missing '## {heading.capitalize()}' section")
    return ""


def _project_path(document: Document) -> str:
    try:
        return str(document.source_path.relative_to(DEFAULT_ROOT.parent))
    except ValueError:
        return str(document.source_path)


def _type_heading(content_type: str) -> str:
    """The section heading a content type uses in channel and example files, e.g. "press release"."""

    return _content_type_key(content_type).replace("_", " ")


def _channel_document(channel: str, root: Optional[Path]) -> Document:
    document = _profile_documents(root or DEFAULT_ROOT).get((CHANNEL_PROFILE_TYPE, _channel_key(channel)))
    if document is None:
        raise ValueError(f"Unsupported channel {channel!r}; choose from {', '.join(CHANNELS)}")
    return document


def get_channel_profile(channel: str, root: Optional[Path] = None) -> ChannelProfile:
    """Return a known channel profile or fail with the accepted channel names."""

    document = _channel_document(channel, root)
    content_types = tuple(_content_type_key(str(name)) for name in document.metadata.get("content_types") or ())
    unknown = sorted(set(content_types) - set(CONTENT_TYPES))
    if not content_types or unknown:
        raise ValueError(
            f"{document.source_path}: 'content_types' must list some of {', '.join(CONTENT_TYPES)}"
            + (f"; unknown: {', '.join(unknown)}" if unknown else "")
        )
    return ChannelProfile(
        name=str(document.metadata["channel"]),
        tone=_section(document, "tone"),
        format=_section(document, "format"),
        content_types=content_types,
        source=_project_path(document),
    )


def channel_content_types(channel: str, root: Optional[Path] = None) -> Tuple[str, ...]:
    """Content types offered on a channel, in the order its profile lists them."""

    return get_channel_profile(channel, root).content_types


def channel_type_rules(channel: str, content_type: str, root: Optional[Path] = None) -> str:
    """Rules for one content type on one channel (e.g. a reply on X), or "" when there are none."""

    return _section(_channel_document(channel, root), _type_heading(content_type), required=False)


def channel_examples(channel: str, content_type: str, root: Optional[Path] = None) -> str:
    """Verbatim past examples for one channel and content type, or "" when none are collected."""

    document = _profile_documents(root or DEFAULT_ROOT).get((CHANNEL_EXAMPLES_TYPE, _channel_key(channel)))
    if document is None:
        return ""
    return _section(document, _type_heading(content_type), required=False)


def _content_type_document(content_type: str, root: Optional[Path]) -> Document:
    documents = _profile_documents(root or DEFAULT_ROOT)
    document = documents.get((CONTENT_TYPE_PROFILE_TYPE, _content_type_key(content_type)))
    if document is None:
        raise ValueError(f"Unsupported content type {content_type!r}; choose from {', '.join(CONTENT_TYPES)}")
    return document


def content_type_label(content_type: str, channel: Optional[str] = None, root: Optional[Path] = None) -> str:
    """Human-readable name, e.g. "regular post"; a channel can rename a type for itself."""

    if channel:
        labels = _channel_document(channel, root).metadata.get("content_type_labels") or {}
        if _content_type_key(content_type) in labels:
            return str(labels[_content_type_key(content_type)])
    document = _content_type_document(content_type, root)
    return str(document.metadata.get("label") or _type_heading(content_type))


def content_type_rules(content_type: str, root: Optional[Path] = None) -> str:
    """Return the format rules for one content type."""

    return _section(_content_type_document(content_type, root), "format rules")


def content_type_voice_rules(content_type: str, root: Optional[Path] = None) -> str:
    """Return the voice rules for one content type, or "" when it has none."""

    return _section(_content_type_document(content_type, root), "voice rules", required=False)


def content_type_temperature(content_type: str, root: Optional[Path] = None) -> Optional[float]:
    """Sampling temperature from the profile's frontmatter, or None to use the model default."""

    value = _content_type_document(content_type, root).metadata.get("temperature")
    return None if value is None else float(value)
