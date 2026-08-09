"""
pages/interview.py
===================
The live AI interview screen.

Flow per turn:
    Question -> Candidate Answer -> POST /answer -> AI Evaluation -> Next Question

On the final answer, calls POST /finish and navigates to the Report page.
"""

import streamlit as st

from frontend.components.chat_box import render_chat
from components.progress import render_interview_progress
from config import submit_answer, finish_interview


def render() -> None:
    if not st.session_state.interview_started or not st.session_state.session_id:
        _render_empty_state()
        return

    st.markdown('<div class="page-title">AI Technical Interview</div>', unsafe_allow_html=True)

    status_col, _ = st.columns([1, 3])
    with status_col:
        st.markdown(
            '<div class="status-badge"><span class="status-dot"></span> AI Interviewer Online</div>',
            unsafe_allow_html=True,
        )

    st.write("")  # spacing

    render_interview_progress(
        current_question=st.session_state.question_number,
        total_questions=st.session_state.total_questions,
    )

    if st.session_state.interview_finished:
        _render_completion_banner()
        return

    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    render_chat(st.session_state.messages)
    st.markdown("</div>", unsafe_allow_html=True)

    answer = st.chat_input("Explain your answer...")

    if answer:
        _handle_answer_submission(answer)


def _render_empty_state() -> None:
    st.markdown('<div class="page-title">AI Technical Interview</div>', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="glass-card" style="text-align:center; padding:3rem 2rem;">
            <div style="font-size:1.1rem; font-weight:700; margin-bottom:0.5rem;">
                No active interview session
            </div>
            <div style="color:#94A3B8; margin-bottom:1.2rem;">
                Head back to Home and select a candidate to begin.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("🏠 Go to Home", type="primary"):
        st.session_state.page = "Home"
        st.rerun()


def _handle_answer_submission(answer: str) -> None:
    # 1. Add candidate answer to chat immediately
    st.session_state.messages.append({"role": "candidate", "content": answer, "meta": None})

    # 2. Call backend (or mock) to evaluate + get next question
    with st.spinner("AI is evaluating your answer..."):
        response = submit_answer(
            session_id=st.session_state.session_id,
            answer=answer,
            question_number=st.session_state.question_number,
        )

    if not response:
        st.rerun()
        return

    evaluation = response.get("evaluation") or {}
    next_question = response.get("next_question")

    # Attach the evaluation to the *previous* AI question bubble so the score
    # shows right under the question it belongs to.
    for msg in reversed(st.session_state.messages):
        if msg["role"] == "ai":
            msg["meta"] = {"score": evaluation.get("score")}
            break

    if next_question:
        # 3. Show the next AI question
        st.session_state.question_number += 1
        st.session_state.current_question = next_question
        st.session_state.messages.append({"role": "ai", "content": next_question, "meta": None})
        st.rerun()
    else:
        # No more questions -> finish the interview
        with st.spinner("Wrapping up your interview..."):
            report = finish_interview(st.session_state.session_id)

        if report:
            st.session_state.report_data = report
            st.session_state.interview_finished = True
        st.rerun()


def _render_completion_banner() -> None:
    st.markdown(
        """
        <div class="glass-card" style="text-align:center; padding:3rem 2rem;">
            <div style="font-size:2rem; margin-bottom:0.4rem;">🎉</div>
            <div style="font-size:1.3rem; font-weight:800; margin-bottom:0.4rem;">Interview Complete</div>
            <div style="color:#94A3B8; margin-bottom:1.6rem;">
                Great work. Your performance report is ready.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col = st.columns([1, 1, 1])[1]
    with col:
        if st.button("📊 View My Report", type="primary", use_container_width=True):
            st.session_state.page = "Report"
            st.rerun()