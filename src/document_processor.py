"""Ingest OKF-style Markdown documents into metadata-rich headed sections."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple, Union

import yaml


PathLike = Union[str, Path]
_FRONTMATTER_RE = re.compile(
    r"\A---[ \t]*\n(?P<yaml>.*?)(?:\n|\r\n?)---[ \t]*(?:\n|\Z)",
    re.DOTALL,
)
_HEADING_RE = re.compile(r"^(?P<marks>#{1,6})[ \t]+(?P<title>.*?)[ \t]*#*[ \t]*$")


@dataclass(frozen=True)
class Section:
    """A non-empty Markdown section and the metadata of its source document."""

    heading: str
    body: str
    level: int
    source_path: Path
    metadata: Mapping[str, Any]


@dataclass(frozen=True)
class Document:
    """An ingested document, retaining all frontmatter and its sections."""

    source_path: Path
    metadata: Mapping[str, Any]
    sections: Tuple[Section, ...]


def _split_frontmatter(text: str, source_path: Path) -> Tuple[Dict[str, Any], str]:
    """Return frontmatter and body, raising a useful error for bad input."""

    match = _FRONTMATTER_RE.match(text)
    if not match:
        raise ValueError(f"{source_path}: expected YAML frontmatter delimited by ---")

    raw_metadata = yaml.safe_load(match.group("yaml"))
    if raw_metadata is None:
        raw_metadata = {}
    if not isinstance(raw_metadata, dict):
        raise ValueError(f"{source_path}: frontmatter must be a YAML mapping")

    metadata = dict(raw_metadata)
    document_type = metadata.get("type")
    if not isinstance(document_type, str) or not document_type.strip():
        raise ValueError(f"{source_path}: frontmatter requires a non-empty 'type'")
    return metadata, text[match.end():]


def _headed_sections(body: str, source_path: Path, metadata: Mapping[str, Any]) -> Tuple[Section, ...]:
    """Parse ATX headings while ignoring headings inside fenced code blocks."""

    sections: List[Section] = []
    current_heading: Optional[str] = None
    current_level = 0
    current_lines: List[str] = []
    fenced = False

    def finish_section() -> None:
        if current_heading is None:
            return
        section_body = "\n".join(current_lines).strip()
        if section_body:
            sections.append(
                Section(
                    heading=current_heading,
                    body=section_body,
                    level=current_level,
                    source_path=source_path,
                    metadata=metadata,
                )
            )

    for line in body.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            fenced = not fenced

        heading_match = None if fenced else _HEADING_RE.match(line)
        if heading_match:
            finish_section()
            current_heading = heading_match.group("title").strip()
            current_level = len(heading_match.group("marks"))
            current_lines = []
        elif current_heading is not None:
            current_lines.append(line)

    finish_section()
    return tuple(sections)


def ingest_document(path: PathLike) -> Document:
    """Read and parse one UTF-8 Markdown document.

    Every returned section has a heading, non-empty body, source path, and
    complete frontmatter mapping. Preamble text before the first heading is
    intentionally not returned because the contract is headed sections.
    """

    source_path = Path(path)
    if not source_path.is_file():
        raise FileNotFoundError(f"Markdown document not found: {source_path}")
    if source_path.suffix.lower() != ".md":
        raise ValueError(f"{source_path}: expected a .md Markdown file")

    text = source_path.read_text(encoding="utf-8")
    metadata, body = _split_frontmatter(text, source_path)
    sections = _headed_sections(body, source_path, metadata)
    if not sections:
        raise ValueError(f"{source_path}: document must contain a headed section with a non-empty body")
    return Document(source_path=source_path, metadata=metadata, sections=sections)


def ingest_directory(directory: PathLike) -> List[Document]:
    """Ingest Markdown files in deterministic path order."""

    root = Path(directory)
    if not root.is_dir():
        raise NotADirectoryError(f"Knowledge-base directory not found: {root}")
    return [ingest_document(path) for path in sorted(root.rglob("*.md"))]


def iter_sections(documents: Iterable[Document]) -> Iterable[Section]:
    """Yield sections from documents, preserving document and section order."""

    for document in documents:
        yield from document.sections
