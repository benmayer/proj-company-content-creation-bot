"""Streamlit UI for the review-gated Ryanair content pipeline."""

from __future__ import annotations

import hashlib
import hmac
import os
import time
from html import escape
from typing import Any, Optional

import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv

from src.content_pipeline import CANNOT_READ_SCREENSHOT, ContentPipeline, ContentRequest, PipelineError, request_problem
from src.channel_profiles import CHANNELS, channel_content_types, content_type_label
from src.feedback_store import FeedbackStoreError
from src.llm_integration import LLMError
from src.knowledge_base import SelectedContext


SCREENSHOT_TYPES = ["png", "jpg", "jpeg", "webp"]

load_dotenv()  # the password gate reads APP_PASSWORD before any LLM call would load .env

AUTH_COOKIE = "ryanair_auth"
AUTH_DAYS = 7


def _draft_box(draft: str) -> None:
    """Show the draft as light text on a dark background (escaped; <br> keeps it one HTML block)."""
    body = escape(draft.strip()).replace("\n", "<br>")
    st.markdown(
        '<div style="background:#14181f;color:#f3f4f6;padding:1.1rem 1.3rem;border-radius:0.5rem;'
        f'font-size:1.05rem;line-height:1.6;">{body}</div>',
        unsafe_allow_html=True,
    )


def _source_names(context: SelectedContext) -> list[str]:
    return [
        f"{selected.source_kind}: {selected.title} ({selected.document.source_path.name})"
        for selected in (*context.primary, *context.secondary)
    ]


def _request_from_form(channel: str, content_type: str, topic: str, original: str, screenshot: Any) -> ContentRequest:
    is_reply = content_type == "reply"
    return ContentRequest(
        content_type=content_type,
        topic="" if is_reply else topic,
        channel=channel,
        original_content=original if is_reply else "",
        screenshot=screenshot.getvalue() if is_reply and screenshot is not None else b"",
        screenshot_type=screenshot.type if is_reply and screenshot is not None else "",
    )


def _generate(request: ContentRequest) -> None:
    pipeline = ContentPipeline()
    try:
        context = pipeline.monitor(request)
        draft = pipeline.draft(request, context)
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
        iterations=1,
        saved_path="",
        declined="",
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
        draft = pipeline.draft(revised_request, context, feedback)
    except (LLMError, PipelineError, RuntimeError) as exc:
        st.session_state["error"] = str(exc)
        return
    st.session_state.update(
        draft=draft,
        error="",
        feedback="",
        iterations=st.session_state.get("iterations", 1) + 1,
    )


def _approve() -> None:
    pipeline: Optional[ContentPipeline] = st.session_state.get("pipeline")
    request: Optional[ContentRequest] = st.session_state.get("request")
    draft = st.session_state.get("draft", "")
    if not pipeline or not request or not draft:
        st.session_state["error"] = "Generate a draft before approving it."
        return
    try:
        path = pipeline.publish(request, draft, iterations=st.session_state.get("iterations", 1))
    except (OSError, PipelineError, FeedbackStoreError) as exc:
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
        pipeline.record_decline(request, reason, st.session_state.get("draft", ""))
    except (OSError, FeedbackStoreError) as exc:
        st.session_state["error"] = str(exc)
        return
    st.session_state["declined"] = reason


def _auth_token(expected: str, expires: int) -> str:
    """Signed ``<expiry>.<hmac>`` token; changing ``APP_PASSWORD`` invalidates every token."""
    sig = hmac.new(expected.encode(), f"auth:{expires}".encode(), hashlib.sha256).hexdigest()
    return f"{expires}.{sig}"


def _valid_auth_token(token: str, expected: str) -> bool:
    expires, _, _ = token.partition(".")
    if not expires.isdigit() or int(expires) < time.time():
        return False
    return hmac.compare_digest(token.encode(), _auth_token(expected, int(expires)).encode())


