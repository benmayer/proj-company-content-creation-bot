"""Channel and content-type rules derived from the primary brand-voice KB."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple


CHANNELS: Tuple[str, ...] = ("LinkedIn", "Instagram", "X", "internal Slack")
CONTENT_TYPES: Tuple[str, ...] = ("reply", "press_release", "post_update", "meme")


@dataclass(frozen=True)
class ChannelProfile:
    """Editorial rules for one channel, with its KB source recorded."""

    name: str
    tone: str
    format: str
    source: str = "knowledge_base/primary/brand_voice.md"


_PROFILES: Dict[str, ChannelProfile] = {
    "linkedin": ChannelProfile(
        "LinkedIn",
        "Clear, professional and human; occasional light humour is welcome, but keep the company context easy to scan.",
        "Use a concise hook, short paragraphs, and explicit company, people, route, investment, technology or operational context when supported.",
    ),
    "instagram": ChannelProfile(
        "Instagram",
        "Lowercase, provocative, visual-first and self-aware; make the punchline land immediately.",
        "Write one short sentence, usually 3–12 words. Use loose grammar, no emojis, no hashtags and no explanation.",
    ),
    "x": ChannelProfile(
        "X",
        "Lowercase, blunt, provocative and topical; sound like a sharp reply, not customer-service copy.",
        "Write one sharp sentence, usually 3–12 words. Use loose grammar, no emojis, no hashtags and no automatic apology.",
    ),
    "internal slack": ChannelProfile(
        "internal Slack",
        "Direct, practical and collaborative; use the brand voice as context but prioritise clarity for colleagues.",
        "Use a short subject-style opener, concise bullets where useful, and a clear action or review question.",
    ),
}


def get_channel_profile(channel: str) -> ChannelProfile:
    """Return a known channel profile or fail with the accepted channel names."""

    key = " ".join(channel.strip().lower().split())
    # ``social`` was the pre-ticket pipeline default; keep old CLI callers working.
    if key == "social":
        key = "linkedin"
    try:
        return _PROFILES[key]
    except KeyError as exc:
        raise ValueError(f"Unsupported channel {channel!r}; choose from {', '.join(CHANNELS)}") from exc


def content_type_label(content_type: str) -> str:
    """Convert a template stem or UI label to a readable content-type name."""

    return content_type.replace("_", " ").strip().lower()


def content_type_rules(content_type: str) -> str:
    """Return format constraints for one supported content type."""

    rules = {
        "reply": "Respond directly to the supplied post or message; address its point before adding a concise brand-relevant angle.",
        "press_release": "Use a factual headline and short news-style paragraphs; include only supplied dates, places, figures, quotes and calls to action.",
        "post_update": "Lead with the update, explain why it matters to the audience, and end with a clear next step when one is supported.",
        "meme": "Set up one recognisable travel moment and deliver a concise, harmless punchline; never joke about protected or vulnerable people.",
    }
    key = content_type.strip().lower().replace(" ", "_")
    if key in {"social_post", "campaign_brief"}:
        return "Keep the output concise, specific and ready for human review."
    try:
        return rules[key]
    except KeyError as exc:
        raise ValueError(f"Unsupported content type {content_type!r}; choose from {', '.join(CONTENT_TYPES)}") from exc
