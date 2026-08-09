"""
components/chat_box.py
=======================
Reusable chat rendering for the AI interview conversation.

Usage:
    from components.chat_box import render_chat
    render_chat(st.session_state.messages)
"""

import streamlit as st


def render_chat(messages: list[dict]) -> None:
    """
    Renders a polished chat thread.

    Each message dict looks like:
        {"role": "ai" | "candidate", "content": "text", "meta": {...optional...}}

    AI messages are left-aligned, candidate messages are right-aligned.
    """

    st.markdown('<div class="chat-thread">', unsafe_allow_html=True)

    for msg in messages:
        role = msg.get("role", "ai")
        content = msg.get("content", "")
        meta = msg.get("meta")

        if role == "ai":
            _render_ai_message(content, meta)
        else:
            _render_candidate_message(content)

    st.markdown("</div>", unsafe_allow_html=True)


def _render_ai_message(content: str, meta: dict | None) -> None:
    eval_badge = ""
    if meta and meta.get("score") is not None:
        score = meta["score"]
        eval_badge = f"""
        <div class="eval-pill">
            <span class="eval-dot"></span> Answer Evaluated &nbsp;•&nbsp; {score}/10
        </div>
        """

    st.markdown(
        f"""
        <div class="msg-row msg-row-ai">
            <div class="avatar avatar-ai">🤖</div>
            <div class="bubble bubble-ai">
                <div class="bubble-label">AI Interviewer</div>
                <div class="bubble-text">{content}</div>
                {eval_badge}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_candidate_message(content: str) -> None:
    st.markdown(
        f"""
        <div class="msg-row msg-row-candidate">
            <div class="bubble bubble-candidate">
                <div class="bubble-label">You</div>
                <div class="bubble-text">{content}</div>
            </div>
            <div class="avatar avatar-candidate">👤</div>
        </div>
        """,
        unsafe_allow_html=True,
    )