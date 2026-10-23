"""Render reusable, content-type-specific prompts from ``templates/``."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Mapping, Tuple, Union

from src.channel_profiles import content_type_label, content_type_rules, get_channel_profile


PathLike = Union[str, Path]
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TEMPLATES_DIR = PROJECT_ROOT / "templates"
_PLACEHOLDER_RE = re.compile(r"\{\{\s*([a-z][a-z0-9_]*)\s*\}\}")


class PromptTemplateError(ValueError):
    """Raised when a prompt template cannot be rendered safely."""


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


def render_prompt(
    content_type: str,
    request: str,
    primary_context: str,
    secondary_context: str,
    voice_rules: str,
    format_limits: str,
    templates_dir: PathLike = DEFAULT_TEMPLATES_DIR,
    channel: str = "LinkedIn",
) -> str:
    """Render a complete prompt for one content type.

    Content templates are intentionally plain text files. Adding a new content
    type therefore requires adding one ``<content_type>.txt`` file, without
    changing this renderer. Primary and secondary context are separate named
    values so templates cannot accidentally hide their provenance.
    """

    if not content_type or Path(content_type).name != content_type:
        raise PromptTemplateError("content_type must be a non-empty template filename stem")

    root = Path(templates_dir)
    system = _read_template(root / "system.txt")
    content_template = _read_template(root / f"{content_type}.txt")
    profile = get_channel_profile(channel)
    values = {
        "request": request,
        "primary_context": primary_context,
        "secondary_context": secondary_context,
        "voice_rules": voice_rules,
        "format_limits": format_limits,
        "channel": profile.name,
        "channel_rules": f"Tone: {profile.tone}\nFormat: {profile.format}\nKB source: {profile.source}",
        "content_type": content_type_label(content_type),
        "content_type_rules": content_type_rules(content_type),
    }
    rendered_content = _render_text(content_template, values, f"{content_type}.txt")
    return "\n\n".join((system, rendered_content)).strip()


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
