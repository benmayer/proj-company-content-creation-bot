"""Orchestrate document -> monitor -> brief -> publish -> iterate."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional, Tuple, Union

from src.feedback_store import APPROVED, DECLINED, FeedbackEvent, FeedbackStore, LearnedFeedback
from src.knowledge_base import KnowledgeBase, SelectedContext, SelectedDocument
from src.llm_integration import generate_draft
from src.prompt_templates import render_prompt
from src.channel_profiles import content_type_rules, get_channel_profile

PathLike = Union[str, Path]
ApprovalCallback = Callable[[str], bool]
FeedbackCallback = Callable[[str], str]
DraftGenerator = Callable[..., str]


class PipelineError(RuntimeError):
    """Raised when the pipeline cannot produce a reviewable approved output."""


@dataclass(frozen=True)
class ContentRequest:
    """Inputs accepted by the content pipeline."""

    content_type: str
    product: str
    topic: str
    channel: str = "social"
    original_content: str = ""
    asset_name: str = ""
    asset_text: str = ""


@dataclass(frozen=True)
class PipelineResult:
    """Approved draft and the file written by the pipeline."""

    request: ContentRequest
    draft: str
    output_path: Path
    iterations: int
    selected_context: SelectedContext


def _render_documents(documents: Tuple[SelectedDocument, ...]) -> str:
    if not documents:
        return "(No context selected.)"
    parts = []
    for selected in documents:
        document = selected.document
        parts.append(f"## Source: {selected.title} ({document.source_path.name})")
        for section in document.sections:
            parts.append(f"### {section.heading}\n{section.body}")
    return "\n\n".join(parts)


def _primary_voice_rules(context: SelectedContext) -> str:
    pieces = []
    for selected in context.primary:
        if selected.document.metadata.get("type") in {"brand_voice", "editorial_guardrails"}:
            pieces.append(_render_documents((selected,)))
    return "\n\n".join(pieces) or "Follow the approved primary context and avoid unsupported claims."


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
            request.topic, channel=request.channel, content_type=request.content_type
        )

    def learned_feedback(self, request: ContentRequest) -> LearnedFeedback:
        """Select past approvals and decline reasons for the same channel and type."""
        return self.feedback_store.select(request.channel, request.content_type)

    def brief(self, request: ContentRequest, context: SelectedContext, feedback: str = "") -> str:
        """Render the complete provider-neutral prompt for one iteration."""
        request_text = (
            f"Create {request.content_type} content for product or service: {request.product}. "
            f"Topic: {request.topic}. Channel: {request.channel}."
        )
        if request.original_content:
            request_text += f"\nOriginal post or message to reply to:\n{request.original_content}"
        if request.asset_name:
            request_text += f"\nAn optional asset named '{request.asset_name}' was supplied."
        if request.asset_text:
            request_text += f"\nText extracted from the optional asset:\n{request.asset_text}"
        if feedback:
            request_text += f"\nHuman feedback from the previous draft: {feedback}"
        return render_prompt(
            request.content_type,
            request=request_text,
            primary_context=_render_documents(context.primary),
            secondary_context=_render_documents(context.secondary),
            voice_rules=_primary_voice_rules(context),
            format_limits=(
                f"{get_channel_profile(request.channel).format} "
                f"{content_type_rules(request.content_type)} Keep the result concise and reviewable."
            ),
            channel=request.channel,
            learned_feedback=self.learned_feedback(request).render(),
        )

    def publish(self, request: ContentRequest, draft: str, iterations: int) -> Path:
        """Save an approved draft with a UTC timestamp and request metadata."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        path = self.output_dir / f"{timestamp}_{request.content_type}.md"
        path.write_text(
            "---\n"
            f"content_type: {request.content_type}\n"
            f"product: {request.product}\n"
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
            product=request.product,
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
            prompt = self.brief(request, context, previous_feedback)
            draft = self.draft_generator(prompt, client=llm_client)
            if approve(draft):
                output_path = self.publish(request, draft, iteration)
                return PipelineResult(request, draft, output_path, iteration, context)
            if feedback is None:
                raise PipelineError("Draft rejected; provide feedback to request an iteration.")
            previous_feedback = feedback(draft).strip()
            if not previous_feedback:
                raise PipelineError("Draft rejected without actionable feedback; nothing was saved.")
        raise PipelineError(f"Draft was not approved after {max_iterations} iterations; nothing was saved.")
