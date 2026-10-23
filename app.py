"""Streamlit UI for the review-gated Ryanair content pipeline."""

from __future__ import annotations

import os
from typing import Any, Callable, Dict, Optional

import streamlit as st

from src.content_pipeline import ContentPipeline, ContentRequest, PipelineError
from src.llm_integration import LLMError, generate_draft
from src.knowledge_base import SelectedContext


CHANNELS = ("LinkedIn", "Instagram", "X", "internal Slack")
CONTENT_TYPES = ("reply", "press release", "post update", "meme")


def _mock_generator(prompt: str, client: object = None) -> str:
    return (
        "Mock draft based on the selected company context.\n\n"
        "HUMAN REVIEW NOTES\n- Confirm wording and claims before approval."
    )


def _generator() -> Callable[..., str]:
    return _mock_generator if st.session_state.get("mock_llm", False) else generate_draft


def _source_names(context: SelectedContext) -> list[str]:
    return [
        f"{selected.source_kind}: {selected.title} ({selected.document.source_path.name})"
        for selected in (*context.primary, *context.secondary)
    ]


def _read_asset(uploaded_file: Any) -> tuple[str, str]:
    if uploaded_file is None:
        return "", ""
    asset_name = uploaded_file.name
    if uploaded_file.type == "text/plain":
        return asset_name, uploaded_file.getvalue().decode("utf-8", errors="replace")
    return asset_name, "(Binary asset retained in memory; inspect it during human review.)"


def _request_from_form(channel: str, content_type: str, product: str, topic: str, original: str, asset: Any) -> ContentRequest:
    asset_name, asset_text = _read_asset(asset)
    return ContentRequest(
        content_type="social_post",
        product=product,
        topic=f"{content_type}: {topic}",
        channel=channel,
        original_content=original,
        asset_name=asset_name,
        asset_text=asset_text,
    )


def _generate(request: ContentRequest) -> None:
    pipeline = ContentPipeline(draft_generator=_generator())
    context = pipeline.monitor(request)
    try:
        draft = pipeline.draft_generator(pipeline.brief(request, context), client=None)
    except (LLMError, PipelineError, RuntimeError) as exc:
        st.session_state["error"] = str(exc)
        return
    st.session_state.update(
        pipeline=pipeline,
        request=request,
        context=context,
        draft=draft,
        feedback="",
        error="",
    )


def _iterate() -> None:
    pipeline: Optional[ContentPipeline] = st.session_state.get("pipeline")
    request: Optional[ContentRequest] = st.session_state.get("request")
    context: Optional[SelectedContext] = st.session_state.get("context")
    feedback = st.session_state.get("feedback", "").strip()
    if not pipeline or not request or not context or not feedback:
        st.session_state["error"] = "Enter feedback before requesting a revised draft."
        return
    revised_request = request
    try:
        draft = pipeline.draft_generator(pipeline.brief(revised_request, context, feedback), client=None)
    except (LLMError, PipelineError, RuntimeError) as exc:
        st.session_state["error"] = str(exc)
        return
    st.session_state.update(draft=draft, error="", feedback="")


def _approve() -> None:
    pipeline: Optional[ContentPipeline] = st.session_state.get("pipeline")
    request: Optional[ContentRequest] = st.session_state.get("request")
    draft = st.session_state.get("draft", "")
    if not pipeline or not request or not draft:
        st.session_state["error"] = "Generate a draft before approving it."
        return
    try:
        path = pipeline.publish(request, draft, iterations=1)
    except (OSError, PipelineError) as exc:
        st.session_state["error"] = str(exc)
        return
    st.session_state["saved_path"] = str(path)


def _decline() -> None:
    pipeline: Optional[ContentPipeline] = st.session_state.get("pipeline")
    request: Optional[ContentRequest] = st.session_state.get("request")
    if not pipeline or not request:
        st.session_state["error"] = "Generate a draft before declining it."
        return
    reason = st.session_state.get("feedback", "").strip() or "No reason supplied."
    try:
        pipeline.record_decline(request, reason)
    except OSError as exc:
        st.session_state["error"] = str(exc)
        return
    st.session_state["declined"] = reason


def main() -> None:
    st.set_page_config(page_title="Ryanair Content Creator", layout="wide")
    st.title("Ryanair Content Creator")
    st.caption("Draft with approved context, review with a human, then save only approved output.")

    with st.sidebar:
        st.header("Request")
        channel = st.selectbox("Channel", CHANNELS)
        content_type = st.selectbox("Type", CONTENT_TYPES)
        product = st.text_input("Product or service", placeholder="e.g. flights")
        topic = st.text_area("Topic", placeholder="What should the content communicate?")
        original = ""
        if content_type == "reply":
            original = st.text_area("Original post or message", height=120)
        asset = st.file_uploader("Optional asset", type=["txt", "png", "jpg", "jpeg", "pdf"])
        st.session_state["mock_llm"] = st.checkbox("Use mocked LLM (no API key)", value=not bool(os.getenv("OPENAI_API_KEY")))
        if st.button("Generate", type="primary", use_container_width=True):
            if not product.strip() or not topic.strip() or (content_type == "reply" and not original.strip()):
                st.session_state["error"] = "Product, topic, and (for replies) the original message are required."
            else:
                _generate(_request_from_form(channel, content_type, product, topic, original, asset))

    left, right = st.columns(2)
    with left:
        st.subheader("Request summary")
        st.write({"channel": channel, "type": content_type, "product": product, "topic": topic})
        context: Optional[SelectedContext] = st.session_state.get("context")
        if context:
            st.subheader("Source documents used")
            st.markdown("\n".join(f"- {name}" for name in _source_names(context)))
    with right:
        st.subheader("Draft")
        if st.session_state.get("draft"):
            st.text_area("Reviewable draft", value=st.session_state["draft"], height=320, disabled=True)
            st.session_state["feedback"] = st.text_area("Give feedback", value=st.session_state.get("feedback", ""), height=100)
            revise, approve, decline = st.columns(3)
            with revise:
                st.button("Revise", on_click=_iterate, use_container_width=True)
            with approve:
                st.button("Approve + save", on_click=_approve, type="primary", use_container_width=True)
            with decline:
                st.button("Decline", on_click=_decline, use_container_width=True)
            if st.session_state.get("saved_path"):
                st.success(f"Approved draft saved to `{st.session_state['saved_path']}`")
            if st.session_state.get("declined"):
                st.info(f"Declined for ticket 19 feedback tracking: {st.session_state['declined']}")
        else:
            st.info("Complete the request form and select Generate.")
    if st.session_state.get("error"):
        st.error(st.session_state["error"])


if __name__ == "__main__":
    main()
