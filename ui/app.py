"""Phase 4 — Streamlit chat UI with Groq rate-limit aware UX."""

from __future__ import annotations

import os
import time
from typing import Any

import httpx
import streamlit as st

API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
DISCLAIMER = "Facts-only. No investment advice."

EXAMPLE_QUESTIONS = [
    "What is the expense ratio of Kotak Large Cap Fund – Direct Growth?",
    "What is the exit load for Kotak Flexicap Fund – Direct Growth?",
    "What is the minimum SIP amount for Kotak Liquid Fund?",
]

st.set_page_config(
    page_title="Kotak Mutual Fund FAQ",
    page_icon="📊",
    layout="centered",
    initial_sidebar_state="expanded",
)


def _fetch_limits() -> dict[str, Any] | None:
    try:
        response = httpx.get(f"{API_BASE_URL}/api/limits", timeout=5.0)
        if response.status_code == 200:
            return response.json()
    except httpx.HTTPError:
        return None
    return None


def _post_chat(message: str) -> tuple[int, dict[str, Any] | str]:
    try:
        response = httpx.post(
            f"{API_BASE_URL}/api/chat",
            json={"message": message},
            timeout=60.0,
        )
        if response.headers.get("content-type", "").startswith("application/json"):
            return response.status_code, response.json()
        return response.status_code, response.text
    except httpx.HTTPError as exc:
        return 0, f"Could not reach API at {API_BASE_URL}. Start it with: uvicorn src.api.main:app --reload"


def _init_session() -> None:
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "last_submit_at" not in st.session_state:
        st.session_state.last_submit_at = 0.0
    if "cooldown_until" not in st.session_state:
        st.session_state.cooldown_until = 0.0


def _can_submit(min_gap: float) -> tuple[bool, float]:
    now = time.time()
    wait_for_cooldown = max(0.0, st.session_state.cooldown_until - now)
    wait_for_gap = max(0.0, min_gap - (now - st.session_state.last_submit_at))
    wait = max(wait_for_cooldown, wait_for_gap)
    return wait <= 0, wait


def _render_limits_sidebar() -> float:
    st.sidebar.header("Groq usage")
    limits = _fetch_limits()
    min_gap = 2.0
    if limits:
        min_gap = float(limits.get("ui_min_seconds_between_requests", 2.0))
        st.sidebar.caption(f"Model: `{limits.get('model', 'openai/gpt-oss-120b')}`")
        remaining = limits.get("remaining", {})
        usage = limits.get("usage", {})
        caps = limits.get("limits", {})
        st.sidebar.metric("Requests / min", f"{usage.get('requests_last_minute', 0)} / {caps.get('requests_per_minute', 30)}")
        st.sidebar.metric("Requests / day", f"{usage.get('requests_last_day', 0)} / {caps.get('requests_per_day', 1000)}")
        st.sidebar.metric("Tokens / min", f"{usage.get('tokens_last_minute', 0)} / {caps.get('tokens_per_minute', 8000)}")
        st.sidebar.metric("Tokens / day", f"{usage.get('tokens_last_day', 0)} / {caps.get('tokens_per_day', 200000)}")
        st.sidebar.progress(
            min(1.0, usage.get("requests_last_minute", 0) / max(1, caps.get("requests_per_minute", 30))),
            text="Minute request budget",
        )
        if remaining.get("requests_minute", 1) == 0:
            st.sidebar.warning("Minute request limit reached. Wait ~60s before retrying.")
    else:
        st.sidebar.warning("API limits unavailable. Is the backend running?")
    st.sidebar.caption("Free-tier guard for openai/gpt-oss-120b on Groq.")
    return min_gap


def _submit_message(message: str, min_gap: float) -> None:
    message = message.strip()
    if not message:
        return

    ok, wait = _can_submit(min_gap)
    if not ok:
        st.warning(f"Please wait {wait:.0f}s before sending another question (rate-limit protection).")
        return

    st.session_state.messages.append({"role": "user", "content": message})
    st.session_state.last_submit_at = time.time()

    status, payload = _post_chat(message)
    if status == 0:
        assistant_text = str(payload)
    elif isinstance(payload, dict):
        assistant_text = payload.get("text", "No response text.")
        if status == 429:
            retry = payload.get("retry_after_seconds") or 60
            st.session_state.cooldown_until = time.time() + float(retry)
            assistant_text = (
                f"{assistant_text}\n\nPlease wait about {int(retry)} seconds before trying again."
            )
        citation = payload.get("citation_url")
        response_type = payload.get("type")
        if citation and response_type not in {"refusal", "performance_refusal", "unsupported", "rate_limited"}:
            assistant_text += f"\n\n[Source]({citation})"
    else:
        assistant_text = f"Unexpected API response ({status}): {payload}"

    st.session_state.messages.append({"role": "assistant", "content": assistant_text})


def main() -> None:
    _init_session()
    min_gap = _render_limits_sidebar()

    st.markdown(
        f"""
        <div style="padding:0.75rem 1rem;border-radius:0.5rem;background:#fff3cd;border:1px solid #ffeeba;margin-bottom:1rem;">
        <strong>{DISCLAIMER}</strong>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.title("Kotak Mutual Fund FAQ")
    st.write(
        "Ask objective, source-backed questions about supported Kotak schemes. "
        "This assistant does not provide investment advice."
    )

    st.subheader("Try an example")
    cols = st.columns(len(EXAMPLE_QUESTIONS))
    for idx, question in enumerate(EXAMPLE_QUESTIONS):
        if cols[idx].button(f"Example {idx + 1}", use_container_width=True):
            _submit_message(question, min_gap)
            st.rerun()

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    prompt = st.chat_input("Ask a factual question about a Kotak scheme…")
    if prompt:
        _submit_message(prompt, min_gap)
        st.rerun()


if __name__ == "__main__":
    main()