def _remember_login(expected: str) -> None:
    """Store a signed token in a browser cookie so a reload does not ask for the password again."""
    token = _auth_token(expected, int(time.time()) + AUTH_DAYS * 86400)
    components.html(
        f"<script>document.cookie = '{AUTH_COOKIE}={token}; max-age={AUTH_DAYS * 86400}; path=/; SameSite=Strict';</script>",
        height=0,
    )


def _password_gate() -> bool:
    """Ask for the shared ``APP_PASSWORD`` before showing the app; True once unlocked.

    Unset locally means open. On Render (which sets ``RENDER``) an unset password fails
    closed, so a missing env var can never expose the LLM quota.
    """
    expected = os.environ.get("APP_PASSWORD", "")
    if not expected:
        if os.environ.get("RENDER"):
            st.error("APP_PASSWORD is not set on this service, so the app is locked.")
            return False
        return True
    if st.session_state.get("unlocked") or _valid_auth_token(st.context.cookies.get(AUTH_COOKIE, ""), expected):
        st.session_state["unlocked"] = True
        if st.session_state.pop("set_cookie", False):
            _remember_login(expected)
        return True
    entered = st.text_input("Password", type="password")
    if entered:
        if hmac.compare_digest(entered.encode(), expected.encode()):
            st.session_state["unlocked"] = True
            st.session_state["set_cookie"] = True
            st.rerun()
        st.error("Wrong password.")
    return False


def main() -> None:
    st.set_page_config(page_title="Ryanair Content Creator", layout="wide")
    st.title("Ryanair Content Creator")
    if not _password_gate():
        return
    st.caption("Draft with approved context, review with a human, then save only approved output.")

    with st.sidebar:
        st.header("Request")
        channel = st.selectbox("Channel", CHANNELS)
        content_type = st.selectbox(
            "Type",
            channel_content_types(channel),
            format_func=lambda value: content_type_label(value, channel).capitalize(),
        )
        is_reply = content_type == "reply"
        topic = original = ""
        screenshot = None
        if is_reply:
            screenshot = st.file_uploader("Screenshot of the post", type=SCREENSHOT_TYPES)
            if screenshot is not None:
                st.image(screenshot, width="stretch")
            original = st.text_area(
                "Or paste the post's text", height=120, help="Links aren't opened; paste the text or upload a screenshot."
            )
        else:
            topic = st.text_area("Topic", placeholder="What should the content communicate?")
        if st.button("Generate", type="primary", use_container_width=True):
            request = _request_from_form(channel, content_type, topic, original, screenshot)
            problem = request_problem(request)
            if problem:
                st.session_state["error"] = problem
            else:
                _generate(request)

    st.subheader("Draft")
    if st.session_state.get("draft"):
        _draft_box(st.session_state["draft"])
        if st.session_state["draft"].strip() == CANNOT_READ_SCREENSHOT:
            st.warning("The model could not read the screenshot. Try a sharper crop, or paste the post's text.")
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
            st.info(
                f"Declined. Later {channel} {content_type_label(content_type, channel)} drafts "
                f"will take this into account: {st.session_state['declined']}"
            )
    else:
        st.info("Complete the request form and select Generate.")
    if st.session_state.get("error"):
        st.error(st.session_state["error"])

    summary, sources = st.columns(2)
    with summary:
        st.subheader("Request summary")
        label = content_type_label(content_type, channel)
        st.write(
            {
                "channel": channel,
                "type": label,
                "post to reply to": original,
                "screenshot": screenshot.name if screenshot is not None else "none",
            }
            if is_reply
            else {"channel": channel, "type": label, "topic": topic}
        )
    with sources:
        context: Optional[SelectedContext] = st.session_state.get("context")
        if context:
            st.subheader("Source documents used")
            st.markdown("\n".join(f"- {name}" for name in _source_names(context)))
            pipeline: Optional[ContentPipeline] = st.session_state.get("pipeline")
            request: Optional[ContentRequest] = st.session_state.get("request")
            if pipeline and request:
                with st.expander("Learned feedback used (style only, not company facts)"):
                    st.text(pipeline.learned_feedback(request).render())


if __name__ == "__main__":
    main()
