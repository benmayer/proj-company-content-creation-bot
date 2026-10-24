"""Orchestrate document -> monitor -> brief -> publish -> iterate."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import re
from typing import Callable, Optional, Tuple, Union

from src.feedback_store import APPROVED, DECLINED, FeedbackEvent, FeedbackStore, LearnedFeedback, clean_draft
from src.knowledge_base import (
    BRAND_VOICE_TYPE,
    GUARDRAILS_TYPE,
    VOICE_RULE_TYPES,
    KnowledgeBase,
    SelectedContext,
    SelectedDocument,
)
from src.llm_integration import generate_draft
from src.prompt_templates import Prompt, render_prompt
from src.channel_profiles import (
    channel_content_types,
    content_type_label,
    content_type_rules,
    content_type_temperature,
    get_channel_profile,
)

PathLike = Union[str, Path]
ApprovalCallback = Callable[[str], bool]
FeedbackCallback = Callable[[str], str]
DraftGenerator = Callable[..., str]

# Sections that help a human reviewer but only dilute the prompt: source lists,
# reviewer checklists, and platform cues that the channel profiles replace.
_NOT_INJECTED_SECTIONS = frozenset(
    {
        "sources",
        "sources and evidence",
        "review questions",
        "public context",
        "platform cues from the public sample",
        "observation method",
    }
)
_URL_RE = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
_WORD_RE = re.compile(r"\w+")
CANNOT_READ_SCREENSHOT = "CANNOT READ SCREENSHOT"


class PipelineError(RuntimeError):
    """Raised when the pipeline cannot produce a reviewable approved output."""


@dataclass(frozen=True)
class ContentRequest:
    """Inputs accepted by the content pipeline.

    A reply is drafted from the post it answers: pasted ``original_content``, a
    ``screenshot`` of it (image bytes plus MIME type), or both. Every other
    content type needs only a ``topic``.
    """

    content_type: str
    topic: str = ""
    channel: str = "LinkedIn"
    original_content: str = ""
    screenshot: bytes = b""
    screenshot_type: str = ""


@dataclass(frozen=True)
class PipelineResult:
    """Approved draft and the file written by the pipeline."""

    request: ContentRequest
    draft: str
    output_path: Path
    iterations: int
    selected_context: SelectedContext


def is_link_only(text: str) -> bool:
    """True when the text is essentially just a URL, which the model cannot open."""

    return bool(_URL_RE.search(text)) and len(_WORD_RE.findall(_URL_RE.sub(" ", text))) < 3


def request_problem(request: ContentRequest) -> str:
    """Return what is wrong with a request, or "" when it can be drafted."""

    try:
        offered = channel_content_types(request.channel)
    except ValueError as exc:
        return str(exc)
    if request.content_type not in offered:
        labels = ", ".join(content_type_label(name, request.channel) for name in offered)
        return f"{request.channel} does not offer {request.content_type.replace('_', ' ')}; choose from {labels}."
    if request.content_type != "reply":
        return "" if request.topic.strip() else "Enter a topic."
    text = request.original_content.strip()
    if request.screenshot:
        return "" if request.screenshot_type.startswith("image/") else "The screenshot must be an image."
    if not text:
        return "Paste the post you are replying to, or upload a screenshot of it."
    if is_link_only(text):
        return "Links can't be opened. Paste the text of the post, or upload a screenshot of it."
    return ""


def _render_documents(documents: Tuple[SelectedDocument, ...]) -> str:
    if not documents:
        return "(No context selected.)"
    parts = []
    for selected in documents:
        document = selected.document
        parts.append(f"## Source: {selected.title} ({document.source_path.name})")
        for section in document.sections:
            if section.heading.strip().lower() not in _NOT_INJECTED_SECTIONS:
                parts.append(f"### {section.heading}\n{section.body}")
    return "\n\n".join(parts)


def _documents_of_type(context: SelectedContext, doc_type: str) -> Tuple[SelectedDocument, ...]:
    return tuple(selected for selected in context.primary if selected.document.metadata.get("type") == doc_type)


def _reply_request(request: ContentRequest) -> str:
    lines = []
    text = request.original_content.strip()
    if text:
        if _URL_RE.search(text):
            lines.append("Links are not opened; treat any URL in the post as plain text.")
        lines.append(f"POST TO REPLY TO:\n{text}")
    if request.screenshot:
        also = " as well" if text else ""
        lines.append(
            f"The post to reply to is in the attached screenshot{also}. Read it first: who posted it, "
            "what the text says and what any picture shows. Reply to that, not to a guess. "
            f"If you cannot read the screenshot, output only: {CANNOT_READ_SCREENSHOT}"
        )
    return "\n\n".join(lines)


class ContentPipeline:
    """Run the review-gated content workflow."""

    def __init__(
        self,
        knowledge_base: Optional[KnowledgeBase] = None,
        output_dir: PathLike = Path("outputs"),
        draft_generator: DraftGenerator = generate_draft,
        feedback_store: Optional[FeedbackStore] = None,
    ) -> None:
        self.knowledge_base = knowledge_base
        self.output_dir = Path(output_dir)
        self.draft_generator = draft_generator
        self.feedback_store = feedback_store or FeedbackStore.from_env(self.output_dir / "feedback.jsonl")

    def document(self) -> KnowledgeBase:
        """Load both Markdown knowledge bases once."""
        if self.knowledge_base is None:
            self.knowledge_base = KnowledgeBase.load()
        return self.knowledge_base

    def monitor(self, request: ContentRequest) -> SelectedContext:
        """Select deterministic context for the request."""
        return self.document().select(
            request.topic or request.original_content, channel=request.channel, content_type=request.content_type
        )

    def learned_feedback(self, request: ContentRequest) -> LearnedFeedback:
        """Select past approvals and decline reasons for the same channel and type."""
        return self.feedback_store.select(request.channel, request.content_type)

    def prompt(self, request: ContentRequest, context: SelectedContext, feedback: str = "") -> Prompt:
        """Render the complete provider-neutral prompt for one iteration."""
        problem = request_problem(request)
        if problem:
            raise PipelineError(problem)
        if request.content_type == "reply":
            request_text = _reply_request(request)
        else:
            request_text = f"Topic: {request.topic.strip()}"
        if feedback:
            request_text += f"\n\nReviewer feedback on the previous draft (apply it): {feedback}"
        return render_prompt(
            request.content_type,
            request=request_text,
            primary_context=_render_documents(
                tuple(selected for selected in context.primary if selected.document.metadata.get("type") not in VOICE_RULE_TYPES)
            ),
            secondary_context=_render_documents(context.secondary),
            voice_rules=_render_documents(_documents_of_type(context, BRAND_VOICE_TYPE)),
            guardrails=_render_documents(_documents_of_type(context, GUARDRAILS_TYPE)),
            format_limits=f"{get_channel_profile(request.channel).format}\n{content_type_rules(request.content_type)}",
            channel=request.channel,
            learned_feedback=self.learned_feedback(request).render(),
        )

    def brief(self, request: ContentRequest, context: SelectedContext, feedback: str = "") -> str:
        """The full prompt as one string (system + user), for display and inspection."""
        return self.prompt(request, context, feedback).text

    def draft(
        self, request: ContentRequest, context: SelectedContext, feedback: str = "", *, client: object = None
    ) -> str:
        """Generate one draft and return only the message, without labels or review notes."""
        prompt = self.prompt(request, context, feedback)
        images = ((request.screenshot_type, request.screenshot),) if request.screenshot else ()
        return clean_draft(
            self.draft_generator(
                prompt.user,
                client=client,
                system=prompt.system,
                images=images,
                temperature=content_type_temperature(request.content_type),
            )
        )

    def publish(self, request: ContentRequest, draft: str, iterations: int) -> Path:
        """Save an approved draft with a UTC timestamp and request metadata."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        path = self.output_dir / f"{timestamp}_{request.content_type}.md"
        path.write_text(
            "---\n"
            f"content_type: {request.content_type}\n"
            f"topic: {request.topic}\n"
            f"channel: {request.channel}\n"
            f"iterations: {iterations}\n"
            "approved: true\n"
            f"created_at: {timestamp}\n"
            "---\n\n"
            f"{draft.strip()}\n",
            encoding="utf-8",
        )
        self._record(APPROVED, request, draft)
        return path

    def record_decline(self, request: ContentRequest, reason: str, draft: str = "") -> FeedbackEvent:
        """Store a declined draft and its reason so later drafts can avoid it."""
        return self._record(DECLINED, request, draft, reason.strip() or "No reason supplied.")

    def _record(self, outcome: str, request: ContentRequest, draft: str, reason: str = "") -> FeedbackEvent:
        return self.feedback_store.record(
            outcome,
            channel=request.channel,
            content_type=request.content_type,
            topic=request.topic,
            draft=draft,
            reason=reason,
        )

    def run(
        self,
        request: ContentRequest,
        approve: ApprovalCallback,
        feedback: Optional[FeedbackCallback] = None,
        *,
        llm_client: object = None,
        max_iterations: int = 3,
    ) -> PipelineResult:
        """Generate drafts until human approval, then save exactly one output."""
        if max_iterations < 1:
            raise PipelineError("max_iterations must be at least 1")
        context = self.monitor(request)
        previous_feedback = ""
        for iteration in range(1, max_iterations + 1):
            draft = self.draft(request, context, previous_feedback, client=llm_client)
            if approve(draft):
                output_path = self.publish(request, draft, iteration)
                return PipelineResult(request, draft, output_path, iteration, context)
            if feedback is None:
                raise PipelineError("Draft rejected; provide feedback to request an iteration.")
            previous_feedback = feedback(draft).strip()
            if not previous_feedback:
                raise PipelineError("Draft rejected without actionable feedback; nothing was saved.")
        raise PipelineError(f"Draft was not approved after {max_iterations} iterations; nothing was saved.")
