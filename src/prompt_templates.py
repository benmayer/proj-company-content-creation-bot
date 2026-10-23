"""Render reusable, content-type-specific prompts from ``templates/``."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Mapping, Tuple, Union

from src.channel_profiles import (
    channel_examples,
    channel_type_rules,
    content_type_label,
    content_type_voice_rules,
    get_channel_profile,
)


PathLike = Union[str, Path]
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TEMPLATES_DIR = PROJECT_ROOT / "templates"
_PLACEHOLDER_RE = re.compile(r"\{\{\s*([a-z][a-z0-9_]*)\s*\}\}")
_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)\s]+\)")
NO_LEARNED_FEEDBACK = "(No learned feedback yet for this channel and type.)"
NO_EXAMPLES = (
    "(No verified examples for this channel and type yet. Follow the voice rules above; "
    "approved drafts under LEARNED FEEDBACK show what reviewers liked.)"
)
NO_GUARDRAILS = "(No guardrails selected; never invent facts.)"


class PromptTemplateError(ValueError):
    """Raised when a prompt template cannot be rendered safely."""


@dataclass(frozen=True)
class Prompt:
    """A rendered prompt: the system instructions and the user message, kept apart."""

    system: str
    user: str

    @property
    def text(self) -> str:
        """Both parts as one string, for display, logging and tests."""
        return f"{self.system}\n\n{self.user}".strip()


@dataclass(frozen=True)
class PromptRequest:
    """All context required to render a content prompt."""

    request: str
    primary_context: str
    secondary_context: str
    voice_rules: str
    format_limits: str


def available_content_types(templates_dir: PathLike = DEFAULT_TEMPLATES_DIR) -> Tuple[str, ...]:
    """Return content types represented by templates, excluding ``system.txt``."""

    root = Path(templates_dir)
    if not root.is_dir():
        raise PromptTemplateError(f"Template directory not found: {root}")
    return tuple(sorted(path.stem for path in root.glob("*.txt") if path.name != "system.txt"))


def _read_template(path: Path) -> str:
    if not path.is_file():
        raise PromptTemplateError(f"Prompt template not found: {path}")
    return path.read_text(encoding="utf-8").strip()


def _render_text(template: str, values: Mapping[str, str], template_name: str) -> str:
    required = set(_PLACEHOLDER_RE.findall(template))
    missing = sorted(required - set(values))
    if missing:
        raise PromptTemplateError(
            f"{template_name}: missing values for placeholders: {', '.join(missing)}"
        )

    rendered = _PLACEHOLDER_RE.sub(lambda match: values[match.group(1)], template)
    unresolved = sorted(set(_PLACEHOLDER_RE.findall(rendered)))
    if unresolved:
        raise PromptTemplateError(
            f"{template_name}: unresolved placeholders: {', '.join(unresolved)}"
        )
    return rendered.strip()


def _without_links(text: str) -> str:
    """Keep a Markdown link's text and drop its URL: provenance for people, noise for the model."""

    return _LINK_RE.sub(r"\1", text)


def _voice_block(channel: str, content_type: str, brand_voice: str) -> str:
    """Voice rules from most to least specific: channel + type, type, channel, brand."""

    profile = get_channel_profile(channel)
    parts = []
    specific = channel_type_rules(channel, content_type)
    if specific:
        parts.append(f"{profile.name}, {content_type_label(content_type, channel)}:\n{specific}")
    type_rules = content_type_voice_rules(content_type)
    if type_rules:
        parts.append(f"Every {content_type_label(content_type)}:\n{type_rules}")
    parts.append(f"{profile.name} in general:\n{profile.tone}")
    parts.append(f"Brand voice everywhere:\n{brand_voice}")
    return "\n\n".join(parts)


def render_prompt(
    content_type: str,
    request: str,
    primary_context: str,
    secondary_context: str,
    voice_rules: str,
    format_limits: str,
    templates_dir: PathLike = DEFAULT_TEMPLATES_DIR,
    channel: str = "LinkedIn",
    learned_feedback: str = NO_LEARNED_FEEDBACK,
    guardrails: str = NO_GUARDRAILS,
) -> Prompt:
    """Render a complete prompt for one content type.

    Content templates are intentionally plain text files. Adding a new content
    type therefore requires adding one ``<content_type>.txt`` file, without
    changing this renderer. Primary and secondary context are separate named
    values so templates cannot accidentally hide their provenance. Learned
    feedback is a third, separately labelled value: style guidance, not fact.

    ``voice_rules`` is the general brand voice. The renderer puts the channel
    and content-type rules from the knowledge base in front of it, and fills
    ``{{examples}}`` with the verbatim past examples for this channel and type.
    """

    if not content_type or Path(content_type).name != content_type:
        raise PromptTemplateError("content_type must be a non-empty template filename stem")

    root = Path(templates_dir)
    system = _read_template(root / "system.txt")
    content_template = _read_template(root / f"{content_type}.txt")
    profile = get_channel_profile(channel)
    values = {
        "request": request,
        "primary_context": _without_links(primary_context),
        "secondary_context": _without_links(secondary_context),
        "guardrails": _without_links(guardrails),
        "voice_rules": _without_links(_voice_block(channel, content_type, voice_rules)),
        "examples": _without_links(channel_examples(channel, content_type)) or NO_EXAMPLES,
        "format_limits": format_limits,
        "learned_feedback": learned_feedback,
        "channel": profile.name,
        "content_type": content_type_label(content_type, channel),
    }
    return Prompt(system, _render_text(content_template, values, f"{content_type}.txt"))


def render_template(
    content_type: str,
    values: Mapping[str, str],
    templates_dir: PathLike = DEFAULT_TEMPLATES_DIR,
) -> str:
    """Render a template using a mapping; useful for custom content types."""

    root = Path(templates_dir)
    system = _read_template(root / "system.txt")
    content_template = _read_template(root / f"{content_type}.txt")
    rendered_content = _render_text(content_template, values, f"{content_type}.txt")
    return "\n\n".join((system, rendered_content)).strip()
